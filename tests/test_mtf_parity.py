"""Live MovingAverageStrategy must fire entries/exits on the same bars as path_sim.build_signals."""

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

from shared.path_sim import build_signals, effective_tfs, gate_allows, simulate_long_path
from strategies.moving_average import MovingAverageStrategy

RISK = {'equity_risk_pct': 0.01, 'min_risk_fraction': 0.25, 'min_notional_usd': 10.0, 'max_notional_pct': 0.25}
BASE = {
    'short_window': 3, 'long_window': 8, 'trend_window': 5, 'atr_period': 4,
    'sl_atr': 2.0, 'trail_atr': 3.0, 'adx_min': 0.0, 'vol_mult': 0.0, 'atr_buffer': 0.0,
    'long_only': True, 'trail_from_entry': True, 'skip_tp1': True,
    'trail_arm_r': 1e9,  # never trail: isolate signal behavior
}
WARM = 190


def make_df(n=340, seed=3):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0008, 0.025, n)))
    idx = pd.date_range('2024-01-01', periods=n, freq='D')
    return pd.DataFrame({'open': close, 'high': close * 1.01, 'low': close * 0.99,
                         'close': close, 'volume': 1.0}, index=idx)


COMBOS = [
    {},
    {'trend_tf': 'W'},
    {'trend_weekly': True},
    {'cross_tf': 'W', 'trend_tf': 'D'},
    {'cross_tf': 'W', 'trend_tf': 'M', 'atr_tf': 'W'},
    {'exit_mode': 'cross', 'exit_tf': 'W'},
    {'exit_mode': 'trend', 'exit_tf': 'D', 'cross_tf': 'D'},
]


class MtfParityTests(unittest.TestCase):
    def test_entries_and_exits_match_sim(self):
        df = make_df()
        for extra in COMBOS:
            params = {**BASE, **extra}
            entry, atr, exit_sig = build_signals(df, params)
            strat = MovingAverageStrategy(dict(params))
            n_entries = n_exits = 0
            for i in range(WARM, len(df)):
                view = df.iloc[: i + 1]
                flat = strat.generate_signal(view, None)
                live_entry = flat.get('action') == 'buy' and flat.get('is_entry', False)
                self.assertEqual(live_entry, bool(entry[i]), f'entry {extra} bar {i}')
                pos = {'entry_price': 100.0, 'side': 'LONG', 'stop_loss': 1e-9,
                       'initial_stop_loss': 1e-9, 'entry_atr': 1.0, 'take_profit': 0.0,
                       'entry_date': str(df.index[i - 1].date())}
                held = strat.generate_signal(view, pos)
                live_exit = held.get('action') == 'sell' and str(held.get('reason', '')).startswith('Exit:')
                self.assertEqual(live_exit, bool(exit_sig[i]), f'exit {extra} bar {i}')
                n_entries += live_entry
                n_exits += live_exit
            if extra.get('cross_tf') != 'M':
                self.assertGreater(n_entries + n_exits, 0, f'no signals exercised for {extra}')

    def test_legacy_alias_and_defaults(self):
        self.assertEqual(effective_tfs({'trend_weekly': True})['trend_tf'], 'W')
        self.assertEqual(effective_tfs({})['exit_mode'], 'stop_only')
        self.assertEqual(effective_tfs({'trend_weekly': True, 'trend_tf': 'M'})['trend_tf'], 'M')

    def test_time_exit_matches_sim(self):
        df = make_df()
        params = {**BASE, 'hold_days': 10}
        entry, atr, _x = build_signals(df, params)
        i0 = int(np.flatnonzero(entry[WARM:])[0]) + WARM
        days = (df.index.values.astype('datetime64[D]').astype('int64'))
        out = simulate_long_path(
            np.eye(1, len(df), i0, dtype=bool)[0], df['close'].to_numpy(), df['low'].to_numpy(), atr,
            2.0, 3.0, i0, 10_000.0, RISK, trail_arm_r=1e9, days=days, max_hold_days=10,
        )
        self.assertEqual(out['closed_trades'], 1)
        # live: entered on day i0, must sell on first bar >= 10 days later
        strat = MovingAverageStrategy(dict(params))
        pos = {'entry_price': float(df['close'].iloc[i0]), 'side': 'LONG', 'stop_loss': 1e-9,
               'initial_stop_loss': 1e-9, 'entry_atr': 1.0, 'take_profit': 0.0,
               'entry_date': str(df.index[i0].date())}
        before = strat.generate_signal(df.iloc[: i0 + 10], pos)
        at = strat.generate_signal(df.iloc[: i0 + 11], pos)
        self.assertNotEqual(before.get('action'), 'sell')
        self.assertEqual(at.get('action'), 'sell')
        self.assertIn('Time exit', at['reason'])
        exp = (df['close'].iloc[i0 + 10] - df['close'].iloc[i0])
        self.assertEqual(out['total_pnl'] > 0, exp > 0)

    def test_gate(self):
        g = (5, 3, 1.0)
        self.assertTrue(gate_allows([], g))
        self.assertTrue(gate_allows([-5, -5], g))  # probation: < min_trades legs
        self.assertFalse(gate_allows([-5, -5, 2], g))
        self.assertTrue(gate_allows([5, -2, 4], g))
        self.assertTrue(gate_allows([-50, 5, -2, 4, 3, 2], g))  # old loss rolls out of window
        self.assertTrue(gate_allows([1, 2, 3], None))


if __name__ == '__main__':
    unittest.main()
