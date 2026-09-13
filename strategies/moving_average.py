from .base_strategy import BaseStrategy
import pandas as pd

class MovingAverageStrategy(BaseStrategy):
    def generate_signal(self, market_data: pd.DataFrame, position_data: dict) -> dict:
        # Default Hold
        signal = {'action': 'hold', 'reason': 'Waiting'}
        
        # Params
        trend_period = self.params.get('trend_window', 50)
        fast_period = self.params.get('short_window', 12)
        slow_period = self.params.get('long_window', 24)
        base_period = int(self.params.get('base_window', 0) or 0)
        atr_period = int(self.params.get('atr_period', 14) or 14)
        adx_period = self.params.get('adx_period', 14)
        adx_min = self.params.get('adx_min', 16)
        vol_ma_period = self.params.get('vol_ma_period', 20)
        vol_mult = self.params.get('vol_mult', 0.85)
        atr_buffer = self.params.get('atr_buffer', 0.05)
        long_only = bool(self.params.get('long_only', False))
        trend_exit = bool(self.params.get('trend_exit', False))
        trend_exit_death_cross = bool(self.params.get('trend_exit_death_cross', True))
        trend_exit_macro = bool(self.params.get('trend_exit_macro', False))
        trail_from_entry = bool(self.params.get('trail_from_entry', False))
        skip_tp1 = bool(self.params.get('skip_tp1', False)) or trail_from_entry
        sl_atr = float(self.params.get('sl_atr', 1.5))
        trend_slope_bars = int(self.params.get('trend_slope_bars', 0) or 0)
        reclaim_lookback = int(self.params.get('reclaim_lookback', 0) or 0)
        macro_ema_window = int(self.params.get('macro_ema_window', 0) or 0)

        # Data provided by DataFetcher is now guaranteed to be closed candles only.
        closed_data = market_data

        min_bars = max(
            trend_period,
            slow_period,
            base_period,
            atr_period,
            adx_period * 2,
            vol_ma_period,
            trend_slope_bars + 1,
            reclaim_lookback + 1,
            macro_ema_window,
        ) + 2
        if len(closed_data) < min_bars:
            return signal

        # Indicators (Calculated on CLOSED data only)
        closes = closed_data['close']
        ema_trend = self._ema(closes, trend_period)
        ema_fast = self._ema(closes, fast_period)
        ema_slow = self._ema(closes, slow_period)
        ema_base = self._ema(closes, base_period) if base_period > 0 else None
        ema_macro = self._ema(closes, macro_ema_window) if macro_ema_window > 0 else None
        atr = self._calculate_atr(closed_data, atr_period)
        adx = self._calculate_adx(closed_data, adx_period)
        vol_ma = closed_data['volume'].rolling(window=vol_ma_period).mean()
        
        # Indicators for snapshot
        indicators = {
            'ema_trend': ema_trend,
            'ema_fast': ema_fast,
            'ema_slow': ema_slow,
            'adx': adx,
        }
        if ema_base is not None:
            indicators['ema_base'] = ema_base
        if ema_macro is not None:
            indicators['ema_macro'] = ema_macro

        # Execution Values (Real-time from original market_data)
        current_price = market_data['close'].iloc[-1]
        current_atr = atr.iloc[-1] 
        
        # --- 1. Global Risk Management Check ---
        risk_signal = self.check_risk_management(market_data.iloc[-1], current_atr, position_data)
        if risk_signal:
            return self._stamp_atr(risk_signal, current_atr, indicators)

        # Signal Values (Operate on last row of CLOSED data)
        signal_trend = ema_trend.iloc[-1]
        signal_fast = ema_fast.iloc[-1]
        signal_slow = ema_slow.iloc[-1]
        prev_signal_fast = ema_fast.iloc[-2]
        prev_signal_slow = ema_slow.iloc[-2]
        signal_price = closes.iloc[-1]
        signal_adx = adx.iloc[-1]
        signal_vol = closed_data['volume'].iloc[-1]
        signal_vol_ma = vol_ma.iloc[-1]
        signal_macro = ema_macro.iloc[-1] if ema_macro is not None else None
        signal_base = ema_base.iloc[-1] if ema_base is not None else None

        if pd.isnull(current_atr):
            return self._stamp_atr(signal, current_atr, indicators)
        if float(adx_min) > 0 and pd.isnull(signal_adx):
            return self._stamp_atr(signal, current_atr, indicators)
        if float(vol_mult) > 0 and pd.isnull(signal_vol_ma):
            return self._stamp_atr(signal, current_atr, indicators)
        if macro_ema_window > 0 and pd.isnull(signal_macro):
            return self._stamp_atr(signal, current_atr, indicators)
        if base_period > 0 and pd.isnull(signal_base):
            return self._stamp_atr(signal, current_atr, indicators)

        crossover_long = prev_signal_fast <= prev_signal_slow and signal_fast > signal_slow
        crossover_short = prev_signal_fast >= prev_signal_slow and signal_fast < signal_slow
        adx_ok = True if float(adx_min) <= 0 else signal_adx > adx_min
        # Yahoo forex volume is typically all zeros; skip volume gate when unusable.
        if float(vol_mult) <= 0:
            volume_ok = True
        elif pd.isnull(signal_vol_ma) or float(signal_vol_ma) <= 0:
            volume_ok = True
        else:
            volume_ok = signal_vol > (vol_mult * signal_vol_ma)
        separation_ok = abs(signal_fast - signal_slow) >= (atr_buffer * current_atr)

        base_ok = True
        if base_period > 0:
            # Base filter: price above base EMA (e.g. EMA50). Optional stack: EMA20 > EMA50.
            require_stack = bool(self.params.get('base_require_stack', False))
            base_ok = float(signal_price) > float(signal_base)
            if base_ok and require_stack:
                base_ok = float(signal_slow) > float(signal_base)

        slope_ok = True
        if trend_slope_bars > 0 and len(ema_trend) > trend_slope_bars:
            prior_trend = ema_trend.iloc[-1 - trend_slope_bars]
            if pd.isnull(prior_trend):
                slope_ok = False
            else:
                slope_ok = float(signal_trend) > float(prior_trend)

        reclaim_ok = True
        if reclaim_lookback > 0:
            look = closes.iloc[-(reclaim_lookback + 1):-1]
            if macro_ema_window > 0 and ema_macro is not None:
                look_level = ema_macro.iloc[-(reclaim_lookback + 1):-1]
            else:
                look_level = ema_trend.iloc[-(reclaim_lookback + 1):-1]
            was_below = (look < look_level).fillna(False).any()
            reclaim_ok = bool(was_below)

        macro_ok = True
        if macro_ema_window > 0:
            macro_ok = float(signal_price) > float(signal_macro)
            if macro_ok and trend_slope_bars > 0 and len(ema_macro) > trend_slope_bars:
                prior_macro = ema_macro.iloc[-1 - trend_slope_bars]
                if pd.isnull(prior_macro):
                    macro_ok = False
                else:
                    macro_ok = float(signal_macro) > float(prior_macro)

        # --- 2. Trend invalidation (long runner) ---
        if (
            trend_exit
            and position_data
            and position_data.get('side', 'LONG') == 'LONG'
        ):
            exit_level = signal_trend
            exit_label = 'close below trend EMA'
            if trend_exit_macro and ema_macro is not None and not pd.isnull(signal_macro):
                exit_level = signal_macro
                exit_label = f'close below EMA{macro_ema_window}'
            below_trend = signal_price < exit_level
            death_exit = trend_exit_death_cross and crossover_short
            if death_exit or below_trend:
                reason = (
                    'Trend exit: death cross'
                    if death_exit and crossover_short else
                    f'Trend exit: {exit_label}'
                )
                return self._stamp_atr({
                    'action': 'sell',
                    'quantity_pct': 1.0,
                    'reason': reason,
                }, current_atr, indicators)

        # --- 3. Entry Logic ---
        if not position_data:
            if (
                crossover_long
                and signal_price > signal_trend
                and adx_ok
                and volume_ok
                and separation_ok
                and base_ok
                and slope_ok
                and reclaim_ok
                and macro_ok
            ):
                initial_sl = current_price - (sl_atr * current_atr)
                signal_out = {
                    'action': 'buy',
                    'stop_loss': initial_sl,
                    'reason': 'Golden Cross + filters',
                    'is_entry': True,
                }
                if not skip_tp1:
                    signal_out['take_profit'] = current_price + (1.0 * current_atr)
                else:
                    signal_out['take_profit'] = 0.0
                    signal_out['reason'] = 'Big-move long: cross + EMA200/reclaim'
                return self._stamp_atr(signal_out, current_atr, indicators)

            if (
                not long_only
                and crossover_short
                and signal_price < signal_trend
                and adx_ok
                and volume_ok
                and separation_ok
            ):
                initial_sl = current_price + (sl_atr * current_atr)
                initial_tp = current_price - (1.0 * current_atr)

                return self._stamp_atr({
                    'action': 'sell',
                    'stop_loss': initial_sl,
                    'take_profit': initial_tp,
                    'reason': 'Death Cross + ADX/vol/trend',
                    'is_entry': True,
                }, current_atr, indicators)

        return self._stamp_atr(signal, current_atr, indicators)


