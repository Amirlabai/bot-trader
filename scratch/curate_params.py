"""
Offline long-only param curator (uses shared.path_sim only).

Modes:
  per_symbol (legacy): solo $10k path per coin, then refine.
  wallet (default for crypto intent): one shared $10k book, same six-pack on all
    symbols via simulate_long_portfolio; lock one algo for the whole market.

Usage:
  .\\.venv\\Scripts\\python.exe scratch\\curate_params.py --market crypto --mode wallet --start 2022-09-11
  .\\.venv\\Scripts\\python.exe scratch\\curate_params.py --market crypto --mode per_symbol --start 2022-09-11
  .\\.venv\\Scripts\\python.exe scratch\\curate_params.py --market commodities --start 2022-09-11
"""
from __future__ import annotations

import argparse
import itertools
import os
import sys
import time
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
os.chdir(REPO_ROOT)
for path in (REPO_ROOT, os.path.join(REPO_ROOT, 'src'), os.path.join(REPO_ROOT, 'scratch')):
    if path not in sys.path:
        sys.path.insert(0, path)

from config import (  # noqa: E402
    COMMODITY_PAIRS,
    CRYPTO_PAIRS,
    FOREX_PAIRS,
    RISK_SETTINGS,
    STOCKS_EQUITY_RISK_PCT,
    Config,
)
from data_ingestion import DataFetcher  # noqa: E402
from shared.curated_params import load_curated_params, save_curated_params  # noqa: E402
from shared.path_sim import (  # noqa: E402
    PathSimInvariantError,
    build_long_entry_mask,
    curator_score,
    ema_series,
    params_from_ratios,
    simulate_long_path,
    simulate_long_portfolio,
)
from shared.stocks_universe import STOCK_SIM_TICKERS  # noqa: E402
from shared.symbols import asset_type_for_symbol  # noqa: E402

FIXED_GATES = {
    'adx_min': 5.0,
    'atr_buffer': 0.0,
    'trail_arm_r': 1.0,
    'adx_period': 14,
    'vol_mult': 0.0,
    # Trail distance uses ATR frozen at entry (path_sim + live).
    'freeze_trail_atr': True,
}

MARKET_SPECS = {
    'crypto': {
        'asset_type': 'crypto',
        'pairs': None,  # filled at runtime from CRYPTO_PAIRS
        'benchmarks': ['BTC/USDT', 'ETH/USDT'],
        'short': list(range(10, 35, 5)),
        'slow_ratios': [1.5, 2.0, 2.5, 3.0, 3.5, 4.0],
        'trend_windows': [100, 150, 200],
        'atr_periods': [10, 14, 21],
        'sl_atrs': [1.5, 2.0, 2.5, 3.0, 3.5, 4.0],
        'trail_atrs': [2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0],
        'regime_symbol': None,
        'regime_ema': 0,
        'equity_risk_pct': 0.01,
        'years_default': 4.0,
        'target_trades_per_year': 20.0,
    },
    'commodities': {
        'asset_type': 'commodity',
        'pairs': None,
        'benchmarks': ['XAU/USD', 'CL/USD'],
        'short': list(range(10, 35, 5)),
        'slow_ratios': [1.5, 2.0, 2.5, 3.0, 3.5, 4.0],
        'trend_windows': [100, 150, 200],
        'atr_periods': [10, 14, 21],
        'sl_atrs': [1.5, 2.0, 2.5, 3.0, 3.5, 4.0],
        'trail_atrs': [2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0],
        'regime_symbol': None,
        'regime_ema': 0,
        'equity_risk_pct': 0.01,
        'years_default': 4.0,
        'target_trades_per_year': 8.0,
    },
    'forex': {
        'asset_type': 'forex',
        'pairs': None,
        'benchmarks': ['EUR/USD', 'USD/JPY'],
        'short': list(range(10, 35, 5)),
        'slow_ratios': [1.5, 2.0, 2.5, 3.0, 3.5, 4.0],
        'trend_windows': [100, 150, 200],
        'atr_periods': [10, 14, 21],
        'sl_atrs': [1.5, 2.0, 2.5, 3.0, 3.5, 4.0],
        'trail_atrs': [2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0],
        'regime_symbol': None,
        'regime_ema': 0,
        'equity_risk_pct': 0.01,
        'years_default': 4.0,
        'target_trades_per_year': 8.0,
    },
    'stocks': {
        'asset_type': 'stock',
        'pairs': None,
        'benchmarks': None,  # filled from STOCK_SIM_TICKERS[:3]
        'short': list(range(10, 35, 5)),
        'slow_ratios': [1.5, 2.0, 2.5, 3.0, 3.5, 4.0],
        'trend_windows': [100, 150, 200],
        'atr_periods': [10, 14, 21],
        'sl_atrs': [1.5, 2.0, 2.5, 3.0, 3.5, 4.0],
        'trail_atrs': [2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0],
        'regime_symbol': None,
        'regime_ema': 0,
        'equity_risk_pct': STOCKS_EQUITY_RISK_PCT,
        'years_default': 10.0,
        'target_trades_per_year': 12.0,
    },
}


