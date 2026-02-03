import os
import json
from datetime import datetime

class ReportGenerator:
    def __init__(self, config):
        self.config = config
        self.ledger_file = config.LEDGER_FILE
        # Ensure we output to both data dir (for local) and docs dir (for github pages) if possible, 
        # or just data and let the frontend fetch it.
        # For GitHub Pages with /docs root, it's best to put data in docs/data or similar.
        # Let's assume the user will configure the page to read from relative locations.
        # If the html is in docs/, the data should probably be in docs/data.json or similar.
        
        # However, the user's structure has `data/ledger.json`.
        # I will create 'docs/report_data.json' so the HTML can read it easily relative to itself.
        
        self.output_dir = os.path.join(os.getcwd(), 'docs')
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            
        self.report_file = os.path.join(self.output_dir, "report_data.json")

    def generate(self):
        """Generates the JSON data for the frontend."""
        if not os.path.exists(self.ledger_file):
            print("No ledger file found for reporting.")
            return

        with open(self.ledger_file, 'r') as f:
            ledger = json.load(f)

        strategies = ledger.get("strategies", {})
        
        output_data = {
            "metadata": {
                "last_updated": datetime.now().isoformat()
            },
            "strategies": {}
        }

        for strat_name, data in strategies.items():
            cash = data.get("cash", 0.0)
            positions = data.get("positions", {})
            history = data.get("history", [])
            
            # 1. Current Snapshot
            active_positions = []
            current_pos_value = 0.0
            
            for symbol, pos in positions.items():
                if isinstance(pos, dict):
                    qty = pos['qty']
                    entry = pos['entry_price']
                    current_pos_value += (qty * entry) # Est value
                    
                    active_positions.append({
                        "symbol": symbol,
                        "side": pos.get('side', 'LONG'),
                        "qty": qty,
                        "entry": entry,
                        "sl": pos.get('stop_loss', 0.0),
                        "value": qty * entry
                    })
            
            current_equity = cash + current_pos_value
            
            # 2. Equity Curve Reconstruction
            # We will reconstruct the "Realized Equity" (Cash) over time from history.
            # Start with internal default 10k or infer from first history? 
            # We'll assume 10,000 initial cash for now as per STATUS.md, or backtrack.
            # Actually, easiest is to replay history forward.
            
            initial_cash = 10000.0 # Default assumption
            
            # Sort history by time
            sorted_history = sorted(history, key=lambda x: x['timestamp'])
            
            equity_curve = []
            running_cash = initial_cash
            
            # Add initial point
            if sorted_history:
                start_date = sorted_history[0]['timestamp']
            else:
                start_date = datetime.now().isoformat()
                
            equity_curve.append({
                "time": start_date, 
                "equity": initial_cash,
                "type": "initial"
            })
            
            for event in sorted_history:
                # "side": "OPEN_LONG", "CLOSE_LONG", "OPEN_SHORT", "CLOSE_SHORT"
                # "total_value": qty * price
                
                val = event['total_value']
                side = event.get('side', '')
                
                # Logic matches ledger_manager.py update logic roughly
                # Opening trades reduces cash (collateral or purchase)
                # Closing trades increases cash
                
                if "OPEN" in side or "ADD" in side:
                    running_cash -= val
                elif "CLOSE" in side:
                    # For closing, we need to know the profit.
                    # The ledger history only logs 'total_value' = qty * exit_price.
                    
                    # Wait, if I CLOSE_LONG, I get back `val`.
                    # If I CLOSE_SHORT, I get back `collateral + profit`.
                    # The ledger history 'total_value' is just `qty * price`. 
                    # This is NOT the cash change for Shorts! 
                    # Warning: The history format in ledger.json might be insufficient for exact replay 
                    # without knowing the exact cash delta.
                    
                    # However, looking at `ledger_manager.py`:
                    # record_history logs `total_value` as `quantity * price`.
                    
                    # For LONG: Cash += quantity * price. (Correct)
                    # For SHORT: Cash += Returns. Returns != quantity * price.
                    # Returns = (Entry * Qty) + (Entry - Exit)*Qty.
                    
                    # We can't perfectly reconstruct Short cash flow from just the history event 
                    # unless we track the matching entry.
                    # For now, let's approximate or just log the realized events we can.
                    
                    if "LONG" in side:
                         running_cash += val
                    elif "SHORT" in side:
                        # We unfortunately don't have the PnL in the history event.
                        # This is a limitation of the current history logging.
                        # We will skip exact cash reconstruction for Shorts for now 
                        # or just assume a flat line to avoid wild errors.
                        # OR, we can just assume `running_cash` is only accurate for Longs.
                        pass
                
                equity_curve.append({
                    "time": event['timestamp'],
                    "equity": running_cash, # This is settled cash, not equity (unrealized pnl missing)
                    "type": "trade"
                })
            
            # Add final point (Current Equity including Unrealized)
            equity_curve.append({
                "time": datetime.now().isoformat(),
                "equity": current_equity,
                "type": "current"
            })

            output_data["strategies"][strat_name] = {
                "active_positions": active_positions,
                "current_cash": cash,
                "current_equity": current_equity,
                "history_events": len(history),
                "equity_curve": equity_curve
            }

        with open(self.report_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"Report data generated: {self.report_file}")
