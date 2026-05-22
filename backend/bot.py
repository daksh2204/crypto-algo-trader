"""Trading bot — multi-symbol concurrent positions + optional pyramiding."""
import asyncio
import logging
import uuid
from datetime import datetime, timezone, date
from typing import List, Dict, Optional
from coindcx_api import get_klines, get_price
from strategies import (
    aggregate_signals, combined_indicators,
    atr as compute_atr, trend_strength, volume_confirmation, find_support_resistance,
)
from ai_signals import generate_ai_signal, evaluate_position

logger = logging.getLogger(__name__)


class TradingBot:
    def __init__(self, db):
        self.db = db
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.config = {
            "symbols": ["BTCINR", "ETHINR", "SOLINR", "BNBINR"],
            "interval": "15m",
            "strategies": ["MA_CROSSOVER", "RSI", "MACD", "BOLLINGER"],
            "use_ai": True,
            "use_news": True,
            "loop_seconds": 30,                # faster reaction
            "min_confidence": 0.55,            # aggressive
            "min_strategies_agree": 1,
            "stop_loss_pct": 2.5,
            "take_profit_pct": 5.0,
            "trailing_stop": True,
            "position_size_pct": 25.0,         # 25% per trade × 4 slots = 100% capital
            "max_daily_loss_pct": 7.0,
            "max_concurrent_positions": 4,     # use all capital across 4 coins
            "allow_pyramiding": False,
            "max_positions_per_symbol": 1,
            "use_full_capital": True,
            "smart_exits": True,                # AI re-evaluates each open position every cycle
            "use_atr_stops": True,              # SL based on ATR (volatility) not fixed %
            "atr_multiplier": 1.5,              # SL distance = entry - 1.5 × ATR
            "tp1_pct": 3.0,                     # first take-profit (sell 50%) at +3%
            "require_volume_confirm": True,     # need volume > 1.2× avg to enter
            "require_htf_trend": True,          # need 4h trend = up for new BUYs
            "growth_target": 4000.0,
            "auto_start": True,
            "mode": "PAPER",
        }
        self._day: Optional[str] = None
        self._day_start_equity: float = 0.0
        self._circuit_tripped: bool = False
        self._target_hit: bool = False

    async def start(self, cfg: Optional[Dict] = None):
        if cfg:
            self.config.update({k: v for k, v in cfg.items() if k in self.config})
        await self._persist_config()
        if self.running:
            return {"ok": True, "already_running": True, "config": self.config}
        self.running = True
        self._target_hit = False
        self._circuit_tripped = False
        self.task = asyncio.create_task(self._run_loop())
        await _add_alert(self.db, "INFO", "Bot started", f"Watching {len(self.config['symbols'])} pairs · target ₹{self.config['growth_target']:.0f} · {'news-aware' if self.config['use_news'] else 'price-only'}")
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

    async def _persist_config(self):
        await self.db.bot_state.update_one(
            {"_id": "main"},
            {"$set": {"config": self.config, "updated_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )

    async def load_persisted_config(self):
        """Called on backend startup to restore saved config + optionally auto-start."""
        doc = await self.db.bot_state.find_one({"_id": "main"})
        if doc and isinstance(doc.get("config"), dict):
            self.config.update({k: v for k, v in doc["config"].items() if k in self.config})
        return self.config

    def status(self):
        return {
            "running": self.running,
            "config": self.config,
            "circuit_tripped": self._circuit_tripped,
            "target_hit": getattr(self, "_target_hit", False),
        }

    async def _run_loop(self):
        try:
            try:
                await self._tick()
            except Exception:
                logger.exception("first tick failed")
            while self.running:
                await asyncio.sleep(self.config["loop_seconds"])
                if not self.running:
                    break
                try:
                    await self._tick()
                except Exception:
                    logger.exception("tick failed")
        except asyncio.CancelledError:
            logger.info("Bot cancelled")

    async def _tick(self):
        await self._maybe_check_target()
        if self._target_hit:
            return
        await self._maybe_trip_circuit()
        if self._circuit_tripped:
            return
        for sym in self.config["symbols"]:
            try:
                await self._evaluate_and_trade(sym)
            except Exception as e:
                logger.exception(f"eval {sym}: {e}")
        await self._check_open_positions()

    async def _maybe_check_target(self):
        target = self.config.get("growth_target", 0)
        if not target or target <= 0:
            return
        portfolio = await get_or_create_portfolio(self.db)
        positions = portfolio.get("positions", [])
        positions_value = 0.0
        for p in positions:
            cur = await _safe_price(p["symbol"]) or p["entry_price"]
            positions_value += cur * p["qty"]
        equity = portfolio["balance"] + positions_value
        if equity >= target and not self._target_hit:
            self._target_hit = True
            self.running = False
            await _add_alert(self.db, "SUCCESS", "🎉 Growth target hit!", f"Equity ₹{equity:.2f} reached target ₹{target:.0f}. Bot paused — time to share CoinDCX live API keys!")

    async def _maybe_trip_circuit(self):
        today = str(date.today())
        portfolio = await get_or_create_portfolio(self.db)
        positions = portfolio.get("positions", [])
        positions_value = 0.0
        for p in positions:
            cur = await _safe_price(p["symbol"]) or p["entry_price"]
            positions_value += cur * p["qty"]
        current_equity = portfolio["balance"] + positions_value
        if self._day != today:
            self._day = today
            self._day_start_equity = current_equity
            return
        if self._day_start_equity > 0:
            day_pnl_pct = (current_equity - self._day_start_equity) / self._day_start_equity * 100
            if day_pnl_pct <= -self.config["max_daily_loss_pct"] and not self._circuit_tripped:
                self._circuit_tripped = True
                self.running = False
                await _add_alert(self.db, "CRITICAL", "Circuit breaker tripped", f"Daily P&L {day_pnl_pct:.2f}% hit limit. Bot auto-stopped.")

    async def _evaluate_and_trade(self, symbol: str):
        klines = await get_klines(symbol, self.config["interval"], 200)
        if len(klines) < 55:
            return
        price = klines[-1]["close"]
        indicators = combined_indicators(klines)
        agg = aggregate_signals(klines, self.config["strategies"])
        agree_count = sum(1 for s in agg["per_strategy"].values() if s["action"] == agg["action"])

        ai = {"action": "HOLD", "confidence": 0, "reasoning": "AI disabled", "risk_level": "MEDIUM", "key_factors": [], "sentiment_score": 0}
        if self.config.get("use_ai"):
            ai = await generate_ai_signal(symbol, {"price": price}, indicators, agg["per_strategy"], use_news=self.config.get("use_news", True))

        final_action = agg["action"]
        final_conf = agg["confidence"]
        if ai["action"] == agg["action"] and ai["action"] != "HOLD":
            final_conf = min(1.0, (agg["confidence"] + ai["confidence"]) / 2 + 0.1)
        elif ai["action"] != agg["action"] and ai["action"] != "HOLD" and agg["action"] != "HOLD":
            final_action = "HOLD"
            final_conf = 0.3

        # ---- ENTRY QUALITY FILTERS ----
        if final_action == "BUY":
            # Volume confirmation
            if self.config.get("require_volume_confirm") and not volume_confirmation(klines):
                final_action = "HOLD"
                final_conf = 0.3
                ai["reasoning"] = (ai.get("reasoning", "") + " | rejected: low volume")[:400]
            # Higher-timeframe trend filter (only for buys, not sells)
            elif self.config.get("require_htf_trend"):
                try:
                    htf = await get_klines(symbol, "4h", 100)
                    if len(htf) >= 50:
                        htf_trend = trend_strength(htf)
                        if htf_trend["direction"] != "up":
                            final_action = "HOLD"
                            final_conf = 0.3
                            ai["reasoning"] = (ai.get("reasoning", "") + f" | rejected: 4h trend = {htf_trend['direction']}")[:400]
                except Exception:
                    pass

        signal_doc = {
            "id": str(uuid.uuid4()), "symbol": symbol, "price": price,
            "action": final_action, "confidence": round(final_conf, 2),
            "strategies_agreed": agree_count,
            "classical": agg, "ai": ai, "indicators": indicators,
            "timestamp": datetime.now(timezone.utc).isoformat(), "source": "bot",
        }
        await self.db.signals.insert_one(dict(signal_doc))
        signal_doc.pop("_id", None)

        if (
            final_action in ("BUY", "SELL")
            and final_conf >= self.config["min_confidence"]
            and agree_count >= self.config["min_strategies_agree"]
        ):
            await self._execute_paper_trade(symbol, final_action, price, signal_doc, klines)

    async def _execute_paper_trade(self, symbol: str, action: str, price: float, signal: Dict, klines: Optional[List[Dict]] = None):
        portfolio = await get_or_create_portfolio(self.db)
        balance = portfolio["balance"]
        positions = list(portfolio.get("positions", []))

        if action == "BUY":
            total_open = len(positions)
            same_sym = sum(1 for p in positions if p["symbol"] == symbol)
            if total_open >= self.config["max_concurrent_positions"]:
                return
            if same_sym >= 1 and not self.config.get("allow_pyramiding"):
                return
            if same_sym >= self.config.get("max_positions_per_symbol", 1):
                return
            if self.config.get("use_full_capital"):
                remaining_slots = self.config["max_concurrent_positions"] - total_open
                alloc = balance / max(1, remaining_slots)
            else:
                alloc = balance * (self.config["position_size_pct"] / 100.0)
            alloc = min(alloc, balance)
            if alloc < 10:
                return
            qty = alloc / price

            # ---- DYNAMIC STOP-LOSS & TAKE-PROFIT ----
            # ATR-based (volatility-adapted) preferred; AI-suggested second; fixed % fallback
            atr_v = compute_atr(klines or [], 14) if klines else 0.0
            ai_sl_pct = float((signal.get("ai") or {}).get("stop_loss_pct") or self.config["stop_loss_pct"])
            ai_tp_pct = float((signal.get("ai") or {}).get("take_profit_pct") or self.config["take_profit_pct"])

            if self.config.get("use_atr_stops") and atr_v > 0:
                sl_price = price - self.config["atr_multiplier"] * atr_v
                # use AI's TP if it's wider than ATR-derived, else 2× ATR distance
                tp_pct = max(ai_tp_pct, (2 * atr_v / price * 100))
                tp_price = price * (1 + tp_pct / 100)
            else:
                sl_price = price * (1 - ai_sl_pct / 100)
                tp_price = price * (1 + ai_tp_pct / 100)

            tp1_price = price * (1 + self.config["tp1_pct"] / 100)

            new_pos = {
                "id": str(uuid.uuid4()), "symbol": symbol, "qty": qty, "original_qty": qty,
                "entry_price": price, "peak": price,
                "entry_time": datetime.now(timezone.utc).isoformat(),
                "stop_loss": sl_price,
                "take_profit": tp_price,
                "tp1": tp1_price,
                "partial_taken": False,
                "atr_at_entry": atr_v,
                "entry_reasoning": (signal.get("ai") or {}).get("reasoning", "")[:200],
            }
            positions.append(new_pos)
            await _save_portfolio(self.db, balance - alloc, positions)
            await _log_trade(self.db, symbol, "BUY", qty, price, "OPEN", signal)
            await _add_alert(self.db, "SUCCESS", f"BUY {symbol}", f"₹{alloc:.0f} @ ₹{price:.2f} · SL ₹{sl_price:.2f} ({((sl_price-price)/price*100):.2f}%) · TP1 ₹{tp1_price:.2f} · TP ₹{tp_price:.2f}")
        elif action == "SELL":
            idx = next((i for i, p in enumerate(positions) if p["symbol"] == symbol), -1)
            if idx < 0:
                return
            pos = positions.pop(idx)
            pnl = (price - pos["entry_price"]) * pos["qty"]
            await _save_portfolio(self.db, balance + pos["qty"] * price, positions)
            await _log_trade(self.db, symbol, "SELL", pos["qty"], price, "CLOSE", signal, pnl=pnl, entry_price=pos["entry_price"])
            await _add_alert(self.db, "SUCCESS" if pnl >= 0 else "WARN", f"SELL signal {symbol}", f"AI flipped bearish · Closed @ ₹{price:.2f} · P&L ₹{pnl:.2f}")

    async def _check_open_positions(self):
        portfolio = await get_or_create_portfolio(self.db)
        positions = list(portfolio.get("positions", []))
        if not positions:
            return
        balance = portfolio["balance"]
        keep = []

        for pos in positions:
            try:
                klines = await get_klines(pos["symbol"], self.config["interval"], 100)
                price = klines[-1]["close"] if klines else await get_price(pos["symbol"])
            except Exception:
                keep.append(pos); continue

            # ---- 1. Update peak + dynamic trailing stop (ATR-based) ----
            peak = max(pos.get("peak", pos["entry_price"]), price)
            pos["peak"] = peak
            if self.config.get("trailing_stop") and len(klines) > 20:
                atr_v = pos.get("atr_at_entry") or compute_atr(klines, 14)
                if self.config.get("use_atr_stops") and atr_v > 0:
                    trail_sl = peak - self.config["atr_multiplier"] * atr_v
                else:
                    trail_sl = peak * (1 - self.config["stop_loss_pct"] / 100)
                if trail_sl > pos["stop_loss"]:
                    pos["stop_loss"] = trail_sl

            # ---- 2. Hard stop-loss (safety net) ----
            if price <= pos["stop_loss"]:
                pnl = (price - pos["entry_price"]) * pos["qty"]
                balance += pos["qty"] * price
                await _log_trade(self.db, pos["symbol"], "SELL", pos["qty"], price, "STOP_LOSS", {}, pnl=pnl, entry_price=pos["entry_price"])
                await _add_alert(self.db, "WARN", f"Stop-loss {pos['symbol']}", f"Exited @ ₹{price:.2f} · P&L ₹{pnl:.2f}")
                continue

            # ---- 3. Hard take-profit ceiling ----
            if price >= pos["take_profit"]:
                pnl = (price - pos["entry_price"]) * pos["qty"]
                balance += pos["qty"] * price
                await _log_trade(self.db, pos["symbol"], "SELL", pos["qty"], price, "TAKE_PROFIT", {}, pnl=pnl, entry_price=pos["entry_price"])
                await _add_alert(self.db, "SUCCESS", f"Take-profit {pos['symbol']}", f"Exited @ ₹{price:.2f} · P&L ₹{pnl:.2f}")
                continue

            # ---- 4. Trend reversal exit (MACD/RSI flipped against us) ----
            if len(klines) > 50:
                trend = trend_strength(klines)
                if trend.get("reversal"):
                    pnl = (price - pos["entry_price"]) * pos["qty"]
                    balance += pos["qty"] * price
                    await _log_trade(self.db, pos["symbol"], "SELL", pos["qty"], price, "REVERSAL_EXIT", {"action": "SELL", "confidence": 0.7}, pnl=pnl, entry_price=pos["entry_price"])
                    await _add_alert(self.db, "WARN" if pnl < 0 else "SUCCESS", f"Reversal exit {pos['symbol']}", f"MACD/RSI flipped bearish · P&L ₹{pnl:.2f}")
                    continue
            else:
                trend = {}

            # ---- 5. Partial take-profit at +tp1_pct ----
            if not pos.get("partial_taken") and price >= pos["tp1"]:
                half = pos["qty"] * 0.5
                proceeds = half * price
                balance += proceeds
                pos["qty"] -= half
                pos["partial_taken"] = True
                # Move stop to break-even, lock in profit
                pos["stop_loss"] = max(pos["stop_loss"], pos["entry_price"])
                await _log_trade(self.db, pos["symbol"], "SELL", half, price, "TP1_PARTIAL", {}, pnl=(price - pos["entry_price"]) * half, entry_price=pos["entry_price"])
                await _add_alert(self.db, "SUCCESS", f"TP1 partial {pos['symbol']}", f"Sold 50% @ ₹{price:.2f} · SL moved to break-even · letting runner ride")

            # ---- 6. AI re-evaluation (smart exit) ----
            if self.config.get("smart_exits") and self.config.get("use_ai"):
                try:
                    indicators = combined_indicators(klines)
                    agg = aggregate_signals(klines, self.config["strategies"])
                    sr = find_support_resistance(klines, 50)
                    decision = await evaluate_position(pos["symbol"], pos, price, indicators, trend or trend_strength(klines), sr, agg["per_strategy"])
                    if decision["decision"] == "EXIT_FULL" and decision["confidence"] >= 0.55:
                        pnl = (price - pos["entry_price"]) * pos["qty"]
                        balance += pos["qty"] * price
                        await _log_trade(self.db, pos["symbol"], "SELL", pos["qty"], price, "AI_EXIT", {"action": "SELL", "confidence": decision["confidence"], "ai": {"reasoning": decision["reasoning"]}}, pnl=pnl, entry_price=pos["entry_price"])
                        await _add_alert(self.db, "SUCCESS" if pnl >= 0 else "WARN", f"AI exit {pos['symbol']}", f"{decision['reasoning'][:140]} · P&L ₹{pnl:.2f}")
                        continue
                    elif decision["decision"] == "EXIT_PARTIAL" and not pos.get("partial_taken") and decision["confidence"] >= 0.5:
                        half = pos["qty"] * 0.5
                        proceeds = half * price
                        balance += proceeds
                        pos["qty"] -= half
                        pos["partial_taken"] = True
                        pos["stop_loss"] = max(pos["stop_loss"], pos["entry_price"])
                        await _log_trade(self.db, pos["symbol"], "SELL", half, price, "AI_PARTIAL", {}, pnl=(price - pos["entry_price"]) * half, entry_price=pos["entry_price"])
                        await _add_alert(self.db, "SUCCESS", f"AI partial {pos['symbol']}", decision["reasoning"][:140])
                    # Apply AI-suggested stop tightening
                    if decision.get("tighten_trail") and decision.get("new_stop_loss"):
                        try:
                            nsl = float(decision["new_stop_loss"])
                            if pos["entry_price"] < nsl < price and nsl > pos["stop_loss"]:
                                pos["stop_loss"] = nsl
                        except (ValueError, TypeError):
                            pass
                except Exception as e:
                    logger.warning(f"smart-exit {pos['symbol']}: {e}")

            keep.append(pos)

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
            "_id": "main", "balance": 3000.0, "initial_balance": 3000.0,
            "currency": "INR", "positions": [],
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
