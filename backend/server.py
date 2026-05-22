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

from coindcx_api import (
    DEFAULT_SYMBOLS, get_all_tickers, get_klines, get_price, get_ticker_24h, CURRENCY, CURRENCY_SYMBOL,
)
from strategies import aggregate_signals, combined_indicators, STRATEGY_REGISTRY
from ai_signals import generate_ai_signal
from bot import TradingBot, get_or_create_portfolio, _log_trade, _save_portfolio, _add_alert
from backtest import run_backtest
from news_sentiment import get_news_bundle, fetch_coindesk_headlines, fetch_fear_greed, fetch_coingecko_trending
from leaderboard import run_leaderboard_sweep, get_best_config

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
    min_strategies_agree: Optional[int] = None
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    trailing_stop: Optional[bool] = None
    position_size_pct: Optional[float] = None
    max_daily_loss_pct: Optional[float] = None
    max_concurrent_positions: Optional[int] = None
    allow_pyramiding: Optional[bool] = None
    max_positions_per_symbol: Optional[int] = None
    use_news: Optional[bool] = None
    growth_target: Optional[float] = None
    auto_start: Optional[bool] = None
    use_full_capital: Optional[bool] = None
    mode: Optional[str] = None


class ManualTrade(BaseModel):
    symbol: str
    side: str
    quantity_inr: float = Field(gt=0)


class BacktestRequest(BaseModel):
    symbol: str = "BTCINR"
    interval: str = "1h"
    limit: int = Field(500, ge=80, le=1000)
    strategies: List[str] = ["MA_CROSSOVER", "RSI", "MACD", "BOLLINGER"]
    initial_balance: float = 3000.0
    position_size_pct: float = 5.0
    stop_loss_pct: float = 2.0
    take_profit_pct: float = 5.0
    min_confidence: float = 0.65
    min_strategies_agree: int = 2
    trailing_stop: bool = True


class PortfolioReset(BaseModel):
    initial_balance: float = Field(3000.0, ge=100, le=20000)


# -------------------- Routes --------------------

@api.get("/")
async def root():
    return {"message": "Algo crypto trading backend", "status": "ok", "exchange": "coindcx", "currency": CURRENCY}


@api.get("/market/symbols")
async def market_symbols():
    return {"symbols": DEFAULT_SYMBOLS, "currency": CURRENCY, "currency_symbol": CURRENCY_SYMBOL}


@api.get("/market/tickers")
async def market_tickers(symbols: Optional[str] = None):
    syms = symbols.split(",") if symbols else DEFAULT_SYMBOLS
    try:
        return {"tickers": await get_all_tickers(syms), "currency": CURRENCY}
    except Exception as e:
        raise HTTPException(502, f"CoinDCX error: {e}")


@api.get("/market/klines/{symbol}")
async def market_klines(symbol: str, interval: str = "1h", limit: int = Query(200, ge=10, le=1000)):
    try:
        return {"symbol": symbol.upper(), "interval": interval, "klines": await get_klines(symbol.upper(), interval, limit)}
    except Exception as e:
        raise HTTPException(502, f"CoinDCX error: {e}")


@api.get("/market/ticker/{symbol}")
async def market_ticker(symbol: str):
    try:
        return await get_ticker_24h(symbol.upper())
    except Exception as e:
        raise HTTPException(502, f"CoinDCX error: {e}")


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
            ai = await generate_ai_signal(symbol, {"price": klines[-1]["close"]}, indicators, agg["per_strategy"])
        action = agg["action"] if agg["action"] == ai["action"] else (agg["action"] if ai["action"] == "HOLD" else ai["action"] if agg["action"] == "HOLD" else "HOLD")
        doc = {
            "id": str(uuid.uuid4()),
            "symbol": symbol,
            "price": klines[-1]["close"],
            "action": action,
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
    return await bot.start(cfg.model_dump(exclude_none=True))


@api.post("/bot/stop")
async def bot_stop():
    return await bot.stop()


@api.get("/bot/status")
async def bot_status():
    return bot.status()


@api.post("/bot/config")
async def bot_update_config(cfg: BotConfig):
    bot.config.update(cfg.model_dump(exclude_none=True))
    return {"ok": True, "config": bot.config}


@api.get("/portfolio")
async def portfolio():
    p = await get_or_create_portfolio(db)
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
        "currency": p.get("currency", "INR"),
        "positions": enriched,
        "total_positions_value": total_positions_value,
        "total_equity": total_equity,
        "total_return_pct": total_return,
    }


