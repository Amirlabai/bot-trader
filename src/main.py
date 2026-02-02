import sys
import os
import importlib
from datetime import datetime

# Ensure src and root are in path
sys.path.append(os.path.join(os.getcwd(), 'src'))
sys.path.append(os.getcwd())

from config import Config, TRADING_CONFIG
from data_ingestion import DataFetcher
from ledger_manager import LedgerManager

def load_strategy(module_name, class_name, params):
    try:
        module = importlib.import_module(module_name)
        strategy_class = getattr(module, class_name)
        return strategy_class(params)
    except Exception as e:
        print(f"Failed to load strategy {class_name} from {module_name}: {e}")
        return None

def main():
    print(f"--- Starting Bot Trader Session: {datetime.now()} ---")
    
    ledger = LedgerManager(Config)
    data_fetcher = DataFetcher(Config)
    
    print(f"Current Balance: ${ledger.get_balance():.2f}")

    for strategy_id, config in TRADING_CONFIG.items():
        print(f"\nProcessing Strategy: {strategy_id}")
        
        strategy = load_strategy(config['strategy_module'], config['strategy_class'], config['params'])
        if not strategy:
            continue
            
        pairs = config['pairs']
        for symbol in pairs:
            asset_type = 'forex' if 'EUR' in symbol or 'USD' in symbol and '/' in symbol and len(symbol)==7 else 'crypto'
            
            print(f"  > Analyzing {symbol} ({asset_type})...")
            
            market_data = data_fetcher.get_data(symbol, asset_type=asset_type)
            if market_data.empty:
                print(f"    No data found for {symbol}. Skipping.")
                continue

            # Pass full position object (dict)
            pos_data = ledger.get_position(symbol)
            
            # Generate Signal
            # Expected format: {'action': 'buy/sell/hold', 'quantity_pct': 0.5, 'stop_loss': 123.4}
            signal_data = strategy.generate_signal(market_data, pos_data)
            
            action = signal_data.get('action', 'hold')
            current_price = market_data['close'].iloc[-1]

            print(f"    Action: {action.upper()} | Reason: {signal_data.get('reason', '')} | Price: {current_price}")

            if action == 'buy':
                # Determine Size
                pct = signal_data.get('quantity_pct', 0.1) # Default 10%
                cash = ledger.get_balance()
                amount_to_spend = cash * pct
                
                # Check min trade
                if amount_to_spend > 10:
                    quantity = amount_to_spend / current_price
                    new_sl = signal_data.get('stop_loss', 0.0)
                    if ledger.update_position(symbol, quantity, current_price, 'buy', stop_loss=new_sl):
                        print(f"    EXECUTED BUY: {quantity:.6f} {symbol} @ {current_price} (SL: {new_sl})")
            
            elif action == 'sell':
                if pos_data:
                    pct = signal_data.get('quantity_pct', 1.0) # Default 100%
                    quantity_to_sell = pos_data['qty'] * pct
                    
                    if ledger.update_position(symbol, quantity_to_sell, current_price, 'sell'):
                        print(f"    EXECUTED SELL: {quantity_to_sell:.6f} {symbol} @ {current_price}")
                        
                        # If partial sell (TP Hit), mark it
                        if 'Partially' in signal_data.get('reason', ''):
                             ledger.mark_tp1_hit(symbol)
                             
                        # Update SL if provided (Trailing or Breakeven)
                        new_sl = signal_data.get('stop_loss')
                        if new_sl:
                            ledger.update_stop_loss(symbol, new_sl)
                            print(f"    UPDATED SL: {new_sl}")

            elif action == 'hold':
                # Check for SL Update (Trailing Stop without trading)
                new_sl = signal_data.get('stop_loss')
                if new_sl and pos_data:
                     # Only update if new_sl is higher (for longs)
                     if new_sl > pos_data.get('stop_loss', 0):
                         ledger.update_stop_loss(symbol, new_sl)
                         print(f"    UPDATED TRAILING SL: {new_sl}")

    print("\n--- Session Complete ---")
    print(f"Final Balance: ${ledger.get_balance():.2f}")
    
    ledger.save_ledger()
    ledger.sync_to_remote(commit_message=f"Journal Update: {datetime.now().strftime('%Y-%m-%d')}")

if __name__ == "__main__":
    main()
