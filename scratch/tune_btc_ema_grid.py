"""
EMA grid (vectorized): fast 10-20, slow 20-50 (step 5), trend 100/150/200.

Grid: atr_period 14-20, sl_atr 1-3, trail_atr 1-3 (0.5 steps).
Entry: golden cross + close > trend EMA. Exit: SL or trail from entry (no TP1).
Default: BTC/USDT, last ~6 months. Use --book crypto|forex for shared-cash multi-pair.

Usage:
  .\\.venv\\Scripts\\python.exe scratch\\tune_btc_ema_grid.py
  .\\.venv\\Scripts\\python.exe scratch\\tune_btc_ema_grid.py --start 2024-09-11 --label "2y pass"
  .\\.venv\\Scripts\\python.exe scratch\\tune_btc_ema_grid.py --book crypto --start 2024-09-11 --label "2y pass"
  .\\.venv\\Scripts\\python.exe scratch\\tune_btc_ema_grid.py --book forex --start 2022-09-11 --label "4y pass"
  .\\.venv\\Scripts\\python.exe scratch\\tune_btc_ema_grid.py --book commodities --start 2022-09-11 --label "4y pass"
  .\\.venv\\Scripts\\python.exe scratch\\tune_btc_ema_grid.py --limit 50
  .\\.venv\\Scripts\\python.exe scratch\\tune_btc_ema_grid.py --parity
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
import time
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
os.chdir(REPO_ROOT)
for path in (REPO_ROOT, os.path.join(REPO_ROOT, 'src'), os.path.join(REPO_ROOT, 'scratch')):
    if path not in sys.path:
        sys.path.insert(0, path)

from config import COMMODITY_PAIRS, CRYPTO_PAIRS, FOREX_PAIRS, Config, RISK_SETTINGS
from data_ingestion import DataFetcher
from strategies.moving_average import MovingAverageStrategy

SYMBOL = 'BTC/USDT'
REPORT_PATH = os.path.join(REPO_ROOT, 'docs', 'btc_ema_grid_6m.md')
PF_CAP = 10.0

BOOKS = {
    'crypto': ('crypto', CRYPTO_PAIRS, 'Crypto'),
    'forex': ('forex', FOREX_PAIRS, 'Forex'),
    'commodities': ('commodity', COMMODITY_PAIRS, 'Commodities'),
}

FAST_WINDOWS = [10, 15, 20]
SLOW_WINDOWS = list(range(20, 55, 5))
TREND_WINDOWS = [100, 150, 200]
ATR_PERIODS = list(range(14, 21))
SL_ATRS = [1.0, 1.5, 2.0, 2.5, 3.0]
TRAIL_ATRS = [1.0, 1.5, 2.0, 2.5, 3.0]

W_WR = 0.25
W_PNL = 0.45
W_PF = 0.30


def _ema_pairs():
    return [(f, s) for f in FAST_WINDOWS for s in SLOW_WINDOWS if f < s]


def _fmt_duration(seconds: float) -> str:
    if seconds < 1:
        return f'{seconds * 1000:.0f}ms'
    if seconds < 60:
        return f'{seconds:.1f}s'
    s = int(round(seconds))
    m, s = divmod(s, 60)
    if m < 60:
        return f'{m}m {s}s'
    h, m = divmod(m, 60)
    return f'{h}h {m}m {s}s'


def _size_long(equity: float, cash: float, price: float, stop: float, risk_settings: dict) -> float:
    equity_risk_pct = risk_settings['equity_risk_pct']
    target_risk = equity * equity_risk_pct
    risk_per = price - stop
    if risk_per <= 0 or price <= 0 or stop <= 0:
        return 0.0
    qty = target_risk / risk_per
    capped = False
    max_notional = equity * risk_settings['max_notional_pct']
    if qty * price > max_notional:
        qty = max_notional / price
        capped = True
    if qty * price > cash:
        qty = cash / price
        capped = True
    actual_risk = qty * risk_per
    notional = qty * price
    if not capped and actual_risk < target_risk * risk_settings['min_risk_fraction']:
        return 0.0
    if notional < risk_settings['min_notional_usd']:
        return 0.0
    return float(qty)


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
) -> dict:
    """Long-only path: entry at close, SL via wick, trail from close after entry bar."""
    cash = float(start_cash)
    qty = 0.0
    entry_price = 0.0
    stop = 0.0
    pnls: list[float] = []
    n = len(close)

    for i in range(start_idx, n):
        a = atr[i]
        if qty > 0:
            if low[i] <= stop:
                exit_px = stop
                pnl = (exit_px - entry_price) * qty
                cash += qty * exit_px
                pnls.append(pnl)
                qty = 0.0
                continue
            if a == a and a > 0:  # not NaN
                proposed = close[i] - trail_atr * a
                if proposed > stop:
                    stop = proposed
            continue

        if not entry[i]:
            continue
        if not (a == a) or a <= 0:
            continue
        price = float(close[i])
        stop0 = price - sl_atr * float(a)
        q = _size_long(cash, cash, price, stop0, risk_settings)
        if q <= 0:
            continue
        qty = q
        entry_price = price
        stop = stop0
        cash -= qty * price

    equity = cash
    if qty > 0:
        equity += qty * float(close[-1])

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
    return {
        'closed_trades': n_closed,
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': round(win_rate, 2),
        'total_pnl': round(sum(pnls), 2),
        'profit_factor': pf,
        'equity': round(equity, 2),
        'net_pnl': round(equity - start_cash, 2),
        'open_positions': 1 if qty > 0 else 0,
        'cash': round(cash, 2),
    }


def _metrics_from_pnls(pnls: list[float], cash: float, open_mtm: float, start_cash: float) -> dict:
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
    open_n = 1 if open_mtm > 0 else 0
    return {
        'closed_trades': n_closed,
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': round(win_rate, 2),
        'total_pnl': round(sum(pnls), 2),
        'profit_factor': pf,
        'equity': round(equity, 2),
        'net_pnl': round(equity - start_cash, 2),
        'open_positions': open_n,
        'cash': round(cash, 2),
    }


def simulate_long_portfolio(
    series: list[dict],
    sl_atr: float,
    trail_atr: float,
    start_cash: float,
    risk_settings: dict,
) -> dict:
    """Shared-cash long-only book across symbols aligned on a common calendar.

    Each series dict: entry/close/low/atr bool|float arrays of equal length (calendar days),
    plus has_bar bool mask (False = no quote that day; skip entry/exit updates).
    Order: exits all symbols, then entries (symbol list order).
    """
    cash = float(start_cash)
    n_sym = len(series)
    n = len(series[0]['close']) if series else 0
    qty = [0.0] * n_sym
    entry_price = [0.0] * n_sym
    stop = [0.0] * n_sym
    pnls: list[float] = []

    for i in range(n):
        for s, ser in enumerate(series):
            if not ser['has_bar'][i] or qty[s] <= 0:
                continue
            a = ser['atr'][i]
            if ser['low'][i] <= stop[s]:
                exit_px = stop[s]
                pnl = (exit_px - entry_price[s]) * qty[s]
                cash += qty[s] * exit_px
                pnls.append(pnl)
                qty[s] = 0.0
                continue
            if a == a and a > 0:
                proposed = ser['close'][i] - trail_atr * a
                if proposed > stop[s]:
                    stop[s] = proposed

        for s, ser in enumerate(series):
            if not ser['has_bar'][i] or qty[s] > 0:
                continue
            if not ser['entry'][i]:
                continue
            a = ser['atr'][i]
            if not (a == a) or a <= 0:
                continue
            price = float(ser['close'][i])
            stop0 = price - sl_atr * float(a)
            q = _size_long(cash, cash, price, stop0, risk_settings)
            if q <= 0:
                continue
            qty[s] = q
            entry_price[s] = price
            stop[s] = stop0
            cash -= q * price

    open_mtm = 0.0
    open_n = 0
    for s, ser in enumerate(series):
        if qty[s] <= 0:
            continue
        # Mark at last available close in window
        last = n - 1
        while last >= 0 and not ser['has_bar'][last]:
            last -= 1
        if last >= 0:
            open_mtm += qty[s] * float(ser['close'][last])
            open_n += 1

    out = _metrics_from_pnls(pnls, cash, open_mtm, start_cash)
    out['open_positions'] = open_n
    return out


def _minmax(values: list) -> list:
    lo, hi = min(values), max(values)
    if hi <= lo:
        return [0.5] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def attach_composite_scores(results: list) -> list:
    if not results:
        return results
    wrs = [r['win_rate'] for r in results]
    pnls = [r['net_pnl'] for r in results]
    pfs = [
        min(PF_CAP, r['profit_factor'] if r['profit_factor'] != float('inf') else PF_CAP)
        for r in results
    ]
    wr_n = _minmax(wrs)
    pnl_n = _minmax(pnls)
    pf_n = _minmax(pfs)
    for i, r in enumerate(results):
        r['composite'] = round(W_WR * wr_n[i] + W_PNL * pnl_n[i] + W_PF * pf_n[i], 4)
    return sorted(results, key=lambda r: (r['composite'], r['net_pnl'], r['win_rate']), reverse=True)


def write_report(
    ranked: list,
    start: date,
    end: date,
    min_trades: int,
    elapsed_s: float,
    n_configs: int,
    report_path: str,
    label: str,
    symbols: list[str] | None = None,
    book_title: str | None = None,
):
    symbols = symbols or [SYMBOL]
    book = book_title or ('Crypto' if len(symbols) > 1 else 'BTC')
    sym_label = ', '.join(symbols) if len(symbols) <= 3 else f'{len(symbols)} {book.lower()} pairs'
    title = f'{book} EMA grid' if len(symbols) > 1 else 'BTC EMA grid'
    eligible = [r for r in ranked if r['closed_trades'] >= min_trades]
    eligible = attach_composite_scores(eligible) if eligible else []

    lines = [
        f'# {title} ({label})',
        '',
        f'Generated: {datetime.now().isoformat(timespec="seconds")}',
        f'Window: `{start}` .. `{end}` | Symbols: `{sym_label}` | Start cash: ${Config.INITIAL_STRATEGY_CASH:,.0f}',
        f'Elapsed: **{_fmt_duration(elapsed_s)}** ({elapsed_s:.1f}s) for **{n_configs}** configs '
        f'({n_configs / elapsed_s:.1f}/s)' if elapsed_s > 0 else f'Elapsed: n/a | Configs: {n_configs}',
        '',
        'Structure: **EMA fast/slow golden cross** (fast∈10/15/20, slow∈20..50 step 5, fast<slow), '
        'trend **close > EMA{100|150|200}**.',
        'Risk: no TP1; SL = `sl_atr` × ATR; trail from entry = `trail_atr` × current ATR. '
        'Long only. ADX/vol off. Metrics from vectorized path sim.',
    ]
    if len(symbols) > 1:
        lines.append(
            f'Shared-cash book across: {", ".join(symbols)}.'
        )
    lines += [
        '',
        f'Configs: **{len(ranked)}** | Eligible (n≥{min_trades}): **{len(eligible)}**',
        '',
        '## Top 15 by composite (eligible)',
        '',
        '| # | PnL | Equity | WR% | Trades | PF | fast | slow | trend | atr | SL× | trail× |',
        '|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for i, r in enumerate(eligible[:15], 1):
        p = r['params']
        pf = r['profit_factor']
        pf_s = 'inf' if pf == float('inf') else f'{pf:.2f}'
        lines.append(
            f"| {i} | ${r['net_pnl']:+,.0f} | ${r['equity']:,.0f} | {r['win_rate']:.0f} | "
            f"{r['closed_trades']} | {pf_s} | {p['short_window']} | {p['long_window']} | "
            f"{p['trend_window']} | {p['atr_period']} | {p['sl_atr']:g} | {p['trail_atr']:g} |"
        )

    lines += [
        '',
        '## Best by net PnL (any trade count)',
        '',
        '| # | PnL | WR% | Trades | PF | fast | slow | trend | atr | SL× | trail× |',
        '|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|',
    ]
    by_pnl = sorted(ranked, key=lambda r: (r['net_pnl'], r['win_rate']), reverse=True)
    for i, r in enumerate(by_pnl[:15], 1):
        p = r['params']
        pf = r['profit_factor']
        pf_s = 'inf' if pf == float('inf') else f'{pf:.2f}'
        lines.append(
            f"| {i} | ${r['net_pnl']:+,.0f} | {r['win_rate']:.0f} | {r['closed_trades']} | "
            f"{pf_s} | {p['short_window']} | {p['long_window']} | {p['trend_window']} | "
            f"{p['atr_period']} | {p['sl_atr']:g} | {p['trail_atr']:g} |"
        )

    lines += [
        '',
        '## Full eligible ranking',
        '',
        '| Rank | Composite | PnL | WR% | n | PF | params |',
        '|---:|---:|---:|---:|---:|---:|---|',
    ]
    for i, r in enumerate(eligible, 1):
        pf = r['profit_factor']
        pf_s = 'inf' if pf == float('inf') else f'{pf:.2f}'
        slim = {
            'short_window': r['params']['short_window'],
            'long_window': r['params']['long_window'],
            'trend_window': r['params']['trend_window'],
            'atr_period': r['params']['atr_period'],
            'sl_atr': r['params']['sl_atr'],
            'trail_atr': r['params']['trail_atr'],
        }
        lines.append(
            f"| {i} | {r['composite']:.4f} | ${r['net_pnl']:+,.0f} | {r['win_rate']:.0f} | "
            f"{r['closed_trades']} | {pf_s} | `{json.dumps(slim)}` |"
        )
    lines.append('')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    print(f'Wrote {report_path}')
    return eligible


def _bar_dates(df: pd.DataFrame) -> np.ndarray:
    return np.array([ts.date() if hasattr(ts, 'date') else pd.Timestamp(ts).date() for ts in df.index])


def run_grid(df: pd.DataFrame, start: date, end: date, limit: int | None = None, symbol: str = SYMBOL):
    base = MovingAverageStrategy({})
    pairs = _ema_pairs()
    ema_periods = sorted({p for pair in pairs for p in pair} | set(TREND_WINDOWS))
    print(f'Precomputing {len(ema_periods)} EMAs + {len(ATR_PERIODS)} ATRs...')
    ema = {p: base._ema(df['close'], p) for p in ema_periods}
    atr_by = {p: base._calculate_atr(df, p) for p in ATR_PERIODS}

    close = df['close'].astype(float)
    low = df['low'].astype(float)
    close_a = close.to_numpy(dtype=float)
    low_a = low.to_numpy(dtype=float)

    dates = _bar_dates(df)
    in_window = (dates >= start) & (dates <= end)
    if not in_window.any():
        raise SystemExit(f'No bars in window {start} .. {end}')
    start_idx = int(np.argmax(in_window))
    end_idx = int(len(df) - 1 - np.argmax(in_window[::-1]))
    close_a = close_a[: end_idx + 1]
    low_a = low_a[: end_idx + 1]
    n_bars = end_idx + 1

    combos = list(itertools.product(pairs, TREND_WINDOWS, ATR_PERIODS, SL_ATRS, TRAIL_ATRS))
    if limit is not None:
        combos = combos[:limit]
    total = len(combos)
    print(f'Running {total} configs on {symbol} ({start} .. {end}, start_idx={start_idx})...')

    results = []
    t0 = time.perf_counter()
    done = 0

    grouped: dict[tuple, list] = {}
    for (fast, slow), tw, ap, sl, trail in combos:
        grouped.setdefault((fast, slow, tw), []).append((ap, sl, trail))

    for (fast, slow, tw), inner in grouped.items():
        fast_s = ema[fast]
        slow_s = ema[slow]
        trend_s = ema[tw]
        cross = (fast_s.shift(1) <= slow_s.shift(1)) & (fast_s > slow_s)
        entry_s = cross & (close > trend_s)
        entry_a = entry_s.fillna(False).to_numpy(dtype=bool)[:n_bars]
        entry_a = entry_a.copy()
        entry_a[:start_idx] = False

        atr_cache = {}
        for ap, sl, trail in inner:
            if ap not in atr_cache:
                atr_cache[ap] = atr_by[ap].to_numpy(dtype=float)[:n_bars]
            metrics = simulate_long_path(
                entry_a,
                close_a,
                low_a,
                atr_cache[ap],
                sl,
                trail,
                start_idx,
                float(Config.INITIAL_STRATEGY_CASH),
                RISK_SETTINGS,
            )
            metrics['params'] = {
                'short_window': fast,
                'long_window': slow,
                'trend_window': tw,
                'atr_period': ap,
                'sl_atr': sl,
                'trail_atr': trail,
            }
            results.append(metrics)
            done += 1
            if done % 250 == 0 or done == total:
                elapsed = time.perf_counter() - t0
                rate = done / elapsed if elapsed > 0 else 0
                eta = (total - done) / rate if rate > 0 else 0
                best = max(r['net_pnl'] for r in results)
                print(
                    f'[{done}/{total}] {rate:.1f}/s ETA {_fmt_duration(eta)} '
                    f'best PnL=${best:+,.0f}'
                )

    elapsed = time.perf_counter() - t0
    return results, elapsed


def run_grid_multi(
    market: dict[str, pd.DataFrame],
    start: date,
    end: date,
    limit: int | None = None,
):
    """Shared-cash grid across multiple crypto symbols on a union calendar."""
    base = MovingAverageStrategy({})
    pairs = _ema_pairs()
    ema_periods = sorted({p for pair in pairs for p in pair} | set(TREND_WINDOWS))
    symbols = list(market.keys())

    all_dates = sorted({
        d
        for df in market.values()
        for d in _bar_dates(df)
        if start <= d <= end
    })
    if not all_dates:
        raise SystemExit(f'No bars in window {start} .. {end}')
    n_days = len(all_dates)
    date_to_i = {d: i for i, d in enumerate(all_dates)}

    print(f'Precomputing indicators for {len(symbols)} symbols ({n_days} calendar days)...')
    prep: dict[str, dict] = {}
    for sym, df in market.items():
        close = df['close'].astype(float)
        dates = _bar_dates(df)
        row_cal = np.array([date_to_i.get(d, -1) for d in dates], dtype=int)

        close_a = np.zeros(n_days, dtype=float)
        low_a = np.zeros(n_days, dtype=float)
        has_a = np.zeros(n_days, dtype=bool)
        valid = row_cal >= 0
        idxs = row_cal[valid]
        close_a[idxs] = close.to_numpy(dtype=float)[valid]
        low_a[idxs] = df['low'].astype(float).to_numpy(dtype=float)[valid]
        has_a[idxs] = True

        ema = {p: base._ema(close, p) for p in ema_periods}
        atr_cal = {}
        for ap in ATR_PERIODS:
            atr_s = base._calculate_atr(df, ap).to_numpy(dtype=float)
            atr_a = np.full(n_days, np.nan, dtype=float)
            atr_a[idxs] = atr_s[valid]
            atr_cal[ap] = atr_a

        prep[sym] = {
            'close': close,
            'ema': ema,
            'close_a': close_a,
            'low_a': low_a,
            'has_a': has_a,
            'atr_cal': atr_cal,
            'row_cal': row_cal,
            'valid': valid,
            'idxs': idxs,
        }

    combos = list(itertools.product(pairs, TREND_WINDOWS, ATR_PERIODS, SL_ATRS, TRAIL_ATRS))
    if limit is not None:
        combos = combos[:limit]
    total = len(combos)
    print(f'Running {total} configs on {len(symbols)} pairs ({start} .. {end})...')

    results = []
    t0 = time.perf_counter()
    done = 0

    grouped: dict[tuple, list] = {}
    for (fast, slow), tw, ap, sl, trail in combos:
        grouped.setdefault((fast, slow, tw), []).append((ap, sl, trail))

    for (fast, slow, tw), inner in grouped.items():
        entry_by_sym: dict[str, np.ndarray] = {}
        for sym, p in prep.items():
            close = p['close']
            fast_s = p['ema'][fast]
            slow_s = p['ema'][slow]
            trend_s = p['ema'][tw]
            cross = (fast_s.shift(1) <= slow_s.shift(1)) & (fast_s > slow_s)
            entry_raw = (cross & (close > trend_s)).fillna(False).to_numpy(dtype=bool)
            entry_a = np.zeros(n_days, dtype=bool)
            entry_a[p['idxs']] = entry_raw[p['valid']]
            entry_by_sym[sym] = entry_a

        for ap, sl, trail in inner:
            series = [
                {
                    'entry': entry_by_sym[sym],
                    'close': prep[sym]['close_a'],
                    'low': prep[sym]['low_a'],
                    'atr': prep[sym]['atr_cal'][ap],
                    'has_bar': prep[sym]['has_a'],
                }
                for sym in symbols
            ]
            metrics = simulate_long_portfolio(
                series, sl, trail, float(Config.INITIAL_STRATEGY_CASH), RISK_SETTINGS,
            )
            metrics['params'] = {
                'short_window': fast,
                'long_window': slow,
                'trend_window': tw,
                'atr_period': ap,
                'sl_atr': sl,
                'trail_atr': trail,
            }
            results.append(metrics)
            done += 1
            if done % 100 == 0 or done == total:
                elapsed = time.perf_counter() - t0
                rate = done / elapsed if elapsed > 0 else 0
                eta = (total - done) / rate if rate > 0 else 0
                best = max(r['net_pnl'] for r in results)
                print(
                    f'[{done}/{total}] {rate:.1f}/s ETA {_fmt_duration(eta)} '
                    f'best PnL=${best:+,.0f}'
                )

    elapsed = time.perf_counter() - t0
    return results, elapsed


def run_parity(df: pd.DataFrame, start: date, end: date):
    """Compare vector sim vs process_symbol on a few configs."""
    from ledger_manager import LedgerManager
    from resim_engine import process_symbol
    from strategies.moving_average import CachedMovingAverageStrategy
    from shared.trade_legs import leg_metric_buckets

    sample = [
        {'short_window': 10, 'long_window': 20, 'trend_window': 100, 'atr_period': 14, 'sl_atr': 1.5, 'trail_atr': 2.0},
        {'short_window': 15, 'long_window': 30, 'trend_window': 150, 'atr_period': 16, 'sl_atr': 2.0, 'trail_atr': 1.5},
        {'short_window': 20, 'long_window': 50, 'trend_window': 200, 'atr_period': 20, 'sl_atr': 2.5, 'trail_atr': 3.0},
    ]
    base = MovingAverageStrategy({})
    close = df['close'].astype(float)
    low = df['low'].astype(float)
    dates = np.array([ts.date() if hasattr(ts, 'date') else pd.Timestamp(ts).date() for ts in df.index])
    in_window = (dates >= start) & (dates <= end)
    start_idx = int(np.argmax(in_window))
    end_idx = int(len(df) - 1 - np.argmax(in_window[::-1]))
    close_a = close.to_numpy(dtype=float)[: end_idx + 1]
    low_a = low.to_numpy(dtype=float)[: end_idx + 1]

    print(f'Parity window {start} .. {end}')
    for p in sample:
        fast_s = base._ema(close, p['short_window'])
        slow_s = base._ema(close, p['long_window'])
        trend_s = base._ema(close, p['trend_window'])
        atr_s = base._calculate_atr(df, p['atr_period'])
        cross = (fast_s.shift(1) <= slow_s.shift(1)) & (fast_s > slow_s)
        entry_s = cross & (close > trend_s)
        entry_a = entry_s.fillna(False).to_numpy(dtype=bool)[: end_idx + 1].copy()
        entry_a[:start_idx] = False
        atr_a = atr_s.to_numpy(dtype=float)[: end_idx + 1]
        vec = simulate_long_path(
            entry_a, close_a, low_a, atr_a,
            p['sl_atr'], p['trail_atr'], start_idx,
            float(Config.INITIAL_STRATEGY_CASH), RISK_SETTINGS,
        )

        params = {
            **p,
            'adx_min': 0,
            'vol_mult': 0.0,
            'atr_buffer': 0.0,
            'long_only': True,
            'use_trailing': True,
            'skip_tp1': True,
            'trail_from_entry': True,
            'trend_exit': False,
        }
        cache = {
            'ema_fast': fast_s,
            'ema_slow': slow_s,
            'ema_trend': trend_s,
            'atr': atr_s,
            'adx': base._calculate_adx(df, 14),
        }
        ledger = LedgerManager(Config)
        ledger.ledger = {
            'strategies': {
                'parity': {
                    'cash': Config.INITIAL_STRATEGY_CASH,
                    'positions': {},
                    'history': [],
                }
            }
        }
        ledger.ledger_file = os.path.join(Config.DATA_DIR, 'ledger_parity_tmp.json')
        strat = CachedMovingAverageStrategy(params)
        strat.bind_cache(cache)
        for ts in df.index:
            d = ts.date() if hasattr(ts, 'date') else pd.Timestamp(ts).date()
            if d < start or d > end:
                continue
            market_data = df.loc[:ts]
            if len(market_data) < 220:
                continue
            process_symbol(
                ledger, 'parity', SYMBOL, strat, market_data,
                event_ts=f'{d.isoformat()}T23:59:59',
                verbose=False,
                build_snapshots=False,
            )
        hist = ledger.ledger['strategies']['parity']['history']
        wins, losses, _ = leg_metric_buckets(hist)
        n = len(wins) + len(losses)
        cash = ledger.ledger['strategies']['parity']['cash']
        pos = ledger.ledger['strategies']['parity']['positions']
        mtm = cash
        for pos_v in pos.values():
            px = (
                pos_v.get('last_price')
                or pos_v.get('current_price')
                or pos_v.get('entry_price')
                or 0
            )
            mtm += float(pos_v.get('qty', 0)) * float(px)
        eng_pnl = mtm - Config.INITIAL_STRATEGY_CASH
        print(
            f"  {p}: vec n={vec['closed_trades']} pnl=${vec['net_pnl']:+.0f} | "
            f"engine n={n} pnl=${eng_pnl:+.0f} | dn={vec['closed_trades'] - n} "
            f"dpnl=${vec['net_pnl'] - eng_pnl:+.0f}"
        )


def _default_report_path(book: str | None, label: str) -> str:
    if book in ('crypto', 'forex', 'commodities'):
        prefix = 'commodities' if book == 'commodities' else book
        if '4y' in label:
            suffix = '4y'
        elif '2y' in label:
            suffix = '2y'
        else:
            suffix = '6m'
        return os.path.join(REPO_ROOT, 'docs', f'{prefix}_ema_grid_{suffix}.md')
    if '2y' in label:
        return os.path.join(REPO_ROOT, 'docs', 'btc_ema_grid_2y.md')
    return REPORT_PATH


def main():
    parser = argparse.ArgumentParser(description='EMA period grid (vectorized)')
    parser.add_argument('--start', default=None, help='ISO start (default: ~6 months before last bar)')
    parser.add_argument('--end', default=None)
    parser.add_argument('--min-trades', type=int, default=3)
    parser.add_argument('--limit', type=int, default=None, help='Cap configs (pilot timing)')
    parser.add_argument('--parity', action='store_true', help='Compare vector sim vs process_symbol')
    parser.add_argument('--report', default=None, help='Report markdown path (default under docs/)')
    parser.add_argument('--label', default=None, help='Report title label (e.g. 2y pass)')
    parser.add_argument(
        '--book',
        choices=sorted(BOOKS.keys()),
        default=None,
        help='Shared-cash multi-pair book (crypto or forex)',
    )
    parser.add_argument(
        '--all-crypto',
        action='store_true',
        help='Alias for --book crypto',
    )
    args = parser.parse_args()

    book = args.book
    if args.all_crypto:
        book = 'crypto'

    fetcher = DataFetcher(Config)
    book_title = None

    if book:
        asset_type, pair_list, book_title = BOOKS[book]
        print(f'Loading {len(pair_list)} {book} pairs...')
        market: dict[str, pd.DataFrame] = {}
        for sym in pair_list:
            df = fetcher.get_data(sym, asset_type=asset_type)
            if df is None or df.empty:
                print(f'  skip {sym}: no data')
                continue
            market[sym] = df
            print(f'  {sym}: {len(df)} bars')
        fetcher.report_fetch_alerts()
        if not market:
            raise SystemExit(f'No {book} market data')
        last_bar = max(df.index[-1].date() for df in market.values())
        symbols = list(market.keys())
    else:
        print('Loading BTC/USDT...')
        df = fetcher.get_data(SYMBOL, asset_type='crypto')
        fetcher.report_fetch_alerts()
        if df.empty:
            raise SystemExit('No BTC data')
        market = {SYMBOL: df}
        last_bar = df.index[-1].date()
        symbols = [SYMBOL]

    end = date.fromisoformat(args.end) if args.end else last_bar
    end = min(end, last_bar)
    if args.start:
        start = date.fromisoformat(args.start)
    else:
        start = end - timedelta(days=182)

    span_days = (end - start).days
    if args.label:
        label = args.label
    elif span_days >= 1200:
        label = '4y pass'
    elif span_days >= 600:
        label = '2y pass'
    elif span_days >= 150:
        label = '6m pass'
    else:
        label = f'{span_days}d pass'

    report_path = args.report or _default_report_path(book, label)

    if args.parity:
        if book:
            raise SystemExit('--parity is BTC-only')
        run_parity(market[SYMBOL], start, end)
        return

    n_full = len(_ema_pairs()) * len(TREND_WINDOWS) * len(ATR_PERIODS) * len(SL_ATRS) * len(TRAIL_ATRS)
    if book:
        results, elapsed = run_grid_multi(market, start, end, limit=args.limit)
    else:
        results, elapsed = run_grid(market[SYMBOL], start, end, limit=args.limit, symbol=SYMBOL)
    rate = len(results) / elapsed if elapsed > 0 else 0
    print(f'\nTimed {len(results)} configs in {_fmt_duration(elapsed)} ({rate:.1f}/s)')
    if args.limit and args.limit < n_full:
        est = elapsed * (n_full / len(results)) if results else 0
        print(f'Full grid estimate ({n_full} configs): ~{_fmt_duration(est)}')

    ranked = attach_composite_scores(results)
    eligible = write_report(
        ranked, start, end, args.min_trades, elapsed, len(results), report_path, label,
        symbols=symbols,
        book_title=book_title,
    )

    print('\n=== Top 10 (eligible) ===')
    for i, r in enumerate(eligible[:10], 1):
        p = r['params']
        print(
            f"{i:2d}. PnL=${r['net_pnl']:+7.0f}  WR={r['win_rate']:5.1f}%  n={r['closed_trades']:2d}  "
            f"fast={p['short_window']} slow={p['long_window']} trend={p['trend_window']} "
            f"atr={p['atr_period']} SL={p['sl_atr']:g} trail={p['trail_atr']:g}"
        )
    if not eligible:
        print('(none with min trades)')
        by_pnl = sorted(ranked, key=lambda r: r['net_pnl'], reverse=True)[:5]
        print('Top by PnL (any n):')
        for i, r in enumerate(by_pnl, 1):
            p = r['params']
            print(
                f"{i:2d}. PnL=${r['net_pnl']:+7.0f} n={r['closed_trades']} "
                f"fast={p['short_window']} slow={p['long_window']} trend={p['trend_window']}"
            )
    print(f'\nReport: {report_path}')


if __name__ == '__main__':
    main()
