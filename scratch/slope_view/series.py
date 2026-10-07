"""Candles, trend EMA, midpoint averages, and their slopes for the slope viewer.

Visual only. No entries, exits, or position state.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from shared.intrabar_resolve import as_naive_ts


def _ema(close: np.ndarray, period: int) -> np.ndarray:
    return pd.Series(close).ewm(span=int(period), adjust=False).mean().to_numpy(dtype=float)


def midpoint_slopes(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    span: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Raw midpoints and slope (mid now - mid n bars ago) / n."""
    n = int(span)
    if n < 1:
        raise ValueError(f'slope_span ({n}) must be >= 1')
    avg_oc = (open_ + close) / 2.0
    avg_hl = (high + low) / 2.0
    slope_oc = np.full(len(close), np.nan, dtype=float)
    slope_hl = np.full(len(close), np.nan, dtype=float)
    if len(close) > n:
        slope_oc[n:] = (avg_oc[n:] - avg_oc[:-n]) / n
        slope_hl[n:] = (avg_hl[n:] - avg_hl[:-n]) / n
    return avg_oc, avg_hl, slope_oc, slope_hl


class SlopeReset:
    """After an exit, both slopes must go negative, then both positive, before the next entry."""

    def __init__(self) -> None:
        self.need = False
        self.saw_oc = False
        self.saw_hl = False

    def on_exit(self) -> None:
        self.need = True
        self.saw_oc = False
        self.saw_hl = False

    @staticmethod
    def _neg(v: float) -> bool:
        return v == v and v < 0

    @staticmethod
    def _pos(v: float) -> bool:
        return v == v and v > 0

    def observe(self, slope_oc: float, slope_hl: float) -> None:
        if not self.need:
            return
        if self._neg(slope_oc):
            self.saw_oc = True
        if self._neg(slope_hl):
            self.saw_hl = True
        if self.saw_oc and self.saw_hl and self._pos(slope_oc) and self._pos(slope_hl):
            self.need = False

    def allows_entry(self) -> bool:
        return not self.need


def close_slope(close: np.ndarray, span: int) -> np.ndarray:
    """Slope of close: (close now - close n bars ago) / n."""
    n = int(span)
    if n < 1:
        raise ValueError(f'slope_span ({n}) must be >= 1')
    slope = np.full(len(close), np.nan, dtype=float)
    if len(close) > n:
        slope[n:] = (close[n:] - close[:-n]) / n
    return slope


def _steep(slope: np.ndarray, min_slope: float) -> np.ndarray:
    """Floor of 0 keeps the original positive test. A positive floor is slope >= that amount."""
    if min_slope > 0:
        return slope >= min_slope
    return slope > 0


def close_slope_entry(
    close: np.ndarray,
    ema_trend: np.ndarray,
    span: int,
    min_slope: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Close slope above the floor and close above the trend EMA. No midpoint averages.

    The post-exit reset is separate: the slope must still go negative, not merely under the floor.
    """
    slope = close_slope(close, span)
    entry = _steep(slope, min_slope) & (close > ema_trend)
    entry = np.nan_to_num(entry.astype(float), nan=0.0).astype(bool)
    return entry, slope


def mid_slope_entry(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    ema_trend: np.ndarray,
    span: int,
    min_slope: float = 0.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """HL midpoint crosses above OC midpoint, both slopes meet the floor, close above trend EMA.

    The post-exit reset is separate: both slopes must still go negative, not merely under the floor.
    """
    avg_oc, avg_hl, slope_oc, slope_hl = midpoint_slopes(open_, high, low, close, span)
    prev_hl = np.roll(avg_hl, 1)
    prev_oc = np.roll(avg_oc, 1)
    prev_hl[0] = np.nan
    prev_oc[0] = np.nan
    cross = (prev_hl <= prev_oc) & (avg_hl > avg_oc)
    entry = (
        cross
        & _steep(slope_oc, min_slope)
        & _steep(slope_hl, min_slope)
        & (close > ema_trend)
    )
    entry = np.nan_to_num(entry.astype(float), nan=0.0).astype(bool)
    return entry, avg_oc, avg_hl, slope_oc, slope_hl


def _bar_dates(df: pd.DataFrame) -> np.ndarray:
    return np.array([as_naive_ts(ts).date() for ts in df.index])


def _round_series(arr: np.ndarray, n: int) -> list[float | None]:
    out: list[float | None] = []
    for i in range(n):
        v = arr[i]
        if v != v:
            out.append(None)
        else:
            out.append(round(float(v), 4))
    return out


def build_view(
    df: pd.DataFrame,
    *,
    trend_window: int = 150,
    slope_span: int = 1,
    start: date | None = None,
    end: date | None = None,
    interval: str = '4h',
) -> dict[str, Any]:
    """Return bars, trend EMA, raw midpoints, and slope over n bars."""
    if df is None or df.empty:
        raise ValueError('No OHLCV data')

    trend = int(trend_window)
    if trend < 2:
        raise ValueError(f'trend_window ({trend}) must be >= 2')
    span = int(slope_span)
    if span < 1:
        raise ValueError(f'slope_span ({span}) must be >= 1')

    close = df['close'].astype(float).to_numpy(dtype=float)
    high = df['high'].astype(float).to_numpy(dtype=float)
    low = df['low'].astype(float).to_numpy(dtype=float)
    open_ = df['open'].astype(float).to_numpy(dtype=float) if 'open' in df.columns else close.copy()

    avg_oc, avg_hl, slope_oc, slope_hl = midpoint_slopes(open_, high, low, close, span)
    ema_trend = _ema(close, trend)

    dates = _bar_dates(df)
    if start is None:
        start = dates[0]
    if end is None:
        end = dates[-1]
    in_window = (dates >= start) & (dates <= end)
    if not in_window.any():
        raise ValueError(f'No bars in window {start} .. {end}')
    start_idx = int(np.argmax(in_window))
    end_idx = int(len(df) - 1 - np.argmax(in_window[::-1]))

    bars = []
    for i in range(end_idx + 1):
        ts = as_naive_ts(df.index[i])
        bars.append({
            'i': i,
            'time': int(ts.timestamp()),
            'time_iso': ts.isoformat(),
            'open': round(float(open_[i]), 4),
            'high': round(float(high[i]), 4),
            'low': round(float(low[i]), 4),
            'close': round(float(close[i]), 4),
        })

    return {
        'symbol': 'BTC/USDT',
        'interval': interval,
        'start_idx': start_idx,
        'end_idx': end_idx,
        'trend_window': trend,
        'slope_span': span,
        'window': {'start': start.isoformat(), 'end': end.isoformat()},
        'bars': bars,
        'series': {
            'ema_trend': _round_series(ema_trend, end_idx + 1),
            'avg_oc': _round_series(avg_oc, end_idx + 1),
            'avg_hl': _round_series(avg_hl, end_idx + 1),
            'slope_oc': _round_series(slope_oc, end_idx + 1),
            'slope_hl': _round_series(slope_hl, end_idx + 1),
        },
    }
