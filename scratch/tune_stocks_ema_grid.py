"""
Stocks EMA/ATR tuner (separate from scratch/tune_btc_ema_grid.py).

Defaults:
  - Shared-cash sim set: STOCK_SIM_TICKERS
  - Equity risk: 7%
  - ATR period: 20 (fixed unless --atr-periods)
  - SL / trail: 1..29 step 1 (same span as tune_btc_ema_grid STOCKS_SL/TRAIL)
  - Two-phase: --phase atr (fix EMA, search SL/trail) then --phase ema (fix risk, search EMA)

Usage:
  .\\.venv\\Scripts\\python.exe scratch\\tune_stocks_ema_grid.py --phase atr --start 2016-09-14
  .\\.venv\\Scripts\\python.exe scratch\\tune_stocks_ema_grid.py --phase ema --fix-risk 20,3,11 --start 2016-09-14
  .\\.venv\\Scripts\\python.exe scratch\\tune_stocks_ema_grid.py --phase atr --fix-ema 20,45,150 --start 2016-09-14
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
os.chdir(REPO_ROOT)
for path in (REPO_ROOT, os.path.join(REPO_ROOT, 'src'), os.path.join(REPO_ROOT, 'scratch')):
    if path not in sys.path:
        sys.path.insert(0, path)

import tune_btc_ema_grid as grid
from config import Config
from data_ingestion import DataFetcher
from shared.stocks_universe import STOCK_SIM_TICKERS

# Keep SL/trail span aligned with tune_btc_ema_grid.py lines 63-64.
SL_ATRS = [float(x) for x in range(1, 30, 1)]
TRAIL_ATRS = [float(x) for x in range(1, 30, 1)]
ATR_PERIODS = [20]
EQUITY_RISK_PCT = 0.07
DEFAULT_FIX_EMA = (20, 45, 150)


def _apply_stocks_globals(
    *,
    atr_periods: list[int],
    sl_atrs: list[float],
    trail_atrs: list[float],
    fast: list[int] | None = None,
    slow: list[int] | None = None,
    trend: list[int] | None = None,
) -> None:
    grid.ATR_PERIODS = list(atr_periods)
    grid.SL_ATRS = list(sl_atrs)
    grid.TRAIL_ATRS = list(trail_atrs)
    if fast is not None:
        grid.FAST_WINDOWS = list(fast)
    if slow is not None:
        grid.SLOW_WINDOWS = list(slow)
    if trend is not None:
        grid.TREND_WINDOWS = list(trend)
    # Runtime lookup inside simulate_* uses this module global.
    grid.RISK_SETTINGS = {
        **grid.RISK_SETTINGS,
        'equity_risk_pct': EQUITY_RISK_PCT,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='Stocks EMA/ATR grid (7% risk, ATR20)')
    parser.add_argument('--start', default=None, help='ISO start (default ~10y before last bar)')
    parser.add_argument('--end', default=None)
    parser.add_argument('--min-trades', type=int, default=3)
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--label', default=None)
    parser.add_argument('--report', default=None)
    parser.add_argument(
        '--phase',
        choices=('atr', 'ema', 'full'),
        default='atr',
        help='atr: fix EMA search SL/trail; ema: fix risk search EMA; full: both free',
    )
    parser.add_argument(
        '--fix-ema',
        default=None,
        help='FAST,SLOW,TREND (default for --phase atr: 20,45,150)',
    )
    parser.add_argument(
        '--fix-risk',
        default=None,
        help='ATR,SL,TRAIL required for --phase ema unless omitted after atr pass',
    )
    parser.add_argument(
        '--atr-periods',
        default='20',
        help='Comma list of ATR periods (default: 20)',
    )
    args = parser.parse_args()

    atr_periods = [int(x.strip()) for x in args.atr_periods.split(',') if x.strip()]
    if not atr_periods:
        atr_periods = list(ATR_PERIODS)

    fix_ema = grid._parse_fix_ema(args.fix_ema) if args.fix_ema else None
    fix_risk = grid._parse_fix_risk(args.fix_risk) if args.fix_risk else None

    if args.phase == 'atr':
        if fix_ema is None:
            fix_ema = DEFAULT_FIX_EMA
        _apply_stocks_globals(
            atr_periods=atr_periods,
            sl_atrs=SL_ATRS,
            trail_atrs=TRAIL_ATRS,
            fast=[fix_ema[0]],
            slow=[fix_ema[1]],
            trend=[fix_ema[2]],
        )
        print(
            f'Phase atr | risk={EQUITY_RISK_PCT:.0%} | EMA fixed '
            f'{fix_ema[0]}/{fix_ema[1]}/{fix_ema[2]} | '
            f'atr={atr_periods} SL={SL_ATRS[0]:g}..{SL_ATRS[-1]:g} '
            f'trail={TRAIL_ATRS[0]:g}..{TRAIL_ATRS[-1]:g}'
        )
    elif args.phase == 'ema':
        if fix_risk is None:
            raise SystemExit('--phase ema requires --fix-risk ATR,SL,TRAIL')
        atr_p, sl, trail = fix_risk
        _apply_stocks_globals(
            atr_periods=[atr_p],
            sl_atrs=[sl],
            trail_atrs=[trail],
            # restore default EMA grid from module defaults
            fast=[10, 15, 20],
            slow=list(range(20, 55, 5)),
            trend=[100, 150, 200],
        )
        print(
            f'Phase ema | risk={EQUITY_RISK_PCT:.0%} | risk fixed '
            f'atr={atr_p} SL={sl:g} trail={trail:g}'
        )
    else:
        _apply_stocks_globals(
            atr_periods=atr_periods,
            sl_atrs=SL_ATRS,
            trail_atrs=TRAIL_ATRS,
            fast=[10, 15, 20],
            slow=list(range(20, 55, 5)),
            trend=[100, 150, 200],
        )
        if fix_ema:
            _apply_stocks_globals(
                atr_periods=grid.ATR_PERIODS,
                sl_atrs=grid.SL_ATRS,
                trail_atrs=grid.TRAIL_ATRS,
                fast=[fix_ema[0]],
                slow=[fix_ema[1]],
                trend=[fix_ema[2]],
            )
        if fix_risk:
            atr_p, sl, trail = fix_risk
            _apply_stocks_globals(
                atr_periods=[atr_p],
                sl_atrs=[sl],
                trail_atrs=[trail],
            )
        print(f'Phase full | risk={EQUITY_RISK_PCT:.0%}')

    fetcher = DataFetcher(Config)
    print(f'Loading {len(STOCK_SIM_TICKERS)} stocks...')
    market: dict = {}
    for sym in STOCK_SIM_TICKERS:
        df = fetcher.get_data(sym, asset_type='stock')
        if df is None or df.empty:
            print(f'  skip {sym}: no data')
            continue
        market[sym] = df
        print(f'  {sym}: {len(df)} bars')
    fetcher.report_fetch_alerts()
    if not market:
        raise SystemExit('No stocks market data')

    last_bar = max(df.index[-1].date() for df in market.values())
    end = date.fromisoformat(args.end) if args.end else last_bar
    end = min(end, last_bar)
    if args.start:
        start = date.fromisoformat(args.start)
    else:
        start = end - timedelta(days=3652)  # ~10y

    span_days = (end - start).days
    if args.label:
        label = args.label
    elif args.phase == 'atr':
        label = '10y atr' if span_days >= 3000 else f'{span_days}d atr'
    elif args.phase == 'ema':
        label = '10y ema' if span_days >= 3000 else f'{span_days}d ema'
    else:
        label = '10y pass' if span_days >= 3000 else f'{span_days}d pass'

    if args.report:
        report_path = args.report
    elif args.phase == 'atr':
        report_path = os.path.join(REPO_ROOT, 'docs', 'stocks_ema_grid_10y_atr.md')
    elif args.phase == 'ema':
        report_path = os.path.join(REPO_ROOT, 'docs', 'stocks_ema_grid_10y_ema.md')
    else:
        report_path = os.path.join(REPO_ROOT, 'docs', 'stocks_ema_grid_10y.md')

    n_full = (
        len(grid._ema_pairs())
        * len(grid.TREND_WINDOWS)
        * len(grid.ATR_PERIODS)
        * len(grid.SL_ATRS)
        * len(grid.TRAIL_ATRS)
    )
    print(f'Configs: {n_full if args.limit is None else min(args.limit, n_full)} (full={n_full})')

    results, elapsed = grid.run_grid_multi(market, start, end, limit=args.limit)
    rate = len(results) / elapsed if elapsed > 0 else 0
    print(f'\nTimed {len(results)} configs in {grid._fmt_duration(elapsed)} ({rate:.1f}/s)')

    ranked = grid.attach_composite_scores(results)
    eligible = grid.write_report(
        ranked,
        start,
        end,
        args.min_trades,
        elapsed,
        len(results),
        report_path,
        label,
        symbols=list(market.keys()),
        book_title=f'Stocks ({EQUITY_RISK_PCT:.0%} risk)',
    )

    print(f'\n=== Top {grid.REPORT_TOP_N} (eligible) ===')
    for i, r in enumerate(eligible[:grid.REPORT_TOP_N], 1):
        p = r['params']
        print(
            f"{i:2d}. PnL=${r['net_pnl']:+7.0f}  WR={r['win_rate']:5.1f}%  n={r['closed_trades']:2d}  "
            f"fast={p['short_window']} slow={p['long_window']} trend={p['trend_window']} "
            f"atr={p['atr_period']} SL={p['sl_atr']:g} trail={p['trail_atr']:g}"
        )
    if not eligible:
        print('(none with min trades)')
    print(f'\nReport: {report_path}')
    print(f'Risk used: equity_risk_pct={EQUITY_RISK_PCT:.0%}')


if __name__ == '__main__':
    main()
