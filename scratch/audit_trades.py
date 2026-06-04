"""
Audit closed-trade legs per strategy: TP1 should happen at most once per open leg.
Writes docs/trade_audit.json and docs/trade_audit.md
"""
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
os.chdir(REPO_ROOT)
for path in (REPO_ROOT, os.path.join(REPO_ROOT, 'src')):
    if path not in sys.path:
        sys.path.insert(0, path)

from config import Config
from shared.constants import reason_is_tp1_exit, tp1_already_done


def _replay_legs(history, attach_close_events=False):
    """Yield completed legs and one open leg per symbol from chronological history."""
    by_symbol = defaultdict(list)
    for event in sorted(history, key=lambda e: e['timestamp']):
        if isinstance(event, dict):
            by_symbol[event['symbol']].append(event)

    for symbol, events in by_symbol.items():
        leg = None
        for event in events:
            side = event.get('side', '')
            if side.startswith('OPEN_'):
                pos_side = 'LONG' if 'LONG' in side else 'SHORT'
                leg = {
                    'symbol': symbol,
                    'side': pos_side,
                    'open_ts': event['timestamp'],
                    'initial_qty': float(event['quantity']),
                    'entry_price': float(event['price']),
                    'closes': [],
                    'open_qty': float(event['quantity']),
                }
                if attach_close_events:
                    leg['close_events'] = []
            elif leg and side.startswith('ADD_'):
                leg['open_qty'] += float(event['quantity'])
                leg['initial_qty'] = leg['open_qty']
            elif leg and 'CLOSE' in side and 'pnl' in event:
                qty = float(event['quantity'])
                initial = leg['initial_qty']
                leg['closes'].append({
                    'ts': event['timestamp'],
                    'qty': qty,
                    'price': float(event['price']),
                    'pnl': float(event.get('pnl', 0)),
                    'reason': event.get('reason', ''),
                    'exit_kind': event.get('exit_kind', ''),
                    'pct_of_initial': round(qty / initial, 4) if initial > 0 else 0,
                    'pct_of_remaining': None,
                })
                if attach_close_events:
                    leg['close_events'].append(event)
                leg['open_qty'] -= qty
                if leg['open_qty'] <= 1e-9:
                    closes = leg['closes']
                    for i, c in enumerate(closes):
                        rem_before = leg['initial_qty'] - sum(x['qty'] for x in closes[:i])
                        c['pct_of_remaining'] = round(c['qty'] / rem_before, 4) if rem_before > 0 else 0
                    yield leg
                    leg = None
        if leg and leg['open_qty'] > 1e-9:
            leg['still_open_qty'] = leg['open_qty']
            yield leg


def _analyze_leg(leg):
    closes = leg['closes']
    tp1_closes = [c for c in closes if reason_is_tp1_exit(c['reason']) or c.get('exit_kind') == 'tp1_partial']
    half_remaining = [
        c for c in closes
        if c.get('pct_of_remaining') is not None and 0.45 <= c['pct_of_remaining'] <= 0.55
    ]
    issues = []
    if len(tp1_closes) > 1:
        issues.append(f'multiple_tp1 ({len(tp1_closes)} partial TP1 closes)')
    if len(closes) > 2 and len(half_remaining) > 1:
        issues.append(f'repeated_half_exits ({len(half_remaining)} closes ~50% of remainder)')
    if len(closes) > 3:
        issues.append(f'many_closes ({len(closes)} ledger rows for one leg)')
    still_open = leg.get('still_open_qty', leg.get('open_qty', 0))
    if still_open > 1e-9:
        rem_pct = still_open / leg['initial_qty'] if leg['initial_qty'] else 0
        if rem_pct < 0.05 and len(closes) >= 5:
            issues.append(f'dust_remainder ({still_open:.6f} left after {len(closes)} closes)')
    open_dt = datetime.fromisoformat(leg['open_ts'][:19])
    last_dt = datetime.fromisoformat(closes[-1]['ts'][:19]) if closes else open_dt
    hold_days = (last_dt - open_dt).days
    expected = 'ok'
    if len(closes) == 1:
        expected = 'single_exit'
    elif len(closes) == 2 and len(tp1_closes) == 1:
        expected = 'tp1_then_final'
    elif issues:
        expected = 'violation'
    return {
        'symbol': leg['symbol'],
        'side': leg['side'],
        'open_ts': leg['open_ts'],
        'entry_price': leg['entry_price'],
        'initial_qty': leg['initial_qty'],
        'close_count': len(closes),
        'tp1_count': len(tp1_closes),
        'hold_days': hold_days,
        'expected_pattern': expected,
        'issues': issues,
        'closes': closes,
        'still_open_qty': still_open,
    }


