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
- **Position Sizing**: `quantity = (equity × 0.01) / |entry − stop|`; capped by free cash (100% collateral for shorts).
- **Undersize guard**: `RISK_SETTINGS` in `src/config.py` (`min_risk_fraction`, `min_notional_usd`, `equity_risk_pct`).
- **TP1 flag**: `TP1_HIT_REASON_LONG` / `TP1_HIT_REASON_SHORT` in `src/config.py` (`TP1_EXIT_REASONS`); imported by `main.py` and `strategies/base_strategy.py`.
- **Exits**: TP1 at 1.0 ATR (50% out, SL to breakeven); trailing 1.5 ATR after TP1. Short TP1 must set `tp1_hit` on cover (buy) path.
- **Snapshot Hardening**: Dynamic windowing and indicator overlays ensure trade charts are accurate and context-rich.

## Tech Stack
- **Language**: Python 3.9+ (Type Hinting, Modular Design).
- **Libraries**: `pandas`, `matplotlib`, `gitpython`, `python-dotenv`.
- **APIs**: Financial Modeling Prep (FMP) for market data.
- **Automation**: GitHub Actions for daily execution and semantic releases.

## Deployment
- **Dashboard**: Hosted on GitHub Pages via `docs/index.html`.
- **Execution**: Runs daily at 22:00 UTC via `.github/workflows/daily_trade.yml`.