def _risk_for(spec: dict) -> dict:
    return {
        **RISK_SETTINGS,
        'equity_risk_pct': float(spec['equity_risk_pct']),
    }


def _load_ohlcv(fetcher: DataFetcher, symbol: str, asset_type: str) -> pd.DataFrame:
    df = fetcher.get_data(symbol, asset_type=asset_type)
    if df is None or df.empty:
        return pd.DataFrame()
    return df


def _aligned_regime_ok(
    index: pd.DatetimeIndex,
    regime_df: pd.DataFrame | None,
    period: int,
) -> np.ndarray | None:
    if regime_df is None or regime_df.empty or period <= 0:
        return None
    r = regime_df.reindex(index)
    r_close = r['close'].ffill().to_numpy(dtype=float)
    ema = ema_series(r_close, period)
    ok = np.zeros(len(index), dtype=bool)
    for i in range(len(index)):
        if r_close[i] == r_close[i] and ema[i] == ema[i]:
            ok[i] = float(r_close[i]) > float(ema[i])
    return ok


def _eval_params_on_df(
    df: pd.DataFrame,
    params: dict,
    risk: dict,
    *,
    start: date,
    regime_ok: np.ndarray | None,
    trail_arm_r: float,
) -> dict | None:
    if df.empty:
        return None
    idx = df.index
    start_ts = pd.Timestamp(start)
    start_i = int(idx.searchsorted(start_ts))
    if start_i >= len(df) - 5:
        return None
    close = df['close'].to_numpy(dtype=float)
    high = df['high'].to_numpy(dtype=float)
    low = df['low'].to_numpy(dtype=float)
    entry, atr = build_long_entry_mask(
        close, high, low,
        short_window=int(params['short_window']),
        long_window=int(params['long_window']),
        trend_window=int(params['trend_window']),
        atr_period=int(params['atr_period']),
        adx_min=float(FIXED_GATES['adx_min']),
        atr_buffer=float(FIXED_GATES['atr_buffer']),
        adx_period=int(FIXED_GATES['adx_period']),
        regime_ok=regime_ok,
    )
    try:
        return simulate_long_path(
            entry, close, low, atr,
            sl_atr=float(params['sl_atr']),
            trail_atr=float(params['trail_atr']),
            start_idx=start_i,
            start_cash=float(Config.INITIAL_STRATEGY_CASH),
            risk_settings=risk,
            trail_arm_r=float(trail_arm_r),
            assert_invariants=True,
        )
    except PathSimInvariantError as e:
        print(f'  INVARIANT FAIL: {e}')
        return None


