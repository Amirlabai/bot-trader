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

# Book mode flags. Not part of the six-pack, but a template must be able to set them.
MODE_KEYS = (
    'trend_weekly',
    # Which timeframe each role uses (D/W/M, resampled from daily; see shared/mtf.py).
    'trend_tf',
    'cross_tf',
    'atr_tf',
    'exit_tf',
    'exit_mode',
    # Hold bot: fixed holding horizon and the per-symbol live profit gate.
    'hold_days',
    'gate_window',
    'gate_min_trades',
    'gate_min_pf',
)

BOT_LIVE = 'live'
BOT_HOLD = 'hold'


def load_curated_params(path: str | None = None) -> dict:
    p = path or DEFAULT_CURATED_PATH
    if not os.path.exists(p):
        return {'version': 1, 'templates': {}, 'symbols': {}, 'hold_templates': {}}
    with open(p, 'r', encoding='utf-8') as f:
        data = json.load(f)
    data.setdefault('version', 1)
    data.setdefault('templates', {})
    data.setdefault('symbols', {})
    data.setdefault('hold_templates', {})
    return data


def save_curated_params(data: dict, path: str | None = None) -> str:
    p = path or DEFAULT_CURATED_PATH
    os.makedirs(os.path.dirname(p) or '.', exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
        f.write('\n')
    return p


def template_params(curated: dict, market: str, bot: str = BOT_LIVE) -> dict[str, Any]:
    templates = curated.get('hold_templates' if bot == BOT_HOLD else 'templates') or {}
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


def merge_effective_params_for_market(
    wallet_params: dict,
    curated: dict | None,
    symbol: str,
    market: str,
    bot: str = BOT_LIVE,
) -> dict:
    out = dict(wallet_params or {})
    if not curated:
        return out
    tmpl = template_params(curated, market, bot)
    for k in list(SIX_PACK_KEYS) + list(GATE_KEYS) + list(MODE_KEYS):
        if k in tmpl:
            out[k] = tmpl[k]
    if bot == BOT_HOLD:  # per-symbol overlays belong to the live book only
        return out
    sym = symbol_params(curated, symbol)
    for k in list(SIX_PACK_KEYS) + list(GATE_KEYS) + list(MODE_KEYS):
        if k in sym:
            out[k] = sym[k]
    return out


def locked_params_summary(curated: dict | None, symbol: str, market: str, wallet_params: dict) -> dict:
    """Six-pack shown on the desk for a traded symbol."""
    eff = merge_effective_params_for_market(wallet_params, curated, symbol, market)
    return {k: eff.get(k) for k in SIX_PACK_KEYS}
