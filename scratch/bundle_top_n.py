"""
Shared-$10k long-only portfolio sweep: top-N curated crypto symbols.

Ranks locked crypto winners by curator score, then for N=3..10 (and all)
runs simulate_long_portfolio with each symbol's locked six-pack.

Usage:
  .\\.venv\\Scripts\\python.exe scratch\\bundle_top_n.py --start 2022-09-11
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
os.chdir(REPO)
sys.path[:0] = [str(REPO), str(REPO / "src"), str(REPO / "scratch")]

from config import Config, RISK_SETTINGS  # noqa: E402
from data_ingestion import DataFetcher  # noqa: E402
from shared.curated_params import load_curated_params  # noqa: E402
from shared.path_sim import (  # noqa: E402
    PathSimInvariantError,
    build_long_entry_mask,
    simulate_long_portfolio,
)


def build_symbol_series(
    symbol: str,
    df: pd.DataFrame,
    params: dict,
    calendar: pd.DatetimeIndex,
) -> dict:
    close = df["close"].to_numpy(dtype=float)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    entry, atr = build_long_entry_mask(
        close, high, low,
        short_window=int(params["short_window"]),
        long_window=int(params["long_window"]),
        trend_window=int(params["trend_window"]),
        atr_period=int(params["atr_period"]),
        adx_min=float(params.get("adx_min") or 0.0),
        atr_buffer=float(params.get("atr_buffer") or 0.0),
        adx_period=int(params.get("adx_period") or 14),
        regime_ok=None,
    )
    native = pd.DataFrame(
        {
            "close": close,
            "low": low,
            "atr": atr,
            "entry": entry.astype(float),
            "has": 1.0,
        },
        index=df.index,
    )
    aligned = native.reindex(calendar)
    has_bar = aligned["has"].fillna(0.0).to_numpy(dtype=bool)
    # ffill OHLC/ATR for open positions across missing native days; entries only on real bars
    close_a = aligned["close"].ffill().to_numpy(dtype=float)
    low_a = aligned["low"].ffill().to_numpy(dtype=float)
    atr_a = aligned["atr"].ffill().to_numpy(dtype=float)
    entry_a = aligned["entry"].fillna(0.0).to_numpy(dtype=float) > 0.5
    entry_a = entry_a & has_bar
    return {
        "symbol": symbol,
        "close": close_a,
        "low": low_a,
        "atr": atr_a,
        "entry": entry_a,
        "has_bar": has_bar,
        "sl_atr": float(params["sl_atr"]),
        "trail_atr": float(params["trail_atr"]),
    }


def main():
    parser = argparse.ArgumentParser(description="Top-N curated crypto bundle sweep")
    parser.add_argument("--start", type=lambda s: date.fromisoformat(s), default=date(2022, 9, 11))
    parser.add_argument("--end", type=lambda s: date.fromisoformat(s), default=None)
    parser.add_argument("--min-n", type=int, default=3)
    parser.add_argument("--max-n", type=int, default=10)
    args = parser.parse_args()
    end = args.end or date.today()

    curated = load_curated_params()
    crypto = [
        (sym, block)
        for sym, block in (curated.get("symbols") or {}).items()
        if (block or {}).get("market") == "crypto"
    ]
    crypto.sort(key=lambda kv: float((kv[1] or {}).get("score") or 0.0), reverse=True)
    if not crypto:
        raise SystemExit("No crypto symbols in curated_params.json")

    print(f"Ranked {len(crypto)} curated crypto symbols by score")
    for i, (sym, block) in enumerate(crypto, 1):
        print(f"  {i:2d}. {sym:12} score={block.get('score')} pnl={((block.get('metrics') or {}).get('net_pnl'))}")

    fetcher = DataFetcher(Config)
    frames: dict[str, pd.DataFrame] = {}
    for sym, _ in crypto:
        df = fetcher.get_data(sym, asset_type="crypto")
        if df is None or df.empty:
            print(f"  skip {sym}: no data")
            continue
        df = df[(df.index >= pd.Timestamp(args.start)) & (df.index <= pd.Timestamp(end))]
        if len(df) < 50:
            print(f"  skip {sym}: too short")
            continue
        frames[sym] = df

    ranked = [(s, b) for s, b in crypto if s in frames]
    calendar = pd.DatetimeIndex(sorted({ts for df in frames.values() for ts in df.index}))
    calendar = calendar[(calendar >= pd.Timestamp(args.start)) & (calendar <= pd.Timestamp(end))]
    if len(calendar) < 50:
        raise SystemExit("Calendar too short")

    risk = {**RISK_SETTINGS, "equity_risk_pct": 0.01}
    start_cash = float(Config.INITIAL_STRATEGY_CASH)
    trail_arm = 1.0

    rows = []
    ns = list(range(args.min_n, min(args.max_n, len(ranked)) + 1))
    if len(ranked) not in ns and len(ranked) > args.max_n:
        ns.append(len(ranked))

    for n in ns:
        bundle = ranked[:n]
        series = []
        for sym, block in bundle:
            ser = build_symbol_series(sym, frames[sym], block["params"], calendar)
            series.append(ser)
        # Default sl/trail unused when per-series set; pass template-ish mid values
        try:
            out = simulate_long_portfolio(
                series,
                sl_atr=2.0,
                trail_atr=5.0,
                start_cash=start_cash,
                risk_settings=risk,
                trail_arm_r=trail_arm,
                assert_invariants=True,
            )
        except PathSimInvariantError as e:
            print(f"N={n}: INVARIANT FAIL {e}")
            continue
        final_eq = float(out.get("equity") or start_cash)
        net = float(out.get("net_pnl") or 0.0)
        pf = out.get("profit_factor")
        trades = int(out.get("closed_trades") or 0)
        wr = float(out.get("win_rate") or 0.0)
        calmar = float(out.get("calmar") or 0.0)
        open_n = int(out.get("open_positions") or 0)
        names = [s for s, _ in bundle]
        rows.append({
            "n": n,
            "symbols": names,
            "net_pnl": net,
            "final_equity": final_eq,
            "profit_factor": pf,
            "closed_trades": trades,
            "win_rate": wr,
            "calmar": calmar,
            "open_positions": open_n,
            "ret_pct": (final_eq / start_cash - 1.0) * 100.0,
        })
        pf_s = "∞" if pf == float("inf") else f"{float(pf):.2f}"
        print(
            f"N={n:2d} | eq=${final_eq:,.0f} | pnl=${net:,.0f} | PF={pf_s} | "
            f"trades={trades} | WR={wr:.1f}% | open={open_n} | {', '.join(x.split('/')[0] for x in names)}"
        )

    # Sweet spot: max final equity, then PF
    if not rows:
        raise SystemExit("No successful runs")
    best = max(rows, key=lambda r: (r["final_equity"], float(r["profit_factor"]) if r["profit_factor"] != float("inf") else 99.0))
    print(f"\nSweet spot by final equity: N={best['n']} -> ${best['final_equity']:,.0f}")

    # Quality-aware pick inside 3..10: best pnl among PF >= median PF of the sweep
    core = [r for r in rows if args.min_n <= r["n"] <= args.max_n]
    pfs = [
        99.0 if r["profit_factor"] == float("inf") else float(r["profit_factor"])
        for r in core
    ]
    med_pf = float(np.median(pfs)) if pfs else 0.0
    quality = [
        r for r in core
        if (99.0 if r["profit_factor"] == float("inf") else float(r["profit_factor"])) >= med_pf
    ]
    qbest = max(quality or core, key=lambda r: r["final_equity"])
    print(
        f"Sweet spot 3..{args.max_n} with PF>=median({med_pf:.2f}): "
        f"N={qbest['n']} -> ${qbest['final_equity']:,.0f}"
    )

    out_md = REPO / "docs" / f"crypto_bundle_topn_{args.start.isoformat()}.md"
    lines = [
        f"# Crypto top-N bundle sweep",
        "",
        f"Generated: {datetime.utcnow().isoformat(timespec='seconds')}",
        f"Window: `{args.start}` .. `{end}` | Start cash: **${start_cash:,.0f}** | Risk: **1%** | Frozen entry ATR trail",
        "",
        "Long-only shared-cash `simulate_long_portfolio` with each symbol's locked curated params.",
        "Same-bar entry order: higher curator score first (gets cash priority).",
        "",
        f"**Max equity (incl. all):** N={best['n']} → ${best['final_equity']:,.0f} "
        f"(pnl ${best['net_pnl']:,.0f})",
        "",
        f"**Quality pick (N={args.min_n}..{args.max_n}, PF ≥ median):** "
        f"N={qbest['n']} → ${qbest['final_equity']:,.0f}",
        "",
        "| N | Final eq | PnL | Ret% | PF | Trades | WR% | Bundle |",
        "|--:|--:|--:|--:|--:|--:|--:|---|",
    ]
    for r in rows:
        pf = r["profit_factor"]
        pf_s = "∞" if pf == float("inf") else f"{float(pf):.2f}"
        bundle = ", ".join(s.split("/")[0] for s in r["symbols"])
        mark = " *" if r["n"] == qbest["n"] else ""
        lines.append(
            f"| {r['n']}{mark} | ${r['final_equity']:,.0f} | ${r['net_pnl']:,.0f} | "
            f"{r['ret_pct']:.1f}% | {pf_s} | {r['closed_trades']} | {r['win_rate']:.1f} | {bundle} |"
        )
    lines.extend([
        "",
        "## Rank order (curator score)",
        "",
    ])
    for i, (sym, block) in enumerate(ranked, 1):
        lines.append(f"{i}. `{sym}` score={block.get('score')}")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out_md}")
    fetcher.report_fetch_alerts()


if __name__ == "__main__":
    main()
