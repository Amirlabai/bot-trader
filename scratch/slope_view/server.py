"""Localhost midpoint slope viewer (scratch-only). Not part of GitHub Pages.

Usage:
  .\\.venv\\Scripts\\python.exe scratch\\slope_view\\server.py
  open http://127.0.0.1:8766
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import date
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')
SIM_PLAYER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'sim_player'))
HOST = '127.0.0.1'
PORT = 8766

os.chdir(REPO_ROOT)
for path in (
    REPO_ROOT,
    os.path.join(REPO_ROOT, 'src'),
    os.path.join(REPO_ROOT, 'scratch'),
    SIM_PLAYER_DIR,
    os.path.dirname(__file__),
):
    if path not in sys.path:
        sys.path.insert(0, path)

from config import Config  # noqa: E402
from data_ingestion import DataFetcher, _normalize_ohlcv  # noqa: E402
from ohlcv import fetch_btc_intraday  # noqa: E402
from series import build_view  # noqa: E402


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


def _load_bars(interval: str, need_from: date | None = None):
    interval = (interval or '4h').strip()

    if interval in ('4h', '1h'):
        cache_name = 'BTC_USDT_4h.csv' if interval == '4h' else 'BTC_USDT_1h.csv'
        cache_path = os.path.join(Config.DATA_DIR, 'ohlcv_cache', cache_name)
        if os.path.isfile(cache_path):
            import pandas as pd
            df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
            df = _normalize_ohlcv(df)
            if not df.empty:
                if need_from is None:
                    return df
                first = df.index[0]
                first_d = first.date() if hasattr(first, 'date') else pd.Timestamp(first).date()
                if first_d <= need_from:
                    return df
        return fetch_btc_intraday(interval, need_from=need_from)

    if interval not in ('1d', '1D', 'd'):
        raise ValueError(f'Unsupported interval: {interval}')
    fetcher = DataFetcher(Config)
    return fetcher.get_data('BTC/USDT', asset_type='crypto')


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def log_message(self, fmt, *args):
        sys.stderr.write(f'[slope_view] {self.address_string()} {fmt % args}\n')

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ('/', '/index.html'):
            self.path = '/index.html'
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != '/api/view':
            self.send_error(404)
            return
        try:
            body = _read_json(self)
            interval = (body.get('interval') or '4h').strip()
            trend_window = int(body.get('trend_window') or 150)
            slope_span = int(body.get('slope_span') or 1)
            start_s = body.get('start') or None
            end_s = body.get('end') or None
            start = date.fromisoformat(start_s) if start_s else None
            end = date.fromisoformat(end_s) if end_s else None

            df = _load_bars(interval, need_from=start)
            if df is None or df.empty:
                _json_response(self, {'error': f'No bars for BTC/USDT {interval}'}, status=404)
                return

            result = build_view(
                df,
                trend_window=trend_window,
                slope_span=slope_span,
                start=start,
                end=end,
                interval='1d' if interval in ('1d', '1D', 'd') else interval,
            )
            _json_response(self, result)
        except Exception as exc:
            traceback.print_exc()
            _json_response(self, {'error': str(exc)}, status=500)


def main():
    os.makedirs(STATIC_DIR, exist_ok=True)
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f'Slope viewer: http://{HOST}:{PORT}')
    print('Ctrl+C to stop')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
    finally:
        httpd.server_close()


if __name__ == '__main__':
    main()
