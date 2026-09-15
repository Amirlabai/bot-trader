import os
import sys
import unittest

import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
for path in (REPO, os.path.join(REPO, 'src')):
    if path not in sys.path:
        sys.path.insert(0, path)

from shared.stocks_screener import fundamentals_screen, ohlcv_screen
from shared.stocks_universe import merge_active_with_open
from shared.symbols import asset_type_for_symbol, is_stock_symbol
from shared.us_market_calendar import is_us_equity_trading_day
from datetime import date


class StocksSymbolTests(unittest.TestCase):
    def test_stock_tickers(self):
        self.assertTrue(is_stock_symbol('NVDA'))
        self.assertTrue(is_stock_symbol('BRK-B'))
        self.assertFalse(is_stock_symbol('BTC/USDT'))
        self.assertEqual(asset_type_for_symbol('AXON'), 'stock')
        self.assertEqual(asset_type_for_symbol('BTC/USDT'), 'crypto')


class StocksScreenerTests(unittest.TestCase):
    def test_ohlcv_rejects_short_series(self):
        df = pd.DataFrame({'close': [20.0] * 50, 'volume': [1_000_000] * 50})
        self.assertIsNone(ohlcv_screen(df))

    def test_fundamentals_mcap_and_rev(self):
        ok = fundamentals_screen({
            'marketCap': 5_000_000_000,
            'revenueGrowth': 0.25,
            'floatShares': 80_000_000,
        })
        self.assertIsNotNone(ok)
        self.assertEqual(ok['market_cap'], 5_000_000_000)

        bad = fundamentals_screen({
            'marketCap': 100_000_000_000,
            'revenueGrowth': 0.25,
        })
        self.assertIsNone(bad)

    def test_merge_keeps_open_off_screen(self):
        matches = [{'ticker': 'AXON'}]
        active, kept = merge_active_with_open(matches, open_symbols=['DECK', 'AXON'])
        self.assertEqual(active[0], 'AXON')
        self.assertIn('DECK', active)
        self.assertEqual(kept, ['DECK'])


class UsCalendarTests(unittest.TestCase):
    def test_weekend_closed(self):
        self.assertFalse(is_us_equity_trading_day(date(2026, 9, 12)))  # Saturday
        self.assertTrue(is_us_equity_trading_day(date(2026, 9, 15)))  # Tuesday


if __name__ == '__main__':
    unittest.main()
