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
        atr_period = 14
        
        # Default signal
        signal = {'action': 'hold', 'reason': 'Neutral'}

        if len(market_data) < max(period, atr_period) + 1:
            return signal

        # Data provided by DataFetcher is now guaranteed to be closed candles only.
        closed_data = market_data

        # Indicators (Calculated on CLOSED data)
        atr = self._calculate_atr(closed_data, atr_period)
        current_atr = atr.iloc[-1]
        
        # Execution Price (Real-time)
        current_price = market_data['close'].iloc[-1]

        # --- 1. Global Risk Management Check ---
        risk_signal = self.check_risk_management(market_data.iloc[-1], current_atr, position_data)
        
        # Calculate RSI on Closed Data
        rsi_series = self._calculate_rsi(closed_data['close'], period)
        current_rsi = rsi_series.iloc[-1] 
        
        # Prepare indicators for snapshot
        indicators = {'rsi': rsi_series}

        if risk_signal:
            return self._stamp_atr(risk_signal, current_atr, indicators)

        if current_rsi < oversold:
            if not position_data:
                initial_sl = current_price - (1.5 * current_atr)
                initial_tp = current_price + (1.0 * current_atr)
                return self._stamp_atr({
                    'action': 'buy',
                    'stop_loss': initial_sl,
                    'take_profit': initial_tp,
                    'reason': f'RSI Oversold ({current_rsi:.2f}) - Long',
                    'is_entry': True,
                }, current_atr, indicators)
            elif position_data.get('side') == 'SHORT':
                return self._stamp_atr({
                    'action': 'buy',
                    'quantity_pct': 1.0,
                    'reason': f'RSI Oversold ({current_rsi:.2f}) - Cover Short'
                }, current_atr, indicators)

        elif current_rsi > overbought:
            if not position_data:
                initial_sl = current_price + (1.5 * current_atr)
                initial_tp = current_price - (1.0 * current_atr)
                return self._stamp_atr({
                    'action': 'sell',
                    'stop_loss': initial_sl,
                    'take_profit': initial_tp,
                    'reason': f'RSI Overbought ({current_rsi:.2f}) - Short',
                    'is_entry': True,
                }, current_atr, indicators)
            elif position_data.get('side') == 'LONG':
                return self._stamp_atr({
                    'action': 'sell',
                    'quantity_pct': 1.0,
                    'reason': f'RSI Overbought ({current_rsi:.2f}) - Close Long'
                }, current_atr, indicators)

        return self._stamp_atr(signal, current_atr, indicators)
