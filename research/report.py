"""Markdown report for one experiment run."""

from __future__ import annotations

import os

import pandas as pd

BASELINE = 'baseline'


def _r(v) -> str:
    return '-' if v is None or pd.isnull(v) else f'{v:+.1f}R'


def _r2(v) -> str:
    return '-' if v is None or pd.isnull(v) else f'{v:+.2f}R'


def _p(v) -> str:
    return '-' if v is None or pd.isnull(v) else f'{v * 100:.0f}%'


def _n(v, d=2) -> str:
    return '-' if v is None or pd.isnull(v) else f'{v:.{d}f}'


def flag_better(variants: pd.DataFrame) -> pd.DataFrame:
    """Better = beats baseline net total R both in-sample and out-of-sample."""
    v = variants.copy()
    base = v.loc[v['variant'] == BASELINE]
    if base.empty:
        v['better'] = False
        return v
    b = base.iloc[0]
    v['is_ret_dd'] = v['is_total_r'] / v['is_max_dd_r'].where(v['is_max_dd_r'] > 0)
    v['d_is'] = v['is_total_r'] - b['is_total_r']
    v['d_oos'] = v['oos_total_r'] - b['oos_total_r']
    v['better'] = (v['d_is'] > 0) & (v['d_oos'] > 0)
    return v


def _rows(df: pd.DataFrame) -> list[str]:
    head = ('| Variant | IS total | IS max DD | IS total/DD | OOS total | OOS max DD | '
            'Win rate | Mean R | PF | Capture | Beats baseline IS+OOS |')
    lines = [head, '|' + '---|' * 11]
    for _, r in df.iterrows():
        lines.append(
            f"| {r['variant']} | {_r(r['is_total_r'])} | {_n(r['is_max_dd_r'], 1)}R | "
            f"{_n(r.get('is_ret_dd'))} | {_r(r['oos_total_r'])} | {_n(r['oos_max_dd_r'], 1)}R | "
            f"{_p(r['all_win_rate'])} | {_r2(r['all_mean_r'])} | {_n(r['all_profit_factor'])} | "
            f"{_p(r['all_capture'])} | {'yes' if r.get('better') else 'no'} |"
        )
    return lines


def _entry_rows(df: pd.DataFrame) -> list[str]:
    head = ('| Variant | Trades | Losers blocked | False starts blocked | Winners kept | '
            'Winner R kept | 3R+ kept | New trades | IS total | OOS total | IS max DD | '
            'Lift vs random | Beats signal IS+OOS |')
    lines = [head, '|' + '---|' * 13]
    for _, r in df.iterrows():
        lines.append(
            f"| {r['variant']} | {int(r['all_n'])} | {_p(r.get('losers_blocked'))} | "
            f"{_p(r.get('false_starts_blocked'))} | {_p(r.get('winners_kept'))} | "
            f"{_p(r.get('winner_r_kept'))} | {_p(r.get('big_winners_kept'))} | "
            f"{'-' if pd.isnull(r.get('new_trades')) else int(r['new_trades'])} | "
            f"{_r(r['is_total_r'])} | {_r(r['oos_total_r'])} | {_n(r['is_max_dd_r'], 1)}R | "
            f"{_r(r.get('lift_r'))} | {'yes' if r.get('beats_signal') else 'no'} |"
        )
    return lines


def _entry_section(v: pd.DataFrame) -> list[str]:
    v = v.copy()
    sig = v.loc[v['entry_mode'] == 'signal'].set_index('exit')
    v['beats_signal'] = v.apply(
        lambda r: r['entry_mode'] != 'signal' and r['exit'] in sig.index
        and r['is_total_r'] > sig.loc[r['exit'], 'is_total_r']
        and r['oos_total_r'] > sig.loc[r['exit'], 'oos_total_r']
        and (r.get('lift_r') or 0) > 0, axis=1,
    )
    md = ['## Confirmation entries', '',
          'Blocked and kept are measured against the signal-entry trades with the same exit, matched by '
          'the crossover bar. Lift vs random = R of the mode minus its trade count times the signal mean R. '
          'A mode beats the signal entry only with higher total R in both periods and positive lift.', '']
    for exit_name in sorted(v['exit'].unique(), key=lambda e: (e != BASELINE, e)):
        sub = v.loc[v['exit'] == exit_name]
        base = sub.loc[sub['entry_mode'] == 'signal']
        rest = sub.loc[sub['entry_mode'] != 'signal'].sort_values('is_total_r', ascending=False)
        n_beat = int(rest['beats_signal'].sum())
        md += [f'### Exit: {exit_name} ({n_beat} of {len(rest)} modes beat the signal entry)', '']
        md += _entry_rows(pd.concat([base, rest.head(15)]))
        md += ['', 'Most losers blocked while keeping at least 80% of winner R:', '']
        keep = rest.loc[rest['winner_r_kept'] >= 0.8].sort_values('losers_blocked', ascending=False)
        md += _entry_rows(keep.head(8)) if not keep.empty else ['- none']
        md.append('')
    return md


