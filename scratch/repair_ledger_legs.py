"""
Consolidate violating trade legs in ledger history to TP1 + final (or TP1 + open).

Rewrites duplicate partial CLOSE rows, replays cash/positions, then refreshes audit.
After save, run scratch/update_snapshots.py to backfill snapshots and exit_kind.
"""
import argparse
import copy
import json
import os
import shutil
import sys
from datetime import datetime

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
os.chdir(REPO_ROOT)
for path in (REPO_ROOT, os.path.join(REPO_ROOT, 'src')):
    if path not in sys.path:
        sys.path.insert(0, path)

from config import Config
from shared.constants import (
    TP1_HIT_REASON_LONG,
    TP1_HIT_REASON_SHORT,
    TP1_MAX_REMAINING_FRACTION,
    reason_is_stop_exit,
    reason_is_tp1_exit,
    reason_is_trailed_stop,
)
from audit_trades import _analyze_leg, _replay_legs, repair_open_positions, run_audit

DUST_FRACTION = 0.05
QTY_EPS = 1e-6
_STRIP_ON_CONSOLIDATE = (
    'snapshot',
    'exit_kind',
    'stop_loss_at_exit',
    'take_profit_at_exit',
    'quantity_pct',
)


def _fill_price_from_pnl(side, entry, qty, pnl):
    if qty <= 0:
        return entry
    if side == 'LONG':
        return entry + pnl / qty
    return entry - pnl / qty


def _build_consolidated_close(template, side, close_side, entry, qty, pnl, reason, exit_kind=None):
    price = _fill_price_from_pnl(side, entry, qty, pnl)
    event = copy.deepcopy(template)
    for key in _STRIP_ON_CONSOLIDATE:
        event.pop(key, None)
    event['side'] = close_side
    event['quantity'] = qty
    event['price'] = price
    event['entry_price'] = entry
    event['total_value'] = qty * price
    event['pnl'] = pnl
    event['reason'] = reason
    if exit_kind:
        event['exit_kind'] = exit_kind
    return event


def _closes_for_analysis(leg):
    """Build close rows with pct_of_remaining (matches audit replay)."""
    initial = leg['initial_qty']
    closes = []
    for e in leg['close_events']:
        closes.append({
            'ts': e['timestamp'],
            'qty': float(e['quantity']),
            'price': float(e['price']),
            'pnl': float(e.get('pnl', 0)),
            'reason': e.get('reason', ''),
            'exit_kind': e.get('exit_kind', ''),
            'pct_of_remaining': None,
        })
    for i, c in enumerate(closes):
        rem_before = initial - sum(x['qty'] for x in closes[:i])
        c['pct_of_remaining'] = round(c['qty'] / rem_before, 4) if rem_before > 0 else 0
    return closes


def _is_tp1_event(event):
    return reason_is_tp1_exit(event.get('reason', '')) or event.get('exit_kind') == 'tp1_partial'


def _bucket_pnls(events, tp1_qty, total_qty, total_pnl):
    """Sum ledger pnl per TP1 vs final bucket; ratio split only when a bucket is empty."""
    tp1_events = [e for e in events if _is_tp1_event(e)]
    final_events = [e for e in events if not _is_tp1_event(e)]

    if tp1_events:
        tp1_pnl = sum(float(e.get('pnl', 0)) for e in tp1_events)
    elif total_qty > QTY_EPS:
        tp1_pnl = total_pnl * (tp1_qty / total_qty)
    else:
        tp1_pnl = 0.0

    if final_events:
        final_pnl = sum(float(e.get('pnl', 0)) for e in final_events)
    else:
        final_pnl = total_pnl - tp1_pnl

    return tp1_pnl, final_pnl


def _resolve_exit_kind(reason, template, qty, initial_qty):
    """Classify consolidated close; omit exit_kind when not a true partial TP1."""
    if reason_is_tp1_exit(reason) and qty < initial_qty * TP1_MAX_REMAINING_FRACTION:
        return 'tp1_partial'
    if reason_is_trailed_stop(reason):
        return 'trailed_stop'
    if template and template.get('exit_kind') == 'trailed_stop':
        return 'trailed_stop'
    if reason_is_stop_exit(reason):
        return 'stop_loss'
    kind = (template or {}).get('exit_kind')
    if kind and kind != 'tp1_partial':
        return kind
    return None


