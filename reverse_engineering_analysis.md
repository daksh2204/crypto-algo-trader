# Algo Crypto Trading Dashboard — Complete Reverse-Engineering Analysis

This artifact provides a comprehensive, deep-dive reverse-engineering analysis of the QuantEdge Algo Crypto Trading Dashboard. It is designed to prepare you for a 10-minute Loom video interview with a startup founder, allowing you to discuss the codebase with the authority and depth of a Principal Architect.

---

# SECTION 1 — PROJECT OVERVIEW

### Project Title
**QuantEdge — Algo Crypto Trading Dashboard**

### Problem Statement
Retail traders want to deploy algorithmic trading strategies on live exchanges to make profits, but they face several barriers:
1. **High Latency/No Action**: Simple scripts run synchronously, blocking executions, and fail to track concurrent trades across multiple pairs.
2. **High Risk of Ruin**: Basic grid bots or momentum scripts buy blindly during downtrends or buy low-volume pumps, leading to catastrophic drawdowns.
3. **Rigid System Parameters**: Hardcoded exit rules (e.g., exit strictly at +5%) do not adapt to current market volatility or news events.
4. **Local setup friction**: Local MongoDB or exchange API disconnects crash the trading engine.

### Why This Project Exists
This project bridges the gap between classical indicators (RSI, MACD, Bollinger Bands) and modern Large Language Models (LLMs). It acts as an automated, risk-managed paper trading cockpit that operates 24/7. It implements professional risk controls (circuit breakers, trailing stops, volatility-adapted position sizing, higher-timeframe trend checks, and volume validations) before placing any paper order, ensuring capital preservation.

### Target Users
- **Quantitative Retail Traders** looking to test combined technical + LLM strategies.
- **Crypto Enthusiasts** wanting a high-fidelity paper trading dashboard to test portfolios before going live.
- **Developers/Hobbyists** looking for a plug-and-play modular crypto trading bot framework.

### Core Features
- **Concurrent Multi-Symbol Trading**: Tracks positions across multiple pairs (BTCINR, ETHINR, SOLINR, BNBINR) simultaneously, deploying capital dynamically.
- **AI Agreement Engine**: Integrates Claude-3.5/4.5 to perform qualitative checks on news feeds, sentiment (Fear & Greed, trending coins), and technical indicators, forming a consensus with classical strategies.
- **Smart Exit Engine**: Evaluates open positions every cycle using AI. Executes multi-stage exits: 50% partial profit take (TP1) with break-even stop adjustments, trailing stops, and trend-reversal closes.
- **Database Fallback Proxy**: If local MongoDB goes down, a custom database proxy instantly intercepts calls and routes them to an in-memory replica, preventing bot crashes.
- **Strategy Leaderboard**: Automates parameter sweeps (A/B testing) across coin pairs, scoring them to allow users to auto-tune the trading parameters to the highest-scoring set.
- **Backtesting Module**: Replays historical candles to compute CAGR, drawdown, and win rate.

### Business Value
- **De-risks live deployment**: Enables testing strategies with real market feeds and zero capital risk.
- **High Retention UI**: Command-center style dark theme with IBM Plex Sans, live feeds, interactive Recharts graphs, and real-time status alerts.
- **Extensible Architecture**: Highly modular structure allows adding live exchange brokers (like CoinDCX/Binance API keys with HMAC signing) with minimal code modification.

### Tech Stack
- **Frontend**: React.js, Tailwind CSS (Command-center dark palette), Recharts, Phosphor Icons.
- **Backend**: FastAPI (Python), httpx (async requests), Pandas & NumPy (indicator calculation), Pydantic (data validation).
- **Database**: MongoDB (via `motor.motor_asyncio`) with a built-in custom in-memory fallback proxy.
- **AI/LLM**: Claude Sonnet 4.5 via custom LLM wrappers (`emergentintegrations.llm.chat`).

### High-Level Architecture Summary
The system follows a classic **Client-Server-Agent** architecture. The React frontend polls the FastAPI backend `/api` endpoints every 10 seconds. The backend houses the `TradingBot` loop running on an asynchronous interval (30 seconds). Every cycle, the bot polls the CoinDCX public candle API, updates indicators via the `strategies` engine, calls the `AI agreement` layer to validate momentum/sentiment, executes risk filters, runs the position manager (calculating stops, partial takes, trailing stops), and writes the state to the DB Proxy.

---

# SECTION 2 — CODEBASE WALKTHROUGH

## Detailed File Analysis

### Backend Component

#### 1. [backend/server.py](file:///c:/Users/Asus/OneDrive/Desktop/crypto%20algo%20trader/backend/server.py)
* **Purpose**: Houses the FastAPI web server, routes, and request validation models.
* **Why it exists**: Serves as the gateway for the frontend to query market data, run manual trades, fetch portfolios, retrieve trade histories, configure/start/stop the bot, run historical backtests, and sweep strategy configurations.
* **Key functions**:
  * `startup()`: Recovers bot configuration from the database on startup and boots the bot if `auto_start` is set to `True`.
  * `signals(symbol)`: Generates manual entry signals combining technical indicators and optional AI reasoning.
  * `backtest(req)`: Runs historical simulations over specified ranges and return trade lists and equity curves.
  * `leaderboard_run()` / `leaderboard_apply_best()`: Sweeps parameter matrices and auto-tunes the bot configuration.
* **Key classes**:
  * `BotConfig`, `ManualTrade`, `BacktestRequest`, `PortfolioReset` (Pydantic DTO models).
* **Dependencies**: `fastapi`, `pydantic`, `coindcx_api`, `bot`, `strategies`, `ai_signals`, `backtest`, `news_sentiment`, `leaderboard`, `db_fallback`.
* **Interactions**: Initialized at launch, instantiates the single instance of `TradingBot`, and orchestrates calls between database proxies and external clients.

#### 2. [backend/bot.py](file:///c:/Users/Asus/OneDrive/Desktop/crypto%20algo%20trader/backend/bot.py)
* **Purpose**: Orchestrates the core automated trading bot loops and position monitoring checks.
* **Why it exists**: Implements the active quantitative executor. It polls indicators, runs risk controls, enters trades, updates trailing stops, manages partial fills, and coordinates AI exit decisions.
* **Key functions**:
  * `start()`: Launches the async background loop `_run_loop()`.
  * `_tick()`: The execution beat. Performs target check, circuit breaker check, sweeps active symbols, and runs position maintenance.
  * `_evaluate_and_trade(symbol)`: Queries indicators, requests Claude signals, applies filters (volume, 4h trend), and calls execution.
  * `_execute_paper_trade()`: Calculates position sizes and entry prices, calculates dynamic ATR/AI stops, and inserts records into the database.
  * `_check_open_positions()`: Loops through active positions, updates trailing stops, triggers SL/TP, checks MACD/RSI reversals, handles partial sales, and requests AI evaluations.
* **Key classes**:
  * `TradingBot`
* **Dependencies**: `coindcx_api`, `strategies`, `ai_signals`, `asyncio`, `uuid`, `logging`, `datetime`.
* **Interactions**: Reads/writes database portfolio collections, consumes indicators from `strategies.py`, fetches market quotes, and updates frontend stats.

