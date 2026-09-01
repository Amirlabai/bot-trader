"""
Replay trading from a start date through the latest closed daily bar.

Builds a fresh ledger using scratch/resim_engine.py (mirrors main.py; does not import main).
Default start: 2026-01-01. Output: data/ledger_resim.json (use --replace-ledger to overwrite ledger.json).
"""
import argparse
import json
import os
import shutil
import sys
from datetime import date, datetime
from typing import Optional

import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
os.chdir(REPO_ROOT)
for path in (REPO_ROOT, os.path.join(REPO_ROOT, 'src'), os.path.join(REPO_ROOT, 'scratch')):
    if path not in sys.path:
        sys.path.insert(0, path)

from config import Config, TRADING_CONFIG
from data_ingestion import DataFetcher
from ledger_manager import LedgerManager
from resim_engine import asset_type_for_symbol, load_strategy, process_symbol

DEFAULT_START = date(2026, 1, 1)


def _empty_ledger():
    return {
        'strategies': {
            strategy_id: {
                'cash': Config.INITIAL_STRATEGY_CASH,
                'positions': {},
                'history': [],
            }
            for strategy_id in TRADING_CONFIG
        }
    }


def _prefetch_market_data(data_fetcher, pairs_by_strategy):
    """symbol -> full OHLCV DataFrame"""
    cache = {}
    symbols = set()
    for pairs in pairs_by_strategy.values():
        symbols.update(pairs)
    for symbol in sorted(symbols):
        asset_type = asset_type_for_symbol(symbol)
        df = data_fetcher.get_data(symbol, asset_type=asset_type)
        if df.empty:
            print(f"  No data for {symbol}")
            continue
        cache[symbol] = df
        print(f"  Loaded {symbol}: {len(df)} bars ({df.index[0].date()} .. {df.index[-1].date()})")
    return cache


def _trading_days(market_cache, start: date, end: date):
    days = set()
    for df in market_cache.values():
        for ts in df.index:
            d = ts.date() if hasattr(ts, 'date') else pd.Timestamp(ts).date()
            if start <= d <= end:
                days.add(d)
    return sorted(days)


def _slice_asof(df: pd.DataFrame, day: date) -> pd.DataFrame:
    end = pd.Timestamp(day)
    sliced = df[df.index <= end]
    return sliced.copy()


def _event_timestamp(day: date) -> str:
    return f"{day.isoformat()}T23:59:59"


def run_resimulation(
    start: date,
    end: Optional[date],
    *,
    verbose: bool = False,
    build_snapshots: bool = False,
    output_path: Optional[str] = None,
):
    data_fetcher = DataFetcher(Config)
    pairs_by_strategy = {sid: cfg['pairs'] for sid, cfg in TRADING_CONFIG.items()}

    print('Prefetching market data...')
    market_cache = _prefetch_market_data(data_fetcher, pairs_by_strategy)
    data_fetcher.report_fetch_alerts()
    if not market_cache:
        raise SystemExit('No market data loaded. Check Yahoo/yfinance access.')

    last_bar = max(df.index[-1].date() for df in market_cache.values())
    if end is None:
        end = last_bar
    end = min(end, last_bar)

    if start > end:
        raise SystemExit(f'Start {start} is after end {end}')

    days = _trading_days(market_cache, start, end)
    print(f"Resimulating {len(days)} trading days from {start} through {end}")

    ledger = LedgerManager(Config)
    ledger.ledger = _empty_ledger()

    strategies = {}
    for strategy_id, cfg in TRADING_CONFIG.items():
        strat = load_strategy(cfg['strategy_module'], cfg['strategy_class'], cfg['params'])
        if strat:
            strategies[strategy_id] = strat
        else:
            print(f"Skipping strategy {strategy_id} (load failed)")

    for day in days:
        event_ts = _event_timestamp(day)
        if verbose:
            print(f"\n=== {day} ===")
        for strategy_id, cfg in TRADING_CONFIG.items():
            strategy = strategies.get(strategy_id)
            if not strategy:
                continue
            if verbose:
                print(f"  Strategy {strategy_id} (cash ${ledger.get_balance(strategy_id):.2f})")
            for symbol in cfg['pairs']:
                full_df = market_cache.get(symbol)
                if full_df is None:
                    continue
                if full_df.index[0].date() > day:
                    continue
                market_data = _slice_asof(full_df, day)
                if len(market_data) < 30:
                    continue
                if verbose:
                    print(f"    {symbol}")
                process_symbol(
                    ledger, strategy_id, symbol, strategy, market_data,
                    event_ts=event_ts,
                    verbose=verbose,
                    build_snapshots=build_snapshots,
                )

    out = output_path or os.path.join(Config.DATA_DIR, 'ledger_resim.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(ledger.ledger, f, indent=4)
    print(f"\nWrote {out}")

    totals = {}
    for sid in TRADING_CONFIG:
        strat = ledger.ledger['strategies'][sid]
        totals[sid] = {
            'cash': round(strat['cash'], 2),
            'open_positions': len(strat.get('positions', {})),
            'history_rows': len(strat.get('history', [])),
        }
    print('Summary:', json.dumps(totals, indent=2))
    return out, ledger


def main():
    parser = argparse.ArgumentParser(description='Resimulate trading from a start date.')
    parser.add_argument(
        '--start',
        default=DEFAULT_START.isoformat(),
        help='First calendar day to simulate (default 2026-01-01)',
    )
    parser.add_argument('--end', default=None, help='Last day (default: latest bar in data)')
    parser.add_argument(
        '--output',
        default=os.path.join(Config.DATA_DIR, 'ledger_resim.json'),
        help='Output ledger path',
    )
    parser.add_argument(
        '--replace-ledger',
        action='store_true',
        help='Copy result to data/ledger.json (backs up existing file first)',
    )
    parser.add_argument('-v', '--verbose', action='store_true', help='Print each symbol/day')
    parser.add_argument(
        '--snapshots',
        action='store_true',
        help='Build close candle snapshots (slower; run update_snapshots later if omitted)',
    )
    parser.add_argument('--audit', action='store_true', help='Run trade audit after save')
    parser.add_argument('--report', action='store_true', help='Regenerate docs/report_data.js after save')
    args = parser.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end) if args.end else None

    print(f"--- Resimulation: {datetime.now()} ---")
    out_path, ledger = run_resimulation(
        start,
        end,
        verbose=args.verbose,
        build_snapshots=args.snapshots,
        output_path=args.output,
    )

    if args.replace_ledger:
        live_path = Config.LEDGER_FILE
        if os.path.exists(live_path):
            shutil.copy2(live_path, live_path + '.pre_resim.bak')
        shutil.copy2(out_path, live_path)
        print(f"Replaced {live_path} (backup {live_path}.pre_resim.bak)")
        ledger.ledger_file = live_path

    if args.audit:
        from audit_trades import run_audit
        run_audit(write_files=True, ledger=ledger.ledger)

    if args.report:
        from reporting import ReportGenerator
        if args.replace_ledger:
            reporter = ReportGenerator(Config)
        else:
            class _Cfg:
                DATA_DIR = Config.DATA_DIR
                LEDGER_FILE = out_path
            reporter = ReportGenerator(_Cfg)
        reporter.generate()
        print(f"Report: {reporter.report_file}")


if __name__ == '__main__':
    main()
