"""Walk-forward probabilities: refit on an expanding window, predict the next block.

Training rows are taken baseline trades whose close is before the block starts,
so no label from the block (or later) leaks into its model. Skip thresholds are
quantiles of the model's own training-set probabilities, never of the block.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from research.filters.dataset import FEATURES
from research.filters.models import make_model

MIN_TRAIN_ROWS = 100


def blocks(first: pd.Timestamp, last: pd.Timestamp, train_months: int, refit_months: int) -> list:
    start = pd.Timestamp(first) + pd.DateOffset(months=train_months)
    out = []
    while start <= last:
        end = start + pd.DateOffset(months=refit_months)
        out.append((start, end))
        start = end
    return out


def walk_forward(table: pd.DataFrame, model_name: str, *, train_months: int = 18,
                 refit_months: int = 3, skip_q=(0.1, 0.2, 0.3, 0.4, 0.5)):
    """Return (probabilities DataFrame, windows list, last fitted model)."""
    probs = []
    windows = []
    model = None
    if table.empty:
        return pd.DataFrame(), windows, model
    for start, end in blocks(table['ts'].min(), table['ts'].max(), train_months, refit_months):
        train = table.loc[table['taken'] & (table['closed_at'] < start)]
        test = table.loc[(table['ts'] >= start) & (table['ts'] < end)]
        if len(train) < MIN_TRAIN_ROWS or train['y'].nunique() < 2 or test.empty:
            continue
        model = make_model(model_name)
        X = train[FEATURES].to_numpy(dtype=float)
        y = train['y'].to_numpy(dtype=int)
        model.fit(X, y)
        p_train = model.predict_proba(X)[:, 1]
        thresholds = {q: float(np.quantile(p_train, 1.0 - q)) for q in skip_q}
        p_test = model.predict_proba(test[FEATURES].to_numpy(dtype=float))[:, 1]
        windows.append({
            'start': start, 'end': end, 'n_train': int(len(train)),
            'train_last_close': train['closed_at'].max(), 'base_rate': float(y.mean()),
            'thresholds': thresholds,
        })
        chunk = test[['symbol', 'ts']].copy()
        chunk['p'] = p_test
        chunk['window_start'] = start
        for q, thr in thresholds.items():
            chunk[f'skip_{q:g}'] = p_test > thr
        probs.append(chunk)
    out = pd.concat(probs, ignore_index=True) if probs else pd.DataFrame()
    return out, windows, model
