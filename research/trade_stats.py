"""Trade statistics on a series of R values. Shared by the learning report and research."""

from __future__ import annotations

import pandas as pd


def r_stats(r) -> dict:
    r = pd.Series(r, dtype=float).dropna()
    n = int(len(r))
    if n == 0:
        return {
            'n': 0, 'win_rate': None, 'mean_r': None, 'total_r': 0.0,
            'profit_factor': None, 'se_r': None,
        }
    gains = float(r[r > 0].sum())
    losses = float(-r[r < 0].sum())
    return {
        'n': n,
        'win_rate': float((r > 0).mean()),
        'mean_r': float(r.mean()),
        'total_r': float(r.sum()),
        'profit_factor': (gains / losses) if losses > 0 else None,
        # Standard error of the mean R. R is fat-tailed, so this is wide on purpose.
        'se_r': float(r.std(ddof=1) / n ** 0.5) if n > 1 else None,
    }


def max_drawdown(r_in_close_order) -> float:
    """Largest peak-to-trough fall of cumulative R (positive number, 0 when none)."""
    peak = 0.0
    equity = 0.0
    worst = 0.0
    for value in r_in_close_order:
        equity += float(value)
        peak = max(peak, equity)
        worst = max(worst, peak - equity)
    return worst


def longest_losing_streak(r_in_close_order) -> int:
    best = run = 0
    for value in r_in_close_order:
        run = run + 1 if float(value) < 0 else 0
        best = max(best, run)
    return best
