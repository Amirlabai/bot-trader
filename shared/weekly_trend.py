"""Weekly trend filter aligned onto daily bars, without the open week."""

from __future__ import annotations

import pandas as pd


def _completed_weekly_close(close: pd.Series) -> pd.Series:
    """Sunday-labeled weekly closes. A week whose Sunday is still ahead is dropped."""
    weekly_close = close.resample('W-SUN').last().dropna()
    last_day = pd.Timestamp(close.index[-1])
    if last_day.tzinfo is not None:
        last_day = last_day.tz_localize(None)
    week_ends = weekly_close.index
    if getattr(week_ends, 'tz', None) is not None:
        week_ends = week_ends.tz_localize(None)
        weekly_close = weekly_close.copy()
        weekly_close.index = week_ends
    complete = week_ends <= last_day.normalize()
    return weekly_close.loc[complete]


def _align_to_daily(close: pd.Series, weekly: pd.Series, *, fill_false: bool) -> pd.Series:
    daily_index = close.index
    naive_index = daily_index.tz_localize(None) if getattr(daily_index, 'tz', None) is not None else daily_index
    union = naive_index.union(weekly.index)
    aligned = weekly.reindex(union).sort_index().ffill()
    out = aligned.reindex(naive_index)
    out.index = daily_index
    if fill_false:
        return out.fillna(0.0).astype(bool)
    return out


def weekly_ema_on_daily(close: pd.Series, span: int, ema_fn) -> pd.Series:
    """Weekly EMA of completed weeks, forward-filled onto each daily bar."""
    weekly_close = _completed_weekly_close(close)
    weekly_ema = ema_fn(weekly_close, span)
    return _align_to_daily(close, weekly_ema, fill_false=False)


def weekly_trend_flags(close: pd.Series, span: int, ema_fn) -> tuple[pd.Series, pd.Series]:
    """Bull and bear flags on each daily bar from the last completed Sunday week.

    Bull: that week's close is above the weekly EMA. Bear: it is below.
    A week still in progress is not used.
    """
    weekly_close = _completed_weekly_close(close)
    weekly_ema = ema_fn(weekly_close, span)
    bull = (weekly_close > weekly_ema).astype(float).where(weekly_ema.notna())
    bear = (weekly_close < weekly_ema).astype(float).where(weekly_ema.notna())
    return (
        _align_to_daily(close, bull, fill_false=True),
        _align_to_daily(close, bear, fill_false=True),
    )


def weekly_trend_on_daily(close: pd.Series, span: int, ema_fn) -> pd.Series:
    """True when the last completed weekly close is above the weekly EMA."""
    bull, _bear = weekly_trend_flags(close, span, ema_fn)
    return bull
