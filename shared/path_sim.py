"""Long-only path simulator for offline curation (risk/fill invariants enforced)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from shared import mtf
from shared.risk_sizing import size_long_from_equity

EPS = 1e-9


class PathSimInvariantError(RuntimeError):
    """Raised when a sim run violates risk or fill invariants."""


def ema_series(close: np.ndarray, period: int) -> np.ndarray:
    return pd.Series(close).ewm(span=int(period), adjust=False).mean().to_numpy(dtype=float)


def atr_series(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    h = pd.Series(high)
    l = pd.Series(low)
    c = pd.Series(close)
    prev_c = c.shift(1)
    tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    tr.iloc[0] = h.iloc[0] - l.iloc[0]
    return tr.ewm(alpha=1.0 / float(period), adjust=False).mean().to_numpy(dtype=float)


def adx_series(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Wilder-style ADX (matches strategies.base_strategy closely enough for gating)."""
    h = pd.Series(high, dtype=float)
    l = pd.Series(low, dtype=float)
    c = pd.Series(close, dtype=float)
    up = h.diff()
    down = -l.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    prev_c = c.shift(1)
    tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    tr.iloc[0] = h.iloc[0] - l.iloc[0]
    alpha = 1.0 / float(period)
    atr = tr.ewm(alpha=alpha, adjust=False).mean()
    plus_di = 100.0 * pd.Series(plus_dm).ewm(alpha=alpha, adjust=False).mean() / atr.replace(0, np.nan)
    minus_di = 100.0 * pd.Series(minus_dm).ewm(alpha=alpha, adjust=False).mean() / atr.replace(0, np.nan)
    dx = (100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    return dx.ewm(alpha=alpha, adjust=False).mean().to_numpy(dtype=float)


def build_long_entry_mask(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    *,
    short_window: int,
    long_window: int,
    trend_window: int,
    atr_period: int,
    adx_min: float = 20.0,
    atr_buffer: float = 0.5,
    adx_period: int = 14,
    regime_ok: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Golden cross + trend + ADX + EMA-ATR separation + optional regime mask.

    Returns (entry_bool, atr_array).
    """
    close = np.asarray(close, dtype=float)
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    n = len(close)
    fast = ema_series(close, short_window)
    slow = ema_series(close, long_window)
    trend = ema_series(close, trend_window)
    atr = atr_series(high, low, close, atr_period)
    adx = adx_series(high, low, close, adx_period) if float(adx_min) > 0 else np.full(n, 100.0)

    entry = np.zeros(n, dtype=bool)
    for i in range(1, n):
        if not (atr[i] == atr[i]) or atr[i] <= 0:
            continue
        if not (fast[i] == fast[i] and slow[i] == slow[i] and trend[i] == trend[i]):
            continue
        cross = fast[i - 1] <= slow[i - 1] and fast[i] > slow[i]
        if not cross:
            continue
        if close[i] <= trend[i]:
            continue
        if float(adx_min) > 0 and (not (adx[i] == adx[i]) or adx[i] < float(adx_min)):
            continue
        if abs(fast[i] - slow[i]) < float(atr_buffer) * float(atr[i]):
            continue
        if regime_ok is not None and not bool(regime_ok[i]):
            continue
        entry[i] = True
    return entry, atr


MTF_DEFAULTS = {
    'trend_tf': 'D', 'cross_tf': 'D', 'atr_tf': 'D', 'exit_tf': 'D', 'exit_mode': 'stop_only',
}


def effective_tfs(params: dict) -> dict:
    """Timeframe params with the legacy trend_weekly flag mapped to trend_tf='W'."""
    out = {k: params.get(k, v) for k, v in MTF_DEFAULTS.items()}
    if params.get('trend_weekly') and 'trend_tf' not in params:
        out['trend_tf'] = 'W'
    for k in ('trend_tf', 'cross_tf', 'atr_tf', 'exit_tf'):
        out[k] = mtf.check_tf(out[k])
    return out


def build_signals(df: pd.DataFrame, params: dict, *, adx_min: float = 0.0, atr_buffer: float = 0.0,
                  adx_period: int = 14) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Entry mask, ATR and signal-exit mask for one symbol from its daily OHLC frame.

    Plain daily params (no trend_weekly / *_tf / exit_mode) reproduce build_long_entry_mask exactly.
    """
    tf = effective_tfs(params)
    n = len(df)
    exit_mode = str(tf['exit_mode'])
    daily_only = (
        tf['trend_tf'] == 'D' and tf['cross_tf'] == 'D' and tf['atr_tf'] == 'D' and exit_mode == 'stop_only'
    )
    close = df['close'].to_numpy(dtype=float)
    high = df['high'].to_numpy(dtype=float)
    low = df['low'].to_numpy(dtype=float)
    fast_w, slow_w = int(params['short_window']), int(params['long_window'])
    trend_w, atr_p = int(params['trend_window']), int(params['atr_period'])
    if daily_only:
        entry, atr = build_long_entry_mask(
            close, high, low, short_window=fast_w, long_window=slow_w, trend_window=trend_w,
            atr_period=atr_p, adx_min=adx_min, atr_buffer=atr_buffer, adx_period=adx_period,
        )
        return entry, atr, np.zeros(n, dtype=bool)

    ema = lambda series, span: series.ewm(span=int(span), adjust=False).mean()  # noqa: E731
    bars = {t: mtf.completed_ohlc(df, t) for t in {tf['cross_tf'], tf['trend_tf'], tf['atr_tf'], tf['exit_tf']}}
    up, _down = mtf.cross_events(df, fast_w, slow_w, tf['cross_tf'], ema, bars[tf['cross_tf']])
    bull, _bear = mtf.trend_flags(df, trend_w, tf['trend_tf'], ema, bars[tf['trend_tf']])
    if tf['atr_tf'] == 'D':
        atr = atr_series(high, low, close, atr_p)
    else:
        atr = mtf.atr_on_tf(df, atr_p, tf['atr_tf'], bars[tf['atr_tf']]).to_numpy(dtype=float)
    entry = up.to_numpy(dtype=bool) & bull.to_numpy(dtype=bool) & (atr == atr) & (atr > 0)
    if float(adx_min) > 0:
        adx = adx_series(high, low, close, adx_period)
        entry &= (adx == adx) & (adx >= float(adx_min))
    if float(atr_buffer) > 0:
        raise ValueError('atr_buffer > 0 is only supported with daily timeframes')
    exit_sig = mtf.exit_flags(
        df, exit_mode, tf['exit_tf'], fast_w, slow_w, trend_w, ema, bars[tf['exit_tf']],
    ).to_numpy(dtype=bool)
    return entry, atr, exit_sig


def _cost_basis_equity(cash: float, qtys: list[float], entries: list[float]) -> float:
    return float(cash) + sum(q * e for q, e in zip(qtys, entries) if q > 0)


def _metrics_from_closed(
    pnls: list[float],
    cash: float,
    open_mtm: float,
    start_cash: float,
    equity_curve: list[float] | None = None,
) -> dict:
    equity = cash + open_mtm
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    n_closed = len(pnls)
    win_rate = (len(wins) / n_closed * 100.0) if n_closed else 0.0
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    if gross_loss > 0:
        pf = gross_win / gross_loss
    elif gross_win > 0:
        pf = float('inf')
    else:
        pf = 0.0
    avg_win = (sum(wins) / len(wins)) if wins else 0.0
    avg_loss = (abs(sum(losses) / len(losses))) if losses else 0.0
    payoff = (avg_win / avg_loss) if avg_loss > 0 else (float('inf') if avg_win > 0 else 0.0)

    # Calmar from equity curve if provided
    calmar = 0.0
    max_dd = 0.0
    if equity_curve and len(equity_curve) > 1:
        peak = equity_curve[0]
        for e in equity_curve:
            if e > peak:
                peak = e
            if peak > 0:
                dd = (peak - e) / peak
                if dd > max_dd:
                    max_dd = dd
        years = max(len(equity_curve) / 252.0, 1e-9)
        cagr = (equity / start_cash) ** (1.0 / years) - 1.0 if start_cash > 0 and equity > 0 else 0.0
        calmar = (cagr / max_dd) if max_dd > EPS else (cagr if cagr > 0 else 0.0)

    return {
        'closed_trades': n_closed,
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': round(win_rate, 2),
        'total_pnl': round(sum(pnls), 2),
        'profit_factor': pf,
        'payoff': payoff,
        'calmar': calmar,
        'max_drawdown': round(max_dd * 100.0, 2),
        'equity': round(equity, 2),
        'net_pnl': round(equity - start_cash, 2),
        'cash': round(cash, 2),
        'open_positions': 1 if open_mtm > EPS else 0,
    }


def _signal_exit(exit_sig, days, max_hold_days: int, i: int, entry_day: int) -> bool:
    """Close at this bar's close: higher-timeframe exit signal, or the holding horizon reached."""
    if exit_sig is not None and bool(exit_sig[i]):
        return True
    return bool(max_hold_days and days is not None and int(days[i]) - entry_day >= int(max_hold_days))


def gate_allows(pnls: list[float], gate: tuple[int, int, float] | None) -> bool:
    """Per-symbol profit gate: last `window` closed legs must net positive with PF >= min_pf.

    Fewer than `min_trades` legs = probation, entry allowed. gate = (window, min_trades, min_pf).
    """
    if not gate:
        return True
    window, min_trades, min_pf = int(gate[0]), int(gate[1]), float(gate[2])
    legs = pnls[-window:]
    if len(legs) < min_trades:
        return True
    if sum(legs) <= 0:
        return False
    loss = -sum(p for p in legs if p <= 0)
    win = sum(p for p in legs if p > 0)
    return loss == 0 or win / loss >= min_pf


def simulate_long_path(
    entry: np.ndarray,
    close: np.ndarray,
    low: np.ndarray,
    atr: np.ndarray,
    sl_atr: float,
    trail_atr: float,
    start_idx: int,
    start_cash: float,
    risk_settings: dict,
    *,
    trail_arm_r: float = 1.0,
    assert_invariants: bool = True,
    exit_sig: np.ndarray | None = None,
    days: np.ndarray | None = None,
    max_hold_days: int = 0,
) -> dict:
    """Long-only single-symbol path: fill stops at SL, trail after trail_arm_r.

    Trail distance uses ATR frozen at entry (not the live daily ATR).
    """
    cash = float(start_cash)
    qty = 0.0
    entry_price = 0.0
    stop = 0.0
    initial_stop = 0.0
    entry_atr = 0.0
    equity_at_entry = 0.0
    entry_day = 0
    trail_armed = False
    pnls: list[float] = []
    equity_curve: list[float] = []
    risk_pct = float(risk_settings['equity_risk_pct'])
    max_notional_pct = float(risk_settings['max_notional_pct'])
    n = len(close)

    for i in range(start_idx, n):
        a = atr[i]
        if qty > 0:
            if low[i] <= stop:
                exit_px = float(stop)  # fill at SL only
                pnl = (exit_px - entry_price) * qty
                if assert_invariants and pnl < 0 and equity_at_entry > 0:
                    loss_frac = abs(pnl) / equity_at_entry
                    if loss_frac > risk_pct + 1e-6:
                        raise PathSimInvariantError(
                            f'stop loss {loss_frac:.4%} of entry equity exceeds '
                            f'equity_risk_pct {risk_pct:.4%} (pnl={pnl:.4f})'
                        )
                cash += qty * exit_px
                pnls.append(pnl)
                qty = 0.0
                trail_armed = False
                equity_curve.append(cash)
                continue

            if _signal_exit(exit_sig, days, max_hold_days, i, entry_day):
                pnl = (float(close[i]) - entry_price) * qty
                cash += qty * float(close[i])
                pnls.append(pnl)
                qty = 0.0
                trail_armed = False
                equity_curve.append(cash)
                continue

            # Trail distance uses entry-bar ATR (frozen), not the live daily ATR.
            trail_a = entry_atr if entry_atr > 0 else a
            if trail_a == trail_a and trail_a > 0:
                # Arm trail after trail_arm_r × initial R
                init_rps = entry_price - initial_stop
                if init_rps > 0 and not trail_armed:
                    if (close[i] - entry_price) >= float(trail_arm_r) * init_rps:
                        trail_armed = True
                if trail_armed:
                    proposed = float(close[i]) - float(trail_atr) * float(trail_a)
                    if proposed > stop:
                        stop = proposed
            equity_curve.append(cash + qty * float(close[i]))
            continue

        if not entry[i]:
            equity_curve.append(cash)
            continue
        if not (a == a) or a <= 0:
            equity_curve.append(cash)
            continue

        price = float(close[i])
        stop0 = price - float(sl_atr) * float(a)
        equity = cash  # flat: equity == cash
        q, _tgt, _act, _cn, _cc, ok = size_long_from_equity(
            equity, cash, price, stop0, risk_settings,
        )
        if not ok or q <= 0:
            equity_curve.append(cash)
            continue

        notional = q * price
        if assert_invariants:
            if notional > max_notional_pct * equity + 1e-6:
                raise PathSimInvariantError(
                    f'open notional {notional / equity:.4%} exceeds max_notional_pct '
                    f'{max_notional_pct:.4%}'
                )
            if notional > cash + 1e-9:
                raise PathSimInvariantError(
                    f'open notional {notional:.4f} exceeds cash {cash:.4f}'
                )

        qty = q
        entry_price = price
        stop = stop0
        initial_stop = stop0
        entry_atr = float(a)
        equity_at_entry = equity
        entry_day = int(days[i]) if days is not None else 0
        trail_armed = False
        cash -= notional
        equity_curve.append(cash + qty * price)

    open_mtm = qty * float(close[-1]) if qty > 0 else 0.0
    out = _metrics_from_closed(pnls, cash, open_mtm, float(start_cash), equity_curve)
    out['open_positions'] = 1 if qty > 0 else 0
    return out


def simulate_long_portfolio(
    series: list[dict],
    sl_atr: float,
    trail_atr: float,
    start_cash: float,
    risk_settings: dict,
    *,
    trail_arm_r: float = 1.0,
    assert_invariants: bool = True,
    max_hold_days: int = 0,
    gate: tuple[int, int, float] | None = None,
) -> dict:
    """Shared-cash long-only book. Exits all symbols, then sequential entries."""
    cash = float(start_cash)
    n_sym = len(series)
    n = len(series[0]['close']) if series else 0
    qty = [0.0] * n_sym
    entry_price = [0.0] * n_sym
    stop = [0.0] * n_sym
    initial_stop = [0.0] * n_sym
    entry_atr = [0.0] * n_sym
    equity_at_entry = [0.0] * n_sym
    entry_day = [0] * n_sym
    sym_pnls: list[list[float]] = [[] for _ in range(n_sym)]
    trail_armed = [False] * n_sym
    pnls: list[float] = []
    equity_curve: list[float] = []
    risk_pct = float(risk_settings['equity_risk_pct'])
    max_notional_pct = float(risk_settings['max_notional_pct'])

    for i in range(n):
        # Exits first
        for s, ser in enumerate(series):
            if not ser['has_bar'][i] or qty[s] <= 0:
                continue
            a = ser['atr'][i]
            if ser['low'][i] <= stop[s]:
                exit_px = float(stop[s])
                pnl = (exit_px - entry_price[s]) * qty[s]
                if assert_invariants and pnl < 0 and equity_at_entry[s] > 0:
                    loss_frac = abs(pnl) / equity_at_entry[s]
                    if loss_frac > risk_pct + 1e-6:
                        raise PathSimInvariantError(
                            f'symbol[{s}] stop loss {loss_frac:.4%} exceeds '
                            f'equity_risk_pct {risk_pct:.4%}'
                        )
                cash += qty[s] * exit_px
                pnls.append(pnl)
                sym_pnls[s].append(pnl)
                qty[s] = 0.0
                trail_armed[s] = False
                continue
            if _signal_exit(ser.get('exit'), ser.get('days'), max_hold_days, i, entry_day[s]):
                px = float(ser['close'][i])
                pnl = (px - entry_price[s]) * qty[s]
                cash += qty[s] * px
                pnls.append(pnl)
                sym_pnls[s].append(pnl)
                qty[s] = 0.0
                trail_armed[s] = False
                continue
            trail_a = entry_atr[s] if entry_atr[s] > 0 else a
            sym_trail = float(ser.get('trail_atr', trail_atr))
            if trail_a == trail_a and trail_a > 0:
                init_rps = entry_price[s] - initial_stop[s]
                if init_rps > 0 and not trail_armed[s]:
                    if (ser['close'][i] - entry_price[s]) >= float(trail_arm_r) * init_rps:
                        trail_armed[s] = True
                if trail_armed[s]:
                    proposed = float(ser['close'][i]) - sym_trail * float(trail_a)
                    if proposed > stop[s]:
                        stop[s] = proposed

        # Sequential entries (update cash after each)
        for s, ser in enumerate(series):
            if not ser['has_bar'][i] or qty[s] > 0:
                continue
            if not ser['entry'][i]:
                continue
            a = ser['atr'][i]
            if not (a == a) or a <= 0:
                continue
            if not gate_allows(sym_pnls[s], gate):
                continue
            price = float(ser['close'][i])
            sym_sl = float(ser.get('sl_atr', sl_atr))
            stop0 = price - sym_sl * float(a)
            equity = _cost_basis_equity(cash, qty, entry_price)
            q, _tgt, _act, _cn, _cc, ok = size_long_from_equity(
                equity, cash, price, stop0, risk_settings,
            )
            if not ok or q <= 0:
                continue
            notional = q * price
            if assert_invariants:
                if notional > max_notional_pct * equity + 1e-6:
                    raise PathSimInvariantError(
                        f'symbol[{s}] notional {notional / equity:.4%} exceeds max_notional_pct'
                    )
                if notional > cash + 1e-9:
                    raise PathSimInvariantError(
                        f'symbol[{s}] notional {notional:.4f} exceeds cash {cash:.4f}'
                    )
            qty[s] = q
            entry_price[s] = price
            stop[s] = stop0
            initial_stop[s] = stop0
            entry_atr[s] = float(a)
            equity_at_entry[s] = equity
            entry_day[s] = int(ser['days'][i]) if ser.get('days') is not None else 0
            trail_armed[s] = False
            cash -= notional

        mtm = sum(
            qty[s] * float(series[s]['close'][i])
            for s in range(n_sym)
            if qty[s] > 0 and series[s]['has_bar'][i]
        )
        equity_curve.append(cash + mtm)

    open_mtm = 0.0
    open_n = 0
    for s, ser in enumerate(series):
        if qty[s] <= 0:
            continue
        last = n - 1
        while last >= 0 and not ser['has_bar'][last]:
            last -= 1
        if last >= 0:
            open_mtm += qty[s] * float(ser['close'][last])
            open_n += 1

    out = _metrics_from_closed(pnls, cash, open_mtm, float(start_cash), equity_curve)
    out['open_positions'] = open_n
    return out


def curator_score(result: dict, *, target_trades_per_year: float = 20.0, years: float = 4.0) -> float:
    """Higher is better: PF + payoff + calmar, with churn penalty."""
    pf = result.get('profit_factor') or 0.0
    if pf == float('inf') or (isinstance(pf, float) and math.isinf(pf)):
        pf = 10.0
    payoff = result.get('payoff') or 0.0
    if payoff == float('inf') or (isinstance(payoff, float) and math.isinf(payoff)):
        payoff = 10.0
    calmar = float(result.get('calmar') or 0.0)
    trades = float(result.get('closed_trades') or 0)
    expected = max(target_trades_per_year * max(years, 0.25), 1.0)
    churn_pen = 0.0
    if trades > expected * 1.5:
        churn_pen = (trades - expected * 1.5) / expected
    return float(0.45 * min(pf, 10.0) + 0.35 * min(payoff, 10.0) + 0.20 * max(calmar, 0.0) - churn_pen)


def params_from_ratios(
    short_window: int,
    slow_ratio: float,
    trend_window: int | None = None,
    trend_ratio: float | None = None,
    *,
    atr_period: int,
    sl_atr: float,
    trail_atr: float,
) -> dict[str, Any] | None:
    """Build six-pack from fast + ratios; None if constraints fail."""
    long_window = int(round(short_window * float(slow_ratio)))
    if long_window <= short_window:
        return None
    if trend_window is None:
        if trend_ratio is None:
            return None
        trend_window = int(round(long_window * float(trend_ratio)))
    trend_window = int(trend_window)
    if trend_window < long_window:
        return None
    if float(trail_atr) < 0.75 * float(sl_atr) - 1e-12:
        return None
    return {
        'short_window': int(short_window),
        'long_window': int(long_window),
        'trend_window': int(trend_window),
        'atr_period': int(atr_period),
        'sl_atr': float(sl_atr),
        'trail_atr': float(trail_atr),
    }
