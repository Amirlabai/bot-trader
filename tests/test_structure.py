import math

import numpy as np

from research.structure import Structure, pivot_highs


def _st(high, close=None, k=2, lookback=50):
    high = np.array(high, dtype=float)
    close = high - 0.5 if close is None else np.array(close, dtype=float)
    low = close - 1.0
    atr = np.full(len(high), 1.0)
    return Structure(high, low, close, atr, k=k, lookback=lookback)


def test_pivot_detection():
    high = [1, 2, 5, 2, 1, 3, 7, 3, 1]
    assert list(pivot_highs(np.array(high, float), 2)) == [2, 6]


def test_pivot_only_known_k_bars_later():
    st = _st([1, 2, 5, 2, 1, 1, 1, 1], close=[0.5] * 8)
    # pivot at bar 2 is confirmed at bar 4 (k = 2)
    assert math.isnan(st.resistance(3))
    assert st.resistance(4) == 5.0


def test_resistance_is_nearest_level_above_close():
    high = [1, 9, 1, 1, 6, 1, 1, 8, 1, 1, 1, 1]
    close = [0.5] * 11 + [5.0]
    st = _st(high, close=close)
    assert st.resistance(11) == 6.0


def test_open_air_when_price_above_all_pivots():
    high = [1, 4, 1, 1, 1, 1]
    st = _st(high, close=[0.5, 0.5, 0.5, 0.5, 0.5, 4.5])
    assert math.isnan(st.resistance(5))


def test_band_high_excludes_current_bar():
    st = _st([1, 3, 2, 10])
    assert st.band_high(3, 3) == 3.0
