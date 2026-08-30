"""Close fill pricing and candle snapshots (shared by main and scratch tools)."""

import pandas as pd

from shared.constants import (
    reason_is_hold_label,
    reason_is_rsi_exit,
    reason_is_stop_exit,
    reason_is_tp1_exit,
    reason_is_trailed_stop,
    reason_is_trade_exit,
)


def _build_candle_snapshot(
    market_data, signal_data, n=20, entry_price=None, entry_date=None, pos_data=None,
    chart_levels_from_position=False, reason_override=None,
):
    start_idx = max(0, len(market_data) - n)
    df = market_data.iloc[start_idx:]

    candles = []
    for ts, row in df.iterrows():
        candles.append({
            "date": str(ts)[:10],
            "open": round(float(row["open"]), 8),
            "high": round(float(row["high"]), 8),
            "low": round(float(row["low"]), 8),
            "close": round(float(row["close"]), 8),
        })

    if chart_levels_from_position and pos_data:
        sl = pos_data.get("stop_loss", 0.0)
        tp = pos_data.get("take_profit", 0.0)
    else:
        sl = signal_data.get("stop_loss")
        if (sl is None or sl == 0.0) and pos_data:
            sl = pos_data.get("stop_loss", 0.0)
        tp = signal_data.get("take_profit")
        if (tp is None or tp == 0.0) and pos_data:
            tp = pos_data.get("take_profit", 0.0)

    if entry_price is not None:
        final_entry_price = entry_price
    elif pos_data:
        final_entry_price = pos_data.get("entry_price")
    else:
        final_entry_price = None
    final_entry_date = str(entry_date)[:10] if entry_date else (pos_data.get("entry_date") if pos_data else None)

    indicators = signal_data.get("indicators", {})
    sliced_indicators = {}
    for key, values in indicators.items():
        if hasattr(values, "iloc"):
            sliced_indicators[key] = [round(float(v), 8) if pd.notnull(v) else None for v in values.iloc[start_idx:]]
        elif isinstance(values, list):
            sliced_indicators[key] = values[start_idx:]

    display_reason = reason_override if reason_override is not None else signal_data.get("reason", "")
    return {
        "candles": candles,
        "stop_loss": sl,
        "take_profit": tp,
        "indicators": sliced_indicators,
        "reason": display_reason,
        "entry_price": final_entry_price,
        "entry_date": final_entry_date,
    }


def _classify_exit_kind(signal_data: dict, pos_data: dict, close_reason: str = None) -> str:
    reason = close_reason or signal_data.get("reason", "") or ""
    pct = clamp_quantity_pct(signal_data.get("quantity_pct", 1.0))
    if reason_is_tp1_exit(reason) and pct < 1.0:
        return "tp1_partial"
    if reason_is_trailed_stop(reason):
        return "trailed_stop"
    if reason_is_stop_exit(reason) or reason_is_rsi_exit(reason):
        return "stop_loss"
    return "other"


def build_close_snapshot(market_data, signal_data, pos_data, fill_price, close_reason=None, n=20):
    if not pos_data:
        pos_data = {}
    entry_price = pos_data.get("entry_price")
    entry_date = pos_data.get("entry_date")
    pct = clamp_quantity_pct(signal_data.get("quantity_pct", 1.0))
    effective_reason = close_reason or ""

    snap = _build_candle_snapshot(
        market_data, signal_data, n=n,
        entry_price=entry_price, entry_date=entry_date, pos_data=pos_data,
        chart_levels_from_position=True,
        reason_override=effective_reason,
    )
    sl_at_exit = float(pos_data.get("stop_loss") or 0)
    tp_at_exit = float(pos_data.get("take_profit") or 0)
    snap["stop_loss"] = sl_at_exit
    snap["take_profit"] = tp_at_exit
    snap["stop_loss_at_exit"] = sl_at_exit
    snap["take_profit_at_exit"] = tp_at_exit
    snap["exit_kind"] = _classify_exit_kind(signal_data, pos_data, close_reason=effective_reason)
    snap["quantity_pct"] = pct
    snap["exit_price"] = fill_price
    exit_date = last_bar_date(market_data)
    if exit_date:
        snap["exit_date"] = exit_date
    if effective_reason:
        snap["reason"] = effective_reason
    return snap


