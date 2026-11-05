import math

import pytest

from research.exit_policy import ExitPolicy, open_position, step_bar

# entry 100, initial stop 90 -> 1R = 10. Large ATR keeps the trail out of the way.
BIG_ATR = 100.0


def _pos():
    return open_position(100.0, 90.0)


def test_baseline_stops_at_initial_stop():
    pos = _pos()
    fills = step_bar(pos, high=101, low=89, close=95, atr=BIG_ATR, policy=ExitPolicy())
    assert pos['closed'] and fills == [('stop', 90.0, 1.0, fills[0][3])]
    assert fills[0][3].startswith('Stop Loss Hit')


def test_half_at_one_r():
    policy = ExitPolicy(name='h', step_r=1.0, fraction=0.5)
    pos = _pos()
    fills = step_bar(pos, high=110, low=99, close=105, atr=BIG_ATR, policy=policy)
    assert fills == [('ladder', 110.0, 0.5, 'Scale-out 1R')]
    assert pos['qty'] == pytest.approx(0.5) and not pos['closed']


def test_keep_selling_half_several_levels_in_one_bar():
    policy = ExitPolicy(name='h', step_r=1.0, fraction=0.5)
    pos = _pos()
    fills = step_bar(pos, high=131, low=99, close=125, atr=BIG_ATR, policy=policy)
    assert [f[1] for f in fills] == [110.0, 120.0, 130.0]
    assert [f[2] for f in fills] == pytest.approx([0.5, 0.25, 0.125])
    assert pos['qty'] == pytest.approx(0.125)


def test_increasing_share_and_cap():
    policy = ExitPolicy(name='inc', step_r=1.0, fraction=0.4, fraction_step=0.3)
    assert [policy.share(k) for k in range(4)] == pytest.approx([0.4, 0.7, 1.0, 1.0])
    pos = _pos()
    step_bar(pos, high=131, low=99, close=125, atr=BIG_ATR, policy=policy)
    # 0.4 of 1.0, then 0.7 of 0.6, then all of the rest at 3R.
    assert pos['closed'] and pos['qty'] == 0.0
    sizes = [f[2] for f in pos['fills']]
    assert sizes == pytest.approx([0.4, 0.42, 0.18])


def test_stop_fills_before_level_on_same_bar():
    policy = ExitPolicy(name='h', step_r=1.0, fraction=0.5)
    pos = _pos()
    fills = step_bar(pos, high=111, low=89, close=100, atr=BIG_ATR, policy=policy)
    assert [f[0] for f in fills] == ['stop']
    assert pos['ambiguous_bars'] == 1


def test_breakeven_after_first_sale():
    policy = ExitPolicy(name='be', step_r=1.0, fraction=0.5, breakeven_after_first=True)
    pos = _pos()
    step_bar(pos, high=110, low=99, close=105, atr=BIG_ATR, policy=policy)
    assert pos['stop_loss'] == 100.0
    fills = step_bar(pos, high=104, low=99.5, close=100, atr=BIG_ATR, policy=policy)
    assert fills[0][:3] == ('stop', 100.0, 0.5)
    assert fills[0][3].startswith('Trailed Stop Hit')


def test_trail_current_atr_mode_asset_trail_rule():
    # asset-trail rule: ATR 2 -> distance max(3*2, (3/1.5)*10) = 20, so close 125 proposes 105.
    pos = _pos()
    policy = ExitPolicy(atr_mode='current', sl_atr=1.5)
    step_bar(pos, high=126, low=120, close=125, atr=2.0, policy=policy)
    assert pos['stop_loss'] == pytest.approx(105.0)


def test_trail_frozen_uses_entry_atr_not_current():
    # Live daily rule: distance = trail_atr x entry ATR (4), whatever the bar ATR is.
    pos = open_position(100.0, 96.0, entry_atr=4.0)
    step_bar(pos, high=126, low=120, close=125, atr=50.0, policy=ExitPolicy())
    assert pos['stop_loss'] == pytest.approx(113.0)


