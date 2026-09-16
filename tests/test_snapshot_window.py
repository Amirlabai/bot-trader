import os
import sys
import unittest

import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
for path in (REPO, os.path.join(REPO, 'src')):
    if path not in sys.path:
        sys.path.insert(0, path)

from shared.exit_snapshots import (
    SNAPSHOT_BAR_CAP,
    _choose_display_frame,
    _frame_from_entry,
    build_close_snapshot,
    build_open_snapshot,
)


def _synthetic_daily(n: int, start='2024-01-02') -> pd.DataFrame:
    idx = pd.bdate_range(start=start, periods=n)
    close = pd.Series(range(100, 100 + n), index=idx, dtype=float)
    return pd.DataFrame({
        'open': close - 0.5,
        'high': close + 1.0,
        'low': close - 1.0,
        'close': close,
        'volume': 1_000_000.0,
    })


class SnapshotWindowTests(unittest.TestCase):
    def test_from_entry_to_exit(self):
        df = _synthetic_daily(100)
        entry = str(df.index[40].date())
        framed = _frame_from_entry(df, entry, fallback_n=20)
        self.assertEqual(framed.index[0].date(), df.index[40].date())
        self.assertEqual(framed.index[-1].date(), df.index[-1].date())
        self.assertEqual(len(framed), 60)

    def test_daily_under_cap(self):
        df = _synthetic_daily(40)
        display, tf = _choose_display_frame(df, cap=60)
        self.assertEqual(tf, '1d')
        self.assertEqual(len(display), 40)

    def test_rolls_to_weekly(self):
        df = _synthetic_daily(120)
        display, tf = _choose_display_frame(df, cap=60)
        self.assertEqual(tf, '1wk')
        self.assertLessEqual(len(display), 60)

    def test_rolls_to_monthly_may_exceed_cap(self):
        # ~10y business days forces monthly when weekly still > small cap
        df = _synthetic_daily(2600, start='2016-01-04')
        display, tf = _choose_display_frame(df, cap=20)
        self.assertEqual(tf, '1mo')
        self.assertGreater(len(display), 0)

    def test_build_close_snapshot_sets_timeframe(self):
        df = _synthetic_daily(80)
        entry = str(df.index[0].date())
        pos = {
            'entry_price': 100.0,
            'entry_date': entry,
            'stop_loss': 90.0,
            'take_profit': 0.0,
        }
        snap = build_close_snapshot(df, {'reason': 'Stop'}, pos, fill_price=95.0)
        self.assertEqual(snap['timeframe'], '1wk')  # 80 daily > 60 cap
        self.assertEqual(snap['entry_date'], entry)
        self.assertLessEqual(len(snap['candles']), SNAPSHOT_BAR_CAP)
        self.assertEqual(snap['bar_cap'], SNAPSHOT_BAR_CAP)

    def test_short_hold_stays_daily_from_entry(self):
        df = _synthetic_daily(40)
        entry = str(df.index[5].date())
        pos = {
            'entry_price': 100.0,
            'entry_date': entry,
            'stop_loss': 90.0,
            'take_profit': 0.0,
        }
        snap = build_close_snapshot(df, {'reason': 'Stop'}, pos, fill_price=95.0)
        self.assertEqual(snap['timeframe'], '1d')
        self.assertEqual(snap['candles'][0]['date'], entry)

    def test_build_open_snapshot_entry_to_now(self):
        df = _synthetic_daily(80)
        entry = str(df.index[10].date())
        pos = {
            'entry_price': 110.0,
            'entry_date': entry,
            'stop_loss': 100.0,
            'take_profit': 120.0,
            'side': 'LONG',
        }
        snap = build_open_snapshot(df, pos)
        self.assertEqual(snap['exit_kind'], 'open')
        self.assertEqual(snap['entry_date'], entry)
        self.assertEqual(snap['stop_loss'], 100.0)
        self.assertAlmostEqual(snap['exit_price'], float(df['close'].iloc[-1]))
        self.assertEqual(snap['timeframe'], '1wk')
        self.assertGreaterEqual(snap['candles'][0]['date'], entry)

    def test_stop_exit_snapshot_sl_matches_fill(self):
        df = _synthetic_daily(40)
        entry = str(df.index[5].date())
        pos = {
            'entry_price': 100.0,
            'entry_date': entry,
            'stop_loss': 90.0,  # replayed / stale
            'take_profit': 0.0,
        }
        reason = 'Trailed Stop Hit @ 95.0 (SL 95.0)'
        snap = build_close_snapshot(
            df, {'reason': 'Waiting'}, pos, fill_price=95.0, close_reason=reason,
        )
        self.assertEqual(snap['exit_kind'], 'trailed_stop')
        self.assertAlmostEqual(snap['exit_price'], 95.0)
        self.assertAlmostEqual(snap['stop_loss'], 95.0)
        self.assertAlmostEqual(snap['stop_loss_at_exit'], 95.0)


if __name__ == '__main__':
    unittest.main()
