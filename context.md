# Project Context: bot-trader

## Overview
`bot-trader` is a multi-strategy algorithmic trading system built in Python. It supports bi-directional trading (Long/Short) for both Crypto and Forex markets, utilizing the Financial Modeling Prep (FMP) API for data ingestion.

## Architecture
- **Core Engine**: `src/main.py` orchestrates the trading loop, strategy loading, and report generation.
- **State Management**: `src/ledger_manager.py` manages independent "wallets" for each strategy, tracking cash, open positions, and trade history in `data/ledger.json`.
- **Reporting & Visualization**: 
    - `src/reporting.py`: Reconstructs equity curves, calculates advanced performance metrics (Win Rate, Profit Factor, Max DD), and renders entry charts.
    - `docs/index.html`: Advanced SPA dashboard with asset exposure tracking, trade history filtering, and P/L percentage analysis.
- **Strategies**: Modular strategy logic is stored in `strategies/` (e.g., `MovingAverageStrategy`, `RSIStrategy`).

## Risk Management
- **Model**: 1% of total equity per trade (`cash + open positions at entry cost`; no unrealized P/L).
- **Position Sizing**: `quantity = (equity × equity_risk_pct) / |entry − stop|`; capped by free cash (100% collateral for shorts). Entry signals may set `quantity_pct` (e.g. 0.1) to scale the risk-sized quantity before open.
- **Undersize guard**: `RISK_SETTINGS` in `src/config.py` (`min_risk_fraction`, `min_notional_usd`, `equity_risk_pct`). Env floats use `_env_float` with clear errors on bad values.
- **TP1 flag**: `shared/constants.py` defines `TP1_HIT_REASON_*` and `TP1_EXIT_REASONS`; re-exported from `src/config.py` for `main.py`.
- **Exits**: TP1 at 1.0 ATR (50% out, SL to breakeven); trailing 1.5 ATR after TP1. SL updates require `new_sl > 0` (hold, TP1, ledger ADD).
- **Same-bar reversal**: After a full SHORT cover or LONG close, `main.py` refreshes position state and may open the opposite side in the same bar.
- **Debug**: Set `BOT_TRADER_DEBUG=1` to re-raise after signal generation errors (traceback always printed).
- **Trade charts**: Exit price drawn as horizontal line (`exit_price` from ledger fill); report metadata includes `initial_cash` for dashboard baseline.

## Tech Stack
- **Language**: Python 3.9+ (Type Hinting, Modular Design).
- **Libraries**: `pandas`, `matplotlib`, `gitpython`, `python-dotenv`.
- **APIs**: Financial Modeling Prep (FMP) for market data.
- **Automation**: GitHub Actions for daily execution and semantic releases.

## Deployment
- **Dashboard**: Hosted on GitHub Pages via `docs/index.html`.
- **Execution**: Runs daily at 00:00 UTC via `.github/workflows/daily_trade.yml` (`python src/main.py` from **repo root**). `main.py` sets `REPO_ROOT` on `sys.path` so `shared.constants` resolves; do not run with cwd=`src/`.
- **Debug**: `BOT_TRADER_DEBUG=1` re-raises after signal errors.