def test_trail_frozen_derives_atr_from_initial_stop():
    # No entry ATR: (entry - initial stop) / sl_atr = 10 -> distance 30.
    pos = _pos()
    step_bar(pos, high=126, low=120, close=125, atr=2.0, policy=ExitPolicy())
    assert pos['stop_loss'] == pytest.approx(95.0)


def test_trail_arm_blocks_until_reached():
    policy = ExitPolicy(trail_arm_r=1.0)
    pos = open_position(100.0, 90.0, entry_atr=1.0)
    step_bar(pos, high=106, low=99, close=105, atr=1.0, policy=policy)  # 0.5R: not armed
    assert pos['stop_loss'] == pytest.approx(90.0)
    step_bar(pos, high=112, low=104, close=111, atr=1.0, policy=policy)  # 1.1R: armed
    assert pos['stop_loss'] == pytest.approx(108.0)


def test_tp1_live_wins_tie_and_moves_stop_to_entry():
    policy = ExitPolicy(tp1_live=True)
    pos = open_position(100.0, 90.0, entry_atr=10.0)
    fills = step_bar(pos, high=111, low=85, close=100, atr=10.0, policy=policy)
    assert [f[0] for f in fills] == ['tp1'] and fills[0][1] == pytest.approx(110.0)
    assert pos['qty'] == pytest.approx(0.5) and pos['stop_loss'] == pytest.approx(100.0)
    assert not pos['closed']
    fills = step_bar(pos, high=101, low=99, close=100, atr=10.0, policy=policy)
    assert pos['closed'] and fills[0][3].startswith('Stop Loss Hit')


def test_tp1_live_no_trail_before_tp1():
    policy = ExitPolicy(tp1_live=True)
    pos = open_position(100.0, 90.0, entry_atr=10.0)
    step_bar(pos, high=109, low=99, close=108, atr=1.0, policy=policy)
    assert pos['stop_loss'] == pytest.approx(90.0)


def test_max_steps_limits_ladder():
    policy = ExitPolicy(name='m', step_r=1.0, fraction=0.5, max_steps=1)
    pos = _pos()
    step_bar(pos, high=150, low=99, close=120, atr=BIG_ATR, policy=policy)
    assert len(pos['fills']) == 1 and pos['qty'] == pytest.approx(0.5)


def test_nan_atr_keeps_stop():
    pos = _pos()
    step_bar(pos, high=120, low=95, close=118, atr=math.nan, policy=ExitPolicy())
    assert pos['stop_loss'] == 90.0


def test_early_exit_fires_without_progress():
    policy = ExitPolicy(name='e', early_exit_bars=3, early_exit_min_r=0.5)
    pos = _pos()
    for _ in range(2):
        assert step_bar(pos, high=103, low=98, close=101, atr=BIG_ATR, policy=policy) == []
    fills = step_bar(pos, high=104, low=98, close=102, atr=BIG_ATR, policy=policy)
    assert fills[0][:3] == ('early', 102.0, 1.0) and pos['closed']


def test_early_exit_skipped_after_progress():
    policy = ExitPolicy(name='e', early_exit_bars=3, early_exit_min_r=0.5)
    pos = _pos()
    step_bar(pos, high=106, low=98, close=101, atr=BIG_ATR, policy=policy)  # best high +0.6R
    for _ in range(3):
        step_bar(pos, high=103, low=98, close=101, atr=BIG_ATR, policy=policy)
    assert not pos['closed']


def test_stop_before_early_exit_on_same_bar():
    policy = ExitPolicy(name='e', early_exit_bars=1, early_exit_min_r=0.5)
    pos = _pos()
    fills = step_bar(pos, high=101, low=89, close=95, atr=BIG_ATR, policy=policy)
    assert [f[0] for f in fills] == ['stop']


def test_early_exit_sells_only_the_remainder_after_a_ladder_fill():
    policy = ExitPolicy(name='e', step_r=0.25, fraction=0.5, early_exit_bars=1, early_exit_min_r=0.5)
    pos = _pos()
    fills = step_bar(pos, high=103, low=99, close=101, atr=BIG_ATR, policy=policy)
    assert [f[0] for f in fills] == ['ladder', 'early']
    assert fills[1][2] == pytest.approx(0.5)
