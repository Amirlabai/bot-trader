import os
import sys
import unittest

import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
for path in (REPO, os.path.join(REPO, 'src')):
    if path not in sys.path:
        sys.path.insert(0, path)

from shared.constants import (
    TP1_HIT_REASON_LONG,
    TP1_HIT_REASON_SHORT,
    STOP_LOSS_REASON_LONG,
    TRAILED_STOP_REASON_LONG,
)
from shared.exit_snapshots import resolve_close_fill_price
from shared.trade_exec import apply_exit
from strategies.base_strategy import BaseStrategy
from data_ingestion import yahoo_block_text, yahoo_ticker


class DummyStrategy(BaseStrategy):
    def generate_signal(self, market_data, position_data):
        return {'action': 'hold', 'reason': 'Waiting'}


def _long_pos(**kwargs):
    pos = {
        'entry_price': 100.0,
        'side': 'LONG',
        'stop_loss': 97.0,
        'take_profit': 103.0,
        'tp1_hit': False,
        'qty': 10.0,
        'initial_qty': 10.0,
    }
    pos.update(kwargs)
    return pos


def _short_pos(**kwargs):
    pos = {
        'entry_price': 100.0,
        'side': 'SHORT',
        'stop_loss': 103.0,
        'take_profit': 97.0,
        'tp1_hit': False,
        'qty': 10.0,
        'initial_qty': 10.0,
    }
    pos.update(kwargs)
    return pos


class WickExitTests(unittest.TestCase):
    def setUp(self):
        self.strategy = DummyStrategy()
        self.atr = 2.0

    def test_tp_wick_close_below_tp_takes_tp1(self):
        bar = pd.Series({'open': 100.0, 'high': 104.0, 'low': 99.0, 'close': 101.0})
        signal = self.strategy.check_risk_management(bar, self.atr, _long_pos())
        self.assertEqual(signal['reason'], TP1_HIT_REASON_LONG)
        self.assertEqual(signal['quantity_pct'], 0.5)
        self.assertEqual(signal['take_profit'], 103.0)

    def test_sl_wick_recovered_close_takes_sl(self):
        bar = pd.Series({'open': 100.0, 'high': 101.0, 'low': 96.0, 'close': 100.0})
        signal = self.strategy.check_risk_management(bar, self.atr, _long_pos())
        self.assertEqual(signal['quantity_pct'], 1.0)
        self.assertIn('Stop Loss Hit', signal['reason'])

    def test_same_bar_both_wicks_tp1_then_remainder_sl(self):
        bar = pd.Series({'open': 100.0, 'high': 104.0, 'low': 96.0, 'close': 98.0})
        first = self.strategy.check_risk_management(bar, self.atr, _long_pos())
        self.assertEqual(first['reason'], TP1_HIT_REASON_LONG)
        remainder = _long_pos(tp1_hit=True, stop_loss=100.0, qty=5.0)
        second = self.strategy.check_risk_management(bar, self.atr, remainder)
        self.assertIn('Stop Loss Hit', second['reason'])
        self.assertTrue(second['reason'].startswith(STOP_LOSS_REASON_LONG))

    def test_post_tp1_trail_uses_close_not_high(self):
        bar = pd.Series({'open': 110.0, 'high': 120.0, 'low': 109.0, 'close': 110.0})
        pos = _long_pos(tp1_hit=True, stop_loss=100.0, qty=5.0)
        signal = self.strategy.check_risk_management(bar, self.atr, pos)
        self.assertEqual(signal['action'], 'hold')
        self.assertAlmostEqual(signal['stop_loss'], 110.0 - 1.5 * self.atr)

    def test_post_tp1_sl_uses_trailed_label_once_sl_moved(self):
        bar = pd.Series({'open': 110.0, 'high': 111.0, 'low': 104.0, 'close': 110.0})
        pos = _long_pos(tp1_hit=True, stop_loss=107.0, qty=5.0)
        signal = self.strategy.check_risk_management(bar, self.atr, pos)
        self.assertTrue(signal['reason'].startswith(TRAILED_STOP_REASON_LONG))

    def test_short_tp_wick_close_above_tp(self):
        bar = pd.Series({'open': 100.0, 'high': 101.0, 'low': 96.0, 'close': 99.0})
        signal = self.strategy.check_risk_management(bar, self.atr, _short_pos())
        self.assertEqual(signal['reason'], TP1_HIT_REASON_SHORT)
        self.assertEqual(signal['quantity_pct'], 0.5)

    def test_short_sl_wick_recovered_close(self):
        bar = pd.Series({'open': 100.0, 'high': 104.0, 'low': 99.0, 'close': 100.0})
        signal = self.strategy.check_risk_management(bar, self.atr, _short_pos())
        self.assertEqual(signal['quantity_pct'], 1.0)
        self.assertIn('Short Stop Loss Hit', signal['reason'])

    def test_follow_up_risk_uses_passed_atr_not_recompute(self):
        idx = pd.date_range('2026-01-01', periods=1)
        market = pd.DataFrame(
            {'open': [100.0], 'high': [104.0], 'low': [96.0], 'close': [98.0]},
            index=idx,
        )
        pos = _long_pos(tp1_hit=True, stop_loss=100.0, qty=5.0)
        self.assertIsNone(self.strategy.follow_up_risk(market, pos))
        signal = self.strategy.follow_up_risk(market, pos, current_atr=2.0)
        self.assertTrue(signal['reason'].startswith(STOP_LOSS_REASON_LONG))

    def test_tp1_fill_is_take_profit_not_close(self):
        fill = resolve_close_fill_price(
            101.5, {'reason': TP1_HIT_REASON_LONG, 'take_profit': 103.0}, _long_pos(),
        )
        self.assertEqual(fill, 103.0)

    def test_sl_fill_is_stop_even_if_close_recovered(self):
        fill = resolve_close_fill_price(
            99.5, {'reason': 'Stop Loss Hit @ 97.0 (SL 97.0)'}, _long_pos(),
        )
        self.assertEqual(fill, 97.0)


