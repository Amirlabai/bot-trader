import sys
import os
from datetime import datetime

# Always run from repo root (IDE may use scratch/ as cwd)
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
os.chdir(REPO_ROOT)
for path in (REPO_ROOT, os.path.join(REPO_ROOT, 'src')):
    if path not in sys.path:
        sys.path.insert(0, path)

from config import Config, TRADING_CONFIG
from ledger_manager import LedgerManager
from data_ingestion import DataFetcher
import importlib

def load_strategy(module_name, class_name, params):
    try:
        module = importlib.import_module(module_name)
        strategy_class = getattr(module, class_name)
        return strategy_class(params)
    except Exception as e:
        print(f"Failed to load strategy {class_name} from {module_name}: {e}")
        return None

def main():
    print(f"--- Snapshot Refresh Session: {datetime.now()} ---")
    
    # We need to import the snapshot builder from main
    # Since main has a lot of top-level code, we might need to be careful
    # or just copy-paste it here.
    
    import pandas as pd
    
    def _build_candle_snapshot(market_data, signal_data, n=20, entry_price=None, entry_date=None, pos_data=None):
        start_idx = max(0, len(market_data) - n)
        df = market_data.iloc[start_idx:]
        candles = []
        for ts, row in df.iterrows():
            candles.append({
                "date": str(ts)[:10],
                "open": round(float(row["open"]), 8),
                "high": round(float(row["high"]), 8),
                "low": round(float(row["low"]), 8),
                "close": round(float(row["close"]), 8),
            })
        sl = signal_data.get("stop_loss")
        if (sl is None or sl == 0.0) and pos_data:
            sl = pos_data.get("stop_loss", 0.0)
        tp = signal_data.get("take_profit")
        if (tp is None or tp == 0.0) and pos_data:
            tp = pos_data.get("take_profit", 0.0)
        final_entry_price = entry_price if entry_price else (pos_data.get("entry_price") if pos_data else None)
        final_entry_date = str(entry_date)[:10] if entry_date else (pos_data.get("entry_date") if pos_data else None)
        indicators = signal_data.get("indicators", {})
        sliced_indicators = {}
        for key, values in indicators.items():
            if hasattr(values, "iloc"):
                sliced_indicators[key] = [round(float(v), 8) if pd.notnull(v) else None for v in values.iloc[start_idx:]]
            elif isinstance(values, list):
                sliced_indicators[key] = values[start_idx:]
        return {
            "candles": candles,
            "stop_loss": sl,
            "take_profit": tp,
            "indicators": sliced_indicators,
            "reason": signal_data.get("reason", ""),
            "entry_price": final_entry_price,
            "entry_date": final_entry_date
        }

    ledger = LedgerManager(Config)
    data_fetcher = DataFetcher(Config)
    
    for strategy_id, config in TRADING_CONFIG.items():
        print(f"\nRefreshing Strategy: {strategy_id}")
        strategy = load_strategy(config['strategy_module'], config['strategy_class'], config['params'])
        if not strategy: continue
        
        # Access internal strategies dict
        strat_data = ledger.ledger['strategies'].get(strategy_id, {})
        
        # 1. Active Positions
        positions = strat_data.get('positions', {})
        for symbol, pos_data in positions.items():
            if not isinstance(pos_data, dict): continue
            
            print(f"  > Refreshing active position snapshot for {symbol}...")
            is_forex = any(cur in symbol for cur in ['EUR', 'USD', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF']) and '/' in symbol and len(symbol) == 7
            asset_type = 'forex' if is_forex else 'crypto'
            market_data = data_fetcher.get_data(symbol, asset_type=asset_type)
            if market_data.empty: continue
            
            signal_data = strategy.generate_signal(market_data, pos_data)
            new_snapshot = _build_candle_snapshot(market_data, signal_data, pos_data=pos_data)
            pos_data['candle_snapshot'] = new_snapshot
            print(f"    Updated (Entry: {new_snapshot['entry_price']})")

        # 2. History Events
        history = strat_data.get('history', [])
        for event in history:
            if not isinstance(event, dict): continue
            
            # We only refresh if it has a snapshot or is a close event (to add one)
            if 'snapshot' in event or 'CLOSE' in event.get('side', ''):
                symbol = event['symbol']
                print(f"  > Refreshing history snapshot for {symbol} ({event['side']})...")
                
                is_forex = any(cur in symbol for cur in ['EUR', 'USD', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF']) and '/' in symbol and len(symbol) == 7
                asset_type = 'forex' if is_forex else 'crypto'
                
                full_market_data = data_fetcher.get_data(symbol, asset_type=asset_type)
                if full_market_data.empty: continue
                
                # Slice market data to the time of the event
                event_ts = pd.to_datetime(event['timestamp']).tz_localize(None)
                market_data_to_event = full_market_data[full_market_data.index <= event_ts]
                
                if market_data_to_event.empty:
                    # If event is in the future relative to data, use full
                    market_data_to_event = full_market_data
                
                # Mock position for signal refresh (preserve SL/TP/tp1 from stored snapshot)
                old_snap = event.get('snapshot') or {}
                mock_pos = {
                    'qty': event.get('quantity', 0.0),
                    'entry_price': event.get('entry_price', event['price']),
                    'side': 'LONG' if 'LONG' in event['side'] else 'SHORT',
                    'stop_loss': old_snap.get('stop_loss') or event.get('stop_loss', 0.0),
                    'take_profit': old_snap.get('take_profit') or event.get('take_profit', 0.0),
                    'tp1_hit': old_snap.get('tp1_hit', event.get('tp1_hit', False)),
                }
                
                signal_data = strategy.generate_signal(market_data_to_event, mock_pos)
                
                # Build new snapshot
                new_snapshot = _build_candle_snapshot(
                    market_data_to_event, 
                    signal_data, 
                    entry_price=event.get('entry_price'),
                    entry_date=event.get('entry_date'),
                    pos_data=mock_pos
                )
                
                if 'CLOSE' in event.get('side', '') or 'pnl' in event:
                    new_snapshot['exit_price'] = event['price']
                event['snapshot'] = new_snapshot
                is_close = 'CLOSE' in event.get('side', '')
                if new_snapshot.get('reason') and not is_close:
                    event['reason'] = new_snapshot['reason']
                print(f"    History updated (Price: {event['price']}, Entry: {new_snapshot['entry_price']}, Reason: {event.get('reason')})")

    ledger.save_ledger()
    print("\n--- Snapshots Refreshed ---")
    
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
    parser = argparse.ArgumentParser(description="Refresh ledger snapshots and/or regenerate dashboard report.")
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Skip API/snapshot refresh; only regenerate docs/report_data.js from ledger.json",
    )
    args = parser.parse_args()
    if args.report_only:
        print(f"--- Report Regeneration: {datetime.now()} ---")
        _regenerate_report()
    else:
        main()
