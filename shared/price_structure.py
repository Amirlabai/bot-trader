"""Price structure without look-ahead: swing-high pivots, resistance above price, band high (shared by live and research).

A swing high at bar j (strength k) is a bar whose high is the highest of
high[j-k .. j+k]. It is only known once bar j+k has closed, so every lookup at
bar t uses pivots with j + k <= t.
"""

from __future__ import annotations

import math

import numpy as np


def pivot_highs(high: np.ndarray, k: int) -> np.ndarray:
    """Indices j that are swing highs of strength k (ties count as pivots)."""
    n = len(high)
    out = []
    for j in range(k, n - k):
        window = high[j - k:j + k + 1]
        if high[j] >= window.max():
            out.append(j)
    return np.array(out, dtype=int)


class Structure:
    """Per-pair lookups at any bar t, using only information known at t's close."""

    def __init__(self, high, low, close, atr, k: int = 3, lookback: int = 120):
        self.high = np.asarray(high, dtype=float)
        self.low = np.asarray(low, dtype=float)
        self.close = np.asarray(close, dtype=float)
        self.atr = np.asarray(atr, dtype=float)
        self.k = int(k)
        self.lookback = int(lookback)
        self.pivots = pivot_highs(self.high, self.k)
        self._confirmed_at = self.pivots + self.k

    def known_pivots(self, t: int) -> np.ndarray:
        """Pivot indices confirmed by bar t and inside the lookback."""
        hi = np.searchsorted(self._confirmed_at, t, side='right')
        piv = self.pivots[:hi]
        return piv[piv >= t - self.lookback]

    def last_swing_high(self, t: int) -> float:
        piv = self.known_pivots(t)
        return float(self.high[piv[-1]]) if len(piv) else math.nan

    def resistance(self, t: int) -> float:
        """Lowest known pivot high above close[t]; NaN when price is above all of them."""
        piv = self.known_pivots(t)
        if not len(piv):
            return math.nan
        levels = self.high[piv]
        above = levels[levels > self.close[t]]
        return float(above.min()) if len(above) else math.nan

    def touches(self, t: int, level: float, tol_atr: float = 0.5) -> int:
        if math.isnan(level) or math.isnan(self.atr[t]):
            return 0
        piv = self.known_pivots(t)
        return int(np.sum(np.abs(self.high[piv] - level) <= tol_atr * self.atr[t]))

    def band_high(self, t: int, bars: int | None = None) -> float:
        """Highest high of the previous `bars` bars, excluding bar t."""
        bars = int(bars or self.lookback)
        lo = max(0, t - bars)
        if lo >= t:
            return math.nan
        return float(self.high[lo:t].max())


def last_swing_high_at(high, t: int, k: int = 3, lookback: int = 120) -> float:
    """Structure(high, ..., k, lookback).last_swing_high(t) without building every pivot.

    Latest j with high[j] >= max(high[j-k .. j+k]), confirmed by t (j + k <= t)
    and inside the lookback (j >= t - lookback). NaN when there is none.
    """
    high = np.asarray(high, dtype=float)
    k = int(k)
    lo = max(k, t - int(lookback))
    for j in range(min(t - k, len(high) - k - 1), lo - 1, -1):
        if high[j] >= high[j - k:j + k + 1].max():
            return float(high[j])
    return math.nan
