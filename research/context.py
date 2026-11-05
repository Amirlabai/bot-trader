"""Context known at the signal bar that a single pair's bars do not carry.

- breadth_above_trend: share of research pairs above their EMA150 at that bar
- prev_r / bars_since_exit: last closed baseline trade on the same pair before the signal

Live can compute the same values (it fetches every pair each session and keeps
its own trade history). In research the prior-trade values come from the
baseline replay, so they do not change when a filter skips entries.
"""

from __future__ import annotations

import bisect

import pandas as pd

from research.settings import BAR_HOURS


def breadth(signals_by_pair: dict) -> pd.Series:
    """Share of pairs above trend per timestamp (pairs with a bar at that time)."""
    frames = [sig['above_trend'].astype(float).rename(sym) for sym, sig in signals_by_pair.items()]
    if not frames:
        return pd.Series(dtype=float)
    wide = pd.concat(frames, axis=1)
    return wide.mean(axis=1, skipna=True)


class PriorTrades:
    """Lookup of the last closed baseline trade on a pair before a timestamp."""

    def __init__(self, trades: pd.DataFrame, r_col: str = 'r_net'):
        self._by_pair: dict[str, tuple[list, list]] = {}
        if trades is None or trades.empty:
            return
        ordered = trades.assign(_closed=pd.to_datetime(trades['closed_at'])).sort_values('_closed')
        for symbol, sub in ordered.groupby('symbol'):
            self._by_pair[symbol] = (list(sub['_closed']), list(sub[r_col]))

    def at(self, symbol: str, ts) -> tuple[float | None, float | None]:
        closed, rs = self._by_pair.get(symbol, ([], []))
        ts = pd.Timestamp(ts)
        i = bisect.bisect_left(closed, ts) - 1  # strictly before ts
        if i < 0:
            return None, None
        hours = (ts - closed[i]).total_seconds() / 3600.0
        return float(rs[i]), hours / BAR_HOURS
