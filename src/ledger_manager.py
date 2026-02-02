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
        return self.ledger.get("positions", {}).get(symbol, 0.0)

    def update_position(self, symbol, quantity, price, side):
        """
        Updates cash and position based on a trade execution.
        side: 'buy' or 'sell'
        """
        cost = quantity * price
        
        if side == 'buy':
            if self.ledger["cash"] >= cost:
                self.ledger["cash"] -= cost
                current_pos = self.ledger["positions"].get(symbol, 0.0)
                self.ledger["positions"][symbol] = current_pos + quantity
                self.record_history(symbol, side, quantity, price)
                return True
            else:
                print(f"Insufficient funds to buy {symbol}. Cash: {self.ledger['cash']}, Cost: {cost}")
                return False
        
        elif side == 'sell':
            current_pos = self.ledger["positions"].get(symbol, 0.0)
            if current_pos >= quantity:
                self.ledger["cash"] += cost
                self.ledger["positions"][symbol] = current_pos - quantity
                
                # Cleanup zero positions
                if self.ledger["positions"][symbol] <= 0:
                     del self.ledger["positions"][symbol]
                     
                self.record_history(symbol, side, quantity, price)
                return True
            else:
                print(f"Insufficient position to sell {symbol}. Owned: {current_pos}, Selling: {quantity}")
                return False
        
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
