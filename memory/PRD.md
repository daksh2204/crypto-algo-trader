# QuantEdge — Algo Crypto Trading Dashboard

## Original Problem Statement
> i want you to create a algo trading software so that i can trade real time crypto to make profit remember take all the knowledge you have it should be automatic , very less loss , high profits , all the knowlede you have about trading put into the model for max profits

## User Choices (gathered 2026-02-28)
- Mode: both paper + future live (start with paper)
- Exchange: Binance (data via public `data-api.binance.vision`)
- Strategies: MA Crossover, RSI, MACD, Bollinger Bands, AI/LLM
- AI: Claude Sonnet 4.5 via Emergent LLM key (free to user)

## Architecture
- Backend: FastAPI + Motor (MongoDB) — `/app/backend`
  - `binance_api.py` — public market data (tickers, klines, price)
  - `strategies.py` — MA/RSI/MACD/Bollinger + aggregator
  - `ai_signals.py` — Claude 4.5 via `emergentintegrations.LlmChat`
  - `bot.py` — async trading loop + paper execution + SL/TP
  - `server.py` — `/api/*` routes
- Frontend: React + Tailwind + shadcn + recharts (dark command-center theme, IBM Plex Sans + JetBrains Mono)

## Implemented (2026-02-28)
- Live market ticker strip (8 coins) + interactive area chart (5m/15m/1h/4h/1d)
- Classical strategies + AI agreement engine, confidence scoring
- Claude 4.5 AI analysis panel with reasoning, risk level, key factors, suggested SL/TP
- Paper trading engine: $10k starting balance, BUY/SELL, SL/TP auto-close
- Auto bot loop: evaluates N symbols on interval, only executes when classical + AI align and confidence ≥ min
- Live signals feed, trade history table, portfolio panel with open positions + unrealized P&L, metrics (win rate, max drawdown)
- Manual paper trade panel
- Portfolio reset

## Backlog (P1/P2)
- P1: Live trading mode (Binance authenticated API) with user-provided API key/secret + HMAC signing
- P1: Backtesting engine over historical klines + equity curve viewer
- P1: Per-strategy performance breakdown and A/B comparison
- P2: Price alerts / Telegram + email notifications
- P2: Portfolio allocation across multiple coins concurrently (currently 1 long per symbol)
- P2: Shareable trade journal / embed card for social

## Known Limitations
- Only long positions on spot pairs (no shorting in paper MVP)
- Public Binance data only — no user-provided Binance API keys yet
- AI signal call is synchronous (~20–40s); front-end uses "Analyzing…" state

---

## Iteration 2 — CoinDCX + Safety + Backtest + Alerts (2026-02-28)