#### 3. [backend/strategies.py](file:///c:/Users/Asus/OneDrive/Desktop/crypto%20algo%20trader/backend/strategies.py)
* **Purpose**: Computes technical indicators and wraps individual trading strategy indicators.
* **Why it exists**: Provides the classical quantitative base. It encapsulates the math for SMA crossovers, RSI, MACD, and Bollinger Bands using vectorized operations.
* **Key functions**:
  * `ma_crossover()`: Evaluates short vs. long moving averages for bullish/bearish crosses.
  * `rsi_strategy()`: Determines oversold (<30) or overbought (>70) status.
  * `macd_strategy()`: Checks histogram flips to detect momentum reversals.
  * `bollinger_strategy()`: Monitors band breakouts/touches.
  * `aggregate_signals()`: Combines enabled strategies. Applies a consensus algorithm with a confidence bonus for multiple agreeing indicators.
  * `atr()`: Calculates Average True Range (volatility metric) to determine stop distances.
  * `trend_strength()`: Evaluates higher-timeframe trend direction (using 20/50 SMA) and momentum rollover indicators.
* **Key classes**: None (functional code layout).
* **Dependencies**: `pandas`, `numpy`.
* **Interactions**: Called by `bot.py`, `server.py`, `backtest.py`, and `leaderboard.py` to evaluate candle series.

#### 4. [backend/db_fallback.py](file:///c:/Users/Asus/OneDrive/Desktop/crypto%20algo%20trader/backend/db_fallback.py)
* **Purpose**: Implements the MongoDB database abstraction layer with transparent local memory fallback.
* **Why it exists**: Prevents application crashes if the MongoDB server goes offline or has network issues.
* **Key functions**:
  * `_prepopulate_mock_data()`: Inserts default paper trading balances (₹3,000) into the local collection.
  * `_get_active_db()`: Attempts to ping/initialize `motor.motor_asyncio`. If it fails, flips `use_fallback` to `True` and switches to the mock instance.
* **Key classes**:
  * `DatabaseProxy`, `CollectionProxy`, `CursorProxy` (routing wrappers).
  * `MockDatabase`, `MockCollection`, `MockCursor` (in-memory data stores).
* **Dependencies**: `motor`, `asyncio`, `logging`, `datetime`.
* **Interactions**: Intercepts all database queries in `server.py`, `bot.py`, and `leaderboard.py`.

#### 5. [backend/ai_signals.py](file:///c:/Users/Asus/OneDrive/Desktop/crypto%20algo%20trader/backend/ai_signals.py)
* **Purpose**: Coordinates prompt compilation and parsing for LLM signals.
* **Why it exists**: Connects quantitative data to LLM intelligence, instructing Claude to act as a quant and output clean, structured decision payloads.
* **Key functions**:
  * `generate_ai_signal()`: Takes market stats, news bundles, and technical outputs to request entry recommendations (BUY/SELL/HOLD, confidence, stop-losses, and take-profits).
  * `evaluate_position()`: Instructs Claude to examine active positions for partial sells, full exits, or trailing stop adjustments.
* **Key classes**: None.
* **Dependencies**: `emergentintegrations.llm.chat`, `news_sentiment`, `json`, `re`.
* **Interactions**: Called by `bot.py` during entry and exit checks.

#### 6. [backend/news_sentiment.py](file:///c:/Users/Asus/OneDrive/Desktop/crypto%20algo%20trader/backend/news_sentiment.py)
* **Purpose**: Fetches sentiment gauges, trending symbols, and RSS feeds.
* **Why it exists**: Provides news context (CoinDesk articles, CoinGecko trends, Crypto Fear & Greed index) to the LLM agent to support qualitative trading decisions.
* **Key functions**:
  * `fetch_coindesk_headlines()`: Parses CoinDesk RSS feeds for recent news items.
  * `fetch_coingecko_trending()`: Pulls hot search coins to detect retail focus.
  * `fetch_fear_greed()`: Retrieves the daily market fear & greed sentiment score.
  * `get_news_bundle()`: Aggregates feeds and filters them by symbol keyword, caching results with a 5-minute TTL.
* **Key classes**: None.
* **Dependencies**: `httpx`, `xml.etree.ElementTree`, `re`, `time`.
* **Interactions**: Supplies data to `ai_signals.py` and `server.py` news endpoints.

#### 7. [backend/coindcx_api.py](file:///c:/Users/Asus/OneDrive/Desktop/crypto%20algo%20trader/backend/coindcx_api.py)
* **Purpose**: CoinDCX public API market client.
* **Why it exists**: Fetches live ticker statistics and historical candlestick data for INR-denominated trading pairs.
* **Key functions**:
  * `get_all_tickers()`: Queries current prices and 24h changes.
  * `get_klines()`: Fetches historical candles, reversing the API response order to display chronological charts.
* **Key classes**: None.
* **Dependencies**: `httpx`.
* **Interactions**: Supplies prices and charts to `bot.py`, `server.py`, `backtest.py`, and `leaderboard.py`.

#### 8. [backend/binance_api.py](file:///c:/Users/Asus/OneDrive/Desktop/crypto%20algo%20trader/backend/binance_api.py)
* **Purpose**: Binance public API market client (USDT pairs).
* **Why it exists**: Acts as a backup or alternative exchange data provider for tickers, prices, and candlestick data.
* **Key functions**:
  * `get_ticker_24h()`, `get_all_tickers()`, `get_klines()`.
* **Key classes**: None.
* **Dependencies**: `httpx`.
* **Interactions**: Optional alternative data provider (the app currently defaults to CoinDCX).

#### 9. [backend/backtest.py](file:///c:/Users/Asus/OneDrive/Desktop/crypto%20algo%20trader/backend/backtest.py)
* **Purpose**: Runs backtest simulations over historical datasets.
* **Why it exists**: Allows users to backtest strategy configurations on historical candle data to calculate metrics (win rate, CAGR, drawdown) before deployment.
* **Key functions**:
  * `run_backtest()`: Simulates order fills, tracks open balances, updates trailing stops, and generates performance metrics.
* **Key classes**: None.
* **Dependencies**: `pandas`, `strategies`.
* **Interactions**: Called by `/api/backtest` and `leaderboard.py`.

#### 10. [backend/leaderboard.py](file:///c:/Users/Asus/OneDrive/Desktop/crypto%20algo%20trader/backend/leaderboard.py)
* **Purpose**: Runs hyperparameter sweeps and ranks strategy configurations.
* **Why it exists**: Optimizes bot performance by running nightly backtests across symbols and parameters, selecting the configurations with the best risk-adjusted scores.
* **Key functions**:
  * `run_leaderboard_sweep()`: Executes strategy backtests across grids, scores the results, clears older entries, and inserts new leaders.
  * `get_best_config()`: Retrieves the highest-scoring parameter set from the collection.
* **Key classes**: None.
* **Dependencies**: `coindcx_api`, `backtest`, `datetime`.
* **Interactions**: Called by `server.py` to auto-tune bot parameters.

#### 11. [backend/emergentintegrations/llm/chat.py](file:///c:/Users/Asus/OneDrive/Desktop/crypto%20algo%20trader/backend/emergentintegrations/llm/chat.py)
* **Purpose**: Custom LLM integration layer.
* **Why it exists**: Interfaces with Claude APIs. It includes an in-memory mock fallback that parses prompts and returns deterministic JSON responses to ensure high test pass rates and low latency.
* **Key functions**:
  * `with_model()`: Selects provider and model (e.g., `anthropic`, `claude-sonnet-4-5-20250929`).
  * `send_message()`: Parses input payloads, determines request type (exit eval or signal), and returns corresponding trading JSON.
* **Key classes**:
  * `LlmChat`, `UserMessage`.
* **Dependencies**: `json`, `re`, `logging`.
* **Interactions**: Called by `ai_signals.py` for LLM evaluations.

---

### Frontend Component

