"""Entry-bar context features for research (copied from asset-trail shared/trade_features.py).

Daily bars: every *_BARS constant counts days. Records only; live code never imports this.
"""

from __future__ import annotations

import os

import pandas as pd


LEARNING_DIR = 'learning'
BACKFILL_FILE = 'backfill_trades.jsonl'
TREND_SPAN = 150
ATR_PERIOD = 14
SLOPE_BARS = 10
RET_BARS = 30
VOL_BARS = 20
BTC_SYMBOL = 'BTC/USDT'


def learning_dir(data_dir: str) -> str:
    return os.path.join(data_dir, LEARNING_DIR)


def r_multiple(entry, initial_stop, exit_price):
    """Risk units for one close. None when initial risk is missing or not positive."""
    try:
        entry_f = float(entry)
        stop_f = float(initial_stop)
        exit_f = float(exit_price)
    except (TypeError, ValueError):
        return None
    risk = entry_f - stop_f
    if risk <= 0:
        return None
    return (exit_f - entry_f) / risk


def _num(value):
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isnull(f):
        return None
    return f


def _series_at(series, offset=1):
    if series is None or not hasattr(series, 'iloc') or len(series) < offset:
        return None
    return _num(series.iloc[-offset])


def _atr(frame: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    prev_close = frame['close'].shift(1)
    tr = pd.concat(
        [
            frame['high'] - frame['low'],
            (frame['high'] - prev_close).abs(),
            (frame['low'] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(window=period).mean()


def _naive_utc(ts) -> pd.Timestamp:
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_convert('UTC').tz_localize(None)
    return ts


def btc_regime(btc_data, at) -> dict:
    """BTC close vs its EMA150 at the bar `at` (market regime). Empty when unknown."""
    if btc_data is None or getattr(btc_data, 'empty', True):
        return {}
    try:
        index = btc_data.index
        if getattr(index, 'tz', None) is not None:
            btc_data = btc_data.copy()
            btc_data.index = index.tz_convert('UTC').tz_localize(None)
        frame = btc_data.loc[btc_data.index <= _naive_utc(at)].tail(1000)
        if len(frame) < TREND_SPAN + 2:
            return {}
        ema = frame['close'].ewm(span=TREND_SPAN, adjust=False).mean()
        atr = _atr(frame)
        close = float(frame['close'].iloc[-1])
        ema_now = float(ema.iloc[-1])
        atr_now = _num(atr.iloc[-1])
        out = {'btc_above_trend': bool(close > ema_now)}
        if atr_now and atr_now > 0:
            out['btc_trend_ext_atr'] = (close - ema_now) / atr_now
        if len(frame) > RET_BARS:
            past = float(frame['close'].iloc[-RET_BARS - 1])
            if past > 0:
                out['btc_ret_30'] = close / past - 1.0
        return out
    except Exception as exc:
        print(f'  Learning: BTC regime skipped: {exc}')
        return {}


def entry_features(market_data, signal, btc_data=None) -> dict:
    """Context at the entry bar, from the indicators the signal already carries."""
    try:
        close = float(market_data['close'].iloc[-1])
        indicators = signal.get('indicators') or {}
        atr = _num(signal.get('current_atr'))
        ema_trend = indicators.get('ema_trend')
        ema_fast = indicators.get('ema_fast')
        ema_slow = indicators.get('ema_slow')
        trend_now = _series_at(ema_trend)
        feats: dict = {}
        if atr and close > 0:
            feats['atr_pct'] = atr / close
        if atr and trend_now is not None:
            feats['trend_ext_atr'] = (close - trend_now) / atr
        trend_then = _series_at(ema_trend, SLOPE_BARS + 1)
        if trend_now is not None and trend_then:
            feats['trend_slope_pct'] = trend_now / trend_then - 1.0
        fast_now = _series_at(ema_fast)
        slow_now = _series_at(ema_slow)
        if atr and fast_now is not None and slow_now is not None:
            feats['cross_gap_atr'] = (fast_now - slow_now) / atr
        if len(market_data) > RET_BARS:
            past = float(market_data['close'].iloc[-RET_BARS - 1])
            if past > 0:
                feats['ret_30_bars'] = close / past - 1.0
        if 'volume' in market_data.columns and len(market_data) > VOL_BARS:
            vol = market_data['volume']
            mean = float(vol.iloc[-VOL_BARS - 1:-1].mean())
            if mean > 0:
                feats['volume_ratio'] = float(vol.iloc[-1]) / mean
        stop = _num(signal.get('stop_loss'))
        if stop and close > 0 and stop < close:
            feats['risk_pct'] = (close - stop) / close
        ts = pd.Timestamp(market_data.index[-1])
        feats['weekday'] = int(_naive_utc(ts).weekday())
        feats.update(shape_features(market_data, ema_fast, ema_slow, atr))
        feats.update(btc_regime(btc_data, ts))
        return feats
    except Exception as exc:
        print(f'  Learning: entry features skipped: {exc}')
        return {}


CROSS_BARS = 60
HIGH_BARS = 50
ATR_CHANGE_BARS = 30
SHORT_RET_BARS = 6
SLOW_TREND_SPAN = 300


def shape_features(market_data, ema_fast, ema_slow, atr) -> dict:
    """Chop, breakout, volatility change and signal-bar shape. Empty pieces are skipped."""
    out: dict = {}
    try:
        close = float(market_data['close'].iloc[-1])
        bar = market_data.iloc[-1]
        if ema_fast is not None and ema_slow is not None and len(ema_fast) > CROSS_BARS:
            sign = (ema_fast - ema_slow).iloc[-CROSS_BARS - 1:] > 0
            out['cross_count_60'] = int((sign != sign.shift(1)).iloc[1:].sum())
        if atr and atr > 0:
            high_50 = float(market_data['high'].iloc[-HIGH_BARS:].max())
            out['dist_high_50_atr'] = (high_50 - close) / atr
            out['body_atr'] = (close - float(bar['open'])) / atr
            if len(market_data) > ATR_CHANGE_BARS + ATR_PERIOD:
                atr_then = _num(_atr(market_data).iloc[-ATR_CHANGE_BARS - 1])
                if atr_then and atr_then > 0:
                    out['atr_change_30'] = atr / atr_then
            if len(market_data) > SLOW_TREND_SPAN:
                ema_slow_trend = float(
                    market_data['close'].ewm(span=SLOW_TREND_SPAN, adjust=False).mean().iloc[-1]
                )
                out['ext_ema300_atr'] = (close - ema_slow_trend) / atr
        span = float(bar['high']) - float(bar['low'])
        if span > 0:
            out['close_pos'] = (close - float(bar['low'])) / span
        if len(market_data) > SHORT_RET_BARS:
            past = float(market_data['close'].iloc[-SHORT_RET_BARS - 1])
            if past > 0:
                out['ret_6_bars'] = close / past - 1.0
    except Exception as exc:
        print(f'  Learning: shape features skipped: {exc}')
    return out
