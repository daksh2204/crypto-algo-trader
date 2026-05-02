"""Iteration 3 — News-sentiment, Leaderboard, multi-symbol concurrent positions."""
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


# -------------------- News --------------------

def test_news_overview(session):
    r = session.get(f"{API}/news", timeout=40)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "headlines" in j and isinstance(j["headlines"], list)
    assert "fear_greed" in j
    assert "trending" in j and isinstance(j["trending"], list)
    fng = j["fear_greed"]
    if fng is not None:
        assert 0 <= int(fng.get("value", -1)) <= 100
        assert isinstance(fng.get("classification"), str) and fng["classification"]
    if j["headlines"]:
        h = j["headlines"][0]
        for f in ("title", "summary", "url"):
            assert f in h, f"headline missing field {f}"


def test_news_for_symbol_btcinr(session):
    r = session.get(f"{API}/news/BTCINR", timeout=40)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["symbol"] == "BTCINR"
    assert "headlines" in j and isinstance(j["headlines"], list)
    assert "fear_greed" in j
    assert "trending_coins" in j and isinstance(j["trending_coins"], list)


# -------------------- Leaderboard --------------------

def test_leaderboard_run_sweep(session):
    r = session.post(f"{API}/leaderboard/run", json={}, timeout=180)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("ok") is True
    assert "count" in j
    assert j["count"] >= 6, f"expected ≥6 sweep results (3 syms × 2 ivs × 2 params), got {j['count']}"
    assert "top" in j and isinstance(j["top"], list) and len(j["top"]) > 0
    top = j["top"][0]
    for f in ("symbol", "interval", "score", "min_confidence", "min_strategies_agree"):
        assert f in top, f"top missing {f}"


def test_leaderboard_list(session):
    r = session.get(f"{API}/leaderboard", timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "leaderboard" in j and isinstance(j["leaderboard"], list)
    assert len(j["leaderboard"]) >= 6
    # Verify sorted desc by score
    scores = [d["score"] for d in j["leaderboard"]]
    assert scores == sorted(scores, reverse=True), "leaderboard not sorted by score desc"
    assert j.get("last_run") is not None
    assert "ran_at" in j["last_run"]


def test_leaderboard_apply_best(session):
    r = session.post(f"{API}/leaderboard/apply-best", json={}, timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("ok") is True
    assert "applied" in j and isinstance(j["applied"], dict)
    assert "best" in j
    applied = j["applied"]
    assert "symbols" in applied and len(applied["symbols"]) == 1
    assert "interval" in applied
    assert "min_confidence" in applied


# -------------------- AI signal w/ news layer --------------------

def test_signal_btcinr_includes_news_summary(session):
    r = session.get(f"{API}/signals/BTCINR", params={"interval": "1h", "use_ai": "true"}, timeout=120)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "ai" in j
    ai = j["ai"]
    # New fields per iteration 3
    assert "sentiment_score" in ai, f"ai missing sentiment_score; keys={list(ai.keys())}"
    assert isinstance(ai["sentiment_score"], (int, float))
    assert "news_summary" in ai, f"ai missing news_summary; keys={list(ai.keys())}"
    ns = ai["news_summary"]
    assert "fear_greed" in ns
    assert "trending" in ns and isinstance(ns["trending"], list)
    assert "headlines_count" in ns and isinstance(ns["headlines_count"], int)


# -------------------- Multi-symbol concurrent positions --------------------

def test_reset_for_multisymbol(session):
    r = session.post(f"{API}/portfolio/reset", json={"initial_balance": 3000}, timeout=20)
    assert r.status_code == 200
    p = session.get(f"{API}/portfolio", timeout=15).json()
    assert p["positions"] == []
    assert p["balance"] == 3000


def test_manual_buy_btcinr_then_ethinr(session):
    r1 = session.post(f"{API}/trades/manual", json={"symbol": "BTCINR", "side": "BUY", "quantity_inr": 500}, timeout=30)
    assert r1.status_code == 200, r1.text
    j1 = r1.json()
    assert j1["symbol"] == "BTCINR" and j1["side"] == "BUY"

    r2 = session.post(f"{API}/trades/manual", json={"symbol": "ETHINR", "side": "BUY", "quantity_inr": 500}, timeout=30)
    assert r2.status_code == 200, r2.text
    j2 = r2.json()
    assert j2["symbol"] == "ETHINR" and j2["side"] == "BUY"

    p = session.get(f"{API}/portfolio", timeout=20).json()
    assert isinstance(p["positions"], list), "portfolio.positions must be a list"
    syms = [pos["symbol"] for pos in p["positions"]]
    assert "BTCINR" in syms and "ETHINR" in syms, f"expected both symbols open, got {syms}"
    assert p["balance"] == pytest.approx(2000, abs=2)


def test_manual_sell_closes_position(session):
    # Sell BTCINR — should close that position; ETHINR should remain
    r = session.post(f"{API}/trades/manual", json={"symbol": "BTCINR", "side": "SELL", "quantity_inr": 1}, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["side"] == "SELL"
    p = session.get(f"{API}/portfolio", timeout=20).json()
    syms = [pos["symbol"] for pos in p["positions"]]
    assert "BTCINR" not in syms
    assert "ETHINR" in syms


# -------------------- Bot start with new safety fields --------------------

def test_bot_start_with_multisymbol_config(session):
    cfg = {
        "symbols": ["BTCINR", "ETHINR"], "interval": "1h", "use_ai": False,
        "use_news": True, "loop_seconds": 60,
        "min_strategies_agree": 2, "min_confidence": 0.65,
        "max_concurrent_positions": 3, "allow_pyramiding": False,
        "max_positions_per_symbol": 1,
    }
    r = session.post(f"{API}/bot/start", json=cfg, timeout=20)
    assert r.status_code == 200, r.text
    time.sleep(1)
    s = session.get(f"{API}/bot/status", timeout=15).json()
    assert s.get("running") is True
    bcfg = s.get("config", {})
    assert bcfg.get("max_concurrent_positions") == 3
    assert bcfg.get("allow_pyramiding") is False
    assert bcfg.get("max_positions_per_symbol") == 1
    assert bcfg.get("use_news") is True
    # cleanup
    session.post(f"{API}/bot/stop", timeout=20)


# -------------------- Cleanup --------------------

def test_cleanup_close_eth(session):
    p = session.get(f"{API}/portfolio", timeout=20).json()
    if any(pos["symbol"] == "ETHINR" for pos in p["positions"]):
        session.post(f"{API}/trades/manual", json={"symbol": "ETHINR", "side": "SELL", "quantity_inr": 1}, timeout=30)
