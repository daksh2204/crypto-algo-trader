"""News + sentiment layer — free sources (CoinDesk RSS, CoinGecko trending). Cached in memory."""
import asyncio
import httpx
import time
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
from html import unescape
import re

_CACHE: Dict[str, Dict] = {}
_CACHE_TTL = 300  # 5 min


def _clean_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s or "")
    return unescape(s).strip()


async def _get(url: str, params: Optional[dict] = None, headers: Optional[dict] = None) -> str:
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as c:
        r = await c.get(url, params=params or {}, headers=headers or {"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        return r.text


async def _get_json(url: str, params: Optional[dict] = None) -> dict:
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as c:
        r = await c.get(url, params=params or {})
        r.raise_for_status()
        return r.json()


async def fetch_coindesk_headlines(limit: int = 10) -> List[Dict]:
    now = time.time()
    c = _CACHE.get("coindesk")
    if c and now - c["t"] < _CACHE_TTL:
        return c["data"][:limit]
    try:
        xml_text = await _get("https://www.coindesk.com/arc/outboundfeeds/rss/")
        root = ET.fromstring(xml_text)
        items = []
        for item in root.iter("item"):
            title = _clean_html(item.findtext("title") or "")
            desc = _clean_html(item.findtext("description") or "")[:240]
            pub = item.findtext("pubDate") or ""
            link = item.findtext("link") or ""
            if title:
                items.append({"title": title, "summary": desc, "published": pub, "url": link, "source": "CoinDesk"})
            if len(items) >= 20:
                break
        _CACHE["coindesk"] = {"t": now, "data": items}
        return items[:limit]
    except Exception as e:
        return _CACHE.get("coindesk", {}).get("data", [])[:limit]


async def fetch_coingecko_trending(limit: int = 10) -> List[Dict]:
    now = time.time()
    c = _CACHE.get("cg_trending")
    if c and now - c["t"] < _CACHE_TTL:
        return c["data"][:limit]
    try:
        data = await _get_json("https://api.coingecko.com/api/v3/search/trending")
        coins = []
        for c_ in (data.get("coins") or [])[:15]:
            item = c_.get("item") or {}
            coins.append({
                "symbol": (item.get("symbol") or "").upper(),
                "name": item.get("name") or "",
                "rank": item.get("market_cap_rank") or 0,
                "price_btc": item.get("price_btc") or 0,
                "score": item.get("score") or 0,
            })
        _CACHE["cg_trending"] = {"t": now, "data": coins}
        return coins[:limit]
    except Exception:
        return _CACHE.get("cg_trending", {}).get("data", [])[:limit]


async def fetch_fear_greed() -> Optional[Dict]:
    now = time.time()
    c = _CACHE.get("fng")
    if c and now - c["t"] < _CACHE_TTL:
        return c["data"]
    try:
        data = await _get_json("https://api.alternative.me/fng/")
        row = (data.get("data") or [None])[0]
        if row:
            out = {
                "value": int(row.get("value", 50)),
                "classification": row.get("value_classification", "Neutral"),
                "updated": row.get("timestamp", ""),
            }
            _CACHE["fng"] = {"t": now, "data": out}
            return out
    except Exception:
        pass
    return _CACHE.get("fng", {}).get("data")


async def get_news_bundle(symbol: str = "BTC") -> Dict:
    """Gather all news/sentiment for a trading context."""
    base = symbol.replace("INR", "").upper()
    headlines, trending, fng = await asyncio.gather(
        fetch_coindesk_headlines(8),
        fetch_coingecko_trending(8),
        fetch_fear_greed(),
        return_exceptions=False,
    )
    # Filter headlines that mention the base coin
    relevant = [h for h in headlines if base.lower() in (h["title"] + " " + h["summary"]).lower()][:5]
    if not relevant:
        relevant = headlines[:5]  # fallback to top general headlines
    return {
        "symbol": symbol,
        "fear_greed": fng,
        "trending_coins": trending,
        "headlines": relevant,
        "all_headlines": headlines[:10],
    }
