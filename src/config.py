import os
from dotenv import load_dotenv

# Load environment variables from .env file (if it exists)
load_dotenv()

class Config:
    # API Keys
    CCXT_API_KEY = os.getenv("CCXT_API_KEY")
    CCXT_SECRET = os.getenv("CCXT_SECRET")
    ALPHAVANTAGE_KEY = os.getenv("ALPHAVANTAGE_KEY")
    FMP_API_KEY = os.getenv("FMP_API_KEY")
    
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
    'ma_crossover_crypto': {
        'strategy_module': 'strategies.moving_average',
        'strategy_class': 'MovingAverageStrategy',
        'pairs': ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT', 'SOL/USDT', 'ADA/USDT', 'DOGE/USDT', 'AVAX/USDT', 'DOT/USDT', 'TRX/USDT'],
        'params': {
            'short_window': 12,
            'long_window': 24,
            'trend_window': 50
        }
    },
    'ma_crossover_forex': {
        'strategy_module': 'strategies.moving_average',
        'strategy_class': 'MovingAverageStrategy',
        'pairs': ['EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'USD/CAD', 'USD/CHF', 'EUR/GBP', 'EUR/JPY', 'GBP/JPY'],
        'params': {
            'short_window': 12,
            'long_window': 24,
            'trend_window': 50
        }
    },
    'rsi_crypto': {
        'strategy_module': 'strategies.rsi_strategy',
        'strategy_class': 'RSIStrategy',
        'pairs': ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT', 'SOL/USDT', 'ADA/USDT', 'DOGE/USDT', 'AVAX/USDT', 'DOT/USDT', 'TRX/USDT'],
        'params': {
            'period': 14,
            'overbought': 70,
            'oversold': 30
        }
    },
    'rsi_forex': {
        'strategy_module': 'strategies.rsi_strategy',
        'strategy_class': 'RSIStrategy',
        'pairs': ['EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'USD/CAD', 'USD/CHF', 'EUR/GBP', 'EUR/JPY', 'GBP/JPY'],
        'params': {
            'period': 14,
            'overbought': 70,
            'oversold': 30
        }
    }
}
