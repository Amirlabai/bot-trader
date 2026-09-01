import sys
import os
import importlib
import traceback
from datetime import datetime

# Repo root on sys.path (required for shared.constants via config). Run: python src/main.py from repo root.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
os.chdir(REPO_ROOT)
for _path in (REPO_ROOT, os.path.join(REPO_ROOT, 'src')):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from config import Config, TRADING_CONFIG, RISK_SETTINGS
from shared.constants import (
    reason_is_entry_long,
    reason_is_entry_short,
)
from shared.exit_snapshots import last_bar_date as _last_bar_date
from shared.risk_sizing import size_for_risk, should_open_after_sizing
from shared.symbols import asset_type_for_symbol
from shared.trade_exec import apply_exit
from data_ingestion import DataFetcher
from ledger_manager import LedgerManager


def _is_entry_signal(signal_data, long=True):
    if signal_data.get('is_entry'):
        return True
    reason = signal_data.get('reason', '')
    return reason_is_entry_long(reason) if long else reason_is_entry_short(reason)


def load_strategy(module_name, class_name, params):
    try:
        module = importlib.import_module(module_name)
        strategy_class = getattr(module, class_name)
        return strategy_class(params)
    except Exception as e:
        print(f"Failed to load strategy {class_name} from {module_name}: {e}")
        return None


def main():
    print(f"--- Starting Bot Trader Session: {datetime.now()} ---")

    ledger = LedgerManager(Config)
    data_fetcher = DataFetcher(Config)

    for strategy_id, config in TRADING_CONFIG.items():
        print(f"\n==========================================")
        print(f"Processing Strategy: {strategy_id}")
        current_balance = ledger.get_balance(strategy_id)
        print(f"Strategy Balance: ${current_balance:.2f}")

        strategy = load_strategy(config['strategy_module'], config['strategy_class'], config['params'])
        if not strategy:
            continue

        pairs = config['pairs']
        for symbol in pairs:
            asset_type = asset_type_for_symbol(symbol)

            print(f"  > Analyzing {symbol} ({asset_type})...")
            market_data = data_fetcher.get_data(symbol, asset_type=asset_type)
            if market_data.empty:
                print(f"    No data found for {symbol}. Skipping.")
                continue

            pos_data = ledger.get_position(strategy_id, symbol)

            try:
                signal_data = strategy.generate_signal(market_data, pos_data)
            except Exception as e:
                print(f"    Error generating signal: {e}")
                traceback.print_exc()
                if os.getenv("BOT_TRADER_DEBUG") == "1":
                    raise
                continue

            action = signal_data.get('action', 'hold')
            current_price = market_data['close'].iloc[-1]

            if pos_data:
                ledger.update_position_price(strategy_id, symbol, current_price)

            print(f"    Action: {action.upper()} | Reason: {signal_data.get('reason', '')} | Price: {current_price}")

            position_side = pos_data.get('side', 'LONG') if pos_data else None

            if action == 'buy':
                if position_side == 'SHORT':
                    pos_data, position_side = apply_exit(
                        ledger, strategy, strategy_id, symbol, market_data, pos_data,
                        signal_data, position_side, build_snapshots=True, verbose=True,
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
                    ):
                        new_tp = signal_data.get('take_profit', 0.0)
                        bar_date = _last_bar_date(market_data)
                        if ledger.update_position(
                            strategy_id, symbol, quantity, current_price, 'buy',
                            stop_loss=new_sl, take_profit=new_tp,
                            reason=signal_data.get('reason'),
                            entry_date=bar_date,
                        ):
                            print(f"    EXECUTED OPEN LONG: {quantity:.6f} {symbol} @ {current_price} (SL {new_sl}, TP {new_tp})")

            elif action == 'sell':
                if position_side == 'LONG':
                    pos_data, position_side = apply_exit(
                        ledger, strategy, strategy_id, symbol, market_data, pos_data,
                        signal_data, position_side, build_snapshots=True, verbose=True,
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
                    ):
                        new_tp = signal_data.get('take_profit', 0.0)
                        bar_date = _last_bar_date(market_data)
                        if ledger.update_position(
                            strategy_id, symbol, quantity, current_price, 'sell',
                            stop_loss=new_sl, take_profit=new_tp,
                            reason=signal_data.get('reason'),
                            entry_date=bar_date,
                        ):
                            print(f"    EXECUTED OPEN SHORT: {quantity:.6f} {symbol} @ {current_price} (SL {new_sl}, TP {new_tp})")

            elif action == 'hold':
                new_sl = signal_data.get('stop_loss')
                if new_sl is not None and new_sl > 0 and pos_data:
                    ledger.update_stop_loss(strategy_id, symbol, new_sl)
                    print(f"    UPDATED SL: {new_sl}")

    data_fetcher.report_fetch_alerts()

    print("\n--- Session Complete ---")

    ledger.save_ledger()

    from reporting import ReportGenerator
    print("\n--- Generating Performance Report Data ---")
    try:
        reporter = ReportGenerator(Config)
        reporter.generate()
    except Exception as e:
        print(f"Error generating report: {e}")

    ledger.sync_to_remote(commit_message=f"Journal Update: {datetime.now().strftime('%Y-%m-%d')}")


if __name__ == "__main__":
    main()