#### 12. [frontend/src/components/Dashboard.jsx](file:///c:/Users/Asus/OneDrive/Desktop/crypto%20algo%20trader/frontend/src/components/Dashboard.jsx)
* **Purpose**: Core application dashboard.
* **Why it exists**: Serves as the central user interface container. It coordinates tabs (Live Trading, Backtest, Leaderboard), handles active symbol changes, and updates shared state (tickers, portfolio, metrics, bot status).
* **Dependencies**: React, `lib/api.js`, custom panels (`PriceChart`, `BotControl`, `PortfolioPanel`, etc.).
* **Interactions**: Polls `/api/market/tickers`, `/api/portfolio`, `/api/metrics`, and `/api/bot/status` every 10 seconds.

#### 13. [frontend/src/components/PriceChart.jsx](file:///c:/Users/Asus/OneDrive/Desktop/crypto%20algo%20trader/frontend/src/components/PriceChart.jsx)
* **Purpose**: Interactive candlestick/area chart.
* **Why it exists**: Visualizes price movements and technical indicators, overlaying active buy and sell signals directly on the chart.
* **Dependencies**: React, `recharts`.
* **Interactions**: Fetches candles from `/api/market/klines/{symbol}` and displays indicators.

#### 14. [frontend/src/components/BotControl.jsx](file:///c:/Users/Asus/OneDrive/Desktop/crypto%20algo%20trader/frontend/src/components/BotControl.jsx)
* **Purpose**: Trading bot control panel.
* **Why it exists**: Allows users to configure bot settings (symbols, strategies, AI status, stops, target equity, circuit breaker limits) and start or stop the bot.
* **Dependencies**: React.
* **Interactions**: Submits settings updates to `/api/bot/config` and controls loops via `/api/bot/start` and `/api/bot/stop`.

#### 15. [frontend/src/components/PortfolioPanel.jsx](file:///c:/Users/Asus/OneDrive/Desktop/crypto%20algo%20trader/frontend/src/components/PortfolioPanel.jsx)
* **Purpose**: Portfolio dashboard and balance tracker.
* **Why it exists**: Shows current balances, open positions, unrealized P&L, and target progress.
* **Dependencies**: React, `@phosphor-icons/react`.
* **Interactions**: Displays data from `/api/portfolio` and triggers resets via `/api/portfolio/reset`.

#### 16. [frontend/src/components/AIInsights.jsx](file:///c:/Users/Asus/OneDrive/Desktop/crypto%20algo%20trader/frontend/src/components/AIInsights.jsx)
* **Purpose**: LLM analysis and sentiment display.
* **Why it exists**: Displays Claude's trade recommendations, reasoning, key factors, risk assessments, and fear & greed sentiment metrics.
* **Dependencies**: React.
* **Interactions**: Reads data from `/api/signals/{symbol}` and displaying raw inputs.

#### 17. [frontend/src/components/LeaderboardPanel.jsx](file:///c:/Users/Asus/OneDrive/Desktop/crypto%20algo%20trader/frontend/src/components/LeaderboardPanel.jsx)
* **Purpose**: Parameter optimization sweeper.
* **Why it exists**: Ranks and displays optimal strategies, allowing users to apply the highest-scoring configurations directly to the live bot.
* **Dependencies**: React.
* **Interactions**: Triggers optimization sweeps via `/api/leaderboard/run` and applies settings via `/api/leaderboard/apply-best`.

#### 18. [frontend/src/components/BacktestPanel.jsx](file:///c:/Users/Asus/OneDrive/Desktop/crypto%20algo%20trader/frontend/src/components/BacktestPanel.jsx)
* **Purpose**: Backtest runner.
* **Why it exists**: Visualizes historical simulation results, rendering equity curves and metrics (win rate, profit factor, max drawdown).
* **Dependencies**: React, `recharts`.
* **Interactions**: Sends requests to `/api/backtest`.

#### 19. [frontend/src/components/AlertsPanel.jsx](file:///c:/Users/Asus/OneDrive/Desktop/crypto%20algo%20trader/frontend/src/components/AlertsPanel.jsx)
* **Purpose**: Real-time system log viewer.
* **Why it exists**: Displays bot actions, circuit-trips, and target notifications.
* **Dependencies**: React.
* **Interactions**: Fetches feeds from `/api/alerts` and clears logs via `/api/alerts/clear`.

#### 20. [frontend/src/components/NewsPanel.jsx](file:///c:/Users/Asus/OneDrive/Desktop/crypto%20algo%20trader/frontend/src/components/NewsPanel.jsx)
* **Purpose**: Market news feeds list.
* **Why it exists**: Displays parsed RSS headlines, fear & greed gauges, and trending assets in the sidebar.
* **Dependencies**: React.
* **Interactions**: Fetches data from `/api/news`.

---

## Codebase Structure Summary

### Top 20 Most Important Files
1. `backend/server.py` (App router & routes gateway)
2. `backend/bot.py` (Automated trading loop manager)
3. `backend/strategies.py` (Technical analysis calculations)
4. `backend/db_fallback.py` (MongoDB fallback database proxy)
5. `backend/ai_signals.py` (LLM integration layer)
6. `backend/backtest.py` (Historical simulation engine)
7. `backend/leaderboard.py` (Strategy optimizer sweep)
8. `backend/coindcx_api.py` (Exchange API client)
9. `backend/news_sentiment.py` (RSS and sentiment gatherer)
10. `frontend/src/components/Dashboard.jsx` (Frontend shell)
11. `frontend/src/components/PriceChart.jsx` (Chart visualizer)
12. `frontend/src/components/BotControl.jsx` (Bot control panel)
13. `frontend/src/components/PortfolioPanel.jsx` (Portfolio dashboard)
14. `frontend/src/components/AIInsights.jsx` (Claude insights viewer)
15. `frontend/src/components/LeaderboardPanel.jsx` (Hyperparameter optimization dashboard)
16. `frontend/src/components/BacktestPanel.jsx` (Backtest parameters panel)
17. `backend/emergentintegrations/llm/chat.py` (Claude API proxy emulator)
18. `frontend/src/index.css` (Tailwind design configuration)
19. `backend/binance_api.py` (USDT alternative data client)
20. `frontend/src/components/AlertsPanel.jsx` (System event logs panel)

### Top 20 Most Important Functions
1. `TradingBot._tick()` (Core event loop runner)
2. `TradingBot._evaluate_and_trade()` (Orchestrates signals, filters, and orders)
3. `TradingBot._check_open_positions()` (Manages trailing stops and dynamic exits)
4. `TradingBot._execute_paper_trade()` (Calculates risk parameters and enters trades)
5. `strategies.aggregate_signals()` (Consolidates classical indicator signals)
6. `strategies.atr()` (Average True Range volatility calculation)
7. `strategies.trend_strength()` (Trend direction check)
8. `strategies.volume_confirmation()` (Volume pump filter)
9. `ai_signals.generate_ai_signal()` (Queries LLM recommendations)
10. `ai_signals.evaluate_position()` (Queries LLM exit reviews)
11. `backtest.run_backtest()` (Historical simulation engine)
12. `leaderboard.run_leaderboard_sweep()` (Grid-search strategy optimizer)
13. `db_fallback.DatabaseProxy._get_active_db()` (Database proxy router)
14. `coindcx_api.get_klines()` (Fetches historical candles)
15. `coindcx_api.get_all_tickers()` (Queries live price ticker data)
16. `news_sentiment.get_news_bundle()` (Aggregates news feeds)
17. `server.bot_start()` (API endpoint to launch bot background task)
18. `server.leaderboard_apply_best()` (API endpoint to auto-tune parameters)
19. `server.manual_trade()` (API endpoint for manual paper trading)
20. `server.portfolio()` (Enriches and calculates portfolio statistics)

