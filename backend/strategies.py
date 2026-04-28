"""Technical-analysis based trading strategies.

Each strategy returns dict: { action: BUY|SELL|HOLD, confidence: 0..1, reason, indicators }
"""
from typing import List, Dict
import pandas as pd
import numpy as np


def _to_df(klines: List[Dict]) -> pd.DataFrame:
    return pd.DataFrame(klines)


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _macd(series: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = _ema(series, fast)
    ema_slow = _ema(series, slow)
    macd = ema_fast - ema_slow
    sig = _ema(macd, signal)
    hist = macd - sig
    return macd, sig, hist


def _bollinger(series: pd.Series, period: int = 20, std_mult: float = 2.0):
    mid = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = mid + std_mult * std
    lower = mid - std_mult * std
    return upper, mid, lower


def ma_crossover(klines: List[Dict], fast: int = 20, slow: int = 50) -> Dict:
    df = _to_df(klines)
    if len(df) < slow + 2:
        return {"action": "HOLD", "confidence": 0.0, "reason": "insufficient data"}
    close = df["close"]
    sma_f = close.rolling(fast).mean()
    sma_s = close.rolling(slow).mean()
    prev_diff = sma_f.iloc[-2] - sma_s.iloc[-2]
    curr_diff = sma_f.iloc[-1] - sma_s.iloc[-1]
    indicators = {"sma_fast": float(sma_f.iloc[-1]), "sma_slow": float(sma_s.iloc[-1])}
    if prev_diff < 0 and curr_diff > 0:
        return {"action": "BUY", "confidence": 0.75, "reason": f"Fast SMA({fast}) crossed above Slow SMA({slow}) — bullish trend", "indicators": indicators}
    if prev_diff > 0 and curr_diff < 0:
        return {"action": "SELL", "confidence": 0.75, "reason": f"Fast SMA({fast}) crossed below Slow SMA({slow}) — bearish trend", "indicators": indicators}
    trend = "above" if curr_diff > 0 else "below"
    return {"action": "HOLD", "confidence": 0.3, "reason": f"Fast SMA is {trend} Slow SMA, no crossover", "indicators": indicators}


def rsi_strategy(klines: List[Dict], period: int = 14, oversold: float = 30, overbought: float = 70) -> Dict:
    df = _to_df(klines)
    if len(df) < period + 2:
        return {"action": "HOLD", "confidence": 0.0, "reason": "insufficient data"}
    rsi = _rsi(df["close"], period)
    val = float(rsi.iloc[-1])
    indicators = {"rsi": val}
    if val < oversold:
        conf = min(1.0, (oversold - val) / oversold + 0.5)
        return {"action": "BUY", "confidence": round(conf, 2), "reason": f"RSI={val:.1f} oversold — momentum reversal expected", "indicators": indicators}
    if val > overbought:
        conf = min(1.0, (val - overbought) / (100 - overbought) + 0.5)
        return {"action": "SELL", "confidence": round(conf, 2), "reason": f"RSI={val:.1f} overbought — reversal expected", "indicators": indicators}
    return {"action": "HOLD", "confidence": 0.25, "reason": f"RSI={val:.1f} neutral", "indicators": indicators}


def macd_strategy(klines: List[Dict]) -> Dict:
    df = _to_df(klines)
    if len(df) < 35:
        return {"action": "HOLD", "confidence": 0.0, "reason": "insufficient data"}
    macd, sig, hist = _macd(df["close"])
    prev_h = float(hist.iloc[-2])
    curr_h = float(hist.iloc[-1])
    indicators = {"macd": float(macd.iloc[-1]), "signal": float(sig.iloc[-1]), "histogram": curr_h}
    if prev_h < 0 and curr_h > 0:
        return {"action": "BUY", "confidence": 0.7, "reason": "MACD histogram turned positive — bullish momentum", "indicators": indicators}
    if prev_h > 0 and curr_h < 0:
        return {"action": "SELL", "confidence": 0.7, "reason": "MACD histogram turned negative — bearish momentum", "indicators": indicators}
    return {"action": "HOLD", "confidence": 0.3, "reason": "MACD histogram stable", "indicators": indicators}


def bollinger_strategy(klines: List[Dict]) -> Dict:
    df = _to_df(klines)
    if len(df) < 22:
        return {"action": "HOLD", "confidence": 0.0, "reason": "insufficient data"}
    upper, mid, lower = _bollinger(df["close"])
    price = float(df["close"].iloc[-1])
    u, m, l = float(upper.iloc[-1]), float(mid.iloc[-1]), float(lower.iloc[-1])
    indicators = {"upper": u, "middle": m, "lower": l, "price": price}
    if price <= l:
        return {"action": "BUY", "confidence": 0.7, "reason": f"Price ${price:.2f} touched/broke lower Bollinger Band (${l:.2f}) — oversold", "indicators": indicators}
    if price >= u:
        return {"action": "SELL", "confidence": 0.7, "reason": f"Price ${price:.2f} touched/broke upper Bollinger Band (${u:.2f}) — overbought", "indicators": indicators}
    return {"action": "HOLD", "confidence": 0.25, "reason": "Price within Bollinger Bands — range-bound", "indicators": indicators}


def combined_indicators(klines: List[Dict]) -> Dict:
    """Compute all indicators at once for display."""
    df = _to_df(klines)
    out = {}
    if len(df) >= 50:
        out["sma_20"] = float(df["close"].rolling(20).mean().iloc[-1])
        out["sma_50"] = float(df["close"].rolling(50).mean().iloc[-1])
    if len(df) >= 15:
        out["rsi"] = float(_rsi(df["close"]).iloc[-1])
    if len(df) >= 35:
        macd, sig, hist = _macd(df["close"])
        out["macd"] = float(macd.iloc[-1])
        out["macd_signal"] = float(sig.iloc[-1])
        out["macd_hist"] = float(hist.iloc[-1])
    if len(df) >= 22:
        u, m, l = _bollinger(df["close"])
        out["bb_upper"] = float(u.iloc[-1])
        out["bb_middle"] = float(m.iloc[-1])
        out["bb_lower"] = float(l.iloc[-1])
    return out


STRATEGY_REGISTRY = {
    "MA_CROSSOVER": ma_crossover,
    "RSI": rsi_strategy,
    "MACD": macd_strategy,
    "BOLLINGER": bollinger_strategy,
}


def aggregate_signals(klines: List[Dict], enabled: List[str]) -> Dict:
    """Combine active strategies into a single recommendation by majority + confidence."""
    signals = {}
    buy_conf = 0.0
    sell_conf = 0.0
    for name in enabled:
        fn = STRATEGY_REGISTRY.get(name)
        if not fn:
            continue
        s = fn(klines)
        signals[name] = s
        if s["action"] == "BUY":
            buy_conf += s["confidence"]
        elif s["action"] == "SELL":
            sell_conf += s["confidence"]
    if buy_conf > sell_conf and buy_conf > 0.5:
        action = "BUY"
        conf = min(1.0, buy_conf / max(len(enabled), 1))
    elif sell_conf > buy_conf and sell_conf > 0.5:
        action = "SELL"
        conf = min(1.0, sell_conf / max(len(enabled), 1))
    else:
        action = "HOLD"
        conf = 0.3
    return {"action": action, "confidence": round(conf, 2), "per_strategy": signals}
