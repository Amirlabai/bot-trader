"""CoinMarketCap top-market-cap universe for crypto pair discovery."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# Quote assets / stables / wrappers we never trade as BASE/USDT.
SKIP_CMC_SYMBOLS = frozenset({
    'USDT', 'USDC', 'USD1', 'DAI', 'FDUSD', 'TUSD', 'USDE', 'USDS', 'BUSD',
    'PYUSD', 'EURC', 'USDD', 'GUSD', 'FRAX', 'LUSD', 'USDP', 'TETHER',
    'WBTC', 'WETH', 'STETH', 'WSTETH', 'CBETH', 'RETH', 'WEETH',
})

CMC_LISTINGS_URL = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
DEFAULT_TOP_N = 15
DROP_BELOW_RANK = 50
# Fetch at least through drop rank so we know who fell out of top-50.
DEFAULT_LISTINGS_LIMIT = max(DEFAULT_TOP_N, DROP_BELOW_RANK)


def cmc_symbol_to_pair(symbol: str) -> str:
    return f'{symbol.upper().strip()}/USDT'


def fetch_cmc_top_symbols(api_key: str, limit: int = DEFAULT_TOP_N) -> list[dict]:
    """Return CMC listings rows for top `limit` by market cap (includes stables)."""
    if not api_key:
        raise ValueError('CMP_API_KEY / CMC API key is empty')
    params = urllib.parse.urlencode({
        'start': 1,
        'limit': int(limit),
        'convert': 'USD',
        'sort': 'market_cap',
    })
    req = urllib.request.Request(
        f'{CMC_LISTINGS_URL}?{params}',
        headers={
            'Accept': 'application/json',
            'X-CMC_PRO_API_KEY': api_key,
        },
        method='GET',
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'CMC HTTP {e.code}: {body[:300]}') from e
    status = payload.get('status') or {}
    if status.get('error_code'):
        raise RuntimeError(
            f"CMC error {status.get('error_code')}: {status.get('error_message')}"
        )
    data = payload.get('data') or []
    if not isinstance(data, list):
        raise RuntimeError('CMC listings response missing data list')
    return data


def tradable_pairs_from_listings(listings: list[dict]) -> list[tuple[str, int, str]]:
    """(pair, cmc_rank, cmc_symbol) for non-stable listings."""
    out = []
    for row in listings:
        sym = str(row.get('symbol') or '').upper().strip()
        if not sym or sym in SKIP_CMC_SYMBOLS:
            continue
        rank = int(row.get('cmc_rank') or row.get('rank') or 0)
        out.append((cmc_symbol_to_pair(sym), rank, sym))
    return out


def load_universe(path: str) -> dict:
    if not os.path.exists(path):
        return {
            'updated_at': None,
            'cmc_top15': [],
            'pairs': [],
            'added': [],
            'dropped': [],
        }
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    data.setdefault('cmc_top15', [])
    data.setdefault('pairs', [])
    data.setdefault('added', [])
    data.setdefault('dropped', [])
    return data


def save_universe(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
        f.write('\n')


def merge_crypto_pairs(base_pairs: list[str], universe_pairs: list[str]) -> list[str]:
    seen = set()
    merged = []
    for p in list(base_pairs) + list(universe_pairs):
        if p in seen:
            continue
        seen.add(p)
        merged.append(p)
    return merged


def sync_crypto_universe(
    api_key: str,
    universe_path: str,
    base_pairs: list[str],
    *,
    top_n: int = DEFAULT_TOP_N,
    drop_below_rank: int = DROP_BELOW_RANK,
    yahoo_ok=None,
) -> dict:
    """Fetch CMC listings; add new top-N tradables; drop pairs ranked worse than drop_below_rank.

    yahoo_ok: optional callable(pair) -> bool to require Yahoo OHLCV before adding.
    Base seed pairs are never removed by rank drop.
    Returns summary with added, dropped, and full merged list.
    """
    listings_limit = max(int(top_n), int(drop_below_rank), DEFAULT_LISTINGS_LIMIT)
    listings = fetch_cmc_top_symbols(api_key, limit=listings_limit)
    tradable_all = tradable_pairs_from_listings(listings)
    rank_by_pair = {pair: rank for pair, rank, _sym in tradable_all}
    top_listings = listings[: int(top_n)]
    cmc_top_symbols = [str(r.get('symbol') or '').upper() for r in top_listings]
    tradable_top = tradable_pairs_from_listings(top_listings)

    universe = load_universe(universe_path)
    known = set(base_pairs) | set(universe.get('pairs') or [])
    added_now = []
    for pair, rank, sym in tradable_top:
        if pair in known:
            continue
        if yahoo_ok is not None and not yahoo_ok(pair):
            print(f'  CMC skip {pair} (rank {rank}): no Yahoo data')
            continue
        universe['pairs'].append(pair)
        known.add(pair)
        entry = {
            'pair': pair,
            'symbol': sym,
            'rank': rank,
            'at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        }
        universe['added'].append(entry)
        added_now.append(entry)
        print(f'  CMC add {pair} (CMC rank {rank})')

    # Drop universe pairs (not base seeds) with rank > drop_below_rank or missing from listings
    dropped_now = []
    kept_pairs = []
    base_set = set(base_pairs)
    now_iso = datetime.now(timezone.utc).isoformat(timespec='seconds')
    for pair in list(universe.get('pairs') or []):
        if pair in base_set:
            kept_pairs.append(pair)
            continue
        rank = rank_by_pair.get(pair)
        if rank is None or rank > int(drop_below_rank):
            drop_entry = {
                'pair': pair,
                'rank': rank,
                'at': now_iso,
                'reason': 'missing_from_listings' if rank is None else f'rank_gt_{drop_below_rank}',
            }
            universe.setdefault('dropped', []).append(drop_entry)
            dropped_now.append(drop_entry)
            print(f'  CMC drop {pair} (CMC rank {rank})')
            continue
        kept_pairs.append(pair)
    universe['pairs'] = kept_pairs

    universe['updated_at'] = now_iso
    universe['cmc_top15'] = cmc_top_symbols
    save_universe(universe_path, universe)

    merged = merge_crypto_pairs(base_pairs, universe['pairs'])
    return {
        'added': added_now,
        'dropped': dropped_now,
        'pairs': merged,
        'cmc_top15': cmc_top_symbols,
        'universe_path': universe_path,
        'drop_below_rank': int(drop_below_rank),
    }
