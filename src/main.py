import sys
import os
import importlib
from datetime import datetime

# Ensure src is in path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from config import Config, TRADING_CONFIG
from data_ingestion import DataFetcher
from ledger_manager import LedgerManager

def load_strategy(module_name, class_name, params):
    """
    Dynamically loads a strategy class from a module.
    """
    try:
        module = importlib.import_module(module_name)
        strategy_class = getattr(module, class_name)
        return strategy_class(params)
    except Exception as e:
        print(f"Failed to load strategy {class_name} from {module_name}: {e}")
        return None

def main():
    print(f"--- Starting Bot Trader Session: {datetime.now()} ---")
    
    # Initialize Core Modules
    ledger = LedgerManager(Config)
    data_fetcher = DataFetcher(Config)
    
    print(f"Current Balance: ${ledger.get_balance():.2f}")

    # Iterate through configured strategies
    for strategy_id, config in TRADING_CONFIG.items():
        print(f"\nProcessing Strategy: {strategy_id}")
        
        # Load Strategy Instance
        strategy = load_strategy(config['strategy_module'], config['strategy_class'], config['params'])
        if not strategy:
            continue
            
        pairs = config['pairs']
        for symbol in pairs:
            # Determine Asset Type (Basic heursitic, can be improved)
            asset_type = 'forex' if 'EUR' in symbol or 'USD' in symbol and '/' in symbol and len(symbol)==7 else 'crypto'
            # Alpha Vantage forex symbols strictly "EURUSD" or "EUR/USD", config has "EUR/USD"
            if asset_type == 'forex' and '/' in symbol:
                 # Clean for checking positions if needed, but fetcher handles normalization
                 pass

            print(f"  > Analyzing {symbol} ({asset_type})...")
            
            # Fetch Data
            market_data = data_fetcher.get_data(symbol, asset_type=asset_type)
            if market_data.empty:
                print(f"    No data found for {symbol}. Skipping.")
                continue

            # Get Current Position
            current_pos = ledger.get_position(symbol)
            
            # Generate Signal
            signal = strategy.generate_signal(market_data, current_pos)
            print(f"    Signal: {signal} | Current Pos: {current_pos}")
            
            # Execute Signal
            current_price = market_data['close'].iloc[-1]
            if signal == 'buy':
                # Simple Sizing: Buy 10% of available cash or fixed amount
                # For demo: Fixed $1000 sized bets or max cash
                amount_to_spend = 1000.0
                if ledger.get_balance() < amount_to_spend:
                    amount_to_spend = ledger.get_balance()
                
                if amount_to_spend > 10: # Minimum trade check
                    quantity = amount_to_spend / current_price
                    if ledger.update_position(symbol, quantity, current_price, 'buy'):
                        print(f"    EXECUTED BUY: {quantity:.6f} {symbol} @ {current_price}")
            
            elif signal == 'sell':
                if current_pos > 0:
                     if ledger.update_position(symbol, current_pos, current_price, 'sell'):
                         print(f"    EXECUTED SELL: {current_pos:.6f} {symbol} @ {current_price}")

    # Finalize
    print("\n--- Session Complete ---")
    print(f"Final Balance: ${ledger.get_balance():.2f}")
    
    # Sync to Git
    ledger.save_ledger()
    ledger.sync_to_remote(commit_message=f"Journal Update: {datetime.now().strftime('%Y-%m-%d')}")

if __name__ == "__main__":
    main()
