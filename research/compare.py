"""Line up variants across result directories.

    python -m research.compare research/results/scale_out_grid/<run> research/results/baseline/<run>
    python -m research.compare <run> <run> --variants baseline r1_sell50 --out compare.md

By default it shows the baseline plus the top 5 in-sample variants of each run.
Runs with different data ranges or code (see each spec.json) are not directly
comparable; the header lists both so differences are visible.
"""

from __future__ import annotations

import argparse
import json
import os

import pandas as pd

import research  # noqa: F401
from research.report import BASELINE, _n, _r, flag_better


def load_run(path: str) -> tuple[dict, pd.DataFrame]:
    with open(os.path.join(path, 'spec.json'), 'r', encoding='utf-8') as handle:
        resolved = json.load(handle)
    return resolved, flag_better(pd.read_csv(os.path.join(path, 'variants.csv')))


def compare(paths: list[str], variants: list[str] | None = None) -> str:
    runs = [(p, *load_run(p)) for p in paths]
    names = list(variants or [])
    if not names:
        names = [BASELINE]
        for _, _, v in runs:
            top = v.loc[v['variant'] != BASELINE].sort_values('is_total_r', ascending=False)
            names += [n for n in top['variant'].head(5) if n not in names]
    md = ['# Run comparison', '']
    for path, resolved, _ in runs:
        pairs = resolved.get('pairs') or {}
        last = max((r[1] for r in pairs.values()), default='-')
        md.append(
            f"- `{os.path.basename(os.path.normpath(path))}` ({resolved['spec']['name']}): git "
            f"{resolved['git_sha']}{' dirty' if resolved.get('git_dirty') else ''}, "
            f"{len(pairs)} pairs, last bar {last}, OOS from {resolved['oos_from'][:10]}"
        )
    md += ['', '| Variant | Run | Trades | Total R | IS total | OOS total | IS max DD | Beats baseline |',
           '|---|---|---|---|---|---|---|---|']
    for name in names:
        for path, _, v in runs:
            row = v.loc[v['variant'] == name]
            if row.empty:
                continue
            r = row.iloc[0]
            md.append(
                f"| {name} | {os.path.basename(os.path.normpath(path))} | {int(r['all_n'])} | "
                f"{_r(r['all_total_r'])} | {_r(r['is_total_r'])} | {_r(r['oos_total_r'])} | "
                f"{_n(r['is_max_dd_r'], 1)}R | {'yes' if r['better'] else 'no'} |"
            )
    return '\n'.join(md) + '\n'


def main():
    parser = argparse.ArgumentParser(description='Compare research runs.')
    parser.add_argument('runs', nargs='+')
    parser.add_argument('--variants', nargs='*', default=None)
    parser.add_argument('--out', default=None)
    args = parser.parse_args()
    text = compare(args.runs, args.variants)
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as handle:
            handle.write(text)
        print(f'Wrote {args.out}')
    else:
        print(text)


if __name__ == '__main__':
    main()
