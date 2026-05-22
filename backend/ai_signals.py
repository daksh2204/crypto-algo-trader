"""Claude-powered position exit decisions + entry signals (with news + sentiment)."""
import os
import json
import logging
import re
from typing import Dict, Optional
from news_sentiment import get_news_bundle

logger = logging.getLogger(__name__)


def _get_key() -> str:
    return os.environ.get("EMERGENT_LLM_KEY", "")


async def _claude_json(system: str, user_msg: str, session_id: str) -> Dict:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    chat = (
        LlmChat(api_key=_get_key(), session_id=session_id, system_message=system)
        .with_model("anthropic", "claude-sonnet-4-5-20250929")
    )
    resp = await chat.send_message(UserMessage(text=user_msg))
    text = resp if isinstance(resp, str) else str(resp)
    m = re.search(r"\{[\s\S]*\}", text)
    return json.loads(m.group(0)) if m else {}


async def generate_ai_signal(
    symbol: str,
    market: Dict,
    indicators: Dict,
    per_strategy: Dict,
    use_news: bool = True,
) -> Dict:
    try:
        news_ctx = await get_news_bundle(symbol) if use_news else {}
    except Exception:
        news_ctx = {}

    system = (
        "You are a senior quantitative crypto trader. Weigh technicals, classical strategy signals, "
        "market sentiment (fear & greed), trending coins, news, support/resistance, volume, and HTF trend "
        "together to find ASYMMETRIC setups (reward > risk). "
        "Return ONLY JSON: action ('BUY'|'SELL'|'HOLD'), confidence (0..1), "
        "reasoning (<140 words citing aligned factors), risk_level ('LOW'|'MEDIUM'|'HIGH'), "
        "key_factors (array), sentiment_score (-1..1), stop_loss_pct (float — based on volatility/SR not arbitrary), "
        "take_profit_pct (float — based on next resistance). "
        "Be conservative: only BUY/SELL when multiple independent signals agree AND risk/reward ≥ 2."
    )

    headlines_compact = [
        {"t": h["title"], "s": (h.get("summary") or "")[:160]}
        for h in (news_ctx.get("headlines") or [])[:5]
    ]
    fng = news_ctx.get("fear_greed") or {"value": 50, "classification": "Neutral"}
    trending = [t["symbol"] for t in (news_ctx.get("trending_coins") or [])[:8]]

    payload = {
        "symbol": symbol,
        "market": market,
        "indicators": indicators,
        "classical_strategies": {
            k: {"action": v["action"], "confidence": v["confidence"], "reason": v.get("reason", "")}
            for k, v in per_strategy.items()
        },
        "sentiment": {"fear_greed": f'{fng["value"]} ({fng["classification"]})', "trending": trending},
        "recent_news": headlines_compact,
    }
    try:
        data = await _claude_json(system, "Analyze and respond JSON only:\n" + json.dumps(payload, indent=2), f"signal-{symbol}")
        return {
            "action": (data.get("action") or "HOLD").upper(),
            "confidence": float(data.get("confidence", 0.5)),
            "reasoning": data.get("reasoning", "")[:400],
            "risk_level": (data.get("risk_level") or "MEDIUM").upper(),
            "key_factors": data.get("key_factors") or [],
            "sentiment_score": float(data.get("sentiment_score", 0.0)),
            "stop_loss_pct": float(data.get("stop_loss_pct", 2.5)),
            "take_profit_pct": float(data.get("take_profit_pct", 5.0)),
            "news_summary": {
                "fear_greed": fng,
                "headlines_count": len(headlines_compact),
                "trending": trending[:5],
            },
        }
    except Exception as e:
        logger.exception("AI signal error")
        return _hold(f"AI error: {e}")


async def evaluate_position(
    symbol: str,
    position: Dict,
    current_price: float,
    indicators: Dict,
    trend: Dict,
    support_resistance: Dict,
    per_strategy: Dict,
) -> Dict:
    """Claude reviews an OPEN position and decides HOLD / EXIT_FULL / EXIT_PARTIAL."""
    pnl_pct = (current_price - position["entry_price"]) / position["entry_price"] * 100
    system = (
        "You are an active crypto trader managing an OPEN long position. "
        "Decide ONE of: 'HOLD' (let it run), 'EXIT_PARTIAL' (take 50% off, trail rest), 'EXIT_FULL' (close now). "
        "Consider: current P&L, momentum reversal, support/resistance proximity, news/sentiment shift, trade thesis still valid. "
        "Default to HOLD unless clear reason to exit. Take partial profit when near resistance or +3% with weakening momentum. "
        "Exit FULL if: trend reversed, AI thesis broken, hit major resistance, or news turned strongly negative. "
        "Return JSON only: decision ('HOLD'|'EXIT_PARTIAL'|'EXIT_FULL'), confidence (0..1), "
        "reasoning (<100 words), new_stop_loss (price level or null), tighten_trail (bool)."
    )
    payload = {
        "symbol": symbol,
        "entry_price": position["entry_price"],
        "current_price": current_price,
        "pnl_pct": round(pnl_pct, 2),
        "hold_duration_min": _duration_min(position.get("entry_time")),
        "current_stop_loss": position.get("stop_loss"),
        "current_take_profit": position.get("take_profit"),
        "peak_since_entry": position.get("peak", current_price),
        "indicators": indicators,
        "trend": trend,
        "support_resistance": support_resistance,
        "classical_now": {k: {"action": v["action"], "confidence": v["confidence"]} for k, v in per_strategy.items()},
        "already_partial": position.get("partial_taken", False),
    }
    try:
        data = await _claude_json(system, "Review and respond JSON only:\n" + json.dumps(payload, indent=2), f"manage-{symbol}-{position.get('id','x')[:6]}")
        return {
            "decision": (data.get("decision") or "HOLD").upper(),
            "confidence": float(data.get("confidence", 0.5)),
            "reasoning": (data.get("reasoning") or "")[:300],
            "new_stop_loss": data.get("new_stop_loss"),
            "tighten_trail": bool(data.get("tighten_trail", False)),
        }
    except Exception as e:
        logger.warning(f"position eval failed: {e}")
        return {"decision": "HOLD", "confidence": 0, "reasoning": f"AI unavailable ({e})", "new_stop_loss": None, "tighten_trail": False}


def _duration_min(iso_str: Optional[str]) -> int:
    if not iso_str:
        return 0
    try:
        from datetime import datetime, timezone
        t = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return int((datetime.now(timezone.utc) - t).total_seconds() / 60)
    except Exception:
        return 0


def _hold(reason: str) -> Dict:
    return {
        "action": "HOLD", "confidence": 0.0, "reasoning": reason,
        "risk_level": "HIGH", "key_factors": [], "sentiment_score": 0.0,
        "stop_loss_pct": 2.5, "take_profit_pct": 5.0,
    }
