import os
import sys
import unittest

import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
for path in (REPO, os.path.join(REPO, 'src')):
    if path not in sys.path:
        sys.path.insert(0, path)

from shared.curated_params import merge_effective_params_for_market
from shared.weekly_trend import weekly_trend_flags


def _flat_ema(series, span):
    return pd.Series(100.0, index=series.index)


class WeeklyTrendTests(unittest.TestCase):
    def _closes(self, end: str) -> pd.Series:
        idx = pd.date_range('2026-09-20', end, freq='D')
        # Completed weeks through Sun 2026-10-04 close at 50 (below the EMA).
        # Mon 2026-10-05 onward closes at 200. That week is not complete until Sun 2026-10-11.
        values = []
        for ts in idx:
            values.append(200.0 if ts >= pd.Timestamp('2026-10-05') else 50.0)
        return pd.Series(values, index=idx)

    def test_open_week_stays_off_through_saturday(self):
        close = self._closes('2026-10-10')
        bull, _bear = weekly_trend_flags(close, 2, _flat_ema)
        self.assertFalse(bool(bull.loc['2026-10-04']))
        self.assertFalse(bool(bull.loc['2026-10-10']))
        self.assertEqual(bool(bull.loc['2026-10-10']), bool(bull.loc['2026-10-04']))

    def test_sunday_close_then_forward_fills(self):
        close = self._closes('2026-10-11')
        close.loc['2026-10-11'] = 200.0
        bull, _bear = weekly_trend_flags(close, 2, _flat_ema)
        self.assertFalse(bool(bull.loc['2026-10-10']))
        self.assertTrue(bool(bull.loc['2026-10-11']))

    def test_merge_copies_trend_weekly_from_template(self):
        curated = {
            'templates': {'crypto': {'params': {'trend_weekly': True, 'trend_window': 150}}},
            'symbols': {},
        }
        out = merge_effective_params_for_market({}, curated, 'XRP/USDT', 'crypto')
        self.assertTrue(out['trend_weekly'])
        self.assertEqual(out['trend_window'], 150)


if __name__ == '__main__':
    unittest.main()
