# Bot Trader Status
**Last Updated:** 2026-02-02 20:10:00 UTC

## Portfolio Summary
| Strategy              | Cash        | Equity       | Open Positions |
| :-------------------- | :---------- | :----------- | :------------- |
| `ma_crossover_crypto` | `$10000.00` | `$10000.00`* | 0              |
| `ma_crossover_forex`  | `$10000.00` | `$10000.00`* | 0              |
| `rsi_crypto`          | `$0.00`     | `$10000.00`* | 10             |
| `rsi_forex`           | `$10000.00` | `$10000.00`* | 0              |

_(*) Equity is estimated based on Entry Price (Unrealized PnL not real-time in this report)_

## Active Positions
### rsi_crypto
- **BTC/USDT**: 0.018755 units @ `$78917.1200`
  - SL: `$73657.2011` | TP1 Hit: False
- **ETH/USDT**: 0.347163 units @ `$2358.2000`
  - SL: `$2070.1507` | TP1 Hit: False
- **BNB/USDT**: 1.789778 units @ `$776.0900`
  - SL: `$720.2171` | TP1 Hit: False
- **XRP/USDT**: 635.396101 units @ `$1.6414`
  - SL: `$1.4852` | TP1 Hit: False
- **SOL/USDT**: 8.369201 units @ `$104.8200`
  - SL: `$92.8714` | TP1 Hit: False
- **ADA/USDT**: 2951.718322 units @ `$0.3000`
  - SL: `$0.2665` | TP1 Hit: False
- **DOGE/USDT**: 8903.303762 units @ `$0.1085`
  - SL: `$0.0973` | TP1 Hit: False
- **AVAX/USDT**: 92.226614 units @ `$10.1900`
  - SL: `$9.1057` | TP1 Hit: False
- **DOT/USDT**: 557.546794 units @ `$1.5590`
  - SL: `$1.3796` | TP1 Hit: False
- **TRX/USDT**: 2574.919125 units @ `$0.2841`
  - SL: `$0.2738` | TP1 Hit: False

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

### 4. Fixes
- **GBP/JPY Detection**: Fixed Asset Type detection to correctly route GBP pairs to Forex API.
- **Binance Time Drift**: Increased `recvWindow` and added manual time sync to fix `Timestamp for this request was 1000ms ahead` errors.
- **Binance CI Fallback**: Automatically switches to `Binance.US` (Public/Anonymous) when Global API is blocked (Error 451).
- **Git Sync Hardening**: Implemented `pull --rebase` before push to handle remote updates seamlessly.
