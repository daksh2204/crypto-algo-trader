"""Binance public market data client (no auth required)."""
import httpx
from typing import List, Dict, Optional

BINANCE_BASE = "https://data-api.binance.vision"

# Preferred trading symbols for the dashboard
DEFAULT_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",
    "XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT",
]


async def _get(path: str, params: Optional[dict] = None) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"{BINANCE_BASE}{path}", params=params or {})
        r.raise_for_status()
        return r.json()


async def get_ticker_24h(symbol: str) -> Dict:
    data = await _get("/api/v3/ticker/24hr", {"symbol": symbol})
    return {
        "symbol": data["symbol"],
        "price": float(data["lastPrice"]),
        "change_pct": float(data["priceChangePercent"]),
        "high": float(data["highPrice"]),
        "low": float(data["lowPrice"]),
        "volume": float(data["volume"]),
        "quote_volume": float(data["quoteVolume"]),
    }


async def get_all_tickers(symbols: List[str]) -> List[Dict]:
    """Fetch ticker data for multiple symbols."""
    symbols_param = '[' + ','.join(f'"{s}"' for s in symbols) + ']'
    data = await _get("/api/v3/ticker/24hr", {"symbols": symbols_param})
    return [
        {
            "symbol": d["symbol"],
            "price": float(d["lastPrice"]),
            "change_pct": float(d["priceChangePercent"]),
            "high": float(d["highPrice"]),
            "low": float(d["lowPrice"]),
            "volume": float(d["volume"]),
            "quote_volume": float(d["quoteVolume"]),
        }
        for d in data
    ]


async def get_price(symbol: str) -> float:
    data = await _get("/api/v3/ticker/price", {"symbol": symbol})
    return float(data["price"])


async def get_klines(symbol: str, interval: str = "1h", limit: int = 200) -> List[Dict]:
    """Return list of candles: open_time, o, h, l, c, v."""
    data = await _get("/api/v3/klines", {
        "symbol": symbol,
        "interval": interval,
        "limit": min(max(limit, 1), 1000),
    })
    return [
        {
            "time": int(k[0]),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
        }
        for k in data
    ]