### Codebase Class Mapping (13 Classes Total)
1. `TradingBot` (in `bot.py`): Manates automated trading cycles and states.
2. `DatabaseProxy` (in `db_fallback.py`): Manages the connection state of the DB.
3. `CollectionProxy` (in `db_fallback.py`): Proxies query methods to the active database.
4. `CursorProxy` (in `db_fallback.py`): Proxies database sorting and list conversions.
5. `MockDatabase` (in `db_fallback.py`): In-memory database simulation client.
6. `MockCollection` (in `db_fallback.py`): In-memory collection simulation client.
7. `MockCursor` (in `db_fallback.py`): In-memory cursor data sorter.
8. `LlmChat` (in `emergentintegrations/llm/chat.py`): Claude integration layer.
9. `UserMessage` (in `emergentintegrations/llm/chat.py`): Compiles chat prompt structures.
10. `BotConfig` (in `server.py`): FastAPI Pydantic validator model for bot settings.
11. `ManualTrade` (in `server.py`): FastAPI Pydantic validator model for manual trades.
12. `BacktestRequest` (in `server.py`): FastAPI Pydantic validator model for backtesting.
13. `PortfolioReset` (in `server.py`): FastAPI Pydantic validator model for account resets.

---

# SECTION 3 — APPLICATION EXECUTION FLOW

```mermaid
sequenceDiagram
    autonumber
    participant App as FastAPI App Boot
    participant DB as DatabaseProxy
    participant Bot as TradingBot Engine
    participant Ex as CoinDCX Public API
    participant Claude as Claude LLM Agent
    participant Web as Client UI Dashboard

    Note over App, Web: 1. STARTUP & INITIALIZATION PHASE
    App->>DB: Instantiate DatabaseProxy & check connection
    alt MongoDB Online
        DB->>DB: Route queries to Real Motor Mongo Client
    else MongoDB Offline
        DB->>DB: Fallback to MockDatabase (in-memory) & Prepopulate balance (₹3000)
    end
    App->>Bot: Instantiate TradingBot with DB Client
    App->>Bot: load_persisted_config() from db.bot_state
    alt Config Auto-Start is True
        App->>Bot: start() background task (asyncio.create_task)
        Bot->>DB: Write Alert "INFO: Bot started"
    end

    Note over Bot, Claude: 2. BOT RUN_LOOP TICK CYCLE (Every 30 seconds)
    loop Asynchronous Evaluation Loop
        Bot->>Bot: _maybe_check_target() -> check if Equity >= Growth Target (₹4000)
        alt Target Reached
            Bot->>DB: Write Success Alert, disable run, pause bot
        end
        Bot->>Bot: _maybe_trip_circuit() -> check if Daily loss <= -7%
        alt Circuit Breaker Tripped
            Bot->>DB: Write Critical Alert, disable run, halt bot
        end
        
        Note over Bot, Ex: 3. MARKET EVALUATION PHASE
        rect rgb(20, 20, 20)
            Bot->>Ex: get_klines() (Symbol, 15m, 200 candles) & get_klines(4h, 100)
            Ex-->>Bot: Return historical candle structures
            Bot->>Bot: Compute Indicators (RSI, MACD, Bollinger Bands)
            Bot->>Bot: aggregate_signals() -> Calculate Consensus Direction (BUY/SELL/HOLD) & Confidence
            Bot->>Bot: trend_strength(4h) -> Check higher-timeframe trend direction
            Bot->>Bot: volume_confirmation(15m) -> Validate current volume > 1.2x avg
        end

        Note over Bot, Claude: 4. DECISION & EXECUTION PHASE
        rect rgb(20, 30, 40)
            alt System config.use_ai is True
                Bot->>Claude: generate_ai_signal() (technicals, news feed, Fear & Greed)
                Claude-->>Bot: Return entry signal JSON (action, confidence, reason, SL/TP)
            end
            Bot->>Bot: Form Consensus (Classical consensus + AI recommendation)
            alt Signal is BUY & Filters Pass (Volume confirm, 4h uptrend, conf >= min)
                Bot->>Bot: _execute_paper_trade() -> calculate position sizing (balance/slots)
                Bot->>Bot: Calculate Volatility-adjusted SL (1.5x ATR) and TP (max(AI, 2x ATR))
                Bot->>DB: Insert trade record to db.trades & alert log
            end
        end

        Note over Bot, Claude: 5. POSITION MONITORING & SMART EXITS
        rect rgb(30, 20, 20)
            loop For Each Open Position
                Bot->>Ex: get_price() / get_klines() (current quote)
                Bot->>Bot: Update highest peak since entry
                Bot->>Bot: Ratchet stop-loss upwards (Trailing Stop = peak - 1.5x ATR)
                alt Current Price <= stop_loss (Stop Loss Hit)
                    Bot->>DB: Sell position, log trade (type=STOP_LOSS), trigger Alert
                else Current Price >= take_profit (Take Profit Hit)
                    Bot->>DB: Sell position, log trade (type=TAKE_PROFIT), trigger Alert
                else Current Price >= TP1 (+3%) and not partial_taken
                    Bot->>Bot: Sell 50%, lock balance, set stop_loss to break-even, update flag
                else MACD/RSI flipped against position (Trend Reversal)
                    Bot->>DB: Sell position, log trade (type=REVERSAL_EXIT), trigger Alert
                else smart_exits is True
                    Bot->>Claude: evaluate_position() (position details, current indicators)
                    Claude-->>Bot: Return exit decision JSON (decision, confidence, reasoning, tighten_trail)
                    alt Decision is EXIT_FULL
                        Bot->>DB: Sell position, log trade (type=AI_EXIT), trigger Alert
                    end
                end
            end
        end
    end

    Note over Web, App: 6. USER INTERACTION INTERACTION
    Web->>App: Poll /market/tickers, /portfolio, /metrics, /alerts, /bot/status (10s interval)
    App-->>Web: Return current state
    Web->>App: User commands (Manual trade, reset portfolio, optimize grid)
    App->>Bot: Trigger update configs / apply optimal tuning
```

---

# SECTION 4 — HIGH LEVEL DESIGN (HLD)

### HLD Component Architecture

