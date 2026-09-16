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

    def _ema(self, series: pd.Series, span: int) -> pd.Series:
        return series.ewm(span=span, adjust=False).mean()

    def _calculate_atr(self, data, period=14):
        high = data['high']
        low = data['low']
        prev_close = data['close'].shift(1)
        tr = pd.concat(
            [
                (high - low),
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        tr.iloc[0] = high.iloc[0] - low.iloc[0]
        return tr.rolling(window=period).mean()

    def _wilder_smooth(self, series: pd.Series, period: int) -> pd.Series:
        """Wilder RMA: first value = SMA of first `period` bars, then RMA."""
        values = series.astype(float).tolist()
        out = [float('nan')] * len(values)
        if len(values) < period:
            return pd.Series(out, index=series.index)
        seed = sum(values[:period]) / period
        out[period - 1] = seed
        for i in range(period, len(values)):
            out[i] = (out[i - 1] * (period - 1) + values[i]) / period
        return pd.Series(out, index=series.index)

    def _calculate_adx(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Average Directional Index (Wilder). ATR used elsewhere stays SMA-of-TR."""
        high = data['high'].astype(float)
        low = data['low'].astype(float)
        close = data['close'].astype(float)

        up_move = high.diff()
        down_move = -low.diff()
        plus_dm = pd.Series(0.0, index=data.index)
        minus_dm = pd.Series(0.0, index=data.index)
        plus_dm[(up_move > down_move) & (up_move > 0)] = up_move
        minus_dm[(down_move > up_move) & (down_move > 0)] = down_move

        prev_close = close.shift(1)
        tr = pd.concat(
            [
                (high - low),
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        tr.iloc[0] = high.iloc[0] - low.iloc[0]

        atr_w = self._wilder_smooth(tr, period)
        plus_dm_s = self._wilder_smooth(plus_dm, period)
        minus_dm_s = self._wilder_smooth(minus_dm, period)

        plus_di = 100.0 * (plus_dm_s / atr_w)
        minus_di = 100.0 * (minus_dm_s / atr_w)
        di_sum = plus_di + minus_di
        dx = 100.0 * (plus_di - minus_di).abs() / di_sum.replace(0, pd.NA)
        return self._wilder_smooth(dx.fillna(0.0), period)

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
        - SL: Entry - sl_atr ATR (default 1.5)
        - TP1: Entry + 1.0 ATR (Sell 50%, Moves SL to Entry) unless skip_tp1 / trail_from_entry
        - Trailing updates use close − trail_atr × ATR frozen at entry (fallback: live ATR)
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
        sl_atr = float(self.params.get('sl_atr', 1.5))
        trail_atr = float(self.params.get('trail_atr', 1.5))
        trail_from_entry = bool(self.params.get('trail_from_entry', False))
        skip_tp1 = bool(self.params.get('skip_tp1', False)) or trail_from_entry
        use_trailing = bool(self.params.get('use_trailing', True))
        trail_ref_atr = self._trail_reference_atr(position_data, current_atr, sl_atr, is_long)

        if stop_loss is None:
            stop_loss = entry_price - (sl_atr * current_atr) if is_long else entry_price + (sl_atr * current_atr)
        tp_price = position_data.get('take_profit')
        if not tp_price or tp_price == 0.0:
            tp_price = entry_price + current_atr if is_long else entry_price - current_atr

        tp_hit = (
            (not skip_tp1)
            and (not post_tp1)
            and (high >= tp_price if is_long else low <= tp_price)
        )
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
            elif trail_from_entry:
                init_sl = position_data.get('initial_stop_loss')
                if init_sl is not None:
                    trailed = (
                        float(stop_loss) > float(init_sl)
                        if is_long else
                        float(stop_loss) < float(init_sl)
                    )
            if trailed:
                label = TRAILED_STOP_REASON_LONG if is_long else TRAILED_STOP_REASON_SHORT
            else:
                label = STOP_LOSS_REASON_LONG if is_long else STOP_LOSS_REASON_SHORT
            reason = f'{label} @ {round(float(stop_loss), 4)} (SL {round(float(stop_loss), 4)})'
            return {'action': close_action, 'quantity_pct': 1.0, 'reason': reason}

        if use_trailing and (post_tp1 or trail_from_entry):
            trail_arm_r = float(self.params.get('trail_arm_r', 0) or 0)
            trail_armed = True
            if trail_from_entry and not post_tp1 and trail_arm_r > 0:
                init_sl = position_data.get('initial_stop_loss')
                if init_sl is not None:
                    if is_long:
                        init_rps = float(entry_price) - float(init_sl)
                        unrealized_r = (close - float(entry_price)) / init_rps if init_rps > 0 else 0.0
                    else:
                        init_rps = float(init_sl) - float(entry_price)
                        unrealized_r = (float(entry_price) - close) / init_rps if init_rps > 0 else 0.0
                    trail_armed = unrealized_r >= trail_arm_r
                if not trail_armed:
                    return None
            proposed_sl = (
                close - (trail_atr * trail_ref_atr)
                if is_long else
                close + (trail_atr * trail_ref_atr)
            )
            better = proposed_sl > stop_loss if is_long else proposed_sl < stop_loss
            if better:
                if trail_from_entry and not post_tp1:
                    hold_reason = (
                        'Updating Trailing Stop (From Entry)'
                        if is_long else
                        'Updating Short Trailing Stop (From Entry)'
                    )
                else:
                    hold_reason = (
                        'Updating Trailing Stop (Post-TP1)'
                        if is_long else
                        'Updating Short Trailing Stop (Post-TP1)'
                    )
                return {'action': 'hold', 'stop_loss': proposed_sl, 'reason': hold_reason}

        return None

    @staticmethod
    def _trail_reference_atr(position_data, current_atr, sl_atr, is_long) -> float:
        """ATR used for trail distance: prefer entry freeze, else derive from initial SL."""
        stored = position_data.get('entry_atr')
        if stored is not None:
            try:
                v = float(stored)
                if v > 0:
                    return v
            except (TypeError, ValueError):
                pass
        init_sl = position_data.get('initial_stop_loss')
        entry = position_data.get('entry_price')
        if init_sl is not None and entry is not None and float(sl_atr) > 0:
            if is_long:
                derived = (float(entry) - float(init_sl)) / float(sl_atr)
            else:
                derived = (float(init_sl) - float(entry)) / float(sl_atr)
            if derived > 0:
                return derived
        return float(current_atr)
