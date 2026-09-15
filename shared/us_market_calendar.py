"""US equity regular session helpers (NYSE/Nasdaq)."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')

# Major NYSE full-day closures (extend annually as needed).
NYSE_HOLIDAYS = frozenset({
    # 2025
    date(2025, 1, 1),
    date(2025, 1, 20),
    date(2025, 2, 17),
    date(2025, 4, 18),
    date(2025, 5, 26),
    date(2025, 6, 19),
    date(2025, 7, 4),
    date(2025, 9, 1),
    date(2025, 11, 27),
    date(2025, 12, 25),
    # 2026
    date(2026, 1, 1),
    date(2026, 1, 19),
    date(2026, 2, 16),
    date(2026, 4, 3),
    date(2026, 5, 25),
    date(2026, 6, 19),
    date(2026, 7, 3),  # Independence Day observed
    date(2026, 9, 7),
    date(2026, 11, 26),
    date(2026, 12, 25),
    # 2027
    date(2027, 1, 1),
    date(2027, 1, 18),
    date(2027, 2, 15),
    date(2027, 3, 26),
    date(2027, 5, 31),
    date(2027, 6, 18),
    date(2027, 7, 5),  # Independence Day observed
    date(2027, 9, 6),
    date(2027, 11, 25),
    date(2027, 12, 24),  # Christmas observed (Fri)
})


def now_et() -> datetime:
    return datetime.now(ET)


def is_us_equity_trading_day(d: date | None = None) -> bool:
    """True on Mon–Fri that are not listed NYSE full-day holidays."""
    day = d or now_et().date()
    if day.weekday() >= 5:
        return False
    return day not in NYSE_HOLIDAYS


def regular_open_et_label() -> str:
    return '09:30 America/New_York'
