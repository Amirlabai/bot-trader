"""BTC intraday OHLCV loaders for the sim player (separate from daily live cache)."""

from __future__ import annotations

import contextlib
import io
import os
import time
from datetime import date, datetime, timedelta

import pandas as pd

from config import Config
from data_ingestion import YAHOO_PAUSE_SEC, _normalize_ohlcv, yahoo_ticker

SYMBOL = 'BTC/USDT'
WARMUP_DAYS = 60
FETCH_SPAN_DAYS = 450


def _cache_path(interval: str) -> str:
    cache_dir = os.path.join(Config.DATA_DIR, 'ohlcv_cache')
    os.makedirs(cache_dir, exist_ok=True)
    safe = interval.replace('/', '_')
    return os.path.join(cache_dir, f'BTC_USDT_{safe}.csv')


def _load_cache(interval: str) -> pd.DataFrame | None:
    path = _cache_path(interval)
    if not os.path.isfile(path):
        return None
    try:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        return _normalize_ohlcv(df)
    except Exception:
        return None


def _save_cache(interval: str, df: pd.DataFrame) -> None:
    if df is None or df.empty:
        return
    try:
        df.to_csv(_cache_path(interval))
    except Exception as exc:
        print(f'WARN: could not write {interval} OHLCV cache: {exc}')


def _cache_fresh(df: pd.DataFrame, max_age_days: int = 2) -> bool:
    if df is None or df.empty:
        return False
    last = df.index[-1]
    last_d = last.date() if hasattr(last, 'date') else pd.Timestamp(last).date()
    return (date.today() - last_d).days <= max_age_days


def _covers(df: pd.DataFrame, need_from: date | None) -> bool:
    if need_from is None or df is None or df.empty:
        return True
    first = df.index[0]
    first_d = first.date() if hasattr(first, 'date') else pd.Timestamp(first).date()
    return first_d <= need_from


def fetch_btc_intraday(
    interval: str,
    need_from: date | None = None,
) -> pd.DataFrame:
    """Yahoo BTC-USD for 4h or 1h with separate disk cache."""
    if interval not in ('4h', '1h'):
        raise ValueError(f'Unsupported intraday interval: {interval}')

    warm_from = (need_from - timedelta(days=WARMUP_DAYS)) if need_from else None
    cached = _load_cache(interval)
    if (
        cached is not None
        and not cached.empty
        and _cache_fresh(cached)
        and _covers(cached, warm_from)
    ):
        print(f'Using fresh {interval} cache ({len(cached)} bars) -> {_cache_path(interval)}')
        return cached

    try:
        import yfinance as yf
    except ImportError as exc:
        if cached is not None and not cached.empty:
            print(f'yfinance missing; using stale {interval} cache ({len(cached)} bars)')
            return cached
        raise RuntimeError(f'yfinance required for {interval}: {exc}') from exc

    ticker = yahoo_ticker(SYMBOL, asset_type='crypto')
    fetch_end = datetime.utcnow().date() + timedelta(days=1)
    span = FETCH_SPAN_DAYS
    if warm_from is not None:
        span = max(span, (fetch_end - warm_from).days + 5)
    span = min(span, 730)
    fetch_start = fetch_end - timedelta(days=span)
    print(f'Fetching {ticker} {interval} from Yahoo ({fetch_start} .. {fetch_end})...')
    stderr_buf = io.StringIO()
    try:
        with contextlib.redirect_stderr(stderr_buf):
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
        if cached is not None and not cached.empty:
            print(f'Yahoo {interval} miss ({exc}); using stale cache ({len(cached)} bars)')
            return cached
        raise RuntimeError(f'Yahoo {interval} fetch failed for {SYMBOL}: {exc}') from exc

    if df.empty:
        err_text = stderr_buf.getvalue().strip()
        if cached is not None and not cached.empty:
            print(f'Yahoo {interval} empty ({err_text or "no rows"}); using stale cache')
            return cached
        raise RuntimeError(
            f'No {interval} Yahoo data for {SYMBOL}' + (f': {err_text}' if err_text else '')
        )

    _save_cache(interval, df)
    print(f'Loaded {len(df)} {interval} bars (cached -> {_cache_path(interval)})')
    return df
