# Project Context: bot-trader

## Overview
`bot-trader` is a multi-strategy algorithmic trading system built in Python. It supports bi-directional trading (Long/Short) for both Crypto and Forex markets. Daily bars come from Financial Modeling Prep (FMP). yfinance is a one-shot VM probe only and is never used as OHLCV.

## Architecture
- **Core Engine**: `src/main.py` orchestrates the trading loop, strategy loading, and report generation.
- **Data**: `src/data_ingestion.py` (`DataFetcher.get_data`) loads daily OHLCV from FMP. On GitHub Actions, one Yahoo probe per session (`probe_yahoo`) only to detect VM rate-limit/block. Local runs skip the probe.
- **State Management**: `src/ledger_manager.py` manages independent "wallets" for each strategy, tracking cash, open positions, and trade history in `data/ledger.json`.
- **Reporting & Visualization**: 
    - `src/reporting.py`: Reconstructs equity curves, calculates advanced performance metrics (Win Rate, Profit Factor, Max DD), and renders entry charts.
    - `docs/index.html`: Advanced SPA dashboard with asset exposure tracking, trade history filtering, and P/L percentage analysis. Visual system: `DESIGN.md` and `.impeccable/design.json` (After-Hours Desk).
- **Strategies**: Modular strategy logic is stored in `strategies/` (e.g., `MovingAverageStrategy`, `RSIStrategy`).

