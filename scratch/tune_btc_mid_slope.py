"""BTC 4h grid: HL midpoint cross, both slopes positive, close above trend EMA.

Same risk axes as the EMA grid: trend EMA 100/150/200, ATR period 14-20,
SL x ATR, and trail x ATR. Also varies slope span n.
Optional --min-slope-step adds a slope floor (entry requires slope >= floor).
The post-exit reset still requires the slope to go negative.
Exit matches the EMA grid: wick SL, trail from close, ambiguous bars on 1h.

Usage:
  .\\.venv\\Scripts\\python.exe scratch\\tune_btc_mid_slope.py
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date, timedelta

import numpy as np
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
os.chdir(REPO_ROOT)
for path in (
    REPO_ROOT,
    os.path.join(REPO_ROOT, 'src'),
    os.path.join(REPO_ROOT, 'scratch'),
    os.path.join(REPO_ROOT, 'scratch', 'sim_player'),
):
    if path not in sys.path:
        sys.path.insert(0, path)

import tune_btc_ema_grid as grid  # noqa: E402
from config import Config, RISK_SETTINGS  # noqa: E402
from engine import _atr_series, _ema_series  # noqa: E402
from shared.intrabar_resolve import as_naive_ts, finer_arrays  # noqa: E402
from sim_player.ohlcv import fetch_btc_intraday  # noqa: E402
from slope_view.series import close_slope_entry, mid_slope_entry  # noqa: E402

SYMBOL = 'BTC/USDT'
SPANS = list(range(10, 101, 5))
TREND_WINDOWS = grid.TREND_WINDOWS
ATR_PERIODS = grid.ATR_PERIODS
SL_ATRS = grid.SL_ATRS
TRAIL_ATRS = grid.TRAIL_ATRS
WARMUP_DAYS = 60
REPORT_PATH = os.path.join(REPO_ROOT, 'docs', 'btc_mid_slope_4h.md')
CLOSE_REPORT_PATH = os.path.join(REPO_ROOT, 'docs', 'btc_close_slope_4h.md')
MIN_REPORT_PATH = os.path.join(REPO_ROOT, 'docs', 'btc_mid_slope_min_4h.md')
MIN_CLOSE_REPORT_PATH = os.path.join(REPO_ROOT, 'docs', 'btc_close_slope_min_4h.md')
MIN_TRADES = 3


def _load_interval(interval: str):
    from data_ingestion import _normalize_ohlcv

    name = 'BTC_USDT_4h.csv' if interval == '4h' else 'BTC_USDT_1h.csv'
    path = os.path.join(Config.DATA_DIR, 'ohlcv_cache', name)
    if os.path.isfile(path):
        df = _normalize_ohlcv(pd.read_csv(path, index_col=0, parse_dates=True))
        if df is not None and not df.empty:
            print(f'Using {interval} cache ({len(df)} bars)')
            return df
    return fetch_btc_intraday(interval)


def _load_4h():
    df = _load_interval('4h')
    if df is None or df.empty:
        raise SystemExit('No BTC 4h data')
    try:
        finer = _load_interval('1h')
    except Exception as exc:
        print(f'WARN: 1h drill unavailable ({exc})')
        finer = None
    return df, finer


def _floors(step: float, max_floor: float) -> list[float]:
    if step <= 0:
        return [0.0]
    floors = []
    value = float(step)
    while value <= max_floor + 1e-9:
        floors.append(value)
        value += step
    if not floors:
        raise SystemExit('Slope floor grid is empty')
    return floors


def _structure(signal: str, floors: list[float]) -> str:
    floored = floors != [0.0]
    if floored:
        step = floors[1] - floors[0] if len(floors) > 1 else floors[0]
        floor_txt = (
            f'Entry also requires slope >= min '
            f'({floors[0]:g}..{floors[-1]:g} step {step:g}, dollars per bar). '
            'After an exit the slope must still go negative, then positive, before the next entry. '
            'Dropping under the floor is not the reset. '
        )
    else:
        floor_txt = ''
    if signal == 'close':
        base = (
            'Structure: **slope of close above the floor** and close > trend EMA. '
            if floored else
            'Structure: **slope of close > 0** and close > trend EMA. '
        )
        return (
            base
            + 'No open-close or high-low averages. '
            + (
                floor_txt
                if floored else
                'After an exit, the close slope must go negative and then positive before the next entry. '
            )
            + 'slope = (close now - close n bars ago) / n. '
        )
    base = (
        'Structure: **HL avg crosses above OC avg**, both slopes meet the floor, close > trend EMA. '
        if floored else
        'Structure: **HL avg crosses above OC avg**, both slopes positive, close > trend EMA. '
    )
    return (
        base
        + (
            floor_txt
            if floored else
            'After an exit, both slopes must go negative and then both positive before the next entry. '
        )
        + 'avg = raw midpoint. slope = (midpoint now - midpoint n bars ago) / n. '
    )


def _write_report(
    ranked, eligible, start, end, elapsed, n_configs, drill_on: bool,
    report_path: str, label: str, signal: str, floors: list[float],
) -> None:
    show_min = floors != [0.0]

    def _table(rows, ranked_rows):
        if show_min:
            lines = [
                '| # | PnL | Equity | WR% | Trades | PF | n | min | trend | atr | SL× | trail× |',
                '|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|',
            ]
        else:
            lines = [
                '| # | PnL | Equity | WR% | Trades | PF | n | trend | atr | SL× | trail× |',
                '|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|',
            ]
        for i, r in enumerate(ranked_rows, 1):
            p = r['params']
            pf = r['profit_factor']
            pf_s = 'inf' if pf == float('inf') else f'{pf:.2f}'
            min_cell = f"{p['min_slope']:g} | " if show_min else ''
            lines.append(
                f"| {i} | ${r['net_pnl']:+,.0f} | ${r['equity']:,.0f} | {r['win_rate']:.0f} | "
                f"{r['closed_trades']} | {pf_s} | {p['slope_span']} | {min_cell}{p['trend_window']} | "
                f"{p['atr_period']} | {p['sl_atr']:g} | {p['trail_atr']:g} |"
            )
        return lines

    by_pnl = sorted(ranked, key=lambda r: r['net_pnl'], reverse=True)
    lines = [
        f"# BTC {'close' if signal == 'close' else 'midpoint'} slope ({label})",
        '',
        f'Generated: {pd.Timestamp.now().isoformat(timespec="seconds")}',
        f'Window: `{start}` .. `{end}` | Interval: `4h` | Symbols: `{SYMBOL}` | '
        f'Start cash: ${Config.INITIAL_STRATEGY_CASH:,.0f}',
        f'Elapsed: **{grid._fmt_duration(elapsed)}** ({elapsed:.1f}s) for **{n_configs}** configs',
        '',
        _structure(signal, floors)
        + f'Trend EMA **{"/".join(str(w) for w in TREND_WINDOWS)}**. '
        f'ATR period **{ATR_PERIODS[0]}..{ATR_PERIODS[-1]}**. '
        f'n is {SPANS[0]}..{SPANS[-1]} step {SPANS[1] - SPANS[0]}.',
        'Risk: no TP1; SL = `sl_atr` x ATR; trail from entry = `trail_atr` x current ATR. Long only.',
        'Bars: **4h**. '
        + (
            'Ambiguous trail bars (`S0 < low <= S1`) resolved on **1h**.'
            if drill_on
            else '1h drill was unavailable.'
        ),
        '',
        f'Configs: **{len(ranked)}** | Eligible (n>={MIN_TRADES}): **{len(eligible)}**',
        '',
        '## Top 10 by composite (eligible)',
        '',
    ]
    lines += _table(eligible, eligible[: grid.REPORT_TOP_N])
    lines += [
        '',
        '## Best by net PnL (top 10, any trade count)',
        '',
    ]
    lines += _table(by_pnl, by_pnl[: grid.REPORT_TOP_N])
    lines.append('')
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines))
    print(f'Wrote {report_path}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', help='First scored day, YYYY-MM-DD. Bars before this stay as warmup.')
    parser.add_argument('--end', help='Last scored day, YYYY-MM-DD.')
    parser.add_argument('--report', help='Markdown path. Default docs/btc_mid_slope_4h.md')
    parser.add_argument('--label', default='4h pass')
    parser.add_argument('--signal', choices=('mid', 'close'), default='mid')
    parser.add_argument('--min-slope-step', type=float, default=0,
                        help='Entry slope floor step. 0 keeps slope > 0.')
    parser.add_argument('--min-slope-max', type=float, default=200,
                        help='Highest slope floor when --min-slope-step is set.')
    args = parser.parse_args()
    floors = _floors(args.min_slope_step, args.min_slope_max)

    df, finer_df = _load_4h()
    first = as_naive_ts(df.index[0]).date()
    last = as_naive_ts(df.index[-1]).date()
    end = date.fromisoformat(args.end) if args.end else last
    end = min(end, last)
    start = date.fromisoformat(args.start) if args.start else first + timedelta(days=WARMUP_DAYS)
    if start > end:
        raise SystemExit(f'Window empty: {start} .. {end}')

    close = df['close'].astype(float).to_numpy(dtype=float)
    high = df['high'].astype(float).to_numpy(dtype=float)
    low = df['low'].astype(float).to_numpy(dtype=float)
    open_ = df['open'].astype(float).to_numpy(dtype=float)

    dates = np.array([as_naive_ts(ts).date() for ts in df.index])
    in_window = (dates >= start) & (dates <= end)
    start_idx = int(np.argmax(in_window))
    end_idx = int(len(df) - 1 - np.argmax(in_window[::-1]))
    n_bars = end_idx + 1
    close_a = close[:n_bars]
    low_a = low[:n_bars]
    high_a = high[:n_bars]
    open_a = open_[:n_bars]

    ema_by = {tw: _ema_series(close_a, tw) for tw in TREND_WINDOWS}
    atr_by = {ap: _atr_series(high_a, low_a, close_a, ap) for ap in ATR_PERIODS}
    bar_times = np.array(
        [pd.Timestamp(as_naive_ts(ts)).to_datetime64() for ts in df.index[:n_bars]],
        dtype='datetime64[ns]',
    )
    finer = finer_arrays(finer_df)
    if finer is not None:
        finer_times, finer_low, finer_close = finer
        print(f'Intrabar drill: 4h ambiguous bars -> 1h ({len(finer_times)} bars)')
    else:
        finer_times = finer_low = finer_close = None
        print('Intrabar drill disabled')

    entries = {}
    slopes = {}
    for span in SPANS:
        if args.signal == 'close':
            _, slope = close_slope_entry(close_a, ema_by[TREND_WINDOWS[0]], span)
            pair = (slope, slope)
        else:
            _, _, _, soc, shl = mid_slope_entry(
                open_a, high_a, low_a, close_a, ema_by[TREND_WINDOWS[0]], span,
            )
            pair = (soc, shl)
        slopes[span] = pair
        for tw in TREND_WINDOWS:
            for floor in floors:
                if args.signal == 'close':
                    entry, _ = close_slope_entry(
                        close_a, ema_by[tw], span, floor,
                    )
                else:
                    entry, _, _, _, _ = mid_slope_entry(
                        open_a, high_a, low_a, close_a, ema_by[tw], span, floor,
                    )
                entry = entry.copy()
                entry[:start_idx] = False
                entries[(span, tw, floor)] = entry
        shown = (floors[0], floors[-1]) if len(floors) > 1 else (floors[0],)
        counts = ', '.join(
            f'min{floor:g}/trend{tw}={int(entries[(span, tw, floor)].sum())}'
            for floor in shown
            for tw in TREND_WINDOWS
        )
        print(f'n={span} entry bars in window: {counts}')

    combos = [
        (n, tw, floor, ap, sl, trail)
        for n in SPANS
        for tw in TREND_WINDOWS
        for floor in floors
        for ap in ATR_PERIODS
        for sl in SL_ATRS
        for trail in TRAIL_ATRS
    ]
    total = len(combos)
    print(f'Running {total} configs on {SYMBOL} ({start} .. {end})...')
    results = []
    t0 = time.perf_counter()
    for done, (span, tw, floor, ap, sl, trail) in enumerate(combos, 1):
        metrics = grid.simulate_long_path(
            entries[(span, tw, floor)],
            close_a,
            low_a,
            atr_by[ap],
            sl,
            trail,
            start_idx,
            float(Config.INITIAL_STRATEGY_CASH),
            RISK_SETTINGS,
            bar_times=bar_times,
            parent_interval='4h',
            finer_times=finer_times,
            finer_low=finer_low,
            finer_close=finer_close,
            slope_oc=slopes[span][0],
            slope_hl=slopes[span][1],
        )
        metrics['params'] = {
            'strategy': 'close_slope' if args.signal == 'close' else 'mid_slope',
            'slope_span': span,
            'min_slope': floor,
            'trend_window': tw,
            'atr_period': ap,
            'sl_atr': sl,
            'trail_atr': trail,
            'short_window': 0,
            'long_window': 0,
        }
        results.append(metrics)
        if done % 2000 == 0 or done == total:
            elapsed_now = time.perf_counter() - t0
            rate = done / elapsed_now if elapsed_now > 0 else 0
            eta = (total - done) / rate if rate > 0 else 0
            best = max(r['net_pnl'] for r in results)
            print(
                f'[{done}/{total}] {rate:.1f}/s ETA {grid._fmt_duration(eta)} '
                f'best PnL=${best:+,.0f}'
            )

    elapsed = time.perf_counter() - t0
    ranked = grid.attach_composite_scores(results)
    eligible = [r for r in ranked if r['closed_trades'] >= MIN_TRADES]
    eligible = grid.attach_composite_scores(eligible) if eligible else []
    if args.report:
        report_path = args.report
    elif floors != [0.0]:
        report_path = MIN_CLOSE_REPORT_PATH if args.signal == 'close' else MIN_REPORT_PATH
    else:
        report_path = CLOSE_REPORT_PATH if args.signal == 'close' else REPORT_PATH
    if not os.path.isabs(report_path):
        report_path = os.path.join(REPO_ROOT, report_path)
    _write_report(
        ranked, eligible, start, end, elapsed, len(combos), finer is not None,
        report_path, args.label, args.signal, floors,
    )
    print(f'\n=== Top {grid.REPORT_TOP_N} (eligible) ===')
    for i, r in enumerate(eligible[: grid.REPORT_TOP_N], 1):
        p = r['params']
        print(
            f"{i}. n={p['slope_span']} min={p['min_slope']:g} trend={p['trend_window']} "
            f"atr={p['atr_period']} "
            f"SL={p['sl_atr']:g} trail={p['trail_atr']:g} "
            f"pnl={r['net_pnl']:+,.0f} wr={r['win_rate']:.0f}% trades={r['closed_trades']} "
            f"pf={r['profit_factor']:.2f}"
        )
    if not eligible:
        print('No eligible configs.')


if __name__ == '__main__':
    main()