def _open_legs_by_symbol(history):
    """Map symbol -> open leg from one replay pass."""
    open_legs = {}
    for leg in _replay_legs(history):
        if leg.get('still_open_qty', 0) > 1e-9:
            open_legs[leg['symbol']] = leg
    return open_legs


def repair_open_positions(ledger):
    """Sync tp1_hit / initial_qty on live positions from history replay."""
    repaired = 0
    for strategy_id, strat in ledger.get('strategies', {}).items():
        history = strat.get('history', [])
        positions = strat.get('positions', {})
        open_by_symbol = _open_legs_by_symbol(history)
        for symbol, pos in list(positions.items()):
            if not isinstance(pos, dict):
                continue
            open_leg = open_by_symbol.get(symbol)
            if not open_leg or open_leg['side'] != pos.get('side', 'LONG'):
                continue
            changed = False
            if not pos.get('initial_qty'):
                pos['initial_qty'] = open_leg['initial_qty']
                changed = True
            if any(reason_is_tp1_exit(c['reason']) for c in open_leg['closes']) and not pos.get('tp1_hit'):
                pos['tp1_hit'] = True
                changed = True
            if tp1_already_done(pos) and not pos.get('tp1_hit'):
                pos['tp1_hit'] = True
                changed = True
            if changed:
                positions[symbol] = pos
                repaired += 1
    return repaired