def _coarse_grid(spec: dict) -> list[dict]:
    out = []
    for short, ratio, trend, atr_p, sl, trail in itertools.product(
        spec['short'],
        spec['slow_ratios'],
        spec['trend_windows'],
        spec['atr_periods'],
        spec['sl_atrs'],
        spec['trail_atrs'],
    ):
        p = params_from_ratios(
            short, ratio, trend_window=trend,
            atr_period=atr_p, sl_atr=sl, trail_atr=trail,
        )
        if p:
            out.append(p)
    return out


def _refine_neighbors(centroid: dict, *, crypto_bias: bool) -> list[dict]:
    """Local neighborhood around centroid (±10% EMA, ±0.5 ATR multiples)."""
    sw = int(centroid['short_window'])
    lw = int(centroid['long_window'])
    tw = int(centroid['trend_window'])
    ap = int(centroid['atr_period'])
    sl = float(centroid['sl_atr'])
    tr = float(centroid['trail_atr'])

    short_opts = sorted({max(5, int(round(sw * f))) for f in (0.9, 1.0, 1.1)})
    if crypto_bias:
        short_opts = sorted(set(short_opts) | {max(5, sw - 5), sw})
    long_opts = sorted({max(sw + 1, int(round(lw * f))) for f in (0.9, 1.0, 1.1)})
    trend_opts = sorted({max(lw, int(round(tw * f))) for f in (0.9, 1.0, 1.1)})
    sl_opts = sorted({round(x, 1) for x in (sl - 0.5, sl, sl + 0.5) if x > 0})
    trail_opts = sorted({round(x, 1) for x in (tr - 0.5, tr, tr + 0.5) if x > 0})
    if crypto_bias:
        trail_opts = sorted(set(trail_opts) | {round(tr + 1.0, 1)})

    out = []
    for s, l, t, sla, tra in itertools.product(short_opts, long_opts, trend_opts, sl_opts, trail_opts):
        if l <= s or t < l:
            continue
        if tra < 0.75 * sla - 1e-12:
            continue
        out.append({
            'short_window': s,
            'long_window': l,
            'trend_window': t,
            'atr_period': ap,
            'sl_atr': float(sla),
            'trail_atr': float(tra),
        })
    # de-dupe
    seen = set()
    uniq = []
    for p in out:
        key = tuple(p[k] for k in (
            'short_window', 'long_window', 'trend_window', 'atr_period', 'sl_atr', 'trail_atr',
        ))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


def _score_row(result: dict, years: float, target_tpy: float) -> float:
    return curator_score(result, target_trades_per_year=target_tpy, years=years)


def _best_on_frames(
    frames: dict[str, pd.DataFrame],
    candidates: list[dict],
    risk: dict,
    start: date,
    regime_maps: dict[str, np.ndarray | None],
    years: float,
    target_tpy: float,
    trail_arm_r: float,
) -> tuple[dict | None, dict | None, float]:
    """Return (best_params, best_metrics, best_score) maximizing mean score across frames."""
    best_p = None
    best_m = None
    best_s = -1e18
    for p in candidates:
        scores = []
        metrics = []
        ok = True
        total_trades = 0
        for sym, df in frames.items():
            m = _eval_params_on_df(
                df, p, risk, start=start,
                regime_ok=regime_maps.get(sym),
                trail_arm_r=trail_arm_r,
            )
            if m is None:
                ok = False
                break
            scores.append(_score_row(m, years, target_tpy))
            metrics.append(m)
            total_trades += int(m.get('closed_trades') or 0)
        if not ok or not scores:
            continue
        # Prefer sets that actually traded
        s = float(np.mean(scores))
        if total_trades <= 0:
            s -= 100.0
        if s > best_s:
            best_s = s
            best_p = p
            best_m = {
                'mean_score': round(s, 4),
                'per_symbol': {sym: metrics[i] for i, sym in enumerate(frames.keys())},
            }
    return best_p, best_m, best_s


