import os
import sys
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
for path in (REPO, os.path.join(REPO, 'src')):
    if path not in sys.path:
        sys.path.insert(0, path)

from config import TRADING_CONFIG
from shared.curated_params import merge_effective_params_for_market
from shared.profit_gate import symbol_gate_ok


def _leg(sym, t0, t1, pnl):
    return [
        {'symbol': sym, 'side': 'OPEN_LONG', 'timestamp': t0, 'quantity': 1, 'price': 100},
        {'symbol': sym, 'side': 'CLOSE_LONG', 'timestamp': t1, 'quantity': 1, 'price': 100 + pnl, 'pnl': pnl},
    ]


def _ledger(**wallets):
    return {'strategies': {k: {'history': v} for k, v in wallets.items()}}


class HoldBotTests(unittest.TestCase):
    def test_hold_wallets_configured(self):
        cfg = TRADING_CONFIG['hold_crypto_long_trail']
        self.assertEqual(cfg['bot'], 'hold')
        self.assertTrue(cfg['params']['long_only'])
        self.assertEqual(cfg['params']['hold_days'], 30)
        self.assertEqual(cfg['gate_sources'], ['hold_crypto_long_trail', 'ma_crypto_long_trail'])
        self.assertEqual(TRADING_CONFIG['ma_crypto_long_trail']['bot'], 'live')

    def test_gate_probation_winner_loser(self):
        params = {'gate_window': 5, 'gate_min_trades': 3, 'gate_min_pf': 1.0}
        src = ['hold_x', 'ma_x']
        self.assertTrue(symbol_gate_ok(_ledger(), src, 'A', params)[0])  # no history: probation
        win = (_leg('A', '2026-01-01T00:00:00', '2026-01-05T00:00:00', 5)
               + _leg('A', '2026-02-01T00:00:00', '2026-02-05T00:00:00', -2)
               + _leg('A', '2026-03-01T00:00:00', '2026-03-05T00:00:00', 4))
        self.assertTrue(symbol_gate_ok(_ledger(ma_x=win), src, 'A', params)[0])
        lose = (_leg('B', '2026-01-01T00:00:00', '2026-01-05T00:00:00', -5)
                + _leg('B', '2026-02-01T00:00:00', '2026-02-05T00:00:00', -2)
                + _leg('B', '2026-03-01T00:00:00', '2026-03-05T00:00:00', 1))
        ok, why = symbol_gate_ok(_ledger(hold_x=lose), src, 'B', params)
        self.assertFalse(ok)
        self.assertIn('net', why)
        # legs from both wallets count together; other symbols do not
        mixed = _ledger(hold_x=lose[:4], ma_x=lose[4:] + win)
        self.assertFalse(symbol_gate_ok(mixed, src, 'B', params)[0])

    def test_hold_template_applies_only_to_hold_bot(self):
        curated = {
            'templates': {'crypto': {'params': {'short_window': 10, 'trend_tf': 'W'}}},
            'hold_templates': {'crypto': {'params': {'short_window': 5, 'hold_days': 60, 'trend_tf': 'M'}}},
            'symbols': {'XRP/USDT': {'params': {'short_window': 7}}},
        }
        live = merge_effective_params_for_market({}, curated, 'XRP/USDT', 'crypto')
        hold = merge_effective_params_for_market({}, curated, 'XRP/USDT', 'crypto', 'hold')
        self.assertEqual((live['short_window'], live['trend_tf']), (7, 'W'))
        self.assertEqual((hold['short_window'], hold['hold_days'], hold['trend_tf']), (5, 60, 'M'))


if __name__ == '__main__':
    unittest.main()
