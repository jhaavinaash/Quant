# Quant Center Architecture Map

**Permanent source of truth:** `C:\Users\Avinaash\quant`  
**Current daily application:** `dashboard\app_ai.py`  
**Future website:** `quant-center-publish/` (React + FastAPI adapters; not hosted yet)

This document describes the existing structure. It is not a redesign. All trading
logic, trading data and operational files remain owned by the Quant root.

## 1. System boundaries

```text
Market data / NSE calendar / Google Sheets / news feeds
                         |
                         v
 C:\Users\Avinaash\quant  (canonical trading system)
 ├── Engines + orchestrator
 ├── Signals, trade book and market data
 ├── AI Scanner / Gemini Flasher
 ├── Market Intelligence
 └── Streamlit dashboard (current operating UI)
                         |
                         | QUANT_BASE_DIR: files, imports, subprocesses
                         v
 quant-center-publish/backend  (FastAPI adapter)
                         |
                         | REST/JSON
                         v
 quant-center-publish/frontend (future quantcenter.in React UI)
```

The website is a presentation and control layer. It must call existing Quant
modules or consume their files through the backend. Strategy, ranking,
portfolio, risk and Market Intelligence rules must not be rewritten in React.

## 2. Repository structure

| Path | Responsibility | Authority |
|---|---|---|
| `config.py` | Resolves canonical paths, engine settings and environment credentials | Canonical |
| `Engines/` | E1–E6, G1 and S1 screening pipelines | Canonical trading logic |
| `core/orchestrator.py` | Runs E1–E6 and G1, normalizes signals and applies earnings blocks | Canonical workflow |
| `core/ai_scanner.py` | Stock-level AI opportunity scan | Canonical |
| `core/gemini_flasher.py` | Independent Gemini/technical scanner | Canonical |
| `core/signal_alerts.py` | Telegram and email notification dispatch | Canonical |
| `market_intelligence/` | Trend, Participation, Leadership, Stress, interpretation and Driving Mode | Canonical |
| `Data/` | Historical prices, universes, calendar, engine status and scanner ledgers | Canonical data |
| `Signals/` | Current signal queue and engine-run log | Canonical operational state |
| `Portfolio/` | Trade book and blocked-signal records | Canonical operational state |
| `dashboard/app_ai.py` | Streamlit trading control center used daily | Current application |
| `research/` | Isolated experiments and reports; never production input | Research only |
| `quant-center-publish/backend/` | FastAPI adapters to Quant plus website authentication/state | Future website |
| `quant-center-publish/frontend/` | React presentation layer | Future website |

`dashboard/app_ai2.py`, `dashboard/app_upgraded.py` and dashboard copies under
`quant-center-publish/` are not the current application.

## 3. Canonical paths and data stores

`config.py` loads `.env`, resolves folder-name casing and exposes the principal
files:

| File | Producer | Main consumers |
|---|---|---|
| `Data/stock_prices_clean.csv` | Price update/download processes | E2, E4, Market Intelligence |
| `Data/sector_map_fixed.csv` | Maintained universe file | Engines, AI Scanner, Market Intelligence |
| `Data/result_calendar.csv` | `core/result_calendar_updater.py` | Orchestrator earnings block, scanner |
| `Data/engine_status.csv` | Orchestrator | Streamlit and website dashboard |
| `Signals/master_signals.csv` | Orchestrator; S1 appends separately | Today Actions, alerts, API |
| `Signals/engine_run.log` | Dashboard run controls | Operational diagnostics |
| `Portfolio/blocked_signals.csv` | Orchestrator | Alerts tab |
| `Portfolio/trades_log.csv` | Manual Trade Entry and later execution/fill processes | Positions, P&L, health, news |
| `Data/ai_paper_trades.csv` | AI Scanner UI | AI Intelligence |
| `Data/flasher_tracked_trades.csv` | Gemini Flasher UI | Gemini ledger |

The Streamlit dashboard derives open positions from `trades_log.csv` rows whose
status is `OPEN`. PostgreSQL is not the trading ledger.

### Databases

- **PostgreSQL (website only):** users, broker credentials/sessions and
  instruments. Configured by `quant-center-publish/backend/app/core/config.py`.
- **Quant files:** signals, positions, trades, engine status and decisions remain
  in CSV/JSON/SQLite artifacts under `QUANT_BASE_DIR`.
- **Website background services:** FastAPI starts AI Scanner and F1 Basket
  watchers; when their production layer exists, they use SQLite under
  `F0/production/`.
- Backend services reference `F0/`, `execution/`, `credentials/` and additional
  signal-layer modules. Those paths are not present in this checked workspace;
  they may exist only on the live laptop and must be verified there before
  execution-related website work.

## 4. Primary operating flows

### A. Engine scan and signals

```text
Dashboard "Run Engines"
  -> core/result_calendar_updater.py
  -> core/orchestrator.py
  -> Engines E1, E2, E3, E4, E5, E6, G1
  -> normalize BUY signals
  -> block tickers with results inside the configured window
  -> Signals/master_signals.csv
  -> Data/engine_status.csv
  -> Portfolio/blocked_signals.csv
```

