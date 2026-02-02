from .base_strategy import BaseStrategy
import pandas as pd
import numpy as np

class MovingAverageStrategy(BaseStrategy):
    def _calculate_atr(self, data, period=14):
        high = data['high']
        low = data['low']
        close = data['close'].shift(1)
        
        tr_list = []
        for i in range(len(data)):
             if i == 0:
                 tr_list.append(high.iloc[i] - low.iloc[i])
             else:
                 h = high.iloc[i]
                 l = low.iloc[i]
                 pc = close.iloc[i]
                 tr_list.append(max(h - l, abs(h - pc), abs(l - pc)))
                 
        tr_series = pd.Series(tr_list, index=data.index)
        return tr_series.rolling(window=period).mean()

    def generate_signal(self, market_data: pd.DataFrame, position_data: dict) -> dict:
        # Default Hold
        signal = {'action': 'hold', 'reason': 'Waiting'}
        
        # Params
        trend_period = self.params.get('trend_window', 50)
        fast_period = self.params.get('short_window', 12)
        slow_period = self.params.get('long_window', 24)
        atr_period = 14

        if len(market_data) < max(trend_period, slow_period, atr_period) + 2:
            return signal

        # Indicators
        closes = market_data['close']
        sma_trend = closes.rolling(window=trend_period).mean()
        sma_fast = closes.rolling(window=fast_period).mean()
        sma_slow = closes.rolling(window=slow_period).mean()
        atr = self._calculate_atr(market_data, atr_period)

        current_price = closes.iloc[-1]
        current_atr = atr.iloc[-1]
        
        # --- 1. Global Risk Management Check ---
        risk_signal = self.check_risk_management(current_price, current_atr, position_data)
        if risk_signal:
            return risk_signal

        # Current Values
        curr_trend = sma_trend.iloc[-1]
        curr_fast = sma_fast.iloc[-1]
        curr_slow = sma_slow.iloc[-1]
        prev_fast = sma_fast.iloc[-2]
        prev_slow = sma_slow.iloc[-2]

        # --- 2. Entry Logic ---
        if not position_data:
            # LONG: Trend Filter (Price > 50 SMA) + Golden Cross
            if current_price > curr_trend:
                if prev_fast <= prev_slow and curr_fast > curr_slow:
                    initial_sl = current_price - (1.5 * current_atr)
                    return {
                        'action': 'buy',
                        'quantity_pct': 0.1, 
                        'stop_loss': initial_sl,
                        'reason': 'Golden Cross (Long)'
                    }
                    
            # SHORT: Trend Filter (Price < 50 SMA) + Death Cross
            elif current_price < curr_trend:
                # Fast crosses BELOW Slow
                if prev_fast >= prev_slow and curr_fast < curr_slow:
                    initial_sl = current_price + (1.5 * current_atr) # Stop Loss Above Entry
                    return {
                        'action': 'sell', # Main loop interprets SELL on Flat as OPEN SHORT
                        'quantity_pct': 0.1, 
                        'stop_loss': initial_sl,
                        'reason': 'Death Cross (Short)'
                    }

        return signal
