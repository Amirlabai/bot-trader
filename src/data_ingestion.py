import contextlib
import io
import os
import re
import time

import pandas as pd

from shared.symbols import COMMODITY_YAHOO_TICKERS

YAHOO_PAUSE_SEC = 0.25

_YFRateLimitError = None
try:
    from yfinance.exceptions import YFRateLimitError as _YFRateLimitError
except ImportError:
    _YFRateLimitError = None


def yahoo_ticker(symbol, asset_type='crypto'):
    if asset_type == 'commodity':
        return COMMODITY_YAHOO_TICKERS[symbol]
    clean = symbol.replace('/', '')
    if asset_type == 'forex':
        return f'{clean}=X'
    if clean.endswith('USDT'):
        return f'{clean[:-4]}-USD'
    return clean


def yahoo_block_text(text):
    lower = (text or '').lower()
    if re.search(r'(?<![\d.])429(?![\d.])', lower):
        return True
    return any(
        token in lower
        for token in (
            'too many requests',
            'rate limit',
            'temporarily blocked',
            'will be blocked',
        )
    )


def _is_yahoo_limit_or_block(exc):
    if exc is None:
        return False
    if _YFRateLimitError is not None and isinstance(exc, _YFRateLimitError):
        return True
    text = str(exc).lower()
    if yahoo_block_text(text):
        return True
    if '403' in text and 'yahoo' in text:
        return True
    return False


def _normalize_ohlcv(df):
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = [str(col[0]).lower() for col in out.columns]
    else:
        out.columns = [str(col).lower() for col in out.columns]
    cols = [c for c in ['open', 'high', 'low', 'close', 'volume'] if c in out.columns]
    if not cols:
        return pd.DataFrame()
    out = out[cols]
    if 'volume' not in out.columns:
        out['volume'] = 0.0
    out = out.astype(float)
    idx = pd.to_datetime(out.index)
    if getattr(idx, 'tz', None) is not None:
        idx = idx.tz_convert('UTC').tz_localize(None)
    out.index = idx
    out.sort_index(inplace=True)
    if not out.empty:
        last_date = out.index[-1].date()
        today_date = pd.Timestamp.utcnow().date()
        if last_date == today_date:
            out = out.iloc[:-1]
    return out


class DataFetcher:
    def __init__(self, config):
        self.config = config
        self.cache = {}
        self.yahoo_blocked = False
        self.fetch_events = []

    def _alert(self, level, message):
        print(f'ALERT: {message}')
        if os.getenv('GITHUB_ACTIONS'):
            cmd = 'error' if level == 'error' else 'warning'
            print(f'::{cmd}::{message}')
        self.fetch_events.append({'level': level, 'message': message})

    def report_fetch_alerts(self):
        print('\n--- Fetch alerts ---')
        if self.yahoo_blocked:
            print('  Yahoo: session blocked after rate-limit; remaining pairs may fail.')
        else:
            print('  Yahoo: ok for all fetched pairs.')
        if not self.fetch_events:
            print('  None.')
        for event in self.fetch_events:
            print(f"  [{event['level']}] {event['message']}")
        print('--- End fetch alerts ---\n')

    def fetch_yahoo_history(self, symbol, asset_type='crypto'):
        try:
            import yfinance as yf
        except ImportError as exc:
            return pd.DataFrame(), exc

        ticker = yahoo_ticker(symbol, asset_type)
        stderr_buf = io.StringIO()
        try:
            with contextlib.redirect_stderr(stderr_buf):
                df = yf.download(
                    ticker,
                    period='max',
                    interval='1d',
                    progress=False,
                    auto_adjust=False,
                    threads=False,
                    multi_level_index=False,
                )
            time.sleep(YAHOO_PAUSE_SEC)
            err_text = stderr_buf.getvalue()
            if yahoo_block_text(err_text):
                return pd.DataFrame(), RuntimeError(err_text.strip() or 'Yahoo block detected')
            return _normalize_ohlcv(df), None
        except Exception as exc:
            return pd.DataFrame(), exc

    def get_data(self, symbol, asset_type='crypto'):
        """Daily OHLCV from yfinance (Yahoo)."""
        if asset_type not in ('crypto', 'forex', 'commodity'):
            print(f'Unknown asset type: {asset_type}')
            return pd.DataFrame()

        if symbol in self.cache:
            return self.cache[symbol].copy()

        if self.yahoo_blocked:
            print(f'Yahoo skipped for {symbol} (blocked this session).')
            self._alert('error', f'No Yahoo market data for {symbol} (session blocked).')
            return pd.DataFrame()

        yahoo_df, yahoo_exc = self.fetch_yahoo_history(symbol, asset_type=asset_type)
        if not yahoo_df.empty:
            self.cache[symbol] = yahoo_df.copy()
            return yahoo_df

        if _is_yahoo_limit_or_block(yahoo_exc):
            self.yahoo_blocked = True
            self._alert(
                'warning',
                f'Yahoo rate-limit or block on {symbol} ({yahoo_ticker(symbol, asset_type)}). '
                'Skipping Yahoo for remaining symbols this session.',
            )
        elif yahoo_exc is not None:
            self._alert('error', f'Yahoo error for {symbol}: {yahoo_exc}')
        else:
            self._alert('error', f'No Yahoo market data for {symbol}.')

        return pd.DataFrame()
