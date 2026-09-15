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

from config import Config, TRADING_CONFIG, RISK_SETTINGS, STOCKS_EQUITY_RISK_PCT, STOCKS_UNIVERSE_FILE
from data_ingestion import DataFetcher
from ledger_manager import LedgerManager
from resim_engine import asset_type_for_symbol, load_strategy, process_symbol
from strategies.moving_average import MovingAverageStrategy, CachedMovingAverageStrategy
from shared.stocks_screener import ohlcv_pass_mask, ohlcv_screen
from shared.stocks_universe import STOCK_SIM_TICKERS, load_universe
from shared.us_market_calendar import regular_open_et_label

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
    # Avoid copy: process_symbol only reads; indicators come from cache.
    return df.loc[: pd.Timestamp(day)]


def _event_timestamp(day: date) -> str:
    return f"{day.isoformat()}T23:59:59"


def _precompute_ma_caches(market_cache, strategies):
    """
    One EMA/ATR/ADX cache per (symbol, short, long, trend, macro) fingerprint.
    Filter thresholds (adx_min, vol_mult, atr_buffer) do not need series caches.
    """
    base = MovingAverageStrategy({})
    caches = {}
    fingerprints = set()
    for strat in strategies.values():
        if not isinstance(strat, CachedMovingAverageStrategy):
            continue
        p = strat.params
        fingerprints.add((
            p.get('short_window', 12),
            p.get('long_window', 24),
            p.get('trend_window', 50),
            int(p.get('macro_ema_window', 0) or 0),
        ))

    if not fingerprints:
        return caches

    print(f'Precomputing MA indicators ({len(fingerprints)} fingerprint(s) x {len(market_cache)} symbols)...')
    for symbol, df in market_cache.items():
        atr = base._calculate_atr(df, 14)
        adx = base._calculate_adx(df, 14)
        for short_w, long_w, trend_w, macro_w in fingerprints:
            key = (symbol, short_w, long_w, trend_w, macro_w)
            entry = {
                'ema_fast': base._ema(df['close'], short_w),
                'ema_slow': base._ema(df['close'], long_w),
                'ema_trend': base._ema(df['close'], trend_w),
                'atr': atr,
                'adx': adx,
            }
            if macro_w > 0:
                entry['ema_macro'] = base._ema(df['close'], macro_w)
            caches[key] = entry
        print(f'  cached {symbol}')
    return caches


def _stocks_universe_pairs() -> list[str]:
    universe = load_universe(STOCKS_UNIVERSE_FILE)
    seen = set()
    out = []
    for sym in list(STOCK_SIM_TICKERS) + list(universe.get('seed_tickers') or []) + list(
        universe.get('active') or []
    ):
        s = str(sym or '').upper().strip()
        if not s or s in seen or len(s) < 2:
            continue
        seen.add(s)
        out.append(s)
    return out


def _precompute_screen_masks(market_cache: dict) -> dict[str, pd.Series]:
    """symbol -> boolean Series indexed by bar timestamp (OHLCV Core, point-in-time)."""
    masks = {}
    print(f'Precomputing daily OHLCV screen masks ({len(market_cache)} symbols)...')
    for symbol, df in market_cache.items():
        masks[symbol] = ohlcv_pass_mask(df)
        n_pass = int(masks[symbol].sum()) if len(masks[symbol]) else 0
        print(f'  {symbol}: {n_pass} eligible bars / {len(df)}')
    return masks


def _eligible_on_day(mask: pd.Series, day: date) -> bool:
    if mask is None or mask.empty:
        return False
    ts = pd.Timestamp(day)
    # Exact calendar day match on the mask index.
    day_rows = mask.index.normalize() == ts.normalize()
    if not day_rows.any():
        # Fall back to last bar on or before day.
        loc = mask.index[mask.index <= ts]
        if len(loc) == 0:
            return False
        return bool(mask.loc[loc[-1]])
    return bool(mask.loc[day_rows].iloc[-1])


def _risk_for_strategy(cfg: dict) -> dict:
    if cfg.get('market') == 'stocks':
        return {**RISK_SETTINGS, 'equity_risk_pct': STOCKS_EQUITY_RISK_PCT}
    return RISK_SETTINGS


def _merge_strategies_into_live(resim_ledger: dict, strategy_ids: list[str]) -> None:
    """Overwrite only the given strategies in data/ledger.json; keep other books."""
    live_path = Config.LEDGER_FILE
    if os.path.exists(live_path):
        shutil.copy2(live_path, live_path + '.pre_resim.bak')
        with open(live_path, 'r', encoding='utf-8') as f:
            live = json.load(f)
    else:
        live = {'strategies': {}}
    live.setdefault('strategies', {})
    for sid in strategy_ids:
        live['strategies'][sid] = resim_ledger['strategies'][sid]
    with open(live_path, 'w', encoding='utf-8') as f:
        json.dump(live, f, indent=4)
    print(f'Merged {len(strategy_ids)} strategy(ies) into {live_path}')