def _consolidate_leg_closes(leg):
    """Return replacement close events (1-2) or None if no change needed."""
    events = leg['close_events']
    if not events:
        return None

    still_open = float(leg.get('still_open_qty', 0))
    analysis = _analyze_leg({
        'symbol': leg['symbol'],
        'side': leg['side'],
        'open_ts': leg['open_ts'],
        'entry_price': leg['entry_price'],
        'initial_qty': leg['initial_qty'],
        'closes': _closes_for_analysis(leg),
        'still_open_qty': still_open,
    })
    if not analysis['issues']:
        return None

    side = leg['side']
    close_side = f'CLOSE_{side}'
    entry = leg['entry_price']
    initial = leg['initial_qty']
    still_open = float(leg.get('still_open_qty', 0))
    total_qty = sum(float(e['quantity']) for e in events)
    total_pnl = sum(float(e.get('pnl', 0)) for e in events)

    tp1_template = None
    for e in events:
        if _is_tp1_event(e):
            tp1_template = e
            break
    if not tp1_template:
        tp1_template = events[0]
    final_template = events[-1]

    tp1_reason = TP1_HIT_REASON_LONG if side == 'LONG' else TP1_HIT_REASON_SHORT
    if tp1_template and reason_is_tp1_exit(tp1_template.get('reason', '')):
        tp1_reason = tp1_template.get('reason', tp1_reason).split(' @')[0]

    tp1_qty = float(tp1_template['quantity']) if tp1_template else initial * 0.5
    if tp1_qty > initial * 0.55 or tp1_qty < initial * 0.45:
        tp1_qty = initial * 0.5

    absorb_dust = still_open > 0 and still_open / initial < DUST_FRACTION
    if absorb_dust:
        final_qty = initial - tp1_qty
    else:
        final_qty = total_qty - tp1_qty

    if final_qty < QTY_EPS:
        if len(events) <= 1:
            return None
        collapse_reason = final_template.get('reason', '') or tp1_reason
        collapse_kind = _resolve_exit_kind(collapse_reason, final_template, total_qty, initial)
        return [_build_consolidated_close(
            final_template, side, close_side, entry, total_qty, total_pnl,
            collapse_reason, collapse_kind,
        )]

    tp1_pnl, final_pnl = _bucket_pnls(events, tp1_qty, total_qty, total_pnl)

    final_reason = final_template.get('reason', '') or 'Stop Loss Hit'
    final_kind = _resolve_exit_kind(final_reason, final_template, final_qty, initial)

    replacements = [
        _build_consolidated_close(
            tp1_template, side, close_side, entry, tp1_qty, tp1_pnl,
            tp1_reason, 'tp1_partial',
        ),
    ]
    if final_qty > QTY_EPS:
        replacements.append(
            _build_consolidated_close(
                final_template, side, close_side, entry, final_qty, final_pnl,
                final_reason, final_kind,
            ),
        )
    return replacements