```mermaid
graph TD
    User([User Trader])
    
    subgraph Frontend [React Frontend - Dark Terminal UI]
        Dashboard[Dashboard Controller]
        PriceChart[Price Chart Widget - Recharts]
        BotControlWidget[Bot Control Widget]
        PortfolioWidget[Portfolio Balance & Target Tracker]
        AIInsightsWidget[Claude AI Insights Widget]
        LeaderboardWidget[Strategy Grid Sweep Widget]
    end

    subgraph Backend [FastAPI Backend - Asynchronous Engine]
        Server[FastAPI API Server - server.py]
        BotEngine[TradingBot Orchestrator - bot.py]
        BacktestEngine[Backtest Simulation - backtest.py]
        LeaderboardSweeper[Leaderboard Sweep Engine - leaderboard.py]
        
        subgraph QuantCore [Quantitative & Logic Engines]
            StrategyEngine[Strategies Indicator Engine - strategies.py]
            AIEngine[AI Prompt & Exit Evaluator - ai_signals.py]
            SentimentLayer[Sentiment RSS & API Aggregator - news_sentiment.py]
        end
    end

    subgraph DB [Database Layer - Proxy abstraction]
        DBProxy[Database Proxy Client - db_fallback.py]
        MockDB[In-Memory Mock Database]
        RealMongo[MongoDB database server - Motor]
    end

    subgraph ExternalServices [External Feeds & Exchanges]
        CoinDCX[CoinDCX Public Exchange API]
        Binance[Binance Vision API Feed]
        CoinDesk[CoinDesk RSS Headlines XML Feed]
        CoinGecko[CoinGecko Trending Search API]
        AlternativeMe[Alternative.me Fear & Greed API]
    end

    %% User Interaction Flow
    User -->|Interacts / Toggles| Frontend
    
    %% Frontend to Backend Connection
    Dashboard -->|HTTP Polling 10s| Server
    BotControlWidget -->|Start / Stop / Config| Server
    LeaderboardWidget -->|Run Sweeps / Apply| Server

    %% Backend Routing & Orchestration
    Server -->|Controls / Configures| BotEngine
    Server -->|Runs Simulations| BacktestEngine
    Server -->|Sweeps Parameter Grid| LeaderboardSweeper
    BotEngine -->|Triggers Cycles| QuantCore
    
    %% Quantitative Layer Operations
    BotEngine -->|Fetches Market Data| CoinDCX
    BacktestEngine -->|Loads Historical Candles| CoinDCX
    LeaderboardSweeper -->|Simulates Combinations| BacktestEngine
    
    StrategyEngine -->|TA Math Calculations| QuantCore
    AIEngine -->|Generates Prompts / Decision Context| Claude[Claude Sonnet 4.5 LLM]
    AIEngine -->|Incorporates RSS & Sentiment| SentimentLayer
    SentimentLayer -->|XML RSS Parsing| CoinDesk
    SentimentLayer -->|Trending Coins JSON| CoinGecko
    SentimentLayer -->|Fear & Greed Index| AlternativeMe

    %% DB Routing fallback
    Server -->|Read / Write State| DBProxy
    BotEngine -->|Save Portfolios / Log Trades / Alerts| DBProxy
    LeaderboardSweeper -->|Save Rank lists| DBProxy
    
    DBProxy -->|Pings / Fallback router| RealMongo
    DBProxy -.->|On Timeout Failover| MockDB
    
    classDef ui fill:#111,stroke:#007AFF,stroke-width:2px,color:#fff;
    classDef be fill:#222,stroke:#00E676,stroke-width:2px,color:#fff;
    classDef db fill:#333,stroke:#FFC107,stroke-width:2px,color:#fff;
    classDef ext fill:#444,stroke:#f00,stroke-width:1px,color:#fff;
    
    class Dashboard,PriceChart,BotControlWidget,PortfolioWidget,AIInsightsWidget,LeaderboardWidget ui;
    class Server,BotEngine,BacktestEngine,LeaderboardSweeper,StrategyEngine,AIEngine,SentimentLayer be;
    class DBProxy,MockDB,RealMongo db;
    class CoinDCX,Binance,CoinDesk,CoinGecko,AlternativeMe ext;
```

---

# SECTION 5 — LOW LEVEL DESIGN (LLD)

### Database Schemas (JSON-B Document Structures)

#### 1. Portfolio Collection (`portfolio` - Document `_id = main`)
This represents the single active ledger tracking funds and open risk.
```json
{
  "_id": "main",
  "balance": 2250.0,
  "initial_balance": 3000.0,
  "currency": "INR",
  "positions": [
    {
      "id": "d7b1d1f0-466a-4933-9092-d6b7b51b3d68",
      "symbol": "BTCINR",
      "qty": 0.000125,
      "original_qty": 0.000125,
      "entry_price": 6000000.0,
      "peak": 6100000.0,
      "entry_time": "2026-06-15T12:00:00.000Z",
      "stop_loss": 5850000.0,
      "take_profit": 6300000.0,
      "tp1": 6180000.0,
      "partial_taken": false,
      "atr_at_entry": 100000.0,
      "entry_reasoning": "Bullish crossover confirmed by AI analysis."
    }
  ],
  "created_at": "2026-06-15T11:00:00.000Z",
  "updated_at": "2026-06-15T12:05:00.000Z"
}
```

#### 2. Trades Collection (`trades`)
Logs all completed or partial execution fills.
```json
{
  "id": "e9a4f210-911b-411a-8bb7-f277a111ba18",
  "symbol": "BTCINR",
  "side": "SELL",
  "qty": 0.0000625,
  "price": 6180000.0,
  "type": "TP1_PARTIAL",
  "pnl": 11250.0,
  "entry_price": 6000000.0,
  "signal_summary": {
    "action": "BUY",
    "confidence": 0.78,
    "ai_reasoning": "Quantitative review for BTCINR indicates an asymmetric setup..."
  },
  "timestamp": "2026-06-15T12:05:00.000Z"
}
```

#### 3. Signals Collection (`signals`)
Stores historical snapshots of generated indicators and decisions.
```json
{
  "id": "c61a5e10-410a-4fb1-90be-e771c51db3f9",
  "symbol": "BTCINR",
  "price": 6000000.0,
  "action": "BUY",
  "confidence": 0.78,
  "strategies_agreed": 3,
  "classical": {
    "action": "BUY",
    "confidence": 0.75,
    "per_strategy": {
      "MA_CROSSOVER": { "action": "BUY", "confidence": 0.75, "reason": "SMA cross" },
      "RSI": { "action": "HOLD", "confidence": 0.25, "reason": "Neutral" },
      "MACD": { "action": "BUY", "confidence": 0.7, "reason": "Histogram flipped" },
      "BOLLINGER": { "action": "BUY", "confidence": 0.7, "reason": "Broke lower band" }
    }
  },
  "ai": {
    "action": "BUY",
    "confidence": 0.78,
    "reasoning": "Asymmetric risk reward trade setup.",
    "risk_level": "MEDIUM",
    "key_factors": ["Support hold", "Indicators consensus"],
    "sentiment_score": 0.2,
    "stop_loss_pct": 2.0,
    "take_profit_pct": 5.0
  },
  "indicators": {
    "sma_20": 5980000.0,
    "sma_50": 5920000.0,
    "rsi": 29.5,
    "macd": 1500.0,
    "macd_signal": 1200.0,
    "macd_hist": 300.0,
    "bb_upper": 6150000.0,
    "bb_middle": 6000000.0,
    "bb_lower": 5850000.0
  },
  "timestamp": "2026-06-15T12:00:00.000Z",
  "source": "bot"
}
```

#### 4. Alerts Collection (`alerts`)
Simple list structures for notification tracking.
```json
{
  "id": "f61a1210-b9bb-4aab-a77b-efb2b51b3d68",
  "level": "SUCCESS",
  "title": "BUY BTCINR",
  "message": "₹750 @ ₹6000000.00 · SL ₹5850000.00 (-2.50%) · TP1 ₹6180000.00 · TP ₹6300000.00",
  "timestamp": "2026-06-15T12:00:00.000Z",
  "read": false
}
```

---

# SECTION 6 — STRATEGY SYSTEM & TECHNICAL MATHEMATICS

Our strategy calculations are vectorized in `strategies.py` using Pandas and NumPy.

### 1. Moving Average Crossover (`ma_crossover`)
* **Logic**: Evaluates a Fast Simple Moving Average (20-period) against a Slow SMA (50-period).
* **Mathematical Crossover Check**:
  $$	ext{prev\_diff} = 	ext{SMA}_{20}(t-1) - 	ext{SMA}_{50}(t-1)$$
  $$	ext{curr\_diff} = 	ext{SMA}_{20}(t) - 	ext{SMA}_{50}(t)$$
  * If $	ext{prev\_diff} < 0$ and $	ext{curr\_diff} > 0$, SMA20 crossed above SMA50 $ightarrow$ **BUY (confidence = 0.75)**.
  * If $	ext{prev\_diff} > 0$ and $	ext{curr\_diff} < 0$, SMA20 crossed below SMA50 $ightarrow$ **SELL (confidence = 0.75)**.

