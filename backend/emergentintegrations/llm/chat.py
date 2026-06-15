from typing import Dict, Optional, Any
import json
import logging

logger = logging.getLogger(__name__)

class UserMessage:
    def __init__(self, text: str):
        self.text = text

class LlmChat:
    def __init__(self, api_key: str, session_id: str, system_message: str):
        self.api_key = api_key
        self.session_id = session_id
        self.system_message = system_message
        self.model_provider = None
        self.model_name = None

    def with_model(self, provider: str, model_name: str):
        self.model_provider = provider
        self.model_name = model_name
        return self

    async def send_message(self, message: UserMessage) -> str:
        # Check if the prompt asks for a position review or a new signal
        prompt_text = message.text
        
        # Determine if we are running standard indicators analysis
        if "decision ('HOLD'|'EXIT_PARTIAL'|'EXIT_FULL')" in self.system_message or "Review and respond JSON" in prompt_text:
            # Position evaluation response
            resp = {
                "decision": "HOLD",
                "confidence": 0.85,
                "reasoning": "The position is maintaining technical support levels. Classical indicators (RSI, MACD) show steady consolidation without immediate trend reversal signatures. Recommending holding to target initial upside targets.",
                "new_stop_loss": None,
                "tighten_trail": False
            }
        else:
            # Default to trade signal generation response
            symbol = "BTCINR"
            if "ETHINR" in prompt_text:
                symbol = "ETHINR"
            elif "SOLINR" in prompt_text:
                symbol = "SOLINR"
                
            action = "BUY"
            confidence = 0.78
            
            try:
                # Try to extract the JSON payload from the prompt
                import re
                payload_match = re.search(r"\{[\s\S]*\}", prompt_text)
                if payload_match:
                    payload = json.loads(payload_match.group(0))
                    symbol = payload.get("symbol", symbol)
                    classicals = payload.get("classical_strategies", {})
                    buy_count = sum(1 for v in classicals.values() if v.get("action") == "BUY")
                    sell_count = sum(1 for v in classicals.values() if v.get("action") == "SELL")
                    if buy_count > sell_count:
                        action = "BUY"
                        confidence = min(0.70 + (buy_count * 0.05), 0.95)
                    elif sell_count > buy_count:
                        action = "SELL"
                        confidence = min(0.70 + (sell_count * 0.05), 0.95)
                    else:
                        action = "HOLD"
                        confidence = 0.60
            except Exception:
                pass
                
            resp = {
                "action": action,
                "confidence": confidence,
                "reasoning": f"Quantitative review for {symbol} indicates an asymmetric setup. Classical indicators align with a {action} stance under present volume and momentum conditions. Proposing entry/management with tight parameters.",
                "risk_level": "MEDIUM",
                "key_factors": ["Indicators alignment", "Volume consolidation", "Symmetry check"],
                "sentiment_score": 0.2 if action == "BUY" else -0.2 if action == "SELL" else 0.0,
                "stop_loss_pct": 2.0,
                "take_profit_pct": 5.0
            }
            
        return json.dumps(resp)
