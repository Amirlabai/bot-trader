import os
import json
import base64
import io
from datetime import datetime, timedelta

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend, safe for server/CI
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: matplotlib not installed. Trade charts will not be generated.")


# --- Chart Rendering -----------------------------------------------------------

def _render_chart_b64(snapshot: dict) -> str:
    """
    Renders a candlestick chart with indicator overlays from a stored snapshot dict.
    Returns a base64-encoded PNG string, or empty string if rendering fails.
    """
    if not MATPLOTLIB_AVAILABLE:
        return ""

    try:
        candles = snapshot.get("candles", [])
        if not candles:
            return ""

        sl = snapshot.get("stop_loss", 0.0)
        tp = snapshot.get("take_profit", 0.0)
        indicators = snapshot.get("indicators", {})
        entry_price = snapshot.get("entry_price")
        exit_date = snapshot.get("exit_date")
        exit_price = snapshot.get("exit_price")

        n = len(candles)
        xs = list(range(n))
        dates = [c["date"] for c in candles]
        opens  = [c["open"]  for c in candles]
        highs  = [c["high"]  for c in candles]
        lows   = [c["low"]   for c in candles]
        closes = [c["close"] for c in candles]

        # --- Determine if RSI chart is needed ---
        has_rsi = "rsi" in indicators
        n_rows = 2 if has_rsi else 1
        height_ratios = [3, 1] if has_rsi else [1]

        fig, axes = plt.subplots(
            n_rows, 1,
            figsize=(8, 4.5 if has_rsi else 3.5),
            gridspec_kw={"height_ratios": height_ratios},
            facecolor="#0d1117"
        )
        if n_rows == 1:
            axes = [axes]

        ax = axes[0]
        ax.set_facecolor("#161b22")

        # --- Candlesticks ---
        bull_color = "#3fb950"
        bear_color = "#f85149"
        candle_width = 0.6
        wick_width = 0.08

        for i, (o, h, l, c) in enumerate(zip(opens, highs, lows, closes)):
            color = bull_color if c >= o else bear_color
            # Body
            body_lo = min(o, c)
            body_hi = max(o, c)
            ax.add_patch(mpatches.FancyBboxPatch(
                (i - candle_width / 2, body_lo),
                candle_width,
                max(body_hi - body_lo, (highs[0] - lows[0]) * 0.002),
                boxstyle="square,pad=0",
                facecolor=color,
                edgecolor=color,
                linewidth=0,
            ))
            # Wick
            ax.plot([i, i], [l, body_lo], color=color, linewidth=wick_width * 8, solid_capstyle="round")
            ax.plot([i, i], [body_hi, h], color=color, linewidth=wick_width * 8, solid_capstyle="round")

        # --- Indicator overlays (SMAs) ---
        sma_colors = {"sma_fast": "#58a6ff", "sma_slow": "#d29922", "sma_trend": "#8b949e"}
        for key, color in sma_colors.items():
            if key in indicators:
                values = indicators[key]
                if isinstance(values, list) and len(values) == n:
                    ax.plot(xs, values, color=color, linewidth=1.2, label=key.replace("_", " ").upper())
                elif isinstance(values, (int, float)):
                    ax.axhline(values, color=color, linewidth=1.0, linestyle="--", label=key.replace("_", " ").upper())

        # --- SL / TP horizontal levels ---
        exit_kind = snapshot.get("exit_kind", "")
        sl_label = "SL at exit" if exit_kind else f"SL {sl:.4g}"
        tp_label = "TP1 target" if exit_kind == "tp1_partial" else (f"TP {tp:.4g}" if tp else "")
        if sl and sl > 0:
            ax.axhline(sl, color="#f85149", linewidth=1.0, linestyle=":", alpha=0.85, label=sl_label)
        if tp and tp > 0:
            ax.axhline(tp, color="#3fb950", linewidth=1.0, linestyle=":", alpha=0.85, label=tp_label or f"TP {tp:.4g}")

        # --- Entry price (horizontal reference for SL context) ---
        if entry_price is not None:
            ax.axhline(
                entry_price, color="#58a6ff", linewidth=1.0, linestyle="-",
                alpha=0.55, label=f"Entry {entry_price:.4g}",
            )

        if exit_price is not None:
            ax.axhline(
                exit_price, color="#a371f7", linewidth=1.2, linestyle=":",
                alpha=0.85, label=f"Exit {exit_price:.4g}",
            )

        if exit_date:
            exit_date_str = str(exit_date)[:10]
            if exit_date_str in dates:
                exit_idx = dates.index(exit_date_str)
            else:
                exit_idx = n - 1
            ax.axvline(
                exit_idx, color="#a371f7", linewidth=1.0, linestyle="--",
                alpha=0.85, label="Close",
            )

        # --- Axis styling ---
        ax.set_xlim(-0.8, n - 0.2)

        all_prices = highs + lows
        if sl: all_prices.append(sl)
        if tp: all_prices.append(tp)
        if entry_price: all_prices.append(entry_price)
        if exit_price is not None:
            all_prices.append(exit_price)

        max_p = max(all_prices)
        min_p = min(all_prices)
        price_range = max_p - min_p if max_p > min_p else max(highs) * 0.01

        ax.set_ylim(min_p - price_range * 0.05, max_p + price_range * 0.05)

        tick_indices = [0, n // 4, n // 2, 3 * n // 4, n - 1]
        ax.set_xticks([i for i in tick_indices if i < n])
        ax.set_xticklabels([dates[i] for i in tick_indices if i < n], color="#8b949e", fontsize=7, rotation=15)
        ax.tick_params(axis="y", colors="#8b949e", labelsize=7)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.4g}"))
        for spine in ax.spines.values():
            spine.set_edgecolor("#30363d")
        ax.grid(axis="y", color="#30363d", linewidth=0.5, alpha=0.7)

        if any(k in indicators for k in sma_colors) or sl or tp:
            ax.legend(
                loc="upper left", fontsize=6,
                facecolor="#21262d", edgecolor="#30363d", labelcolor="#c9d1d9",
                framealpha=0.85
            )

        # --- RSI subplot ---
        if has_rsi:
            ax_rsi = axes[1]
            ax_rsi.set_facecolor("#161b22")
            rsi_vals = indicators["rsi"]
            if isinstance(rsi_vals, list) and len(rsi_vals) == n:
                ax_rsi.plot(xs, rsi_vals, color="#d29922", linewidth=1.2)
            ax_rsi.axhline(70, color="#f85149", linewidth=0.7, linestyle="--", alpha=0.6)
            ax_rsi.axhline(30, color="#3fb950", linewidth=0.7, linestyle="--", alpha=0.6)
            ax_rsi.set_ylim(0, 100)
            ax_rsi.set_xlim(-0.8, n - 0.2)
            ax_rsi.set_xticks([])
            ax_rsi.tick_params(axis="y", colors="#8b949e", labelsize=7)
            ax_rsi.set_ylabel("RSI", color="#8b949e", fontsize=7)
            for spine in ax_rsi.spines.values():
                spine.set_edgecolor("#30363d")
            ax_rsi.grid(axis="y", color="#30363d", linewidth=0.5, alpha=0.7)

        plt.tight_layout(pad=0.4)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("utf-8")

    except Exception as exc:
        print(f"Chart render error: {exc}")
        return ""