def _build_wallet_series(
    frames: dict[str, pd.DataFrame],
    params: dict,
    calendar: pd.DatetimeIndex,
    *,
    start: date,
) -> list[dict]:
    """Aligned multi-symbol series with the same six-pack on every coin."""
    series = []
    start_ts = pd.Timestamp(start)
    for sym, df in frames.items():
        native = df[df.index >= start_ts] if len(df) else df
        if native.empty or len(native) < 50:
            continue
        close = native['close'].to_numpy(dtype=float)
        high = native['high'].to_numpy(dtype=float)
        low = native['low'].to_numpy(dtype=float)
        entry, atr = build_long_entry_mask(
            close, high, low,
            short_window=int(params['short_window']),
            long_window=int(params['long_window']),
            trend_window=int(params['trend_window']),
            atr_period=int(params['atr_period']),
            adx_min=float(FIXED_GATES['adx_min']),
            atr_buffer=float(FIXED_GATES['atr_buffer']),
            adx_period=int(FIXED_GATES['adx_period']),
            regime_ok=None,
        )
        pack = pd.DataFrame(
            {
                'close': close,
                'low': low,
                'atr': atr,
                'entry': entry.astype(float),
                'has': 1.0,
            },
            index=native.index,
        )
        al = pack.reindex(calendar)
        has = al['has'].fillna(0.0).to_numpy(dtype=bool)
        ent = (al['entry'].fillna(0.0).to_numpy(dtype=float) > 0.5) & has
        series.append({
            'symbol': sym,
            'close': al['close'].ffill().to_numpy(dtype=float),
            'low': al['low'].ffill().to_numpy(dtype=float),
            'atr': al['atr'].ffill().to_numpy(dtype=float),
            'entry': ent,
            'has_bar': has,
            'sl_atr': float(params['sl_atr']),
            'trail_atr': float(params['trail_atr']),
        })
    return series


def _eval_wallet_params(
    frames: dict[str, pd.DataFrame],
    params: dict,
    risk: dict,
    *,
    start: date,
    calendar: pd.DatetimeIndex,
    trail_arm_r: float,
) -> dict | None:
    series = _build_wallet_series(frames, params, calendar, start=start)
    if len(series) < 2:
        return None
    try:
        return simulate_long_portfolio(
            series,
            sl_atr=float(params['sl_atr']),
            trail_atr=float(params['trail_atr']),
            start_cash=float(Config.INITIAL_STRATEGY_CASH),
            risk_settings=risk,
            trail_arm_r=float(trail_arm_r),
            assert_invariants=True,
        )
    except PathSimInvariantError as e:
        print(f'  INVARIANT FAIL: {e}')
        return None


def _best_on_wallet(
    frames: dict[str, pd.DataFrame],
    candidates: list[dict],
    risk: dict,
    start: date,
    calendar: pd.DatetimeIndex,
    years: float,
    target_tpy: float,
    trail_arm_r: float,
) -> tuple[dict | None, dict | None, float]:
    best_p = None
    best_m = None
    best_s = -1e18
    n = len(candidates)
    for i, p in enumerate(candidates, 1):
        if i == 1 or i % 200 == 0 or i == n:
            print(f'  wallet search {i}/{n}...')
        m = _eval_wallet_params(
            frames, p, risk, start=start, calendar=calendar, trail_arm_r=trail_arm_r,
        )
        if m is None:
            continue
        trades = int(m.get('closed_trades') or 0)
        s = _score_row(m, years, target_tpy)
        if trades <= 0:
            s -= 100.0
        if s > best_s:
            best_s = s
            best_p = p
            best_m = m
            print(
                f'    new best score={s:.3f} pnl={m.get("net_pnl")} '
                f'PF={m.get("profit_factor")} trades={trades} '
                f'{p["short_window"]}/{p["long_window"]}/{p["trend_window"]} '
                f'ATR{p["atr_period"]} SL{p["sl_atr"]} trail{p["trail_atr"]}'
            )
    return best_p, best_m, best_s


