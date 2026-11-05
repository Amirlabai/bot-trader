# Research

Offline replay of the live daily crypto strategy, for comparing exit policies, confirmation entries and entry filters. Ported from `asset-trail/research/` (4h Binance) to bot-trader daily bars (yfinance). Nothing here places orders, touches `data/ledger.json`, or changes live behavior.

## Layout

| Path | Role | In git |
|------|------|--------|
| `experiments/*.json` | Experiment specs (what to run) | yes |
| `results/<experiment>/<YYYYmmdd-HHMM>_<git sha>[_dirty]/` | One run: `spec.json`, `variants.csv`, `report.md` | yes |
| `results/.../trades.csv.gz` | Every simulated trade of that run | no |
| `cache/signals/`, `cache/learning/` | Per-bar entry signals; learning export | no |
| `history.py` | Daily bars from `DataFetcher.get_data` (disk cache in `data/ohlcv_cache/`) | |
| `signals.py` | One pass of the live strategy per pair. Entries do not depend on the exit, so one pass serves every variant | |
| `exit_policy.py` | Exit rules (`ExitPolicy`, `step_bar`). Research only; live keeps `BaseStrategy.check_risk_management` | |
| `engine.py` | Simulates trades for one `ExitPolicy` | |
| `metrics.py`, `report.py`, `trade_stats.py` | Stats, in-sample and out-of-sample split, ranked report | |
| `features.py`, `context.py`, `filters/` | Entry features, breadth and prior-trade context, walk-forward false-start models | |
| `entries.py`, `structure.py`, `audit.py` | Confirmation entries, swing pivots, loser audit | |
| `run.py`, `compare.py`, `export_learning.py` | CLIs | |

The replay uses the live wallet `ma_crypto_long_trail` (`settings.STRATEGY_ID`): its params from `src/config.py` and its pairs (the CMC universe). A spec may set `"strategy_id"` to replay another wallet of the same strategy, e.g. `ma_crypto_long_tp1`.

## Commands (from the repo root)

```
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt    # once: pytest, scikit-learn
.\.venv\Scripts\python.exe -m research.run research/experiments/baseline.json
.\.venv\Scripts\python.exe -m research.run research/experiments/scale_out_grid.json
.\.venv\Scripts\python.exe -m research.run <spec> --refresh        # force a Yahoo pull first
.\.venv\Scripts\python.exe -m research.run <spec> --pairs BTC/USDT ETH/USDT
.\.venv\Scripts\python.exe -m research.compare research/results/<a>/<run> research/results/<b>/<run> [--variants baseline r1_sell50]
.\.venv\Scripts\python.exe -m research.export_learning             # baseline -> research/cache/learning/backfill_trades.jsonl
.\.venv\Scripts\python.exe -m pytest tests
```

The first run computes the signals (about 50 seconds per pair for 4 years: live calls the strategy on the full history each day, so the replay does too). Later runs on the same bars reuse the cache and take seconds. New daily bars change the cache key, so the next run after a data refresh recomputes.

## Adding an experiment

Copy a spec in `experiments/` and edit it:

- `variants`: explicit list of `ExitPolicy` fields.
- `grid`: list of blocks; each block is the cartesian product of its lists.

`ExitPolicy` fields:

- `step_r`: R spacing between ladder levels.
- `first_r`: first level; defaults to `step_r`.
- `fraction`: share of what is still held sold at the first level.
- `fraction_step`: added at each later level.
- `fraction_max`: cap on the share.
- `max_steps`: limit on the number of levels.
- `breakeven_after_first`: move the stop to entry after the first sale.
- `sl_atr`, `trail_atr`: stop and trail widths in ATR (live crypto: 1 and 3). `trail_atr: 0` turns the trail off.
- `atr_mode`: `frozen` (live: trail distance = `trail_atr` x ATR at entry) or `current` (asset-trail: bar ATR, widened to the initial stop distance x `trail_atr / sl_atr`).
- `trail_arm_r`: the trail moves only while the close is at least this many R above entry (live crypto: 0).
- `tp1_live`: the live TP1 wallet: sell `tp1_fraction` (0.5) at entry + 1 entry ATR, move the stop to entry, then trail. TP1 wins a bar that also touches the stop, and the remainder is checked from the next bar.

Early exit:

- `early_exit_bars`: N days; after exactly N bars, sell the rest at the close if the best high so far is below entry + `early_exit_min_r` x R.
- `early_exit_min_r`: the progress threshold, in R.

