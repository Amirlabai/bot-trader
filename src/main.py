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

import pandas as pd

from config import Config, TRADING_CONFIG, RISK_SETTINGS, TP1_EXIT_REASONS
from data_ingestion import DataFetcher
from ledger_manager import LedgerManager

def _build_candle_snapshot(market_data, signal_data, n=20, entry_price=None, entry_date=None, pos_data=None):
    """
    Builds a lightweight OHLCV snapshot plus indicator values.
    Capped at 'n' candles (default 20) as per Boss Man's request.
    Y-axis will scale to include entry_price even if date is outside window.
    """
    start_idx = max(0, len(market_data) - n)
    df = market_data.iloc[start_idx:]
    
    candles = []
    for ts, row in df.iterrows():
        candles.append({
            "date": str(ts)[:10],
            "open": round(float(row["open"]), 8),
            "high": round(float(row["high"]), 8),
            "low": round(float(row["low"]), 8),
            "close": round(float(row["close"]), 8),
        })

    # 2. Extract Levels (Signal Data priority, then Position Data)
    sl = signal_data.get("stop_loss")
    if (sl is None or sl == 0.0) and pos_data:
        sl = pos_data.get("stop_loss", 0.0)
    
    tp = signal_data.get("take_profit")
    if (tp is None or tp == 0.0) and pos_data:
        tp = pos_data.get("take_profit", 0.0)

    # Use explicitly passed entry info or fallback to pos_data
    if entry_price is not None:
        final_entry_price = entry_price
    elif pos_data:
        final_entry_price = pos_data.get("entry_price")
    else:
        final_entry_price = None
    final_entry_date = str(entry_date)[:10] if entry_date else (pos_data.get("entry_date") if pos_data else None)

    # 3. Extract Indicators
    indicators = signal_data.get("indicators", {})
    sliced_indicators = {}
    for key, values in indicators.items():
        if hasattr(values, "iloc"):
            sliced_indicators[key] = [round(float(v), 8) if pd.notnull(v) else None for v in values.iloc[start_idx:]]
        elif isinstance(values, list):
            sliced_indicators[key] = values[start_idx:]

    return {
        "candles": candles,
        "stop_loss": sl,
        "take_profit": tp,
        "indicators": sliced_indicators,
        "reason": signal_data.get("reason", ""),
        "entry_price": final_entry_price,
        "entry_date": final_entry_date
    }


def _clamp_quantity_pct(pct, default=1.0):
    """Clamp strategy quantity_pct to (0, 1]."""
    try:
        v = float(pct)
    except (TypeError, ValueError):
        return default
    if v <= 0:
        return default
    return min(1.0, v)


def _apply_tp1_updates(ledger, strategy_id, symbol, signal_data):
    """After a partial exit, move SL to breakeven and record TP1 (long or short)."""
    new_sl = signal_data.get('stop_loss')
    if new_sl is not None and new_sl > 0:
        ledger.update_stop_loss(strategy_id, symbol, new_sl)
    if signal_data.get('reason', '') in TP1_EXIT_REASONS:
        ledger.mark_tp1_hit(strategy_id, symbol)
        print(f"    TP1 HIT RECORDED for {symbol}")


def _size_for_risk(ledger, strategy_id, current_price, stop_loss, equity_risk_pct, is_short=False):
    """
    Size from equity_risk_pct of total equity (cash + open positions at cost, no unrealized P/L).
    Caps notional at max_notional_pct of equity, then at free cash.
    Returns (quantity, target_risk, actual_risk, capped_notional, capped_cash, sizing_ok).
    """
    stop_loss = float(stop_loss or 0)
    total_equity = ledger.get_total_equity(strategy_id)
    target_risk = total_equity * equity_risk_pct
    max_notional_pct = RISK_SETTINGS['max_notional_pct']

    if stop_loss <= 0:
        return 0.0, target_risk, 0.0, False, False, False

    if is_short:
        risk_per_share = stop_loss - current_price
    else:
        risk_per_share = current_price - stop_loss

    if risk_per_share <= 0:
        return 0.0, target_risk, 0.0, False, False, False

    if current_price <= 0:
        return 0.0, target_risk, 0.0, False, False, False

    quantity = target_risk / risk_per_share
    capped_notional = False
    capped_cash = False

    max_notional = total_equity * max_notional_pct
    if quantity * current_price > max_notional:
        quantity = max_notional / current_price
        capped_notional = True

    current_cash = ledger.get_balance(strategy_id)
    if quantity * current_price > current_cash:
        quantity = current_cash / current_price
        capped_cash = True

    actual_risk = quantity * risk_per_share
    return quantity, target_risk, actual_risk, capped_notional, capped_cash, True


