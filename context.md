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
- **Model**: 1% Absolute Equity Risk per trade.
- **Position Sizing**: Automatically calculated based on ATR-derived Stop Loss levels.
- **Exits**: Supports multi-stage exits (TP1 at 1.0 ATR, move SL to breakeven) and trailing stops.
- **Snapshot Hardening**: Dynamic windowing and indicator overlays ensure trade charts are accurate and context-rich.

## Tech Stack
- **Language**: Python 3.9+ (Type Hinting, Modular Design).
- **Libraries**: `pandas`, `matplotlib`, `gitpython`, `python-dotenv`.
- **APIs**: Financial Modeling Prep (FMP) for market data.
- **Automation**: GitHub Actions for daily execution and semantic releases.

## Deployment
- **Dashboard**: Hosted on GitHub Pages via `docs/index.html`.
- **Execution**: Runs daily at 22:00 UTC via `.github/workflows/daily_trade.yml`.