class FakeLedger:
    def __init__(self, pos):
        self.pos = dict(pos)
        self.closed = []

    def get_position(self, strategy_id, symbol):
        return dict(self.pos) if self.pos else None

    def update_stop_loss(self, strategy_id, symbol, new_sl):
        if self.pos:
            self.pos['stop_loss'] = new_sl

    def mark_tp1_hit(self, strategy_id, symbol):
        if self.pos:
            self.pos['tp1_hit'] = True

    def update_position(self, strategy_id, symbol, qty, fill_price, fill_action, **kwargs):
        self.closed.append((qty, fill_price, kwargs.get('reason')))
        if self.pos:
            self.pos['qty'] = self.pos['qty'] - qty
            if self.pos['qty'] <= 1e-9:
                self.pos = None
        return True


class ApplyExitTests(unittest.TestCase):
    def test_duplicate_tp1_does_not_same_bar_sl(self):
        strategy = DummyStrategy()
        pos = _long_pos(tp1_hit=True, qty=5.0, initial_qty=10.0, stop_loss=100.0)
        ledger = FakeLedger(pos)
        idx = pd.date_range('2026-01-01', periods=1)
        market = pd.DataFrame(
            {'open': [100.0], 'high': [104.0], 'low': [96.0], 'close': [98.0]},
            index=idx,
        )
        signal = {'reason': TP1_HIT_REASON_LONG, 'quantity_pct': 0.5, 'current_atr': 2.0}
        apply_exit(
            ledger, strategy, 's', 'ADA/USDT', market, pos, signal, 'LONG', verbose=False,
        )
        self.assertEqual(ledger.closed, [])

    def test_tp1_leaves_remainder_open_same_bar(self):
        strategy = DummyStrategy()
        pos = _long_pos()
        ledger = FakeLedger(pos)
        idx = pd.date_range('2026-01-01', periods=1)
        market = pd.DataFrame(
            {'open': [100.0], 'high': [104.0], 'low': [96.0], 'close': [98.0]},
            index=idx,
        )
        signal = {
            'reason': TP1_HIT_REASON_LONG,
            'quantity_pct': 0.5,
            'stop_loss': 100.0,
            'take_profit': 103.0,
            'current_atr': 2.0,
        }
        apply_exit(
            ledger, strategy, 's', 'ADA/USDT', market, pos, signal, 'LONG', verbose=False,
        )
        self.assertEqual(len(ledger.closed), 1)
        self.assertEqual(ledger.closed[0][0], 5.0)
        self.assertIsNotNone(ledger.pos)
        self.assertAlmostEqual(ledger.pos['qty'], 5.0)


class YahooTickerTests(unittest.TestCase):
    def test_ticker_mapping(self):
        self.assertEqual(yahoo_ticker('BTC/USDT', 'crypto'), 'BTC-USD')
        self.assertEqual(yahoo_ticker('EUR/USD', 'forex'), 'EURUSD=X')
        self.assertEqual(yahoo_ticker('ADA/USDT', 'crypto'), 'ADA-USD')
        self.assertEqual(yahoo_ticker('EUR/GBP', 'forex'), 'EURGBP=X')
        self.assertEqual(yahoo_ticker('XAU/USD', 'commodity'), 'GC=F')
        self.assertEqual(yahoo_ticker('XAG/USD', 'commodity'), 'SI=F')
        self.assertEqual(yahoo_ticker('CL/USD', 'commodity'), 'CL=F')


class AssetTypeTests(unittest.TestCase):
    def test_asset_type_for_symbol(self):
        from shared.symbols import asset_type_for_symbol

        self.assertEqual(asset_type_for_symbol('BTC/USDT'), 'crypto')
        self.assertEqual(asset_type_for_symbol('EUR/USD'), 'forex')
        self.assertEqual(asset_type_for_symbol('XAU/USD'), 'commodity')
        self.assertEqual(asset_type_for_symbol('XAG/USD'), 'commodity')


class YahooProbeTextTests(unittest.TestCase):
    def test_block_phrases(self):
        self.assertTrue(yahoo_block_text('HTTP 429 Too Many Requests'))
        self.assertTrue(yahoo_block_text('rate limit exceeded'))
        self.assertFalse(yahoo_block_text(''))
        self.assertFalse(yahoo_block_text('no data for ticker'))
        self.assertFalse(yahoo_block_text('BTC-USD close 429.00'))


if __name__ == '__main__':
    unittest.main()