# --- Snapshot Lookup -----------------------------------------------------------

def _find_open_event(history: list, symbol: str, entry_price: float, before_timestamp: str = None) -> dict:
    """Latest OPEN_* event for symbol before close time (fallback: closest entry price)."""
    candidates = [
        e for e in history
        if e["symbol"] == symbol
        and ("OPEN" in e.get("side", ""))
    ]
    if before_timestamp:
        candidates = [e for e in candidates if e["timestamp"] <= before_timestamp]
    if not candidates:
        return {}
    if before_timestamp:
        return max(candidates, key=lambda e: e["timestamp"])
    return min(candidates, key=lambda e: abs(e["price"] - entry_price))


def _find_open_snapshot(history: list, symbol: str, entry_price: float, before_timestamp: str = None) -> dict:
    open_event = _find_open_event(history, symbol, entry_price, before_timestamp)
    return open_event.get("snapshot", {}) if open_event else {}


def _merge_trade_snapshot(
    event: dict,
    snapshot: dict,
    entry_price: float,
    entry_date: str = "",
    exit_date: str = "",
) -> dict:
    """Build chart/report snapshot with exit fill and repaired entry metadata."""
    if not snapshot:
        return {}
    snap = {**snapshot}
    snap["exit_price"] = event["price"]
    if entry_price and entry_price > 0:
        snap["entry_price"] = entry_price
    elif not snap.get("entry_price"):
        snap["entry_price"] = entry_price or None
    if entry_date:
        snap["entry_date"] = entry_date
    if exit_date:
        snap["exit_date"] = exit_date
    if event.get("reason"):
        snap["reason"] = event["reason"]
    return snap


