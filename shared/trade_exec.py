"""Close execution shared by live main and resim (do not import main)."""

from shared.constants import reason_is_tp1_exit, tp1_already_done
from shared.exit_snapshots import (
    bar_close_price,
    build_close_snapshot,
    clamp_quantity_pct,
    resolve_close_fill_price,
    resolve_close_reason,
)


def apply_tp1_updates(ledger, strategy_id, symbol, signal_data, *, verbose=False):
    new_sl = signal_data.get('stop_loss')
    if new_sl is not None and new_sl > 0:
        ledger.update_stop_loss(strategy_id, symbol, new_sl)
    if reason_is_tp1_exit(signal_data.get('reason', '') or ''):
        ledger.mark_tp1_hit(strategy_id, symbol)
        if verbose:
            print(f'    TP1 HIT RECORDED for {symbol}')


def execute_close(
    ledger, strategy_id, symbol, market_data, pos_data, signal_data, position_side,
    *, event_ts=None, build_snapshots=False, verbose=True,
):
    """Close or reduce. Returns (pos_data, position_side, filled_tp1)."""
    skip_dup_tp1 = (
        reason_is_tp1_exit(signal_data.get('reason', ''))
        and tp1_already_done(pos_data)
    )
    if skip_dup_tp1:
        if verbose:
            kind = 'cover' if position_side == 'SHORT' else 'sell'
            print(f'    SKIP duplicate TP1 {kind} for {symbol} (TP1 already taken)')
        apply_tp1_updates(ledger, strategy_id, symbol, signal_data, verbose=verbose)
        pos_data = ledger.get_position(strategy_id, symbol)
        return pos_data, pos_data.get('side') if pos_data else None, False

    if verbose:
        print(
            f"    Signal {'BUY' if position_side == 'SHORT' else 'SELL'} "
            f'-> Closing {position_side} {symbol}'
        )
    pct = clamp_quantity_pct(signal_data.get('quantity_pct', 1.0))
    qty = pos_data['qty'] * pct
    fill_action = 'buy' if position_side == 'SHORT' else 'sell'
    bar_close = bar_close_price(market_data)
    fill_price = resolve_close_fill_price(bar_close, signal_data, pos_data)
    close_reason = resolve_close_reason(signal_data, fill_price)
    snapshot = None
    if build_snapshots:
        snapshot = build_close_snapshot(
            market_data, signal_data, pos_data, fill_price, close_reason=close_reason,
        )
    if ledger.update_position(
        strategy_id, symbol, qty, fill_price, fill_action,
        candle_snapshot=snapshot, reason=close_reason, event_ts=event_ts,
    ):
        if verbose:
            label = 'COVER SHORT' if position_side == 'SHORT' else 'SELL LONG'
            print(f'    EXECUTED {label}: {qty:.6f} {symbol} @ {fill_price}')
        apply_tp1_updates(ledger, strategy_id, symbol, signal_data, verbose=verbose)
        filled_tp1 = reason_is_tp1_exit(signal_data.get('reason', '') or '')
        pos_data = ledger.get_position(strategy_id, symbol)
        return pos_data, pos_data.get('side') if pos_data else None, filled_tp1
    return pos_data, position_side, False


def maybe_same_bar_sl(
    strategy, ledger, strategy_id, symbol, market_data, pos_data,
    *, current_atr=None, event_ts=None, build_snapshots=False, verbose=True,
):
    """After a real TP1 fill, re-check the same bar's wick against remainder SL."""
    if not pos_data:
        return pos_data, None
    follow = strategy.follow_up_risk(market_data, pos_data, current_atr=current_atr)
    if not follow:
        return pos_data, pos_data.get('side')
    side = pos_data.get('side')
    action = follow.get('action')
    if action == 'hold':
        new_sl = follow.get('stop_loss')
        if new_sl is not None and new_sl > 0:
            ledger.update_stop_loss(strategy_id, symbol, new_sl)
            if verbose:
                print(f'    UPDATED SL: {new_sl}')
        return pos_data, side
    if side == 'LONG' and action != 'sell':
        return pos_data, side
    if side == 'SHORT' and action != 'buy':
        return pos_data, side
    if verbose:
        print(f'    Same-bar SL after TP1 for {symbol}')
    pos_data, side, _filled = execute_close(
        ledger, strategy_id, symbol, market_data, pos_data, follow, side,
        event_ts=event_ts, build_snapshots=build_snapshots, verbose=verbose,
    )
    return pos_data, side


def apply_exit(
    ledger, strategy, strategy_id, symbol, market_data, pos_data, signal_data, position_side,
    *, event_ts=None, build_snapshots=False, verbose=True,
):
    """Close/reduce, then same-bar SL only if this call actually filled TP1."""
    pos_data, position_side, filled_tp1 = execute_close(
        ledger, strategy_id, symbol, market_data, pos_data, signal_data, position_side,
        event_ts=event_ts, build_snapshots=build_snapshots, verbose=verbose,
    )
    if filled_tp1:
        pos_data, position_side = maybe_same_bar_sl(
            strategy, ledger, strategy_id, symbol, market_data, pos_data,
            current_atr=signal_data.get('current_atr'),
            event_ts=event_ts, build_snapshots=build_snapshots, verbose=verbose,
        )
    return pos_data, position_side
