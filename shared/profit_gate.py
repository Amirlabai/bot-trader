"""Per-symbol live profit gate for the hold bot.

Looks at completed legs of a symbol across the given wallets (hold wallet plus the live
book it follows) and lets a new entry through only while the recent legs are net profitable.
The rule itself is shared with the offline sim (shared.path_sim.gate_allows).
"""

from __future__ import annotations

from shared.path_sim import gate_allows
from shared.trade_legs import completed_leg_records

DEFAULT_GATE = {'gate_window': 5, 'gate_min_trades': 3, 'gate_min_pf': 1.0}


def gate_tuple(params: dict) -> tuple[int, int, float]:
    return (
        int(params.get('gate_window', DEFAULT_GATE['gate_window'])),
        int(params.get('gate_min_trades', DEFAULT_GATE['gate_min_trades'])),
        float(params.get('gate_min_pf', DEFAULT_GATE['gate_min_pf'])),
    )


def symbol_leg_pnls(ledger_data: dict, strategy_ids: list[str], symbol: str) -> list[float]:
    """Completed-leg P/L for a symbol across wallets, oldest first."""
    strategies = ledger_data.get('strategies') or {}
    records = []
    for sid in strategy_ids:
        history = (strategies.get(sid) or {}).get('history') or []
        records.extend(r for r in completed_leg_records(history) if r['symbol'] == symbol and r['side'] == 'LONG')
    records.sort(key=lambda r: r['time'])
    return [float(r['pnl']) for r in records]


def symbol_gate_ok(ledger_data: dict, strategy_ids: list[str], symbol: str, params: dict) -> tuple[bool, str]:
    pnls = symbol_leg_pnls(ledger_data, strategy_ids, symbol)
    gate = gate_tuple(params)
    ok = gate_allows(pnls, gate)
    legs = pnls[-gate[0]:]
    if len(legs) < gate[1]:
        why = f'probation ({len(legs)}/{gate[1]} legs)'
    else:
        why = f'last {len(legs)} legs net {sum(legs):+.2f}'
    return ok, why
