"""Walk-forward must never train on a label that closes inside or after its test block."""

import numpy as np
import pandas as pd

from research.filters.dataset import FEATURES
from research.filters.walkforward import walk_forward


def _table(n=900, seed=0):
    rng = np.random.default_rng(seed)
    ts = pd.date_range('2020-01-01', periods=n, freq='1D')
    table = pd.DataFrame({f: rng.normal(size=n) for f in FEATURES})
    table['symbol'] = 'SYN'
    table['ts'] = ts
    table['taken'] = True
    hold = rng.integers(1, 60, n)
    table['closed_at'] = ts + pd.to_timedelta(hold, unit='D')
    # Label depends on one feature, so the model has something to learn.
    table['y'] = (table['atr_pct'] + rng.normal(scale=0.5, size=n) > 0).astype(int)
    table['r_net'] = np.where(table['y'] == 1, -1.0, 1.5)
    return table


def test_no_label_leaks_into_its_block():
    table = _table()
    probs, windows, _ = walk_forward(table, 'logistic', train_months=12, refit_months=3)
    assert windows and not probs.empty
    for w in windows:
        assert w['train_last_close'] < w['start']
    assert (probs['ts'] >= probs['window_start']).all()


def test_model_learns_signal_out_of_sample():
    from sklearn.metrics import roc_auc_score
    table = _table()
    probs, _, _ = walk_forward(table, 'logistic', train_months=12, refit_months=3)
    merged = table.merge(probs, on=['symbol', 'ts'])
    assert roc_auc_score(merged['y'], merged['p']) > 0.7
