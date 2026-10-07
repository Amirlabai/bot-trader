"""One shared-cash crypto book on the BTC 4h 6-month midpoint winner.

Params are composite #1 from docs/btc_mid_slope_4h_6m.md.
Slope must be positive. After an exit that symbol's slopes must go negative
before it can enter again. Dollars-per-bar floors are not used: 160 is a BTC
price scale and would shut out cheaper coins.

One $10k wallet. Symbols share cash. This does not run a solo account per coin.

Usage:
  .\\.venv\\Scripts\\python.exe scratch\\run_crypto_mid_slope_book.py
  .\\.venv\\Scripts\\python.exe scratch\\run_crypto_mid_slope_book.py --signal close
"""
from __future__ import annotations

import os
import sys
import time
from datetime import date, datetime, timedelta

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
from config import CRYPTO_PAIRS, Config, RISK_SETTINGS  # noqa: E402
from data_ingestion import YAHOO_PAUSE_SEC, _normalize_ohlcv, yahoo_ticker  # noqa: E402
from engine import _atr_series, _ema_series  # noqa: E402
from shared.intrabar_resolve import (  # noqa: E402
    as_naive_ts,
    finer_arrays,
    parent_bar_end,
    resolve_ambiguous,
    trail_from_close,
)
from slope_view.series import SlopeReset, close_slope_entry, mid_slope_entry  # noqa: E402

# docs/btc_mid_slope_4h_6m.md composite #1, or close-slope composite #1.
SLOPE_SPAN = 95
TREND_WINDOW = 100
ATR_PERIOD = 14
SL_ATR = 3.0
TRAIL_ATR = 1.5
SIGNAL = 'mid'
START = date(2026, 3, 24)
END = date(2026, 9, 22)
WARMUP_DAYS = 60
REPORT_PATH = os.path.join(REPO_ROOT, 'docs', 'crypto_mid_slope_4h_6m.md')


def _apply_signal(signal: str) -> None:
    global SLOPE_SPAN, TREND_WINDOW, ATR_PERIOD, SL_ATR, TRAIL_ATR, SIGNAL, REPORT_PATH
    SIGNAL = signal
    if signal == 'close':
        # docs/btc_close_slope_4h_6m.md composite #1
        SLOPE_SPAN = 40
        TREND_WINDOW = 100
        ATR_PERIOD = 14
        SL_ATR = 1.0
        TRAIL_ATR = 1.5
        REPORT_PATH = os.path.join(REPO_ROOT, 'docs', 'crypto_close_slope_4h_6m.md')
        return
    SLOPE_SPAN = 95
    TREND_WINDOW = 100
    ATR_PERIOD = 14
    SL_ATR = 3.0
    TRAIL_ATR = 1.5
    REPORT_PATH = os.path.join(REPO_ROOT, 'docs', 'crypto_mid_slope_4h_6m.md')


def _cache_path(symbol: str, interval: str) -> str:
    cache_dir = os.path.join(Config.DATA_DIR, 'ohlcv_cache')
    os.makedirs(cache_dir, exist_ok=True)
    safe = symbol.replace('/', '_')
    return os.path.join(cache_dir, f'{safe}_{interval}.csv')


def _covers(df: pd.DataFrame, need_from: date, need_to: date) -> bool:
    if df is None or df.empty:
        return False
    first = as_naive_ts(df.index[0]).date()
    last = as_naive_ts(df.index[-1]).date()
    return first <= need_from and last >= need_to


