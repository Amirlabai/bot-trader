"""US mid-cap stock universe: IJH/MDY seed + runner screener sync."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Callable

from shared.stocks_screener import fundamentals_screen, merge_match, ohlcv_screen
from shared.us_market_calendar import now_et, regular_open_et_label

SEED_ETFS = ('IJH', 'MDY')
FUNDAMENTALS_TTL_SEC = 7 * 24 * 3600
YAHOO_PAUSE_SEC = 0.35

# Frozen sim set for EMA/ATR grid (not the live screener universe).
STOCK_SIM_TICKERS = ['AXON', 'DECK', 'FIX', 'CASY', 'MANH', 'WSM']


def load_universe(path: str) -> dict:
    if not os.path.exists(path):
        return {
            'updated_at': None,
            'seed_tickers': [],
            'active': [],
            'matches': [],
            'open_positions_kept': [],
        }
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    data.setdefault('seed_tickers', [])
    data.setdefault('active', [])
    data.setdefault('matches', [])
    data.setdefault('open_positions_kept', [])
    return data


def save_universe(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
        f.write('\n')


def load_fundamentals_cache(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_fundamentals_cache(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
        f.write('\n')


def _normalize_ticker(sym: str) -> str | None:
    s = str(sym or '').upper().strip().replace('.', '-')
    if not s or '/' in s or s in SEED_ETFS:
        return None
    # Skip obvious non-equity rows and 1-character noise from holdings tables.
    if len(s) < 2 or s.endswith('=F') or s.endswith('=X'):
        return None
    return s


def fetch_etf_holdings(etf: str) -> list[str]:
    """Best-effort holdings from yfinance; empty on failure."""
    try:
        import yfinance as yf
    except ImportError:
        return []
    tickers: list[str] = []
    try:
        t = yf.Ticker(etf)
        holdings = None
        funds = getattr(t, 'funds_data', None)
        if funds is not None:
            holdings = getattr(funds, 'top_holdings', None)
        if holdings is None:
            try:
                holdings = t.get_holdings()
            except Exception:
                holdings = None
        if holdings is not None and hasattr(holdings, 'index'):
            for idx in holdings.index:
                norm = _normalize_ticker(str(idx))
                if norm:
                    tickers.append(norm)
        time.sleep(YAHOO_PAUSE_SEC)
    except Exception as exc:
        print(f'  WARN: could not load holdings for {etf}: {exc}')
    return tickers


def seed_tickers_from_etfs(existing: list[str] | None = None) -> list[str]:
    """Add-only merge of IJH/MDY holdings into an existing seed list."""
    seen = set()
    out: list[str] = []
    for sym in list(existing or []) + list(STOCK_SIM_TICKERS):
        norm = _normalize_ticker(sym)
        if norm and norm not in seen:
            seen.add(norm)
            out.append(norm)
    for etf in SEED_ETFS:
        print(f'--- Seeding from {etf} holdings ---')
        for sym in fetch_etf_holdings(etf):
            if sym not in seen:
                seen.add(sym)
                out.append(sym)
                print(f'  seed add {sym}')
    if len(out) <= len(STOCK_SIM_TICKERS):
        print('  WARN: ETF holdings thin; sim tickers remain the core seed')
    return out


def fetch_yahoo_info(ticker: str) -> dict | None:
    try:
        import yfinance as yf
    except ImportError:
        return None
    try:
        info = yf.Ticker(ticker).info or {}
        time.sleep(YAHOO_PAUSE_SEC)
        return info if isinstance(info, dict) else None
    except Exception as exc:
        print(f'  WARN: info miss for {ticker}: {exc}')
        return None


def get_cached_fundamentals(
    ticker: str,
    cache: dict,
    *,
    fetch: bool = True,
    ttl_sec: int = FUNDAMENTALS_TTL_SEC,
) -> dict | None:
    now = time.time()
    row = cache.get(ticker)
    if isinstance(row, dict):
        fetched_at = float(row.get('fetched_at') or 0)
        if now - fetched_at <= ttl_sec and 'info' in row:
            return row.get('info')
    if not fetch:
        return None
    info = fetch_yahoo_info(ticker)
    cache[ticker] = {'fetched_at': now, 'info': info}
    return info


def screen_universe(
    tickers: list[str],
    get_ohlcv: Callable[[str], object],
    fundamentals_cache: dict,
    *,
    yahoo_blocked: Callable[[], bool] | None = None,
) -> list[dict]:
    """Two-pass screen: OHLCV then fundamentals on survivors."""
    matches: list[dict] = []
    ohlcv_hits: list[tuple[str, dict]] = []

    for ticker in tickers:
        if yahoo_blocked is not None and yahoo_blocked():
            print('  Yahoo blocked; stopping OHLCV screen early.')
            break
        df = get_ohlcv(ticker)
        hit = ohlcv_screen(df)
        if hit:
            ohlcv_hits.append((ticker, hit))

    print(f'  OHLCV survivors: {len(ohlcv_hits)}')
    for ticker, ohlcv in ohlcv_hits:
        if yahoo_blocked is not None and yahoo_blocked():
            print('  Yahoo blocked; stopping fundamentals screen early.')
            break
        info = get_cached_fundamentals(ticker, fundamentals_cache, fetch=True)
        fund = fundamentals_screen(info)
        if not fund:
            continue
        matches.append(merge_match(ticker, ohlcv, fund))
        print(f'  MATCH {ticker}')
    return matches


def merge_active_with_open(
    matches: list[dict],
    open_symbols: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Active = today's matches; keep open positions tradeable even if off-screen."""
    active = []
    seen = set()
    for row in matches:
        t = row.get('ticker')
        if t and t not in seen:
            seen.add(t)
            active.append(t)
    kept = []
    for sym in open_symbols or []:
        norm = _normalize_ticker(sym)
        if norm and norm not in seen:
            seen.add(norm)
            active.append(norm)
            kept.append(norm)
    return active, kept


