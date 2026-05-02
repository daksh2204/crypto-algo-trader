"""Trading bot — upgraded with safety features.

Safety:
- Trailing stop-loss
- Daily loss circuit breaker
- Min 2-strategy agreement
- Higher default confidence + smaller position size
- In-app alerts written to db.alerts
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone, date
from typing import List, Dict, Optional
from coindcx_api import get_klines, get_price
from strategies import aggregate_signals, combined_indicators
from ai_signals import generate_ai_signal

logger = logging.getLogger(__name__)


class TradingBot:
    def __init__(self, db):
        self.db = db
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.config = {
            "symbols": ["BTCINR", "ETHINR", "SOLINR"],
            "interval": "15m",
            "strategies": ["MA_CROSSOVER", "RSI", "MACD", "BOLLINGER"],
            "use_ai": True,
            "loop_seconds": 60,
            "min_confidence": 0.65,       # safer
            "min_strategies_agree": 2,    # require 2/N agreement
            "stop_loss_pct": 2.0,
            "take_profit_pct": 5.0,
            "trailing_stop": True,
            "position_size_pct": 5.0,     # safer
            "max_daily_loss_pct": 5.0,    # circuit breaker
            "mode": "PAPER",
        }
        self._day: Optional[str] = None
        self._day_start_equity: float = 0.0
        self._circuit_tripped: bool = False

    async def start(self, cfg: Optional[Dict] = None):
        if cfg:
            self.config.update({k: v for k, v in cfg.items() if k in self.config})
        if self.running:
            return {"ok": True, "already_running": True, "config": self.config}
        self.running = True
        self._circuit_tripped = False
        self.task = asyncio.create_task(self._run_loop())
        await _add_alert(self.db, "INFO", "Bot started", f"Watching {len(self.config['symbols'])} pairs with {len(self.config['strategies'])} strategies")
        return {"ok": True, "started": True, "config": self.config}

    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except Exception:
                pass
        await _add_alert(self.db, "INFO", "Bot stopped", "Manual stop")
        return {"ok": True, "stopped": True}

    def status(self):
        return {"running": self.running, "config": self.config, "circuit_tripped": self._circuit_tripped}

    async def _run_loop(self):
        try:
            while self.running:
                # Circuit breaker check
                await self._maybe_trip_circuit()
                if self._circuit_tripped:
                    await asyncio.sleep(self.config["loop_seconds"])
                    continue

                for sym in self.config["symbols"]:
                    try:
                        await self._evaluate_and_trade(sym)
                    except Exception as e:
                        logger.exception(f"eval {sym}: {e}")
                await self._check_open_positions()
                await asyncio.sleep(self.config["loop_seconds"])
        except asyncio.CancelledError:
            logger.info("Bot cancelled")

    async def _maybe_trip_circuit(self):
        today = str(date.today())
        portfolio = await get_or_create_portfolio(self.db)
        current_equity = portfolio["balance"] + sum(
            (await _safe_price(p["symbol"]) or p["entry_price"]) * p["qty"]
            for p in portfolio.get("positions", [])
        )
        if self._day != today:
            self._day = today
            self._day_start_equity = current_equity
            return
        if self._day_start_equity > 0:
            day_pnl_pct = (current_equity - self._day_start_equity) / self._day_start_equity * 100
            if day_pnl_pct <= -self.config["max_daily_loss_pct"] and not self._circuit_tripped:
                self._circuit_tripped = True
                self.running = False
                await _add_alert(self.db, "CRITICAL", "Circuit breaker tripped", f"Daily P&L {day_pnl_pct:.2f}% hit limit of -{self.config['max_daily_loss_pct']}%. Bot auto-stopped.")

    async def _evaluate_and_trade(self, symbol: str):
        klines = await get_klines(symbol, self.config["interval"], 200)
        if len(klines) < 55:
            return
        price = klines[-1]["close"]
        indicators = combined_indicators(klines)
        agg = aggregate_signals(klines, self.config["strategies"])

        # require N strategies to agree
        agree_count = sum(1 for s in agg["per_strategy"].values() if s["action"] == agg["action"])

        ai = {"action": "HOLD", "confidence": 0, "reasoning": "AI disabled", "risk_level": "MEDIUM", "key_factors": []}
        if self.config.get("use_ai"):
            ai = await generate_ai_signal(symbol, {"price": price}, indicators, agg["per_strategy"])

        final_action = agg["action"]
        final_conf = agg["confidence"]
        if ai["action"] == agg["action"] and ai["action"] != "HOLD":
            final_conf = min(1.0, (agg["confidence"] + ai["confidence"]) / 2 + 0.1)
        elif ai["action"] != agg["action"] and ai["action"] != "HOLD" and agg["action"] != "HOLD":
            final_action = "HOLD"
            final_conf = 0.3

        signal_doc = {
            "id": str(uuid.uuid4()),
            "symbol": symbol,
            "price": price,
            "action": final_action,
            "confidence": round(final_conf, 2),
            "strategies_agreed": agree_count,
            "classical": agg,
            "ai": ai,
            "indicators": indicators,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "bot",
        }
        await self.db.signals.insert_one(dict(signal_doc))
        signal_doc.pop("_id", None)

        if (
            final_action in ("BUY", "SELL")
            and final_conf >= self.config["min_confidence"]
            and agree_count >= self.config["min_strategies_agree"]
        ):
            await self._execute_paper_trade(symbol, final_action, price, signal_doc)

    async def _execute_paper_trade(self, symbol: str, action: str, price: float, signal: Dict):
        portfolio = await get_or_create_portfolio(self.db)
        balance = portfolio["balance"]
        positions = {p["symbol"]: p for p in portfolio.get("positions", [])}

        pos = positions.get(symbol)
        if action == "BUY":
            if pos:
                return
            alloc = balance * (self.config["position_size_pct"] / 100.0)
            if alloc < 10:
                return
            qty = alloc / price
            new_pos = {
                "symbol": symbol, "qty": qty, "entry_price": price, "peak": price,
                "entry_time": datetime.now(timezone.utc).isoformat(),
                "stop_loss": price * (1 - self.config["stop_loss_pct"] / 100),
                "take_profit": price * (1 + self.config["take_profit_pct"] / 100),
            }
            positions[symbol] = new_pos
            await _save_portfolio(self.db, balance - alloc, list(positions.values()))
            await _log_trade(self.db, symbol, "BUY", qty, price, "OPEN", signal)
            await _add_alert(self.db, "SUCCESS", f"BUY {symbol}", f"Entered @ ₹{price:.2f} · SL ₹{new_pos['stop_loss']:.2f} · TP ₹{new_pos['take_profit']:.2f}")
        elif action == "SELL" and pos:
            qty = pos["qty"]
            pnl = (price - pos["entry_price"]) * qty
            del positions[symbol]
            await _save_portfolio(self.db, balance + qty * price, list(positions.values()))
            await _log_trade(self.db, symbol, "SELL", qty, price, "CLOSE", signal, pnl=pnl, entry_price=pos["entry_price"])
            await _add_alert(self.db, "SUCCESS" if pnl >= 0 else "WARN", f"SELL {symbol}", f"Closed @ ₹{price:.2f} · P&L ₹{pnl:.2f}")

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
                keep.append(pos); continue

            # Trailing stop — ratchet the stop_loss up as price climbs
            if self.config.get("trailing_stop"):
                peak = max(pos.get("peak", pos["entry_price"]), price)
                pos["peak"] = peak
                trail_sl = peak * (1 - self.config["stop_loss_pct"] / 100)
                if trail_sl > pos["stop_loss"]:
                    pos["stop_loss"] = trail_sl

            if price <= pos["stop_loss"]:
                pnl = (price - pos["entry_price"]) * pos["qty"]
                balance += pos["qty"] * price
                await _log_trade(self.db, pos["symbol"], "SELL", pos["qty"], price, "STOP_LOSS", {}, pnl=pnl, entry_price=pos["entry_price"])
                await _add_alert(self.db, "WARN", f"Stop-loss {pos['symbol']}", f"Exited @ ₹{price:.2f} · P&L ₹{pnl:.2f}")
                changed = True
            elif price >= pos["take_profit"]:
                pnl = (price - pos["entry_price"]) * pos["qty"]
                balance += pos["qty"] * price
                await _log_trade(self.db, pos["symbol"], "SELL", pos["qty"], price, "TAKE_PROFIT", {}, pnl=pnl, entry_price=pos["entry_price"])
                await _add_alert(self.db, "SUCCESS", f"Take-profit {pos['symbol']}", f"Exited @ ₹{price:.2f} · P&L ₹{pnl:.2f}")
                changed = True
            else:
                keep.append(pos)
        if changed:
            await _save_portfolio(self.db, balance, keep)
        else:
            # Persist trailing stop updates
            await _save_portfolio(self.db, balance, keep)


# ---------- persistence helpers ----------

async def _safe_price(symbol: str):
    try:
        return await get_price(symbol)
    except Exception:
        return None


async def get_or_create_portfolio(db) -> Dict:
    doc = await db.portfolio.find_one({"_id": "main"}, {"_id": 0})
    if not doc:
        doc = {
            "_id": "main",
            "balance": 3000.0,
            "initial_balance": 3000.0,
            "currency": "INR",
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
        "id": str(uuid.uuid4()), "symbol": symbol, "side": side, "qty": qty, "price": price,
        "type": kind, "pnl": pnl, "entry_price": entry_price,
        "signal_summary": {
            "action": signal.get("action"), "confidence": signal.get("confidence"),
            "ai_reasoning": (signal.get("ai") or {}).get("reasoning", "")[:400],
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await db.trades.insert_one(dict(doc))
    doc.pop("_id", None)
    return doc


async def _add_alert(db, level: str, title: str, message: str):
    doc = {
        "id": str(uuid.uuid4()), "level": level, "title": title, "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(), "read": False,
    }
    await db.alerts.insert_one(dict(doc))
