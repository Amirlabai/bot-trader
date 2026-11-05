import numpy as np
import pandas as pd
import pytest

from research.engine import simulate
from research.entries import EntryContext, EntryMode, check_pending, fresh_stop, start_pending
from research.signals import compute_signals
from research.exit_policy import ExitPolicy
from strategies.moving_average import MovingAverageStrategy

PARAMS = {'trend_window': 150, 'short_window': 20, 'long_window': 40,
          'atr_period': 15, 'sl_atr': 1.5, 'trail_atr': 3.0}


def _signals(closes, highs=None, entry_at=None, stop=90.0):
    n = len(closes)
    idx = pd.date_range('2024-01-01', periods=n, freq='1D')
    closes = np.array(closes, dtype=float)
    highs = closes + 0.5 if highs is None else np.array(highs, dtype=float)
    sig = pd.DataFrame({
        'high': highs, 'low': closes - 0.5, 'close': closes, 'atr': 2.0,
        'entry': False, 'above_trend': True, 'stop': np.nan, 'features': '',
    }, index=idx)
    if entry_at is not None:
        sig.iloc[entry_at, sig.columns.get_loc('entry')] = True
        sig.iloc[entry_at, sig.columns.get_loc('stop')] = stop
    return sig


def _rising(n=80):
    return list(np.linspace(100, 140, n))


def test_higher_high_waits_then_enters_with_fresh_stop():
    closes = _rising()
    closes[60] = 120.0           # signal bar
    closes[61] = 120.2           # not above the signal high (120.5)
    closes[62] = 121.0           # trigger
    sig = _signals(closes, entry_at=60, stop=117.0)
    mode = EntryMode(type='higher_high', within=3)
    ctx = EntryContext(sig, mode)
    action, pending = start_pending(ctx, 60, 117.0)
    assert action == 'wait' and pending['level'] == pytest.approx(120.5)
    assert check_pending(ctx, pending, 61) == 'wait'
    assert check_pending(ctx, pending, 62) == 'enter'
    assert fresh_stop(ctx, 62, 1.5) == pytest.approx(121.0 - 3.0)


def test_pending_expires_and_cancels():
    closes = _rising()
    sig = _signals(closes, entry_at=60)
    ctx = EntryContext(sig, EntryMode(type='higher_high', within=2))
    pending = {'s': 60, 'level': 1e9, 'stop': 0.0}
    assert check_pending(ctx, pending, 62) == 'wait'
    assert check_pending(ctx, pending, 63) == 'cancel'          # expired
    pending = {'s': 60, 'level': 1e9, 'stop': 1e9}
    assert check_pending(ctx, pending, 61) == 'cancel'          # close below the signal stop


def test_engine_entry_is_at_trigger_and_maps_to_signal():
    closes = _rising(120)
    closes[60] = 120.0
    closes[61] = 120.2
    closes[62] = 121.0
    closes[70] = 100.0           # stop out later
    sig = _signals(closes, entry_at=60, stop=117.0)
    trades = simulate('SYN', sig, ExitPolicy(), entry_mode=EntryMode(type='higher_high', within=3))
    assert len(trades) == 1
    t = trades[0]
    assert t['entry_price'] == pytest.approx(121.0)
    assert t['signal_date'] == '2024-03-01 00:00'      # bar 60
    assert t['bars_waited'] == 2


def test_signal_mode_equals_default_engine():
    rng = np.random.default_rng(5)
    n = 1500
    close = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.02, n)))
    opens = np.r_[close[0], close[:-1]]
    df = pd.DataFrame({
        'open': opens,
        'high': np.maximum(opens, close) * (1 + np.abs(rng.normal(0, 0.01, n))),
        'low': np.minimum(opens, close) * (1 - np.abs(rng.normal(0, 0.01, n))),
        'close': close, 'volume': 1.0,
    }, index=pd.date_range('2023-01-01', periods=n, freq='1D'))
    sig = compute_signals(df, MovingAverageStrategy(PARAMS))
    a = simulate('S', sig, ExitPolicy())
    b = simulate('S', sig, ExitPolicy(), entry_mode=EntryMode())
    assert [(x['entry_date'], x['r_net']) for x in a] == [(x['entry_date'], x['r_net']) for x in b]
    assert all(x['signal_date'] == x['entry_date'] for x in b)


def test_buy_stop_fills_at_level_and_keeps_signal_stop():
    closes = _rising(120)
    closes[60] = 120.0                     # signal high 120.5
    closes[61] = 120.1
    highs = np.array(closes) + 0.5
    highs[61] = 121.0                      # breaks 120.5 intrabar
    closes[70] = 100.0
    sig = _signals(closes, highs=highs, entry_at=60, stop=117.0)
    mode = EntryMode(type='higher_high', within=3, trigger='break')
    trades = simulate('SYN', sig, ExitPolicy(), entry_mode=mode)
    assert trades[0]['entry_price'] == pytest.approx(120.5)
    assert trades[0]['initial_stop_loss'] == pytest.approx(117.0)
    assert trades[0]['bars_waited'] == 1


def test_buy_stop_gap_fills_at_open():
    closes = _rising(120)
    closes[60] = 120.0
    closes[61] = 120.3                     # closes below the level, no fill yet
    closes[62] = 123.0
    highs = np.array(closes) + 0.1         # bar 62 high 123.1 reaches any level below it
    highs[60] = 120.5
    closes[70] = 100.0
    sig = _signals(closes, highs=highs, entry_at=60, stop=117.0)
    ctx = EntryContext(sig, EntryMode(type='higher_high', within=3, trigger='break'))
    pending = {'s': 60, 'level': 120.35, 'stop': 117.0}
    assert check_pending(ctx, pending, 62) == 'fill'
    from research.entries import fill_price
    assert fill_price(ctx, pending, 62) == pytest.approx(120.35)
    pending['level'] = 120.2              # bar 61 closed above it: open of bar 62 is 120.3
    assert fill_price(ctx, pending, 62) == pytest.approx(120.3)


def test_buy_stop_same_bar_reversal_is_a_loss():
    closes = _rising(120)
    closes[60] = 120.0
    highs = np.array(closes) + 0.5
    lows = np.array(closes) - 0.5
    highs[61] = 121.0
    closes[61] = 116.0                     # spikes through the level, then closes below the stop
    sig = _signals(closes, highs=highs, entry_at=60, stop=117.0)
    sig['low'] = lows
    sig.iloc[61, sig.columns.get_loc('low')] = 115.0
    trades = simulate('SYN', sig, ExitPolicy(),
                      entry_mode=EntryMode(type='higher_high', within=3, trigger='break'))
    assert trades[0]['entry_date'] == trades[0]['closed_at']
    assert trades[0]['r_multiple'] == pytest.approx(-1.0)
