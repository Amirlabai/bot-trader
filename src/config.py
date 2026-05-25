import os
from dotenv import load_dotenv

from shared.constants import TP1_EXIT_REASONS, TP1_HIT_REASON_LONG, TP1_HIT_REASON_SHORT

# Load environment variables from .env file (if it exists)
load_dotenv()


def _env_float(name, default):
    raw = os.getenv(name, str(default))
    try:
        return float(raw)
    except ValueError as e:
        raise ValueError(f"Invalid {name} in environment: {raw!r}") from e


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
    INITIAL_STRATEGY_CASH = _env_float("INITIAL_STRATEGY_CASH", 10000)


def _load_risk_settings():
    defaults = {
        'equity_risk_pct': 0.01,
        'min_risk_fraction': 0.25,
        'min_notional_usd': 10.0,
    }
    settings = {
        'equity_risk_pct': _env_float('EQUITY_RISK_PCT', defaults['equity_risk_pct']),
        'min_risk_fraction': _env_float('MIN_RISK_FRACTION', defaults['min_risk_fraction']),
        'min_notional_usd': _env_float('MIN_NOTIONAL_USD', defaults['min_notional_usd']),
    }
    pct = settings['equity_risk_pct']
    if not 0 < pct <= 1:
        raise ValueError(f"equity_risk_pct must be in (0, 1], got {pct}")
    frac = settings['min_risk_fraction']
    if not 0 < frac < 1:
        raise ValueError(f"min_risk_fraction must be in (0, 1), got {frac}")
    if settings['min_notional_usd'] <= 0:
        raise ValueError(f"min_notional_usd must be > 0, got {settings['min_notional_usd']}")
    return settings


RISK_SETTINGS = _load_risk_settings()

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
