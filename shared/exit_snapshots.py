"""Close fill pricing and candle snapshots (shared by main and scratch tools)."""

from __future__ import annotations

import pandas as pd

from shared.constants import (
    reason_is_hold_label,
    reason_is_rsi_exit,
    reason_is_stop_exit,
    reason_is_tp1_exit,
    reason_is_trailed_stop,
    reason_is_trade_exit,
)

# Max candles on the chart at daily or weekly resolution. Monthly may exceed this.
SNAPSHOT_BAR_CAP = 60


def _parse_entry_ts(entry_date) -> pd.Timestamp | None:
    if entry_date is None:
        return None
    try:
        return pd.Timestamp(str(entry_date)[:10])
    except (TypeError, ValueError):
        return None


def _ohlc_frame(market_data: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in ('open', 'high', 'low', 'close') if c in market_data.columns]
    out = market_data[cols].astype(float).copy()
    idx = pd.to_datetime(out.index)
    if getattr(idx, 'tz', None) is not None:
        idx = idx.tz_convert('UTC').tz_localize(None)
    out.index = idx
    out.sort_index(inplace=True)
    return out


def _resample_ohlc(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    if df.empty:
        return df
    agg = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
    use = {k: v for k, v in agg.items() if k in df.columns}
    out = df.resample(rule).agg(use).dropna(how='any')
    return out


def _frame_from_entry(market_data: pd.DataFrame, entry_date, fallback_n: int) -> pd.DataFrame:
    """Daily bars from entry through the last bar (exit). Fallback: last fallback_n bars."""
    df = _ohlc_frame(market_data)
    if df.empty:
        return df
    entry_ts = _parse_entry_ts(entry_date)
    if entry_ts is not None:
        sliced = df.loc[df.index.normalize() >= entry_ts.normalize()]
        if not sliced.empty:
            return sliced
    n = max(1, int(fallback_n))
    return df.iloc[-n:]


def _choose_display_frame(daily: pd.DataFrame, cap: int = SNAPSHOT_BAR_CAP) -> tuple[pd.DataFrame, str]:
    """
    Prefer daily from entry→exit. If over cap, roll up to weekly; if still over, monthly.
    Monthly is allowed to exceed the cap.
    """
    if daily is None or daily.empty:
        return daily if daily is not None else pd.DataFrame(), '1d'
    if len(daily) <= cap:
        return daily, '1d'
    weekly = _resample_ohlc(daily, 'W-FRI')
    if len(weekly) <= cap:
        return weekly, '1wk'
    monthly = _resample_ohlc(daily, 'ME')
    return monthly, '1mo'


def _candles_from_frame(df: pd.DataFrame) -> list[dict]:
    candles = []
    for ts, row in df.iterrows():
        candles.append({
            'date': str(pd.Timestamp(ts))[:10],
            'open': round(float(row['open']), 8),
            'high': round(float(row['high']), 8),
            'low': round(float(row['low']), 8),
            'close': round(float(row['close']), 8),
        })
    return candles


def _slice_indicators_to_frame(indicators: dict, daily_index: pd.DatetimeIndex, display: pd.DataFrame, timeframe: str) -> dict:
    """Align indicator series to the display frame (last value in each bucket when resampled)."""
    if not indicators:
        return {}
    sliced = {}
    for key, values in indicators.items():
        if hasattr(values, 'iloc'):
            series = values.copy()
            series.index = pd.to_datetime(series.index)
            if getattr(series.index, 'tz', None) is not None:
                series.index = series.index.tz_convert('UTC').tz_localize(None)
            series = series.reindex(daily_index)
            if timeframe == '1d':
                aligned = series.reindex(display.index)
            elif timeframe == '1wk':
                aligned = series.resample('W-FRI').last().reindex(display.index)
            else:
                aligned = series.resample('ME').last().reindex(display.index)
            sliced[key] = [
                round(float(v), 8) if pd.notnull(v) else None for v in aligned
            ]
        elif isinstance(values, list) and len(values) == len(daily_index):
            series = pd.Series(values, index=daily_index)
            if timeframe == '1d':
                aligned = series.reindex(display.index)
            elif timeframe == '1wk':
                aligned = series.resample('W-FRI').last().reindex(display.index)
            else:
                aligned = series.resample('ME').last().reindex(display.index)
            sliced[key] = [
                round(float(v), 8) if pd.notnull(v) else None for v in aligned
            ]
    return sliced


def _build_candle_snapshot(
    market_data, signal_data, n=SNAPSHOT_BAR_CAP, entry_price=None, entry_date=None, pos_data=None,
    chart_levels_from_position=False, reason_override=None, bar_cap: int = SNAPSHOT_BAR_CAP,
):
    daily = _frame_from_entry(market_data, entry_date, fallback_n=n)
    display, timeframe = _choose_display_frame(daily, cap=bar_cap)
    candles = _candles_from_frame(display)

    if chart_levels_from_position and pos_data:
        sl = pos_data.get('stop_loss', 0.0)
        tp = pos_data.get('take_profit', 0.0)
    else:
        sl = signal_data.get('stop_loss')
        if (sl is None or sl == 0.0) and pos_data:
            sl = pos_data.get('stop_loss', 0.0)
        tp = signal_data.get('take_profit')
        if (tp is None or tp == 0.0) and pos_data:
            tp = pos_data.get('take_profit', 0.0)

    if entry_price is not None:
        final_entry_price = entry_price
    elif pos_data:
        final_entry_price = pos_data.get('entry_price')
    else:
        final_entry_price = None
    final_entry_date = str(entry_date)[:10] if entry_date else (pos_data.get('entry_date') if pos_data else None)

    daily_index = daily.index
    indicators = signal_data.get('indicators', {}) or {}
    try:
        full_index = _ohlc_frame(market_data).index
    except Exception:
        full_index = daily_index
    # Indicators from generate_signal are usually full-history length.
    source_index = daily_index
    aligned_indicators = indicators
    if indicators:
        sample = next(iter(indicators.values()), None)
        if hasattr(sample, '__len__') and len(sample) == len(full_index):
            source_index = full_index
            if final_entry_date:
                entry_ts = _parse_entry_ts(final_entry_date)
                if entry_ts is not None:
                    source_index = full_index[full_index.normalize() >= entry_ts.normalize()]
            aligned_indicators = {}
            for key, values in indicators.items():
                if hasattr(values, 'iloc'):
                    series = values.copy()
                    series.index = pd.to_datetime(full_index)
                    aligned_indicators[key] = series.reindex(source_index)
                elif isinstance(values, list) and len(values) == len(full_index):
                    aligned_indicators[key] = pd.Series(values, index=full_index).reindex(source_index)
    sliced_indicators = _slice_indicators_to_frame(
        aligned_indicators, source_index, display, timeframe,
    )

    display_reason = reason_override if reason_override is not None else signal_data.get('reason', '')
    return {
        'candles': candles,
        'timeframe': timeframe,
        'bar_cap': bar_cap,
        'stop_loss': sl,
        'take_profit': tp,
        'indicators': sliced_indicators,
        'reason': display_reason,
        'entry_price': final_entry_price,
        'entry_date': final_entry_date,
    }


def _classify_exit_kind(signal_data: dict, pos_data: dict, close_reason: str = None) -> str:
    reason = close_reason or signal_data.get('reason', '') or ''
    pct = clamp_quantity_pct(signal_data.get('quantity_pct', 1.0))
    if reason_is_tp1_exit(reason) and pct < 1.0:
        return 'tp1_partial'
    if reason_is_trailed_stop(reason):
        return 'trailed_stop'
    if reason_is_stop_exit(reason) or reason_is_rsi_exit(reason):
        return 'stop_loss'
    return 'other'


def build_close_snapshot(
    market_data, signal_data, pos_data, fill_price, close_reason=None, n=SNAPSHOT_BAR_CAP,
    bar_cap: int = SNAPSHOT_BAR_CAP,
):
    if not pos_data:
        pos_data = {}
    entry_price = pos_data.get('entry_price')
    entry_date = pos_data.get('entry_date')
    pct = clamp_quantity_pct(signal_data.get('quantity_pct', 1.0))
    effective_reason = close_reason or ''

    snap = _build_candle_snapshot(
        market_data, signal_data, n=n,
        entry_price=entry_price, entry_date=entry_date, pos_data=pos_data,
        chart_levels_from_position=True,
        reason_override=effective_reason,
        bar_cap=bar_cap,
    )
    sl_at_exit = float(pos_data.get('stop_loss') or 0)
    tp_at_exit = float(pos_data.get('take_profit') or 0)
    snap['stop_loss'] = sl_at_exit
    snap['take_profit'] = tp_at_exit
    snap['stop_loss_at_exit'] = sl_at_exit
    snap['take_profit_at_exit'] = tp_at_exit
    snap['exit_kind'] = _classify_exit_kind(signal_data, pos_data, close_reason=effective_reason)
    snap['quantity_pct'] = pct
    snap['exit_price'] = fill_price
    exit_date = last_bar_date(market_data)
    if exit_date:
        snap['exit_date'] = exit_date
    if effective_reason:
        snap['reason'] = effective_reason
    return snap


def build_open_snapshot(
    market_data, pos_data, n=SNAPSHOT_BAR_CAP, bar_cap: int = SNAPSHOT_BAR_CAP,
):
    """Entry→now candle snapshot for an open position (dashboard expand chart)."""
    if not pos_data:
        pos_data = {}
    entry_price = pos_data.get('entry_price')
    entry_date = pos_data.get('entry_date')
    snap = _build_candle_snapshot(
        market_data, {}, n=n,
        entry_price=entry_price, entry_date=entry_date, pos_data=pos_data,
        chart_levels_from_position=True,
        reason_override='Open',
        bar_cap=bar_cap,
    )
    sl = float(pos_data.get('stop_loss') or 0)
    tp = float(pos_data.get('take_profit') or 0)
    snap['stop_loss'] = sl
    snap['take_profit'] = tp
    snap['stop_loss_at_exit'] = sl
    snap['take_profit_at_exit'] = tp
    snap['exit_kind'] = 'open'
    snap['quantity_pct'] = None
    if market_data is not None and not market_data.empty:
        snap['exit_price'] = bar_close_price(market_data)
        snap['exit_date'] = last_bar_date(market_data)
    snap['reason'] = 'Open'
    return snap


def last_bar_date(market_data):
    if market_data is None or market_data.empty:
        return None
    return str(market_data.index[-1])[:10]


def bar_close_price(market_data) -> float:
    return float(market_data['close'].iloc[-1])


def is_stop_or_trail_reason(reason: str) -> bool:
    return reason_is_stop_exit(reason) or reason_is_trailed_stop(reason)


def _level_price(signal_data, pos_data, key):
    raw = signal_data.get(key) if signal_data else None
    if raw is None or raw == 0:
        raw = pos_data.get(key) if pos_data else None
    try:
        value = float(raw or 0)
    except (TypeError, ValueError):
        return 0.0
    return value if value > 0 else 0.0


def _execution_price(bar_close, signal_data, pos_data):
    reason = signal_data.get('reason', '') or ''
    if reason_is_tp1_exit(reason):
        tp = _level_price(signal_data, pos_data, 'take_profit')
        if tp > 0:
            return tp
        return float(bar_close)
    if not pos_data or not is_stop_or_trail_reason(reason):
        return float(bar_close)
    sl = _level_price(signal_data, pos_data, 'stop_loss')
    if sl > 0:
        return sl
    return float(bar_close)


def resolve_close_fill_price(bar_close, signal_data, pos_data, fallback_reason=None):
    reason = signal_data.get('reason', '') or fallback_reason or ''
    if reason_is_hold_label(reason) and fallback_reason:
        reason = fallback_reason
    ctx = {**signal_data, 'reason': reason}
    return _execution_price(bar_close, ctx, pos_data)


def _pnl_for_close(position_side, quantity, entry_price, fill_price):
    qty = float(quantity)
    entry = float(entry_price)
    fill = float(fill_price)
    if position_side == 'LONG':
        return qty * (fill - entry)
    return qty * (entry - fill)


def _cash_delta_for_fill_change(position_side, quantity, old_fill, new_fill):
    qty = float(quantity)
    if position_side == 'LONG':
        return qty * (new_fill - old_fill)
    return qty * (old_fill - new_fill)


def apply_close_fill_to_event(event, position_side, fill_price, entry_price=None):
    entry = float(entry_price if entry_price is not None else event.get('entry_price', event['price']))
    qty = float(event['quantity'])
    old_fill = float(event['price'])
    fill = float(fill_price)
    event['entry_price'] = entry
    event['price'] = fill
    event['total_value'] = qty * fill
    event['pnl'] = _pnl_for_close(position_side, qty, entry, fill)
    return _cash_delta_for_fill_change(position_side, qty, old_fill, fill)


def reason_with_fill(signal_data, fill_price):
    """Rewrite stop/trail reason so ledger shows actual fill price."""
    reason = signal_data.get('reason', '') or ''
    fill = round(float(fill_price), 4)
    for prefix in ('Stop Loss Hit @', 'Short Stop Loss Hit @', 'Trailed Stop Hit @', 'Short Trailed Stop Hit @'):
        if prefix in reason:
            sl_marker = '(SL '
            sl_idx = reason.find(sl_marker)
            label = reason.split('@')[0].strip()
            if sl_idx == -1:
                return f'{label} @ {fill}'
            sl_tail = reason[sl_idx + len(sl_marker):].rstrip(')')
            try:
                sl_val = round(float(sl_tail.strip().split()[0]), 4)
            except (TypeError, ValueError):
                sl_val = fill
            return f'{label} @ {fill} (SL {sl_val})'
    return reason


def resolve_close_reason(signal_data, fill_price, ledger_reason=None):
    """
    Pick the close reason to store on ledger rows.

    Never return hold labels (Waiting/Neutral). Prefer the live exit signal; else keep
    the existing ledger reason; else fill-adjusted stop/trail text.
    """
    from_signal = reason_with_fill(signal_data, fill_price)
    if reason_is_trade_exit(from_signal):
        return from_signal

    prior = ledger_reason or ''
    if reason_is_trade_exit(prior):
        return reason_with_fill({'reason': prior}, fill_price)

    if from_signal and not reason_is_hold_label(from_signal):
        return from_signal
    return prior


def clamp_quantity_pct(pct, default=1.0):
    try:
        v = float(pct)
    except (TypeError, ValueError):
        return default
    if v <= 0:
        return default
    return min(1.0, v)
