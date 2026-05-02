"""Claude Sonnet 4.5 trade-signal analyzer — now with news + sentiment context."""
import os
import json
import logging
import re
from typing import Dict, Optional
from news_sentiment import get_news_bundle

logger = logging.getLogger(__name__)


def _get_key() -> str:
    return os.environ.get("EMERGENT_LLM_KEY", "")


async def generate_ai_signal(
    symbol: str,
    market: Dict,
    indicators: Dict,
    per_strategy: Dict,
    use_news: bool = True,
) -> Dict:
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except Exception as e:
        logger.warning(f"emergentintegrations unavailable: {e}")
        return _hold("AI layer unavailable")

    news_ctx = {}
    if use_news:
        try:
            news_ctx = await get_news_bundle(symbol)
        except Exception as e:
            logger.warning(f"news fetch failed: {e}")

    system = (
        "You are a senior quantitative crypto trading analyst. "
        "Weigh technicals, classical strategy signals, market sentiment (fear & greed), trending coins, and news headlines together. "
        "Return ONLY a strict JSON object with keys: action ('BUY'|'SELL'|'HOLD'), "
        "confidence (0..1 float), reasoning (string, <140 words, cite which factors aligned), "
        "risk_level ('LOW'|'MEDIUM'|'HIGH'), key_factors (array of short strings), "
        "sentiment_score (-1..1), stop_loss_pct (float), take_profit_pct (float). "
        "Be conservative: only recommend BUY/SELL if multiple independent signals agree. Adjust risk_level higher when Fear & Greed is extreme."
    )

    headlines_compact = [
        {"t": h["title"], "s": (h.get("summary") or "")[:160]} for h in (news_ctx.get("headlines") or [])[:5]
    ]
    trending_compact = [t["symbol"] for t in (news_ctx.get("trending_coins") or [])[:8]]
    fng = news_ctx.get("fear_greed") or {"value": 50, "classification": "Neutral"}

    payload = {
        "symbol": symbol,
        "market": market,
        "indicators": indicators,
        "classical_strategies": {
            k: {"action": v["action"], "confidence": v["confidence"], "reason": v.get("reason", "")}
            for k, v in per_strategy.items()
        },
        "sentiment": {
            "fear_greed_index": f'{fng["value"]} ({fng["classification"]})',
            "trending_coins": trending_compact,
        },
        "recent_news": headlines_compact,
    }
    user_msg = (
        "Analyze this crypto setup and respond with the required JSON only.\n\n"
        f"{json.dumps(payload, indent=2)}"
    )
    try:
        chat = (
            LlmChat(api_key=_get_key(), session_id=f"signal-{symbol}", system_message=system)
            .with_model("anthropic", "claude-sonnet-4-5-20250929")
        )
        from emergentintegrations.llm.chat import UserMessage
        resp = await chat.send_message(UserMessage(text=user_msg))
        text = resp if isinstance(resp, str) else str(resp)
        m = re.search(r"\{[\s\S]*\}", text)
        data = json.loads(m.group(0)) if m else {}
        return {
            "action": (data.get("action") or "HOLD").upper(),
            "confidence": float(data.get("confidence", 0.5)),
            "reasoning": data.get("reasoning", text[:400]),
            "risk_level": (data.get("risk_level") or "MEDIUM").upper(),
            "key_factors": data.get("key_factors") or [],
            "sentiment_score": float(data.get("sentiment_score", 0.0)),
            "stop_loss_pct": float(data.get("stop_loss_pct", 2.0)),
            "take_profit_pct": float(data.get("take_profit_pct", 5.0)),
            "news_summary": {
                "fear_greed": fng,
                "headlines_count": len(headlines_compact),
                "trending": trending_compact[:5],
            },
        }
    except Exception as e:
        logger.exception("AI signal error")
        return _hold(f"AI error: {e}")


def _hold(reason: str) -> Dict:
    return {
        "action": "HOLD", "confidence": 0.0, "reasoning": reason,
        "risk_level": "HIGH", "key_factors": [], "sentiment_score": 0.0,
        "stop_loss_pct": 2.0, "take_profit_pct": 5.0,
    }