def _exit_date_from_event(event: dict, snap: dict) -> str:
    if event.get("snapshot"):
        candles = snap.get("candles") or []
        if candles:
            return str(candles[-1]["date"])[:10]
    return str(event["timestamp"])[:10]


def _hold_days(entry_date: str, exit_date: str):
    if not entry_date or not exit_date:
        return None
    try:
        entry_dt = datetime.fromisoformat(str(entry_date)[:10])
        exit_dt = datetime.fromisoformat(str(exit_date)[:10])
        return max(0, (exit_dt - entry_dt).days)
    except (ValueError, TypeError):
        return None


def _date_from_open_event(event: dict) -> str:
    osnap = event.get("snapshot") or {}
    if osnap.get("entry_date"):
        return str(osnap["entry_date"])[:10]
    candles = osnap.get("candles") or []
    if candles:
        return str(candles[-1]["date"])[:10]
    return str(event["timestamp"])[:10]


def _entry_date_for_trade(history: list, event: dict, snap: dict, entry_price: float) -> str:
    if snap.get("entry_date"):
        return str(snap["entry_date"])[:10]
    open_event = _find_open_event(
        history, event["symbol"], entry_price, event.get("timestamp"),
    )
    if open_event:
        return _date_from_open_event(open_event)
    return ""


def _entry_date_for_open_position(history: list, symbol: str, side: str) -> str:
    """Entry date for a still-open position by replaying OPEN/CLOSE qty for the symbol."""
    open_side = "OPEN_LONG" if side == "LONG" else "OPEN_SHORT"
    close_side = "CLOSE_LONG" if side == "LONG" else "CLOSE_SHORT"
    add_side = "ADD_LONG" if side == "LONG" else "ADD_SHORT"

    events = sorted(
        (e for e in history if e.get("symbol") == symbol),
        key=lambda x: x["timestamp"],
    )
    entry_date = ""
    qty = 0.0

    for event in events:
        event_side = event.get("side", "")
        if event_side == open_side:
            qty = float(event["quantity"])
            entry_date = _date_from_open_event(event)
        elif event_side == add_side:
            qty += float(event["quantity"])
        elif event_side == close_side and "pnl" in event:
            qty -= float(event["quantity"])
            if qty <= 1e-12:
                qty = 0.0
                entry_date = ""

    return entry_date


# --- Pair performance ----------------------------------------------------------

ROLLING_PAIR_DAYS = 30
# Intentional floor: when the 30-day window is thin, use the last N trades so pair rankings stay stable.
ROLLING_PAIR_MIN_TRADES = 50
PAIR_PERF_TOP_N = 5


def _compute_pair_performance(trade_history_chronological: list, top_n: int = PAIR_PERF_TOP_N) -> dict:
    """
    Rolling pair P/L: aggregate closed trades in the last ROLLING_PAIR_DAYS,
    or the most recent ROLLING_PAIR_MIN_TRADES if the window is thin.
    """
    if not trade_history_chronological:
        return {
            "winners": [],
            "losers": [],
            "window_label": "No closed trades",
            "trades_in_window": 0,
        }

    latest_ts = max(t["time"] for t in trade_history_chronological)
    latest_dt = datetime.fromisoformat(latest_ts[:19])
    cutoff = (latest_dt - timedelta(days=ROLLING_PAIR_DAYS)).isoformat()
    rolling = [t for t in trade_history_chronological if t["time"] >= cutoff]

    if len(rolling) < ROLLING_PAIR_MIN_TRADES:
        rolling = trade_history_chronological[-ROLLING_PAIR_MIN_TRADES:]

    by_symbol = {}
    for t in rolling:
        sym = t["symbol"]
        if sym not in by_symbol:
            by_symbol[sym] = {"symbol": sym, "pnl": 0.0, "trades": 0, "wins": 0}
        by_symbol[sym]["pnl"] += t["pnl"]
        by_symbol[sym]["trades"] += 1
        if t["pnl"] > 0:
            by_symbol[sym]["wins"] += 1

    rows = []
    for d in by_symbol.values():
        rows.append({
            "symbol": d["symbol"],
            "pnl": round(d["pnl"], 2),
            "trades": d["trades"],
            "win_rate": round(d["wins"] / d["trades"] * 100, 1) if d["trades"] else 0.0,
        })

    rows.sort(key=lambda x: x["pnl"], reverse=True)
    winners = [r for r in rows if r["pnl"] > 0][:top_n]
    losers = sorted([r for r in rows if r["pnl"] < 0], key=lambda x: x["pnl"])[:top_n]

    window_label = f"Last {ROLLING_PAIR_DAYS} days ({len(rolling)} trades)"
    if len(rolling) >= ROLLING_PAIR_MIN_TRADES and rolling[0]["time"] < cutoff:
        window_label = f"Last {len(rolling)} closed trades"

    return {
        "winners": winners,
        "losers": losers,
        "window_label": window_label,
        "trades_in_window": len(rolling),
    }


