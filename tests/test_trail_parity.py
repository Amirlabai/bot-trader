"""Live trail rules (BaseStrategy) must match the curator backtest (path_sim)."""

from __future__ import annotations

import os
import sys
import unittest

import numpy as np
import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
for path in (REPO, os.path.join(REPO, 'src')):
    if path not in sys.path:
        sys.path.insert(0, path)

from shared.path_sim import simulate_long_path
from shared.risk_sizing import size_long_from_equity
from strategies.moving_average import MovingAverageStrategy

RISK = {
    'equity_risk_pct': 0.01,
    'min_risk_fraction': 0.25,
    'min_notional_usd': 10.0,
    'max_notional_pct': 0.25,
}
SL_ATR, TRAIL_ATR, ARM_R = 2.0, 3.0, 1.0
ENTRY_IDX = 5


def _live_pnl(close, low, atr, start_cash):
    """Step bars through live check_risk_management; return realized pnl."""
    strat = MovingAverageStrategy({
        'sl_atr': SL_ATR, 'trail_atr': TRAIL_ATR, 'trail_arm_r': ARM_R,
        'trail_from_entry': True, 'skip_tp1': True, 'use_trailing': True,
    })
    entry = float(close[ENTRY_IDX])
    stop = entry - SL_ATR * atr[ENTRY_IDX]
    qty, *_rest, ok = size_long_from_equity(start_cash, start_cash, entry, stop, RISK)
    assert ok
    pos = {
        'entry_price': entry, 'side': 'LONG', 'stop_loss': stop,
        'initial_stop_loss': stop, 'entry_atr': float(atr[ENTRY_IDX]),
        'take_profit': 0.0,
    }
    for i in range(ENTRY_IDX + 1, len(close)):
        bar = pd.Series({'high': close[i] + 0.5, 'low': low[i], 'close': close[i]})
        sig = strat.check_risk_management(bar, float(atr[i]), pos)
        if not sig:
            continue
        if sig['action'] == 'sell':
            return round((pos['stop_loss'] - entry) * qty, 2)
        pos['stop_loss'] = sig['stop_loss']
    return None


def _sim_pnl(close, low, atr, start_cash):
    entry_mask = np.zeros(len(close), dtype=bool)
    entry_mask[ENTRY_IDX] = True
    out = simulate_long_path(
        entry_mask, close, low, atr, SL_ATR, TRAIL_ATR, ENTRY_IDX, start_cash, RISK,
        trail_arm_r=ARM_R,
    )
    assert out['closed_trades'] == 1
    return out['total_pnl']


class TrailParityTests(unittest.TestCase):
    def _check(self, close, atr):
        low = close - 0.5
        live = _live_pnl(close, low, atr, 10_000.0)
        sim = _sim_pnl(close, low, atr, 10_000.0)
        self.assertIsNotNone(live)
        self.assertAlmostEqual(live, sim, places=2)
        return live

    def test_armed_trail_exit_matches(self):
        # Run up well past 1R (R = 4), then fall through the trail. Live ATR drifts
        # so a live-ATR trail would diverge from the entry-frozen one.
        close = np.concatenate([np.full(6, 100.0), np.linspace(101, 120, 15), np.linspace(119, 95, 20)])
        atr = np.linspace(2.0, 4.0, len(close))
        self.assertGreater(self._check(close, atr), 0)

    def test_unarmed_exits_at_initial_stop(self):
        # Never reaches 1R, so no trail; exit at entry - 2 ATR.
        close = np.concatenate([np.full(6, 100.0), np.linspace(101, 103, 5), np.linspace(102, 90, 10)])
        atr = np.full(len(close), 2.0)
        self.assertLess(self._check(close, atr), 0)


if __name__ == '__main__':
    unittest.main()