def _write_report(path: str, market: str, start: date, end: date, template: dict, symbols: dict, elapsed: float):
    lines = [
        f'# {market.title()} curated EMA params',
        '',
        f'Generated: {datetime.utcnow().isoformat(timespec="seconds")}',
        f'Window: `{start}` .. `{end}` | Elapsed: **{elapsed:.1f}s**',
        '',
        'Long-only path sim (`shared.path_sim`) with risk invariants '
        '(≤ equity risk at SL fill, max notional, cash, fill-at-SL). '
        'Trail distance uses **ATR frozen at entry**.',
        '',
        '## Template centroid',
        '',
        f'```json',
        f'{template}',
        f'```',
        '',
        '## Per-symbol winners',
        '',
        '| Symbol | Score | PnL | PF | Trades | Params |',
        '|---|---:|---:|---:|---:|---|',
    ]
    for sym, block in sorted(symbols.items()):
        m = block.get('metrics') or {}
        p = block.get('params') or {}
        pf = m.get('profit_factor')
        if pf is None:
            pf_s = '-'
        elif pf == float('inf') or (isinstance(pf, float) and pf != pf):  # inf or nan
            pf_s = '∞'
        else:
            try:
                pf_s = f'{float(pf):.2f}'
            except (TypeError, ValueError):
                pf_s = '-'
        pnl = m.get('net_pnl')
        pnl_s = f'${pnl:,.0f}' if isinstance(pnl, (int, float)) else '-'
        trades = m.get('closed_trades')
        trades_s = trades if trades is not None else '-'
        lines.append(
            f"| {sym} | {block.get('score', 0):.3f} | {pnl_s} | "
            f"{pf_s} | {trades_s} | "
            f"`{p.get('short_window')}/{p.get('long_window')}/{p.get('trend_window')} · "
            f"ATR{p.get('atr_period')} · SL{p.get('sl_atr')} · trail{p.get('trail_atr')}` |"
        )
    lines.append('')
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f'Wrote {path}')