def _latest_screen_payload(market_cache: dict, masks: dict, end: date) -> dict:
    matches = []
    for symbol, df in market_cache.items():
        mask = masks.get(symbol)
        if not _eligible_on_day(mask, end):
            continue
        slice_df = df.loc[: pd.Timestamp(end)]
        hit = ohlcv_screen(slice_df)
        if hit:
            matches.append({'ticker': symbol, **hit})
    return {
        'as_of': f'{end.isoformat()}T16:00:00',
        'open_et': regular_open_et_label(),
        'seed_count': len(market_cache),
        'match_count': len(matches),
        'matches': matches,
        'active': [m['ticker'] for m in matches],
        'screen_mode': 'ohlcv_daily_pit',
        'note': '4y resim: OHLCV Core gates evaluated each day (fundamentals not PIT).',
    }

def run_resimulation(
    start: date,
    end: Optional[date],
    *,
    verbose: bool = False,
    build_snapshots: bool = False,
    output_path: Optional[str] = None,
    strategy_ids: Optional[list] = None,
    screen_daily: bool = False,
    stocks_universe_pairs: bool = False,
):
    data_fetcher = DataFetcher(Config)
    active_config = TRADING_CONFIG
    if strategy_ids:
        missing = [sid for sid in strategy_ids if sid not in TRADING_CONFIG]
        if missing:
            raise SystemExit(f'Unknown strategy id(s): {missing}')
        active_config = {sid: TRADING_CONFIG[sid] for sid in strategy_ids}

    # Copy configs so we can expand stocks pairs for the resim without mutating live config.
    active_config = {
        sid: {**cfg, 'pairs': list(cfg.get('pairs') or [])}
        for sid, cfg in active_config.items()
    }
    if stocks_universe_pairs:
        uni = _stocks_universe_pairs()
        for sid, cfg in active_config.items():
            if cfg.get('market') == 'stocks':
                cfg['pairs'] = list(uni)
                print(f'{sid}: screening universe {len(uni)} tickers')

    pairs_by_strategy = {sid: cfg['pairs'] for sid, cfg in active_config.items()}

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
    if strategy_ids:
        print(f"Strategies: {', '.join(strategy_ids)}")
    if screen_daily:
        print('Daily OHLCV screener: new entries only when Core gates pass that day')

    screen_masks = _precompute_screen_masks(market_cache) if screen_daily else {}

    ledger = LedgerManager(Config)
    ledger.ledger = {
        'strategies': {
            strategy_id: {
                'cash': Config.INITIAL_STRATEGY_CASH,
                'positions': {},
                'history': [],
            }
            for strategy_id in active_config
        }
    }

    strategies = {}
    for strategy_id, cfg in active_config.items():
        if cfg.get('strategy_class') == 'MovingAverageStrategy':
            strat = CachedMovingAverageStrategy(cfg.get('params'))
        else:
            strat = load_strategy(cfg['strategy_module'], cfg['strategy_class'], cfg['params'])
        if strat:
            strategies[strategy_id] = strat
        else:
            print(f"Skipping strategy {strategy_id} (load failed)")

    ma_caches = _precompute_ma_caches(market_cache, strategies)

    progress_every = max(1, len(days) // 20)
    for day_i, day in enumerate(days, 1):
        event_ts = _event_timestamp(day)
        if verbose:
            print(f"\n=== {day} ===")
        elif day_i % progress_every == 0 or day_i == len(days):
            print(f"  day {day_i}/{len(days)} ({day})")
        for strategy_id, cfg in active_config.items():
            strategy = strategies.get(strategy_id)
            if not strategy:
                continue
            risk_settings = _risk_for_strategy(cfg)
            if verbose:
                print(f"  Strategy {strategy_id} (cash ${ledger.get_balance(strategy_id):.2f})")
            for symbol in cfg['pairs']:
                full_df = market_cache.get(symbol)
                if full_df is None:
                    continue
                if full_df.index[0].date() > day:
                    continue
                pos_open = ledger.get_position(strategy_id, symbol) is not None
                eligible = True
                if screen_daily and cfg.get('market') == 'stocks':
                    eligible = _eligible_on_day(screen_masks.get(symbol), day)
                    # Always manage open positions; block new entries when off-screen.
                    if not eligible and not pos_open:
                        continue
                market_data = _slice_asof(full_df, day)
                if len(market_data) < 30:
                    continue
                if isinstance(strategy, CachedMovingAverageStrategy):
                    p = strategy.params
                    cache_key = (
                        symbol,
                        p.get('short_window', 12),
                        p.get('long_window', 24),
                        p.get('trend_window', 50),
                        int(p.get('macro_ema_window', 0) or 0),
                    )
                    strategy.bind_cache(ma_caches[cache_key])
                if verbose:
                    print(f"    {symbol}")
                process_symbol(
                    ledger, strategy_id, symbol, strategy, market_data,
                    event_ts=event_ts,
                    verbose=verbose,
                    build_snapshots=build_snapshots,
                    risk_settings=risk_settings,
                    allow_new_entries=(eligible if screen_daily else True),
                )

    out = output_path or os.path.join(Config.DATA_DIR, 'ledger_resim.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(ledger.ledger, f, indent=4)
    print(f"\nWrote {out}")

    totals = {}
    for sid in active_config:
        strat = ledger.ledger['strategies'][sid]
        totals[sid] = {
            'cash': round(strat['cash'], 2),
            'open_positions': len(strat.get('positions', {})),
            'history_rows': len(strat.get('history', [])),
        }
    print('Summary:', json.dumps(totals, indent=2))
    screen_payload = None
    if screen_daily:
        screen_payload = _latest_screen_payload(market_cache, screen_masks, end)
        print(f"End-date screen matches: {screen_payload['match_count']}")
    return out, ledger, screen_payload


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
        help='Copy/merge result into data/ledger.json (backs up existing file first)',
    )
    parser.add_argument(
        '--merge-strategies',
        action='store_true',
        help='With --replace-ledger, only overwrite strategies included in this resim',
    )
    parser.add_argument('-v', '--verbose', action='store_true', help='Print each symbol/day')
    parser.add_argument(
        '--snapshots',
        action='store_true',
        help='Build close candle snapshots (slower; run update_snapshots later if omitted)',
    )
    parser.add_argument('--audit', action='store_true', help='Run trade audit after save')
    parser.add_argument('--report', action='store_true', help='Regenerate docs/report_data.js after save')
    parser.add_argument(
        '--strategy',
        action='append',
        dest='strategies',
        default=None,
        help='Limit resim to one or more strategy ids (repeatable)',
    )
    parser.add_argument(
        '--market',
        default=None,
        help='Limit to strategies in this market (e.g. stocks)',
    )
    parser.add_argument(
        '--screen-daily',
        action='store_true',
        help='Stocks: evaluate OHLCV Core screener each day; entries only when eligible',
    )
    parser.add_argument(
        '--stocks-universe',
        action='store_true',
        help='Stocks: trade the seed/sim universe (not only current active list)',
    )
    args = parser.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end) if args.end else None

    strategy_ids = list(args.strategies) if args.strategies else None
    if args.market:
        market_ids = [
            sid for sid, cfg in TRADING_CONFIG.items()
            if cfg.get('market') == args.market
        ]
        if not market_ids:
            raise SystemExit(f'No strategies for market={args.market}')
        strategy_ids = market_ids if strategy_ids is None else [
            sid for sid in strategy_ids if sid in market_ids
        ]

    stocks_universe = bool(args.stocks_universe or (args.screen_daily and args.market == 'stocks'))

    print(f"--- Resimulation: {datetime.now()} ---")
    out_path, ledger, screen_payload = run_resimulation(
        start,
        end,
        verbose=args.verbose,
        build_snapshots=args.snapshots,
        output_path=args.output,
        strategy_ids=strategy_ids,
        screen_daily=args.screen_daily,
        stocks_universe_pairs=stocks_universe,
    )

    if args.replace_ledger:
        if args.merge_strategies or (strategy_ids and len(strategy_ids) < len(TRADING_CONFIG)):
            _merge_strategies_into_live(ledger.ledger, list(ledger.ledger['strategies'].keys()))
        else:
            live_path = Config.LEDGER_FILE
            if os.path.exists(live_path):
                shutil.copy2(live_path, live_path + '.pre_resim.bak')
            shutil.copy2(out_path, live_path)
            print(f"Replaced {live_path} (backup {live_path}.pre_resim.bak)")
        ledger.ledger_file = Config.LEDGER_FILE

    if args.audit:
        from audit_trades import run_audit
        # Prefer live ledger after merge.
        if args.replace_ledger and os.path.exists(Config.LEDGER_FILE):
            with open(Config.LEDGER_FILE, 'r', encoding='utf-8') as f:
                run_audit(write_files=True, ledger=json.load(f))
        else:
            run_audit(write_files=True, ledger=ledger.ledger)

    if args.report:
        from reporting import ReportGenerator
        if args.replace_ledger:
            reporter = ReportGenerator(Config)
        else:
            class _Cfg:
                DATA_DIR = Config.DATA_DIR
                LEDGER_FILE = out_path
                INITIAL_STRATEGY_CASH = Config.INITIAL_STRATEGY_CASH
            reporter = ReportGenerator(_Cfg)
        reporter.generate(stocks_screener=screen_payload)
        print(f"Report: {reporter.report_file}")


if __name__ == '__main__':
    main()
