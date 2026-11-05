"""The research engine (baseline policy) must match the live daily wallet bar for bar.

Replaces asset-trail tests/test_engine_parity.py (which replayed paper_shadow).
Live here = MovingAverageStrategy.generate_signal on the growing history, with a
position dict shaped like src/ledger_manager.update_position and exit fills from
shared.exit_snapshots.resolve_close_fill_price, as src/main.py does each day.
"""

import numpy as np
import pandas as pd
import pytest

from research.engine import simulate
from research.exit_policy import ExitPolicy
from research.run import base_exit
from research.signals import compute_signals, warmup_bars
from shared.exit_snapshots import resolve_close_fill_price
from shared.path_sim import build_signals, simulate_long_path
from strategies.moving_average import MovingAverageStrategy

# Live crypto asset-trail wallet (src/config.py _CRYPTO_EMA + _asset_trail_params), minus trend_weekly.
DAILY = {
    'short_window': 10, 'long_window': 20, 'trend_window': 150, 'atr_period': 14,
    'adx_period': 14, 'adx_min': 0, 'vol_ma_period': 20, 'vol_mult': 0.0, 'atr_buffer': 0.0,
    'sl_atr': 1.0, 'trail_atr': 3.0, 'trail_arm_r': 0.0, 'long_only': True,
    'use_trailing': True, 'trail_from_entry': True, 'skip_tp1': True, 'trend_exit': False,
}
WEEKLY = {**DAILY, 'trend_weekly': True}
TP1 = {**DAILY, 'trail_from_entry': False, 'skip_tp1': False}


def _series(seed, n=900):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.001, 0.03, n)))
    opens = np.r_[close[0], close[:-1]]
    high = np.maximum(opens, close) * (1 + np.abs(rng.normal(0, 0.015, n)))
    low = np.minimum(opens, close) * (1 - np.abs(rng.normal(0, 0.015, n)))
    idx = pd.date_range('2020-01-01', periods=n, freq='1D')
    return pd.DataFrame({'open': opens, 'high': high, 'low': low, 'close': close,
                         'volume': rng.uniform(1, 2, n)}, index=idx)


def _live_replay(df, params):
    """(entry_ts, exit_ts, R) per closed leg, stepping the live strategy one day at a time."""
    strategy = MovingAverageStrategy(params)
    trades, pos = [], None
    for i in range(warmup_bars(params), len(df)):
        window = df.iloc[:i + 1]
        signal = strategy.generate_signal(window, pos)
        bar_close = float(window['close'].iloc[-1])
        if pos is None:
            if signal.get('action') == 'buy' and signal.get('is_entry'):
                stop = float(signal['stop_loss'])
                pos = {'qty': 1.0, 'initial_qty': 1.0, 'entry_price': bar_close, 'side': 'LONG',
                       'stop_loss': stop, 'take_profit': signal.get('take_profit', 0.0),
                       'tp1_hit': False, 'initial_stop_loss': stop,
                       'entry_atr': float(signal['current_atr']), '_ts': df.index[i], '_pnl': 0.0}
            continue
        action = signal.get('action')
        if action == 'sell':
            pct = float(signal.get('quantity_pct', 1.0))
            fill = float(resolve_close_fill_price(bar_close, signal, pos))
            qty = pos['qty'] * pct
            pos['_pnl'] += qty * (fill - pos['entry_price'])
            pos['qty'] -= qty
            if signal.get('stop_loss'):
                pos['stop_loss'] = float(signal['stop_loss'])
            if pct < 1.0:
                pos['tp1_hit'] = True
            if pos['qty'] <= 1e-12:
                risk = pos['entry_price'] - pos['initial_stop_loss']
                trades.append((pos['_ts'], df.index[i], pos['_pnl'] / risk))
                pos = None
        elif action == 'hold' and signal.get('stop_loss') and signal['stop_loss'] > 0:
            pos['stop_loss'] = float(signal['stop_loss'])
    return trades


def _engine(df, params, **policy):
    signals = compute_signals(df, MovingAverageStrategy(params))
    exit_policy = ExitPolicy.from_dict({**base_exit(params), **policy})
    return [(pd.Timestamp(t['entry_date']), pd.Timestamp(t['closed_at']), t['r_multiple'])
            for t in simulate('SYN', signals, exit_policy, fee_rate=0.0)]


def _assert_same(engine, live):
    assert len(live) > 3
    assert [(a, b) for a, b, _ in engine] == [(a, b) for a, b, _ in live]
    assert [r for *_, r in engine] == pytest.approx([r for *_, r in live], abs=1e-9)


@pytest.mark.parametrize('seed', [1, 7, 42])
def test_baseline_matches_live_daily_wallet(seed):
    df = _series(seed)
    _assert_same(_engine(df, DAILY), _live_replay(df, DAILY))


@pytest.mark.parametrize('seed', [3, 11])
def test_baseline_matches_live_weekly_trend(seed):
    df = _series(seed, n=1250)
    _assert_same(_engine(df, WEEKLY), _live_replay(df, WEEKLY))


@pytest.mark.parametrize('seed', [5, 13])
def test_tp1_policy_matches_live_tp1_wallet(seed):
    df = _series(seed)
    assert base_exit(TP1)['tp1_live'] is True
    _assert_same(_engine(df, TP1), _live_replay(df, TP1))


def test_trail_arm_matches_live():
    params = {**DAILY, 'trail_arm_r': 1.0}
    df = _series(21)
    _assert_same(_engine(df, params), _live_replay(df, params))


@pytest.mark.parametrize('params', [DAILY, WEEKLY], ids=['daily', 'weekly'])
def test_entries_and_trades_match_path_sim(params):
    df = _series(9, n=1250)
    signals = compute_signals(df, MovingAverageStrategy(params))
    entry, atr, _exit = build_signals(df, params)
    offset = len(df) - len(signals)
    assert signals['entry'].to_numpy().tolist() == entry[offset:].tolist()

    trades = simulate('SYN', signals, ExitPolicy.from_dict(base_exit(params)), fee_rate=0.0)
    risk = {'equity_risk_pct': 0.01, 'min_risk_fraction': 0.0, 'min_notional_usd': 0.0,
            'max_notional_pct': 1.0}
    path = simulate_long_path(
        entry, df['close'].to_numpy(float), df['low'].to_numpy(float), atr,
        params['sl_atr'], params['trail_atr'], offset, 1e9, risk,
        trail_arm_r=params['trail_arm_r'], assert_invariants=False,
    )
    assert len(trades) > 3
    assert path['closed_trades'] == len(trades)
    assert path['wins'] == sum(1 for t in trades if t['r_multiple'] > 0)


def test_fees_reduce_r():
    df = _series(3)
    signals = compute_signals(df, MovingAverageStrategy(DAILY))
    gross = simulate('SYN', signals, ExitPolicy(), fee_rate=0.0)
    net = simulate('SYN', signals, ExitPolicy(), fee_rate=0.001)
    assert gross and all(n['r_net'] < g['r_net'] for g, n in zip(gross, net))
