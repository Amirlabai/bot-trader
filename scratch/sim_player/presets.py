"""Parse docs/*_ema_grid_*.md into selectable algo presets."""

from __future__ import annotations

import glob
import os
import re
from typing import Any

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def _parse_header(text: str, source: str | None = None) -> dict[str, Any]:
    meta: dict[str, Any] = {
        'interval': '1d',
        'symbol': 'BTC/USDT',
        'window': None,
        'label': None,
    }
    # Title: # BTC EMA grid (4h 1y pass)
    m = re.search(r'^#\s+(.+?)\s*\(([^)]+)\)\s*$', text, re.M)
    if m:
        meta['title'] = m.group(1).strip()
        meta['label'] = m.group(2).strip()

    # Window dates (allow notes between end date and following fields)
    wm = re.search(
        r'Window:\s*`([^`]+)`\s*\.\.\s*`([^`]+)`',
        text,
    )
    if wm:
        meta['window'] = {'start': wm.group(1).strip(), 'end': wm.group(2).strip()}

    im = re.search(r'Interval:\s*`([^`]+)`', text)
    if im:
        meta['interval'] = im.group(1).strip()
    elif meta.get('label') and re.search(r'\b4h\b', meta['label'], re.I):
        meta['interval'] = '4h'
    elif source and '_4h_' in source:
        meta['interval'] = '4h'

    sm = re.search(r'Symbols:\s*`([^`]+)`', text)
    if sm:
        meta['symbol'] = sm.group(1).split(',')[0].strip()
    return meta


def _parse_table_section(text: str, heading: str, source: str | None = None) -> list[dict[str, Any]]:
    """Parse a markdown table under a ## heading. Returns row dicts with params."""
    # Find heading then table
    pat = re.compile(
        rf'^##\s+{re.escape(heading)}\s*$',
        re.M | re.I,
    )
    m = pat.search(text)
    if not m:
        return []
    rest = text[m.end() :]
    next_h = re.search(r'^##\s+', rest, re.M)
    block = rest[: next_h.start()] if next_h else rest

    lines = [ln.strip() for ln in block.splitlines() if ln.strip().startswith('|')]
    if len(lines) < 2:
        return []

    headers = [h.strip().lower() for h in lines[0].strip('|').split('|')]
    # skip separator
    rows = []
    for line in lines[2:]:
        cells = [c.strip() for c in line.strip('|').split('|')]
        if len(cells) < len(headers):
            continue
        row = {headers[i]: cells[i] for i in range(len(headers))}
        params = _row_to_params(row, source)
        if params is None:
            continue
        rank = _parse_int(row.get('#') or row.get('rank') or '')
        rows.append({
            'rank': rank,
            'params': params,
            'net_pnl': _parse_money(row.get('pnl')),
            'win_rate': _parse_float(row.get('wr%') or row.get('wr')),
            'trades': _parse_int(row.get('trades') or row.get('n')),
            'profit_factor': _parse_pf(row.get('pf')),
        })
    return rows


def _row_to_params(row: dict[str, str], source: str | None = None) -> dict[str, Any] | None:
    # Table columns: fast | slow | trend | atr | SL× | trail×
    # Or params cell: short=20 long=45 ...
    if 'n' in row and 'fast' not in row:
        try:
            return {
                'strategy': 'close_slope' if source and 'close_slope' in source else 'mid_slope',
                'slope_span': int(float(row['n'])),
                'min_slope': float(row.get('min') or 0),
                'trend_window': int(float(row.get('trend', '150'))),
                'atr_period': int(float(row.get('atr', '14'))),
                'sl_atr': float(row.get('sl×') or row.get('slx') or row.get('sl') or '1'),
                'trail_atr': float(row.get('trail×') or row.get('trailx') or row.get('trail') or '1'),
                'short_window': 0,
                'long_window': 0,
            }
        except (TypeError, ValueError):
            return None
    if 'fast' in row and 'slow' in row:
        try:
            return {
                'short_window': int(float(row['fast'])),
                'long_window': int(float(row['slow'])),
                'trend_window': int(float(row.get('trend', '100'))),
                'atr_period': int(float(row.get('atr', '14'))),
                'sl_atr': float(row.get('sl×') or row.get('slx') or row.get('sl') or '1'),
                'trail_atr': float(row.get('trail×') or row.get('trailx') or row.get('trail') or '1'),
            }
        except (TypeError, ValueError):
            return None
    params_cell = row.get('params') or ''
    # e.g. fast=20 slow=45 trend=200 atr=19 SL=2 trail=2
    nums = {}
    for key, pat in (
        ('short_window', r'fast[=:\s]+(\d+)'),
        ('long_window', r'slow[=:\s]+(\d+)'),
        ('trend_window', r'trend[=:\s]+(\d+)'),
        ('atr_period', r'atr[=:\s]+(\d+)'),
        ('sl_atr', r'SL[=:\s×x]*([\d.]+)'),
        ('trail_atr', r'trail[=:\s×x]*([\d.]+)'),
    ):
        mm = re.search(pat, params_cell, re.I)
        if not mm:
            return None
        nums[key] = float(mm.group(1)) if key.endswith('_atr') else int(float(mm.group(1)))
    return nums


