"""Trade simulation over cached signals for one exit policy.

Rules match the live daily wallet (src/main.py + BaseStrategy.check_risk_management):
open at the entry bar close with the signal stop and the signal ATR frozen; exits
start on the next bar; no new entry on the bar that closed a trade.
Fills follow research/exit_policy.step_bar.
"""

from __future__ import annotations

import json
import math

import pandas as pd

from research.settings import BAR_HOURS
from research.settings import bar_ts
from research.exit_policy import ExitPolicy, open_position, step_bar


def _exit_kind(fills) -> str:
    last = fills[-1] if fills else None
    if last is None:
        return 'open'
    if last[0] == 'ladder':
        return 'scale_out'
    if last[0] == 'early':
        return 'early_exit'
    if last[0] == 'tp1':
        return 'tp1_partial'
    return 'trailed_stop' if last[3].startswith('Trailed') else 'stop_loss'


def _finish(symbol, policy, pos, entry_ts, exit_ts, max_high, min_low, features, fee_rate):
    entry = pos['entry_price']
    risk = entry - pos['initial_stop_loss']
    fills = pos['fills']
    sold = sum(f[2] for f in fills)
    gross_pnl = sum(f[2] * (f[1] - entry) for f in fills)
    fee_cost = fee_rate * entry + sum(fee_rate * f[1] * f[2] for f in fills)
    r_gross = gross_pnl / risk
    r_net = (gross_pnl - fee_cost) / risk
    avg_exit = (sum(f[1] * f[2] for f in fills) / sold) if sold else None
    mfe = max(0.0, (max_high - entry) / risk)
    mae = min(0.0, (min_low - entry) / risk)
    return {
        'variant': policy.name,
        'source': 'backfill',
        'symbol': symbol,
        'entry_date': bar_ts(entry_ts),
        'closed_at': bar_ts(exit_ts),
        'entry_price': entry,
        'initial_stop_loss': pos['initial_stop_loss'],
        'exit_price': avg_exit,
        'exit_reason': fills[-1][3] if fills else '',
        'exit_kind': _exit_kind(fills),
        'r_multiple': r_gross,
        'r_net': r_net,
        'mfe_r': mfe,
        'mae_r': mae,
        'give_back_r': mfe - r_gross,
        'bars_held': (pd.Timestamp(exit_ts) - pd.Timestamp(entry_ts)).total_seconds() / 3600.0 / BAR_HOURS,
        'ladder_fills': sum(1 for f in fills if f[0] in ('ladder', 'tp1')),
        'ambiguous_bars': pos['ambiguous_bars'],
        'fills': json.dumps([[f[0], f[1], f[2]] for f in fills]),
        'features': features,
    }


def simulate(symbol: str, signals: pd.DataFrame, policy: ExitPolicy, fee_rate: float = 0.0,
             entry_allowed=None, entry_mode=None, entry_ctx=None) -> list[dict]:
    """Closed trades for one pair. A position still open at the last bar is dropped.

    entry_allowed: optional boolean array aligned with signals. A blocked entry
    leaves the pair flat, so a later signal can still enter (as live would).
    entry_mode: optional research.entries.EntryMode. None or 'signal' buys at the
    crossover close (today). Other modes hold a pending signal until it confirms.
    entry_ctx: optional prebuilt EntryContext for this pair and mode (speed).
    """
    if signals is None or signals.empty:
        return []
    ts = list(signals.index)
    high = signals['high'].to_numpy(dtype=float)
    low = signals['low'].to_numpy(dtype=float)
    close = signals['close'].to_numpy(dtype=float)
    atr = signals['atr'].to_numpy(dtype=float)
    entry = signals['entry'].to_numpy(dtype=bool)
    stop = signals['stop'].to_numpy(dtype=float)
    features = signals['features'].tolist()
    allowed = None if entry_allowed is None else list(entry_allowed)

    ctx = None
    if entry_mode is not None and entry_mode.type != 'signal':
        from research.entries import EntryContext
        ctx = entry_ctx or EntryContext(signals, entry_mode)
    if ctx is not None:
        from research.entries import check_pending, fill_price, fresh_stop, start_pending

    trades = []
    pos = None
    pending = None
    entry_i = signal_i = None
    max_high = min_low = None

    def _open(i, entry_stop, origin, price=None):
        nonlocal pos, entry_i, signal_i, max_high, min_low
        pos = open_position(close[i] if price is None else price, entry_stop, atr[i])
        entry_i, signal_i = i, origin
        max_high, min_low = -math.inf, math.inf

    def _step(i):
        """Apply bar i to the open position; book the trade when it closes."""
        nonlocal pos, max_high, min_low
        max_high = max(max_high, high[i])
        min_low = min(min_low, low[i])
        step_bar(pos, high[i], low[i], close[i], atr[i], policy)
        if pos['closed']:
            raw = features[signal_i] if signal_i is not None else ''
            feats = json.loads(raw) if raw else {}
            trade = _finish(
                symbol, policy, pos, ts[entry_i], ts[i], max_high, min_low, feats, fee_rate,
            )
            trade['signal_date'] = bar_ts(ts[signal_i])
            trade['bars_waited'] = entry_i - signal_i
            trades.append(trade)
            pos = None  # next entry is checked from bar i + 1

    for i in range(len(ts)):
        if pos is None:
            is_signal = entry[i] and not math.isnan(stop[i]) and stop[i] > 0 and (allowed is None or allowed[i])
            if ctx is None:
                if is_signal:
                    _open(i, stop[i], i)
                continue
            if is_signal:
                # A new crossover replaces any pending one.
                action, pending = start_pending(ctx, i, stop[i])
                if action == 'now':
                    _open(i, stop[i], i)
                continue
            if pending is not None:
                state = check_pending(ctx, pending, i)
                if state == 'enter':
                    new_stop = fresh_stop(ctx, i, policy.sl_atr)
                    if not math.isnan(new_stop) and 0 < new_stop < close[i]:
                        _open(i, new_stop, pending['s'])
                    pending = None
                elif state == 'fill':
                    # Buy-stop filled intrabar; the signal's stop stays. The fill bar is
                    # then stepped too, stop first, so a same-bar reversal is a loss.
                    price = fill_price(ctx, pending, i)
                    origin, stop_px = pending['s'], pending['stop']
                    pending = None
                    if price > stop_px > 0:
                        _open(i, stop_px, origin, price=price)
                        _step(i)
                elif state == 'cancel':
                    pending = None
            continue
        _step(i)
    return trades