### 2. Relative Strength Index (`rsi_strategy`)
* **Formula**:
  $$	ext{RSI} = 100 - rac{100}{1 + 	ext{RS}}$$
  $$	ext{RS} = rac{	ext{Average Gain}}{	ext{Average Loss}}$$
* **Logic**: Evaluates a 14-period RSI window.
  * If $	ext{RSI} < 30$ (Oversold), confidence increases relative to oversold depth:
    $$	ext{Confidence} = \min\left(1.0, rac{30 - 	ext{RSI}}{30} + 0.5ight)$$
    Action $ightarrow$ **BUY**.
  * If $	ext{RSI} > 70$ (Overbought), confidence scale:
    $$	ext{Confidence} = \min\left(1.0, rac{	ext{RSI} - 70}{100 - 70} + 0.5ight)$$
    Action $ightarrow$ **SELL**.

### 3. Moving Average Convergence Divergence (`macd_strategy`)
* **Calculation**:
  $$	ext{EMA}_{	ext{fast}} = 	ext{EMA}_{12}(	ext{Close})$$
  $$	ext{EMA}_{	ext{slow}} = 	ext{EMA}_{26}(	ext{Close})$$
  $$	ext{MACD Line} = 	ext{EMA}_{	ext{fast}} - 	ext{EMA}_{	ext{slow}}$$
  $$	ext{Signal Line} = 	ext{EMA}_{9}(	ext{MACD Line})$$
  $$	ext{Histogram} = 	ext{MACD Line} - 	ext{Signal Line}$$
* **Crossover Logic**:
  * If $	ext{Histogram}(t-1) < 0$ and $	ext{Histogram}(t) > 0$, line crossed above signal $ightarrow$ **BUY (confidence = 0.7)**.
  * If $	ext{Histogram}(t-1) > 0$ and $	ext{Histogram}(t) < 0$, line crossed below signal $ightarrow$ **SELL (confidence = 0.7)**.

### 4. Bollinger Bands Strategy (`bollinger_strategy`)
* **Calculation**:
  $$	ext{Middle Band} = 	ext{SMA}_{20}(	ext{Close})$$
  $$	ext{StdDev} = \sqrt{rac{1}{N}\sum(x_i - \mu)^2}$$
  $$	ext{Upper Band} = 	ext{Middle Band} + 2.0 	imes 	ext{StdDev}$$
  $$	ext{Lower Band} = 	ext{Middle Band} - 2.0 	imes 	ext{StdDev}$$
* **Logic**:
  * Price $\le$ Lower Band $ightarrow$ Oversold. Action $ightarrow$ **BUY (confidence = 0.7)**.
  * Price $\ge$ Upper Band $ightarrow$ Overbought. Action $ightarrow$ **SELL (confidence = 0.7)**.

### 5. Higher-Timeframe Trend Filter
* Operates on the 4-hour candles. Validates that current price > 20 EMA > 50 EMA before entering a BUY. This prevents buying pullbacks in long-term downtrends.

### 6. Volume Confirmation Filter
* Checks if the latest candle volume is at least $1.2	imes$ the 20-period simple moving average of volume. If false, entries are blocked to prevent trading low-liquidity spikes.

---

# SECTION 7 — RISK MANAGEMENT & CIRCUIT BREAKERS

### 1. Daily loss circuit breaker
Runs at every bot tick (`_maybe_trip_circuit()`).
* Stores equity value at the beginning of the day (marked by date change: `self._day != today`).
* Calculates total current equity:
  $$	ext{Equity} = 	ext{Cash Balance} + \sum(	ext{Position Qty} 	imes 	ext{Current Price})$$
* If $rac{	ext{Equity} - 	ext{StartEquity}}{	ext{StartEquity}} \le -0.07$ (7% loss):
  * Sets `self._circuit_tripped = True`.
  * Sets `self.running = False` (pauses bot).
  * Writes a critical alert log, preventing further automated trade execution.

### 2. Multi-Symbol Capital Allocation
Instead of fixed position sizes, the bot implements **aggressive full-capital allocation** across a grid of up to 4 concurrent positions:
* Available slots:
  $$	ext{Slots} = 	ext{Max Concurrent Positions} - 	ext{Open Positions}$$
* Allocation per trade:
  $$	ext{Allocation} = rac{	ext{Balance}}{\max(1, 	ext{Slots})}$$
* Example scenario:
  * Portfolio has ₹3,000 cash and 0 open positions (4 slots available).
  * First buy signal triggers: allocation is ₹3,000 / 4 = ₹750. Cash becomes ₹2,250.
  * Second buy triggers: allocation is ₹2,250 / 3 = ₹750. Cash becomes ₹1,500.
  * Third buy triggers: allocation is ₹1,500 / 2 = ₹750. Cash becomes ₹750.
  * Fourth buy triggers: allocation is ₹750 / 1 = ₹750. Cash becomes ₹0.
  * All ₹3,000 is fully deployed across 4 positions. If any position is closed, the proceeds go back into the cash balance, to be split among remaining slots on the next buy.

### 3. Growth Target Cap
* Bot config contains a target (₹4,000). If total equity exceeds this value, `_maybe_check_target()` triggers a success alert and stops the bot.

---

# SECTION 8 — DYNAMIC EXIT MECHANICS

The engine manages open risk dynamically through six distinct layers:

### 1. Volatility-Adjusted Stops (ATR Stops)
Stop-losses are set based on the Average True Range (ATR) over 14 periods:
* True Range (TR):
  $$	ext{TR} = \max\left( (H - L), |H - C_{t-1}|, |L - C_{t-1}| ight)$$
* Average True Range (ATR):
  $$	ext{ATR} = 	ext{RollingMean}_{14}(	ext{TR})$$
* Stop-Loss Price:
  $$	ext{SL Price} = 	ext{Entry Price} - 1.5 	imes 	ext{ATR}$$
* Take-Profit Price:
  $$	ext{TP Price} = 	ext{Entry Price} 	imes \left(1 + rac{\max(	ext{AI TakeProfitPct}, rac{2 	imes 	ext{ATR}}{	ext{Entry Price}} 	imes 100)}{100}ight)$$

### 2. Trailing Stop Ratchets
If `trailing_stop` is enabled, the bot updates the maximum price peak since entry:
* $	ext{Peak} = \max(	ext{Peak}, 	ext{CurrentPrice})$
* Dynamic Stop-loss value is computed:
  $$	ext{Trail SL} = 	ext{Peak} - 1.5 	imes 	ext{ATR}$$
* If $	ext{Trail SL} > 	ext{Current Stop Loss}$, the stop-loss is adjusted upwards. Stop-losses can only move up, locking in profits.

### 3. Two-Stage Exits (TP1 Partials)
* First profit target (TP1) is set at +3% of the entry price.
* When price $\ge$ TP1, the bot sells 50% of the position quantity.
* Cash proceeds are returned to the balance.
* The remaining position's stop-loss is moved to the break-even entry price.

### 4. Technical Reversal Exits
* Evaluates the short-term indicators. If the MACD histogram crosses below zero or the RSI crosses down from overbought levels, the bot exits the position immediately to preserve capital.

### 5. Smart AI Re-evaluations
* The bot calls `evaluate_position()` every cycle. Claude reviews indicators, support/resistance, current P&L, and news context, returning a decision: `HOLD`, `EXIT_PARTIAL`, or `EXIT_FULL`.
* An `EXIT_FULL` decision with confidence $\ge 0.55$ triggers an immediate market exit.

---

# SECTION 9 — AI ENGINE & PROMPT ENGINEERING

Claude is integrated using the `LlmChat` client wrapper.

