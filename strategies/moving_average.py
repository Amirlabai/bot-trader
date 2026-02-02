from .base_strategy import BaseStrategy
import pandas as pd

class MovingAverageStrategy(BaseStrategy):
    def generate_signal(self, market_data: pd.DataFrame, current_position: float) -> str:
        """
        Simple SMA Crossover.
        Buy when Short MA crosses above Long MA.
        Sell when Short MA crosses below Long MA.
        """
        short_window = self.params.get('short_window', 50)
        long_window = self.params.get('long_window', 200)

        if len(market_data) < long_window:
            return 'hold'

        # Calculate Indicators
        signals = pd.DataFrame(index=market_data.index)
        signals['short_mavg'] = market_data['close'].rolling(window=short_window, min_periods=1).mean()
        signals['long_mavg'] = market_data['close'].rolling(window=long_window, min_periods=1).mean()
        
        # Current values (last row)
        current_short = signals['short_mavg'].iloc[-1]
        current_long = signals['long_mavg'].iloc[-1]
        
        # Previous values (second to last row) for crossover check
        # We need at least 2 rows
        if len(signals) < 2:
            return 'hold'
            
        prev_short = signals['short_mavg'].iloc[-2]
        prev_long = signals['long_mavg'].iloc[-2]

        # Logic
        # Cross Over (Golden Cross) -> Buy
        if prev_short <= prev_long and current_short > current_long:
            if current_position == 0:
                return 'buy'
        
        # Cross Under (Death Cross) -> Sell
        elif prev_short >= prev_long and current_short < current_long:
            if current_position > 0:
                return 'sell'
                
        return 'hold'
