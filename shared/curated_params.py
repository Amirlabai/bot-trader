"""Load / merge locked curated per-symbol EMA params."""

from __future__ import annotations

import json
import os
from typing import Any

DEFAULT_CURATED_PATH = os.path.join(os.getcwd(), 'data', 'curated_params.json')

SIX_PACK_KEYS = (
    'short_window',
    'long_window',
    'trend_window',
    'atr_period',
    'sl_atr',
    'trail_atr',
)

GATE_KEYS = (
    'adx_min',
    'atr_buffer',
    'trail_arm_r',
    'adx_period',
    'vol_mult',
)


def load_curated_params(path: str | None = None) -> dict:
    p = path or DEFAULT_CURATED_PATH
    if not os.path.exists(p):
        return {'version': 1, 'templates': {}, 'symbols': {}}
    with open(p, 'r', encoding='utf-8') as f:
        data = json.load(f)
    data.setdefault('version', 1)
    data.setdefault('templates', {})
    data.setdefault('symbols', {})
    return data


def save_curated_params(data: dict, path: str | None = None) -> str:
    p = path or DEFAULT_CURATED_PATH
    os.makedirs(os.path.dirname(p) or '.', exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
        f.write('\n')
    return p


def template_params(curated: dict, market: str) -> dict[str, Any]:
    templates = curated.get('templates') or {}
    block = templates.get(market) or {}
    if isinstance(block, dict) and 'params' in block:
        return dict(block.get('params') or {})
    return dict(block) if isinstance(block, dict) else {}


def symbol_params(curated: dict, symbol: str) -> dict[str, Any]:
    symbols = curated.get('symbols') or {}
    block = symbols.get(symbol) or {}
    if isinstance(block, dict) and 'params' in block:
        return dict(block.get('params') or {})
    return {}


def merge_effective_params(wallet_params: dict, curated: dict | None, symbol: str) -> dict:
    """Wallet mode flags + template defaults + per-symbol locked six-pack."""
    out = dict(wallet_params or {})
    if not curated:
        return out
    market = out.get('market')  # may be absent on params
    # Prefer symbol overlay; else market template
    sym = symbol_params(curated, symbol)
    if sym:
        for k in SIX_PACK_KEYS:
            if k in sym:
                out[k] = sym[k]
        for k in GATE_KEYS:
            if k in sym:
                out[k] = sym[k]
        return out

    # Infer market from curated symbol entry or templates keys via caller
    return out


def merge_effective_params_for_market(
    wallet_params: dict,
    curated: dict | None,
    symbol: str,
    market: str,
) -> dict:
    out = dict(wallet_params or {})
    if not curated:
        return out
    tmpl = template_params(curated, market)
    for k in list(SIX_PACK_KEYS) + list(GATE_KEYS):
        if k in tmpl:
            out[k] = tmpl[k]
    sym = symbol_params(curated, symbol)
    for k in list(SIX_PACK_KEYS) + list(GATE_KEYS):
        if k in sym:
            out[k] = sym[k]
    return out


def locked_params_summary(curated: dict | None, symbol: str, market: str, wallet_params: dict) -> dict:
    """Six-pack shown on the desk for a traded symbol."""
    eff = merge_effective_params_for_market(wallet_params, curated, symbol, market)
    return {k: eff.get(k) for k in SIX_PACK_KEYS}
