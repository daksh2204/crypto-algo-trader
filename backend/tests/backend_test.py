"""Backend API tests for Algo Crypto Trading platform."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://algo-crypto-edge.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- Health ----------
def test_root_health(session):
    r = session.get(f"{API}/", timeout=15)
    assert r.status_code == 200
    j = r.json()
    assert j.get("status") == "ok"


# ---------- Market data ----------
def test_market_tickers(session):
    r = session.get(f"{API}/market/tickers", timeout=30)
    assert r.status_code == 200
    j = r.json()
    assert "tickers" in j and isinstance(j["tickers"], list)
    syms = [t.get("symbol") for t in j["tickers"]]
    assert "BTCUSDT" in syms


def test_market_klines(session):
    r = session.get(f"{API}/market/klines/BTCUSDT", params={"interval": "1h", "limit": 100}, timeout=30)
    assert r.status_code == 200
    j = r.json()
    assert j["symbol"] == "BTCUSDT"
    assert len(j["klines"]) >= 90
    k = j["klines"][0]
    for f in ("open", "high", "low", "close", "volume"):
        assert f in k


def test_market_ticker_24h(session):
    r = session.get(f"{API}/market/ticker/BTCUSDT", timeout=20)
    assert r.status_code == 200
    j = r.json()
    assert j.get("symbol") == "BTCUSDT" or "lastPrice" in j or "last_price" in j


# ---------- Portfolio reset (early to clean state) ----------
def test_portfolio_reset(session):
    r = session.post(f"{API}/portfolio/reset", timeout=20)
    assert r.status_code == 200
    j = r.json()
    assert j.get("ok") is True
    assert j.get("balance") == 10000


def test_portfolio_after_reset(session):
    r = session.get(f"{API}/portfolio", timeout=30)
    assert r.status_code == 200
    j = r.json()
    assert j["balance"] == 10000
    assert j["initial_balance"] == 10000
    assert j["positions"] == []
    assert j["total_equity"] == 10000


# ---------- Signals ----------
def test_generate_signal_with_ai(session):
    r = session.get(f"{API}/signals/BTCUSDT", params={"interval": "1h", "use_ai": "true"}, timeout=90)
    assert r.status_code == 200, r.text
    j = r.json()
    for f in ("action", "confidence", "classical", "ai", "indicators", "symbol"):
        assert f in j, f"missing field {f}"
    ai = j["ai"]
    for f in ("action", "confidence", "reasoning", "risk_level", "key_factors"):
        assert f in ai, f"missing ai field {f}"
    assert j["action"] in ("BUY", "SELL", "HOLD")


def test_list_signals(session):
    r = session.get(f"{API}/signals", timeout=20)
    assert r.status_code == 200
    j = r.json()
    assert "signals" in j and isinstance(j["signals"], list)
    assert len(j["signals"]) >= 1


# ---------- Manual trades ----------
def test_manual_buy_eth(session):
    payload = {"symbol": "ETHUSDT", "side": "BUY", "quantity_usd": 500}
    r = session.post(f"{API}/trades/manual", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["symbol"] == "ETHUSDT"
    assert j["side"] == "BUY"
    assert j["type"] == "MANUAL"
    assert j["qty"] > 0


def test_portfolio_after_buy(session):
    r = session.get(f"{API}/portfolio", timeout=30)
    assert r.status_code == 200
    j = r.json()
    assert j["balance"] == pytest.approx(9500, abs=1)
    syms = [p["symbol"] for p in j["positions"]]
    assert "ETHUSDT" in syms


def test_manual_buy_duplicate_returns_400(session):
    r = session.post(f"{API}/trades/manual", json={"symbol": "ETHUSDT", "side": "BUY", "quantity_usd": 100}, timeout=20)
    assert r.status_code == 400


def test_manual_sell_eth(session):
    r = session.post(f"{API}/trades/manual", json={"symbol": "ETHUSDT", "side": "SELL", "quantity_usd": 1}, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["side"] == "SELL"
    assert j["type"] == "MANUAL"
    assert "pnl" in j


def test_trades_list(session):
    r = session.get(f"{API}/trades", timeout=20)
    assert r.status_code == 200
    j = r.json()
    assert len(j["trades"]) >= 2
    sides = [t["side"] for t in j["trades"]]
    assert "BUY" in sides and "SELL" in sides


def test_metrics(session):
    r = session.get(f"{API}/metrics", timeout=20)
    assert r.status_code == 200
    j = r.json()
    for f in ("win_rate_pct", "total_pnl", "max_drawdown", "total_trades"):
        assert f in j


# ---------- Bot ----------
def test_bot_start(session):
    cfg = {"symbols": ["BTCUSDT"], "interval": "1h", "use_ai": False, "loop_seconds": 60}
    r = session.post(f"{API}/bot/start", json=cfg, timeout=20)
    assert r.status_code == 200
    time.sleep(1)
    s = session.get(f"{API}/bot/status", timeout=15).json()
    assert s.get("running") is True


def test_bot_stop(session):
    r = session.post(f"{API}/bot/stop", timeout=20)
    assert r.status_code == 200
    time.sleep(1)
    s = session.get(f"{API}/bot/status", timeout=15).json()
    assert s.get("running") is False