@api.post("/portfolio/reset")
async def portfolio_reset(req: PortfolioReset):
    await db.portfolio.delete_one({"_id": "main"})
    await db.trades.delete_many({})
    await db.signals.delete_many({})
    await db.alerts.delete_many({})
    await db.portfolio.insert_one({
        "_id": "main",
        "balance": req.initial_balance,
        "initial_balance": req.initial_balance,
        "currency": "INR",
        "positions": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await _add_alert(db, "INFO", "Portfolio reset", f"Starting balance: ₹{req.initial_balance:.0f}")
    return {"ok": True, "balance": req.initial_balance}


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
    curve, cum, peak, max_dd = [], 0.0, 0.0, 0.0
    for t in sorted(closed, key=lambda x: x["timestamp"]):
        cum += t.get("pnl", 0)
        curve.append(cum)
        if cum > peak:
            peak = cum
        max_dd = max(max_dd, peak - cum)
    return {
        "total_trades": len(closed), "wins": len(wins), "losses": len(losses),
        "win_rate_pct": wl_rate, "total_pnl": total_pnl, "max_drawdown": max_dd,
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
    positions = list(portfolio_doc.get("positions", []))
    if side == "BUY":
        if any(p["symbol"] == symbol for p in positions):
            raise HTTPException(400, "Already have an open position for this symbol (manual trades don't pyramid)")
        if t.quantity_inr > balance:
            raise HTTPException(400, "Insufficient paper balance")
        qty = t.quantity_inr / price
        new_pos = {
            "id": str(uuid.uuid4()),
            "symbol": symbol, "qty": qty, "entry_price": price, "peak": price,
            "entry_time": datetime.now(timezone.utc).isoformat(),
            "stop_loss": price * (1 - bot.config["stop_loss_pct"] / 100),
            "take_profit": price * (1 + bot.config["take_profit_pct"] / 100),
        }
        positions.append(new_pos)
        await _save_portfolio(db, balance - t.quantity_inr, positions)
        doc = await _log_trade(db, symbol, "BUY", qty, price, "MANUAL", {"action": "BUY", "confidence": 1.0})
        await _add_alert(db, "INFO", f"Manual BUY {symbol}", f"₹{t.quantity_inr:.0f} @ ₹{price:.2f}")
        return doc
    else:
        idx = next((i for i, p in enumerate(positions) if p["symbol"] == symbol), -1)
        if idx < 0:
            raise HTTPException(400, "No open position to sell")
        pos = positions.pop(idx)
        pnl = (price - pos["entry_price"]) * pos["qty"]
        await _save_portfolio(db, balance + pos["qty"] * price, positions)
        doc = await _log_trade(db, symbol, "SELL", pos["qty"], price, "MANUAL", {"action": "SELL", "confidence": 1.0}, pnl=pnl, entry_price=pos["entry_price"])
        await _add_alert(db, "SUCCESS" if pnl >= 0 else "WARN", f"Manual SELL {symbol}", f"P&L ₹{pnl:.2f}")
        return doc


@api.get("/alerts")
async def list_alerts(limit: int = Query(50, ge=1, le=200)):
    docs = await db.alerts.find({}, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    return {"alerts": docs}


@api.post("/alerts/clear")
async def clear_alerts():
    await db.alerts.delete_many({})
    return {"ok": True}


@api.post("/backtest")
async def backtest(req: BacktestRequest):
    try:
        klines = await get_klines(req.symbol.upper(), req.interval, req.limit)
        if len(klines) < 80:
            raise HTTPException(400, "Not enough historical data")
        result = run_backtest(
            klines, req.strategies, req.initial_balance,
            req.position_size_pct, req.stop_loss_pct, req.take_profit_pct,
            req.min_confidence, req.min_strategies_agree, req.trailing_stop,
        )
        if "error" in result:
            raise HTTPException(400, result["error"])
        return {"symbol": req.symbol.upper(), "interval": req.interval, **result}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("backtest error")
        raise HTTPException(500, str(e))


@app.on_event("shutdown")
async def shutdown():
    await bot.stop()
    client.close()


@api.get("/news/{symbol}")
async def news_for_symbol(symbol: str):
    try:
        return await get_news_bundle(symbol.upper())
    except Exception as e:
        raise HTTPException(502, str(e))


@api.get("/news")
async def news_overview():
    try:
        headlines, fng, trending = await fetch_coindesk_headlines(10), await fetch_fear_greed(), await fetch_coingecko_trending(10)
        return {"headlines": headlines, "fear_greed": fng, "trending": trending}
    except Exception as e:
        raise HTTPException(502, str(e))


@api.post("/leaderboard/run")
async def leaderboard_run():
    try:
        results = await run_leaderboard_sweep(db)
        return {"ok": True, "count": len(results), "top": results[:5]}
    except Exception as e:
        logger.exception("leaderboard")
        raise HTTPException(500, str(e))


@api.get("/leaderboard")
async def leaderboard_list(limit: int = Query(20, ge=1, le=100)):
    docs = await db.leaderboard.find({}, {"_id": 0}).sort("score", -1).to_list(limit)
    last_run = await db.leaderboard_runs.find_one({}, {"_id": 0}, sort=[("ran_at", -1)])
    return {"leaderboard": docs, "last_run": last_run}


@api.post("/leaderboard/apply-best")
async def leaderboard_apply_best():
    best = await get_best_config(db)
    if not best:
        raise HTTPException(400, "No leaderboard results — run sweep first")
    cfg = {
        "symbols": [best["symbol"]],
        "interval": best["interval"],
        "min_confidence": best["min_confidence"],
        "min_strategies_agree": best["min_strategies_agree"],
        "stop_loss_pct": best["stop_loss_pct"],
        "take_profit_pct": best["take_profit_pct"],
        "trailing_stop": best["trailing_stop"],
    }
    bot.config.update(cfg)
    await _add_alert(db, "INFO", "Auto-tuned", f"Applied best config: {best['symbol']}/{best['interval']} · score {best['score']}")
    return {"ok": True, "applied": cfg, "best": best}


app.include_router(api)


@app.on_event("startup")
async def startup():
    """Restore saved bot config & auto-start the bot if configured."""
    try:
        await bot.load_persisted_config()
        if bot.config.get("auto_start", True):
            await bot.start()
            logger.info(f"Bot auto-started on app boot: {bot.config['symbols']}")
    except Exception as e:
        logger.exception(f"auto-start failed: {e}")

