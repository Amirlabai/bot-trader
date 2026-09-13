import os
import sys
import unittest

import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
for path in (REPO, os.path.join(REPO, 'src')):
    if path not in sys.path:
        sys.path.insert(0, path)

from strategies.base_strategy import BaseStrategy
from strategies.moving_average import MovingAverageStrategy
from tests.test_ma_entry_filters import StubbedMA, _ohlcv, _series_like


class StubbedMAMacro(StubbedMA):
    def __init__(self, params, ema_fast, ema_slow, ema_trend, atr, adx, ema_macro=None):
        super().__init__(params, ema_fast, ema_slow, ema_trend, atr, adx)
        self._ema_macro = ema_macro

    def _ema(self, series, span):
        macro = int(self.params.get('macro_ema_window', 0) or 0)
        if macro > 0 and span == macro and self._ema_macro is not None:
            return self._ema_macro
        return super()._ema(series, span)


class DummyStrategy(BaseStrategy):
    def generate_signal(self, market_data, position_data):
        return {'action': 'hold', 'reason': 'Waiting'}


class LongOnlyBeTrendExitTests(unittest.TestCase):
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
            'long_only': True,
            'use_trailing': False,
            'trend_exit': True,
            'trend_exit_death_cross': True,
        }
        self.n = 40

    def _strategy(self, df, *, fast, slow, trend, atr=2.0, adx=30.0, params=None, macro=None):
        p = dict(self.params)
        if params:
            p.update(params)
        if macro is None:
            return StubbedMA(
                p,
                _series_like(df, fast),
                _series_like(df, slow),
                _series_like(df, trend),
                _series_like(df, atr),
                _series_like(df, adx),
            )
        return StubbedMAMacro(
            p,
            _series_like(df, fast),
            _series_like(df, slow),
            _series_like(df, trend),
            _series_like(df, atr),
            _series_like(df, adx),
            _series_like(df, macro),
        )

    def test_long_only_rejects_death_cross_short(self):
        vols = [1000.0] * (self.n - 1) + [2000.0]
        df = _ohlcv(self.n, close=90.0, volume=vols)
        fast = [11.0] * (self.n - 2) + [10.0, 8.0]
        slow = [10.0] * (self.n - 2) + [10.0, 10.0]
        strategy = self._strategy(df, fast=fast, slow=slow, trend=100.0)
        signal = strategy.generate_signal(df, position_data=None)
        self.assertEqual(signal['action'], 'hold')

    def test_trend_exit_on_close_below_trend_ema(self):
        vols = [1000.0] * self.n
        df = _ohlcv(self.n, close=90.0, volume=vols)
        fast = [10.0] * self.n
        slow = [10.0] * self.n
        strategy = self._strategy(df, fast=fast, slow=slow, trend=100.0)
        pos = {
            'side': 'LONG',
            'entry_price': 100.0,
            'stop_loss': 100.0,
            'take_profit': 102.0,
            'tp1_hit': True,
            'qty': 0.5,
            'initial_qty': 1.0,
        }
        df.loc[df.index[-1], 'low'] = 100.5
        df.loc[df.index[-1], 'high'] = 101.0
        signal = strategy.generate_signal(df, position_data=pos)
        self.assertEqual(signal['action'], 'sell')
        self.assertEqual(signal.get('quantity_pct'), 1.0)
        self.assertIn('close below trend EMA', signal['reason'])

    def test_trend_exit_on_death_cross(self):
        vols = [1000.0] * self.n
        df = _ohlcv(self.n, close=110.0, volume=vols)
        fast = [11.0] * (self.n - 2) + [10.0, 8.0]
        slow = [10.0] * (self.n - 2) + [10.0, 10.0]
        strategy = self._strategy(df, fast=fast, slow=slow, trend=100.0)
        pos = {
            'side': 'LONG',
            'entry_price': 100.0,
            'stop_loss': 100.0,
            'take_profit': 102.0,
            'tp1_hit': True,
            'qty': 0.5,
            'initial_qty': 1.0,
        }
        df.loc[df.index[-1], 'low'] = 100.5
        signal = strategy.generate_signal(df, position_data=pos)
        self.assertEqual(signal['action'], 'sell')
        self.assertEqual(signal.get('quantity_pct'), 1.0)
        self.assertIn('death cross', signal['reason'])

    def test_no_death_cross_exit_when_disabled(self):
        df = _ohlcv(self.n, close=110.0, volume=1000.0)
        fast = [11.0] * (self.n - 2) + [10.0, 8.0]
        slow = [10.0] * (self.n - 2) + [10.0, 10.0]
        strategy = self._strategy(
            df, fast=fast, slow=slow, trend=100.0,
            params={'trend_exit_death_cross': False, 'skip_tp1': True},
        )
        pos = {
            'side': 'LONG',
            'entry_price': 100.0,
            'stop_loss': 95.0,
            'take_profit': 0.0,
            'tp1_hit': False,
            'qty': 1.0,
            'initial_qty': 1.0,
        }
        df.loc[df.index[-1], 'low'] = 100.5
        signal = strategy.generate_signal(df, position_data=pos)
        self.assertEqual(signal['action'], 'hold')

    def test_exit_below_ema200_when_macro_exit(self):
        df = _ohlcv(self.n, close=105.0, volume=1000.0)
        fast = [10.0] * self.n
        slow = [10.0] * self.n
        strategy = self._strategy(
            df, fast=fast, slow=slow, trend=90.0, macro=110.0,
            params={
                'macro_ema_window': 8,
                'trend_exit_macro': True,
                'trend_exit_death_cross': False,
                'skip_tp1': True,
            },
        )
        pos = {
            'side': 'LONG',
            'entry_price': 100.0,
            'stop_loss': 90.0,
            'take_profit': 0.0,
            'tp1_hit': False,
            'qty': 1.0,
            'initial_qty': 1.0,
        }
        df.loc[df.index[-1], 'low'] = 104.0
        signal = strategy.generate_signal(df, position_data=pos)
        self.assertEqual(signal['action'], 'sell')
        self.assertIn('close below EMA8', signal['reason'])

    def test_skip_tp1_ignores_tp_wick(self):
        strat = DummyStrategy({'skip_tp1': True, 'use_trailing': False})
        pos = {
            'side': 'LONG',
            'entry_price': 100.0,
            'stop_loss': 96.0,
            'take_profit': 102.0,
            'tp1_hit': False,
            'qty': 1.0,
            'initial_qty': 1.0,
        }
        bar = pd.Series({'open': 100.0, 'high': 104.0, 'low': 99.0, 'close': 103.0})
        signal = strat.check_risk_management(bar, current_atr=2.0, position_data=pos)
        self.assertIsNone(signal)

    def test_no_trail_when_use_trailing_false(self):
        strat = DummyStrategy({'use_trailing': False})
        pos = {
            'side': 'LONG',
            'entry_price': 100.0,
            'stop_loss': 100.0,
            'take_profit': 102.0,
            'tp1_hit': True,
            'qty': 0.5,
            'initial_qty': 1.0,
        }
        bar = pd.Series({'open': 110.0, 'high': 112.0, 'low': 109.0, 'close': 111.0})
        signal = strat.check_risk_management(bar, current_atr=2.0, position_data=pos)
        self.assertIsNone(signal)

    def test_trail_still_updates_when_use_trailing_true(self):
        strat = DummyStrategy({'use_trailing': True})
        pos = {
            'side': 'LONG',
            'entry_price': 100.0,
            'stop_loss': 100.0,
            'take_profit': 102.0,
            'tp1_hit': True,
            'qty': 0.5,
            'initial_qty': 1.0,
        }
        bar = pd.Series({'open': 110.0, 'high': 112.0, 'low': 109.0, 'close': 111.0})
        signal = strat.check_risk_management(bar, current_atr=2.0, position_data=pos)
        self.assertIsNotNone(signal)
        self.assertEqual(signal['action'], 'hold')
        self.assertAlmostEqual(signal['stop_loss'], 111.0 - 1.5 * 2.0)
        self.assertIn('Trailing Stop', signal['reason'])

    def test_trail_atr_param_uses_current_atr(self):
        strat = DummyStrategy({'use_trailing': True, 'trail_atr': 2.5})
        pos = {
            'side': 'LONG',
            'entry_price': 100.0,
            'stop_loss': 100.0,
            'take_profit': 102.0,
            'tp1_hit': True,
            'qty': 0.5,
            'initial_qty': 1.0,
        }
        bar = pd.Series({'open': 110.0, 'high': 112.0, 'low': 109.0, 'close': 111.0})
        signal = strat.check_risk_management(bar, current_atr=2.0, position_data=pos)
        self.assertAlmostEqual(signal['stop_loss'], 111.0 - 2.5 * 2.0)

    def test_trail_from_entry_updates_without_tp1(self):
        strat = DummyStrategy({
            'trail_from_entry': True,
            'use_trailing': True,
            'skip_tp1': True,
            'trail_atr': 1.5,
        })
        pos = {
            'side': 'LONG',
            'entry_price': 100.0,
            'stop_loss': 97.0,
            'initial_stop_loss': 97.0,
            'take_profit': 0.0,
            'tp1_hit': False,
            'qty': 1.0,
            'initial_qty': 1.0,
        }
        bar = pd.Series({'open': 110.0, 'high': 112.0, 'low': 109.0, 'close': 111.0})
        signal = strat.check_risk_management(bar, current_atr=2.0, position_data=pos)
        self.assertIsNotNone(signal)
        self.assertEqual(signal['action'], 'hold')
        self.assertAlmostEqual(signal['stop_loss'], 111.0 - 1.5 * 2.0)
        self.assertIn('From Entry', signal['reason'])

    def test_trail_from_entry_ignores_tp_wick(self):
        strat = DummyStrategy({
            'trail_from_entry': True,
            'use_trailing': True,
            'trail_atr': 1.5,
        })
        pos = {
            'side': 'LONG',
            'entry_price': 100.0,
            'stop_loss': 97.0,
            'initial_stop_loss': 97.0,
            'take_profit': 102.0,
            'tp1_hit': False,
            'qty': 1.0,
            'initial_qty': 1.0,
        }
        # High pierces old TP1 level; should trail, not take TP1.
        bar = pd.Series({'open': 100.0, 'high': 104.0, 'low': 99.0, 'close': 103.0})
        signal = strat.check_risk_management(bar, current_atr=2.0, position_data=pos)
        self.assertIsNotNone(signal)
        self.assertEqual(signal['action'], 'hold')
        self.assertAlmostEqual(signal['stop_loss'], 103.0 - 1.5 * 2.0)

    def test_trail_from_entry_sl_uses_trailed_label(self):
        strat = DummyStrategy({'trail_from_entry': True, 'use_trailing': True})
        pos = {
            'side': 'LONG',
            'entry_price': 100.0,
            'stop_loss': 105.0,
            'initial_stop_loss': 97.0,
            'take_profit': 0.0,
            'tp1_hit': False,
            'qty': 1.0,
            'initial_qty': 1.0,
        }
        bar = pd.Series({'open': 106.0, 'high': 107.0, 'low': 104.0, 'close': 104.5})
        signal = strat.check_risk_management(bar, current_atr=2.0, position_data=pos)
        self.assertEqual(signal['action'], 'sell')
        self.assertIn('Trailed Stop', signal['reason'])

    def test_dual_wallet_config_flags(self):
        from config import TRADING_CONFIG

        self.assertEqual(
            set(TRADING_CONFIG),
            {
                'ma_crypto_long_trail',
                'ma_crypto_long_tp1',
                'ma_crypto_ls_trail',
                'ma_crypto_ls_tp1',
                'ma_commodities_long_trail',
                'ma_commodities_long_tp1',
                'ma_commodities_ls_trail',
                'ma_commodities_ls_tp1',
            },
        )
        long_trail = TRADING_CONFIG['ma_crypto_long_trail']['params']
        self.assertTrue(long_trail['long_only'])
        self.assertTrue(long_trail['trail_from_entry'])
        self.assertTrue(long_trail['skip_tp1'])

        long_tp1 = TRADING_CONFIG['ma_crypto_long_tp1']['params']
        self.assertTrue(long_tp1['long_only'])
        self.assertFalse(long_tp1['trail_from_entry'])
        self.assertFalse(long_tp1['skip_tp1'])

        ls_trail = TRADING_CONFIG['ma_crypto_ls_trail']['params']
        self.assertFalse(ls_trail['long_only'])
        self.assertTrue(ls_trail['trail_from_entry'])
        self.assertTrue(ls_trail['skip_tp1'])

        ls_tp1 = TRADING_CONFIG['ma_crypto_ls_tp1']['params']
        self.assertFalse(ls_tp1['long_only'])
        self.assertFalse(ls_tp1['trail_from_entry'])
        self.assertFalse(ls_tp1['skip_tp1'])

        com = TRADING_CONFIG['ma_commodities_long_trail']['params']
        self.assertEqual(com['sl_atr'], 3.0)
        self.assertEqual(com['trail_atr'], 3.0)
        self.assertEqual(com['trend_window'], 200)


if __name__ == '__main__':
    unittest.main()