def load_interval(symbol: str, interval: str, need_from: date, need_to: date) -> pd.DataFrame | None:
    path = _cache_path(symbol, interval)
    cached = None
    if os.path.isfile(path):
        try:
            cached = _normalize_ohlcv(pd.read_csv(path, index_col=0, parse_dates=True))
        except Exception:
            cached = None
    if cached is not None and _covers(cached, need_from, need_to):
        print(f'Using {symbol} {interval} cache ({len(cached)} bars)')
        return cached

    try:
        import yfinance as yf
    except ImportError:
        if cached is not None and not cached.empty:
            print(f'{symbol} {interval}: yfinance missing, using stale cache')
            return cached
        print(f'{symbol} {interval}: no data')
        return None

    ticker = yahoo_ticker(symbol, asset_type='crypto')
    fetch_end = datetime.utcnow().date() + timedelta(days=1)
    fetch_start = need_from - timedelta(days=5)
    print(f'Fetching {ticker} {interval} ({fetch_start} .. {fetch_end})...')
    try:
        raw = yf.download(
            ticker,
            start=fetch_start.isoformat(),
            end=fetch_end.isoformat(),
            interval=interval,
            progress=False,
            auto_adjust=False,
            threads=False,
            multi_level_index=False,
        )
        time.sleep(YAHOO_PAUSE_SEC)
        df = _normalize_ohlcv(raw)
    except Exception as exc:
        print(f'{symbol} {interval} fetch failed ({exc})')
        return cached if cached is not None and not cached.empty else None
    if df is None or df.empty:
        print(f'{symbol} {interval}: Yahoo returned no rows')
        return cached if cached is not None and not cached.empty else None
    try:
        df.to_csv(path)
    except Exception as exc:
        print(f'WARN: could not cache {symbol} {interval}: {exc}')
    print(f'Loaded {symbol} {interval}: {len(df)} bars')
    return df


def _prep(df: pd.DataFrame) -> dict:
    close = df['close'].astype(float).to_numpy(dtype=float)
    high = df['high'].astype(float).to_numpy(dtype=float)
    low = df['low'].astype(float).to_numpy(dtype=float)
    open_ = df['open'].astype(float).to_numpy(dtype=float)
    ema = _ema_series(close, TREND_WINDOW)
    atr = _atr_series(high, low, close, ATR_PERIOD)
    if SIGNAL == 'close':
        entry, slope = close_slope_entry(close, ema, SLOPE_SPAN, 0.0)
        soc = shl = slope
    else:
        entry, _, _, soc, shl = mid_slope_entry(
            open_, high, low, close, ema, SLOPE_SPAN, 0.0,
        )
    times = [as_naive_ts(ts) for ts in df.index]
    return {
        'times': times,
        'by_ts': {ts: i for i, ts in enumerate(times)},
        'close': close,
        'low': low,
        'atr': atr,
        'entry': entry,
        'slope_oc': soc,
        'slope_hl': shl,
    }


def _equity(cash: float, qty: list[float], entry_price: list[float]) -> float:
    equity = cash
    for q, px in zip(qty, entry_price):
        if q > 0:
            equity += q * px
    return equity


