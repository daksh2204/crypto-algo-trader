"""Trading bot engine — runs in background, evaluates strategies, executes paper trades."""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Optional
from binance_api import get_klines, get_price
from strategies import aggregate_signals, combined_indicators
from ai_signals import generate_ai_signal

logger = logging.getLogger(__name__)


class TradingBot:
    def __init__(self, db):
        self.db = db
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.config = {
            "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
            "interval": "15m",
            "strategies": ["MA_CROSSOVER", "RSI", "MACD", "BOLLINGER"],
            "use_ai": True,
            "loop_seconds": 60,
            "min_confidence": 0.55,
            "stop_loss_pct": 2.0,
            "take_profit_pct": 5.0,
            "position_size_pct": 10.0,  # % of balance per trade
            "mode": "PAPER",  # PAPER | LIVE (LIVE not executed here)
        }

    async def start(self, cfg: Optional[Dict] = None):
        if cfg:
            self.config.update({k: v for k, v in cfg.items() if k in self.config})
        if self.running:
            return {"ok": True, "already_running": True, "config": self.config}
        self.running = True
        self.task = asyncio.create_task(self._run_loop())
        logger.info(f"Bot started: {self.config}")
        return {"ok": True, "started": True, "config": self.config}

    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except Exception:
                pass
        logger.info("Bot stopped")
        return {"ok": True, "stopped": True}

    def status(self):
        return {"running": self.running, "config": self.config}

    async def _run_loop(self):
        try:
            while self.running:
                for sym in self.config["symbols"]:
                    try:
                        await self._evaluate_and_trade(sym)
                    except Exception as e:
                        logger.exception(f"eval {sym}: {e}")
                # also check stop-loss / take-profit on open positions
                await self._check_open_positions()
                await asyncio.sleep(self.config["loop_seconds"])
        except asyncio.CancelledError:
            logger.info("Bot loop cancelled")

    async def _evaluate_and_trade(self, symbol: str):
        klines = await get_klines(symbol, self.config["interval"], 200)
        if len(klines) < 55:
            return
        price = klines[-1]["close"]
        indicators = combined_indicators(klines)
        agg = aggregate_signals(klines, self.config["strategies"])
        ai = {"action": "HOLD", "confidence": 0, "reasoning": "AI disabled", "risk_level": "MEDIUM", "key_factors": []}
        if self.config.get("use_ai"):
            ai = await generate_ai_signal(
                symbol,
                {"price": price, "change_pct": 0},
                indicators,
                agg["per_strategy"],
            )

        # final action: require classical agg + AI to agree (or AI alone with high confidence)
        final_action = agg["action"]
        final_conf = agg["confidence"]
        if ai["action"] == agg["action"] and ai["action"] != "HOLD":
            final_conf = min(1.0, (agg["confidence"] + ai["confidence"]) / 2 + 0.1)
        elif ai["action"] != "HOLD" and agg["action"] == "HOLD" and ai["confidence"] > 0.75:
            final_action = ai["action"]
            final_conf = ai["confidence"]
        elif ai["action"] != agg["action"] and ai["action"] != "HOLD" and agg["action"] != "HOLD":
            final_action = "HOLD"
            final_conf = 0.3

        signal_doc = {
            "id": str(uuid.uuid4()),
            "symbol": symbol,
            "price": price,
            "action": final_action,
            "confidence": round(final_conf, 2),
            "classical": agg,
            "ai": ai,
            "indicators": indicators,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "bot",
        }
        await self.db.signals.insert_one(dict(signal_doc))
        signal_doc.pop("_id", None)

        if final_action in ("BUY", "SELL") and final_conf >= self.config["min_confidence"]:
            await self._execute_paper_trade(symbol, final_action, price, signal_doc)

    async def _execute_paper_trade(self, symbol: str, action: str, price: float, signal: Dict):
        portfolio = await get_or_create_portfolio(self.db)
        balance = portfolio["balance"]
        positions = {p["symbol"]: p for p in portfolio.get("positions", [])}

        pos = positions.get(symbol)
        if action == "BUY":
            if pos:
                return  # already long — skip
            alloc = balance * (self.config["position_size_pct"] / 100.0)
            if alloc < 10:
                return
            qty = alloc / price
            new_balance = balance - alloc
            new_pos = {
                "symbol": symbol,
                "qty": qty,
                "entry_price": price,
                "entry_time": datetime.now(timezone.utc).isoformat(),
                "stop_loss": price * (1 - self.config["stop_loss_pct"] / 100),
                "take_profit": price * (1 + self.config["take_profit_pct"] / 100),
            }
            positions[symbol] = new_pos
            await _save_portfolio(self.db, new_balance, list(positions.values()))
            await _log_trade(self.db, symbol, "BUY", qty, price, "OPEN", signal)
        elif action == "SELL":
            if not pos:
                return  # no long to close — skip (no shorting in paper MVP)
            qty = pos["qty"]
            proceeds = qty * price
            pnl = (price - pos["entry_price"]) * qty
            new_balance = balance + proceeds
            del positions[symbol]
            await _save_portfolio(self.db, new_balance, list(positions.values()))
            await _log_trade(self.db, symbol, "SELL", qty, price, "CLOSE", signal, pnl=pnl, entry_price=pos["entry_price"])

    async def _check_open_positions(self):
        portfolio = await get_or_create_portfolio(self.db)
        positions = portfolio.get("positions", [])
        if not positions:
            return
        changed = False
        balance = portfolio["balance"]
        keep = []
        for pos in positions:
            try:
                price = await get_price(pos["symbol"])
            except Exception:
                keep.append(pos)
                continue
            if price <= pos["stop_loss"]:
                pnl = (price - pos["entry_price"]) * pos["qty"]
                balance += pos["qty"] * price
                await _log_trade(self.db, pos["symbol"], "SELL", pos["qty"], price, "STOP_LOSS", {}, pnl=pnl, entry_price=pos["entry_price"])
                changed = True
            elif price >= pos["take_profit"]:
                pnl = (price - pos["entry_price"]) * pos["qty"]
                balance += pos["qty"] * price
                await _log_trade(self.db, pos["symbol"], "SELL", pos["qty"], price, "TAKE_PROFIT", {}, pnl=pnl, entry_price=pos["entry_price"])
                changed = True
            else:
                keep.append(pos)
        if changed:
            await _save_portfolio(self.db, balance, keep)


# ---------- persistence helpers ----------

async def get_or_create_portfolio(db) -> Dict:
    doc = await db.portfolio.find_one({"_id": "main"}, {"_id": 0})
    if not doc:
        doc = {
            "_id": "main",
            "balance": 10000.0,
            "initial_balance": 10000.0,
            "positions": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.portfolio.insert_one(doc)
        doc.pop("_id", None)
    return doc


async def _save_portfolio(db, balance: float, positions: List[Dict]):
    await db.portfolio.update_one(
        {"_id": "main"},
        {"$set": {"balance": balance, "positions": positions, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )


async def _log_trade(db, symbol: str, side: str, qty: float, price: float, kind: str, signal: Dict, pnl: float = 0.0, entry_price: float = 0.0):
    doc = {
        "id": str(uuid.uuid4()),
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "price": price,
        "type": kind,  # OPEN | CLOSE | STOP_LOSS | TAKE_PROFIT | MANUAL
        "pnl": pnl,
        "entry_price": entry_price,
        "signal_summary": {
            "action": signal.get("action"),
            "confidence": signal.get("confidence"),
            "ai_reasoning": (signal.get("ai") or {}).get("reasoning", "")[:400],
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await db.trades.insert_one(dict(doc))
    doc.pop("_id", None)
    return doc