class CachedMovingAverageStrategy(MovingAverageStrategy):
    """Resim/tune helper: slice precomputed EMA/ATR/ADX from a full-history cache."""

    def bind_cache(self, cache: dict):
        self._ind_cache = cache

    def _ema(self, series: pd.Series, span: int) -> pd.Series:
        n = len(series)
        short = self.params.get('short_window', 12)
        long = self.params.get('long_window', 24)
        trend = self.params.get('trend_window', 50)
        base = int(self.params.get('base_window', 0) or 0)
        macro = int(self.params.get('macro_ema_window', 0) or 0)
        if span == short:
            return self._ind_cache['ema_fast'].iloc[:n]
        if span == long:
            return self._ind_cache['ema_slow'].iloc[:n]
        if base > 0 and span == base and 'ema_base' in self._ind_cache:
            return self._ind_cache['ema_base'].iloc[:n]
        if macro > 0 and span == macro and 'ema_macro' in self._ind_cache:
            return self._ind_cache['ema_macro'].iloc[:n]
        if span == trend:
            return self._ind_cache['ema_trend'].iloc[:n]
        return self._ind_cache['ema_trend'].iloc[:n]

    def _calculate_atr(self, data, period=14):
        return self._ind_cache['atr'].iloc[: len(data)]

    def _calculate_adx(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        return self._ind_cache['adx'].iloc[: len(data)]