def build_report(resolved: dict, variants: pd.DataFrame, extra=None) -> str:
    v = flag_better(variants)
    spec = resolved['spec']
    pairs = resolved['pairs']
    first = min(r[0] for r in pairs.values()) if pairs else '-'
    last = max(r[1] for r in pairs.values()) if pairs else '-'
    md = [
        f"# Experiment: {spec['name']}",
        '',
        spec.get('description', ''),
        '',
        f"- Ran {resolved['ran_at']} at git {resolved['git_sha']}"
        f"{' (uncommitted changes)' if resolved['git_dirty'] else ''}",
        f"- {len(pairs)} pairs, bars {first} to {last}",
        f"- Fee {resolved['fee_rate'] * 100:.2f}% per side on every fill. All R below is net of fees.",
        f"- In-sample: trades opened before {resolved['oos_from'][:10]}. "
        f"Out-of-sample: opened after (last {resolved['oos_months']} months).",
        '- A variant beats the baseline only if its total R is higher in-sample and out-of-sample.',
        '- Same-bar rule: when one bar touches both the stop and a ladder level, the stop fills first.',
        '',
    ]
    base = v.loc[v['variant'] == BASELINE]
    if not base.empty:
        b = base.iloc[0]
        md += [
            '## Baseline (live daily exit, no scale-out)', '',
            f"- {int(b['all_n'])} trades, net {_r(b['all_total_r'])} "
            f"(gross {_r(b['all_total_r_gross'])}), win {_p(b['all_win_rate'])}, "
            f"mean {_r2(b['all_mean_r'])}, PF {_n(b['all_profit_factor'])}",
            f"- In-sample {_r(b['is_total_r'])} with max drawdown {_n(b['is_max_dd_r'], 1)}R; "
            f"out-of-sample {_r(b['oos_total_r'])} with max drawdown {_n(b['oos_max_dd_r'], 1)}R",
            '',
        ]
    if resolved.get('missing_pairs'):
        md += [f"Pairs without data (skipped): {', '.join(resolved['missing_pairs'])}", '']
    if resolved.get('filters', {}).get('walk_forward_from'):
        md += [f"All arms, baseline included, trade only from {resolved['filters']['walk_forward_from'][:10]} "
               '(first walk-forward block), so they cover the same period.', '']
    others = v.loc[v['variant'] != BASELINE]
    if 'filter' in v and v['filter'].nunique() > 1:
        by_filter = v.loc[v['exit'] == BASELINE].sort_values('is_total_r', ascending=False)
        md += ['## Entry filters with the current exit', '']
        md += _rows(by_filter)
        md.append('')
    if 'exit' in v and v['exit'].nunique() > 1 and 'filter' in v:
        exits = v.loc[v['filter'] == 'none']
        if 'entry_mode' in exits:
            exits = exits.loc[exits['entry_mode'] == 'signal']
        exits = exits.sort_values('is_total_r', ascending=False)
        if len(exits) > 1:
            md += ['## Exit variants without a filter (top 15)', '']
            md += _rows(exits.head(16))
            md.append('')
    if 'entry_mode' in v and v['entry_mode'].nunique() > 1:
        md += _entry_section(v)
    if extra:
        md += list(extra)
    if not others.empty:
        better = others.loc[others['better']]
        md += [f"{len(better)} of {len(others)} variants beat the baseline in both periods.", '']
        md += ['## Top 15 by in-sample total R', '']
        md += _rows(pd.concat([base, others.sort_values('is_total_r', ascending=False).head(15)]))
        md += ['', '## Top 15 by in-sample return over drawdown', '',
               'Total R divided by max drawdown. Higher means a smoother equity curve for the same return.', '']
        md += _rows(pd.concat([base, others.sort_values('is_ret_dd', ascending=False).head(15)]))
        half = others.loc[(others['fraction'] == 0.5) & (others['fraction_step'] == 0)]
        if not half.empty:
            md += ['', '## Sell half at every step', '']
            md += _rows(pd.concat([base, half.sort_values(['breakeven_after_first', 'step_r'])]))
        md.append('')
        amb = int(v['ambiguous_bars'].max()) if 'ambiguous_bars' in v else 0
        md += [f'Most same-bar stop/level conflicts in any one variant: {amb} bars.', '']
    return '\n'.join(md)


def write_report(out_dir: str, resolved: dict, variants: pd.DataFrame, extra=None) -> str:
    path = os.path.join(out_dir, 'report.md')
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(build_report(resolved, variants, extra))
    return path
