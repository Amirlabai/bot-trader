import sys
import os
import importlib
import time
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
            # Heuristic for Asset Type
            is_forex = any(cur in symbol for cur in ['EUR', 'USD', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF']) and '/' in symbol and len(symbol) == 7
            asset_type = 'forex' if is_forex else 'crypto'
            
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

            # Current State
            is_flat = pos_data is None
            position_side = pos_data.get('side', 'LONG') if pos_data else None
            
            # --- SIGNAL PROCESSING ---
            if action == 'buy':
                # 1. Close SHORT if exists
                if position_side == 'SHORT':
                    print(f"    Signal BUY -> Closing SHORT {symbol}")
                    pct = signal_data.get('quantity_pct', 1.0)
                    qty_to_cover = pos_data['qty'] * pct
                    if ledger.update_position(strategy_id, symbol, qty_to_cover, current_price, 'buy'):
                         print(f"    EXECUTED COVER SHORT: {qty_to_cover:.6f} {symbol} @ {current_price}")

                # 2. Open/Add LONG (If Flat or Long)
                elif position_side in [None, 'LONG']:
                    # Risk Management: Size based on 1% Risk
                    total_equity = ledger.get_total_equity(strategy_id)
                    risk_amount = total_equity * 0.01
                    new_sl = signal_data.get('stop_loss', 0.0)
                    
                    # Risk Per Share = Entry - SL
                    risk_per_share = current_price - new_sl if new_sl > 0 else current_price * 0.05 # Fallback
                    
                    if risk_per_share <= 0: risk_per_share = current_price * 0.01 # Sanity check
                    
                    quantity = risk_amount / risk_per_share
                    
                    # Cash Check
                    current_cash = ledger.get_balance(strategy_id)
                    cost = quantity * current_price
                    if cost > current_cash:
                        quantity = current_cash / current_price
                    
                    if (quantity * current_price) > 10:
                        if ledger.update_position(strategy_id, symbol, quantity, current_price, 'buy', stop_loss=new_sl):
                             print(f"    EXECUTED OPEN LONG: {quantity:.6f} {symbol} @ {current_price} (SL {new_sl})")

            elif action == 'sell':
                # 1. Close LONG if exists
                if position_side == 'LONG':
                    print(f"    Signal SELL -> Closing LONG {symbol}")
                    pct = signal_data.get('quantity_pct', 1.0)
                    qty_to_sell = pos_data['qty'] * pct
                    if ledger.update_position(strategy_id, symbol, qty_to_sell, current_price, 'sell'):
                        print(f"    EXECUTED SELL LONG: {qty_to_sell:.6f} {symbol} @ {current_price}")
                        # Check for TP/SL updates if partial
                        new_sl = signal_data.get('stop_loss')
                        if new_sl: ledger.update_stop_loss(strategy_id, symbol, new_sl)

                # 2. Open/Add SHORT (If Flat or Short)
                elif position_side in [None, 'SHORT']:
                    # Risk Management for Short
                    total_equity = ledger.get_total_equity(strategy_id)
                    risk_amount = total_equity * 0.01
                    new_sl = signal_data.get('stop_loss', 0.0)
                    
                    # Risk Per Share = SL - Entry (Short loses when price goes up)
                    # For Short, SL > Entry.
                    risk_per_share = new_sl - current_price if new_sl > 0 else current_price * 0.05
                    if risk_per_share <= 0: risk_per_share = current_price * 0.01

                    quantity = risk_amount / risk_per_share
                    
                    # Collateral Check (Cash needs to cover Short Value)
                    current_cash = ledger.get_balance(strategy_id)
                    market_value = quantity * current_price
                    if market_value > current_cash:
                        quantity = current_cash / current_price
                        
                    if (quantity * current_price) > 10:
                        if ledger.update_position(strategy_id, symbol, quantity, current_price, 'sell', stop_loss=new_sl):
                             print(f"    EXECUTED OPEN SHORT: {quantity:.6f} {symbol} @ {current_price} (SL {new_sl})")

            elif action == 'hold':
                 # Trailing SL Updates
                 new_sl = signal_data.get('stop_loss')
                 if new_sl and pos_data:
                      ledger.update_stop_loss(strategy_id, symbol, new_sl)
                      print(f"    UPDATED SL: {new_sl}")

    print("\n--- Session Complete ---")
    
    ledger.save_ledger()

    # Generate Report (JSON for SPA)
    from reporting import ReportGenerator
    print("\n--- Generating Performance Report Data ---")
    try:
        reporter = ReportGenerator(Config)
        reporter.generate()
    except Exception as e:
        print(f"Error generating report: {e}")

    ledger.sync_to_remote(commit_message=f"Journal Update: {datetime.now().strftime('%Y-%m-%d')}")

if __name__ == "__main__":
    main()
