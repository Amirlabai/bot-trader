"""Write the baseline replay into the learning log.

    python -m research.export_learning [--years 4] [--refresh]

Produces research/cache/learning/backfill_trades.jsonl (source='backfill', gross R).
bot-trader has no learning pipeline yet, so the file stays inside research/.
"""

from __future__ import annotations

import argparse
import json
import os

import research  # noqa: F401
from research.run import run_experiment
from research.features import BACKFILL_FILE
from research.settings import DEFAULT_YEARS, LEARNING_DIR

LEARNING_KEYS = (
    'source', 'symbol', 'entry_date', 'closed_at', 'entry_price', 'initial_stop_loss',
    'exit_price', 'exit_reason', 'exit_kind', 'r_multiple', 'mfe_r', 'mae_r',
    'give_back_r', 'bars_held', 'features',
)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--years', type=float, default=DEFAULT_YEARS)
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()

    spec = {'name': 'learning_backfill', 'years': args.years, 'fee_rate': 0.0,
            'include_baseline': True}
    result = run_experiment(spec, refresh=args.refresh, write=False)
    trades = result['trades']
    params = result['resolved']['strategy_params']
    out_dir = LEARNING_DIR
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, BACKFILL_FILE)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as handle:
        for _, row in trades.iterrows():
            item = {k: row[k] for k in LEARNING_KEYS}
            item['params'] = params
            handle.write(json.dumps(item, default=str) + '\n')
    os.replace(tmp, path)
    print(f'Wrote {len(trades)} trades to {path}')


if __name__ == '__main__':
    main()
