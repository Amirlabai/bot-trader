"""Research paths and defaults (daily bars, bot-trader crypto book)."""
from __future__ import annotations

import os

from research import REPO_ROOT

RESEARCH_DIR = os.path.join(REPO_ROOT, 'research')
EXPERIMENTS_DIR = os.path.join(RESEARCH_DIR, 'experiments')
RESULTS_DIR = os.path.join(RESEARCH_DIR, 'results')
CACHE_DIR = os.path.join(RESEARCH_DIR, 'cache')
SIGNALS_CACHE = os.path.join(CACHE_DIR, 'signals')
LEARNING_DIR = os.path.join(CACHE_DIR, 'learning')

# Live passes the full yfinance history (period='max') to generate_signal each day.
# None = the replay does the same (growing prefix). An int slides a fixed window.
WINDOW_BARS = None
# Spot taker fee per side, applied to every fill in research only.
DEFAULT_FEE_RATE = 0.001
# Trades opened in the last N months are out-of-sample.
DEFAULT_OOS_MONTHS = 12
DEFAULT_YEARS = 4.0
BAR_HOURS = 24.0
# Live wallet whose params and pairs the replay uses.
STRATEGY_ID = 'ma_crypto_long_trail'


def bar_ts(ts) -> str | None:
    """Bar label used as a trade key (same format as asset-trail: YYYY-MM-DD HH:MM)."""
    if ts is None:
        return None
    import pandas as pd
    return pd.Timestamp(ts).strftime('%Y-%m-%d %H:%M')