def last_bar_date(market_data):
    if market_data is None or market_data.empty:
        return None
    return str(market_data.index[-1])[:10]


def bar_close_price(market_data) -> float:
    return float(market_data['close'].iloc[-1])


def is_stop_or_trail_reason(reason: str) -> bool:
    return reason_is_stop_exit(reason) or reason_is_trailed_stop(reason)


def _level_price(signal_data, pos_data, key):
    raw = signal_data.get(key) if signal_data else None
    if raw is None or raw == 0:
        raw = pos_data.get(key) if pos_data else None
    try:
        value = float(raw or 0)
    except (TypeError, ValueError):
        return 0.0
    return value if value > 0 else 0.0


def _execution_price(bar_close, signal_data, pos_data):
    reason = signal_data.get('reason', '') or ''
    if reason_is_tp1_exit(reason):
        tp = _level_price(signal_data, pos_data, 'take_profit')
        if tp > 0:
            return tp
        return float(bar_close)
    if not pos_data or not is_stop_or_trail_reason(reason):
        return float(bar_close)
    sl = _level_price(signal_data, pos_data, 'stop_loss')
    if sl > 0:
        return sl
    return float(bar_close)


def resolve_close_fill_price(bar_close, signal_data, pos_data, fallback_reason=None):
    reason = signal_data.get('reason', '') or fallback_reason or ''
    if reason_is_hold_label(reason) and fallback_reason:
        reason = fallback_reason
    ctx = {**signal_data, 'reason': reason}
    return _execution_price(bar_close, ctx, pos_data)


def _pnl_for_close(position_side, quantity, entry_price, fill_price):
    qty = float(quantity)
    entry = float(entry_price)
    fill = float(fill_price)
    if position_side == 'LONG':
        return qty * (fill - entry)
    return qty * (entry - fill)


def _cash_delta_for_fill_change(position_side, quantity, old_fill, new_fill):
    qty = float(quantity)
    if position_side == 'LONG':
        return qty * (new_fill - old_fill)
    return qty * (old_fill - new_fill)


def apply_close_fill_to_event(event, position_side, fill_price, entry_price=None):
    entry = float(entry_price if entry_price is not None else event.get('entry_price', event['price']))
    qty = float(event['quantity'])
    old_fill = float(event['price'])
    fill = float(fill_price)
    event['entry_price'] = entry
    event['price'] = fill
    event['total_value'] = qty * fill
    event['pnl'] = _pnl_for_close(position_side, qty, entry, fill)
    return _cash_delta_for_fill_change(position_side, qty, old_fill, fill)


def reason_with_fill(signal_data, fill_price):
    """Rewrite stop/trail reason so ledger shows actual fill price."""
    reason = signal_data.get('reason', '') or ''
    for prefix in ('Stop Loss Hit @', 'Short Stop Loss Hit @', 'Trailed Stop Hit @', 'Short Trailed Stop Hit @'):
        if prefix in reason:
            sl_marker = '(SL '
            sl_idx = reason.find(sl_marker)
            label = reason.split('@')[0].strip()
            if sl_idx == -1:
                return f'{label} @ {fill_price}'
            return f'{label} @ {fill_price} {reason[sl_idx:]}'
    return reason


def resolve_close_reason(signal_data, fill_price, ledger_reason=None):
    """
    Pick the close reason to store on ledger rows.

    Never return hold labels (Waiting/Neutral). Prefer the live exit signal; else keep
    the existing ledger reason; else fill-adjusted stop/trail text.
    """
    from_signal = reason_with_fill(signal_data, fill_price)
    if reason_is_trade_exit(from_signal):
        return from_signal

    prior = ledger_reason or ''
    if reason_is_trade_exit(prior):
        return reason_with_fill({'reason': prior}, fill_price)

    if from_signal and not reason_is_hold_label(from_signal):
        return from_signal
    return prior


def clamp_quantity_pct(pct, default=1.0):
    try:
        v = float(pct)
    except (TypeError, ValueError):
        return default
    if v <= 0:
        return default
    return min(1.0, v)
