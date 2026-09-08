# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Anyone whom it may concern: operators, reviewers, or curious readers who open the desk to see how the daily paper run performed. Not a multi-tenant SaaS audience; no separate roles were confirmed.

## Product Purpose

**Bot Trader** is a daily trade tester: a simple algorithmic paper-trading system on a fixed set of assets (crypto, forex, and commodities), with a GitHub Pages dashboard for after-run review.

Success means the bot runs on a schedule, the ledger stays coherent with the risk and exit rules, and the desk makes equity, exposure, open risk, and closed-trade outcomes easy to scan. It is not a live brokerage, not a marketplace product, and not a claim of profitable live trading.

## Positioning

Paper-tests simple long/short strategies (moving average and RSI families) on a declared symbol set with a shared risk model (about 1% equity risk per new open, TP1 then trail), then publishes a static post-run desk. Neighboring “trading dashboards” without this ledgered daily bot loop cannot truthfully claim the same workflow.

## Operating Context

- Daily GitHub Actions run (`daily_trade.yml`, 00:00 UTC) executes `src/main.py` from repo root.
- Market data: yfinance only (Yahoo); session can block further Yahoo fetches after rate-limit/block.
- State lives in `data/ledger.json` (per-strategy wallets); reports land in `docs/` (`report_data.js`, lazy `report_charts.js`).
- Dashboard: static SPA at `docs/index.html`, hosted on GitHub Pages.
- Operator rituals: review KPIs and charts, filter closed trades, expand rows for SL/TP and close snapshots; optional audit/repair/snapshot backfill via `scratch/` scripts.
- Local knowledge graph (`graphify-out/`) is a development aid, not a user-facing surface.

## Capabilities and Constraints

**Capabilities (built and in scope to preserve):**
- Multi-strategy paper trading (long and short) across configured crypto, forex, and commodity symbols.
- Risk sizing, TP1 (50% at 1.0 ATR) and trailing stop after TP1; wick-aware stop/TP1 fills on daily bars.
- Equity curve, exposure, rolling pair winners/losers, Long vs Short window stats with Bull/Bear/Flat bias cue.
- Open positions and closed-trade history with expand detail and lazy close charts.
- Trade audit and ledger repair/backfill tooling under `scratch/`.

**Constraints:**
- Paper cash and ledger only; no live order routing.
- Dashboard is static HTML/JS (no app framework); Python 3.9+ bot stack.
- Preserve as much of what is already built as possible; do not strip working desk or engine behavior without an explicit product decision.
- Undecided: public marketing site, paid product packaging, multi-user auth, and formal accessibility compliance target.

## Brand Commitments

- Product name: **Bot Trader** (dashboard title; two words).
- Voice: quiet, dense, operational desk language (formal plain language; no emoji in product UI).
- Visual system is recorded separately in `DESIGN.md` (After-Hours Desk); init does not redefine it.

## Evidence on Hand

- Live desk and report artifacts: `docs/index.html`, `docs/report_data.js`, `docs/report_charts.js`.
- Design authority: `DESIGN.md`, `.impeccable/design.json`.
- Engineering context: `context.md`, `status.md`, strategies under `strategies/`, shared risk/exit modules under `shared/`.
- Do not invent testimonials, live P/L claims, customer logos, or third-party endorsements.

## Product Principles

1. **Honest paper first** — Show the ledger and fills as the system actually ran; do not dress paper results as live brokerage.
2. **Desk after the run** — Prefer scanability for post-daily review over promotional storytelling.
3. **Preserve the build** — Extend the existing bot and dashboard; avoid replacing working surfaces without a clear product reason.
4. **Simple algo, fixed book** — Keep the strategy set and traded assets understandable; complexity belongs in risk/exit correctness, not in UI spectacle.
5. **Open to whom it may concern** — The Pages desk can be read by anyone with the link; do not assume private-only UX or invent access control that is not built.
