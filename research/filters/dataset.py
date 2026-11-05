"""Entry table: one row per entry signal bar, with features, context, and baseline outcome."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from research.context import PriorTrades, breadth

# Model inputs. Calendar fields (hour, weekday) are left out on purpose: in the
# first replay they looked like noise, and they invite overfitting.
FEATURES = [
    'atr_pct', 'trend_ext_atr', 'trend_slope_pct', 'cross_gap_atr', 'ret_30_bars',
    'volume_ratio', 'btc_above_trend', 'btc_trend_ext_atr', 'btc_ret_30',
    'cross_count_60', 'dist_high_50_atr', 'atr_change_30', 'close_pos', 'body_atr',
    'ret_6_bars', 'ext_ema300_atr',
    'breadth_above_trend', 'prev_r', 'bars_since_exit',
]

LABELS = {
    # Closed at the initial stop and never reached +1R: the signal never worked.
    'false_start': lambda t: (t['exit_kind'] == 'stop_loss') & (t['mfe_r'] < 1.0),
    # Any trade that lost after fees.
    'loser': lambda t: t['r_net'] <= 0,
}


def entry_table(signals_by_pair: dict, baseline_trades: pd.DataFrame, label: str = 'false_start') -> pd.DataFrame:
    """All entry-signal bars (taken or not by the baseline), with the baseline label when taken."""
    share = breadth(signals_by_pair)
    prior = PriorTrades(baseline_trades)
    outcome = {}
    if baseline_trades is not None and not baseline_trades.empty:
        labelled = baseline_trades.assign(label_y=LABELS[label](baseline_trades).astype(int))
        for row in labelled.itertuples(index=False):
            outcome[(row.symbol, row.entry_date)] = (row.label_y, row.r_net, row.closed_at, row.exit_kind)

    from research.settings import bar_ts
    rows = []
    for symbol, sig in signals_by_pair.items():
        entries = sig.loc[sig['entry'] & sig['stop'].notna()]
        for ts, rec in entries.iterrows():
            feats = json.loads(rec['features']) if rec['features'] else {}
            prev_r, since = prior.at(symbol, ts)
            row = {k: feats.get(k) for k in FEATURES}
            row['btc_above_trend'] = (
                float(feats['btc_above_trend']) if 'btc_above_trend' in feats else np.nan
            )
            row['breadth_above_trend'] = float(share.get(ts, np.nan))
            row['prev_r'] = prev_r
            row['bars_since_exit'] = since
            row['symbol'] = symbol
            row['ts'] = pd.Timestamp(ts)
            hit = outcome.get((symbol, bar_ts(ts)))
            row['taken'] = hit is not None
            row['y'] = hit[0] if hit else np.nan
            row['r_net'] = hit[1] if hit else np.nan
            row['closed_at'] = pd.Timestamp(hit[2]) if hit else pd.NaT
            row['exit_kind'] = hit[3] if hit else None
            rows.append(row)
    table = pd.DataFrame(rows)
    if not table.empty:
        for col in FEATURES:
            table[col] = pd.to_numeric(table[col], errors='coerce')
        table = table.sort_values('ts').reset_index(drop=True)
    return table
