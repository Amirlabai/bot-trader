"""Mid-cap runner screener filters (OHLCV + fundamentals)."""

from __future__ import annotations

from typing import Any

import pandas as pd

# Core screener parameters (plan SoT).
MIN_PRICE = 15.0
MIN_AVG_VOLUME_30 = 750_000
MAX_DIST_52W_HIGH = 0.03  # within 3%
MIN_PERF_6M = 0.20
RSI_PERIOD = 14
RSI_MIN = 55.0
RSI_MAX = 70.0
SMA_FAST = 50
SMA_SLOW = 200
MIN_MARKET_CAP = 2_000_000_000
MAX_MARKET_CAP = 30_000_000_000
MIN_REVENUE_GROWTH_YOY = 0.20
MAX_FLOAT_SHARES = 150_000_000  # optional gate when available


def rsi(series: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, pd.NA)
    return 100.0 - (100.0 / (1.0 + rs))


def ohlcv_screen(df: pd.DataFrame) -> dict[str, Any] | None:
    """Return metrics dict if OHLCV Core gates pass on the last bar; else None."""
    need = max(SMA_SLOW, 126, RSI_PERIOD, 30) + 5
    if df is None or df.empty or len(df) < need:
        return None
    mask = ohlcv_pass_mask(df)
    if mask.empty or not bool(mask.iloc[-1]):
        return None
    close = df['close'].astype(float)
    volume = df['volume'].astype(float)
    price = float(close.iloc[-1])
    avg_vol_30 = float(volume.iloc[-30:].mean())
    high_52w = float(close.iloc[-252:].max()) if len(close) >= 252 else float(close.max())
    dist_high = (high_52w - price) / high_52w if high_52w > 0 else 1.0
    perf_6m = float(close.iloc[-1] / close.iloc[-126] - 1.0)
    sma50 = float(close.rolling(SMA_FAST).mean().iloc[-1])
    sma200 = float(close.rolling(SMA_SLOW).mean().iloc[-1])
    rsi_val = float(rsi(close).iloc[-1])
    return {
        'price': round(price, 4),
        'avg_volume_30': int(round(avg_vol_30)),
        'dist_52w_high_pct': round(dist_high * 100.0, 2),
        'perf_6m_pct': round(perf_6m * 100.0, 2),
        'rsi_14': round(rsi_val, 2),
        'sma50': round(sma50, 4),
        'sma200': round(sma200, 4),
        'reasons': [
            f'price>{MIN_PRICE:g}',
            f'avgVol30>{MIN_AVG_VOLUME_30}',
            'within3pct52wHigh',
            f'perf6m>{MIN_PERF_6M:.0%}',
            f'rsi{RSI_MIN:g}-{RSI_MAX:g}',
            'close>sma50>sma200',
        ],
    }


def ohlcv_pass_mask(df: pd.DataFrame) -> pd.Series:
    """Per-bar boolean: True when Core OHLCV gates pass using only data through that bar."""
    need = max(SMA_SLOW, 126, RSI_PERIOD, 30) + 5
    if df is None or df.empty or not {'close', 'volume'}.issubset(df.columns):
        return pd.Series(dtype=bool)
    close = df['close'].astype(float)
    volume = df['volume'].astype(float)
    avg_vol_30 = volume.rolling(30, min_periods=30).mean()
    high_52w = close.rolling(252, min_periods=126).max()
    dist_high = (high_52w - close) / high_52w.replace(0.0, pd.NA)
    perf_6m = close / close.shift(126) - 1.0
    sma50 = close.rolling(SMA_FAST, min_periods=SMA_FAST).mean()
    sma200 = close.rolling(SMA_SLOW, min_periods=SMA_SLOW).mean()
    rsi_val = rsi(close)
    ok = (
        (close > MIN_PRICE)
        & (avg_vol_30 > MIN_AVG_VOLUME_30)
        & (dist_high >= 0)
        & (dist_high <= MAX_DIST_52W_HIGH)
        & (perf_6m > MIN_PERF_6M)
        & (close > sma50)
        & (sma50 > sma200)
        & (rsi_val >= RSI_MIN)
        & (rsi_val <= RSI_MAX)
    )
    out = ok.fillna(False).astype(bool)
    if len(out) >= need:
        out.iloc[:need] = False
    else:
        out[:] = False
    return out


def fundamentals_screen(info: dict | None) -> dict[str, Any] | None:
    """Return fundamentals metrics if Core gates pass; else None."""
    if not info:
        return None
    mcap = info.get('marketCap') or info.get('market_cap')
    if mcap is None:
        return None
    try:
        mcap_f = float(mcap)
    except (TypeError, ValueError):
        return None
    if not (MIN_MARKET_CAP <= mcap_f <= MAX_MARKET_CAP):
        return None

    rev = info.get('revenueGrowth')
    if rev is None:
        rev = info.get('revenue_growth')
    if rev is None:
        return None
    try:
        rev_f = float(rev)
    except (TypeError, ValueError):
        return None
    # yfinance usually stores as fraction (0.25 = 25%).
    if rev_f > 5:
        rev_f = rev_f / 100.0
    if rev_f <= MIN_REVENUE_GROWTH_YOY:
        return None

    out: dict[str, Any] = {
        'market_cap': int(mcap_f),
        'revenue_growth_yoy': round(rev_f, 4),
        'reasons': [
            'mcap2to30B',
            f'revYoY>{MIN_REVENUE_GROWTH_YOY:.0%}',
        ],
    }

    float_shares = info.get('floatShares') or info.get('float_shares')
    if float_shares is not None:
        try:
            fs = float(float_shares)
        except (TypeError, ValueError):
            fs = None
        if fs is not None:
            out['float_shares'] = int(fs)
            if fs > MAX_FLOAT_SHARES:
                return None
            out['reasons'].append(f'float<{MAX_FLOAT_SHARES // 1_000_000}M')

    return out


def merge_match(ticker: str, ohlcv: dict[str, Any], fundamentals: dict[str, Any]) -> dict[str, Any]:
    reasons = list(ohlcv.get('reasons') or []) + list(fundamentals.get('reasons') or [])
    row = {
        'ticker': ticker,
        **{k: v for k, v in ohlcv.items() if k != 'reasons'},
        **{k: v for k, v in fundamentals.items() if k != 'reasons'},
        'reasons': reasons,
    }
    return row
