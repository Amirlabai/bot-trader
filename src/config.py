import os
from dotenv import load_dotenv

# Load environment variables from .env file (if it exists)
load_dotenv()

class Config:
    # API Keys
    CCXT_API_KEY = os.getenv("CCXT_API_KEY")
    CCXT_SECRET = os.getenv("CCXT_SECRET")
    ALPHAVANTAGE_KEY = os.getenv("ALPHAVANTAGE_KEY")
    
    # GitHub Token for pushing (optional if using GITHUB_TOKEN in CI)
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

    # Data Settings
    DATA_DIR = os.path.join(os.getcwd(), 'data')
    LEDGER_FILE = os.path.join(DATA_DIR, 'ledger.json')

    # Defaults
    DEFAULT_TIMEFRAME = '1d'

# Strategy Configuration
# Maps Strategy ID -> { 'class': ClassName, 'pairs': [list of pairs], 'params': {dict of params} }
TRADING_CONFIG = {
    'ma_crossover_btc': {
        'strategy_module': 'strategies.moving_average',
        'strategy_class': 'MovingAverageStrategy',
        'pairs': ['BTC/USDT', 'ETH/USDT'],
        'params': {
            'short_window': 50,
            'long_window': 200
        }
    },
    'rsi_eth': {
        'strategy_module': 'strategies.rsi_strategy',
        'strategy_class': 'RSIStrategy',
        'pairs': ['ETH/USDT'],
        'params': {
            'period': 14,
            'overbought': 70,
            'oversold': 30
        }
    },
     'forex_eurusd_ma': {
        'strategy_module': 'strategies.moving_average',
        'strategy_class': 'MovingAverageStrategy',
        'pairs': ['EUR/USD'], # Forex pair format for Alpha Vantage might differ, typically "EURUSD" or "EUR/USD" depending on normalizer
        'params': {
            'short_window': 20,
            'long_window': 50
        }
    }
}