def _replay_strategy_state(strat, initial_cash):
    """Rebuild cash and positions from history (uses recorded pnl on closes)."""
    cash = float(initial_cash)
    positions = {}

    for event in sorted(strat.get('history', []), key=lambda e: e['timestamp']):
        if not isinstance(event, dict):
            continue
        symbol = event['symbol']
        side = event.get('side', '')
        qty = float(event['quantity'])
        price = float(event['price'])

        if side == 'OPEN_LONG':
            cash -= qty * price
            positions[symbol] = {
                'qty': qty,
                'initial_qty': qty,
                'entry_price': price,
                'side': 'LONG',
                'stop_loss': 0.0,
                'take_profit': 0.0,
                'tp1_hit': False,
            }
        elif side == 'OPEN_SHORT':
            cash -= qty * price
            positions[symbol] = {
                'qty': qty,
                'initial_qty': qty,
                'entry_price': price,
                'side': 'SHORT',
                'stop_loss': 0.0,
                'take_profit': 0.0,
                'tp1_hit': False,
            }
        elif side == 'ADD_LONG' and symbol in positions:
            pos = positions[symbol]
            old_qty = pos['qty']
            new_qty = old_qty + qty
            pos['entry_price'] = ((old_qty * pos['entry_price']) + (qty * price)) / new_qty
            pos['qty'] = new_qty
            pos['initial_qty'] = new_qty
            cash -= qty * price
        elif side == 'ADD_SHORT' and symbol in positions:
            pos = positions[symbol]
            old_qty = pos['qty']
            new_qty = old_qty + qty
            pos['entry_price'] = ((old_qty * pos['entry_price']) + (qty * price)) / new_qty
            pos['qty'] = new_qty
            pos['initial_qty'] = new_qty
            cash -= qty * price
        elif side == 'CLOSE_LONG' and symbol in positions:
            pos = positions[symbol]
            entry = pos['entry_price']
            cash += qty * price
            pos['qty'] -= qty
            if reason_is_tp1_exit(event.get('reason', '')):
                pos['tp1_hit'] = True
                pos['stop_loss'] = entry
            if pos['qty'] <= QTY_EPS:
                del positions[symbol]
        elif side == 'CLOSE_SHORT' and symbol in positions:
            pos = positions[symbol]
            entry = pos['entry_price']
            pnl = float(event.get('pnl', (entry - price) * qty))
            cash += qty * entry + pnl
            pos['qty'] -= qty
            if reason_is_tp1_exit(event.get('reason', '')):
                pos['tp1_hit'] = True
                pos['stop_loss'] = entry
            if pos['qty'] <= QTY_EPS:
                del positions[symbol]

    strat['cash'] = cash
    strat['positions'] = positions


def repair_violating_legs(ledger, initial_cash):
    """Consolidate legs with audit issues; replay cash/positions per strategy."""
    stats = {'legs_fixed': 0, 'closes_removed': 0, 'closes_added': 0}

    for strategy_id, strat in ledger.get('strategies', {}).items():
        history = strat.get('history', [])
        remove_ids = set()
        insertions = []

        for leg in _replay_legs(history, attach_close_events=True):
            if 'close_events' not in leg:
                continue
            replacements = _consolidate_leg_closes(leg)
            if not replacements:
                continue
            for ev in leg['close_events']:
                remove_ids.add(id(ev))
            stats['closes_removed'] += len(leg['close_events'])
            stats['closes_added'] += len(replacements)
            stats['legs_fixed'] += 1
            insertions.append((leg['open_ts'], replacements))

        if not remove_ids:
            continue

        new_history = [e for e in history if id(e) not in remove_ids]
        for open_ts, replacements in insertions:
            new_history.extend(replacements)
        new_history.sort(key=lambda e: e['timestamp'])
        strat['history'] = new_history
        _replay_strategy_state(strat, initial_cash)

    repair_open_positions(ledger)
    return stats


def main():
    parser = argparse.ArgumentParser(description='Consolidate violating ledger legs to TP1+final.')
    parser.add_argument('--dry-run', action='store_true', help='Report only; do not write ledger')
    args = parser.parse_args()

    ledger_path = Config.LEDGER_FILE
    with open(ledger_path, 'r', encoding='utf-8') as f:
        ledger = json.load(f)

    before = run_audit(write_files=False)
    print(
        f'Before: {before["totals"]["violations"]} violations / '
        f'{before["totals"]["legs"]} legs'
    )

    stats = repair_violating_legs(ledger, Config.INITIAL_STRATEGY_CASH)
    after = run_audit(write_files=False, ledger=ledger)
    print(
        f'After: {after["totals"]["violations"]} violations / '
        f'{after["totals"]["legs"]} legs'
    )
    print(
        f'Fixed {stats["legs_fixed"]} leg(s); '
        f'removed {stats["closes_removed"]} close row(s), '
        f'added {stats["closes_added"]}'
    )

    if args.dry_run:
        print('Dry run — ledger not saved')
        return

    backup = ledger_path + '.bak'
    shutil.copy2(ledger_path, backup)
    with open(ledger_path, 'w', encoding='utf-8') as f:
        json.dump(ledger, f, indent=4)
    print(f'Saved {ledger_path} (backup {backup})')
    print('Next: .\\.venv\\Scripts\\python.exe scratch\\update_snapshots.py')

    run_audit(write_files=True)


if __name__ == '__main__':
    main()
