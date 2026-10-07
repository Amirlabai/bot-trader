"""Bar-by-bar long-only event emitter matching the BTC EMA grid path.

On 4h parents: ambiguous bars (S0 < low <= S1) are re-resolved on 1h bars.
On 1d parents: ambiguous bars are re-resolved on 4h bars.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from shared.intrabar_resolve import (
    as_naive_ts,
    finer_arrays,
    parent_bar_end,
    resolve_ambiguous,
    trail_from_close,
)
from shared.risk_sizing import size_long_from_equity


def _ema_series(close: np.ndarray, period: int) -> np.ndarray:
    return pd.Series(close).ewm(span=int(period), adjust=False).mean().to_numpy(dtype=float)


def _atr_series(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    """Match strategies.base_strategy / tune_btc_ema_grid: SMA of true range."""
    h = pd.Series(high)
    l = pd.Series(low)
    c = pd.Series(close)
    prev_c = c.shift(1)
    tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    tr.iloc[0] = h.iloc[0] - l.iloc[0]
    return tr.rolling(window=int(period)).mean().to_numpy(dtype=float)


def _bar_dates(df: pd.DataFrame) -> np.ndarray:
    return np.array([
        ts.date() if hasattr(ts, 'date') else pd.Timestamp(ts).date()
        for ts in df.index
    ])


def _ts_unix(ts) -> int:
    return int(as_naive_ts(ts).timestamp())


def run_sim(
    df: pd.DataFrame,
    params: dict[str, Any],
    *,
    start: date | None = None,
    end: date | None = None,
    start_cash: float = 10_000.0,
    risk_settings: dict | None = None,
    interval: str = '1d',
    df_finer: pd.DataFrame | None = None,
    df_1h: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Return bars, EMA/ATR series, and entry/exit events for playback."""
    if risk_settings is None:
        from config import RISK_SETTINGS
        risk_settings = RISK_SETTINGS

    if df is None or df.empty:
        raise ValueError('No OHLCV data')

    interval = (interval or '1d').strip()
    # Back-compat: df_1h alias for 4h parent drill
    if df_finer is None and df_1h is not None:
        df_finer = df_1h
    finer = finer_arrays(df_finer)
    use_drill = finer is not None
    if use_drill:
        finer_times, finer_low, finer_close = finer
    else:
        finer_times = finer_low = finer_close = None

    drill_tf = '1h' if interval == '4h' else '4h'
    parent_interval = '4h' if interval == '4h' else '1d'

    strategy = (params.get('strategy') or 'ema_cross').strip()
    trend = int(params['trend_window'])
    atr_period = int(params['atr_period'])
    sl_atr = float(params['sl_atr'])
    trail_atr = float(params['trail_atr'])
    fast = int(params.get('short_window') or 0)
    slow = int(params.get('long_window') or 0)
    slope_span = int(params.get('slope_span') or 1)
    min_slope = float(params.get('min_slope') or 0)

    close = df['close'].astype(float).to_numpy(dtype=float)
    high = df['high'].astype(float).to_numpy(dtype=float)
    low = df['low'].astype(float).to_numpy(dtype=float)
    open_ = df['open'].astype(float).to_numpy(dtype=float) if 'open' in df.columns else close.copy()
    volume = (
        df['volume'].astype(float).to_numpy(dtype=float)
        if 'volume' in df.columns
        else np.zeros(len(df), dtype=float)
    )

    ema_trend = _ema_series(close, trend)
    atr = _atr_series(high, low, close, atr_period)
    avg_oc = avg_hl = slope_oc = slope_hl = None
    ema_fast = ema_slow = None

    if strategy == 'mid_slope':
        from slope_view.series import mid_slope_entry
        entry_sig, avg_oc, avg_hl, slope_oc, slope_hl = mid_slope_entry(
            open_, high, low, close, ema_trend, slope_span, min_slope,
        )
    elif strategy == 'close_slope':
        from slope_view.series import close_slope_entry
        entry_sig, slope_close = close_slope_entry(close, ema_trend, slope_span, min_slope)
        slope_oc = slope_close
        slope_hl = slope_close
    else:
        if fast >= slow:
            raise ValueError(f'fast ({fast}) must be < slow ({slow})')
        ema_fast = _ema_series(close, fast)
        ema_slow = _ema_series(close, slow)
        prev_fast = np.roll(ema_fast, 1)
        prev_slow = np.roll(ema_slow, 1)
        prev_fast[0] = np.nan
        prev_slow[0] = np.nan
        cross = (prev_fast <= prev_slow) & (ema_fast > ema_slow)
        entry_sig = cross & (close > ema_trend)
        entry_sig = np.nan_to_num(entry_sig.astype(float), nan=0.0).astype(bool)

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

    entry_sig = entry_sig.copy()
    entry_sig[:start_idx] = False
    entry_sig[end_idx + 1 :] = False

    cash = float(start_cash)
    qty = 0.0
    entry_price = 0.0
    stop = 0.0
    events: list[dict[str, Any]] = []
    stop_check: list[float | None] = [None] * (end_idx + 1)
    stop_trail: list[float | None] = [None] * (end_idx + 1)
    ambiguous_flags: list[bool] = [False] * (end_idx + 1)
    drill_count = 0
    drill_exits = 0
    slope_reset = None
    if strategy in ('mid_slope', 'close_slope'):
        from slope_view.series import SlopeReset
        slope_reset = SlopeReset()

    def _arm_reset(i: int) -> None:
        if slope_reset is None:
            return
        slope_reset.on_exit()
        slope_reset.observe(float(slope_oc[i]), float(slope_hl[i]))

    for i in range(start_idx, end_idx + 1):
        a = atr[i]
        if qty > 0:
            s0 = float(stop)
            stop_check[i] = s0

            if low[i] <= s0:
                exit_px = s0
                pnl = (exit_px - entry_price) * qty
                cash += qty * exit_px
                events.append({
                    'i': i,
                    'type': 'exit',
                    'price': round(float(exit_px), 4),
                    'pnl': round(float(pnl), 2),
                    'qty': round(float(qty), 8),
                    'cash': round(float(cash), 2),
                    'stop': round(float(s0), 4),
                    'resolved': parent_interval,
                })
                qty = 0.0
                stop_trail[i] = None
                _arm_reset(i)
                continue

            trail_dist = float(trail_atr * a) if (a == a and a > 0) else 0.0
            s1 = trail_from_close(s0, float(close[i]), trail_dist)
            ambiguous = bool(trail_dist > 0 and s0 < float(low[i]) <= s1)
            ambiguous_flags[i] = ambiguous

            if ambiguous and use_drill:
                drill_count += 1
                t0 = as_naive_ts(df.index[i])
                t1 = parent_bar_end(t0, parent_interval)
                hit, exit_or_final = resolve_ambiguous(
                    t0, t1, s0, trail_dist, finer_times, finer_low, finer_close,
                )
                if hit:
                    drill_exits += 1
                    exit_px = float(exit_or_final)
                    pnl = (exit_px - entry_price) * qty
                    cash += qty * exit_px
                    events.append({
                        'i': i,
                        'type': 'exit',
                        'price': round(exit_px, 4),
                        'pnl': round(float(pnl), 2),
                        'qty': round(float(qty), 8),
                        'cash': round(float(cash), 2),
                        'stop': round(exit_px, 4),
                        'resolved': drill_tf,
                    })
                    qty = 0.0
                    stop_trail[i] = None
                    _arm_reset(i)
                    continue
                stop = float(exit_or_final)
                stop_trail[i] = float(stop)
                continue

            stop = float(s1)
            stop_trail[i] = float(stop)
            continue

        if slope_reset is not None:
            slope_reset.observe(float(slope_oc[i]), float(slope_hl[i]))
            if not slope_reset.allows_entry():
                continue
        if not entry_sig[i]:
            continue
        if not (a == a) or a <= 0:
            continue
        price = float(close[i])
        stop0 = price - sl_atr * float(a)
        q, _, _, _, _, ok = size_long_from_equity(cash, cash, price, stop0, risk_settings)
        if not ok or q <= 0:
            continue
        qty = float(q)
        entry_price = price
        stop = float(stop0)
        cash -= qty * price
        stop_check[i] = float(stop)
        stop_trail[i] = float(stop)
        events.append({
            'i': i,
            'type': 'entry',
            'price': round(price, 4),
            'qty': round(qty, 8),
            'cash': round(float(cash), 2),
            'stop': round(float(stop), 4),
            'pnl': None,
            'resolved': None,
        })

    bars = []
    for i in range(end_idx + 1):
        ts = df.index[i]
        bars.append({
            'i': i,
            'time': _ts_unix(ts),
            'time_iso': as_naive_ts(ts).isoformat(),
            'open': round(float(open_[i]), 4),
            'high': round(float(high[i]), 4),
            'low': round(float(low[i]), 4),
            'close': round(float(close[i]), 4),
            'volume': round(float(volume[i]), 4),
            'ambiguous': bool(ambiguous_flags[i]) if i < len(ambiguous_flags) else False,
        })

    def _series_from_list(vals: list[float | None]) -> list[float | None]:
        return [None if v is None else round(float(v), 4) for v in vals]

    def _series(arr: np.ndarray) -> list[float | None]:
        out: list[float | None] = []
        for i in range(end_idx + 1):
            v = arr[i]
            if v != v:
                out.append(None)
            else:
                out.append(round(float(v), 4))
        return out

    equity_end = cash
    if qty > 0:
        equity_end += qty * float(close[end_idx])

    return {
        'start_idx': start_idx,
        'end_idx': end_idx,
        'start_cash': float(start_cash),
        'interval': interval,
        'params': {
            'strategy': strategy,
            'short_window': fast,
            'long_window': slow,
            'trend_window': trend,
            'slope_span': slope_span if strategy in ('mid_slope', 'close_slope') else None,
            'min_slope': min_slope if strategy in ('mid_slope', 'close_slope') else None,
            'atr_period': atr_period,
            'sl_atr': sl_atr,
            'trail_atr': trail_atr,
        },
        'bars': bars,
        'series': {
            'ema_fast': _series(ema_fast) if ema_fast is not None else None,
            'ema_slow': _series(ema_slow) if ema_slow is not None else None,
            'ema_trend': _series(ema_trend),
            'avg_oc': _series(avg_oc) if avg_oc is not None else None,
            'avg_hl': _series(avg_hl) if avg_hl is not None else None,
            'slope_oc': _series(slope_oc) if slope_oc is not None else None,
            'slope_hl': _series(slope_hl) if strategy == 'mid_slope' and slope_hl is not None else None,
            'atr': _series(atr),
            'stop': _series_from_list(stop_check),
            'stop_trail': _series_from_list(stop_trail),
        },
        'events': events,
        'drill': {
            'enabled': use_drill,
            'finer_interval': drill_tf if use_drill else None,
            'ambiguous_bars': drill_count,
            'exits_finer': drill_exits,
            'exits_1h': drill_exits if drill_tf == '1h' else 0,
        },
        'summary': {
            'closed_trades': sum(1 for e in events if e['type'] == 'exit'),
            'open_position': qty > 0,
            'cash': round(float(cash), 2),
            'equity': round(float(equity_end), 2),
            'net_pnl': round(float(equity_end) - start_cash, 2),
        },
    }
