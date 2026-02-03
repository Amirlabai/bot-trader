# Bot Trader Status
**Last Updated:** 2026-02-03 20:36:00 UTC

## Portfolio Status

> **Interactive Dashboard**: View the full [Performance Report](docs/index.html) for real-time equity curves and positions.

---

## Session Work Summary
*A summary of changes implemented during this development session.*

### 1. Architecture & Core
- **Long/Short Trading**: System now supports bi-directional trading.
    - **Long**: Buy low, Sell high.
    - **Short**: Open Short (Sell) high, Cover (Buy) low.
    - **Collateral**: Shorts require 100% cash collateral.
- **Multi-Strategy Engine**: Refactored `src/main.py` and `src/ledger_manager.py` to support multiple simultaneous strategies.
- **Independent Ledgers**: Each strategy now has its own isolated "Wallet" in `ledger.json`.

### 2. Risk Management (Universal)
- **ATR Integration**: Promoted ATR calculation to `BaseStrategy`, making it available to ALL strategies.
- **Dynamic Position Sizing**: Adopted **1% Equity Risk** model.
    - Trade size is calculated so that a Stop Loss hit equals exactly 1% loss of total realized equity.
- **Advanced Exits**:
    - **Stop Loss**: 1.5x ATR from Entry.
    - **Take Profit 1**: Sell 50% at 1.0x ATR gain, move SL to Breakeven.
    - **Trailing Stop**: tightens SL as price moves in favor (1.5 ATR trailing).

### 3. Automation & DevOps
- **Semantic Release**: Implemented `python-semantic-release` via GitHub Actions (`.github/workflows/release.yml`) to automatically version tag (`v1.1.0`), changelog, and release on every merge to master.
- **Git Hardening**:
    - Updated specific git commands to prevent "Detached HEAD" in CI.
    - Implemented `fetch-depth: 0` for proper history analysis.
- **Rate Limiting**: Added strict 15s delay between Forex calls to respect Alpha Vantage Free Tier (5 calls/min).

### 4. Data Infrastructure (2026-02-03)
- **FMP API Migration**: Switched all data ingestion (Forex & Crypto) to Financial Modeling Prep (FMP) API.
    - Replaces Alpha Vantage and CCXT/Binance.
    - Uses stable `historical-price-eod/full` endpoint.
- **In-Memory Caching**: Implemented session-level caching (`DataFetcher.cache`) to prevent redundant API calls for the same ticker.
- **Smart Symbol Mapping**: Auto-converts `BTC/USDT` -> `BTCUSD` for FMP compatibility.

### 5. Strategy Logic
- **Clean Data Slicing (No Repainting)**: 
    - Strategies now use `_get_closed_candle_index` to intelligently slice the dataset.
    - **Logic**: Any open/incomplete candle (Today) is stripped from the dataset *before* calculating indicators (SMA, RSI, ATR).
    - **Result**: Signals are derived strictly from confirmed historical closes, while execution occurs at the real-time market price (`iloc[-1]` of original data).

### 6. Reporting & Visualization
- **SPA Dashboard**: Implemented a standalone Single Page Application (`docs/index.html`) for GitHub Pages.
- **Interactive Charts**: Integrated Chart.js to visualize Equity Curve (Cash Balance) history.
- **Reporting Engine**: `src/reporting.py` now outputs structured JSON (`docs/report_data.json`) instead of static HTML, enabling dynamic strategy selection and filtering.

### 7. Fixes
- **GBP/JPY Detection**: Fixed Asset Type detection to correctly route GBP pairs to Forex API.
- **Binance Time Drift**: Increased `recvWindow` and added manual time sync to fix `Timestamp for this request was 1000ms ahead` errors.
- **Binance CI Fallback**: Automatically switches to `Binance.US` (Public/Anonymous) when Global API is blocked (Error 451).
- **Git Sync Hardening**: Implemented `pull --rebase` before push to handle remote updates seamlessly.
