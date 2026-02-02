from abc import ABC, abstractmethod
import pandas as pd

class BaseStrategy(ABC):
    def __init__(self, params=None):
        """
        Initialize the strategy with a dictionary of parameters.
        """
        self.params = params or {}

    @abstractmethod
    def generate_signal(self, market_data: pd.DataFrame, position_data: dict) -> dict:
        """
        Analyzes market data and returns a signal dictionary.
        market_data: OHLCV DataFrame
        position_data: Dictionary {'qty', 'entry_price', 'stop_loss', 'tp1_hit'} or None if no position.
        
        Returns:
            {
                'action': 'buy' | 'sell' | 'hold',
                'quantity_pct': float (0.0 - 1.0), # Percent of Balance to buy or Position to sell
                'stop_loss': float, # For Buys or Trailing Updates
                'reason': str
            }
        """
        pass
