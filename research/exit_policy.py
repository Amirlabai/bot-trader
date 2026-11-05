"""Exit logic for a long position: initial stop, ATR trail, optional TP1 and scale-out ladder.

Copied from asset-trail strategies/exit_policy.py and adapted to bot-trader's
daily long asset-trail wallet (strategies/base_strategy.check_risk_management):

- the trail distance is trail_atr x ATR frozen at entry (atr_mode='frozen');
  asset-trail's rule (current ATR, widened to the initial stop) is atr_mode='current';
- the trail moves only while close >= entry + trail_arm_r x R (checked each bar);
- stops trigger on the low and fill at the stop level.

Research only: live bot-trader keeps its own exit code. tests/test_research_parity.py
checks that the default policy matches the live wallet bar for bar.

Ladder: levels sit at first_r, first_r + step_r, first_r + 2*step_r, ... in R,
where R = entry - initial stop. At level k (0-based) the position sells
min(fraction + k * fraction_step, fraction_max) of the quantity still held.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

STOP_LABEL = 'Stop Loss Hit'
TRAILED_LABEL = 'Trailed Stop Hit'
LADDER_LABEL = 'Scale-out'
EARLY_LABEL = 'Early exit'
TP1_LABEL = 'TP1'
_QTY_EPS = 1e-9


def _isnan(value) -> bool:
    try:
        return math.isnan(value)
    except TypeError:
        return False


def trail_proposal(close, current_atr, position_data, *, sl_atr=1.5, trail_atr=3.0):
    """asset-trail rule: distance max(trail_atr x ATR, (trail_atr / sl_atr) x initial risk)."""
    if not position_data or position_data.get('side', 'LONG') != 'LONG':
        return None
    try:
        close_f = float(close)
        atr = float(current_atr)
        entry_price = float(position_data['entry_price'])
    except (TypeError, ValueError, KeyError):
        return None
    if _isnan(atr) or _isnan(close_f):
        return None
    sl_atr = float(sl_atr)
    trail_atr = float(trail_atr)
    stop_loss = position_data.get('stop_loss')
    if stop_loss is None:
        stop_loss = entry_price - (sl_atr * atr)
    try:
        stop_loss = float(stop_loss)
    except (TypeError, ValueError):
        return None
    trail_dist = trail_atr * atr
    anchor_sl = position_data.get('initial_stop_loss')
    if anchor_sl is None and stop_loss < entry_price:
        anchor_sl = stop_loss
    if anchor_sl is not None and sl_atr > 0:
        try:
            init_dist = entry_price - float(anchor_sl)
        except (TypeError, ValueError):
            init_dist = 0.0
        if init_dist > 0:
            trail_dist = max(trail_dist, (trail_atr / sl_atr) * init_dist)
    return {
        'stop_loss': stop_loss,
        'trail_distance': float(trail_dist),
        'proposed_stop': close_f - float(trail_dist),
    }


def reference_atr(pos: dict, current_atr: float, sl_atr: float) -> float:
    """Live BaseStrategy._trail_reference_atr: entry ATR, else derived from the initial stop."""
    stored = pos.get('entry_atr')
    if stored is not None and not _isnan(stored) and float(stored) > 0:
        return float(stored)
    risk = pos['entry_price'] - pos['initial_stop_loss']
    if sl_atr > 0 and risk > 0:
        return risk / float(sl_atr)
    return float(current_atr)


@dataclass(frozen=True)
class ExitPolicy:
    name: str = 'baseline'
    step_r: float | None = None          # None = no ladder (today's trail only)
    first_r: float | None = None         # default: step_r
    fraction: float = 0.0                # share of remaining sold at the first level
    fraction_step: float = 0.0           # added per later level (0 = constant share)
    fraction_max: float = 1.0
    max_steps: int | None = None
    breakeven_after_first: bool = False
    # Early exit: after exactly N bars, sell the rest at the close if the best
    # high so far is below entry + early_exit_min_r * R. None = off.
    early_exit_bars: int | None = None
    early_exit_min_r: float = 0.5
    sl_atr: float = 1.0
    trail_atr: float = 3.0
    # 'frozen' = live bot-trader (trail_atr x entry ATR); 'current' = asset-trail rule.
    atr_mode: str = 'frozen'
    trail_arm_r: float = 0.0
    # Live TP1 wallet: sell 50% at entry + 1 entry ATR, stop to entry, TP1 wins a tie with the stop.
    tp1_live: bool = False
    tp1_fraction: float = 0.5

    @property
    def has_early_exit(self) -> bool:
        return bool(self.early_exit_bars) and self.early_exit_bars > 0

    @property
    def has_ladder(self) -> bool:
        return bool(self.step_r) and self.step_r > 0 and self.fraction > 0

    def level_r(self, k: int) -> float:
        first = self.first_r if self.first_r is not None else self.step_r
        return float(first) + k * float(self.step_r)

    def share(self, k: int) -> float:
        return max(0.0, min(self.fraction + k * self.fraction_step, self.fraction_max, 1.0))

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'ExitPolicy':
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in (data or {}).items() if k in known})


def open_position(entry_price: float, initial_stop: float, entry_atr: float | None = None) -> dict:
    atr = None
    if entry_atr is not None and not _isnan(entry_atr) and float(entry_atr) > 0:
        atr = float(entry_atr)
    return {
        'side': 'LONG',
        'entry_price': float(entry_price),
        'initial_stop_loss': float(initial_stop),
        'stop_loss': float(initial_stop),
        'entry_atr': atr,
        'qty': 1.0,              # remaining share of the original size
        'next_level': 0,
        'bars': 0,               # bars stepped since entry
        'max_high': float(entry_price),
        'fills': [],             # (kind, price, size, reason)
        'ambiguous_bars': 0,
        'tp1_done': False,
        'closed': False,
    }


def _stop_reason(pos: dict) -> str:
    if pos.get('tp1_done'):
        trailed = pos['stop_loss'] > pos['entry_price']
    else:
        trailed = pos['stop_loss'] > pos['initial_stop_loss']
    label = TRAILED_LABEL if trailed else STOP_LABEL
    stop = round(pos['stop_loss'], 4)
    return f'{label} @ {stop} (SL {stop})'


def _trail(pos: dict, close: float, atr: float, policy: ExitPolicy) -> None:
    if policy.trail_atr <= 0:
        return
    if policy.tp1_live and not pos.get('tp1_done'):
        return  # live TP1 wallet trails only after TP1
    if policy.atr_mode == 'current':
        proposal = trail_proposal(close, atr, pos, sl_atr=policy.sl_atr, trail_atr=policy.trail_atr)
        if proposal is not None and proposal['proposed_stop'] > pos['stop_loss']:
            pos['stop_loss'] = proposal['proposed_stop']
        return
    risk = pos['entry_price'] - pos['initial_stop_loss']
    if policy.trail_arm_r > 0 and not pos.get('tp1_done'):
        unrealized = (close - pos['entry_price']) / risk if risk > 0 else 0.0
        if unrealized < policy.trail_arm_r:
            return
    ref = reference_atr(pos, atr, policy.sl_atr)
    if _isnan(ref):
        return
    proposed = close - policy.trail_atr * ref
    if proposed > pos['stop_loss']:
        pos['stop_loss'] = proposed


def step_bar(pos: dict, high: float, low: float, close: float, atr: float, policy: ExitPolicy) -> list:
    """Apply one bar after entry. Mutates pos; returns the fills made on this bar.

    Order inside the bar:
    0. TP1 on the high (tp1_live only; wins a tie with the stop, as live does; the
       remainder is checked from the next bar)
    1. stop on the low (whole remainder at the stop price)
    2. ladder levels on the high (limit fills at each level price)
    3. early exit on the close (bar N only, when the best high is below the threshold)
    4. trail from the close
    5. break-even raise after the first ladder sale (if enabled)
    """
    if pos['closed']:
        return []
    fills = []
    pos['bars'] = pos.get('bars', 0) + 1
    pos['max_high'] = max(pos.get('max_high', pos['entry_price']), high)
    risk = pos['entry_price'] - pos['initial_stop_loss']

    # 0. Live TP1.
    if policy.tp1_live and not pos.get('tp1_done') and risk > 0:
        tp_px = pos['entry_price'] + reference_atr(pos, atr, policy.sl_atr)
        if high >= tp_px:
            size = pos['qty'] * policy.tp1_fraction
            fill = ('tp1', tp_px, size, f'{TP1_LABEL} @ {round(tp_px, 4)}')
            fills.append(fill)
            pos['fills'].append(fill)
            pos['qty'] -= size
            pos['tp1_done'] = True
            pos['stop_loss'] = pos['entry_price']
            return fills

    next_level_px = None
    if policy.has_ladder and risk > 0 and (
        policy.max_steps is None or pos['next_level'] < policy.max_steps
    ):
        next_level_px = pos['entry_price'] + policy.level_r(pos['next_level']) * risk

    # 1. Stop first.
    if low <= pos['stop_loss']:
        if next_level_px is not None and high >= next_level_px:
            pos['ambiguous_bars'] += 1
        fill = ('stop', pos['stop_loss'], pos['qty'], _stop_reason(pos))
        fills.append(fill)
        pos['fills'].append(fill)
        pos['qty'] = 0.0
        pos['closed'] = True
        return fills

    # 2. Ladder.
    if policy.has_ladder and risk > 0:
        while pos['qty'] > _QTY_EPS:
            k = pos['next_level']
            if policy.max_steps is not None and k >= policy.max_steps:
                break
            level_px = pos['entry_price'] + policy.level_r(k) * risk
            if high < level_px:
                break
            size = pos['qty'] * policy.share(k)
            if size > _QTY_EPS:
                fill = ('ladder', level_px, size, f'{LADDER_LABEL} {policy.level_r(k):g}R')
                fills.append(fill)
                pos['fills'].append(fill)
                pos['qty'] -= size
            pos['next_level'] = k + 1
        if pos['qty'] <= _QTY_EPS:
            pos['qty'] = 0.0
            pos['closed'] = True
            return fills

    # 3. Early exit: no progress after N bars.
    if policy.has_early_exit and risk > 0 and pos['bars'] == policy.early_exit_bars:
        if pos['max_high'] < pos['entry_price'] + policy.early_exit_min_r * risk:
            fill = ('early', float(close), pos['qty'],
                    f'{EARLY_LABEL} {policy.early_exit_bars} bars < {policy.early_exit_min_r:g}R')
            fills.append(fill)
            pos['fills'].append(fill)
            pos['qty'] = 0.0
            pos['closed'] = True
            return fills

    # 4. Trail from the close.
    _trail(pos, close, atr, policy)

    # 5. Break-even after the first sale.
    if policy.breakeven_after_first and pos['next_level'] > 0 and pos['stop_loss'] < pos['entry_price']:
        pos['stop_loss'] = pos['entry_price']
    return fills
