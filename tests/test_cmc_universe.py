import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
for path in (REPO, os.path.join(REPO, 'src')):
    if path not in sys.path:
        sys.path.insert(0, path)

from shared.cmc_universe import (
    cmc_symbol_to_pair,
    merge_crypto_pairs,
    sync_crypto_universe,
    tradable_pairs_from_listings,
)


class CmcUniverseTests(unittest.TestCase):
    def test_pair_mapping(self):
        self.assertEqual(cmc_symbol_to_pair('btc'), 'BTC/USDT')

    def test_skips_stables(self):
        listings = [
            {'symbol': 'BTC', 'cmc_rank': 1},
            {'symbol': 'USDT', 'cmc_rank': 3},
            {'symbol': 'USDC', 'cmc_rank': 7},
            {'symbol': 'SUI', 'cmc_rank': 12},
        ]
        pairs = tradable_pairs_from_listings(listings)
        self.assertEqual([p[0] for p in pairs], ['BTC/USDT', 'SUI/USDT'])

    def test_merge_preserves_order_and_dedupes(self):
        merged = merge_crypto_pairs(
            ['BTC/USDT', 'ETH/USDT'],
            ['ETH/USDT', 'SUI/USDT'],
        )
        self.assertEqual(merged, ['BTC/USDT', 'ETH/USDT', 'SUI/USDT'])

    def test_sync_adds_new_top15_alts(self):
        listings = [
            {'symbol': 'BTC', 'cmc_rank': 1},
            {'symbol': 'ETH', 'cmc_rank': 2},
            {'symbol': 'USDT', 'cmc_rank': 3},
            {'symbol': 'SUI', 'cmc_rank': 11},
            {'symbol': 'LINK', 'cmc_rank': 14},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'crypto_universe.json')
            with patch(
                'shared.cmc_universe.fetch_cmc_top_symbols',
                return_value=listings,
            ):
                summary = sync_crypto_universe(
                    'fake-key',
                    path,
                    ['BTC/USDT', 'ETH/USDT'],
                    yahoo_ok=lambda _p: True,
                )
            self.assertEqual(
                [a['pair'] for a in summary['added']],
                ['SUI/USDT', 'LINK/USDT'],
            )
            self.assertIn('SUI/USDT', summary['pairs'])
            self.assertIn('LINK/USDT', summary['pairs'])
            with open(path, encoding='utf-8') as f:
                saved = json.load(f)
            self.assertEqual(saved['pairs'], ['SUI/USDT', 'LINK/USDT'])
            self.assertEqual(saved['cmc_top15'], ['BTC', 'ETH', 'USDT', 'SUI', 'LINK'])

    def test_sync_drops_pairs_below_rank_50(self):
        # First sync adds OLDCOIN at rank 12
        listings_add = [
            {'symbol': 'BTC', 'cmc_rank': 1},
            {'symbol': 'ETH', 'cmc_rank': 2},
            {'symbol': 'OLDCOIN', 'cmc_rank': 12},
        ]
        # Later: OLDCOIN at rank 60 (still in fetch of 50+? simulate missing from top-50)
        listings_drop = [
            {'symbol': 'BTC', 'cmc_rank': 1},
            {'symbol': 'ETH', 'cmc_rank': 2},
        ] + [
            {'symbol': f'X{i}', 'cmc_rank': i} for i in range(3, 51)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'crypto_universe.json')
            with patch(
                'shared.cmc_universe.fetch_cmc_top_symbols',
                return_value=listings_add,
            ):
                sync_crypto_universe(
                    'fake-key', path, ['BTC/USDT', 'ETH/USDT'],
                    yahoo_ok=lambda _p: True,
                )
            with patch(
                'shared.cmc_universe.fetch_cmc_top_symbols',
                return_value=listings_drop,
            ):
                summary = sync_crypto_universe(
                    'fake-key', path, ['BTC/USDT', 'ETH/USDT'],
                    yahoo_ok=lambda _p: True,
                )
            self.assertTrue(any(d['pair'] == 'OLDCOIN/USDT' for d in summary['dropped']))
            self.assertNotIn('OLDCOIN/USDT', summary['pairs'])
            # Base seeds kept
            self.assertIn('BTC/USDT', summary['pairs'])
            self.assertIn('ETH/USDT', summary['pairs'])


if __name__ == '__main__':
    unittest.main()
