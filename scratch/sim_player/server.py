"""Localhost EMA sim player (scratch-only). Not part of GitHub Pages.

Usage:
  .\\.venv\\Scripts\\python.exe scratch\\sim_player\\server.py
  open http://127.0.0.1:8765
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import date
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')
HOST = '127.0.0.1'
PORT = 8765

os.chdir(REPO_ROOT)
for path in (
    REPO_ROOT,
    os.path.join(REPO_ROOT, 'src'),
    os.path.join(REPO_ROOT, 'scratch'),
    os.path.dirname(__file__),
):
    if path not in sys.path:
        sys.path.insert(0, path)

from config import Config  # noqa: E402
from data_ingestion import DataFetcher, _normalize_ohlcv  # noqa: E402
from engine import run_sim  # noqa: E402
from ohlcv import fetch_btc_intraday  # noqa: E402
from presets import load_presets  # noqa: E402


def _json_response(handler: SimpleHTTPRequestHandler, obj, status: int = 200):
    body = json.dumps(obj, allow_nan=False).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(body)))
    handler.send_header('Cache-Control', 'no-store')
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: SimpleHTTPRequestHandler) -> dict:
    length = int(handler.headers.get('Content-Length') or 0)
    raw = handler.rfile.read(length) if length else b'{}'
    if not raw:
        return {}
    return json.loads(raw.decode('utf-8'))


def _load_bars(symbol: str, interval: str, need_from: date | None = None):
    symbol = symbol or 'BTC/USDT'
    interval = (interval or '1d').strip()

    if interval in ('4h', '1h'):
        cache_name = 'BTC_USDT_4h.csv' if interval == '4h' else 'BTC_USDT_1h.csv'
        cache_path = os.path.join(Config.DATA_DIR, 'ohlcv_cache', cache_name)
        if os.path.isfile(cache_path):
            import pandas as pd
            df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
            df = _normalize_ohlcv(df)
            if not df.empty:
                # Refetch if caller needs older history than cache covers
                if need_from is not None:
                    first = df.index[0]
                    first_d = first.date() if hasattr(first, 'date') else pd.Timestamp(first).date()
                    if first_d <= need_from:
                        return df
                else:
                    return df
        return fetch_btc_intraday(interval, need_from=need_from)

    fetcher = DataFetcher(Config)
    asset_type = 'crypto'
    if symbol.endswith('=X') or (len(symbol) == 7 and '/' in symbol and not symbol.endswith('USDT')):
        asset_type = 'forex'
    return fetcher.get_data(symbol, asset_type=asset_type)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def log_message(self, fmt, *args):
        sys.stderr.write(f'[sim_player] {self.address_string()} {fmt % args}\n')

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/presets':
            try:
                presets = load_presets()
                _json_response(self, {'presets': presets})
            except Exception as exc:
                traceback.print_exc()
                _json_response(self, {'error': str(exc)}, status=500)
            return
        if parsed.path == '/api/bars':
            qs = parse_qs(parsed.query)
            symbol = (qs.get('symbol') or ['BTC/USDT'])[0]
            interval = (qs.get('interval') or ['4h'])[0]
            try:
                df = _load_bars(symbol, interval)
                if df is None or df.empty:
                    _json_response(self, {'error': f'No bars for {symbol} {interval}'}, status=404)
                    return
                bars = []
                for ts, row in df.iterrows():
                    t = __import__('pandas').Timestamp(ts)
                    if t.tzinfo is not None:
                        t = t.tz_convert('UTC').tz_localize(None)
                    bars.append({
                        'time': int(t.timestamp()),
                        'time_iso': t.isoformat(),
                        'open': float(row['open']),
                        'high': float(row['high']),
                        'low': float(row['low']),
                        'close': float(row['close']),
                        'volume': float(row['volume']) if 'volume' in row else 0.0,
                    })
                _json_response(self, {
                    'symbol': symbol,
                    'interval': interval,
                    'bars': bars,
                    'count': len(bars),
                })
            except Exception as exc:
                traceback.print_exc()
                _json_response(self, {'error': str(exc)}, status=500)
            return
        if parsed.path in ('/', '/index.html'):
            self.path = '/index.html'
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != '/api/sim':
            self.send_error(404)
            return
        try:
            body = _read_json(self)
            params = body.get('params') or {}
            strategy = (params.get('strategy') or 'ema_cross').strip()
            if strategy in ('mid_slope', 'close_slope'):
                required = (
                    'slope_span', 'trend_window',
                    'atr_period', 'sl_atr', 'trail_atr',
                )
            else:
                required = (
                    'short_window', 'long_window', 'trend_window',
                    'atr_period', 'sl_atr', 'trail_atr',
                )
            missing = [k for k in required if k not in params]
            if missing:
                _json_response(self, {'error': f'Missing params: {missing}'}, status=400)
                return
            symbol = body.get('symbol') or 'BTC/USDT'
            interval = body.get('interval') or '4h'
            start_s = body.get('start')
            end_s = body.get('end')
            start = date.fromisoformat(start_s) if start_s else None
            end = date.fromisoformat(end_s) if end_s else None
            start_cash = float(body.get('start_cash') or Config.INITIAL_STRATEGY_CASH)

            df = _load_bars(symbol, interval, need_from=start)
            if df is None or df.empty:
                _json_response(self, {'error': f'No bars for {symbol} {interval}'}, status=404)
                return

            df_finer = None
            if interval == '4h':
                try:
                    df_finer = _load_bars(symbol, '1h', need_from=start)
                except Exception as exc:
                    print(f'WARN: 1h drill data unavailable ({exc}); continuing without drill')
            elif interval in ('1d', '1D', 'd'):
                try:
                    df_finer = _load_bars(symbol, '4h', need_from=start)
                except Exception as exc:
                    print(f'WARN: 4h drill data unavailable ({exc}); continuing without drill')

            result = run_sim(
                df,
                params,
                start=start,
                end=end,
                start_cash=start_cash,
                interval=interval,
                df_finer=df_finer,
            )
            result['symbol'] = symbol
            result['interval'] = interval
            _json_response(self, result)
        except Exception as exc:
            traceback.print_exc()
            _json_response(self, {'error': str(exc)}, status=500)


def main():
    os.makedirs(STATIC_DIR, exist_ok=True)
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f'Sim player: http://{HOST}:{PORT}')
    print('Ctrl+C to stop')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
    finally:
        httpd.server_close()


if __name__ == '__main__':
    main()