def run_audit(write_files=True, ledger=None):
    if ledger is None:
        with open(Config.LEDGER_FILE, 'r', encoding='utf-8') as f:
            ledger = json.load(f)

    summary = {
        'generated_at': datetime.now().isoformat(),
        'strategies': {},
        'totals': {
            'legs': 0,
            'ok': 0,
            'tp1_then_final': 0,
            'single_exit': 0,
            'violations': 0,
            'still_open_legs': 0,
        },
    }

    for strategy_id, strat in ledger.get('strategies', {}).items():
        legs = [_analyze_leg(leg) for leg in _replay_legs(strat.get('history', []))]
        violations = [l for l in legs if l['issues']]
        open_legs = [l for l in legs if l['still_open_qty'] > 1e-9]
        summary['strategies'][strategy_id] = {
            'total_legs': len(legs),
            'violations': violations,
            'open_legs': open_legs,
            'violation_count': len(violations),
        }
        for leg in legs:
            summary['totals']['legs'] += 1
            if leg['expected_pattern'] == 'ok':
                summary['totals']['ok'] += 1
            elif leg['expected_pattern'] == 'tp1_then_final':
                summary['totals']['tp1_then_final'] += 1
            elif leg['expected_pattern'] == 'single_exit':
                summary['totals']['single_exit'] += 1
            elif leg['expected_pattern'] == 'violation':
                summary['totals']['violations'] += 1
        summary['totals']['still_open_legs'] += len(open_legs)

    if write_files:
        os.makedirs(os.path.join(REPO_ROOT, 'docs'), exist_ok=True)
        json_path = os.path.join(REPO_ROOT, 'docs', 'trade_audit.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)

        md_path = os.path.join(REPO_ROOT, 'docs', 'trade_audit.md')
        lines = [
            '# Trade leg audit',
            '',
            f'Generated: {summary["generated_at"]}',
            '',
            'Expected: at most one TP1 partial (50% of initial), then one final close for the remainder.',
            '',
            '## Totals',
            '',
            f'- Legs analyzed: {summary["totals"]["legs"]}',
            f'- TP1 then final (2 closes): {summary["totals"]["tp1_then_final"]}',
            f'- Single full exit: {summary["totals"]["single_exit"]}',
            f'- Clean (other): {summary["totals"]["ok"]}',
            f'- Violations: {summary["totals"]["violations"]}',
            f'- Still open legs: {summary["totals"]["still_open_legs"]}',
            '',
        ]
        for sid, data in summary['strategies'].items():
            lines.append(f'## {sid}')
            lines.append('')
            lines.append(f'Violation count: {data["violation_count"]}')
            for v in data['violations'][:30]:
                lines.append(
                    f'- {v["symbol"]} {v["side"]} opened {v["open_ts"][:10]}: '
                    f'{v["close_count"]} closes, TP1={v["tp1_count"]}, '
                    f'hold {v["hold_days"]}d — {", ".join(v["issues"])}'
                )
            if len(data['violations']) > 30:
                lines.append(f'- ... and {len(data["violations"]) - 30} more')
            if data['open_legs']:
                lines.append('')
                lines.append('Still open:')
                for o in data['open_legs']:
                    lines.append(
                        f'- {o["symbol"]} {o["side"]}: {o["still_open_qty"]:.6f} remaining '
                        f'of {o["initial_qty"]:.6f} ({len(o["closes"])} prior closes)'
                    )
            lines.append('')
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        print(f'Wrote {json_path} and {md_path}')

    return summary


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--repair-positions', action='store_true', help='Set tp1_hit/initial_qty on open positions from history')
    parser.add_argument('--fix-history', action='store_true', help='Consolidate violating legs (TP1+final) and save ledger')
    parser.add_argument('--dry-run', action='store_true', help='With --fix-history, do not save ledger')
    parser.add_argument('--save-ledger', action='store_true', help='Save ledger after repair')
    args = parser.parse_args()

    if args.fix_history:
        from repair_ledger_legs import repair_violating_legs
        from ledger_manager import LedgerManager
        lm = LedgerManager(Config)
        before = run_audit(write_files=False, ledger=lm.ledger)
        print(f'Before: {before["totals"]["violations"]} violations')
        stats = repair_violating_legs(lm.ledger, Config.INITIAL_STRATEGY_CASH)
        after = run_audit(write_files=False, ledger=lm.ledger)
        print(
            f'After: {after["totals"]["violations"]} violations; '
            f'fixed {stats["legs_fixed"]} leg(s)'
        )
        if not args.dry_run:
            import shutil
            shutil.copy2(Config.LEDGER_FILE, Config.LEDGER_FILE + '.bak')
            lm.save_ledger()
            print('Ledger saved')
            print('Next: .\\.venv\\Scripts\\python.exe scratch\\update_snapshots.py')
        summary = run_audit(write_files=not args.dry_run, ledger=lm.ledger if args.dry_run else None)
        print(
            f'Audit: {summary["totals"]["legs"]} legs, '
            f'{summary["totals"]["violations"]} violations'
        )
        raise SystemExit(0)

    if args.repair_positions:
        from ledger_manager import LedgerManager
        lm = LedgerManager(Config)
        n = repair_open_positions(lm.ledger)
        print(f'Repaired {n} open position(s)')
        if args.save_ledger:
            lm.save_ledger()
            print('Ledger saved')

    summary = run_audit(write_files=True)
    print(
        f'Audit: {summary["totals"]["legs"]} legs, '
        f'{summary["totals"]["violations"]} violations, '
        f'{summary["totals"]["tp1_then_final"]} tp1+final'
    )
