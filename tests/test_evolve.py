import copy
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np
import pandas as pd

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


def _synthetic_frames(n=1500, symbols=('AAA/USDT', 'BBB/USDT', 'CCC/USDT', 'DDD/USDT')):
    frames = {}
    for k, sym in enumerate(symbols):
        rng = np.random.default_rng(k + 10)
        # trending regimes so crosses and trends actually occur
        drift = np.repeat(rng.normal(0.0012, 0.003, n // 100 + 1), 100)[:n]
        close = 50 * np.exp(np.cumsum(drift + rng.normal(0, 0.02, n)))
        idx = pd.date_range(end='2026-10-01', periods=n, freq='D')
        frames[sym] = pd.DataFrame({'open': close, 'high': close * 1.01, 'low': close * 0.99,
                                    'close': close, 'volume': 1.0}, index=idx)
    return frames


class LabCycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = (curated_params.DEFAULT_CURATED_PATH, engine.LOG_PATH, engine.LEDGER_PATH)
        curated_params.DEFAULT_CURATED_PATH = os.path.join(self.tmp, 'curated.json')
        engine.LOG_PATH = os.path.join(self.tmp, 'log.json')
        engine.LEDGER_PATH = os.path.join(self.tmp, 'ledger.json')
        with open(engine.LEDGER_PATH, 'w') as f:
            json.dump({'strategies': {}}, f)
        self.start = {
            'version': 1, 'symbols': {},
            'templates': {'crypto': {'params': {
                'short_window': 10, 'long_window': 20, 'trend_window': 20, 'trend_weekly': True,
                'atr_period': 14, 'sl_atr': 1.0, 'trail_atr': 3.0, 'adx_min': 0.0, 'atr_buffer': 0.0,
                'trail_arm_r': 0.0, 'adx_period': 14}}},
        }
        curated_params.save_curated_params(copy.deepcopy(self.start))
        frames = _synthetic_frames()
        self.patches = [
            mock.patch.object(engine.cp, 'CRYPTO_PAIRS', list(frames)),
            mock.patch.object(engine.cp, '_load_ohlcv', lambda f, sym, at: frames[sym]),
            mock.patch.object(engine.cp, 'DataFetcher', lambda cfg: None),
            mock.patch.object(engine.cp, 'asset_type_for_symbol', lambda sym: 'crypto'),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        curated_params.DEFAULT_CURATED_PATH, engine.LOG_PATH, engine.LEDGER_PATH = self.old

    def test_champion_reads_legacy_weekly_flag(self):
        champ = engine.champion_params(curated_params.load_curated_params(), 'crypto')
        self.assertEqual(champ['trend_tf'], 'W')
        self.assertEqual(champ['exit_mode'], 'stop_only')

    def test_timeframe_cycle_report_and_promote_rollback(self):
        r = engine.run_cycle('crypto', timeframes=True, max_sims=72, max_refine=20)
        self.assertEqual(len(r['folds']['challenger']), 3)
        self.assertTrue(any('sub-periods' in g['name'] for g in r['gates']))
        self.assertTrue(set(engine.TF_KEYS) <= set(r['challenger']['params']))
        engine.promote(r, force=True)
        now = curated_params.load_curated_params()['templates']['crypto']['params']
        self.assertEqual(now['trend_tf'], r['challenger']['params']['trend_tf'])
        self.assertEqual(now['trend_weekly'], r['challenger']['params']['trend_tf'] == 'W')
        engine.rollback('crypto')
        self.assertEqual(curated_params.load_curated_params()['templates'], self.start['templates'])

    def test_hold_cycle_writes_hold_template_only(self):
        r = engine.run_cycle('crypto', bot='hold', timeframes=False, max_sims=60, max_refine=20)
        self.assertEqual(r['bot'], 'hold')
        self.assertIn('hold_days', r['challenger']['params'])
        engine.promote(r, force=True)
        cur = curated_params.load_curated_params()
        self.assertEqual(cur['templates'], self.start['templates'])  # live book untouched
        hold = cur['hold_templates']['crypto']['params']
        self.assertIn('hold_days', hold)
        self.assertEqual(hold['adx_min'], 0.0)  # gates inherited from live template
        engine.rollback('crypto', 'hold')
        self.assertNotIn('crypto', curated_params.load_curated_params()['hold_templates'])


if __name__ == '__main__':
    unittest.main()
