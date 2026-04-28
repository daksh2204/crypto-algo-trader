from fastapi import FastAPI, APIRouter, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from typing import List, Optional
from pathlib import Path
from datetime import datetime, timezone
import os, logging, uuid

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from binance_api import (
    DEFAULT_SYMBOLS, get_all_tickers, get_klines, get_price, get_ticker_24h,
)
from strategies import aggregate_signals, combined_indicators, STRATEGY_REGISTRY
from ai_signals import generate_ai_signal
from bot import TradingBot, get_or_create_portfolio, _log_trade, _save_portfolio

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("algo-trader")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="Algo Crypto Trading")
api = APIRouter(prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

bot = TradingBot(db)

# -------------------- Models --------------------

class BotConfig(BaseModel):
    symbols: Optional[List[str]] = None
    interval: Optional[str] = None
    strategies: Optional[List[str]] = None
    use_ai: Optional[bool] = None
    loop_seconds: Optional[int] = None
    min_confidence: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    position_size_pct: Optional[float] = None
    mode: Optional[str] = None


class ManualTrade(BaseModel):
    symbol: str
    side: str  # BUY | SELL
    quantity_usd: float = Field(gt=0)


# -------------------- Routes --------------------

@api.get("/")
async def root():
    return {"message": "Algo crypto trading backend", "status": "ok"}


@api.get("/market/symbols")
async def market_symbols():
    return {"symbols": DEFAULT_SYMBOLS}


@api.get("/market/tickers")
async def market_tickers(symbols: Optional[str] = None):
    syms = symbols.split(",") if symbols else DEFAULT_SYMBOLS
    try:
        data = await get_all_tickers(syms)
        return {"tickers": data}
    except Exception as e:
        raise HTTPException(502, f"Binance error: {e}")


@api.get("/market/klines/{symbol}")
async def market_klines(symbol: str, interval: str = "1h", limit: int = Query(200, ge=10, le=1000)):
    try:
        data = await get_klines(symbol.upper(), interval, limit)
        return {"symbol": symbol.upper(), "interval": interval, "klines": data}
    except Exception as e:
        raise HTTPException(502, f"Binance error: {e}")


@api.get("/market/ticker/{symbol}")
async def market_ticker(symbol: str):
    try:
        return await get_ticker_24h(symbol.upper())
    except Exception as e:
        raise HTTPException(502, f"Binance error: {e}")


@api.get("/signals/{symbol}")
async def signals(symbol: str, interval: str = "1h", use_ai: bool = True):
    symbol = symbol.upper()
    try:
        klines = await get_klines(symbol, interval, 200)
        if len(klines) < 55:
            raise HTTPException(400, "Not enough data for signals")
        indicators = combined_indicators(klines)
        agg = aggregate_signals(klines, list(STRATEGY_REGISTRY.keys()))
        ai = {"action": "HOLD", "confidence": 0, "reasoning": "AI disabled", "risk_level": "MEDIUM", "key_factors": []}
        if use_ai:
            ai = await generate_ai_signal(
                symbol,
                {"price": klines[-1]["close"]},
                indicators,
                agg["per_strategy"],
            )
        doc = {
            "id": str(uuid.uuid4()),
            "symbol": symbol,
            "price": klines[-1]["close"],
            "action": agg["action"] if agg["action"] == ai["action"] else (agg["action"] if ai["action"] == "HOLD" else ai["action"] if agg["action"] == "HOLD" else "HOLD"),
            "confidence": round((agg["confidence"] + float(ai.get("confidence", 0))) / 2, 2) if use_ai else agg["confidence"],
            "classical": agg,
            "ai": ai,
            "indicators": indicators,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "manual",
        }
        await db.signals.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("signals error")
        raise HTTPException(500, str(e))


@api.get("/signals")
async def list_signals(limit: int = Query(30, ge=1, le=200)):
    docs = await db.signals.find({}, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    return {"signals": docs}


@api.post("/bot/start")
async def bot_start(cfg: BotConfig):
    res = await bot.start(cfg.model_dump(exclude_none=True))
    return res


@api.post("/bot/stop")
async def bot_stop():
    return await bot.stop()


@api.get("/bot/status")
async def bot_status():
    return bot.status()


@api.post("/bot/config")
async def bot_update_config(cfg: BotConfig):
    updates = cfg.model_dump(exclude_none=True)
    bot.config.update(updates)
    return {"ok": True, "config": bot.config}


@api.get("/portfolio")
async def portfolio():
    p = await get_or_create_portfolio(db)
    # compute current market value
    positions = p.get("positions", [])
    total_positions_value = 0.0
    enriched = []
    for pos in positions:
        try:
            cur = await get_price(pos["symbol"])
        except Exception:
            cur = pos["entry_price"]
        value = pos["qty"] * cur
        pnl = (cur - pos["entry_price"]) * pos["qty"]
        pnl_pct = (cur - pos["entry_price"]) / pos["entry_price"] * 100
        total_positions_value += value
        enriched.append({**pos, "current_price": cur, "value": value, "pnl": pnl, "pnl_pct": pnl_pct})
    total_equity = p["balance"] + total_positions_value
    total_return = (total_equity - p["initial_balance"]) / p["initial_balance"] * 100
    return {
        "balance": p["balance"],
        "initial_balance": p["initial_balance"],
        "positions": enriched,
        "total_positions_value": total_positions_value,
        "total_equity": total_equity,
        "total_return_pct": total_return,
    }


@api.post("/portfolio/reset")
async def portfolio_reset():
    await db.portfolio.delete_one({"_id": "main"})
    await db.trades.delete_many({})
    await db.signals.delete_many({})
    p = await get_or_create_portfolio(db)
    return {"ok": True, "balance": p["balance"]}


@api.get("/trades")
async def list_trades(limit: int = Query(100, ge=1, le=500)):
    docs = await db.trades.find({}, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    return {"trades": docs}


@api.get("/metrics")
async def metrics():
    trades = await db.trades.find({}, {"_id": 0}).to_list(5000)
    closed = [t for t in trades if t["type"] in ("CLOSE", "STOP_LOSS", "TAKE_PROFIT")]
    wins = [t for t in closed if t.get("pnl", 0) > 0]
    losses = [t for t in closed if t.get("pnl", 0) <= 0]
    total_pnl = sum(t.get("pnl", 0) for t in closed)
    wl_rate = (len(wins) / len(closed) * 100) if closed else 0
    # Simple max drawdown on cumulative pnl curve
    curve = []
    cum = 0.0
    for t in sorted(closed, key=lambda x: x["timestamp"]):
        cum += t.get("pnl", 0)
        curve.append(cum)
    max_dd = 0.0
    peak = 0.0
    for c in curve:
        if c > peak:
            peak = c
        dd = peak - c
        if dd > max_dd:
            max_dd = dd
    return {
        "total_trades": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": wl_rate,
        "total_pnl": total_pnl,
        "max_drawdown": max_dd,
    }


@api.post("/trades/manual")
async def manual_trade(t: ManualTrade):
    symbol = t.symbol.upper()
    side = t.side.upper()
    if side not in ("BUY", "SELL"):
        raise HTTPException(400, "side must be BUY or SELL")
    price = await get_price(symbol)
    portfolio_doc = await get_or_create_portfolio(db)
    balance = portfolio_doc["balance"]
    positions = {p["symbol"]: p for p in portfolio_doc.get("positions", [])}

    if side == "BUY":
        if symbol in positions:
            raise HTTPException(400, "Already have an open position for this symbol")
        if t.quantity_usd > balance:
            raise HTTPException(400, "Insufficient paper balance")
        qty = t.quantity_usd / price
        new_pos = {
            "symbol": symbol, "qty": qty, "entry_price": price,
            "entry_time": datetime.now(timezone.utc).isoformat(),
            "stop_loss": price * (1 - bot.config["stop_loss_pct"] / 100),
            "take_profit": price * (1 + bot.config["take_profit_pct"] / 100),
        }
        positions[symbol] = new_pos
        await _save_portfolio(db, balance - t.quantity_usd, list(positions.values()))
        doc = await _log_trade(db, symbol, "BUY", qty, price, "MANUAL", {"action": "BUY", "confidence": 1.0})
        return doc
    else:
        if symbol not in positions:
            raise HTTPException(400, "No open position to sell")
        pos = positions[symbol]
        proceeds = pos["qty"] * price
        pnl = (price - pos["entry_price"]) * pos["qty"]
        del positions[symbol]
        await _save_portfolio(db, balance + proceeds, list(positions.values()))
        doc = await _log_trade(db, symbol, "SELL", pos["qty"], price, "MANUAL", {"action": "SELL", "confidence": 1.0}, pnl=pnl, entry_price=pos["entry_price"])
        return doc


app.include_router(api)


@app.on_event("shutdown")
async def shutdown():
    await bot.stop()
    client.close()
