"""
Remove Waiting/Neutral hold labels mistakenly stored on OPEN/CLOSE ledger rows.
"""
import json
import os
import shutil
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
os.chdir(REPO_ROOT)
for path in (REPO_ROOT, os.path.join(REPO_ROOT, 'src')):
    if path not in sys.path:
        sys.path.insert(0, path)

from config import Config
from shared.constants import (
    reason_is_hold_label,
    reason_is_rsi_exit,
    reason_is_tp1_exit,
    reason_is_trailed_stop,
    reason_is_trade_exit,
)


def _exit_kind_from_reason(reason: str, qty_pct: float = 1.0) -> str:
    if reason_is_tp1_exit(reason) and qty_pct < 1.0:
        return 'tp1_partial'
    if reason_is_trailed_stop(reason):
        return 'trailed_stop'
    if reason_is_trade_exit(reason):
        return 'stop_loss'
    return 'other'


def scrub_ledger(ledger):
    fixed = 0
    for strat in ledger.get('strategies', {}).values():
        for event in strat.get('history', []):
            snap = event.get('snapshot') or {}
            qty_pct = float(event.get('quantity_pct') or snap.get('quantity_pct') or 1.0)

            for field in ('reason',):
                if reason_is_hold_label(event.get(field, '')):
                    alt = snap.get('reason', '')
                    if reason_is_trade_exit(alt):
                        event[field] = alt
                    else:
                        event.pop(field, None)
                    fixed += 1

            if snap and reason_is_hold_label(snap.get('reason', '')):
                if reason_is_trade_exit(event.get('reason', '')):
                    snap['reason'] = event['reason']
                else:
                    snap.pop('reason', None)
                fixed += 1

            if 'pnl' in event and event.get('reason'):
                kind = _exit_kind_from_reason(event['reason'], qty_pct)
                if event.get('exit_kind') != kind:
                    event['exit_kind'] = kind
                    fixed += 1
                if snap and snap.get('exit_kind') != kind:
                    snap['exit_kind'] = kind
                    fixed += 1
    return fixed


def main():
    path = Config.LEDGER_FILE
    with open(path, 'r', encoding='utf-8') as f:
        ledger = json.load(f)
    n = scrub_ledger(ledger)
    if n == 0:
        print('No Waiting/Neutral hold labels on trade rows.')
        return
    backup = path + '.pre_waiting_fix.bak'
    shutil.copy2(path, backup)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(ledger, f, indent=4)
    print(f'Fixed {n} field(s). Backup: {backup}')


if __name__ == '__main__':
    main()
