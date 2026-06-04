"""Position sizing from equity risk (shared by main and resim)."""


def size_for_risk(ledger, strategy_id, current_price, stop_loss, equity_risk_pct, risk_settings, is_short=False):
    stop_loss = float(stop_loss or 0)
    total_equity = ledger.get_total_equity(strategy_id)
    target_risk = total_equity * equity_risk_pct
    max_notional_pct = risk_settings['max_notional_pct']

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


def should_open_after_sizing(
    side_label,
    quantity,
    current_price,
    target_risk,
    actual_risk,
    capped_notional,
    capped_cash,
    sizing_ok,
    ledger,
    strategy_id,
    risk_settings,
    verbose=True,
):
    min_frac = risk_settings['min_risk_fraction']
    min_notional = risk_settings['min_notional_usd']
    notional = quantity * current_price
    free_cash = ledger.get_balance(strategy_id)
    capped = capped_notional or capped_cash

    if not sizing_ok:
        if verbose:
            print(f"    SKIP OPEN {side_label}: invalid stop (missing or on wrong side of entry)")
        return False
    if not capped and actual_risk < target_risk * min_frac:
        if verbose:
            print(
                f"    SKIP OPEN {side_label}: ${actual_risk:.2f} risk below "
                f"{min_frac:.0%} of target (${target_risk:.2f})"
            )
        return False
    if notional < min_notional:
        if verbose:
            print(
                f"    SKIP OPEN {side_label}: below min notional "
                f"(${notional:.2f} < ${min_notional:.2f})"
            )
        return False
    if capped and verbose:
        cap_parts = []
        if capped_notional:
            cap_parts.append(f"max notional {risk_settings['max_notional_pct']:.0%} of equity")
        if capped_cash:
            cap_parts.append(f"free cash ${free_cash:.2f}")
        print(
            f"    SIZE-CAPPED ({', '.join(cap_parts)}): target risk ${target_risk:.2f}, "
            f"actual ${actual_risk:.2f}, notional ${notional:.2f}"
        )
    return True