def run_market(market: str, start: date, end: date | None, limit_symbols: int | None = None):
    spec = dict(MARKET_SPECS[market])
    if market == 'crypto':
        pairs = list(CRYPTO_PAIRS)
    elif market == 'commodities':
        pairs = list(COMMODITY_PAIRS)
    elif market == 'forex':
        pairs = list(FOREX_PAIRS)
    else:
        pairs = list(STOCK_SIM_TICKERS)
        spec['benchmarks'] = list(STOCK_SIM_TICKERS[:3])

    if limit_symbols:
        pairs = pairs[: int(limit_symbols)]

    risk = _risk_for(spec)
    trail_arm_r = float(FIXED_GATES['trail_arm_r'])
    years = float(spec['years_default'])
    target_tpy = float(spec['target_trades_per_year'])
    fetcher = DataFetcher(Config)
    asset_type = spec['asset_type']

    print(f'=== Curate {market} | start={start} | pairs={len(pairs)} ===')
    t0 = time.time()

    # Load OHLCV
    frames: dict[str, pd.DataFrame] = {}
    for sym in pairs:
        df = _load_ohlcv(fetcher, sym, asset_type_for_symbol(sym) if market != 'stocks' else 'stock')
        if df.empty:
            print(f'  skip {sym}: no data')
            continue
        if end:
            df = df[df.index <= pd.Timestamp(end)]
        frames[sym] = df
    if not frames:
        raise SystemExit(f'No OHLCV for market {market}')

    # Regime series
    regime_df = None
    if spec.get('regime_symbol'):
        rsym = spec['regime_symbol']
        rtype = 'crypto' if market == 'crypto' else 'stock'
        regime_df = _load_ohlcv(fetcher, rsym, rtype)

    regime_maps: dict[str, np.ndarray | None] = {}
    for sym, df in frames.items():
        regime_maps[sym] = _aligned_regime_ok(df.index, regime_df, int(spec.get('regime_ema') or 0))

    # Phase template on benchmarks
    benches = [b for b in (spec['benchmarks'] or []) if b in frames]
    if not benches:
        benches = list(frames.keys())[:2]
    bench_frames = {b: frames[b] for b in benches}
    bench_regime = {b: regime_maps[b] for b in benches}
    candidates = _coarse_grid(spec)
    print(f'Template phase: {len(candidates)} candidates on {benches}')
    centroid, centroid_metrics, centroid_score = _best_on_frames(
        bench_frames, candidates, risk, start, bench_regime, years, target_tpy, trail_arm_r,
    )
    if not centroid:
        raise SystemExit('No valid template centroid (all candidates failed)')
    print(f'Template centroid score={centroid_score:.4f} params={centroid}')

    # Phase refine per symbol
    crypto_bias = market == 'crypto'
    symbol_winners: dict[str, Any] = {}
    for sym, df in frames.items():
        neighbors = _refine_neighbors(centroid, crypto_bias=crypto_bias)
        # Always include centroid
        neighbors = [centroid] + [p for p in neighbors if p != centroid]
        best_p, best_m, best_s = _best_on_frames(
            {sym: df}, neighbors, risk, start, {sym: regime_maps[sym]},
            years, target_tpy, trail_arm_r,
        )
        if not best_p:
            print(f'  {sym}: REJECT (no valid refine)')
            continue
        # Peer consistency: require positive PF on at least this symbol
        m = (best_m or {}).get('per_symbol', {}).get(sym) or {}
        pf = m.get('profit_factor') or 0.0
        trades = int(m.get('closed_trades') or 0)
        if trades <= 0:
            # Fall back to template centroid for this symbol
            best_p = dict(centroid)
            m = ((centroid_metrics or {}).get('per_symbol') or {}).get(sym) or {
                'net_pnl': 0,
                'profit_factor': 0.0,
                'payoff': 0.0,
                'calmar': 0.0,
                'closed_trades': 0,
                'win_rate': 0.0,
            }
            best_s = centroid_score
            print(f'  {sym}: using template centroid (no refine trades)')
        elif pf != float('inf') and float(pf) <= 0:
            print(f'  {sym}: REJECT (PF={pf})')
            continue
        params = {**best_p, **FIXED_GATES}
        symbol_winners[sym] = {
            'market': market,
            'params': params,
            'score': round(best_s, 4),
            'metrics': {
                'net_pnl': m.get('net_pnl'),
                'profit_factor': m.get('profit_factor'),
                'payoff': m.get('payoff'),
                'calmar': m.get('calmar'),
                'closed_trades': m.get('closed_trades'),
                'win_rate': m.get('win_rate'),
            },
        }
        print(f'  {sym}: score={best_s:.3f} {params["short_window"]}/{params["long_window"]}/{params["trend_window"]}')

    elapsed = time.time() - t0
    curated = load_curated_params()
    curated.setdefault('templates', {})
    curated.setdefault('symbols', {})
    curated['templates'][market] = {
        'params': {**centroid, **FIXED_GATES},
        'score': round(centroid_score, 4),
        'benchmarks': benches,
        'metrics': centroid_metrics,
    }
    for sym, block in symbol_winners.items():
        curated['symbols'][sym] = block
    curated['version'] = 1
    curated['updated_at'] = datetime.utcnow().isoformat(timespec='seconds')
    out_path = save_curated_params(curated)
    print(f'Locked {out_path} ({len(symbol_winners)} symbols)')

    end_d = end or date.today()
    report = os.path.join(REPO_ROOT, 'docs', f'{market}_curated_{start.isoformat()}.md')
    _write_report(
        report, market, start, end_d,
        curated['templates'][market]['params'],
        symbol_winners,
        elapsed,
    )
    fetcher.report_fetch_alerts()


