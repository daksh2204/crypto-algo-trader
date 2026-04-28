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
