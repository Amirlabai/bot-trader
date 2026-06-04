"""Shared constants used by src and strategies (no sys.path hacks)."""

TP1_HIT_REASON_LONG = 'TP1 Hit'
TP1_HIT_REASON_SHORT = 'Short TP1 Hit'
TP1_EXIT_REASONS = frozenset({TP1_HIT_REASON_LONG, TP1_HIT_REASON_SHORT})

TRAILED_STOP_REASON_LONG = 'Trailed Stop Hit'
TRAILED_STOP_REASON_SHORT = 'Short Trailed Stop Hit'
TRAILED_STOP_EXIT_REASONS = frozenset({TRAILED_STOP_REASON_LONG, TRAILED_STOP_REASON_SHORT})

STOP_LOSS_REASON_LONG = 'Stop Loss Hit'
STOP_LOSS_REASON_SHORT = 'Short Stop Loss Hit'
STOP_LOSS_EXIT_REASONS = frozenset({STOP_LOSS_REASON_LONG, STOP_LOSS_REASON_SHORT})

# Default hold labels from strategies — must never be stored on OPEN/CLOSE ledger rows.
HOLD_REASON_LABELS = frozenset({
    'Waiting',
    'Neutral',
    'Updating Trailing Stop (Post-TP1)',
    'Updating Short Trailing Stop (Post-TP1)',
})

TP1_MAX_REMAINING_FRACTION = 0.55


def reason_is_hold_label(reason: str) -> bool:
    """True if reason is a no-trade / trailing-hold label, not an entry or exit."""
    reason = (reason or '').strip()
    if reason in HOLD_REASON_LABELS:
        return True
    return reason.startswith('Updating Trailing Stop')


def reason_is_tp1_exit(reason: str) -> bool:
    reason = reason or ''
    return any(reason == r or reason.startswith(f"{r} @") for r in TP1_EXIT_REASONS)


def reason_is_trailed_stop(reason: str) -> bool:
    reason = reason or ''
    return any(reason == r or reason.startswith(f"{r} @") for r in TRAILED_STOP_EXIT_REASONS)


def reason_is_stop_exit(reason: str) -> bool:
    reason = reason or ''
    if reason_is_trailed_stop(reason):
        return False
    return any(reason == r or reason.startswith(f"{r} @") for r in STOP_LOSS_EXIT_REASONS)


def reason_is_rsi_exit(reason: str) -> bool:
    reason = reason or ''
    return (
        ('RSI Oversold' in reason and 'Cover' in reason)
        or ('RSI Overbought' in reason and 'Close Long' in reason)
    )


def reason_is_trade_exit(reason: str) -> bool:
    """True if reason describes closing/reducing a position."""
    if reason_is_hold_label(reason):
        return False
    return (
        reason_is_tp1_exit(reason)
        or reason_is_trailed_stop(reason)
        or reason_is_stop_exit(reason)
        or reason_is_rsi_exit(reason)
    )


def reason_is_entry_long(reason: str) -> bool:
    reason = reason or ''
    return 'Golden Cross' in reason or (
        'RSI Oversold' in reason and 'Long' in reason
    )


def reason_is_entry_short(reason: str) -> bool:
    reason = reason or ''
    return 'Death Cross' in reason or (
        'RSI Overbought' in reason and 'Short' in reason
    )


def tp1_already_done(position_data: dict) -> bool:
    if not position_data:
        return False
    if position_data.get('tp1_hit'):
        return True
    initial = float(position_data.get('initial_qty') or position_data.get('qty') or 0)
    current = float(position_data.get('qty') or 0)
    return initial > 0 and current < initial * TP1_MAX_REMAINING_FRACTION