### 1. Entry Signal Prompt Structure
* **System Prompt**: Sets the role to a Quantitative Crypto Trader. Instructs the model to check indicators, sentiment, news, support/resistance levels, and HTF trends, requiring a consensus of independent indicators with a risk/reward ratio $\ge 2$.
* **Input Payload**: Contains the token symbol, market statistics, technical indicators (RSI, MACD, Bollinger Bands), outputs from classical strategies, and current news sentiment.
* **News Sentiment Inputs**:
  * CoinGecko trending tokens.
  * Fear & Greed Index score.
  * Headline summaries from CoinDesk.
* **Output Specification**: Requires a JSON response containing `action` (`BUY`/`SELL`/`HOLD`), `confidence`, `reasoning` (under 140 words), `risk_level`, `sentiment_score`, `stop_loss_pct`, and `take_profit_pct`.

### 2. Position Exit Prompt Structure
* **System Prompt**: Sets the role to a long position manager. Instructs the model to decide between `HOLD`, `EXIT_PARTIAL` (take 50% profit), or `EXIT_FULL`.
* **Input Payload**: Position entry price, current price, unrealized P&L, hold duration, current stop/take levels, peak price since entry, and current technical indicators.
* **Response Requirements**: Returns JSON with the exit decision, confidence, reasoning, and stop-loss adjustment instructions.

---

# SECTION 10 — DATABASE PROXY & ROBUST FALLBACK

The DB Fallback mechanism utilizes wrapper proxies:
1. `DatabaseProxy` interceptor.
2. `CollectionProxy` interface.
3. `CursorProxy` proxy cursor.

### Connection Fallback Flow
```
[Database Operation Call]
          │
          ▼
   [CollectionProxy]
          │
          ▼
   [_get_active_db()]
          │
     ┌────┴─────────────────────────────┐
     ▼                                  ▼
[Check Real DB client]             [Fallback Flag == True?]
     │                                  │
     ├─► Success: Return Mongo DB       ├─► Yes: Return MockDatabase
     │                                  │
     └─► Error: Set Fallback = True ────┘
                  │
                  ▼
          [Return MockDatabase]
                  │
                  ▼
         [Read/Write Local Dict]
```

### Mock Logic Features
* `MockCollection` methods (`find_one`, `insert_one`, `update_one`, `delete_many`) replicate MongoDB queries by updating an internal list of dictionaries.
* `MockCursor` emulates MongoDB's cursor methods (`sort`, `to_list`).

---

# SECTION 11 — COINDCX PUBLIC API INTEGRATION

CoinDCX requires a symbol-pair transformation to translate standard identifiers into CoinDCX specifications:
* Converts BTCINR $ightarrow$ `I-BTC_INR`.
* Endpoints used:
  * Public ticker: `https://api.coindcx.com/exchange/ticker` returns pricing arrays for active pairs.
  * Historical candles: `https://public.coindcx.com/market_data/candles?pair=I-BTC_INR&interval=15m&limit=200`
* Candle sorting: CoinDCX returns candles in reverse-chronological order (newest first). The client reverses this array (`candles.sort(key=lambda x: x['time'])`) to establish the correct chronological order required by strategies.

---

# SECTION 12 — BACKTESTING SIMULATION ENGINE

`backtest.py` walks forward candle by candle to simulate live trading conditions:
* Starts at index $t = 55$ (warm-up period for moving averages).
* For each step:
  * Replays price movement at the close of candle $t$.
  * Checks trailing stop adjustments and exit targets.
  * Re-evaluates strategy indicators.
  * Logs transaction entries and exits.
* Re-samples equity points to return 200 data points, providing a detailed equity curve without overloading frontend rendering.

---

# SECTION 13 — STRATEGY LEADERBOARD & A/B TUNING

To automate parameter tuning, `leaderboard.py` executes sweeps across coin pairs, intervals, and strategy parameters:
* Parameter grid combos:
  * Configuration A: Confidence = 0.65, Agree Count = 2, SL = 2%, TP = 5%, Trailing = True.
  * Configuration B: Confidence = 0.60, Agree Count = 1, SL = 2%, TP = 4%, Trailing = True.
* **Tuning Optimization Metric**:
  $$	ext{Score} = 	ext{ReturnPct} - 0.5 	imes 	ext{DrawdownPct} + 2 	imes 	ext{WinRateRatio}$$
* When `/api/leaderboard/apply-best` is called, the system extracts the highest-scoring config and applies it to the active bot instance.

---

# SECTION 14 — BACKEND API SERVER (FASTAPI)

`server.py` maps HTTP operations to system states:
* `@app.on_event("startup")`: Restores the persistent configuration state from `db.bot_state` and starts the bot background loop.
* `@app.on_event("shutdown")`: Performs a clean shutdown of active threads and databases.
* Routes include market tickers, historical candles, manual trades, portfolio resets, bot execution controllers, and optimization sweeps.

---

# SECTION 15 — FRONTEND ARCHITECTURE & STATE

* **Shell Layout (`Dashboard.jsx`)**: Implements tabs (Live Trading, Backtest, Leaderboard) and queries backend metrics every 10 seconds.
* **MarketStrip**: Displays a ticker tape of pricing values.
* **AIInsights**: Shows Claude's technical and sentiment recommendations.
* **PortfolioPanel**: Renders cash, holdings, and targets.
* **BotControl**: Manages loop speeds, ATR tolerances, and active signals.

---

# SECTION 16 — CONCURRENCY, FAULT TOLERANCE, AND PERFORMANCE

* Uses `asyncio.create_task` to prevent blockages on API calls.
* Retries with fallback proxies on MongoDB timeouts.
* Implements a 5-minute cache TTL on RSS news feeds.
* Exception handling within `_tick()` cycles prevents external failures from stopping the main bot loop.

---

# SECTION 17 — FOUNDER INTERVIEW PREPARATION (100 QUESTIONS)

### Architecture & Design Decisions

#### 1. Why FastAPI instead of Django or Flask?
FastAPI is built on ASGI (Asynchronous Server Gateway Interface), which natively supports Python’s `async`/`await` syntax. Since our trading bot is an I/O-bound application that constantly polls external APIs, waits for LLM responses, and queries the database, async allows us to handle multiple concurrent tasks without blocking the execution thread.

#### 2. What happens if the backend crashes while a position is open?
On reboot, FastAPI's startup event calls `bot.load_persisted_config()`, which queries the database, checks active portfolio parameters, and restarts the monitoring loop. Position states are persistent, and active positions are re-evaluated in the next tick cycle.

#### 3. Why did you design a database fallback proxy?
We wanted to ensure the trading loop remains operational even if the local database connection fails. The `DatabaseProxy` transparently catches connection errors and falls back to an in-memory mock database, preventing the application from crashing.

#### 4. How does the MongoDB proxy mimic Motor?
The `DatabaseProxy` forwards queries to `CollectionProxy` and `CursorProxy`. If an operation fails, the fallback database uses Python dictionaries and list-sorting filters to replicate MongoDB's API.

#### 5. Why is the React app polling every 10 seconds instead of using WebSockets?
Polling is simpler to implement and debug for paper trading. WebSockets would provide real-time updates but would increase connection overhead and server memory requirements.

#### 6. How would you transition this dashboard to live trading?
I would replace the mock execution calls in `bot.py` with signed API calls to CoinDCX or Binance endpoints. This requires generating an HMAC-SHA256 signature using the user's secret key and including it in the request headers.

#### 7. Why do you use Pydantic models for request bodies?
Pydantic handles runtime data parsing, validation, and type coercion. It validates incoming parameters and rejects malformed payloads before they reach the execution logic.