def _parse_int(s: str | None) -> int | None:
    if s is None or s == '':
        return None
    try:
        return int(float(re.sub(r'[^\d.-]', '', s)))
    except ValueError:
        return None


def _parse_float(s: str | None) -> float | None:
    if s is None or s == '':
        return None
    try:
        return float(re.sub(r'[^\d.-]', '', s))
    except ValueError:
        return None


def _parse_money(s: str | None) -> float | None:
    if s is None or s == '':
        return None
    try:
        return float(re.sub(r'[^\d.+-]', '', s.replace(',', '')))
    except ValueError:
        return None


def _parse_pf(s: str | None) -> float | None:
    if s is None or s == '':
        return None
    if s.strip().lower() == 'inf':
        return None
    return _parse_float(s)


def load_presets(docs_dir: str | None = None) -> list[dict[str, Any]]:
    docs = docs_dir or os.path.join(REPO_ROOT, 'docs')
    paths = sorted(glob.glob(os.path.join(docs, '*_ema_grid_*.md')))
    paths += sorted(glob.glob(os.path.join(docs, '*_mid_slope_*.md')))
    paths += sorted(glob.glob(os.path.join(docs, '*_close_slope_*.md')))
    # Prefer newer mtime first so recent 4h runs surface at top of the dropdown.
    paths.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    presets: list[dict[str, Any]] = []
    seen: set[tuple] = set()

    for path in paths:
        try:
            text = open(path, encoding='utf-8').read()
        except OSError:
            continue
        meta = _parse_header(text, source=os.path.basename(path))
        source = os.path.basename(path)
        label_base = meta.get('label') or source.replace('.md', '')

        sections = [
            ('Top 10 by composite (eligible)', 'composite'),
            ('Best by net PnL (top 10, any trade count)', 'pnl'),
        ]
        for heading, kind in sections:
            rows = _parse_table_section(text, heading, source)
            for row in rows:
                p = row['params']
                key = (
                    source,
                    kind,
                    p.get('strategy') or 'ema_cross',
                    p.get('slope_span'),
                    p.get('short_window'),
                    p.get('long_window'),
                    p['trend_window'],
                    p['atr_period'],
                    p['sl_atr'],
                    p['trail_atr'],
                    p.get('min_slope') or 0,
                )
                if key in seen:
                    continue
                seen.add(key)
                rank = row['rank'] or 0
                if p.get('strategy') in ('mid_slope', 'close_slope'):
                    floor = p.get('min_slope') or 0
                    floor_s = f' · min{floor:g}' if floor else ''
                    side = 'Close' if p['strategy'] == 'close_slope' else 'Midpoint'
                    pid = f'{source}:{kind}:{rank}:n{p["slope_span"]}/{p["trend_window"]}/m{floor:g}'
                    label = (
                        f'{side} · {label_base} #{rank} {kind} · '
                        f'n{p["slope_span"]}{floor_s} · trend{p["trend_window"]} · '
                        f'ATR{p["atr_period"]} · SL{p["sl_atr"]:g} · trail{p["trail_atr"]:g}'
                    )
                else:
                    pid = f'{source}:{kind}:{rank}:{p["short_window"]}/{p["long_window"]}/{p["trend_window"]}'
                    label = (
                        f'{label_base} #{rank} {kind} · '
                        f'{p["short_window"]}/{p["long_window"]}/{p["trend_window"]} · '
                        f'ATR{p["atr_period"]} · SL{p["sl_atr"]:g} · trail{p["trail_atr"]:g}'
                    )
                presets.append({
                    'id': pid,
                    'source': source,
                    'kind': kind,
                    'rank': rank,
                    'label': label,
                    'interval': meta.get('interval') or '1d',
                    'symbol': meta.get('symbol') or 'BTC/USDT',
                    'window': meta.get('window'),
                    'params': p,
                    'metrics': {
                        'net_pnl': row.get('net_pnl'),
                        'win_rate': row.get('win_rate'),
                        'trades': row.get('trades'),
                        'profit_factor': row.get('profit_factor'),
                    },
                })
    head = [
        'btc_mid_slope_min_4h.md',
        'btc_close_slope_min_4h.md',
        'btc_mid_slope_min_4h_6m.md',
        'btc_close_slope_min_4h_6m.md',
    ]

    def _order(item: dict[str, Any]) -> tuple[int, int]:
        if item['kind'] == 'composite' and item['rank'] == 1 and item['source'] in head:
            return (0, head.index(item['source']))
        return (1, 0)

    presets.sort(key=_order)
    return presets
