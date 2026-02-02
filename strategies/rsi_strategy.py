from .base_strategy import BaseStrategy
import pandas as pd

class RSIStrategy(BaseStrategy):
    def _calculate_rsi(self, data, window):
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def generate_signal(self, market_data: pd.DataFrame, position_data: dict) -> dict:
        """
        RSI Mean Reversion Strategy.
        Buy when RSI < Oversold.
        Sell when RSI > Overbought.
        """
        period = self.params.get('period', 14)
        overbought = self.params.get('overbought', 70)
        oversold = self.params.get('oversold', 30)
        
        # Default signal
        signal = {'action': 'hold', 'reason': 'Neutral'}

        if len(market_data) < period + 1:
            return signal

        # Calculate RSI
        rsi_series = self._calculate_rsi(market_data['close'], period)
        current_rsi = rsi_series.iloc[-1]
        
        current_position_qty = position_data['qty'] if position_data else 0.0

        # Logic
        if current_rsi < oversold:
            if current_position_qty == 0:
                return {
                    'action': 'buy',
                    'quantity_pct': 0.1,
                    'stop_loss': 0.0, # No advanced SL logic for this simple strategy yet
                    'reason': f'RSI Oversold ({current_rsi:.2f})'
                }
        
        elif current_rsi > overbought:
            if current_position_qty > 0:
                return {
                    'action': 'sell',
                    'quantity_pct': 1.0, # Sell All
                    'reason': f'RSI Overbought ({current_rsi:.2f})'
                }
        
        return signal
