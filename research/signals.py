"""Per-bar entry signals from the live daily strategy, computed once per pair and cached.

Entries depend only on the bars (the strategy is called flat, as live does when
it holds nothing). The exit policy decides when the engine is flat again, so one
signal pass serves every exit variant.

Live calls generate_signal once a day on the full yfinance history, so the replay
calls it on the growing prefix df[:i+1] (WINDOW_BARS = None). Only bars from
`start` on are emitted; earlier bars are warmup (the weekly EMA 150 needs ~3 years).
"""

from __future__ import annotations

import hashlib
import json
import os
import time

import pandas as pd

from research.features import entry_features
from research.settings import SIGNALS_CACHE, WINDOW_BARS
from shared import mtf
from shared.constants import reason_is_entry_long
from shared.path_sim import effective_tfs

SIGNALS_VERSION = 1  # bot-trader daily port


def warmup_bars(params: dict) -> int:
    return max(
        int(params.get('trend_window', 150)),
        int(params.get('long_window', 40)),
        int(params.get('atr_period', 14)),
        int(params.get('adx_period', 14)) * 2,
        int(params.get('vol_ma_period', 20)),
    ) + 2


def _is_entry(signal: dict) -> bool:
    if signal.get('action') != 'buy':
        return False
    return bool(signal.get('is_entry')) or reason_is_entry_long(signal.get('reason', ''))


def _above_trend(df: pd.DataFrame, params: dict) -> pd.Series:
    """Trend flag the strategy uses on each bar (no look-ahead: completed higher-tf bars)."""
    span = int(params.get('trend_window', 150))
    ema_fn = lambda series, s: series.ewm(span=s, adjust=False).mean()  # noqa: E731
    trend_tf = effective_tfs(params)['trend_tf']
    if trend_tf != 'D':
        bull, _bear = mtf.trend_flags(df, span, trend_tf, ema_fn)
        return bull.astype(bool)
    return df['close'] > ema_fn(df['close'], span)


def _window(df: pd.DataFrame, i: int) -> pd.DataFrame:
    if WINDOW_BARS is None:
        return df.iloc[:i + 1]
    return df.iloc[max(0, i - WINDOW_BARS + 1):i + 1]


def compute_signals(df: pd.DataFrame, strategy, btc_df=None, start=None) -> pd.DataFrame:
    """One row per bar from `start` (or warmup) on: high, low, close, atr, entry, stop, features."""
    params = getattr(strategy, 'params', {}) or {}
    first = warmup_bars(params)
    if start is not None:
        first = max(first, int(df.index.searchsorted(pd.Timestamp(start))))
    above = _above_trend(df, params)
    rows = []
    for i in range(first, len(df)):
        window = _window(df, i)
        signal = strategy.generate_signal(window, None)
        bar = df.iloc[i]
        atr = signal.get('current_atr')
        entry = _is_entry(signal)
        stop = None
        features = ''
        if entry:
            try:
                stop = float(signal.get('stop_loss'))
            except (TypeError, ValueError):
                stop = None
            if stop is None or stop <= 0 or stop >= float(bar['close']):
                entry = False
            else:
                features = json.dumps(entry_features(window, signal, btc_df))
        rows.append({
            'ts': df.index[i],
            'open': float(bar['open']),
            'high': float(bar['high']),
            'low': float(bar['low']),
            'close': float(bar['close']),
            'atr': float(atr) if atr is not None else float('nan'),
            'entry': entry,
            'above_trend': bool(above.iloc[i]),
            'stop': stop,
            'features': features,
        })
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.set_index('ts')
    return out


def _cache_key(symbol: str, params: dict, df: pd.DataFrame, btc_df=None, start=None) -> str:
    blob = json.dumps({
        'v': SIGNALS_VERSION,
        'btc_last': str(btc_df.index[-1]) if btc_df is not None and len(btc_df) else None,
        'btc_first': str(btc_df.index[0]) if btc_df is not None and len(btc_df) else None,
        'params': params,
        'window': WINDOW_BARS,
        'start': str(start),
        'first': str(df.index[0]),
        'last': str(df.index[-1]),
        'n': len(df),
    }, sort_keys=True, default=str)
    digest = hashlib.sha1(blob.encode('utf-8')).hexdigest()[:12]
    return f"{symbol.replace('/', '_')}_{digest}.csv.gz"


def get_signals(symbol: str, df: pd.DataFrame, strategy, btc_df=None, start=None) -> pd.DataFrame:
    params = getattr(strategy, 'params', {}) or {}
    if df is None or len(df) <= warmup_bars(params):
        return pd.DataFrame()  # too little history (e.g. a young listing on Yahoo)
    path = os.path.join(SIGNALS_CACHE, _cache_key(symbol, params, df, btc_df, start))
    if os.path.exists(path) and os.path.getsize(path) < 64:
        return pd.DataFrame()  # cached empty pass
    if os.path.exists(path):
        cached = pd.read_csv(path, index_col=0, parse_dates=True, keep_default_na=False,
                             na_values={'atr': [''], 'stop': ['']})
        cached['entry'] = cached['entry'].astype(str).str.lower() == 'true'
        cached['above_trend'] = cached['above_trend'].astype(str).str.lower() == 'true'
        cached['features'] = cached['features'].fillna('').astype(str)
        return cached
    started = time.time()
    out = compute_signals(df, strategy, btc_df, start=start)
    os.makedirs(SIGNALS_CACHE, exist_ok=True)
    out.to_csv(path)
    print(f'  {symbol}: signals computed ({len(out)} bars, {time.time() - started:.0f}s)')
    return out
