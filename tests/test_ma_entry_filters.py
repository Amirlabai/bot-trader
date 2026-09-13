import os
import sys
import unittest

import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
for path in (REPO, os.path.join(REPO, 'src')):
    if path not in sys.path:
        sys.path.insert(0, path)

from strategies.moving_average import MovingAverageStrategy


def _ohlcv(n=40, close=100.0, volume=1000.0):
    idx = pd.date_range('2024-01-01', periods=n, freq='D')
    if isinstance(close, (list, tuple, pd.Series)):
        closes = pd.Series(list(close), index=idx, dtype=float)
    else:
        closes = pd.Series([float(close)] * n, index=idx)
    if isinstance(volume, (list, tuple, pd.Series)):
        volumes = pd.Series(list(volume), index=idx, dtype=float)
    else:
        volumes = pd.Series([float(volume)] * n, index=idx)
    return pd.DataFrame(
        {
            'open': closes,
            'high': closes + 1.0,
            'low': closes - 1.0,
            'close': closes,
            'volume': volumes,
        },
        index=idx,
    )


class StubbedMA(MovingAverageStrategy):
    """Inject indicator series so entry-filter gates can be asserted directly."""

    def __init__(self, params, ema_fast, ema_slow, ema_trend, atr, adx):
        super().__init__(params)
        self._ema_fast = ema_fast
        self._ema_slow = ema_slow
        self._ema_trend = ema_trend
        self._atr = atr
        self._adx = adx

    def _ema(self, series, span):
        if span == self.params.get('short_window', 12):
            return self._ema_fast
        if span == self.params.get('long_window', 24):
            return self._ema_slow
        return self._ema_trend

    def _calculate_atr(self, data, period=14):
        return self._atr

    def _calculate_adx(self, data, period=14):
        return self._adx


def _series_like(df, values):
    if isinstance(values, (int, float)):
        return pd.Series([float(values)] * len(df), index=df.index)
    return pd.Series(list(values), index=df.index, dtype=float)


class MAEntryFilterTests(unittest.TestCase):
    def setUp(self):
        self.params = {
            'short_window': 3,
            'long_window': 5,
            'trend_window': 8,
            'adx_period': 3,
            'adx_min': 22,
            'vol_ma_period': 5,
            'vol_mult': 1.2,
            'atr_buffer': 0.2,
        }
        self.n = 40

    def _strategy(self, df, *, fast, slow, trend, atr=2.0, adx=30.0):
        return StubbedMA(
            self.params,
            _series_like(df, fast),
            _series_like(df, slow),
            _series_like(df, trend),
            _series_like(df, atr),
            _series_like(df, adx),
        )

    def _long_cross_series(self, n, *, fast_last=12.0, slow_last=10.0):
        """Prev bar flat/below; last bar golden cross with clear separation."""
        fast = [9.0] * (n - 2) + [10.0, fast_last]
        slow = [10.0] * (n - 2) + [10.0, slow_last]
        return fast, slow

    def test_golden_cross_passes_all_filters(self):
        vols = [1000.0] * (self.n - 1) + [2000.0]
        df = _ohlcv(self.n, close=110.0, volume=vols)
        fast, slow = self._long_cross_series(self.n)
        strategy = self._strategy(df, fast=fast, slow=slow, trend=100.0, atr=2.0, adx=30.0)
        signal = strategy.generate_signal(df, position_data=None)
        self.assertEqual(signal['action'], 'buy')
        self.assertTrue(signal.get('is_entry'))
        self.assertIn('Golden Cross', signal['reason'])

    def test_blocked_when_adx_low(self):
        vols = [1000.0] * (self.n - 1) + [2000.0]
        df = _ohlcv(self.n, close=110.0, volume=vols)
        fast, slow = self._long_cross_series(self.n)
        strategy = self._strategy(df, fast=fast, slow=slow, trend=100.0, atr=2.0, adx=15.0)
        signal = strategy.generate_signal(df, position_data=None)
        self.assertEqual(signal['action'], 'hold')

    def test_blocked_when_volume_low(self):
        vols = [1000.0] * self.n  # last bar not above 1.0x SMA
        df = _ohlcv(self.n, close=110.0, volume=vols)
        fast, slow = self._long_cross_series(self.n)
        strategy = self._strategy(df, fast=fast, slow=slow, trend=100.0, atr=2.0, adx=30.0)
        # Need volume strictly above average; equal fails with vol_mult 1.0
        strategy.params['vol_mult'] = 1.0
        signal = strategy.generate_signal(df, position_data=None)
        self.assertEqual(signal['action'], 'hold')

    def test_forex_zero_volume_skips_volume_gate(self):
        vols = [0.0] * self.n
        df = _ohlcv(self.n, close=110.0, volume=vols)
        fast, slow = self._long_cross_series(self.n)
        strategy = self._strategy(df, fast=fast, slow=slow, trend=100.0, atr=2.0, adx=30.0)
        signal = strategy.generate_signal(df, position_data=None)
        self.assertEqual(signal['action'], 'buy')

    def test_blocked_against_trend(self):
        vols = [1000.0] * (self.n - 1) + [2000.0]
        df = _ohlcv(self.n, close=90.0, volume=vols)
        fast, slow = self._long_cross_series(self.n)
        strategy = self._strategy(df, fast=fast, slow=slow, trend=100.0, atr=2.0, adx=30.0)
        signal = strategy.generate_signal(df, position_data=None)
        self.assertEqual(signal['action'], 'hold')

    def test_blocked_when_atr_buffer_fails(self):
        vols = [1000.0] * (self.n - 1) + [2000.0]
        df = _ohlcv(self.n, close=110.0, volume=vols)
        # Cross exists but separation 0.1 < 0.2 * ATR(2.0) = 0.4
        fast = [9.0] * (self.n - 2) + [10.0, 10.1]
        slow = [10.0] * (self.n - 2) + [10.0, 10.0]
        strategy = self._strategy(df, fast=fast, slow=slow, trend=100.0, atr=2.0, adx=30.0)
        signal = strategy.generate_signal(df, position_data=None)
        self.assertEqual(signal['action'], 'hold')

    def test_death_cross_passes_all_filters(self):
        vols = [1000.0] * (self.n - 1) + [2000.0]
        df = _ohlcv(self.n, close=90.0, volume=vols)
        fast = [11.0] * (self.n - 2) + [10.0, 8.0]
        slow = [10.0] * (self.n - 2) + [10.0, 10.0]
        strategy = self._strategy(df, fast=fast, slow=slow, trend=100.0, atr=2.0, adx=30.0)
        signal = strategy.generate_signal(df, position_data=None)
        self.assertEqual(signal['action'], 'sell')
        self.assertTrue(signal.get('is_entry'))


if __name__ == '__main__':
    unittest.main()
