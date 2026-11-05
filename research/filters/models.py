"""Classifiers for false starts. Kept small and regularized on purpose."""

from __future__ import annotations

from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

MODELS = ('logistic', 'gbm')


def make_model(name: str):
    if name == 'logistic':
        # Weights on standardized inputs; exportable to JSON for live scoring later.
        return make_pipeline(
            SimpleImputer(strategy='median'),
            StandardScaler(),
            LogisticRegression(C=0.3, max_iter=2000),
        )
    if name == 'gbm':
        return HistGradientBoostingClassifier(
            max_depth=3,
            min_samples_leaf=40,
            learning_rate=0.05,
            max_iter=150,
            l2_regularization=1.0,
            random_state=0,
        )
    raise ValueError(f'Unknown model {name!r}; use one of {MODELS}')


def logistic_weights(model, features) -> dict:
    """Standardized coefficients (positive = more likely a false start)."""
    coef = model[-1].coef_[0]
    return dict(sorted(zip(features, coef), key=lambda kv: -abs(kv[1])))
