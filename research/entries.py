"""Entry modes: when, after an EMA crossover signal, the engine actually buys.

signal            buy at the crossover close (today's live behaviour)
higher_high       wait up to `within` bars for a close above the reference high
resistance_break  wait up to `within` bars for a close above resistance

A pending signal is cancelled when a close falls below the signal's stop (the
setup failed) or the fast EMA falls back under the slow EMA. A new crossover
replaces it. Pending signals are tracked on every bar, also while a position is
open, and only the first trigger counts, so the rule depends on the bars alone
(the live confirm_entry in strategies/moving_average.py does the same).
Confirmed entries buy at the trigger close with a fresh stop of
close - sl_atr x ATR, which is how the live strategy sets its stop.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from research.structure import Structure


@dataclass(frozen=True)
class EntryMode:
    type: str = 'signal'               # signal | higher_high | resistance_break
    within: int = 6                    # bars to wait for the trigger
    ref: str = 'signal_high'           # higher_high: signal_high | swing_high
    level: str = 'pivot'               # resistance_break: pivot | band
    pivot_k: int = 3
    lookback: int = 120
    none_above: str = 'enter'          # pivot level missing (open air): enter | skip
    trigger: str = 'close'             # close: buy at a close above the level
                                       # break: buy-stop resting at the level (fills intrabar)

    @property
    def name(self) -> str:
        if self.type == 'signal':
            return 'signal'
        suffix = '_stop' if self.trigger == 'break' else ''
        if self.type == 'higher_high':
            ref = 'sig' if self.ref == 'signal_high' else f'swing{self.pivot_k}'
            return f'hh_{ref}_w{self.within}{suffix}'
        lvl = f'piv{self.pivot_k}' if self.level == 'pivot' else 'band'
        tail = f'_{self.none_above}' if self.level == 'pivot' else ''
        return f'res_{lvl}_L{self.lookback}_w{self.within}{tail}{suffix}'

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'EntryMode':
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in (data or {}).items() if k in known})


class EntryContext:
    """Per-pair arrays a mode needs. Built once per pair and mode family."""

    def __init__(self, signals: pd.DataFrame, mode: EntryMode, fast_span: int = 10, slow_span: int = 20,
                 history: pd.DataFrame | None = None):
        # fast/slow: the live crossover EMAs (bot-trader crypto 10/20); a reversal cancels a pending signal.
        # history: the full OHLC the signals are the tail of. EMAs and pivots then match live
        # (which sees the whole history) from the first replay bar.
        self.mode = mode
        self.offset = 0
        if history is not None and len(history) >= len(signals) and len(signals):
            off = len(history) - len(signals)
            if pd.Timestamp(history.index[off]) == pd.Timestamp(signals.index[0]):
                self.offset = off
            else:
                history = None
        else:
            history = None
        src = signals if history is None else history
        self.close = signals['close'].to_numpy(dtype=float)
        self.open = (signals['open'].to_numpy(dtype=float) if 'open' in signals.columns
                     else np.r_[np.nan, self.close[:-1]])
        self.high = signals['high'].to_numpy(dtype=float)
        self.atr = signals['atr'].to_numpy(dtype=float)
        closes = src['close'].astype(float)
        fast = closes.ewm(span=int(fast_span), adjust=False).mean().to_numpy()
        slow = closes.ewm(span=int(slow_span), adjust=False).mean().to_numpy()
        self.fast_above = (fast > slow)[self.offset:]
        self.structure = None
        if mode.type != 'signal' and (mode.type == 'resistance_break' or mode.ref == 'swing_high'):
            atr = signals['atr'].to_numpy(dtype=float)
            if self.offset:
                atr = np.r_[np.full(self.offset, np.nan), atr]
            self.structure = Structure(
                src['high'], src['low'], src['close'], atr,
                k=mode.pivot_k, lookback=mode.lookback,
            )

    def level_at_signal(self, s: int) -> float | str:
        """Trigger level for a signal at bar s; 'now' to enter at once; 'skip' to drop it."""
        m = self.mode
        h = s + self.offset  # index into the structure arrays
        if m.type == 'higher_high':
            level = self.high[s]
            if m.ref == 'swing_high':
                swing = self.structure.last_swing_high(h)
                if not math.isnan(swing):
                    level = max(level, swing)
            return level
        if m.level == 'band':
            level = self.structure.band_high(h)
            if math.isnan(level) or self.close[s] > level:
                return 'now'
            return level
        level = self.structure.resistance(h)
        if math.isnan(level):
            return 'now' if m.none_above == 'enter' else 'skip'
        return level


def start_pending(ctx: EntryContext, s: int, signal_stop: float):
    """Return ('now', None), ('skip', None), or ('wait', pending dict)."""
    if ctx.mode.type == 'signal':
        return 'now', None
    level = ctx.level_at_signal(s)
    if level == 'now':
        return 'now', None
    if level == 'skip':
        return 'skip', None
    return 'wait', {'s': s, 'level': float(level), 'stop': float(signal_stop)}


def check_pending(ctx: EntryContext, pending: dict, i: int) -> str:
    """At bar i (> signal bar): 'fill' (buy-stop hit), 'enter' (close above), 'cancel', or 'wait'.

    A buy-stop rests from the close that set it, so it can fill during bar i
    before that bar's close is known; cancel rules are checked at the close.
    """
    if i - pending['s'] > ctx.mode.within:
        return 'cancel'
    if ctx.mode.trigger == 'break' and ctx.high[i] >= pending['level']:
        return 'fill'
    if ctx.close[i] < pending['stop'] or not ctx.fast_above[i]:
        return 'cancel'
    if ctx.mode.trigger == 'close' and ctx.close[i] > pending['level']:
        return 'enter'
    return 'wait'


def fill_price(ctx: EntryContext, pending: dict, i: int) -> float:
    """Buy-stop fill: the level, or the bar's open when it gaps above it."""
    opened = ctx.open[i]
    if np.isnan(opened):
        opened = ctx.close[i - 1]
    return float(max(pending['level'], opened))


def fresh_stop(ctx: EntryContext, i: int, sl_atr: float) -> float:
    atr = ctx.atr[i]
    if atr is None or np.isnan(atr) or atr <= 0:
        return math.nan
    return float(ctx.close[i] - sl_atr * atr)
