from .base_strategy import BaseStrategy
import pandas as pd

class RSIStrategy(BaseStrategy):
    def _calculate_rsi(self, data, window):
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def generate_signal(self, market_data: pd.DataFrame, current_position: float) -> str:
        """
        RSI Mean Reversion Strategy.
        Buy when RSI < Oversold.
        Sell when RSI > Overbought.
        """
        period = self.params.get('period', 14)
        overbought = self.params.get('overbought', 70)
        oversold = self.params.get('oversold', 30)

        if len(market_data) < period + 1:
            return 'hold'

        # Calculate RSI
        rsi_series = self._calculate_rsi(market_data['close'], period)
        current_rsi = rsi_series.iloc[-1]

        # Logic
        if current_rsi < oversold:
            if current_position == 0:
                return 'buy'
        
        elif current_rsi > overbought:
            if current_position > 0:
                return 'sell'
        
        return 'hold'