After a successful orchestrator run, the dashboard separately invokes
`core/signal_alerts.py` to send Telegram/email alerts. Alert dispatch is not part
of the orchestrator itself.

S1 is separate: `Engines/claude_system1_live.py` runs from the 3:15 PM button
and appends S1 signals. The orchestrator preserves same-day S1 rows when it
overwrites the master signal file.

### B. Trade supervision

```text
Portfolio/trades_log.csv
  -> Streamlit live-price refresh through yfinance
  -> open-position SL/TP gap alerts
  -> P&L, engine health and closed-trade analytics
  -> manual add/edit/close/delete through Trade Entry
```

The current Streamlit application does not place broker orders. Broker routing,
fill reconciliation and canonical position snapshots belong to the separate
execution/F0 layer when present.

The future website position service expects `OPEN_POSITIONS_FILE` (normally
`F0/production/open_positions.csv`); this differs from Streamlit's direct
`trades_log.csv` view.

### C. Independent intelligence tools

- **AI Scanner:** `core/ai_scanner.py` reads the stock universe, results calendar
  and yfinance history; UI results can be recorded in `ai_paper_trades.csv`.
- **Gemini Flasher:** `core/gemini_flasher.py` uses the Nifty 500/universe files
  and yfinance; tracked outcomes use a separate flasher ledger.
- **Market Intelligence:** reads `stock_prices_clean.csv` and
  `sector_map_fixed.csv`, then runs:

```text
calculate_market_intelligence()
  -> interpret_market_intelligence()
  -> determine_driving_mode()
  -> Personal Market Briefing
```

Market Intelligence is read-only, engine-independent and describes the overall
trading approach. It does not generate orders or modify F1.

## 5. Streamlit dashboard

`dashboard/app_ai.py` is a monolithic Streamlit application. It reads canonical
Quant files directly and invokes Python modules/subprocesses directly.

| Area | Responsibility |
|---|---|
| Market Briefing | Overall approach, four conditions and transparent metrics |
| Today Actions | Current normalized signals and live prices |
| Open / Closed Positions | Trade monitoring, P&L and SL/TP proximity |
| Engines / Alerts | Engine status, health and blocked signals |
| News | News for active portfolio tickers |
| Portfolio | Read-only Google Sheets medium-term portfolio |
| AI Intelligence | AI Scanner and paper-trade ledger |
| Trade Entry | Direct manual updates to `trades_log.csv` |
| Gemini Flasher | Independent scanner and tracking ledger |

Despite its historical “read-only” header, the dashboard can write the trade
book, scanner ledgers and engine log, and its buttons launch production
subprocesses. Treat it as an operational control application.

## 6. Future website and API

### React

`quant-center-publish/frontend/src/main.tsx` starts the React application;
`App.tsx` registers routes and `views/Dashboard.tsx` is `/`. Axios currently
targets `http://127.0.0.1:8000/api/v1`, so this is still a local-development
configuration. The React/FastAPI application is substantially built and runs
locally, but it is not publicly hosted.

### FastAPI

`quant-center-publish/backend/app/main.py` mounts `/api/v1` routers and connects
to PostgreSQL. Services bridge to Quant through `QUANT_BASE_DIR` by:

1. reading canonical files,
2. importing canonical Quant modules, or
3. launching canonical subprocesses.

Current API domains include dashboard, positions, trades, trade entry,
execution, brokers, AI Scanner, F1/F1 Basket and Market Briefing. The website
must remain an adapter: React renders API responses; FastAPI must not duplicate
strategy formulas. Some dashboard KPI formulas are currently mirrored in
FastAPI services, which is an existing drift risk.

### Hosting status

Repository evidence shows local Vite (`:5173`), FastAPI (`:8000`), Streamlit
(`:8501`) and PostgreSQL workflows only. The frontend API URL is localhost,
Docker Compose does not include the frontend or reverse proxy, and no active
hosting pipeline is defined. A Caddy configuration exists but is not connected
to Compose. `quantcenter.in` is therefore a target, not a currently deployed
system.

## 7. Rules for future development

1. Begin every change in `C:\Users\Avinaash\quant`.
2. Preserve `dashboard/app_ai.py` as the current operational application.
3. Keep strategy and decision logic in canonical Quant modules.
4. Website work must consume canonical outputs through thin APIs.
5. Never make React the source of trading calculations.
6. Never write production files from research code.
7. Confirm the exact producer and consumer before changing any CSV schema.
8. Treat `trades_log.csv`, `master_signals.csv` and engine status as shared
   contracts; coordinate all readers before changing them.
9. Verify locally present but untracked execution/F0 modules before modifying
   broker, fill or F1 flows.
10. Do not treat duplicate dashboards or `quant-center-publish` copies as an
    independent source of truth.
11. Check path casing before Linux deployment: root config resolves folder case,
    while some website services use lowercase paths directly.