The baseline (the live wallet's exit) is included automatically. Variant names add a tag for every live-exit field that differs from the wallet (`atrcurrent`, `trail4`, `arm1`, `tp1`, ...).

Other spec keys:

- `pairs`: a list, or `"universe"` for the live crypto list.
- `strategy_id`: live wallet to replay (default `ma_crypto_long_trail`).
- `btc_symbol`: the BTC pair used for the regime features (default `BTC/USDT`).
- `years` (default 4), `fee_rate`, `oos_months`.

All bar counts in specs are days. The asset-trail specs were rescaled from 4h bars (`early_exit_bars` 3..18 became 2..15, `within` 3..24 became 2..10). `lookback` values were kept as daily bars.

### Entry modes block (confirmation entries)

```
"entry_modes": [
  {"type": "higher_high", "ref": ["signal_high", "swing_high"], "within": [2, 3], "trigger": "break"},
  {"type": "resistance_break", "level": "pivot", "pivot_k": 5, "lookback": 60, "within": 5,
   "none_above": "enter", "trigger": "break"},
  {"type": "resistance_break", "level": "band", "lookback": 55, "within": 5, "trigger": "break"}
]
```

- After the EMA crossover, the signal waits up to `within` bars for price to clear a level:
  - `higher_high`: the signal bar high (`signal_high`), or the higher of that and the last swing high (`swing_high`).
  - `resistance_break` with `pivot`: the nearest confirmed swing high above price, from the last `lookback` bars (`research/structure.py`; a pivot is known only `pivot_k` bars after it forms).
  - `resistance_break` with `band`: the `lookback`-bar high.
- `trigger: close` buys at a close above the level with a fresh `sl_atr` x ATR stop. `trigger: break` is a buy-stop at the level: it fills intrabar (at the daily open on a gap) and keeps the signal stop.
- A pending signal is cancelled on a close below the signal stop or a reversal of the live crossover EMAs (10/20 for crypto). A new crossover replaces it.
- The `signal` mode (today's entry) is always included, and the report compares every mode with it, matched by crossover bar: losers and false starts blocked, winners and winner R kept, lift over random.
- `"audit": {"pivot_k": 3, "lookback": 120}` adds the loser audit (`research/audit.py`) to the report.
- `"save_trades_for_exits": ["baseline"]` limits `trades.csv.gz` size.

### Entry filter block

```
"entry_filter": {"label": "false_start", "models": ["logistic", "gbm"],
                 "skip_q": [0.1, 0.2, 0.3], "train_months": 18, "refit_months": 3}
```

- Each entry signal gets a probability from a model trained only on baseline trades that closed before its 3-month block. `tests/test_walkforward.py` checks that no label leaks.
- The riskiest `skip_q` share is skipped; the threshold is a quantile of training probabilities.
- Variants are named `<model>_skip<q>+<exit>`.
- Every arm, the baseline included, trades only from the first walk-forward block, so all arms cover the same period.
- Model inputs and labels: `research/filters/dataset.py`. Breadth and prior-trade context: `research/context.py`.
- Filter quality (AUC, false starts removed against winner R removed, logistic weights) is written into the run's `report.md`.
- Daily crypto makes few trades per pair, so the filter specs use a wider USDT list over 6 years.

## Rules the engine follows

- Same rules as the live daily wallet (`src/main.py` with `BaseStrategy.check_risk_management`): open at the signal bar close with the `sl_atr` x ATR stop and that ATR frozen, step from the next bar, and no new entry on the bar that closed a trade. `tests/test_research_parity.py` replays the live strategy day by day and checks entries, exits and R bar for bar (daily trend, weekly trend, TP1 wallet, trail arm), and checks the entries and trade count against `shared/path_sim.py`.
- Inside a bar: TP1 (if on), then the stop on the low (filled at the stop level), then ladder levels on the high (filled at the level price), then the early exit on the close, then the trail from the close, then the break-even raise.
- R is per trade and ignores wallet cash. The live wallet shares $10k across pairs and skips entries when cash is fully deployed, so it takes a subset of the replay's trades.
- A fee of 0.1% per side is charged on every fill. Reports show R net of fees. Baseline gross R is also shown.
- Trades opened in the last 12 months are out-of-sample. A variant counts as better only if it beats the baseline in both periods.
- Today's universe is replayed over past bars, so results carry survivorship bias.
