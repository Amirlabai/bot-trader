import json
import os
import git
from datetime import datetime

class LedgerManager:
    def __init__(self, config):
        self.config = config
        self.ledger_file = config.LEDGER_FILE
        self.data_dir = config.DATA_DIR
        self._ensure_data_dir()
        self.ledger = self._load_ledger()

    def _ensure_data_dir(self):
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

    def _load_ledger(self):
        if os.path.exists(self.ledger_file):
            try:
                with open(self.ledger_file, 'r') as f:
                    data = json.load(f)
                    # Simple check to see if we need migration to new schema
                    if "strategies" not in data:
                        print("Migrating legacy ledger to strategy-based schema...")
                        return {"strategies": {}} 
                    return data
            except json.JSONDecodeError:
                print("Error decoding ledger file. Starting fresh.")
        
        return {"strategies": {}}

    def _ensure_strategy_state(self, strategy_id):
        if strategy_id not in self.ledger["strategies"]:
            self.ledger["strategies"][strategy_id] = {
                "cash": 10000.0,
                "positions": {},
                "history": []
            }

    def save_ledger(self):
        with open(self.ledger_file, 'w') as f:
            json.dump(self.ledger, f, indent=4)

    def get_balance(self, strategy_id):
        self._ensure_strategy_state(strategy_id)
        return self.ledger["strategies"][strategy_id]["cash"]

    def get_total_equity(self, strategy_id):
        """
        Calculates Total Realized Equity: Cash + Cost Basis of Open Positions.
        Does not include Unrealized PnL.
        """
        self._ensure_strategy_state(strategy_id)
        strat = self.ledger["strategies"][strategy_id]
        cash = strat["cash"]
        
        positions_cost = 0.0
        for symbol, pos in strat["positions"].items():
            # Handle both simple float (legacy) and dict
            if isinstance(pos, dict):
                positions_cost += pos['qty'] * pos['entry_price']
            else:
                # Should not happen with new logic, but safe fallback
                pass
                
        return cash + positions_cost

    def get_position(self, strategy_id, symbol):
        """
        Returns the position dictionary for a symbol under a specific strategy.
        Format: {'qty': float, 'entry_price': float, 'stop_loss': float, 'tp1_hit': bool}
        Returns None if no position exists.
        """
        self._ensure_strategy_state(strategy_id)
        pos = self.ledger["strategies"][strategy_id]["positions"].get(symbol)
        
        if pos and isinstance(pos, (int, float)):
             # Migration for old simpler format
             return {'qty': float(pos), 'entry_price': 0.0, 'stop_loss': 0.0, 'tp1_hit': False}
        return pos

    def update_position(self, strategy_id, symbol, quantity, price, side, stop_loss=0.0):
        """
        Updates cash and position based on a trade execution for a specific strategy.
        """
        self._ensure_strategy_state(strategy_id)
        strat_ledger = self.ledger["strategies"][strategy_id]
        
        cost = quantity * price
        
        if side == 'buy':
            if strat_ledger["cash"] >= cost:
                strat_ledger["cash"] -= cost
                
                current_pos_data = self.get_position(strategy_id, symbol)
                if current_pos_data:
                    # Averaging
                    old_qty = current_pos_data['qty']
                    new_qty = old_qty + quantity
                    avg_entry = ((old_qty * current_pos_data['entry_price']) + (quantity * price)) / new_qty
                    
                    current_pos_data['qty'] = new_qty
                    current_pos_data['entry_price'] = avg_entry
                    if stop_loss > 0:
                        current_pos_data['stop_loss'] = stop_loss
                    strat_ledger["positions"][symbol] = current_pos_data
                else:
                    # New Position
                    strat_ledger["positions"][symbol] = {
                        'qty': quantity,
                        'entry_price': price,
                        'stop_loss': stop_loss,
                        'tp1_hit': False
                    }

                self.record_history(strategy_id, symbol, side, quantity, price)
                return True
            else:
                print(f"[{strategy_id}] Insufficient funds to buy {symbol}. Cash: {strat_ledger['cash']}, Cost: {cost}")
                return False
        
        elif side == 'sell':
            current_pos_data = self.get_position(strategy_id, symbol)
            if current_pos_data and current_pos_data['qty'] >= quantity:
                strat_ledger["cash"] += cost
                current_pos_data['qty'] -= quantity
                
                if current_pos_data['qty'] <= 1e-6:
                     del strat_ledger["positions"][symbol]
                else:
                     strat_ledger["positions"][symbol] = current_pos_data
                     
                self.record_history(strategy_id, symbol, side, quantity, price)
                return True
            else:
                print(f"[{strategy_id}] Insufficient position to sell {symbol}. Owned: {current_pos_data}, Selling: {quantity}")
                return False
        
        return False

    def update_stop_loss(self, strategy_id, symbol, new_sl):
        pos = self.get_position(strategy_id, symbol)
        if pos:
            pos['stop_loss'] = new_sl
            self.ledger["strategies"][strategy_id]["positions"][symbol] = pos
            return True
        return False

    def mark_tp1_hit(self, strategy_id, symbol):
        pos = self.get_position(strategy_id, symbol)
        if pos:
            pos['tp1_hit'] = True
            self.ledger["strategies"][strategy_id]["positions"][symbol] = pos
            return True
        return False

    def record_history(self, strategy_id, symbol, side, quantity, price):
        self._ensure_strategy_state(strategy_id)
        record = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "total_value": quantity * price
        }
        self.ledger["strategies"][strategy_id]["history"].append(record)

    def sync_to_remote(self, commit_message="Update ledger"):
        try:
            repo_path = os.getcwd() 
            repo = git.Repo(repo_path)
            
            # Configure git user (Critical for CI)
            with repo.config_writer() as git_config:
                if not git_config.has_option('user', 'email'):
                    git_config.set_value('user', 'email', '41898282+github-actions[bot]@users.noreply.github.com')
                    git_config.set_value('user', 'name', 'github-actions[bot]')

            # Add ledger and version file if changed
            repo.index.add([self.ledger_file])
            if os.path.exists("VERSION"):
                repo.index.add(["VERSION"])
            
            if repo.is_dirty(path=self.ledger_file) or repo.is_dirty(path="VERSION"):
                repo.index.commit(commit_message)
                print(f"Committed: {commit_message}")
                
                # Push to master specifically to avoid detached HEAD issues in CI
                origin = repo.remote(name='origin')
                # Use git command directly for specific refspec logic which is often safer/clearer
                repo.git.push('origin', 'HEAD:master')
                print("Pushed to origin/master.")
            else:
                print("No changes to commit.")

        except Exception as e:
            print(f"Git Sync Failed: {e}")