def sync_stocks_universe(
    universe_path: str,
    fundamentals_cache_path: str,
    get_ohlcv: Callable[[str], object],
    *,
    open_symbols: list[str] | None = None,
    yahoo_blocked: Callable[[], bool] | None = None,
    refresh_seed: bool = True,
) -> dict:
    """Seed (add-only), screen, update active list. Returns summary for reporting."""
    universe = load_universe(universe_path)
    if refresh_seed or not universe.get('seed_tickers'):
        universe['seed_tickers'] = seed_tickers_from_etfs(universe.get('seed_tickers'))
    else:
        universe['seed_tickers'] = [
            t for t in (_normalize_ticker(x) for x in universe.get('seed_tickers') or []) if t
        ]

    fund_cache = load_fundamentals_cache(fundamentals_cache_path)
    print(f'--- Stocks screener ({len(universe["seed_tickers"])} seeds) ---')
    matches = screen_universe(
        universe['seed_tickers'],
        get_ohlcv,
        fund_cache,
        yahoo_blocked=yahoo_blocked,
    )
    save_fundamentals_cache(fundamentals_cache_path, fund_cache)

    active, kept = merge_active_with_open(matches, open_symbols=open_symbols)
    # Ensure sim tickers remain available as a floor when screen is empty and no opens.
    if not active:
        active = list(STOCK_SIM_TICKERS)
        print('  No screen matches; using STOCK_SIM_TICKERS as active floor.')

    et_now = now_et()
    universe['updated_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    universe['active'] = active
    universe['matches'] = matches
    universe['open_positions_kept'] = kept
    universe['screener_meta'] = {
        'as_of': et_now.isoformat(timespec='seconds'),
        'open_et': regular_open_et_label(),
        'seed_count': len(universe['seed_tickers']),
        'match_count': len(matches),
    }
    save_universe(universe_path, universe)

    return {
        'active': active,
        'matches': matches,
        'kept': kept,
        'seed_count': len(universe['seed_tickers']),
        'universe_path': universe_path,
        'screener_meta': universe['screener_meta'],
    }
