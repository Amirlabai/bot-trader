"""
Historical resimulation only — mirrors src/main.py signal handling.

Do not import from live main (main sets cwd and runs the daily session on import).
"""

import importlib
import os
import traceback

from config import RISK_SETTINGS
from shared.constants import (
    reason_is_entry_long,
    reason_is_entry_short,
)
from shared.exit_snapshots import last_bar_date
from shared.risk_sizing import size_for_risk, should_open_after_sizing
from shared.trade_exec import apply_exit


def load_strategy(module_name, class_name, params):
    try:
        module = importlib.import_module(module_name)
        strategy_class = getattr(module, class_name)
        return strategy_class(params)
    except Exception as e:
        print(f"Failed to load strategy {class_name} from {module_name}: {e}")
        return None


def asset_type_for_symbol(symbol: str) -> str:
    is_forex = (
        any(cur in symbol for cur in ['EUR', 'USD', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF'])
        and '/' in symbol
        and len(symbol) == 7
    )
    return 'forex' if is_forex else 'crypto'


def _is_entry_signal(signal_data, long=True):
    if signal_data.get('is_entry'):
        return True
    reason = signal_data.get('reason', '')
    return reason_is_entry_long(reason) if long else reason_is_entry_short(reason)


def process_symbol(
    ledger,
    strategy_id,
    symbol,
    strategy,
    market_data,
    *,
    event_ts=None,
    verbose=True,
    build_snapshots=False,
):
    """One simulated trading day for a symbol (same rules as src/main.py)."""
    if market_data.empty:
        return

    pos_data = ledger.get_position(strategy_id, symbol)

    try:
        signal_data = strategy.generate_signal(market_data, pos_data)
    except Exception as e:
        if verbose:
            print(f"    Error generating signal: {e}")
            traceback.print_exc()
        if os.getenv("BOT_TRADER_DEBUG") == "1":
            raise
        return

    action = signal_data.get('action', 'hold')
    current_price = float(market_data['close'].iloc[-1])

    if pos_data:
        ledger.update_position_price(strategy_id, symbol, current_price)

    if verbose:
        print(
            f"    Action: {action.upper()} | Reason: {signal_data.get('reason', '')} | "
            f"Price: {current_price}"
        )

    position_side = pos_data.get('side', 'LONG') if pos_data else None

    if action == 'buy':
        if position_side == 'SHORT':
            pos_data, position_side = apply_exit(
                ledger, strategy, strategy_id, symbol, market_data, pos_data,
                signal_data, position_side,
                event_ts=event_ts, build_snapshots=build_snapshots, verbose=verbose,
            )

        if position_side is None and _is_entry_signal(signal_data, long=True):
            new_sl = signal_data.get('stop_loss', 0.0)
            quantity, target_risk, actual_risk, capped_notional, capped_cash, sizing_ok = size_for_risk(
                ledger, strategy_id, current_price, new_sl,
                RISK_SETTINGS['equity_risk_pct'], RISK_SETTINGS, is_short=False,
            )
            if should_open_after_sizing(
                'LONG', quantity, current_price, target_risk, actual_risk,
                capped_notional, capped_cash, sizing_ok, ledger, strategy_id, RISK_SETTINGS,
                verbose=verbose,
            ):
                new_tp = signal_data.get('take_profit', 0.0)
                bar_date = last_bar_date(market_data)
                ledger.update_position(
                    strategy_id, symbol, quantity, current_price, 'buy',
                    stop_loss=new_sl, take_profit=new_tp,
                    reason=signal_data.get('reason'),
                    entry_date=bar_date, event_ts=event_ts,
                )

    elif action == 'sell':
        if position_side == 'LONG':
            pos_data, position_side = apply_exit(
                ledger, strategy, strategy_id, symbol, market_data, pos_data,
                signal_data, position_side,
                event_ts=event_ts, build_snapshots=build_snapshots, verbose=verbose,
            )

        if position_side is None and _is_entry_signal(signal_data, long=False):
            new_sl = signal_data.get('stop_loss', 0.0)
            quantity, target_risk, actual_risk, capped_notional, capped_cash, sizing_ok = size_for_risk(
                ledger, strategy_id, current_price, new_sl,
                RISK_SETTINGS['equity_risk_pct'], RISK_SETTINGS, is_short=True,
            )
            if should_open_after_sizing(
                'SHORT', quantity, current_price, target_risk, actual_risk,
                capped_notional, capped_cash, sizing_ok, ledger, strategy_id, RISK_SETTINGS,
                verbose=verbose,
            ):
                new_tp = signal_data.get('take_profit', 0.0)
                bar_date = last_bar_date(market_data)
                ledger.update_position(
                    strategy_id, symbol, quantity, current_price, 'sell',
                    stop_loss=new_sl, take_profit=new_tp,
                    reason=signal_data.get('reason'),
                    entry_date=bar_date, event_ts=event_ts,
                )

    elif action == 'hold':
        new_sl = signal_data.get('stop_loss')
        if new_sl is not None and new_sl > 0 and pos_data:
            ledger.update_stop_loss(strategy_id, symbol, new_sl)
