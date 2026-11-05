"""Daily OHLCV for research, from bot-trader's DataFetcher (yfinance).

DataFetcher.get_data already keeps a disk cache in data/ohlcv_cache/ and refreshes
it when the last bar is older than about four days. The full history is returned:
the weekly EMA 150 trend needs about three years of warmup before the replay window.
refresh=True (CLI --refresh) forces a Yahoo pull.
"""

from __future__ import annotations

import pandas as pd

_FETCHER = None


def _fetcher():
    global _FETCHER
    if _FETCHER is None:
        from config import Config
        from data_ingestion import DataFetcher
        _FETCHER = DataFetcher(Config)
    return _FETCHER


def get_history(symbol: str, *, fetcher=None, refresh: bool = False,
                asset_type: str = 'crypto') -> pd.DataFrame:
    """All completed daily bars for `symbol`. Empty when unavailable."""
    fetcher = fetcher or _fetcher()
    df = None
    if refresh:
        df, exc = fetcher.fetch_yahoo_history(symbol, asset_type=asset_type)
        if exc is not None or df is None or df.empty:
            print(f'  {symbol}: refresh failed ({exc}); using cache')
            df = None
        else:
            fetcher._save_disk_cache(symbol, df)
    if df is None:
        df = fetcher.get_data(symbol, asset_type)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    if getattr(df.index, 'tz', None) is not None:
        df.index = df.index.tz_convert('UTC').tz_localize(None)
    df = df[['open', 'high', 'low', 'close', 'volume']].sort_index()
    df = df[~df.index.duplicated(keep='last')]
    df.index.name = 'ts'
    return df