def _should_open_after_sizing(
    side_label, quantity, current_price, target_risk, actual_risk,
    capped_notional, capped_cash, sizing_ok, ledger, strategy_id,
):
    """Log skip reasons or cap notes; return True only when an open should proceed."""
    min_frac = RISK_SETTINGS['min_risk_fraction']
    min_notional = RISK_SETTINGS['min_notional_usd']
    notional = quantity * current_price
    free_cash = ledger.get_balance(strategy_id)
    capped = capped_notional or capped_cash

    if not sizing_ok:
        print(f"    SKIP OPEN {side_label}: invalid stop (missing or on wrong side of entry)")
        return False
    if not capped and actual_risk < target_risk * min_frac:
        print(
            f"    SKIP OPEN {side_label}: ${actual_risk:.2f} risk below "
            f"{min_frac:.0%} of target (${target_risk:.2f})"
        )
        return False
    if notional < min_notional:
        print(
            f"    SKIP OPEN {side_label}: below min notional "
            f"(${notional:.2f} < ${min_notional:.2f})"
        )
        return False
    if capped:
        cap_parts = []
        if capped_notional:
            cap_parts.append(f"max notional {RISK_SETTINGS['max_notional_pct']:.0%} of equity")
        if capped_cash:
            cap_parts.append(f"free cash ${free_cash:.2f}")
        print(
            f"    SIZE-CAPPED ({', '.join(cap_parts)}): target risk ${target_risk:.2f}, "
            f"actual ${actual_risk:.2f}, notional ${notional:.2f}"
        )
    return True


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
    
    # Iterate through configured strategies
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
            # Heuristic for Asset Type
            is_forex = any(cur in symbol for cur in ['EUR', 'USD', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF']) and '/' in symbol and len(symbol) == 7
            asset_type = 'forex' if is_forex else 'crypto'
            
            print(f"  > Analyzing {symbol} ({asset_type})...")
            
            market_data = data_fetcher.get_data(symbol, asset_type=asset_type)
            if market_data.empty:
                print(f"    No data found for {symbol}. Skipping.")
                continue

            # Pass full position object (dict) linked to this strategy
            pos_data = ledger.get_position(strategy_id, symbol)
            
            # Generate Signal
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
            
            # --- Update Unrelized PnL Data in Ledger ---
            if pos_data:
                ledger.update_position_price(strategy_id, symbol, current_price)

            print(f"    Action: {action.upper()} | Reason: {signal_data.get('reason', '')} | Price: {current_price}")

            position_side = pos_data.get('side', 'LONG') if pos_data else None
            
            # --- SIGNAL PROCESSING ---
            if action == 'buy':
                # 1. Close SHORT if exists
                if position_side == 'SHORT':
                    print(f"    Signal BUY -> Closing SHORT {symbol}")
                    pct = _clamp_quantity_pct(signal_data.get('quantity_pct', 1.0))
                    qty_to_cover = pos_data['qty'] * pct
                    entry_price = pos_data.get('entry_price')
                    entry_date = pos_data.get('entry_date')
                    snapshot = _build_candle_snapshot(market_data, signal_data, entry_price=entry_price, entry_date=entry_date, pos_data=pos_data)
                    if ledger.update_position(strategy_id, symbol, qty_to_cover, current_price, 'buy', candle_snapshot=snapshot, reason=signal_data.get('reason')):
                         print(f"    EXECUTED COVER SHORT: {qty_to_cover:.6f} {symbol} @ {current_price}")
                         _apply_tp1_updates(ledger, strategy_id, symbol, signal_data)
                         pos_data = ledger.get_position(strategy_id, symbol)
                         position_side = pos_data.get('side') if pos_data else None

                # 2. Open LONG only when flat; same-bar flip after full cover
                if position_side is None:
                    new_sl = signal_data.get('stop_loss', 0.0)
                    quantity, target_risk, actual_risk, capped_notional, capped_cash, sizing_ok = _size_for_risk(
                        ledger, strategy_id, current_price, new_sl,
                        RISK_SETTINGS['equity_risk_pct'], is_short=False,
                    )
                    if _should_open_after_sizing(
                        'LONG', quantity, current_price, target_risk, actual_risk,
                        capped_notional, capped_cash, sizing_ok, ledger, strategy_id,
                    ):
                        new_tp = signal_data.get('take_profit', 0.0)
                        snapshot = _build_candle_snapshot(market_data, signal_data, pos_data=pos_data)
                        if ledger.update_position(strategy_id, symbol, quantity, current_price, 'buy', stop_loss=new_sl, take_profit=new_tp, candle_snapshot=snapshot, reason=signal_data.get('reason')):
                             print(f"    EXECUTED OPEN LONG: {quantity:.6f} {symbol} @ {current_price} (SL {new_sl}, TP {new_tp})")

            elif action == 'sell':
                # 1. Close LONG if exists
                if position_side == 'LONG':
                    print(f"    Signal SELL -> Closing LONG {symbol}")
                    pct = _clamp_quantity_pct(signal_data.get('quantity_pct', 1.0))
                    qty_to_sell = pos_data['qty'] * pct
                    entry_price = pos_data.get('entry_price')
                    entry_date = pos_data.get('entry_date')
                    snapshot = _build_candle_snapshot(market_data, signal_data, entry_price=entry_price, entry_date=entry_date, pos_data=pos_data)
                    if ledger.update_position(strategy_id, symbol, qty_to_sell, current_price, 'sell', candle_snapshot=snapshot, reason=signal_data.get('reason')):
                        print(f"    EXECUTED SELL LONG: {qty_to_sell:.6f} {symbol} @ {current_price}")
                        _apply_tp1_updates(ledger, strategy_id, symbol, signal_data)
                        pos_data = ledger.get_position(strategy_id, symbol)
                        position_side = pos_data.get('side') if pos_data else None

                # 2. Open SHORT only when flat; same-bar flip after full close
                if position_side is None:
                    new_sl = signal_data.get('stop_loss', 0.0)
                    quantity, target_risk, actual_risk, capped_notional, capped_cash, sizing_ok = _size_for_risk(
                        ledger, strategy_id, current_price, new_sl,
                        RISK_SETTINGS['equity_risk_pct'], is_short=True,
                    )
                    if _should_open_after_sizing(
                        'SHORT', quantity, current_price, target_risk, actual_risk,
                        capped_notional, capped_cash, sizing_ok, ledger, strategy_id,
                    ):
                        new_tp = signal_data.get('take_profit', 0.0)
                        snapshot = _build_candle_snapshot(market_data, signal_data, pos_data=pos_data)
                        if ledger.update_position(strategy_id, symbol, quantity, current_price, 'sell', stop_loss=new_sl, take_profit=new_tp, candle_snapshot=snapshot, reason=signal_data.get('reason')):
                             print(f"    EXECUTED OPEN SHORT: {quantity:.6f} {symbol} @ {current_price} (SL {new_sl}, TP {new_tp})")

            elif action == 'hold':
                 # Trailing SL Updates
                 new_sl = signal_data.get('stop_loss')
                 if new_sl is not None and new_sl > 0 and pos_data:
                      ledger.update_stop_loss(strategy_id, symbol, new_sl)
                      print(f"    UPDATED SL: {new_sl}")

    print("\n--- Session Complete ---")
    
    ledger.save_ledger()

    # Generate Report (JSON for SPA)
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
