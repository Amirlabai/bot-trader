# Project Context: bot-trader

## Overview
`bot-trader` is a multi-strategy algorithmic trading system built in Python. It supports bi-directional trading (Long/Short) for both Crypto and Forex markets, utilizing the Financial Modeling Prep (FMP) API for data ingestion.

## Architecture
- **Core Engine**: `src/main.py` orchestrates the trading loop, strategy loading, and report generation.
- **State Management**: `src/ledger_manager.py` manages independent "wallets" for each strategy, tracking cash, open positions, and trade history in `data/ledger.json`.
- **Reporting & Visualization**: 
    - `src/reporting.py` processes ledger data to reconstruct equity curves and generates trade entry charts using `matplotlib`.
    - `docs/index.html` serves as a standalone SPA dashboard for monitoring performance and reviewing trade history.
- **Strategies**: Modular strategy logic is stored in `strategies/` (e.g., `MovingAverageStrategy`, `RSIStrategy`).

## Risk Management
- **Model**: 1% Absolute Equity Risk per trade.
- **Position Sizing**: Automatically calculated based on ATR-derived Stop Loss levels.
- **Exits**: Supports multi-stage exits (TP1 at 1.0 ATR, move SL to breakeven) and trailing stops.

## Tech Stack
- **Language**: Python 3.9+ (Type Hinting, Modular Design).
- **Libraries**: `pandas` (data analysis), `matplotlib` (charting), `gitpython` (ledger syncing), `python-dotenv` (config).
- **Automation**: GitHub Actions for daily execution and semantic releases.
