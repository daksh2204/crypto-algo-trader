"""CoinDCX public market data client (INR pairs, no auth)."""
import httpx
from typing import List, Dict, Optional

PUBLIC_BASE = "https://public.coindcx.com"
API_BASE = "https://api.coindcx.com"

# Popular INR pairs on CoinDCX (symbol = <COIN>INR)
DEFAULT_SYMBOLS = [
    "BTCINR", "ETHINR", "SOLINR", "BNBINR",
    "XRPINR", "DOGEINR", "ADAINR", "MATICINR",
]

CURRENCY = "INR"
CURRENCY_SYMBOL = "₹"


def _pair_for(symbol: str) -> str:
    """Convert display symbol (BTCINR) → CoinDCX pair (B-BTC_INR)."""
    sym = symbol.upper().replace("INR", "")
    return f"I-{sym}_INR"


async def _get(url: str, params: Optional[dict] = None) -> dict:
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(url, params=params or {})
        r.raise_for_status()
        return r.json()


async def get_all_tickers(symbols: List[str]) -> List[Dict]:
    data = await _get(f"{API_BASE}/exchange/ticker")
    wanted = set(symbols)
    out = []
    for d in data:
        mk = d.get("market")
        if mk in wanted:
            try:
                out.append({
                    "symbol": mk,
                    "price": float(d.get("last_price", 0) or 0),
                    "change_pct": float(d.get("change_24_hour", 0) or 0),
                    "high": float(d.get("high", 0) or 0),
                    "low": float(d.get("low", 0) or 0),
                    "volume": float(d.get("volume", 0) or 0),
                    "quote_volume": float(d.get("volume", 0) or 0) * float(d.get("last_price", 0) or 0),
                })
            except (TypeError, ValueError):
                continue
    # Preserve requested order
    by_sym = {t["symbol"]: t for t in out}
    return [by_sym[s] for s in symbols if s in by_sym]


async def get_ticker_24h(symbol: str) -> Dict:
    all_t = await get_all_tickers([symbol])
    if not all_t:
        raise ValueError(f"Ticker {symbol} not found on CoinDCX")
    return all_t[0]


async def get_price(symbol: str) -> float:
    t = await get_ticker_24h(symbol)
    return t["price"]


# CoinDCX interval codes
_INTERVAL_MAP = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "2h": "2h", "4h": "4h", "6h": "6h", "8h": "8h",
    "1d": "1d", "3d": "3d", "1w": "1w", "1M": "1M",
}


async def get_klines(symbol: str, interval: str = "1h", limit: int = 200) -> List[Dict]:
    iv = _INTERVAL_MAP.get(interval, "1h")
    pair = _pair_for(symbol)
    data = await _get(f"{PUBLIC_BASE}/market_data/candles", {
        "pair": pair, "interval": iv, "limit": min(max(limit, 1), 1000),
    })
    # CoinDCX returns newest first — reverse
    candles = [
        {
            "time": int(c["time"]),
            "open": float(c["open"]),
            "high": float(c["high"]),
            "low": float(c["low"]),
            "close": float(c["close"]),
            "volume": float(c.get("volume", 0)),
        }
        for c in data
    ]
    candles.sort(key=lambda x: x["time"])
    return candles
