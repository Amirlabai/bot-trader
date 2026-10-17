import copy
import json
import os
import sys
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(REPO, 'scratch', 'evolve_lab'))

import engine  # noqa: E402
from shared import curated_params  # noqa: E402


def _report(passed=True):
    return {
        'market': 'crypto', 'at': '2026-10-17T00:00:00', 'passed': passed,
        'challenger': {
            'params': {'short_window': 5, 'long_window': 9, 'trend_window': 99, 'atr_period': 7,
                       'sl_atr': 2.0, 'trail_atr': 3.0},
            'holdout': {'net_pnl': 1.0}, 'holdout_score': 2.0,
        },
    }


class EvolveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = (curated_params.DEFAULT_CURATED_PATH, engine.LOG_PATH)
        curated_params.DEFAULT_CURATED_PATH = os.path.join(self.tmp, 'curated.json')
        engine.LOG_PATH = os.path.join(self.tmp, 'log.json')
        self.start = {
            'version': 1, 'symbols': {
                'BTC/USDT': {'market': 'crypto', 'params': {'short_window': 25, 'sl_atr': 1.0}},
                'EUR/USD': {'market': 'forex', 'params': {'short_window': 10}},
            },
            'templates': {'crypto': {'params': {'short_window': 25, 'long_window': 75, 'trend_window': 100,
                                                'atr_period': 10, 'sl_atr': 1.0, 'trail_atr': 4.5, 'adx_min': 5.0}}},
        }
        curated_params.save_curated_params(copy.deepcopy(self.start))

    def tearDown(self):
        curated_params.DEFAULT_CURATED_PATH, engine.LOG_PATH = self.old

    def test_promote_then_rollback_restores_exactly(self):
        engine.promote(_report())
        now = curated_params.load_curated_params()
        self.assertEqual(now['templates']['crypto']['params']['short_window'], 5)
        self.assertEqual(now['templates']['crypto']['params']['adx_min'], 5.0)  # gates survive
        self.assertEqual(now['symbols']['BTC/USDT']['params']['short_window'], 5)
        self.assertEqual(now['symbols']['EUR/USD']['params']['short_window'], 10)  # other books untouched
        engine.rollback('crypto')
        back = curated_params.load_curated_params()
        self.assertEqual(back['templates'], self.start['templates'])
        self.assertEqual(back['symbols'], self.start['symbols'])
        with self.assertRaises(ValueError):
            engine.rollback('crypto')

    def test_failed_gates_need_force(self):
        with self.assertRaises(ValueError):
            engine.promote(_report(passed=False))
        entry = engine.promote(_report(passed=False), force=True)
        self.assertTrue(entry['forced'])
        self.assertEqual(len(json.load(open(engine.LOG_PATH))), 1)


if __name__ == '__main__':
    unittest.main()