## Risk Management
- **Model**: 1% of total equity per new open (`cash + open positions at entry cost`; no unrealized P/L).
- **Position Sizing**: `quantity = (equity × equity_risk_pct) / |entry − stop|`; then capped by `max_notional_pct` of equity (default 25%), then by free cash. Caps reduce notional only — actual risk may fall below 1% but the trade still opens.
- **Undersize guard**: `RISK_SETTINGS` in `src/config.py` (`min_risk_fraction`, `min_notional_usd`, `equity_risk_pct`, `max_notional_pct`). Env floats use `_env_float` with clear errors on bad values. `min_risk_fraction` is skipped when a notional or cash cap applies.
- **Exits**: `quantity_pct` on close/cover only (TP1 50%, full exit 100%). TP1 at 1.0 ATR (50% out, SL to breakeven); trailing 1.5 ATR after TP1. TP1 and SL hits use the last closed bar **high/low** (wicks); trail *updates* still use close. Same-bar both wicks: TP1 first, then remainder SL via `shared/trade_exec.py` `apply_exit` (live `main.py` and `resim_engine.py`). Follow-up uses ATR from `generate_signal`, not a recompute. SL updates require `new_sl > 0` (hold, TP1, ledger ADD). TP1 fires **once per leg** (`tp1_hit`, `initial_qty`, `tp1_already_done()`); duplicate TP1 fills are skipped and do not trigger same-bar SL.
- **Trade audit**: `scratch/audit_trades.py` writes `docs/trade_audit.md` (per-leg TP1/final pattern). Run after backfill via `update_snapshots.py` or standalone.
- **Trailed stop**: After TP1, remainder SL at breakeven uses `Stop Loss Hit`. Once the trail has moved off entry, a full remainder exit uses `Trailed Stop Hit @ fill (SL level)` (long/short variants in `shared/constants.py`).
- **TP1 flag**: `shared/constants.py` defines `TP1_HIT_REASON_*`, `TRAILED_STOP_*`, `reason_is_tp1_exit()`, `reason_is_trailed_stop()`, `tp1_already_done()` (uses `TP1_MAX_REMAINING_FRACTION` when `tp1_hit` unset). Close fills/snapshots live in `shared/exit_snapshots.py` (used by `main.py` and `scratch/update_snapshots.py`, not via `main` import).
- **Close snapshots**: Chart SL/TP come from **position levels at exit** (`chart_levels_from_position`), not post-TP1 signal SL. Fields: `exit_kind` (`tp1_partial` | `stop_loss` | `trailed_stop`), `stop_loss_at_exit`, `take_profit_at_exit`, `quantity_pct`, `reason` (fill-adjusted). Backfill: `scratch/update_snapshots.py` (`--dry-run` skips save; default run backs up `data/ledger.json.bak` first). **History repair**: `scratch/repair_ledger_legs.py` or `scratch/audit_trades.py --fix-history` consolidates violating legs to TP1+final, replays cash/positions, saves ledger — then always run `update_snapshots.py` (repair strips stale snapshots; backfill is not chained). `docs/trade_audit.json` and `docs/report_data.json` are gitignored; keep `docs/trade_audit.md` and `docs/report_data.js` for Pages.
- **Resim ledger**: `scratch/resimulate.py` writes `data/ledger_resim.json` (local compare artifact; gitignored). Use `--replace-ledger` only when intentionally overwriting live `ledger.json`.
- **Risk sizing**: `shared/risk_sizing.py` (`size_for_risk`, `should_open_after_sizing`) used by `src/main.py` and `scratch/resim_engine.py`.
- **Same-bar reversal**: After a full SHORT cover or LONG close, `main.py` refreshes position state and may open the opposite side in the same bar.
- **Debug**: Set `BOT_TRADER_DEBUG=1` to re-raise after signal generation errors (traceback always printed).
- **Trade charts**: Close-only snapshots (`_build_close_snapshot` on exit in `main.py`); last ~20 daily bars ending on the close bar; chart shows SL/TP, entry price line, exit price/date. OPEN history does not store chart snapshots. Backfill closes: `.\.venv\Scripts\python.exe scratch\update_snapshots.py`.
- **Stop-loss fills**: Stop/trail exits always fill at the **SL level** (including a wick through SL that closes back inside). TP1 fills at stored **take_profit**. Same rule in live `main.py` and backfill (`apply_close_fill_to_event` updates `price`, `pnl`, and strategy `cash`).
- **Dashboard**: Pair performance (rolling winners/losers) under the equity/exposure charts; closed trades table shows exit date, entry date, days held, qty, entry/exit prices, and P/L; expand row shows SL at exit and TP1 target when applicable. Open positions show entry date. Mobile (≤720px): stacked header/filter, 2-col KPI grid with Total Trades spanning, compact charts, 12px expand padding, primary table columns only (secondary fields in expand). Money columns use tabular numerals.
- **Report**: `trade_history` exports `entry_date`, `exit_date`, `hold_days`, `exit_kind`, `stop_loss_at_exit`, `take_profit_at_exit`, `quantity_pct`, `reason`, `chart_id` (PNG bytes live in `docs/report_charts.js`, loaded on row expand). Regenerate: `scratch\update_snapshots.py --report-only`.
- **Dashboard load**: Lean `report_data.js` (~0.4 MB) for first paint; `report_charts.js` (~20 MB) fetched only when a closed-trade row is expanded.

## Tech Stack
- **Language**: Python 3.9+ (Type Hinting, Modular Design).
- **Libraries**: `pandas`, `matplotlib`, `gitpython`, `python-dotenv`, `yfinance`.
- **Market data**: FMP for all OHLCV (cache by bot symbol). Yahoo: one `5d` probe of `BTC-USD` per `DataFetcher` session on GitHub Actions only. Empty/429/block: `ALERT:` plus GitHub Actions `::warning::`; bars still from FMP. FMP 429: one `::error::`. Missing FMP data (not rate-limited): `::error::`. Summary: `DataFetcher.report_fetch_alerts()`.
- **Automation**: GitHub Actions for daily execution and semantic releases.
- **Local knowledge graph**: `graphify-out/` (gitignored). Incremental rebuild: `/graphify --update`.

## Deployment
- **Dashboard**: Hosted on GitHub Pages via `docs/index.html` (`report_data.js` + lazy `report_charts.js`).
- **Execution**: Runs daily at 00:00 UTC via `.github/workflows/daily_trade.yml` (`python src/main.py` from **repo root**). `main.py` sets `REPO_ROOT` on `sys.path` so `shared.constants` resolves; do not run with cwd=`src/`.
- **Debug**: `BOT_TRADER_DEBUG=1` re-raises after signal errors.
