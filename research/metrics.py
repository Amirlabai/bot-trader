"""Per-variant metrics, overall and split into in-sample / out-of-sample by entry date."""

from __future__ import annotations

import pandas as pd

from research.trade_stats import longest_losing_streak, max_drawdown, r_stats


def split_date(last_bar: pd.Timestamp, oos_months: int) -> pd.Timestamp:
    return pd.Timestamp(last_bar) - pd.DateOffset(months=int(oos_months))


def _block(df: pd.DataFrame, col: str) -> dict:
    if df.empty:
        return {'n': 0, 'win_rate': None, 'mean_r': None, 'total_r': 0.0, 'profit_factor': None,
                'max_dd_r': 0.0, 'losing_streak': 0, 'big_share': None, 'capture': None,
                'pairs_positive': 0, 'pairs': 0}
    ordered = df.sort_values('closed_at')
    stats = r_stats(ordered[col])
    winners = ordered.loc[ordered[col] > 0]
    mfe = winners['mfe_r'].where(winners['mfe_r'] > 0)
    by_pair = ordered.groupby('symbol')[col].sum()
    stats.update({
        'max_dd_r': max_drawdown(ordered[col]),
        'losing_streak': longest_losing_streak(ordered[col]),
        'big_share': float((ordered[col] >= 3.0).mean()),
        'capture': float((winners['r_multiple'] / mfe).mean()) if len(winners) else None,
        'pairs_positive': int((by_pair > 0).sum()),
        'pairs': int(len(by_pair)),
    })
    return stats


def variant_metrics(trades: pd.DataFrame, cutoff: pd.Timestamp, col: str = 'r_net') -> dict:
    """Flat dict: all_*, is_*, oos_* blocks, plus gross total R for reference."""
    entry = pd.to_datetime(trades['entry_date'])
    out = {}
    for prefix, sub in (
        ('all', trades),
        ('is', trades.loc[entry < cutoff]),
        ('oos', trades.loc[entry >= cutoff]),
    ):
        for key, value in _block(sub, col).items():
            out[f'{prefix}_{key}'] = value
    out['all_total_r_gross'] = float(trades['r_multiple'].sum()) if len(trades) else 0.0
    out['ladder_fill_share'] = float((trades['ladder_fills'] > 0).mean()) if len(trades) else 0.0
    out['ambiguous_bars'] = int(trades['ambiguous_bars'].sum()) if len(trades) else 0
    return out
