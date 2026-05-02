"""Backtesting engine — replays historical klines through the same signal logic."""
from typing import List, Dict
import pandas as pd
from strategies import aggregate_signals, STRATEGY_REGISTRY


def run_backtest(
    klines: List[Dict],
    strategies: List[str],
    initial_balance: float = 3000.0,
    position_size_pct: float = 5.0,
    stop_loss_pct: float = 2.0,
    take_profit_pct: float = 5.0,
    min_confidence: float = 0.65,
    min_strategies_agree: int = 2,
    trailing_stop: bool = True,
) -> Dict:
    """Walk forward through klines, generate signals using a sliding window, simulate trades."""
    if len(klines) < 80:
        return {"error": "Need at least 80 candles for backtest"}

    balance = initial_balance
    position = None  # { qty, entry_price, stop_loss, take_profit, peak }
    trades = []
    equity_curve = []

    # Start after warm-up (strategies need ~55 candles)
    warm = 55
    for i in range(warm, len(klines)):
        window = klines[: i + 1]
        price = window[-1]["close"]
        ts = window[-1]["time"]

        # Position management
        if position:
            if trailing_stop:
                position["peak"] = max(position["peak"], price)
                trail_sl = position["peak"] * (1 - stop_loss_pct / 100)
                position["stop_loss"] = max(position["stop_loss"], trail_sl)
            exited = None
            if price <= position["stop_loss"]:
                exited = "STOP_LOSS"
            elif price >= position["take_profit"]:
                exited = "TAKE_PROFIT"
            if exited:
                pnl = (price - position["entry_price"]) * position["qty"]
                balance += position["qty"] * price
                trades.append({
                    "time": ts, "type": exited, "side": "SELL",
                    "price": price, "qty": position["qty"],
                    "entry_price": position["entry_price"], "pnl": pnl,
                })
                position = None

        # Strategy signals — check every bar
        if True:
            agg = aggregate_signals(window, strategies)
            agree_count = sum(1 for s in agg["per_strategy"].values() if s["action"] == agg["action"])
            if not position and agg["action"] == "BUY" and agg["confidence"] >= min_confidence and agree_count >= min_strategies_agree:
                alloc = balance * (position_size_pct / 100)
                if alloc >= 10:
                    qty = alloc / price
                    balance -= alloc
                    position = {
                        "qty": qty, "entry_price": price, "peak": price,
                        "stop_loss": price * (1 - stop_loss_pct / 100),
                        "take_profit": price * (1 + take_profit_pct / 100),
                    }
                    trades.append({
                        "time": ts, "type": "OPEN", "side": "BUY",
                        "price": price, "qty": qty, "entry_price": price, "pnl": 0,
                    })
            elif position and agg["action"] == "SELL" and agg["confidence"] >= min_confidence and agree_count >= min_strategies_agree:
                pnl = (price - position["entry_price"]) * position["qty"]
                balance += position["qty"] * price
                trades.append({
                    "time": ts, "type": "CLOSE", "side": "SELL",
                    "price": price, "qty": position["qty"],
                    "entry_price": position["entry_price"], "pnl": pnl,
                })
                position = None

        current_equity = balance + (position["qty"] * price if position else 0)
        equity_curve.append({"time": ts, "equity": current_equity})

    # Close any open position at end
    if position:
        last_price = klines[-1]["close"]
        pnl = (last_price - position["entry_price"]) * position["qty"]
        balance += position["qty"] * last_price
        trades.append({
            "time": klines[-1]["time"], "type": "END_CLOSE", "side": "SELL",
            "price": last_price, "qty": position["qty"],
            "entry_price": position["entry_price"], "pnl": pnl,
        })

    closed = [t for t in trades if t["type"] in ("STOP_LOSS", "TAKE_PROFIT", "END_CLOSE")]
    wins = [t for t in closed if t["pnl"] > 0]
    losses = [t for t in closed if t["pnl"] <= 0]
    total_pnl = sum(t["pnl"] for t in closed)
    win_rate = len(wins) / len(closed) * 100 if closed else 0
    avg_win = sum(t["pnl"] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t["pnl"] for t in losses) / len(losses) if losses else 0

    # Max drawdown on equity curve
    peak = initial_balance
    max_dd = 0
    for e in equity_curve:
        peak = max(peak, e["equity"])
        dd = (peak - e["equity"]) / peak * 100
        max_dd = max(max_dd, dd)

    return {
        "initial_balance": initial_balance,
        "final_balance": balance,
        "total_return_pct": (balance - initial_balance) / initial_balance * 100,
        "total_trades": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": win_rate,
        "total_pnl": total_pnl,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": (sum(t["pnl"] for t in wins) / abs(sum(t["pnl"] for t in losses))) if losses and sum(t["pnl"] for t in losses) != 0 else 0,
        "max_drawdown_pct": max_dd,
        "trades": trades[-100:],
        "equity_curve": equity_curve[:: max(1, len(equity_curve) // 200)],  # downsample to ~200 points
    }
