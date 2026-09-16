"""Completed-trade legs for metrics (win rate, PF) vs per-close ledger events."""
from collections import defaultdict


def iter_legs(history, *, completed_only=False):
    """
    Yield position legs from chronological ledger history.

    Completed legs have no `still_open_qty`. Open legs set `still_open_qty`.
    Each close in `closes` has ts, qty, price, pnl, reason, exit_kind.
    """
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
            elif leg and side.startswith('ADD_'):
                leg['open_qty'] += float(event['quantity'])
                leg['initial_qty'] = leg['open_qty']
            elif leg and 'CLOSE' in side and 'pnl' in event:
                qty = float(event['quantity'])
                leg['closes'].append({
                    'ts': event['timestamp'],
                    'qty': qty,
                    'price': float(event['price']),
                    'pnl': float(event.get('pnl', 0)),
                    'reason': event.get('reason', ''),
                    'exit_kind': event.get('exit_kind', ''),
                })
                leg['open_qty'] -= qty
                if leg['open_qty'] <= 1e-9:
                    yield leg
                    leg = None
        if leg and leg['open_qty'] > 1e-9:
            leg['still_open_qty'] = leg['open_qty']
            if not completed_only:
                yield leg


def completed_leg_records(history):
    """
    One metric trade per finished leg: pnl = sum of close pnls.
    `time` is the final close timestamp (for rolling windows).
    """
    records = []
    for leg in iter_legs(history, completed_only=True):
        if not leg.get('closes'):
            continue
        pnl = sum(c['pnl'] for c in leg['closes'])
        records.append({
            'symbol': leg['symbol'],
            'side': leg['side'],
            'time': leg['closes'][-1]['ts'],
            'pnl': pnl,
            'entry_price': leg['entry_price'],
            'entry_notional': float(leg['entry_price']) * float(leg['initial_qty']),
            'open_ts': leg['open_ts'],
            'closes': len(leg['closes']),
        })
    records.sort(key=lambda r: r['time'])
    return records


def leg_metric_buckets(history):
    """Win/loss pnl lists and totals from completed legs."""
    records = completed_leg_records(history)
    wins = [r['pnl'] for r in records if r['pnl'] > 0]
    losses = [r['pnl'] for r in records if r['pnl'] <= 0]
    return wins, losses, records
