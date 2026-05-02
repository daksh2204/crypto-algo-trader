"""Strategy Leaderboard — nightly sweep across pairs × intervals × param sets."""
import asyncio
import logging
from datetime import datetime, timezone
from coindcx_api import get_klines, DEFAULT_SYMBOLS
from backtest import run_backtest

logger = logging.getLogger(__name__)

# Intervals tested
LEADERBOARD_INTERVALS = ["1h", "4h"]

# Param grid — small search to keep runtime manageable
PARAM_GRID = [
    # (min_conf, min_agree, sl_pct, tp_pct, trailing)
    (0.65, 2, 2.0, 5.0, True),
    (0.60, 1, 2.0, 4.0, True),
]


async def run_leaderboard_sweep(db, symbols=None, intervals=None, limit: int = 400, initial_balance: float = 3000.0):
    syms = symbols or DEFAULT_SYMBOLS[:3]
    ivs = intervals or LEADERBOARD_INTERVALS
    results = []
    for sym in syms:
        for iv in ivs:
            try:
                klines = await get_klines(sym, iv, limit)
                if len(klines) < 80:
                    continue
            except Exception as e:
                logger.warning(f"leaderboard fetch {sym} {iv}: {e}")
                continue
            for (mc, ms, sl, tp, tr) in PARAM_GRID:
                try:
                    r = run_backtest(
                        klines=klines,
                        strategies=["MA_CROSSOVER", "RSI", "MACD", "BOLLINGER"],
                        initial_balance=initial_balance,
                        position_size_pct=5.0,
                        stop_loss_pct=sl,
                        take_profit_pct=tp,
                        min_confidence=mc,
                        min_strategies_agree=ms,
                        trailing_stop=tr,
                    )
                    if "error" in r:
                        continue
                    # Composite score — weight return positively, drawdown negatively
                    score = r["total_return_pct"] - 0.5 * r["max_drawdown_pct"] + (r["win_rate_pct"] / 100.0) * 2
                    results.append({
                        "symbol": sym, "interval": iv,
                        "min_confidence": mc, "min_strategies_agree": ms,
                        "stop_loss_pct": sl, "take_profit_pct": tp, "trailing_stop": tr,
                        "total_return_pct": r["total_return_pct"],
                        "win_rate_pct": r["win_rate_pct"],
                        "max_drawdown_pct": r["max_drawdown_pct"],
                        "total_trades": r["total_trades"],
                        "profit_factor": r.get("profit_factor", 0),
                        "score": round(score, 3),
                    })
                except Exception as e:
                    logger.warning(f"leaderboard run {sym}/{iv}: {e}")

    # Persist
    results.sort(key=lambda x: x["score"], reverse=True)
    await db.leaderboard.delete_many({})
    if results:
        await db.leaderboard.insert_many([dict(r) for r in results])
    await db.leaderboard_runs.insert_one({
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "count": len(results),
        "top_score": results[0]["score"] if results else 0,
    })
    return results


async def get_best_config(db):
    """Return the top-ranked backtest config."""
    doc = await db.leaderboard.find_one({}, {"_id": 0}, sort=[("score", -1)])
    return doc