def run_market_wallet(market: str, start: date, end: date | None, limit_symbols: int | None = None):
    """One shared $10k wallet; same six-pack on every symbol; lock that algo."""
    spec = dict(MARKET_SPECS[market])
    if market == 'crypto':
        pairs = list(CRYPTO_PAIRS)
    elif market == 'commodities':
        pairs = list(COMMODITY_PAIRS)
    elif market == 'forex':
        pairs = list(FOREX_PAIRS)
    else:
        pairs = list(STOCK_SIM_TICKERS)
    if limit_symbols:
        pairs = pairs[: int(limit_symbols)]

    risk = _risk_for(spec)
    years = float(spec['years_default'])
    target_tpy = float(spec['target_trades_per_year'])
    trail_arm_r = float(FIXED_GATES['trail_arm_r'])
    fetcher = DataFetcher(Config)

    print(f'=== Curate WALLET {market} | start={start} | pairs={len(pairs)} | cash=${Config.INITIAL_STRATEGY_CASH:g} ===')
    t0 = time.time()

    frames: dict[str, pd.DataFrame] = {}
    for sym in pairs:
        df = _load_ohlcv(fetcher, sym, asset_type_for_symbol(sym) if market != 'stocks' else 'stock')
        if df.empty:
            print(f'  skip {sym}: no data')
            continue
        if end:
            df = df[df.index <= pd.Timestamp(end)]
        frames[sym] = df
    if len(frames) < 2:
        raise SystemExit(f'Need >=2 symbols for wallet curate, got {len(frames)}')

    end_d = end or date.today()
    calendar = pd.DatetimeIndex(sorted({ts for df in frames.values() for ts in df.index}))
    calendar = calendar[(calendar >= pd.Timestamp(start)) & (calendar <= pd.Timestamp(end_d))]
    if len(calendar) < 50:
        raise SystemExit('Calendar too short')

    candidates = _coarse_grid(spec)
    print(f'Wallet coarse search: {len(candidates)} candidates on {list(frames.keys())}')
    best_p, best_m, best_s = _best_on_wallet(
        frames, candidates, risk, start, calendar, years, target_tpy, trail_arm_r,
    )
    if not best_p:
        raise SystemExit('No valid wallet candidate')
    print(f'Coarse winner score={best_s:.4f} params={best_p}')

    neighbors = _refine_neighbors(best_p, crypto_bias=(market == 'crypto'))
    neighbors = [best_p] + [p for p in neighbors if p != best_p]
    print(f'Wallet refine: {len(neighbors)} neighbors')
    ref_p, ref_m, ref_s = _best_on_wallet(
        frames, neighbors, risk, start, calendar, years, target_tpy, trail_arm_r,
    )
    if ref_p and ref_s >= best_s:
        best_p, best_m, best_s = ref_p, ref_m, ref_s
    print(f'Locked wallet algo score={best_s:.4f} params={best_p}')

    params = {**best_p, **FIXED_GATES}
    metrics = {
        'net_pnl': (best_m or {}).get('net_pnl'),
        'profit_factor': (best_m or {}).get('profit_factor'),
        'payoff': (best_m or {}).get('payoff'),
        'calmar': (best_m or {}).get('calmar'),
        'closed_trades': (best_m or {}).get('closed_trades'),
        'win_rate': (best_m or {}).get('win_rate'),
        'equity': (best_m or {}).get('equity'),
        'mode': 'wallet',
    }

    # Stamp every book symbol with the same algo (no per-coin overlays).
    symbol_winners: dict[str, Any] = {}
    for sym in frames:
        symbol_winners[sym] = {
            'market': market,
            'params': dict(params),
            'score': round(best_s, 4),
            'metrics': dict(metrics),
        }

    elapsed = time.time() - t0
    curated = load_curated_params()
    curated.setdefault('templates', {})
    curated.setdefault('symbols', {})
    curated['templates'][market] = {
        'params': dict(params),
        'score': round(best_s, 4),
        'benchmarks': list(frames.keys()),
        'metrics': metrics,
        'mode': 'wallet',
    }
    # Drop prior per-symbol divergences for this market, then write identical locks.
    drop = [
        s for s, block in (curated.get('symbols') or {}).items()
        if (block or {}).get('market') == market
    ]
    for s in drop:
        del curated['symbols'][s]
    for sym, block in symbol_winners.items():
        curated['symbols'][sym] = block
    curated['version'] = 1
    curated['updated_at'] = datetime.utcnow().isoformat(timespec='seconds')
    out_path = save_curated_params(curated)
    print(f'Locked {out_path} (wallet mode, {len(symbol_winners)} symbols, one algo)')

    report = os.path.join(REPO_ROOT, 'docs', f'{market}_curated_{start.isoformat()}.md')
    _write_wallet_report(report, market, start, end_d, params, metrics, list(frames.keys()), elapsed)
    fetcher.report_fetch_alerts()


