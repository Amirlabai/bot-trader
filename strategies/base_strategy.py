from abc import ABC, abstractmethod

import pandas as pd

from shared.constants import (
    TP1_HIT_REASON_LONG,
    TP1_HIT_REASON_SHORT,
    TRAILED_STOP_REASON_LONG,
    TRAILED_STOP_REASON_SHORT,
    STOP_LOSS_REASON_LONG,
    STOP_LOSS_REASON_SHORT,
    tp1_already_done,
)

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

    def _stamp_atr(self, signal, current_atr, indicators=None):
        if signal is None:
            return None
        try:
            if pd.notnull(current_atr):
                signal['current_atr'] = float(current_atr)
        except (TypeError, ValueError):
            pass
        if indicators is not None:
            signal['indicators'] = indicators
        return signal

    def follow_up_risk(self, market_data, position_data, current_atr=None):
        """Re-check SL/trail on the same closed bar after a TP1 fill. Requires ATR from generate_signal."""
        if position_data is None or market_data is None or market_data.empty:
            return None
        try:
            atr = float(current_atr)
        except (TypeError, ValueError):
            return None
        if pd.isnull(atr):
            return None
        idx = self._get_closed_candle_index(market_data)
        if idx < -len(market_data):
            return None
        return self.check_risk_management(market_data.iloc[idx], atr, position_data)

    def check_risk_management(self, bar, current_atr, position_data):
        """
        Standard Risk Management (last closed bar):
        - TP1 / SL hits use high/low wicks
        - SL: Entry - 1.5 ATR
        - TP1: Entry + 1.0 ATR (Sell 50%, Moves SL to Entry)
        - Trailing updates use close (1.5 ATR)
        """
        if not position_data:
            return None

        high = float(bar['high'])
        low = float(bar['low'])
        close = float(bar['close'])
        entry_price = position_data['entry_price']
        side = position_data.get('side', 'LONG')
        is_long = side == 'LONG'
        if side not in ('LONG', 'SHORT'):
            return None
        stop_loss = position_data.get('stop_loss')
        post_tp1 = tp1_already_done(position_data)
        close_action = 'sell' if is_long else 'buy'

        if stop_loss is None:
            stop_loss = entry_price - (1.5 * current_atr) if is_long else entry_price + (1.5 * current_atr)
        tp_price = position_data.get('take_profit')
        if not tp_price or tp_price == 0.0:
            tp_price = entry_price + current_atr if is_long else entry_price - current_atr

        tp_hit = (not post_tp1) and (high >= tp_price if is_long else low <= tp_price)
        sl_hit = (low <= stop_loss) if is_long else (high >= stop_loss)

        if tp_hit:
            return {
                'action': close_action,
                'quantity_pct': 0.5,
                'stop_loss': entry_price,
                'take_profit': tp_price,
                'reason': TP1_HIT_REASON_LONG if is_long else TP1_HIT_REASON_SHORT,
            }

        if sl_hit:
            trailed = False
            if post_tp1:
                trailed = (stop_loss > entry_price) if is_long else (stop_loss < entry_price)
            if trailed:
                label = TRAILED_STOP_REASON_LONG if is_long else TRAILED_STOP_REASON_SHORT
            else:
                label = STOP_LOSS_REASON_LONG if is_long else STOP_LOSS_REASON_SHORT
            reason = f'{label} @ {stop_loss} (SL {stop_loss})'
            return {'action': close_action, 'quantity_pct': 1.0, 'reason': reason}

        if post_tp1:
            proposed_sl = close - (1.5 * current_atr) if is_long else close + (1.5 * current_atr)
            better = proposed_sl > stop_loss if is_long else proposed_sl < stop_loss
            if better:
                hold_reason = (
                    'Updating Trailing Stop (Post-TP1)'
                    if is_long else
                    'Updating Short Trailing Stop (Post-TP1)'
                )
                return {'action': 'hold', 'stop_loss': proposed_sl, 'reason': hold_reason}

        return None
