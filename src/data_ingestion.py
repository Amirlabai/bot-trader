import contextlib
import io
import os
import re
import time

import pandas as pd
import requests

YAHOO_PROBE_TICKER = 'BTC-USD'
YAHOO_PROBE_PERIOD = '5d'

_YFRateLimitError = None
try:
    from yfinance.exceptions import YFRateLimitError as _YFRateLimitError
except ImportError:
    _YFRateLimitError = None


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


def _is_fmp_limit(status_code, payload):
    if status_code == 429:
        return True
    if isinstance(payload, dict):
        text = str(payload.get('Error Message') or payload.get('error') or '')
    else:
        text = str(payload or '')
    lower = text.lower()
    return 'rate limit' in lower or 'too many requests' in lower or 'limit reached' in lower


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
        self._yahoo_probed = False
        self.fetch_events = []
        self._last_fmp_limited = False

    def _alert(self, level, message):
        print(f'ALERT: {message}')
        if os.getenv('GITHUB_ACTIONS'):
            cmd = 'error' if level == 'error' else 'warning'
            print(f'::{cmd}::{message}')
        self.fetch_events.append({'level': level, 'message': message})

    def report_fetch_alerts(self):
        print('\n--- Fetch alerts ---')
        if self.yahoo_blocked:
            print('  Yahoo VM probe: blocked or rate-limited (bars still from FMP).')
        elif self._yahoo_probed:
            print('  Yahoo VM probe: ok (not used for bars).')
        if not self.fetch_events:
            print('  None.')
        for event in self.fetch_events:
            print(f"  [{event['level']}] {event['message']}")
        print('--- End fetch alerts ---\n')

    def probe_yahoo(self):
        """Dry check whether this host is rejected by Yahoo. Never used as OHLCV."""
        if self._yahoo_probed:
            return not self.yahoo_blocked
        self._yahoo_probed = True
        try:
            import yfinance as yf
        except ImportError as exc:
            self._alert('warning', f'yfinance not installed; skip Yahoo VM probe ({exc}).')
            return False

        stderr_buf = io.StringIO()
        try:
            with contextlib.redirect_stderr(stderr_buf):
                df = yf.download(
                    YAHOO_PROBE_TICKER,
                    period=YAHOO_PROBE_PERIOD,
                    interval='1d',
                    progress=False,
                    auto_adjust=False,
                    threads=False,
                    multi_level_index=False,
                )
            time.sleep(0.25)
            err_text = stderr_buf.getvalue()
            empty = df is None or df.empty
            if empty or yahoo_block_text(err_text):
                self.yahoo_blocked = True
                self._alert(
                    'warning',
                    f'Yahoo VM probe failed for {YAHOO_PROBE_TICKER} '
                    f'(empty={empty}). Host may be rate-limited or blocked. Bars still come from FMP.',
                )
                return False
            print(f'Yahoo VM probe: ok ({YAHOO_PROBE_TICKER}). Not using Yahoo for market data.')
            return True
        except Exception as exc:
            self.yahoo_blocked = _is_yahoo_limit_or_block(exc) or yahoo_block_text(stderr_buf.getvalue())
            level = 'warning'
            if self.yahoo_blocked:
                self._alert(
                    level,
                    f'Yahoo rate-limit or block on VM probe ({exc}). Bars still come from FMP.',
                )
            else:
                self._alert(level, f'Yahoo VM probe error ({exc}). Bars still come from FMP.')
            return False

    def fetch_fmp_history(self, symbol):
        """
        Fetches historical data using Financial Modeling Prep API.
        Works for both Forex (e.g., 'EURUSD') and Crypto (e.g., 'BTCUSD').
        """
        self._last_fmp_limited = False
        api_key = self.config.FMP_API_KEY
        if not api_key:
            print('FMP API Key missing.')
            return pd.DataFrame()

        clean_symbol = symbol.replace('/', '')
        if clean_symbol.endswith('USDT'):
            clean_symbol = clean_symbol.replace('USDT', 'USD')

        url = (
            'https://financialmodelingprep.com/stable/historical-price-eod/full'
            f'?symbol={clean_symbol}&apikey={api_key}'
        )

        try:
            response = requests.get(url, timeout=30)
            if response.status_code != 200:
                print(f'FMP API returned status {response.status_code} for {clean_symbol}')
                self._last_fmp_limited = _is_fmp_limit(response.status_code, response.text)
                return pd.DataFrame()

            try:
                data = response.json()
            except ValueError:
                print(f'FMP API returned invalid JSON for {clean_symbol}')
                return pd.DataFrame()

            if isinstance(data, dict):
                if 'historical' in data:
                    data = data['historical']
                elif 'Error Message' in data:
                    print(f"FMP API Error for {clean_symbol}: {data['Error Message']}")
                    self._last_fmp_limited = _is_fmp_limit(response.status_code, data)
                    return pd.DataFrame()
                else:
                    print(f'Unexpected FMP response format for {clean_symbol}: {data.keys()}')
                    return pd.DataFrame()

            if not isinstance(data, list) or not data:
                print(f'No historical data found for {clean_symbol} in FMP response.')
                return pd.DataFrame()

            df = pd.DataFrame(data)
            if 'date' not in df.columns:
                print(f'Date column missing in FMP data for {clean_symbol}. Columns: {df.columns}')
                return pd.DataFrame()

            df['timestamp'] = pd.to_datetime(df['date'])
            df.set_index('timestamp', inplace=True)
            df.sort_index(inplace=True)
            return _normalize_ohlcv(df)

        except Exception as e:
            print(f'Error fetching FMP data for {symbol}: {e}')
            return pd.DataFrame()

    def get_data(self, symbol, asset_type='crypto'):
        """Daily OHLCV from FMP. Yahoo is probed once per session and never used for bars."""
        if asset_type not in ('crypto', 'forex'):
            print(f'Unknown asset type: {asset_type}')
            return pd.DataFrame()

        if os.getenv('GITHUB_ACTIONS') and not self._yahoo_probed:
            self.probe_yahoo()

        if symbol in self.cache:
            return self.cache[symbol].copy()

        fmp_df = self.fetch_fmp_history(symbol)
        if self._last_fmp_limited:
            self._alert('error', f'FMP rate-limit or block on {symbol}.')
            return pd.DataFrame()
        if fmp_df is not None and not fmp_df.empty:
            self.cache[symbol] = fmp_df.copy()
            return fmp_df
        self._alert('error', f'No FMP market data for {symbol}.')
        return pd.DataFrame()
