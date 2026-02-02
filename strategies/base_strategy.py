from abc import ABC, abstractmethod
import pandas as pd

class BaseStrategy(ABC):
    def __init__(self, params=None):
        """
        Initialize the strategy with a dictionary of parameters.
        """
        self.params = params or {}

    @abstractmethod
    def generate_signal(self, market_data: pd.DataFrame, current_position: float) -> str:
        """
        Analyzes market data and returns a signal.
        market_data: OHLCV DataFrame
        current_position: Current quantity held (0 if none)
        
        Returns: 'buy', 'sell', or 'hold'
        """
        pass
