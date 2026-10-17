import os
import sys
import unittest

import numpy as np
import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
for path in (REPO, os.path.join(REPO, 'src')):
    if path not in sys.path:
        sys.path.insert(0, path)

from shared import mtf
from shared.weekly_trend import weekly_trend_flags


def ema(series, span):
    return series.ewm(span=span, adjust=False).mean()


def make_df(n=400, seed=1, start='2024-01-01'):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.001, 0.02, n)))
    idx = pd.date_range(start, periods=n, freq='D')
    return pd.DataFrame({
        'open': close, 'high': close * 1.01, 'low': close * 0.99, 'close': close, 'volume': 1.0,
    }, index=idx)


class MtfTests(unittest.TestCase):
    def test_daily_tf_is_identity(self):
        df = make_df()
        out = mtf.ema_on_tf(df, 20, 'D', ema)
        pd.testing.assert_series_equal(out, ema(df['close'], 20), check_names=False, check_freq=False)

    def test_weekly_trend_matches_weekly_trend_module(self):
        df = make_df()
        bull, bear = mtf.trend_flags(df, 10, 'W', ema)
        wb, wbear = weekly_trend_flags(df['close'], 10, ema)
        self.assertTrue((bull == wb).all())
        self.assertTrue((bear == wbear).all())

    def test_no_lookahead(self):
        df = make_df(n=400)
        for tf in ('W', 'M'):
            for cut in (250, 301, 333):  # includes mid-week and mid-month cuts
                short = df.iloc[:cut]
                for name, fn in (
                    ('ema', lambda d: mtf.ema_on_tf(d, 5, tf, ema)),
                    ('atr', lambda d: mtf.atr_on_tf(d, 5, tf)),
                    ('bull', lambda d: mtf.trend_flags(d, 5, tf, ema)[0].astype(float)),
                    ('up', lambda d: mtf.cross_events(d, 3, 6, tf, ema)[0].astype(float)),
                ):
                    full = fn(df).iloc[:cut]
                    part = fn(short)
                    pd.testing.assert_series_equal(
                        full, part, check_names=False, check_freq=False,
                        obj=f'{name} tf={tf} cut={cut}',
                    )

    def test_open_period_not_used(self):
        df = make_df(n=40, start='2026-09-20')  # starts Sunday, ends mid-week
        bars = mtf.completed_ohlc(df, 'W')
        self.assertLessEqual(bars.index[-1], df.index[-1].normalize())
        self.assertEqual(bars.index[-1].dayofweek, 6)
        mbars = mtf.completed_ohlc(df, 'M')
        self.assertTrue(all(ts.is_month_end for ts in mbars.index))

    def test_cross_event_only_on_label_day(self):
        df = make_df(n=300, seed=7)
        up, down = mtf.cross_events(df, 3, 8, 'W', ema)
        for ts in df.index[up | down]:
            self.assertEqual(ts.dayofweek, 6)
        self.assertGreater(int(up.sum()), 0)

    def test_exit_flags_modes(self):
        df = make_df()
        self.assertFalse(mtf.exit_flags(df, 'stop_only', 'W', 3, 8, 10, ema).any())
        self.assertTrue(mtf.exit_flags(df, 'cross', 'D', 3, 8, 10, ema).any())
        self.assertTrue(mtf.exit_flags(df, 'trend', 'D', 3, 8, 10, ema).any())

    def test_bad_tf_raises(self):
        with self.assertRaises(ValueError):
            mtf.check_tf('4H')


if __name__ == '__main__':
    unittest.main()