### Major changes
- **Exchange migrated:** Binance USDT → CoinDCX INR (BTCINR, ETHINR, SOLINR, BNBINR, XRPINR, DOGEINR, ADAINR)
- **Paper balance:** configurable ₹100–₹20,000 (default ₹3,000 to match user's wallet)
- **Safety upgrades (all ON by default):**
  - Trailing stop-loss
  - Daily loss circuit breaker (default -5% → auto-stop bot)
  - Minimum 2-strategy agreement before execution
  - Position size 5% of balance (down from 10%)
  - Min confidence 0.65 (up from 0.55)
  - Confidence aggregation rescaled to `avg(agreeing) + 0.1 * (count-1)`
- **Backtesting engine** (`/api/backtest`) — historical simulation with full config; returns KPIs + equity curve + trades
- **In-app Alerts** (`/api/alerts`) — levels INFO/SUCCESS/WARN/CRITICAL, auto-populated on bot events
- **Tabs UI:** Live Trading | Backtest

### Status
- 18/18 backend tests pass
- Frontend fully working (fmtUsd→fmtInr fix auto-applied by testing agent in LiveSignals.jsx)

### Backlog
- P1: CoinDCX authenticated trading API (HMAC SHA-256 signing) when user is ready to go live
- P2: Email/Telegram notifications (user chose in-app only for now)
- P2: Multi-symbol concurrent positions

---

## Iteration 3 — News Sentiment + Leaderboard + Multi-Symbol (2026-02-28)

### Major changes
- **Multi-symbol concurrent positions:** portfolio.positions is now a LIST supporting multiple open positions simultaneously across different symbols. New config: `max_concurrent_positions` (default 3), `allow_pyramiding` (default false), `max_positions_per_symbol`.
- **News-sentiment layer** injected into Claude AI prompt: CoinDesk RSS headlines + CoinGecko trending coins + alternative.me Fear & Greed index. AI now returns `sentiment_score` (-1..1) and `news_summary`.
- **Strategy Leaderboard** sweeps 3 symbols × 2 intervals × 2 param-sets, ranks by `return - 0.5*drawdown + 2*winrate`, persists in db.leaderboard. `POST /api/leaderboard/apply-best` auto-tunes bot to top config.

### New endpoints
- `GET /api/news`, `GET /api/news/{symbol}`
- `POST /api/leaderboard/run`, `GET /api/leaderboard`, `POST /api/leaderboard/apply-best`

### New UI
- Tabs: Live Trading | Backtest | Leaderboard
- NewsPanel (market intel + F&G gauge + trending chips + CoinDesk headlines)
- LeaderboardPanel (ranked table with RUN SWEEP / APPLY BEST buttons)
- AIInsights now shows Sentiment Layer section

### Status
- 29/29 backend tests pass
- Ready for CoinDCX live API integration next (pending user providing keys)

---

## Iteration 4 — Auto-start + Growth Target + Balanced Mode (2026-02-28)

### Changes
- **Bot auto-starts on backend boot** (`@app.on_event("startup")` calls `bot.load_persisted_config()` + `bot.start()` if `auto_start=True`)
- **Bot config persisted** in `db.bot_state` (single doc `_id=main`)
- **Growth target** ₹4,000 default — bot auto-pauses with success alert when equity ≥ target
- **Balanced defaults**: `min_confidence=0.6`, `min_strategies_agree=1` (was 0.65/2) for ~5-10 trades/day
- **Immediate first tick** — bot runs evaluation immediately on start (no 60s wait)
- **Robust loop** — exception in tick no longer kills bot loop
- **UI**: `AUTO-RUNNING` / `🎉 TARGET HIT` badge in TopBar, growth-progress bar in PortfolioPanel, growth-target field + auto-start toggle in BotControl

### Bug fixed
- `_maybe_check_target` and `_maybe_trip_circuit` were using async generator inside `sum()` (TypeError) which silently killed the bot loop. Refactored to explicit for-loops.

---

## Iteration 5 — Aggressive Capital Deployment (2026-02-28)

### Final config (user wants max-utilization mode)
- **4 symbols watched**: BTCINR, ETHINR, SOLINR, BNBINR
- **Position size 25%** of cash per trade (was 5%)
- **`use_full_capital=True`** — when ON, BUY allocation = `cash / remaining_slots` (fully deploys capital across multiple coins simultaneously)
- **Max 4 concurrent positions** — no sequential trading; capital is spread across all 4 pairs simultaneously
- **30s loop** for faster reaction (was 60s)
- **Confidence 0.55** + 1-strategy agreement (more trade opportunities)
- **SL 2.5% / TP 5% / Trailing ON** · **Daily-loss circuit 7%** · **Target ₹4,000**

### How it allocates capital
- With 0 open + ₹3000 cash + 4 slots → first BUY uses ₹750
- With 1 open + ₹2250 cash + 3 slots → next BUY uses ₹750
- All 4 slots → 100% capital deployed across BTC + ETH + SOL + BNB
- If any closes (SL/TP/SELL signal), remaining cash redeployed on next BUY signal

---

## Iteration 6 — Smart Trader Exit Engine (2026-02-28)

### Now the bot trades like a real trader, not a fixed-% script

**Entry quality (only BUY when ALL agree):**
- Classical strategies + AI signal aligned
- Volume confirmation: latest bar > 1.2× 20-bar avg
- HTF (4h) trend filter: 4h must be uptrend for new BUYs
- Confidence ≥ 0.55

**Dynamic stop-loss (volatility-aware, NOT fixed %):**
- `use_atr_stops=True` → SL = entry − 1.5 × ATR(14)
- ATR adapts to each coin's volatility (BTC's 2% move ≠ DOGE's 2% move)
- TP = max(AI-suggested, 2 × ATR distance)
- Hard SL/TP still act as safety net

**Multi-stage exits (real-trader style):**
1. **TP1 partial** at +3%: sell 50%, move SL to break-even, let runner ride
2. **Trailing stop** ratchets up as price climbs (ATR-based)
3. **Trend-reversal exit**: MACD bearish cross or RSI peak rolling over → instant full close
4. **AI re-evaluation every cycle** (`smart_exits=True`) — Claude examines each open position with current P&L, momentum, S/R, news and decides HOLD / EXIT_PARTIAL / EXIT_FULL
5. **AI-suggested stop tightening**: if AI suggests a higher SL, bot adopts it
6. Hard SL / TP / daily-loss circuit always act as safety net

### New strategies.py helpers
- `atr(klines, period=14)`
- `trend_strength(klines)` — direction + reversal detection
- `volume_confirmation(klines)`
- `find_support_resistance(klines, lookback=50)`

### New ai_signals function
- `evaluate_position(symbol, pos, price, indicators, trend, sr, per_strategy)` — returns `{decision: HOLD|EXIT_PARTIAL|EXIT_FULL, confidence, reasoning, new_stop_loss, tighten_trail}`
