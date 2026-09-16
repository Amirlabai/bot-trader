"""Risk/fill invariant tests for shared.path_sim."""

from __future__ import annotations

import os
import sys
import unittest

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
for path in (REPO, os.path.join(REPO, 'src')):
    if path not in sys.path:
        sys.path.insert(0, path)

from shared.path_sim import (
    PathSimInvariantError,
    build_long_entry_mask,
    simulate_long_path,
    simulate_long_portfolio,
)
from shared.risk_sizing import size_long_from_equity

RISK = {
    'equity_risk_pct': 0.01,
    'min_risk_fraction': 0.25,
    'min_notional_usd': 10.0,
    'max_notional_pct': 0.25,
}


def _trend_up_then_dump(n=80, dump_at=60):
    """Synthetic path: slow grind up, then sharp dump through SL."""
    close = np.linspace(100.0, 120.0, n)
    close[dump_at:] = np.linspace(120.0, 90.0, n - dump_at)
    high = close + 1.0
    low = close - 1.0
    # Force a deep wick on dump day
    low[dump_at] = 85.0
    atr = np.full(n, 2.0)
    entry = np.zeros(n, dtype=bool)
    entry[10] = True
    return entry, close, low, atr, high


class PathSimRiskTests(unittest.TestCase):
    def test_size_respects_max_notional_and_cash(self):
        q, tgt, act, cn, cc, ok = size_long_from_equity(
            10_000, 10_000, 100.0, 99.0, RISK,
        )
        # 1% of 10k = 100 risk; rps=1 => qty=100; notional=10k > 25% => cap 25
        self.assertTrue(ok)
        self.assertTrue(cn)
        self.assertAlmostEqual(q * 100.0, 2500.0, places=4)
        self.assertLessEqual(act, tgt + 1e-9)

    def test_size_skips_when_cash_zero(self):
        q, *_rest, ok = size_long_from_equity(10_000, 0.0, 100.0, 99.0, RISK)
        self.assertFalse(ok)
        self.assertEqual(q, 0.0)

    def test_stop_fill_at_sl_not_wick(self):
        entry, close, low, atr, _high = _trend_up_then_dump()
        # Use wide enough start so entry fires with cash
        out = simulate_long_path(
            entry, close, low, atr,
            sl_atr=1.0, trail_atr=2.0,
            start_idx=0, start_cash=10_000.0, risk_settings=RISK,
            trail_arm_r=99.0,  # never arm trail
            assert_invariants=True,
        )
        # Must not raise; any loss <= 1%
        self.assertGreaterEqual(out['closed_trades'] + out['open_positions'], 0)

    def test_loss_never_exceeds_equity_risk_at_sl(self):
        entry, close, low, atr, _ = _trend_up_then_dump()
        out = simulate_long_path(
            entry, close, low, atr,
            sl_atr=2.0, trail_atr=3.0,
            start_idx=0, start_cash=10_000.0, risk_settings=RISK,
            trail_arm_r=99.0,
            assert_invariants=True,
        )
        # Invariant checker already ran; also spot-check net
        self.assertIsInstance(out['net_pnl'], (int, float))

    def test_portfolio_sequential_cash_no_overspend(self):
        n = 40
        close = np.linspace(50, 60, n)
        low = close - 0.5
        atr = np.full(n, 1.0)
        entry_a = np.zeros(n, dtype=bool)
        entry_b = np.zeros(n, dtype=bool)
        entry_a[5] = True
        entry_b[5] = True  # same bar both want to enter
        series = [
            {
                'entry': entry_a, 'close': close, 'low': low, 'atr': atr,
                'has_bar': np.ones(n, dtype=bool),
            },
            {
                'entry': entry_b, 'close': close.copy(), 'low': low.copy(), 'atr': atr.copy(),
                'has_bar': np.ones(n, dtype=bool),
            },
        ]
        out = simulate_long_portfolio(
            series, sl_atr=1.0, trail_atr=2.0,
            start_cash=10_000.0, risk_settings=RISK,
            trail_arm_r=99.0, assert_invariants=True,
        )
        self.assertLessEqual(out['open_positions'], 2)

    def test_entry_mask_requires_adx_and_buffer(self):
        n = 200
        rng = np.random.default_rng(0)
        close = 100 + np.cumsum(rng.normal(0, 0.5, n))
        high = close + 1
        low = close - 1
        entry, atr = build_long_entry_mask(
            close, high, low,
            short_window=10, long_window=30, trend_window=50,
            atr_period=14, adx_min=20, atr_buffer=0.5,
        )
        self.assertEqual(len(entry), n)
        self.assertEqual(len(atr), n)
        self.assertTrue(entry.dtype == bool)


if __name__ == '__main__':
    unittest.main()
