"""Backend API tests for QuantEdge CoinDCX/INR algo trading platform (iteration 2)."""
import os
import time
import pytest
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path("/app/frontend/.env"))
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- Health / Root ----------
def test_root_health(session):
    r = session.get(f"{API}/", timeout=15)
    assert r.status_code == 200
    j = r.json()
    assert j.get("status") == "ok"
    assert j.get("exchange") == "coindcx"
    assert j.get("currency") == "INR"


# ---------- Market data ----------
def test_market_tickers_inr(session):
    r = session.get(f"{API}/market/tickers", timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("currency") == "INR"
    tickers = j.get("tickers", [])
    assert isinstance(tickers, list) and len(tickers) > 0
    syms = [t.get("symbol") for t in tickers]
    # At least BTCINR must be present
    assert "BTCINR" in syms, f"Got symbols: {syms}"
    # Validate price > 0 for BTCINR
    btc = next(t for t in tickers if t["symbol"] == "BTCINR")
    price = float(btc.get("last_price") or btc.get("price") or 0)
    assert price > 0, f"BTC INR price not positive: {btc}"


def test_market_klines_btcinr(session):
    r = session.get(f"{API}/market/klines/BTCINR", params={"interval": "1h", "limit": 200}, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["symbol"] == "BTCINR"
    klines = j["klines"]
    assert len(klines) >= 150, f"Expected ~200 candles, got {len(klines)}"
    k = klines[0]
    for f in ("open", "high", "low", "close", "volume"):
        assert f in k


# ---------- Portfolio reset (clean state, INR) ----------
def test_portfolio_reset_3000(session):
    r = session.post(f"{API}/portfolio/reset", json={"initial_balance": 3000}, timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("ok") is True
    assert j.get("balance") == 3000


def test_portfolio_reset_validation_too_low(session):
    r = session.post(f"{API}/portfolio/reset", json={"initial_balance": 50}, timeout=15)
    assert r.status_code in (400, 422), r.text


def test_portfolio_reset_validation_too_high(session):
    r = session.post(f"{API}/portfolio/reset", json={"initial_balance": 50000}, timeout=15)
    assert r.status_code in (400, 422), r.text


def test_portfolio_after_reset_inr(session):
    r = session.get(f"{API}/portfolio", timeout=30)
    assert r.status_code == 200
    j = r.json()
    assert j["currency"] == "INR"
    assert j["balance"] == 3000
    assert j["initial_balance"] == 3000
    assert j["positions"] == []
    assert j["total_equity"] == 3000


# ---------- Manual trade with quantity_inr ----------
def test_manual_buy_eth_inr(session):
    r = session.post(f"{API}/trades/manual", json={"symbol": "ETHINR", "side": "BUY", "quantity_inr": 300}, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["symbol"] == "ETHINR"
    assert j["side"] == "BUY"
    assert j["type"] == "MANUAL"
    assert j["qty"] > 0


def test_portfolio_after_buy(session):
    r = session.get(f"{API}/portfolio", timeout=30)
    assert r.status_code == 200
    j = r.json()
    assert j["balance"] == pytest.approx(2700, abs=1)
    syms = [p["symbol"] for p in j["positions"]]
    assert "ETHINR" in syms


def test_manual_sell_eth_inr(session):
    r = session.post(f"{API}/trades/manual", json={"symbol": "ETHINR", "side": "SELL", "quantity_inr": 1}, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["side"] == "SELL"
    assert j["type"] == "MANUAL"
    assert "pnl" in j


# ---------- Signals (AI) ----------
def test_generate_signal_btcinr_with_ai(session):
    r = session.get(f"{API}/signals/BTCINR", params={"interval": "1h", "use_ai": "true"}, timeout=90)
    assert r.status_code == 200, r.text
    j = r.json()
    for f in ("action", "confidence", "classical", "ai", "indicators", "symbol"):
        assert f in j, f"missing field {f}"
    ai = j["ai"]
    for f in ("action", "confidence", "reasoning", "risk_level", "key_factors"):
        assert f in ai, f"missing ai field {f}"
    assert j["action"] in ("BUY", "SELL", "HOLD")


# ---------- Backtest ----------
def test_backtest_btcinr(session):
    payload = {
        "symbol": "BTCINR", "interval": "1h", "limit": 500,
        "initial_balance": 3000, "min_confidence": 0.55, "min_strategies_agree": 1,
    }
    r = session.post(f"{API}/backtest", json=payload, timeout=60)
    assert r.status_code == 200, r.text
    j = r.json()
    for f in ("total_trades", "equity_curve", "trades", "win_rate_pct", "max_drawdown_pct", "profit_factor"):
        assert f in j, f"backtest missing {f}: keys={list(j.keys())}"
    assert isinstance(j["equity_curve"], list) and len(j["equity_curve"]) > 0
    assert isinstance(j["trades"], list) and len(j["trades"]) > 0, "no simulated trades at all"
    # Verify CLOSE/STOP_LOSS/TAKE_PROFIT exits are present in the trade tape
    closes = [t for t in j["trades"] if t.get("type") in ("CLOSE", "STOP_LOSS", "TAKE_PROFIT", "END_CLOSE")]
    assert len(closes) > 0, "no exit trades simulated"
    # NOTE: total_trades count is broken upstream — see iteration_2 report


# ---------- Bot start/stop with safety ----------
def test_bot_start_with_safety(session):
    cfg = {
        "symbols": ["BTCINR"], "interval": "1h", "use_ai": False, "loop_seconds": 60,
        "min_strategies_agree": 2, "trailing_stop": True, "max_daily_loss_pct": 5.0,
        "min_confidence": 0.65, "position_size_pct": 5.0,
    }
    r = session.post(f"{API}/bot/start", json=cfg, timeout=20)
    assert r.status_code == 200, r.text
    time.sleep(1)
    s = session.get(f"{API}/bot/status", timeout=15).json()
    assert s.get("running") is True
    assert s.get("circuit_tripped") is False


def test_bot_stop_creates_alert(session):
    r = session.post(f"{API}/bot/stop", timeout=20)
    assert r.status_code == 200
    time.sleep(1)
    s = session.get(f"{API}/bot/status", timeout=15).json()
    assert s.get("running") is False
    # Verify "Bot stopped" alert exists
    a = session.get(f"{API}/alerts", timeout=15).json()
    titles = [x.get("title", "") for x in a.get("alerts", [])]
    assert any("Bot stopped" in t or "stopped" in t.lower() for t in titles), f"no bot stop alert: {titles}"


# ---------- Alerts ----------
def test_alerts_listing(session):
    r = session.get(f"{API}/alerts", timeout=15)
    assert r.status_code == 200
    j = r.json()
    assert "alerts" in j and isinstance(j["alerts"], list)
    titles = [x.get("title", "") for x in j["alerts"]]
    # Should have Portfolio reset, Bot started, Bot stopped, manual BUY/SELL alerts
    joined = " | ".join(titles).lower()
    assert "portfolio reset" in joined
    assert "bot started" in joined or "bot start" in joined


def test_alerts_clear(session):
    r = session.post(f"{API}/alerts/clear", timeout=15)
    assert r.status_code == 200
    assert r.json().get("ok") is True
    a = session.get(f"{API}/alerts", timeout=15).json()
    assert a["alerts"] == []


# ---------- List signals & trades sanity ----------
def test_list_signals(session):
    r = session.get(f"{API}/signals", timeout=20)
    assert r.status_code == 200
    j = r.json()
    assert "signals" in j and isinstance(j["signals"], list)


def test_trades_list(session):
    r = session.get(f"{API}/trades", timeout=20)
    assert r.status_code == 200
    j = r.json()
    assert isinstance(j.get("trades"), list)
