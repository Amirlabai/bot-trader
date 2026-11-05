"""Live confirm_entry (higher-high) wallets must match the research entry mode bar for bar.

Live: MovingAverageStrategy with params['confirm_entry'], stepped one day at a time like
src/main.py (tests/test_research_parity._live_replay). Research: base signals plus
research.entries EntryMode hh_swing3_w10 (trigger 'close') in research.engine.simulate.
"""

import numpy as np
import pandas as pd
import pytest

from research.engine import simulate
from research.entries import EntryContext, EntryMode
from research.exit_policy import ExitPolicy
from research.run import base_exit
from research.signals import compute_signals
from strategies.moving_average import MovingAverageStrategy
from tests.test_research_parity import DAILY, WEEKLY, _live_replay, _series

CONFIRM = {'type': 'higher_high', 'ref': 'swing_high', 'within': 10, 'pivot_k': 3, 'lookback': 120}
MODE = EntryMode(type='higher_high', ref='swing_high', within=10, pivot_k=3, lookback=120)


def _engine(df, params):
    signals = compute_signals(df, MovingAverageStrategy(params))
    ctx = EntryContext(signals, MODE, params['short_window'], params['long_window'], history=df)
    policy = ExitPolicy.from_dict(base_exit(params))
    trades = simulate('SYN', signals, policy, fee_rate=0.0, entry_mode=MODE, entry_ctx=ctx)
    return trades, [(pd.Timestamp(t['entry_date']), pd.Timestamp(t['closed_at']), t['r_multiple'])
                    for t in trades]


@pytest.mark.parametrize('seed', [1, 13, 42])
def test_confirm_wallet_matches_research_mode(seed):
    df = _series(seed, n=1100)
    raw, engine = _engine(df, DAILY)
    live = _live_replay(df, {**DAILY, 'confirm_entry': CONFIRM})
    assert len(live) > 3
    assert any(t['bars_waited'] > 0 for t in raw)
    assert [(a, b) for a, b, _ in engine] == [(a, b) for a, b, _ in live]
    assert [r for *_, r in engine] == pytest.approx([r for *_, r in live], abs=1e-9)


def test_confirm_wallet_matches_research_mode_weekly_trend():
    df = _series(3, n=1500)
    _raw, engine = _engine(df, WEEKLY)
    live = _live_replay(df, {**WEEKLY, 'confirm_entry': CONFIRM})
    assert len(live) > 2
    assert [(a, b) for a, b, _ in engine] == [(a, b) for a, b, _ in live]
    assert [r for *_, r in engine] == pytest.approx([r for *_, r in live], abs=1e-9)


def _frame(close, high=None):
    close = np.asarray(close, dtype=float)
    high = close + 0.5 if high is None else np.asarray(high, dtype=float)
    idx = pd.date_range('2024-01-01', periods=len(close), freq='1D')
    return pd.DataFrame({'open': close, 'high': high, 'low': close - 0.5, 'close': close,
                         'volume': 1.0}, index=idx)


class _Scripted(MovingAverageStrategy):
    """Base entries forced at chosen bars, so the confirm rules can be checked directly."""

    def __init__(self, params, entry_bars, stop):
        super().__init__(params)
        self._entry_bars, self._stop = set(entry_bars), stop

    def _generate_base_signal(self, market_data, position_data):
        i = len(market_data) - 1
        if i in self._entry_bars:
            return {'action': 'buy', 'is_entry': True, 'stop_loss': self._stop,
                    'current_atr': 1.0, 'reason': 'Golden Cross'}
        return {'action': 'hold', 'reason': 'Waiting', 'current_atr': 1.0}


PARAMS = {'short_window': 2, 'long_window': 4, 'sl_atr': 1.0, 'long_only': True,
          'confirm_entry': {**CONFIRM, 'ref': 'signal_high'}}


def test_enters_on_first_close_above_signal_high_only():
    close = [100.0] * 30 + [101, 101.2, 101.4, 102, 103, 104]
    df = _frame(close)
    strat = _Scripted(PARAMS, entry_bars=[30], stop=95.0)
    # Signal bar 30, high 101.5. Bar 33 closes 102 > 101.5: enter there, not before or after.
    decisions = [strat.generate_signal(df.iloc[:i + 1], None) for i in range(30, len(df))]
    entered = [i + 30 for i, d in enumerate(decisions) if d.get('is_entry')]
    assert entered == [33]
    assert decisions[3]['stop_loss'] == pytest.approx(101.0)


def test_cancel_on_close_below_signal_stop():
    close = [100.0] * 30 + [101, 94, 102]
    strat = _Scripted(PARAMS, entry_bars=[30], stop=95.0)
    sig = strat.generate_signal(_frame(close), None)
    assert not sig.get('is_entry') and sig['reason'] == 'Confirmation cancelled'


def test_expires_after_within_bars():
    close = [100.0] * 30 + [101] + [101.0] * 10 + [110]
    strat = _Scripted(PARAMS, entry_bars=[30], stop=95.0)
    assert not strat.generate_signal(_frame(close), None).get('is_entry')


def test_signal_formed_while_in_position_is_honored_by_engine_and_live():
    # Signal at 5 -> confirmed at 7 (close 102 > high 101.5). While held, a new signal at 10
    # (high 103.7). Bar 12 wicks to the stop (exit). Bar 14 closes above 103.7: both enter
    # there. Bar 16 wicks out the second leg.
    close = [100.0] * 5 + [101, 101.2, 102, 102.5, 103, 103.2, 103.4, 103.5, 103.6, 104, 104.2, 104.3, 104.4]
    df = _frame(close)
    df.iloc[12, df.columns.get_loc('low')] = 100.0
    df.iloc[16, df.columns.get_loc('low')] = 100.0
    n = len(df)
    signals = pd.DataFrame({
        'open': df['open'], 'high': df['high'], 'low': df['low'], 'close': df['close'],
        'atr': 1.0, 'entry': [i in (5, 10) for i in range(n)], 'above_trend': True,
        'stop': [95.0 if i in (5, 10) else np.nan for i in range(n)], 'features': '',
    }, index=df.index)
    mode = EntryMode(type='higher_high', ref='signal_high', within=10)
    ctx = EntryContext(signals, mode, 2, 4, history=df)
    trades = simulate('SYN', signals, ExitPolicy(sl_atr=1.0, trail_atr=3.0), entry_mode=mode, entry_ctx=ctx)
    legs = [(t['entry_date'][:10], t['closed_at'][:10], t['signal_date'][:10]) for t in trades]
    assert legs == [('2024-01-08', '2024-01-13', '2024-01-06'), ('2024-01-15', '2024-01-17', '2024-01-11')]
    strat = _Scripted(PARAMS, entry_bars=[5, 10], stop=95.0)
    assert strat.generate_signal(df.iloc[:15], None).get('is_entry')      # bar 14
    assert not strat.generate_signal(df.iloc[:14], None).get('is_entry')  # bar 13
