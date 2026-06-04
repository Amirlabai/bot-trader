import sys
import os
from datetime import datetime
import copy

# Always run from repo root (IDE may use scratch/ as cwd)
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
os.chdir(REPO_ROOT)
for path in (REPO_ROOT, os.path.join(REPO_ROOT, 'src'), os.path.join(REPO_ROOT, 'scratch')):
    if path not in sys.path:
        sys.path.insert(0, path)

from config import Config, TRADING_CONFIG
from ledger_manager import LedgerManager
from data_ingestion import DataFetcher
from shared.constants import reason_is_tp1_exit
from shared.exit_snapshots import (
    build_close_snapshot,
    reason_with_fill,
    resolve_close_fill_price,
    bar_close_price,
    is_stop_or_trail_reason,
    apply_close_fill_to_event,
)
from reporting import _entry_date_for_trade
import importlib
import pandas as pd


def load_strategy(module_name, class_name, params):
    try:
        module = importlib.import_module(module_name)
        strategy_class = getattr(module, class_name)
        return strategy_class(params)
    except Exception as e:
        print(f"Failed to load strategy {class_name} from {module_name}: {e}")
        return None


def _asset_type(symbol):
    is_forex = (
        any(cur in symbol for cur in ['EUR', 'USD', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF'])
        and '/' in symbol
        and len(symbol) == 7
    )
    return 'forex' if is_forex else 'crypto'


def _initial_sl_tp(strategy, market_slice, mock_pos):
    """Bootstrap SL/TP from standard 1.5 ATR / 1.0 ATR rules when not on position."""
    if market_slice is None or market_slice.empty:
        return 0.0, 0.0
    idx = strategy._get_closed_candle_index(market_slice)
    if idx < -len(market_slice) or idx >= len(market_slice):
        return 0.0, 0.0
    atr_series = strategy._calculate_atr(market_slice)
    atr_val = atr_series.iloc[idx]
    atr = float(atr_val) if pd.notnull(atr_val) else 0.0
    if atr <= 0:
        return 0.0, 0.0
    entry = float(mock_pos['entry_price'])
    side = mock_pos.get('side', 'LONG')
    if side == 'LONG':
        return entry - (1.5 * atr), entry + (1.0 * atr)
    return entry + (1.5 * atr), entry - (1.0 * atr)


def _ensure_pos_levels(strategy, market_slice, mock_pos):
    """Fill missing stop_loss / take_profit on mock position (ledger opens often omit them)."""
    sl = float(mock_pos.get('stop_loss') or 0)
    tp = float(mock_pos.get('take_profit') or 0)
    if sl > 0 and tp > 0:
        return
    new_sl, new_tp = _initial_sl_tp(strategy, market_slice, mock_pos)
    if sl <= 0 and new_sl > 0:
        mock_pos['stop_loss'] = new_sl
    if tp <= 0 and new_tp > 0:
        mock_pos['take_profit'] = new_tp


def _position_before_close(history, close_event):
    """Replay OPEN/CLOSE/ADD for symbol; return position dict immediately before this close."""
    symbol = close_event['symbol']
    close_side = close_event['side']
    pos_side = 'LONG' if 'LONG' in close_side else 'SHORT'
    open_side = f'OPEN_{pos_side}'
    add_side = f'ADD_{pos_side}'
    close_prefix = f'CLOSE_{pos_side}'

    pos = None
    for event in sorted(history, key=lambda e: e['timestamp']):
        if event is close_event:
            return copy.deepcopy(pos) if pos else None
        if event.get('symbol') != symbol:
            continue
        side = event.get('side', '')
        if side == open_side:
            qty = float(event['quantity'])
            pos = {
                'qty': qty,
                'initial_qty': qty,
                'entry_price': float(event['price']),
                'side': pos_side,
                'stop_loss': 0.0,
                'take_profit': 0.0,
                'tp1_hit': False,
                'entry_date': str(event['timestamp'])[:10],
            }
        elif side == add_side and pos:
            pos['qty'] += float(event['quantity'])
            pos['initial_qty'] = pos['qty']
        elif side.startswith(close_prefix) and 'pnl' in event and pos:
            qty_close = float(event['quantity'])
            reason = event.get('reason', '') or ''
            if reason_is_tp1_exit(reason):
                pos['tp1_hit'] = True
                pos['stop_loss'] = pos['entry_price']
            pos['qty'] -= qty_close
            if pos['qty'] <= 1e-12:
                pos = None
    return None


def _simulate_trailing(strategy, market_data, mock_pos, entry_date, exit_ts):
    """Replay daily hold signals to reconstruct trailed stop_loss up to exit."""
    if not mock_pos or not entry_date:
        return
    entry_dt = pd.to_datetime(entry_date).tz_localize(None)
    exit_dt = pd.to_datetime(exit_ts).tz_localize(None)
    days = market_data.index[
        (market_data.index >= entry_dt) & (market_data.index < exit_dt)
    ]
    for day in days:
        day_end = pd.to_datetime(day).tz_localize(None) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        slice_md = market_data[market_data.index <= day_end]
        if slice_md.empty:
            continue
        sig = strategy.generate_signal(slice_md, mock_pos)
        if sig.get('action') == 'hold':
            new_sl = sig.get('stop_loss')
            if new_sl is not None and float(new_sl) > 0:
                mock_pos['stop_loss'] = float(new_sl)


def _backfill_close_event(strategy, data_fetcher, history, event, strat_cash_holder):
    symbol = event['symbol']
    asset_type = _asset_type(symbol)
    market_data = data_fetcher.get_data(symbol, asset_type=asset_type)
    if market_data.empty:
        return False

    event_ts = pd.to_datetime(event['timestamp']).tz_localize(None)
    market_data_to_event = market_data[market_data.index <= event_ts]
    if market_data_to_event.empty:
        market_data_to_event = market_data

    pos_side = 'LONG' if 'LONG' in event['side'] else 'SHORT'
    mock_pos = _position_before_close(history, event)
    if not mock_pos:
        entry_price = float(event.get('entry_price', event['price']))
        entry_date = _entry_date_for_trade(history, event, {}, entry_price)
        mock_pos = {
            'qty': float(event['quantity']),
            'entry_price': entry_price,
            'side': pos_side,
            'stop_loss': 0.0,
            'take_profit': 0.0,
            'tp1_hit': False,
            'entry_date': entry_date,
        }
    else:
        entry_price = mock_pos['entry_price']
        entry_date = mock_pos.get('entry_date') or _entry_date_for_trade(
            history, event, {}, entry_price,
        )
        mock_pos['entry_date'] = entry_date

    open_ts = None
    open_side = f'OPEN_{pos_side}'
    for e in sorted(history, key=lambda x: x['timestamp']):
        if e is event:
            break
        if e.get('symbol') == symbol and e.get('side') == open_side:
            open_ts = pd.to_datetime(e['timestamp']).tz_localize(None)

    if open_ts is not None:
        md_open = market_data[market_data.index <= open_ts]
        _ensure_pos_levels(strategy, md_open, mock_pos)

    _ensure_pos_levels(strategy, market_data_to_event, mock_pos)

    _simulate_trailing(strategy, market_data, mock_pos, mock_pos.get('entry_date'), event_ts)

    _ensure_pos_levels(strategy, market_data_to_event, mock_pos)

    signal_data = strategy.generate_signal(market_data_to_event, mock_pos)
    bar_close = bar_close_price(market_data_to_event)
    fallback_reason = event.get('reason', '') if is_stop_or_trail_reason(event.get('reason', '')) else None
    fill_price = resolve_close_fill_price(
        pos_side, bar_close, signal_data, mock_pos, fallback_reason=fallback_reason,
    )
    entry_for_pnl = float(event.get('entry_price', mock_pos['entry_price']))
    cash_delta = apply_close_fill_to_event(event, pos_side, fill_price, entry_for_pnl)
    if strat_cash_holder is not None and abs(cash_delta) > 1e-12:
        strat_cash_holder[0] += cash_delta

    from shared.exit_snapshots import resolve_close_reason
    close_reason = resolve_close_reason(
        signal_data, fill_price, ledger_reason=event.get('reason') or fallback_reason,
    )
    if close_reason:
        event['reason'] = close_reason

    snapshot = build_close_snapshot(
        market_data_to_event, signal_data, mock_pos, fill_price, close_reason=close_reason,
    )
    event['snapshot'] = snapshot
    for key in ('exit_kind', 'stop_loss_at_exit', 'take_profit_at_exit', 'quantity_pct'):
        if key in snapshot:
            event[key] = snapshot[key]
    return True


def _repair_open_positions_from_history(ledger):
    """Sync tp1_hit / initial_qty on open positions so live runs cannot repeat TP1."""
    from audit_trades import repair_open_positions
    return repair_open_positions(ledger)


def main(dry_run=False):
    print(f"--- Close Snapshot Backfill: {datetime.now()} ---")
    if dry_run:
        print("DRY RUN: ledger will not be saved")

    ledger = LedgerManager(Config)
    if not dry_run:
        import shutil
        backup_path = ledger.ledger_file + '.bak'
        shutil.copy2(ledger.ledger_file, backup_path)
        print(f"Ledger backup: {backup_path}")
    repaired = _repair_open_positions_from_history(ledger.ledger)
    if repaired:
        print(f"Repaired tp1_hit/initial_qty on {repaired} open position(s)")

    data_fetcher = DataFetcher(Config)

    for strategy_id, config in TRADING_CONFIG.items():
        print(f"\nStrategy: {strategy_id}")
        strategy = load_strategy(config['strategy_module'], config['strategy_class'], config['params'])
        if not strategy:
            continue

        strat_data = ledger.ledger['strategies'].get(strategy_id, {})
        history = strat_data.get('history', [])
        cash_holder = [float(strat_data.get('cash', 0.0))]

        stripped = 0
        for event in history:
            if not isinstance(event, dict):
                continue
            if 'OPEN' in event.get('side', '') and 'snapshot' in event:
                del event['snapshot']
                stripped += 1
        if stripped:
            print(f"  Removed {stripped} OPEN history snapshots")

        closes = 0
        close_events = sorted(
            (e for e in history if isinstance(e, dict) and 'pnl' in e),
            key=lambda e: e['timestamp'],
        )
        for event in close_events:
            symbol = event['symbol']
            print(f"  > Close snapshot for {symbol} ({event['side']}) @ {event['price']}")

            if not _backfill_close_event(strategy, data_fetcher, history, event, cash_holder):
                print("    Skip: no market data")
                continue

            closes += 1
            snap = event.get('snapshot') or {}
            last_date = snap['candles'][-1]['date'] if snap.get('candles') else '?'
            kind = snap.get('exit_kind', '?')
            sl = snap.get('stop_loss_at_exit', snap.get('stop_loss'))
            print(f"    OK — {kind}, SL {sl}, window ends {last_date}")

        strat_data['cash'] = cash_holder[0]
        print(f"  Backfilled {closes} close snapshots (strategy cash {cash_holder[0]:.2f})")

    if dry_run:
        print("\n--- Dry run complete (ledger unchanged on disk) ---")
    else:
        ledger.save_ledger()
        print("\n--- Ledger saved ---")

    if not dry_run:
        from audit_trades import run_audit
        summary = run_audit(write_files=True)
        print(
            f"Trade audit: {summary['totals']['violations']} violation leg(s) "
            f"of {summary['totals']['legs']} (see docs/trade_audit.md)"
        )
        _regenerate_report()


def _regenerate_report():
    """Rebuild docs/report_data.js so trade charts use current reporting.py renderer."""
    from reporting import ReportGenerator
    reporter = ReportGenerator(Config)
    reporter.generate()
    print(f"Report written: {reporter.report_file}")
    print("Hard-refresh the dashboard (Ctrl+F5) so the browser loads the new report_data.js.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Backfill CLOSE snapshots and/or regenerate dashboard report.")
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Skip API/snapshot refresh; only regenerate docs/report_data.js from ledger.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Backfill in memory only; do not save ledger or write audit/report artifacts",
    )
    args = parser.parse_args()
    if args.report_only:
        print(f"--- Report Regeneration: {datetime.now()} ---")
        _regenerate_report()
    else:
        main(dry_run=args.dry_run)
