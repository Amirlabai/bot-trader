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
        """
        pass

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

    def check_risk_management(self, current_price, current_atr, position_data):
        """
        Standard Risk Management:
        - SL: Entry - 1.5 ATR
        - TP1: Entry + 1.0 ATR (Sell 50%, Moves SL to Entry)
        - Trailing: 1.5 ATR trailing stop
        """
        if not position_data:
            return None

        entry_price = position_data['entry_price']
        stop_loss = position_data.get('stop_loss')
        # If SL not set (legacy or manual), assume 1.5 ATR from entry
        if not stop_loss:
            stop_loss = entry_price - (1.5 * current_atr)

        tp1_hit = position_data.get('tp1_hit', False)
        
        # 1. Check Hard Stop Loss
        if current_price <= stop_loss:
            return {
                'action': 'sell',
                'quantity_pct': 1.0,
                'reason': f'Stop Loss Hit @ {current_price} (SL {stop_loss})'
            }
            
        # 2. Check TP1 (Sell Half) - Gain >= 1 ATR
        # Only if we haven't hit TP1 yet
        if not tp1_hit:
             if current_price >= (entry_price + current_atr):
                 return {
                     'action': 'sell',
                     'quantity_pct': 0.5,
                     'stop_loss': entry_price, # Move SL to Breakeven
                     'reason': 'TP1 Hit: Selling Half, SL to Breakeven'
                 }

        # 3. Trailing Stop Logic
        # We assume a 1.5 ATR trailing distance from HIGH water mark? 
        # Or simple "Price - 1.5 ATR"? 
        # User said: "then trailing stop". 
        # Let's use simple trailing: If (Price - 1.5 ATR) > Current SL, update SL.
        proposed_sl = current_price - (1.5 * current_atr)
        
        # Only tighten, never loosen
        if proposed_sl > stop_loss:
            return {
                'action': 'hold', # No trade, just update
                'stop_loss': proposed_sl,
                'reason': 'Updating Trailing Stop'
            }
            
        return None