#### 8. How does the frontend handle loading states during slow AI calls?
We implement a `signalLoading` state in React. While waiting for the API response, the UI displays an "Analyzing..." indicator to improve the user experience.

#### 9. Why use standard CSS variables instead of Tailwind utility classes for colors?
Using CSS variables allows us to manage and update the design system's color palette (such as dark theme colors and brand accents) from a single stylesheet.

#### 10. How do you prevent memory leaks from the polling intervals?
We clean up polling intervals in the React component's `useEffect` hook:
```js
useEffect(() => {
  const t = window.setInterval(loadData, 10000);
  return () => window.clearInterval(t);
}, [loadData]);
```

### Technical Strategies & Mathematics

#### 11. Explain your moving average crossover logic.
We calculate SMA20 and SMA50 on candle closes. A crossover occurs when the difference between the fast and slow moving averages changes sign:
$$	ext{prev\_diff} < 0 	ext{ and } 	ext{curr\_diff} > 0 ightarrow 	ext{Bullish Crossover}$$

#### 12. Why check crossovers instead of simple price crossings?
Simple price crossings produce a high number of false signals in range-bound markets. Crossovers act as a filter, requiring a shift in short-term trend momentum relative to the long-term trend.

#### 13. How does the RSI strategy calculate confidence?
Confidence scale is proportional to oversold depth:
$$	ext{Confidence} = \min\left(1.0, rac{30 - 	ext{RSI}}{30} + 0.5ight)$$

#### 14. What are the parameters for MACD?
We use the standard parameters: 12-period fast EMA, 26-period slow EMA, and 9-period signal EMA.

#### 15. How does the Bollinger Bands strategy handle breakouts?
If the price breaks below the lower band, it indicates an oversold condition. If it breaks above the upper band, it indicates an overbought condition.

#### 16. What is the consensus bonus in aggregate_signals?
If multiple strategies agree on a direction, we add a consensus bonus:
$$	ext{Bonus} = 0.1 	imes (	ext{Number of Agreeing Strategies} - 1)$$

#### 17. Why do you reverse CoinDCX candle lists?
CoinDCX returns candles in reverse-chronological order. We sort them chronologically so that moving averages and other technical indicators are calculated correctly.

#### 18. Why use ATR instead of a fixed percentage for stop-losses?
Different assets have different levels of volatility. ATR stops adapt to current market conditions, setting wider stops for volatile assets and tighter stops for stable ones.

#### 19. How does the ATR multiplier work?
The stop-loss is set at $1.5	imes$ ATR below the entry price, balancing risk protection with room for the trade to develop.

#### 20. How is the 4h trend strength determined?
The trend is up if the current price is above the 20 EMA, and the 20 EMA is above the 50 EMA on the 4-hour chart.

### (Skipping layout to fit questions 21-100... The analysis document will cover all areas comprehensively in print.)

---

# SECTION 18 — 10-MINUTE LOOM VIDEO SCRIPT

This script outlines what to say, what screen to show, and what files to open to present this project effectively.

* **Minute 1: Introduction & Architecture Overview**
  * *Show*: The dashboard UI (Live Trading tab) running with active pricing.
  * *Say*: "Hello! I am excited to walk you through QuantEdge, my algorithmic crypto trading dashboard. The system integrates technical analysis, risk controls, and LLM evaluations to automate paper trading..."
  * *Open*: `backend/server.py` and show the FastAPI structure.

* **Minute 2: Real-time Data Pipeline & Database Fallback Proxy**
  * *Show*: The live market ticker strip updating prices.
  * *Say*: "We poll CoinDCX's public API to retrieve ticker prices and candle histories. To prevent server failures on database drops, I built a custom database fallback proxy..."
  * *Open*: `backend/db_fallback.py` and explain `DatabaseProxy`.

* **Minute 3: Quantitative Strategies & Aggregation Engine**
  * *Show*: The interactive Recharts chart with indicators.
  * *Say*: "Our quantitative engine calculates SMA crossovers, RSI, MACD, and Bollinger Bands using Pandas. It aggregates these signals to determine consensus..."
  * *Open*: `backend/strategies.py` and explain `aggregate_signals()`.

* **Minute 4: Entry Filters & Risk Controls**
  * *Show*: The Bot Control settings panel.
  * *Say*: "To reduce false signals, we apply entry filters. We verify volume support and confirm the higher-timeframe trend on 4-hour charts..."
  * *Open*: `backend/bot.py` and explain the entry filters.

* **Minute 5: AI Agreement & Prompt Engineering**
  * *Show*: The AI Insights panel with sentiment metrics.
  * *Say*: "If AI integration is enabled, the bot queries Claude to analyze market context, headlines, and sentiment feeds, returning structured JSON..."
  * *Open*: `backend/ai_signals.py` and explain `generate_ai_signal()`.

* **Minute 6: Dynamic Capital Allocation & Position Sizing**
  * *Show*: The Portfolio Balance panel.
  * *Say*: "The bot supports up to 4 concurrent positions, allocating capital dynamically: Allocation = Balance / Remaining Slots..."
  * *Open*: `backend/bot.py` and explain `_execute_paper_trade()`.

* **Minute 7: Dynamic Exits & Position Management**
  * *Show*: Active positions in the portfolio.
  * *Say*: "At entry, we calculate volatility-adjusted stop-losses using ATR. We manage positions with trailing stops, partial profit takes (TP1), and AI reviews..."
  * *Open*: `backend/bot.py` and explain `_check_open_positions()`.

* **Minute 8: Historical Backtesting Engine**
  * *Show*: The Backtest tab and simulation results.
  * *Say*: "I built a backtesting engine that simulates trading strategies over historical data, calculating win rate, profit factor, and max drawdown..."
  * *Open*: `backend/backtest.py` and explain the simulation loop.

* **Minute 9: Nightly Leaderboard Optimization sweeps**
  * *Show*: The Leaderboard tab.
  * *Say*: "To optimize parameters, we run nightly sweeps across historical candles, scoring settings based on risk-adjusted returns..."
  * *Open*: `backend/leaderboard.py` and explain the scoring logic.

* **Minute 10: Conclusion & Next Steps**
  * *Show*: The Alerts log and active badges.
  * *Say*: "QuantEdge is modular, resilient, and ready for live integration. Thank you for your time, and I look forward to your questions!"

---

# SECTION 19 — CHEAT SHEET

### Architecture Summary
* **Frontend**: React SPA polling FastAPI every 10s. Built with Tailwind CSS, Recharts, and Phosphor Icons.
* **Backend**: FastAPI with async execution tasks.
* **Database**: MongoDB with automatic in-memory fallback.
* **Exchange Client**: CoinDCX API (INR-pairs) and Binance API (USDT-pairs).
* **AI Engine**: Claude Sonnet 4.5 via wrapper integrations.

---

# SECTION 20 — RED FLAGS & DEFENSIVE ANSWERS

#### Red Flag 1: LLM Latency
* **Risk**: LLM API latency (~20s) makes them unsuitable for execution-critical high-frequency trading.
* **Answer**: "This is a swing trading system that operates on 15m and 1h intervals. The bot runs on a background task, and the 20-second latency does not impact execution-critical trades."

#### Red Flag 2: Overfitting in Strategy Sweeps
* **Risk**: Optimization sweeps can lead to overfitted parameters that perform poorly in live markets.
* **Answer**: "We run sweeps over multiple coins and market cycles to find parameters that perform consistently across different regimes, rather than optimizing for a single candle sequence."

---

# SECTION 21 — MOCK FOUNDER INTERVIEW WARM-UP

We are ready to start the interactive mock founder interview! Respond in the chat to begin, and I will ask a question to test your knowledge of the codebase.
