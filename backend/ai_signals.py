"""Claude Sonnet 4.5 powered trade-signal analyzer using Emergent LLM key."""
import os
import json
import logging
import re
from typing import Dict

logger = logging.getLogger(__name__)


def _get_key() -> str:
    return os.environ.get("EMERGENT_LLM_KEY", "")


async def generate_ai_signal(symbol: str, market: Dict, indicators: Dict, per_strategy: Dict) -> Dict:
    """Return { action, confidence, reasoning, risk_level, key_factors }."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except Exception as e:
        logger.warning(f"emergentintegrations unavailable: {e}")
        return {
            "action": "HOLD",
            "confidence": 0.0,
            "reasoning": "AI layer unavailable.",
            "risk_level": "MEDIUM",
            "key_factors": [],
        }

    system = (
        "You are a senior quantitative crypto trading analyst. "
        "Analyze the provided market data, technical indicators, and classical strategy signals. "
        "Return ONLY a strict JSON object with keys: action ('BUY'|'SELL'|'HOLD'), "
        "confidence (0..1 float), reasoning (string, <120 words), risk_level ('LOW'|'MEDIUM'|'HIGH'), "
        "key_factors (array of short strings), stop_loss_pct (float), take_profit_pct (float). "
        "Be conservative: only recommend BUY/SELL if multiple signals align."
    )
    user_payload = {
        "symbol": symbol,
        "market": market,
        "indicators": indicators,
        "classical_strategies": {k: {"action": v["action"], "confidence": v["confidence"], "reason": v.get("reason", "")} for k, v in per_strategy.items()},
    }
    user_msg = (
        f"Analyze this crypto trade setup and respond in the required JSON only:\n"
        f"{json.dumps(user_payload, indent=2)}"
    )
    try:
        chat = (
            LlmChat(api_key=_get_key(), session_id=f"signal-{symbol}", system_message=system)
            .with_model("anthropic", "claude-sonnet-4-5-20250929")
        )
        resp = await chat.send_message(UserMessage(text=user_msg))
        text = resp if isinstance(resp, str) else str(resp)
        m = re.search(r"\{[\s\S]*\}", text)
        data = json.loads(m.group(0)) if m else {}
        return {
            "action": (data.get("action") or "HOLD").upper(),
            "confidence": float(data.get("confidence", 0.5)),
            "reasoning": data.get("reasoning", text[:300]),
            "risk_level": (data.get("risk_level") or "MEDIUM").upper(),
            "key_factors": data.get("key_factors") or [],
            "stop_loss_pct": float(data.get("stop_loss_pct", 2.0)),
            "take_profit_pct": float(data.get("take_profit_pct", 5.0)),
        }
    except Exception as e:
        logger.exception("AI signal error")
        return {
            "action": "HOLD",
            "confidence": 0.0,
            "reasoning": f"AI error: {e}",
            "risk_level": "HIGH",
            "key_factors": [],
        }
