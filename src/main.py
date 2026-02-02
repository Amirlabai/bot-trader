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
    
    # Iterate through configured strategies
    for strategy_id, config in TRADING_CONFIG.items():
        print(f"\n==========================================")
        print(f"Processing Strategy: {strategy_id}")
        current_balance = ledger.get_balance(strategy_id)
        print(f"Strategy Balance: ${current_balance:.2f}")
        
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

            # Pass full position object (dict) linked to this strategy
            pos_data = ledger.get_position(strategy_id, symbol)
            
            # Generate Signal
            try:
                signal_data = strategy.generate_signal(market_data, pos_data)
            except Exception as e:
                print(f"    Error generating signal: {e}")
                continue
            
            action = signal_data.get('action', 'hold')
            current_price = market_data['close'].iloc[-1]

            print(f"    Action: {action.upper()} | Reason: {signal_data.get('reason', '')} | Price: {current_price}")

            if action == 'buy':
                # Risk Management: Size based on 1% Risk
                # Risk Amount = 1% of Total Realized Equity
                total_equity = ledger.get_total_equity(strategy_id)
                risk_amount = total_equity * 0.01
                
                new_sl = signal_data.get('stop_loss', 0.0)
                
                # Risk Per Share = Entry - SL
                if new_sl > 0 and current_price > new_sl:
                    risk_per_share = current_price - new_sl
                    quantity = risk_amount / risk_per_share
                else:
                    # Fallback if no SL provided (shouldn't happen with ATR logic) or invalid SL: Use simple 10% size
                    print(f"    WARNING: Invalid SL ({new_sl}) for Buy. Defaulting to 10% sizing.")
                    current_cash = ledger.get_balance(strategy_id)
                    quantity = (current_cash * 0.10) / current_price

                # Check Affordability (Do we have enough Cash?)
                cost = quantity * current_price
                current_cash = ledger.get_balance(strategy_id)
                
                if cost > current_cash:
                    # Scale down to max cash
                    quantity = current_cash / current_price
                    print(f"    NOTICE: Risk-based size exceeds cash. Scaled down to max affordable.")

                # Minimum Trade Value Check ($10)
                if (quantity * current_price) > 10:
                    if ledger.update_position(strategy_id, symbol, quantity, current_price, 'buy', stop_loss=new_sl):
                        print(f"    EXECUTED BUY: {quantity:.6f} {symbol} @ {current_price} (SL: {new_sl})")
                        print(f"      > Risk: ${risk_amount:.2f} (1%) | SL Distance: ${(current_price - new_sl):.2f}")
            
            elif action == 'sell':
                if pos_data:
                    pct = signal_data.get('quantity_pct', 1.0) 
                    quantity_to_sell = pos_data['qty'] * pct
                    
                    if ledger.update_position(strategy_id, symbol, quantity_to_sell, current_price, 'sell'):
                        print(f"    EXECUTED SELL: {quantity_to_sell:.6f} {symbol} @ {current_price}")
                        
                        if 'Partially' in signal_data.get('reason', ''):
                             ledger.mark_tp1_hit(strategy_id, symbol)
                             
                        new_sl = signal_data.get('stop_loss')
                        if new_sl:
                            ledger.update_stop_loss(strategy_id, symbol, new_sl)
                            print(f"    UPDATED SL: {new_sl}")

            elif action == 'hold':
                # Check for SL Update (Trailing Stop)
                new_sl = signal_data.get('stop_loss')
                if new_sl and pos_data:
                     if new_sl > pos_data.get('stop_loss', 0):
                         ledger.update_stop_loss(strategy_id, symbol, new_sl)
                         print(f"    UPDATED TRAILING SL: {new_sl}")

    print("\n--- Session Complete ---")
    
    ledger.save_ledger()
    ledger.sync_to_remote(commit_message=f"Journal Update: {datetime.now().strftime('%Y-%m-%d')}")

if __name__ == "__main__":
    main()
