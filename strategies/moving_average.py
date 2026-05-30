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

        # Data provided by DataFetcher is now guaranteed to be closed candles only.
        closed_data = market_data

        if len(closed_data) < max(trend_period, slow_period, atr_period) + 2:
            return signal

        # Indicators (Calculated on CLOSED data only)
        closes = closed_data['close']
        sma_trend = closes.rolling(window=trend_period).mean()
        sma_fast = closes.rolling(window=fast_period).mean()
        sma_slow = closes.rolling(window=slow_period).mean()
        atr = self._calculate_atr(closed_data, atr_period)
        
        # Indicators for snapshot
        indicators = {
            'sma_trend': sma_trend,
            'sma_fast': sma_fast,
            'sma_slow': sma_slow
        }

        # Execution Values (Real-time from original market_data)
        current_price = market_data['close'].iloc[-1]
        current_atr = atr.iloc[-1] 
        
        # --- 1. Global Risk Management Check ---
        risk_signal = self.check_risk_management(current_price, current_atr, position_data)
        if risk_signal:
            risk_signal['indicators'] = indicators
            return risk_signal

        # Signal Values (Operate on last row of CLOSED data)
        signal_trend = sma_trend.iloc[-1]
        signal_fast = sma_fast.iloc[-1]
        signal_slow = sma_slow.iloc[-1]
        prev_signal_fast = sma_fast.iloc[-2]
        prev_signal_slow = sma_slow.iloc[-2]
        signal_price = closes.iloc[-1]

        # --- 2. Entry Logic ---
        if not position_data:
            if signal_price > signal_trend:
                if prev_signal_fast <= prev_signal_slow and signal_fast > signal_slow:
                    initial_sl = current_price - (1.5 * current_atr)
                    initial_tp = current_price + (1.0 * current_atr)
                    return {
                        'action': 'buy',
                        'stop_loss': initial_sl,
                        'take_profit': initial_tp,
                        'indicators': indicators,
                        'reason': 'Golden Cross (Confirmed Close)'
                    }
                    
            elif signal_price < signal_trend:
                if prev_signal_fast >= prev_signal_slow and signal_fast < signal_slow:
                    initial_sl = current_price + (1.5 * current_atr)
                    initial_tp = current_price - (1.0 * current_atr)

                    return {
                        'action': 'sell',
                        'stop_loss': initial_sl,
                        'take_profit': initial_tp,
                        'indicators': indicators,
                        'reason': 'Death Cross (Short)'
                    }

        signal['indicators'] = indicators
        return signal
