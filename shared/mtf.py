"""Higher-timeframe indicators derived from daily bars, aligned back onto the daily index.

Weekly bars end on Sunday, monthly bars on the calendar month end. A higher-timeframe bar is
only used once its last day is present in the data, so nothing here looks ahead. Live strategy
and the offline sim both call these functions, which keeps them identical.
"""

from __future__ import annotations

import pandas as pd

TFS = ('D', 'W', 'M')
_RULE = {'W': 'W-SUN', 'M': 'ME'}


def check_tf(tf: str) -> str:
    tf = str(tf or 'D').upper()
    if tf not in TFS:
        raise ValueError(f'timeframe must be one of {TFS}, got {tf!r}')
    return tf


def _naive(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    return index.tz_localize(None) if getattr(index, 'tz', None) is not None else index


def completed_ohlc(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    """OHLC of completed tf bars, labeled by period end (tz-naive). D returns the frame as is."""
    tf = check_tf(tf)
    cols = [c for c in ('open', 'high', 'low', 'close') if c in df.columns]
    base = df[cols].copy()
    base.index = _naive(base.index)
    if tf == 'D':
        return base
    agg = {c: {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}[c] for c in cols}
    out = base.resample(_RULE[tf]).agg(agg).dropna(subset=['close'])
    last_day = base.index[-1].normalize()
    return out.loc[out.index <= last_day]


def align_to_daily(daily_index: pd.DatetimeIndex, series: pd.Series, *, fill=None,
                   as_event: bool = False) -> pd.Series:
    """Put a tf series onto daily bars. State series forward-fill; events land on the label day only."""
    naive = _naive(daily_index)
    if as_event:
        out = series.reindex(naive)
        out = out.fillna(False).astype(bool)
    else:
        union = naive.union(series.index)
        out = series.reindex(union).sort_index().ffill().reindex(naive)
        if fill is not None:
            out = out.fillna(fill)
            if isinstance(fill, bool):
                out = out.astype(bool)
    out.index = daily_index
    return out


def ema_on_tf(df: pd.DataFrame, span: int, tf: str, ema_fn, bars: pd.DataFrame | None = None) -> pd.Series:
    """EMA of completed tf closes, forward-filled onto each daily bar.

    `bars` is an optional precomputed completed_ohlc(df, tf) to skip the resample.
    """
    bars = completed_ohlc(df, tf) if bars is None else bars
    return align_to_daily(df.index, ema_fn(bars['close'], int(span)))


def trend_flags(df: pd.DataFrame, span: int, tf: str, ema_fn,
                bars: pd.DataFrame | None = None) -> tuple[pd.Series, pd.Series]:
    """(bull, bear): last completed tf close above / below its EMA. False until the EMA exists."""
    bars = completed_ohlc(df, tf) if bars is None else bars
    ema = ema_fn(bars['close'], int(span))
    ok = ema.notna()
    bull = (bars['close'] > ema) & ok
    bear = (bars['close'] < ema) & ok
    return (
        align_to_daily(df.index, bull.astype(float).where(ok), fill=False),
        align_to_daily(df.index, bear.astype(float).where(ok), fill=False),
    )


def cross_events(df: pd.DataFrame, fast: int, slow: int, tf: str, ema_fn,
                 bars: pd.DataFrame | None = None) -> tuple[pd.Series, pd.Series]:
    """(up, down): fast EMA crossed above / below slow EMA on a completed tf bar.

    The event is True on the daily bar that completes that tf bar.
    """
    bars = completed_ohlc(df, tf) if bars is None else bars
    f = ema_fn(bars['close'], int(fast))
    s = ema_fn(bars['close'], int(slow))
    pf, ps = f.shift(1), s.shift(1)
    up = (pf <= ps) & (f > s) & f.notna() & s.notna() & pf.notna() & ps.notna()
    down = (pf >= ps) & (f < s) & f.notna() & s.notna() & pf.notna() & ps.notna()
    return (
        align_to_daily(df.index, up, as_event=True),
        align_to_daily(df.index, down, as_event=True),
    )


def atr_on_tf(df: pd.DataFrame, period: int, tf: str, bars: pd.DataFrame | None = None) -> pd.Series:
    """Simple-mean ATR of completed tf bars, forward-filled onto each daily bar."""
    bars = completed_ohlc(df, tf) if bars is None else bars
    prev = bars['close'].shift(1)
    tr = pd.concat(
        [bars['high'] - bars['low'], (bars['high'] - prev).abs(), (bars['low'] - prev).abs()],
        axis=1,
    ).max(axis=1)
    tr.iloc[0] = bars['high'].iloc[0] - bars['low'].iloc[0]
    return align_to_daily(df.index, tr.rolling(int(period)).mean())


def exit_flags(df: pd.DataFrame, mode: str, tf: str, fast: int, slow: int, trend: int, ema_fn,
               bars: pd.DataFrame | None = None) -> pd.Series:
    """Signal-exit flag per daily bar. 'cross': death cross on a completed tf bar.
    'trend': last completed tf close below its trend EMA. Anything else: never."""
    mode = str(mode or 'stop_only')
    if mode == 'cross':
        return cross_events(df, fast, slow, tf, ema_fn, bars)[1]
    if mode == 'trend':
        return trend_flags(df, trend, tf, ema_fn, bars)[1]
    return pd.Series(False, index=df.index)
