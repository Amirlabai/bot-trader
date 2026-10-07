"""Resolve ambiguous parent OHLC bars using a finer timeframe.

Ambiguous = S0 < low <= S1 where S0 is pre-trail stop and S1 is trail from parent close.
Walk finer bars in [bar_start, bar_end): wick vs stop, then trail from finer close.
Trail distance stays parent `trail_atr * atr` (path order only).
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd


def as_naive_ts(ts) -> pd.Timestamp:
    t = pd.Timestamp(ts)
    if t.tzinfo is not None:
        t = t.tz_convert('UTC').tz_localize(None)
    return t


def trail_from_close(stop: float, close_px: float, trail_dist: float) -> float:
    if trail_dist <= 0 or not (close_px == close_px):
        return float(stop)
    proposed = close_px - trail_dist
    return float(proposed) if proposed > stop else float(stop)


def parent_bar_end(bar_start: pd.Timestamp, interval: str) -> pd.Timestamp:
    """Exclusive end of parent bar window."""
    t0 = as_naive_ts(bar_start)
    if interval == '4h':
        return t0 + timedelta(hours=4)
    # daily (and default): calendar day window
    d = t0.normalize()
    return d + timedelta(days=1)


def finer_arrays(df: pd.DataFrame | None) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """Return (times_ns, low, close) or None."""
    if df is None or df.empty:
        return None
    times = np.array([as_naive_ts(ts).to_datetime64() for ts in df.index], dtype='datetime64[ns]')
    low = df['low'].astype(float).to_numpy(dtype=float)
    close = df['close'].astype(float).to_numpy(dtype=float)
    order = np.argsort(times)
    return times[order], low[order], close[order]


def resolve_ambiguous(
    bar_start,
    bar_end,
    s0: float,
    trail_dist: float,
    finer_times: np.ndarray,
    finer_low: np.ndarray,
    finer_close: np.ndarray,
) -> tuple[bool, float]:
    """Walk finer bars in [bar_start, bar_end).

    Returns (hit, exit_price_or_final_stop).
    """
    t0 = np.datetime64(as_naive_ts(bar_start).to_datetime64())
    t1 = np.datetime64(as_naive_ts(bar_end).to_datetime64())
    left = int(np.searchsorted(finer_times, t0, side='left'))
    right = int(np.searchsorted(finer_times, t1, side='left'))
    if left >= right:
        return False, float(s0)

    stop = float(s0)
    for j in range(left, right):
        if finer_low[j] <= stop:
            return True, stop
        stop = trail_from_close(stop, float(finer_close[j]), trail_dist)
    return False, stop


def drill_interval_for_parent(parent_interval: str) -> str | None:
    """Map parent bar interval to finer drill interval."""
    if parent_interval == '4h':
        return '1h'
    if parent_interval in ('1d', '1D', 'd', 'daily'):
        return '4h'
    return None
