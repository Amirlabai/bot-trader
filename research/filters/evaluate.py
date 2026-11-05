"""How well a walk-forward filter separates false starts, and what it costs in R."""

from __future__ import annotations

import pandas as pd

from research.filters.dataset import FEATURES
from research.filters.models import logistic_weights


def evaluate(table: pd.DataFrame, probs: pd.DataFrame, skip_q, model=None, model_name='') -> dict:
    """Metrics on baseline trades inside the walk-forward period (all out-of-sample)."""
    from sklearn.metrics import roc_auc_score

    if probs.empty:
        return {'n': 0}
    merged = table.merge(probs, on=['symbol', 'ts'], how='inner')
    taken = merged.loc[merged['taken']]
    out = {'n_signals': int(len(merged)), 'n_trades': int(len(taken)),
           'base_rate': float(taken['y'].mean()) if len(taken) else None}
    if taken['y'].nunique() == 2:
        out['auc'] = float(roc_auc_score(taken['y'], taken['p']))
    rows = []
    for q in skip_q:
        skip = taken[f'skip_{q:g}']
        removed = taken.loc[skip]
        kept = taken.loc[~skip]
        rows.append({
            'skip_q': q,
            'removed': int(len(removed)),
            'false_starts_removed': int(removed['y'].sum()),
            'false_starts_total': int(taken['y'].sum()),
            'precision': float(removed['y'].mean()) if len(removed) else None,
            'winners_removed': int((removed['r_net'] > 0).sum()),
            'r_removed': float(removed['r_net'].sum()),
            'winner_r_removed': float(removed.loc[removed['r_net'] > 0, 'r_net'].sum()),
            'r_kept': float(kept['r_net'].sum()),
        })
    out['by_q'] = rows
    if model is not None and model_name == 'logistic':
        out['weights'] = logistic_weights(model, FEATURES)
    return out


def format_eval(name: str, ev: dict) -> list[str]:
    md = [f'### {name}', '']
    if not ev.get('n_trades'):
        return md + ['No walk-forward trades.', '']
    md += [
        f"- Out-of-sample baseline trades: {ev['n_trades']} "
        f"(false-start rate {ev['base_rate'] * 100:.0f}%), entry signals scored: {ev['n_signals']}",
        f"- AUC {ev.get('auc', float('nan')):.3f} (0.5 = no skill)",
        '',
        '| Skip riskiest | Removed | False starts removed | Precision | Winners removed | '
        'Winner R removed | R removed | R kept |',
        '|---|---|---|---|---|---|---|---|',
    ]
    for r in ev['by_q']:
        prec = '-' if r['precision'] is None else f"{r['precision'] * 100:.0f}%"
        md.append(
            f"| {r['skip_q'] * 100:.0f}% | {r['removed']} | "
            f"{r['false_starts_removed']} of {r['false_starts_total']} | {prec} | "
            f"{r['winners_removed']} | {r['winner_r_removed']:+.1f}R | {r['r_removed']:+.1f}R | "
            f"{r['r_kept']:+.1f}R |"
        )
    if ev.get('weights'):
        md += ['', 'Logistic weights (standardized; positive = more likely a false start, last refit):', '']
        md += [f'- {k}: {v:+.2f}' for k, v in list(ev['weights'].items())[:10]]
    md.append('')
    return md