# --- Report Generator ---------------------------------------------------------

class ReportGenerator:
    def __init__(self, config):
        self.config = config
        self.ledger_file = config.LEDGER_FILE
        self.output_dir = os.path.join(os.getcwd(), 'docs')
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        self.report_file = os.path.join(self.output_dir, "report_data.json")

    def generate(self):
        """Generates the JSON data for the frontend."""
        if not os.path.exists(self.ledger_file):
            print("No ledger file found for reporting.")
            return

        with open(self.ledger_file, 'r') as f:
            ledger = json.load(f)

        strategies = ledger.get("strategies", {})

        output_data = {
            "metadata": {
                "last_updated": datetime.now().isoformat(),
                "initial_cash": self.config.INITIAL_STRATEGY_CASH,
            },
            "strategies": {}
        }

        for strat_name, data in strategies.items():
            cash = data.get("cash", 0.0)
            positions = data.get("positions", {})
            history = data.get("history", [])

            # 1. Current Snapshot
            active_positions = []
            current_pos_value = 0.0

            for symbol, pos in positions.items():
                if isinstance(pos, dict):
                    qty = pos['qty']
                    entry = pos['entry_price']
                    current_price = pos.get('last_price', entry)
                    market_value = qty * current_price
                    current_pos_value += market_value

                    unrealized_pnl = 0.0
                    side = pos.get('side', 'LONG')

                    if side == 'LONG':
                        unrealized_pnl = (current_price - entry) * qty
                    elif side == 'SHORT':
                        unrealized_pnl = (entry - current_price) * qty

                    active_positions.append({
                        "symbol": symbol,
                        "side": side,
                        "qty": qty,
                        "entry": entry,
                        "entry_date": pos.get("entry_date") or _entry_date_for_open_position(
                            history, symbol, side,
                        ),
                        "current_price": current_price,
                        "unrealized_pnl": unrealized_pnl,
                        "sl": pos.get('stop_loss', 0.0),
                        "tp1": pos.get('tp1_hit', False),
                        "tp_price": pos.get('take_profit', 0.0),
                        "value": market_value
                    })

            current_equity = cash + current_pos_value

            # 2. Equity Curve Reconstruction
            initial_cash = self.config.INITIAL_STRATEGY_CASH
            sorted_history = sorted(history, key=lambda x: x['timestamp'])

            equity_curve = []
            running_cash = initial_cash
            running_inventory_value = 0.0

            if sorted_history:
                start_date = sorted_history[0]['timestamp']
            else:
                start_date = datetime.now().isoformat()

            equity_curve.append({"time": start_date, "equity": initial_cash, "type": "initial"})

            for event in sorted_history:
                val = event['total_value']
                side = event.get('side', '')
                qty = event['quantity']
                price = event['price']

                if "OPEN" in side or "ADD" in side:
                    running_cash -= val
                    if "SHORT" in side:
                        running_inventory_value += val
                    else:
                        running_inventory_value += val

                elif "CLOSE" in side:
                    if "LONG" in side:
                        pnl = event.get('pnl', 0.0)
                        revenue = val
                        running_cash += revenue
                        cost_basis_released = revenue - pnl
                        running_inventory_value -= cost_basis_released

                    elif "SHORT" in side:
                        pnl = event.get('pnl', 0.0)
                        entry_price = event.get('entry_price', price)
                        entry_val = qty * entry_price
                        amount_returned = entry_val + pnl
                        running_cash += amount_returned
                        running_inventory_value -= entry_val

                if running_inventory_value < 0:
                    running_inventory_value = 0

                equity_curve.append({
                    "time": event['timestamp'],
                    "equity": running_cash + running_inventory_value,
                    "type": "trade"
                })

            equity_curve.append({
                "time": datetime.now().isoformat(),
                "equity": current_equity,
                "type": "current"
            })

            # 3. Trade History (Closed Positions) + Chart Generation
            trade_history = []
            wins = []
            losses = []
            
            for event in sorted_history:
                if "pnl" in event:
                    pnl = event['pnl']
                    entry_price = event.get('entry_price', 0.0)
                    
                    if pnl > 0: wins.append(pnl)
                    else: losses.append(pnl)

                    snapshot = event.get('snapshot')

                    pnl_pct = 0.0
                    if entry_price > 0:
                        pnl_pct = (pnl / (event['quantity'] * entry_price)) * 100

                    entry_date = _entry_date_for_trade(history, event, snapshot or {}, entry_price)
                    exit_date = _exit_date_from_event(event, snapshot or {})

                    snap = _merge_trade_snapshot(
                        event, snapshot, entry_price, entry_date, exit_date,
                    ) if snapshot else {}
                    chart_b64 = _render_chart_b64(snap) if snapshot else ""

                    sl_level = 0.0
                    tp_level = 0.0
                    if snap:
                        sl_level = float(
                            snap.get("stop_loss_at_exit") or snap.get("stop_loss") or 0
                        )
                        tp_level = float(
                            snap.get("take_profit_at_exit") or snap.get("take_profit") or 0
                        )

                    exit_kind = (
                        event.get("exit_kind")
                        or (snap.get("exit_kind") if snap else "")
                        or ""
                    )
                    quantity_pct = event.get("quantity_pct") or (snap.get("quantity_pct") if snap else None)

                    trade_history.append({
                        "time": event['timestamp'],
                        "symbol": event['symbol'],
                        "side": "LONG" if "LONG" in event['side'] else "SHORT",
                        "qty": event['quantity'],
                        "entry_price": entry_price,
                        "exit_price": event['price'],
                        "entry_date": entry_date,
                        "exit_date": exit_date,
                        "hold_days": _hold_days(entry_date, exit_date),
                        "stop_loss": sl_level,
                        "take_profit": tp_level,
                        "stop_loss_at_exit": sl_level,
                        "take_profit_at_exit": tp_level,
                        "exit_kind": exit_kind,
                        "quantity_pct": quantity_pct,
                        "pnl": pnl,
                        "pnl_pct": pnl_pct,
                        "reason": event.get('reason') or 'N/A',
                        "chart_b64": chart_b64,
                    })

            # 4. Advanced Metrics
            total_closed = len(wins) + len(losses)
            win_rate = (len(wins) / total_closed * 100) if total_closed > 0 else 0.0
            profit_factor = (abs(sum(wins) / sum(losses))) if len(losses) > 0 and sum(losses) != 0 else (float('inf') if len(wins) > 0 else 0.0)
            
            # Max Drawdown
            max_equity = 0.0
            max_dd = 0.0
            for pt in equity_curve:
                if pt['equity'] > max_equity:
                    max_equity = pt['equity']
                dd = (max_equity - pt['equity']) / max_equity * 100 if max_equity > 0 else 0.0
                if dd > max_dd:
                    max_dd = dd

            # Exposure calculation
            exposure = {}
            for pos in active_positions:
                sym = pos['symbol']
                exposure[sym] = exposure.get(sym, 0.0) + pos['value']

            pair_performance = _compute_pair_performance(trade_history)

            output_data["strategies"][strat_name] = {
                "active_positions": active_positions,
                "current_cash": cash,
                "current_equity": current_equity,
                "history_events": len(history),
                "equity_curve": equity_curve,
                "trade_history": list(reversed(trade_history)),  # Newest first
                "pair_performance": pair_performance,
                "metrics": {
                    "win_rate": win_rate,
                    "profit_factor": profit_factor if profit_factor != float('inf') else "∞",
                    "total_pnl": sum(wins) + sum(losses),
                    "avg_pnl": (sum(wins) + sum(losses)) / total_closed if total_closed > 0 else 0.0,
                    "max_drawdown": max_dd,
                    "total_trades": total_closed
                },
                "exposure": exposure
            }

        with open(self.report_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)

        # Also write JS file for local usage without CORS
        js_file = os.path.join(self.output_dir, "report_data.js")
        with open(js_file, 'w', encoding='utf-8') as f:
            f.write("window.REPORT_DATA = ")
            json.dump(output_data, f, indent=2)
            f.write(";")

        print(f"Report data generated: {self.report_file} and {js_file}")
