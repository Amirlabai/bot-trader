"""Shared constants used by src and strategies (no sys.path hacks)."""

TP1_HIT_REASON_LONG = 'TP1 Hit'
TP1_HIT_REASON_SHORT = 'Short TP1 Hit'
TP1_EXIT_REASONS = frozenset({TP1_HIT_REASON_LONG, TP1_HIT_REASON_SHORT})
