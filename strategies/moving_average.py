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
        """
        - Trend: Price > 50 SMA (Bullish) or Price < 50 SMA (Bearish). Long only for now if trend is bullish.
        - Entry: 12 SMA > 24 SMA (Crossover).
        - Exit:
            - SL: Entry - 1.5 * ATR
            - TP1: Entry + 1.0 * ATR (Sell 50%, Move SL to Entry)
            - Trailing: If Price > Entry + 1.0 ATR, SL = Price - 1.0 ATR (Simple Trailing)
        """
        # Default Hold
        signal = {'action': 'hold', 'reason': 'Waiting'}
        
        # Params
        trend_period = 50
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
        
        # Current Values
        curr_trend = sma_trend.iloc[-1]
        curr_fast = sma_fast.iloc[-1]
        curr_slow = sma_slow.iloc[-1]
        
        # Previous Values (for crossover)
        prev_fast = sma_fast.iloc[-2]
        prev_slow = sma_slow.iloc[-2]

        # --- Position Management Logic ---
        if position_data:
            entry_price = position_data['entry_price']
            stop_loss = position_data.get('stop_loss', entry_price - (1.5 * current_atr))
            tp1_hit = position_data.get('tp1_hit', False)
            qty = position_data['qty']

            # 1. Check Stop Loss
            if current_price <= stop_loss:
                return {
                    'action': 'sell',
                    'quantity_pct': 1.0,
                    'reason': f'Stop Loss Hit @ {current_price} (SL {stop_loss})'
                }

            # 2. Check TP1 (Sell Half)
            tp1_price = entry_price + (1.0 * current_atr) # Fixed TP based on Entry ATR? Or Current? user said "sell half at 1 atr"
            # Ideally TP is based on ATR at entry, but we didn't store Entry ATR. Using current ATR is a proxy.
            # Or better: Sell if PnL > 1.0 ATR (relative to price)
            
            # Let's assume user meant: Gain >= 1 * ATR value
            if not tp1_hit:
                 if current_price >= (entry_price + current_atr): # Or fixed price target
                     return {
                         'action': 'sell',
                         'quantity_pct': 0.5,
                         'stop_loss': entry_price, # Move SL to Entry (Breakeven)
                         'reason': 'TP1 Hit: Selling Half, SL to Breakeven'
                     }

            # 3. Trailing Stop Logic (Active after TP1 or generally?)
            # User: "then trailing stop". Implies after TP1.
            if tp1_hit:
                # Simple Trailing: Stop is always 1 ATR below current price? Or tightens? 
                # "1.5 ATR trailing" or "1 ATR trailing"?
                # Let's use 1.5 ATR trailing to allow room, or user's 1.5 ATR initial implied volatility.
                # User's text: "stop loss is 1.5 atr... sell half at 1 atr... then trailing stop"
                # I'll assume trailing width is same as initial or tighter. Let's use 1.0 ATR trail to lock profit.
                proposed_sl = current_price - (1.5 * current_atr)
                
                if proposed_sl > stop_loss:
                    return {
                        'action': 'hold', # No trade, just update SL
                        'stop_loss': proposed_sl,
                        'reason': 'Updating Trailing Stop'
                    }

        # --- Entry Logic ---
        else:
            # 1. Trend Filter: Price > 50 SMA (for Long)
            if current_price > curr_trend:
                # 2. Crossover: Fast crosses above Slow
                if prev_fast <= prev_slow and curr_fast > curr_slow:
                    # Entry
                    initial_sl = current_price - (1.5 * current_atr)
                    return {
                        'action': 'buy',
                        'quantity_pct': 0.1, # 10% of cash
                        'stop_loss': initial_sl,
                        'reason': 'Trend Follow Crossover'
                    }

        return signal