def run_book(prepared: list[dict], timeline: list[pd.Timestamp]) -> dict:
    n_sym = len(prepared)
    cash = float(Config.INITIAL_STRATEGY_CASH)
    qty = [0.0] * n_sym
    entry_price = [0.0] * n_sym
    stop = [0.0] * n_sym
    resets = [SlopeReset() for _ in range(n_sym)]
    pnls: list[float] = []
    by_symbol: list[list[float]] = [[] for _ in range(n_sym)]

    for ts in timeline:
        # Exits first so freed cash can fund a later entry on this bar.
        for s, ser in enumerate(prepared):
            i = ser['by_ts'].get(ts)
            if i is None or qty[s] <= 0:
                continue
            s0 = float(stop[s])
            if ser['low'][i] <= s0:
                exit_px = s0
                pnl = (exit_px - entry_price[s]) * qty[s]
                cash += qty[s] * exit_px
                pnls.append(pnl)
                by_symbol[s].append(pnl)
                qty[s] = 0.0
                resets[s].on_exit()
                resets[s].observe(float(ser['slope_oc'][i]), float(ser['slope_hl'][i]))
                continue

            a = ser['atr'][i]
            trail_dist = float(TRAIL_ATR * a) if (a == a and a > 0) else 0.0
            s1 = trail_from_close(s0, float(ser['close'][i]), trail_dist)
            ambiguous = bool(trail_dist > 0 and s0 < float(ser['low'][i]) <= s1)
            finer = ser['finer']
            if ambiguous and finer is not None:
                hit, exit_or_final = resolve_ambiguous(
                    ts,
                    parent_bar_end(ts, '4h'),
                    s0,
                    trail_dist,
                    finer[0],
                    finer[1],
                    finer[2],
                )
                if hit:
                    exit_px = float(exit_or_final)
                    pnl = (exit_px - entry_price[s]) * qty[s]
                    cash += qty[s] * exit_px
                    pnls.append(pnl)
                    by_symbol[s].append(pnl)
                    qty[s] = 0.0
                    resets[s].on_exit()
                    resets[s].observe(float(ser['slope_oc'][i]), float(ser['slope_hl'][i]))
                    continue
                stop[s] = float(exit_or_final)
                continue
            stop[s] = float(s1)

        for s, ser in enumerate(prepared):
            i = ser['by_ts'].get(ts)
            if i is None or qty[s] > 0:
                continue
            resets[s].observe(float(ser['slope_oc'][i]), float(ser['slope_hl'][i]))
            if not resets[s].allows_entry():
                continue
            if not ser['entry'][i]:
                continue
            a = ser['atr'][i]
            if not (a == a) or a <= 0:
                continue
            price = float(ser['close'][i])
            stop0 = price - SL_ATR * float(a)
            equity = _equity(cash, qty, entry_price)
            q = grid._size_long(equity, cash, price, stop0, RISK_SETTINGS)
            if q <= 0:
                continue
            qty[s] = q
            entry_price[s] = price
            stop[s] = stop0
            cash -= q * price

    open_mtm = 0.0
    open_n = 0
    open_symbols = []
    for s, ser in enumerate(prepared):
        if qty[s] <= 0:
            continue
        last_i = None
        for ts in reversed(timeline):
            idx = ser['by_ts'].get(ts)
            if idx is not None:
                last_i = idx
                break
        if last_i is None:
            continue
        open_mtm += qty[s] * float(ser['close'][last_i])
        open_n += 1
        open_symbols.append(ser['symbol'])

    metrics = grid._metrics_from_pnls(pnls, cash, open_mtm, float(Config.INITIAL_STRATEGY_CASH))
    metrics['open_positions'] = open_n
    metrics['open_symbols'] = open_symbols
    metrics['by_symbol'] = by_symbol
    return metrics


def _sym_row(pnls: list[float]) -> tuple[float, int, float]:
    n = len(pnls)
    wr = (sum(1 for p in pnls if p > 0) / n * 100.0) if n else 0.0
    return sum(pnls), n, wr