def _write_wallet_report(
    path: str,
    market: str,
    start: date,
    end: date,
    params: dict,
    metrics: dict,
    symbols: list[str],
    elapsed: float,
):
    pf = metrics.get('profit_factor')
    if pf is None:
        pf_s = '-'
    elif pf == float('inf') or (isinstance(pf, float) and pf != pf):
        pf_s = '∞'
    else:
        try:
            pf_s = f'{float(pf):.2f}'
        except (TypeError, ValueError):
            pf_s = '-'
    pnl = metrics.get('net_pnl')
    pnl_s = f'${pnl:,.0f}' if isinstance(pnl, (int, float)) else '-'
    eq = metrics.get('equity')
    eq_s = f'${eq:,.0f}' if isinstance(eq, (int, float)) else '-'
    lines = [
        f'# {market.title()} curated EMA params (wallet mode)',
        '',
        f'Generated: {datetime.utcnow().isoformat(timespec="seconds")}',
        f'Window: `{start}` .. `{end}` | Elapsed: **{elapsed:.1f}s**',
        '',
        'Shared-cash long-only wallet sim (`simulate_long_portfolio`): '
        '**one $10k book**, **same six-pack on every symbol**. '
        'Trail ATR frozen at entry. No per-coin param overlays.',
        '',
        '## Locked wallet algo',
        '',
        '```json',
        f'{params}',
        '```',
        '',
        f'- Final equity: **{eq_s}**',
        f'- Net P/L: **{pnl_s}**',
        f'- PF: **{pf_s}**',
        f'- Trades: **{metrics.get("closed_trades", "-")}**',
        f'- WR%: **{metrics.get("win_rate", "-")}**',
        '',
        '## Symbols (identical params)',
        '',
        ', '.join(f'`{s}`' for s in symbols),
        '',
    ]
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f'Wrote {path}')


def main():
    parser = argparse.ArgumentParser(description='Offline long-only param curator')
    parser.add_argument('--market', required=True, choices=list(MARKET_SPECS.keys()))
    parser.add_argument(
        '--mode',
        choices=('wallet', 'per_symbol'),
        default='wallet',
        help='wallet=shared $10k one algo (default); per_symbol=solo $10k each',
    )
    parser.add_argument('--start', type=lambda s: date.fromisoformat(s), default=None)
    parser.add_argument('--end', type=lambda s: date.fromisoformat(s), default=None)
    parser.add_argument('--limit-symbols', type=int, default=None)
    args = parser.parse_args()
    spec = MARKET_SPECS[args.market]
    start = args.start
    if start is None:
        years = float(spec['years_default'])
        start = date.today() - timedelta(days=int(365.25 * years))
    if args.mode == 'wallet':
        run_market_wallet(args.market, start, args.end, args.limit_symbols)
    else:
        run_market(args.market, start, args.end, args.limit_symbols)


if __name__ == '__main__':
    main()
