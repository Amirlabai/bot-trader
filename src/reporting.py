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
                    
                    # Use last known price if available, otherwise fallback to entry (0 PnL)
                    current_price = pos.get('last_price', entry)
                    
                    market_value = qty * current_price
                    current_pos_value += market_value
                    
                    unrealized_pnl = 0.0
                    side = pos.get('side', 'LONG')
                    
                    if side == 'LONG':
                        unrealized_pnl = (current_price - entry) * qty
                    elif side == 'SHORT':
                        # Short PnL = (Entry - Current) * Qty
                        unrealized_pnl = (entry - current_price) * qty

                    active_positions.append({
                        "symbol": symbol,
                        "side": side,
                        "qty": qty,
                        "entry": entry,
                        "current_price": current_price,
                        "unrealized_pnl": unrealized_pnl,
                        "sl": pos.get('stop_loss', 0.0),
                        "tp1": pos.get('tp1_hit', False),
                        "tp_price": pos.get('take_profit', 0.0),
                        "value": market_value
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
            running_inventory_value = 0.0 # Track cost basis of open positions (approx)
            
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
                val = event['total_value']
                side = event.get('side', '')
                qty = event['quantity']
                price = event['price']

                if "OPEN" in side or "ADD" in side:
                    # Cash goes down, Inventory goes up
                    running_cash -= val
                    
                    # For Short, we technically get cash (proceeds) but lock it as collateral + margin.
                    # But sticking to the "Cash Balance" view where Shorts consume Buying Power/Cash for collateral:
                    if "SHORT" in side:
                         # Treat as collateral lock (same as drawing down cash)
                         # Inventory value (Negative? No, let's track Net Liquidation Value Logic)
                         # Net Liq = Cash + Position Value.
                         # Short Position Value = Liability (Negative).
                         # But wait, we deducted Cash. 
                         # If we deduct cash for collateral, we shouldn't also have negative inventory value 
                         # unless we treat that cash as "Locked" not "Gone".
                         
                         # Simpler Model used in `ledger_manager`:
                         # OPEN SHORT: Cash -= Cost (Collateral). 
                         # So Net Equity = Cash (Remaining) + Collateral (Locked) = Original Cash.
                         running_inventory_value += val 
                    else:
                         # LONG
                         running_inventory_value += val
                
                elif "CLOSE" in side:
                    if "LONG" in side:
                        # Cash += Revenue
                        # Inventory -= Cost Basis
                        
                        revenue = val
                        # Get entry info from event or approximation
                        # If we have pnl, we know exact numbers
                        pnl = event.get('pnl', 0.0)
                        
                        running_cash += revenue
                        
                        # Inventory Change = Revenue - PnL = Cost Basis
                        cost_basis_released = revenue - pnl
                        running_inventory_value -= cost_basis_released

                    elif "SHORT" in side:
                        # Cash += Collateral + Profit
                        # Inventory -= Collateral
                        
                        # Reconstruct from PnL
                        pnl = event.get('pnl', 0.0)
                        entry_price = event.get('entry_price', price) # Fallback
                        
                        # In ledger manager:
                        # entry_val = qty * entry_price (This is the Collateral we tracked in inventory)
                        entry_val = qty * entry_price
                        
                        # We return: entry_val + pnl to cash
                        amount_returned = entry_val + pnl
                        running_cash += amount_returned
                        
                        running_inventory_value -= entry_val

                # Ensure non-negative inventory value (sanity check for approximations)
                if running_inventory_value < 0: running_inventory_value = 0

                equity_curve.append({
                    "time": event['timestamp'],
                    "equity": running_cash + running_inventory_value,
                    "type": "trade"
                })
            
            # Add final point (Current Equity including Unrealized)
            equity_curve.append({
                "time": datetime.now().isoformat(),
                "equity": current_equity,
                "type": "current"
            })

            # 3. Trade History (Closed Positions)
            trade_history = []
            for event in sorted_history:
                if "pnl" in event:
                    trade_history.append({
                        "time": event['timestamp'],
                        "symbol": event['symbol'],
                        "side": "LONG" if "LONG" in event['side'] else "SHORT",
                        "qty": event['quantity'],
                        "entry_price": event.get('entry_price', 0.0),
                        "exit_price": event['price'],
                        "pnl": event['pnl']
                    })

            output_data["strategies"][strat_name] = {
                "active_positions": active_positions,
                "current_cash": cash,
                "current_equity": current_equity,
                "history_events": len(history),
                "equity_curve": equity_curve,
                "trade_history": list(reversed(trade_history)) # Newest first
            }

        with open(self.report_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)
        
        # Also write JS file for local usage without CORS
        js_file = os.path.join(self.output_dir, "report_data.js")
        with open(js_file, 'w', encoding='utf-8') as f:
            f.write("window.REPORT_DATA = ")
            json.dump(output_data, f, indent=2)
            f.write(";")

        print(f"Report data generated: {self.report_file} and {js_file}")