def write_report(metrics: dict, symbols: list[str], skipped: list[str], drill_n: int, elapsed: float) -> None:
    rows = []
    for sym, pnls in zip(symbols, metrics['by_symbol']):
        pnl, n, wr = _sym_row(pnls)
        rows.append((sym, pnl, n, wr))
    rows.sort(key=lambda r: r[1], reverse=True)
    pf = metrics['profit_factor']
    pf_s = 'inf' if pf == float('inf') else f'{pf:.2f}'
    kind = 'close slope' if SIGNAL == 'close' else 'midpoint'
    source = (
        'docs/btc_close_slope_4h_6m.md'
        if SIGNAL == 'close'
        else 'docs/btc_mid_slope_4h_6m.md'
    )
    if SIGNAL == 'close':
        structure = (
            'Structure: slope of close is positive and close is above the trend EMA. '
            'After an exit, that symbol must see the close slope go negative and then positive '
            'before it can enter again.'
        )
    else:
        structure = (
            'Structure: HL midpoint crosses above OC midpoint, both slopes positive, close above trend EMA. '
            'After an exit, that symbol must see both slopes go negative and then positive before it can enter again.'
        )
    lines = [
        f'# Crypto book, 4h 6m {kind} (shared wallet)',
        '',
        f'Generated: {pd.Timestamp.now().isoformat(timespec="seconds")}',
        f'Source: `{source}` composite #1 '
        f'(n={SLOPE_SPAN}, trend={TREND_WINDOW}, ATR={ATR_PERIOD}, '
        f'SL={SL_ATR:g}, trail={TRAIL_ATR:g}).',
        f'Window: `{START}` .. `{END}` | Interval: `4h` | Symbols: {len(symbols)} | '
        f'Start cash: ${Config.INITIAL_STRATEGY_CASH:,.0f}',
        f'Elapsed: **{grid._fmt_duration(elapsed)}**',
        '',
        'One shared wallet. A new long is sized off cash plus open positions at entry cost, '
        'then capped by free cash. Symbols are not given their own $10k.',
        structure,
        'The later BTC dollar slope floor is not applied. A floor of 160 dollars per bar only fits BTC.',
        f'Risk: no TP1. SL = {SL_ATR:g} x ATR. Trail from the close = {TRAIL_ATR:g} x current ATR.',
        (
            f'Ambiguous trail bars resolved on 1h for **{drill_n}** of {len(symbols)} symbols.'
            if drill_n
            else '1h drill was unavailable, so ambiguous trail bars use the 4h wick check only.'
        ),
        '',
        '## Shared wallet',
        '',
        f'- Net PnL: **${metrics["net_pnl"]:+,.0f}**',
        f'- Equity: **${metrics["equity"]:,.0f}**',
        f'- WR: **{metrics["win_rate"]:.0f}%** | Trades: **{metrics["closed_trades"]}** | PF: **{pf_s}**',
        f'- Open positions: **{metrics["open_positions"]}** | Cash: **${metrics["cash"]:,.0f}**',
        (
            '- Still open: ' + ', '.join(metrics['open_symbols'])
            if metrics['open_symbols']
            else '- Still open: none'
        ),
        '',
        '## Contribution inside the shared wallet',
        '',
        'Closed-trade PnL only. These are not separate accounts.',
        '',
        '| Symbol | PnL | Trades | WR% |',
        '|---|---:|---:|---:|',
    ]
    for sym, pnl, n, wr in rows:
        lines.append(f'| {sym} | ${pnl:+,.0f} | {n} | {wr:.0f} |')
    if skipped:
        lines += ['', 'Skipped (no 4h bars in the window): ' + ', '.join(skipped)]
    lines.append('')
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines))
    print(f'Wrote {REPORT_PATH}')


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--signal', choices=('mid', 'close'), default='mid')
    args = parser.parse_args()
    _apply_signal(args.signal)

    need_from = START - timedelta(days=WARMUP_DAYS)
    prepared = []
    skipped = []
    t0 = time.perf_counter()
    for symbol in CRYPTO_PAIRS:
        df = load_interval(symbol, '4h', need_from, END)
        if df is None or df.empty:
            skipped.append(symbol)
            continue
        ser = _prep(df)
        in_window = any(need_from <= ts.date() <= END for ts in ser['times'])
        if not in_window:
            skipped.append(symbol)
            continue
        finer_df = load_interval(symbol, '1h', START, END)
        ser['finer'] = finer_arrays(finer_df)
        ser['symbol'] = symbol
        prepared.append(ser)
        print(f'{symbol} entry bars: {int(ser["entry"].sum())} drill={"yes" if ser["finer"] else "no"}')

    if not prepared:
        raise SystemExit('No crypto 4h data')

    timeline = sorted({
        ts
        for ser in prepared
        for ts in ser['times']
        if START <= ts.date() <= END
    })
    print(f'Shared book: {len(prepared)} symbols, {len(timeline)} 4h bars')
    metrics = run_book(prepared, timeline)
    elapsed = time.perf_counter() - t0
    symbols = [ser['symbol'] for ser in prepared]
    drill_n = sum(1 for ser in prepared if ser['finer'] is not None)
    write_report(metrics, symbols, skipped, drill_n, elapsed)
    print(
        f"Shared PnL ${metrics['net_pnl']:+,.0f} "
        f"WR {metrics['win_rate']:.0f}% trades {metrics['closed_trades']} "
        f"PF {metrics['profit_factor']:.2f} open {metrics['open_positions']}"
    )


if __name__ == '__main__':
    main()
