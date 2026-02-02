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
                    return json.load(f)
            except json.JSONDecodeError:
                print("Error decoding ledger file. Starting fresh.")
        
        # Default Initial State
        return {
            "cash": 10000.0,  # Startup mock cash
            "positions": {},   # { "BTC/USDT": 0.5, "EURUSD": 1000 }
            "history": []      # List of trade records
        }

    def save_ledger(self):
        with open(self.ledger_file, 'w') as f:
            json.dump(self.ledger, f, indent=4)

    def get_balance(self):
        return self.ledger.get("cash", 0.0)

    def get_position(self, symbol):
        """
        Returns the position dictionary for a symbol.
        Format: {'qty': float, 'entry_price': float, 'stop_loss': float, 'tp1_hit': bool}
        Returns None if no position exists.
        """
        pos = self.ledger.get("positions", {}).get(symbol)
        if pos and isinstance(pos, (int, float)):
             # Migration for old simpler format
             return {'qty': float(pos), 'entry_price': 0.0, 'stop_loss': 0.0, 'tp1_hit': False}
        return pos

    def update_position(self, symbol, quantity, price, side, stop_loss=0.0):
        """
        Updates cash and position based on a trade execution.
        side: 'buy' or 'sell'
        stop_loss: Optional SL price for new entries.
        """
        cost = quantity * price
        
        if side == 'buy':
            if self.ledger["cash"] >= cost:
                self.ledger["cash"] -= cost
                
                current_pos_data = self.get_position(symbol)
                if current_pos_data:
                    # Averaging down/scaling in (Simple weighted average for entry)
                    old_qty = current_pos_data['qty']
                    new_qty = old_qty + quantity
                    avg_entry = ((old_qty * current_pos_data['entry_price']) + (quantity * price)) / new_qty
                    # We keep the old SL/TP status or reset? Strategy decides. 
                    # For now, we update entry and qty, strategy should manage SL updates if needed via separate call.
                    # But if this is a fresh entry logic, we might want to reset. 
                    # Assuming simple addition:
                    current_pos_data['qty'] = new_qty
                    current_pos_data['entry_price'] = avg_entry
                    if stop_loss > 0:
                        current_pos_data['stop_loss'] = stop_loss
                    self.ledger["positions"][symbol] = current_pos_data
                else:
                    # New Position
                    self.ledger["positions"][symbol] = {
                        'qty': quantity,
                        'entry_price': price,
                        'stop_loss': stop_loss,
                        'tp1_hit': False
                    }

                self.record_history(symbol, side, quantity, price)
                return True
            else:
                print(f"Insufficient funds to buy {symbol}. Cash: {self.ledger['cash']}, Cost: {cost}")
                return False
        
        elif side == 'sell':
            current_pos_data = self.get_position(symbol)
            if current_pos_data and current_pos_data['qty'] >= quantity:
                self.ledger["cash"] += cost
                current_pos_data['qty'] -= quantity
                
                # Cleanup zero positions
                if current_pos_data['qty'] <= 1e-6: # Float tolerance
                     del self.ledger["positions"][symbol]
                else:
                     self.ledger["positions"][symbol] = current_pos_data
                     
                self.record_history(symbol, side, quantity, price)
                return True
            else:
                print(f"Insufficient position to sell {symbol}. Owned: {current_pos_data}, Selling: {quantity}")
                return False
        
        return False

    def update_stop_loss(self, symbol, new_sl):
        """
        Updates the Stop Loss for an open position.
        """
        pos = self.get_position(symbol)
        if pos:
            pos['stop_loss'] = new_sl
            self.ledger["positions"][symbol] = pos
            return True
        return False

    def mark_tp1_hit(self, symbol):
        """
        Marks that TP1 has been hit for the position.
        """
        pos = self.get_position(symbol)
        if pos:
            pos['tp1_hit'] = True
            self.ledger["positions"][symbol] = pos
            return True
        return False

    def record_history(self, symbol, side, quantity, price):
        record = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "total_value": quantity * price
        }
        self.ledger["history"].append(record)

    def sync_to_remote(self, commit_message="Update ledger"):
        """
        Commits the ledger file and pushes to remote.
        This assumes the script is running inside the git repo.
        """
        try:
            repo_path = os.getcwd() # Assumes we run from root
            repo = git.Repo(repo_path)
            
            # Configure git user if needed (often needed in CI if not set globally)
            with repo.config_writer() as git_config:
                if not git_config.has_option('user', 'email'):
                    git_config.set_value('user', 'email', 'bot-trader@automated.com')
                    git_config.set_value('user', 'name', 'Bot Trader')

            # Add ledger file
            # Ideally we only add the ledger file, but we can add everything in data/
            repo.index.add([self.ledger_file])
            
            if repo.is_dirty(path=self.ledger_file):
                repo.index.commit(commit_message)
                print(f"Committed ledger update: {commit_message}")
                
                # Push
                # If using a token, the remote URL might need adjustment, 
                # but in GitHub Actions 'actions/checkout' usually handles the auth token for the 'origin'.
                origin = repo.remote(name='origin')
                origin.push()
                print("Pushed ledger to remote.")
            else:
                print("No changes to ledger to commit.")

        except Exception as e:
            print(f"Git Sync Failed: {e}")
