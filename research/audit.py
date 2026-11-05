"""Loser audit around price structure at the signal bar.

For each baseline trade: distance to resistance, open air, band breakout, touches,
and (descriptive only, it looks ahead) whether a higher close came within N bars.
Then a "would block" table: losers and false starts blocked against winners and
winner R kept, for simple structure rules.

Enabled from a spec with  "audit": {"pivot_k": 3, "lookback": 120}
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from research.structure import Structure
from research.settings import bar_ts

HH_BARS = (1, 2, 3, 6, 12)


def structure_table(signals_by_pair: dict, trades: pd.DataFrame, pivot_k=3, lookback=120) -> pd.DataFrame:
    rows = []
    for symbol, sig in signals_by_pair.items():
        sub = trades.loc[trades['symbol'] == symbol]
        if sub.empty:
            continue
        st = Structure(sig['high'], sig['low'], sig['close'], sig['atr'], k=pivot_k, lookback=lookback)
        pos_of = {bar_ts(ts): i for i, ts in enumerate(sig.index)}
        close, high, atr = st.close, st.high, st.atr
        for t in sub.itertuples(index=False):
            s = pos_of.get(t.entry_date)
            if s is None or math.isnan(atr[s]) or atr[s] <= 0:
                continue
            res = st.resistance(s)
            band20 = st.band_high(s, 20)
            band55 = st.band_high(s, 55)
            row = {
                'symbol': symbol, 'r_net': t.r_net, 'exit_kind': t.exit_kind, 'mfe_r': t.mfe_r,
                'open_air': math.isnan(res),
                'res_dist_atr': (res - close[s]) / atr[s] if not math.isnan(res) else np.nan,
                'touches': st.touches(s, res),
                'above_band20': bool(close[s] > band20) if not math.isnan(band20) else False,
                'above_band55': bool(close[s] > band55) if not math.isnan(band55) else False,
                'band55_dist_atr': (band55 - close[s]) / atr[s] if not math.isnan(band55) else np.nan,
            }
            later = close[s + 1:s + 1 + max(HH_BARS)]
            for n in HH_BARS:
                row[f'hh_within_{n}'] = bool(np.any(later[:n] > high[s]))
            rows.append(row)
    df = pd.DataFrame(rows)
    if not df.empty:
        df['winner'] = df['r_net'] > 0
        df['big'] = df['r_net'] >= 3.0
        df['false_start'] = (df['exit_kind'] == 'stop_loss') & (df['mfe_r'] < 1.0)
    return df


def _p(x):
    return '-' if x is None or pd.isnull(x) else f'{x * 100:.0f}%'


def _rule_row(df: pd.DataFrame, name: str, block: pd.Series, mean_r: float) -> dict:
    kept = ~block
    win, big, fs = df['winner'], df['big'], df['false_start']

    def share(mask, of):
        return float((mask & of).sum() / of.sum()) if of.sum() else None

    r_kept = float(df.loc[kept, 'r_net'].sum())
    return {
        'rule': name,
        'blocked': int(block.sum()),
        'losers_blocked': share(block, ~win),
        'false_starts_blocked': share(block, fs),
        'winners_kept': share(kept, win),
        'winner_r_kept': float(df.loc[kept & win, 'r_net'].sum() / df.loc[win, 'r_net'].sum()),
        'big_kept': share(kept, big),
        'r_kept': r_kept,
        'lift': r_kept - int(kept.sum()) * mean_r,
    }


def build_audit(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return ['## Loser audit', '', 'No trades to audit.', '']
    mean_r = float(df['r_net'].mean())
    n = len(df)
    md = ['## Loser audit (price structure at the signal bar)', '',
          f"{n} baseline trades: {int(df['winner'].sum())} winners, {int((~df['winner']).sum())} losers, "
          f"{int(df['false_start'].sum())} false starts, {int(df['big'].sum())} of 3R or more. "
          f"Mean {mean_r:+.2f}R.", '']

    md += ['### Share of each group by structure', '',
           '| Condition | All | Winners | Losers | False starts | 3R+ | Mean R |', '|---|---|---|---|---|---|---|']
    res = df['res_dist_atr']
    conditions = {
        'Open air (no swing high above)': df['open_air'],
        'Resistance within 1 ATR': res < 1,
        'Resistance 1 to 3 ATR': (res >= 1) & (res < 3),
        'Resistance 3+ ATR': res >= 3,
        'Resistance touched 2+ times': df['touches'] >= 2,
        'Close above 20-bar high': df['above_band20'],
        'Close above 55-bar high': df['above_band55'],
    }
    for n_bars in HH_BARS:
        conditions[f'Higher close within {n_bars} bars (look-ahead)'] = df[f'hh_within_{n_bars}']
    for name, mask in conditions.items():
        mask = mask.fillna(False).astype(bool)
        md.append(
            f"| {name} | {_p(mask.mean())} | {_p(mask[df['winner']].mean())} | "
            f"{_p(mask[~df['winner']].mean())} | {_p(mask[df['false_start']].mean())} | "
            f"{_p(mask[df['big']].mean())} | {df.loc[mask, 'r_net'].mean():+.2f}R |"
        )

    rules = {
        'Block unless open air': ~df['open_air'],
        'Block if resistance within 1 ATR': (res < 1).fillna(False),
        'Block if resistance within 2 ATR': (res < 2).fillna(False),
        'Block if resistance touched 2+ times': df['touches'] >= 2,
        'Block unless close above 20-bar high': ~df['above_band20'],
        'Block unless close above 55-bar high': ~df['above_band55'],
    }
    for n_bars in HH_BARS:
        rules[f'Block unless higher close within {n_bars} bars (look-ahead ceiling)'] = ~df[f'hh_within_{n_bars}']
    table = [_rule_row(df, name, mask.astype(bool), mean_r) for name, mask in rules.items()]
    md += ['', '### Would block', '',
           'Look-ahead rows use later bars, so they are not tradable as written. They show the most a '
           'wait-for-a-higher-high rule could achieve before paying the higher entry price, which the '
           'confirmation-entry experiment measures.', '',
           '| Rule | Blocked | Losers blocked | False starts blocked | Winners kept | Winner R kept | '
           '3R+ kept | R kept | Lift vs random |', '|---|---|---|---|---|---|---|---|---|']
    for r in table:
        md.append(
            f"| {r['rule']} | {r['blocked']} | {_p(r['losers_blocked'])} | {_p(r['false_starts_blocked'])} | "
            f"{_p(r['winners_kept'])} | {_p(r['winner_r_kept'])} | {_p(r['big_kept'])} | "
            f"{r['r_kept']:+.1f}R | {r['lift']:+.1f}R |"
        )
    md.append('')
    return md
