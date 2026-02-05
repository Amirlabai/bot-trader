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

    def _get_closed_candle_index(self, data: pd.DataFrame) -> int:
        """
        Determines the index of the last CLOSED candle.
        - If last timestamp is Today (UTC), assume it's Open/Incomplete -> Use -2 (Yesterday).
        - If last timestamp is Before Today, assume it's Closed -> Use -1.
        """
        if data.empty:
            return -1
        
        last_ts = data.index[-1]
        today = pd.Timestamp.utcnow().normalize()
        
        # Ensure last_ts is timezone-aware for comparison, or normalize both if naive.
        if last_ts.tzinfo is None:
            last_ts = last_ts.replace(tzinfo=pd.Timestamp.utcnow().tzinfo)
        
        # Normalize to date (remove time)
        last_date = last_ts.normalize()
        
        if last_date == today:
            # The last candle is from Today (Open/Incomplete)
            return -2
        else:
            # The last candle is from Yesterday or earlier (Closed)
            return -1

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
        side = position_data.get('side', 'LONG')
        stop_loss = position_data.get('stop_loss')
        tp1_hit = position_data.get('tp1_hit', False)

        # --- LONG LOGIC ---
        if side == 'LONG':
             if not stop_loss: stop_loss = entry_price - (1.5 * current_atr)
             
             # Hard SL
             if current_price <= stop_loss:
                 return {'action': 'sell', 'quantity_pct': 1.0, 'reason': f'Stop Loss Hit @ {current_price} (SL {stop_loss})'}
             
             # TP1
             if not tp1_hit and current_price >= (entry_price + current_atr):
                 # TP1 Hit: Sell 50%, Move SL to Entry
                 return {
                     'action': 'sell', 
                     'quantity_pct': 0.5, 
                     'stop_loss': entry_price, 
                     'reason': 'TP1 Hit' # Main loop looks for "TP1" string
                 }
            
             # Trailing (ONLY AFTER TP1)
             if tp1_hit:
                 proposed_sl = current_price - (1.5 * current_atr)
                 if proposed_sl > stop_loss:
                     return {'action': 'hold', 'stop_loss': proposed_sl, 'reason': 'Updating Trailing Stop (Post-TP1)'}

        # --- SHORT LOGIC ---
        elif side == 'SHORT':
             if not stop_loss: stop_loss = entry_price + (1.5 * current_atr)
             
             # Hard SL (Price went UP)
             if current_price >= stop_loss:
                 return {'action': 'buy', 'quantity_pct': 1.0, 'reason': f'Short Stop Loss Hit @ {current_price} (SL {stop_loss})'}
             
             # TP1 (Price went DOWN by 1 ATR)
             if not tp1_hit and current_price <= (entry_price - current_atr):
                 return {
                     'action': 'buy', 
                     'quantity_pct': 0.5, 
                     'stop_loss': entry_price, 
                     'reason': 'Short TP1 Hit' # Main loop looks for "TP1" string
                 }
            
             # Trailing (ONLY AFTER TP1)
             if tp1_hit:
                 proposed_sl = current_price + (1.5 * current_atr)
                 if proposed_sl < stop_loss:
                     return {'action': 'hold', 'stop_loss': proposed_sl, 'reason': 'Updating Short Trailing Stop (Post-TP1)'}
            
        return None
