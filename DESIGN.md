---
name: Bot Trader Dashboard
description: GitHub-dark paper-trading desk for scanning equity, exposure, and closed trades.
colors:
  canvas: "#0d1117"
  surface: "#161b22"
  ink: "#c9d1d9"
  frost: "#f0f6fc"
  muted: "#8b949e"
  stroke: "#30363d"
  accent: "#58a6ff"
  pnl-gain: "#3fb950"
  pnl-loss: "#f85149"
  caution: "#d29922"
  gain-wash: "rgba(59, 190, 80, 0.15)"
  loss-wash: "rgba(248, 81, 73, 0.15)"
  accent-hover: "rgba(88, 166, 255, 0.06)"
typography:
  display:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"Segoe UI\", Helvetica, Arial, sans-serif"
    fontSize: "clamp(1.35rem, 4vw, 2rem)"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "normal"
  headline:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"Segoe UI\", Helvetica, Arial, sans-serif"
    fontSize: "24px"
    fontWeight: 600
    letterSpacing: "normal"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"Segoe UI\", Helvetica, Arial, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    letterSpacing: "normal"
  table:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"Segoe UI\", Helvetica, Arial, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    letterSpacing: "normal"
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"Segoe UI\", Helvetica, Arial, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    letterSpacing: "0.5px"
  caption:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"Segoe UI\", Helvetica, Arial, sans-serif"
    fontSize: "11px"
    fontWeight: 400
    letterSpacing: "normal"
  chip:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"Segoe UI\", Helvetica, Arial, sans-serif"
    fontSize: "10px"
    fontWeight: 600
    letterSpacing: "normal"
rounded:
  md: "6px"
  bar: "4px"
  pill: "10px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "15px"
  lg: "20px"
  xl: "30px"
components:
  metric-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.frost}"
    rounded: "{rounded.md}"
    padding: "15px"
  chart-panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.muted}"
    rounded: "{rounded.md}"
    padding: "20px"
    height: "380px"
  pair-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.muted}"
    rounded: "{rounded.md}"
    padding: "12px"
  filter-control:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
    height: "44px"
  symbol-filter:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
    height: "44px"
    width: "min(240px, 100%)"
  chip-long:
    backgroundColor: "{colors.gain-wash}"
    textColor: "{colors.pnl-gain}"
    typography: "{typography.chip}"
    rounded: "{rounded.pill}"
    padding: "3px 7px"
  chip-short:
    backgroundColor: "{colors.loss-wash}"
    textColor: "{colors.pnl-loss}"
    typography: "{typography.chip}"
    rounded: "{rounded.pill}"
    padding: "3px 7px"
  chip-tp1:
    backgroundColor: "rgba(210, 153, 34, 0.1)"
    textColor: "{colors.caution}"
    typography: "{typography.chip}"
    rounded: "{rounded.pill}"
    padding: "3px 7px"
  expand-well:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.frost}"
    padding: "20px"
  trade-row-hover:
    backgroundColor: "{colors.accent-hover}"
  page-header:
    textColor: "{colors.accent}"
    typography: "{typography.display}"
---

# Design System: Bot Trader Dashboard

## Overview

**Creative North Star: "The After-Hours Desk"**

The dashboard is a GitHub-dark paper-trading desk: one cool canvas, hairline-bordered panels, and the platform system UI stack. It exists to scan equity, exposure, and closed trades after the daily run, not to sell a product. Personality is quiet, dense, and operational. Almost all color sits in graphite until a figure is profit, loss, or the page title.

Visual rejections confirmed by the shipped CSS: no drop shadows, no webfonts, no lifted cards, no decorative illustration. Depth is a 1px stroke and a darker well when a trade row expands. The brand mark is the accent-blue title plus the chart series. Everything else is muted labels and frost values.

**Key Characteristics:**
- Cool graphite surfaces with one Primer-blue accent
- P/L is only green or red, never the accent
- Shared 6px rectangles; pills are side badges only
- System UI stack at every type role
- Expand-row is the detail pattern; compact view hides secondary columns

## Colors

The palette is GitHub Primer dark: a near-black canvas, one step-up panel, iron rules, pewter copy, and a single blue used as title and chart ink.

### Primary
- **After-Hours Blue**: Page title and Chart.js series (equity line, exposure bars). Also the faint hover veil on a closed-trade row. Not used for body copy or P/L.

### Secondary
- **Ledger Green**: Positive realized and unrealized P/L, LONG side chips, winning pair totals.
- **Ledger Red**: Negative P/L, SHORT side chips, Max Drawdown when the value is greater than zero, error text in the loader.
- **Amber Caution**: TP1 HIT chip on an open position. Status, not brand.

### Neutral
- **Night Canvas**: Page background and the open expand well under a trade.
- **Graphite Panel**: Metric cards, chart shells, pair cards, section cards, and control fills.
- **Pewter Ink**: Default body and control text.
- **Frost Value**: KPI figures and expand-summary values.
- **Ash Caption**: Section labels, table headers, sync line, empty states, chart axis ticks.
- **Iron Hairline**: Borders, table row rules, and chart gridlines.

Washes (green, red) sit behind side chips only. They are not card fills. Text selection uses a 30% After-Hours Blue wash on Frost Value text.

**The Accent Scarcity Rule.** After-Hours Blue is title and chart series. It is not a P/L color and not a body-text color.

**The P/L Binary Rule.** Signed money is Ledger Green or Ledger Red. Neutral frost is for unsigned magnitudes (equity, trade count, profit factor). Max Drawdown is Ledger Red only when the value is greater than zero.

## Typography

**Display Font:** System UI (-apple-system, BlinkMacSystemFont, Segoe UI, Helvetica, Arial, sans-serif)
**Body Font:** Same stack
**Label/Mono Font:** None. Tables and chips stay in the same sans.

**Character:** One family. Rank comes from size, weight, uppercase, and tracking, not from a second face.

### Hierarchy
- **Display**: Page title. Accent color. The title is the two words Bot Trader, nothing else.
- **Headline**: KPI numeric line. Frost. Compact viewport steps the size down one notch in CSS, still this role.
- **Body**: Page default and native control text (explicit 16px on select and input so iOS does not zoom).
- **Table**: Closed-trades and positions density. Symbols and signed P/L bump to semibold.
- **Label**: Uppercase section titles, chart captions, and expand-summary keys. Tracking on.
- **Caption**: Sync timestamp, pair-window hint, table column headers (headers also uppercase).
- **Chip**: LONG, SHORT, and TP1 HIT.

### Named Rules
**The System Face Rule.** Do not load a webfont. Every role uses the shipped system stack.

**The Caps Label Rule.** Chrome that names a region (KPI title, chart caption, table header, expand dt) is uppercase and Ash Caption. Values stay sentence case.

## Layout

The page is a single centered column (`max-width: 1300px`) with `--page-pad` 20px, shrinking to 12px at 720px, and safe-area insets on all sides. Vertical rhythm between header, KPI grid, chart band, and section cards is the `xl` gap (20px at compact). Horizontal overflow is clipped on the body; tables scroll inside `.table-scroll` instead.

KPI metrics use `auto-fit` columns with `minmax(min(200px, 100%), 1fr)` and the `md` gutter. At 720px the grid locks to two columns and 10px gutters; `.card-span` on Total Trades spans both columns so it is not an orphan. At 380px it becomes one column.

The chart band is `2fr 1fr` for equity vs exposure, with pair performance spanning the full row as two equal cards. At 900px equity, exposure, then pair cards stack to one column.

The header and the closed-trades filter bar are space-between rows that wrap. At 720px both stack to full width; the strategy select and symbol filter become 100% wide. Strategy select `min-height` is 44px.

History and positions tables sit in a touch-scrolling wrapper. History tables keep `min-width: 560px` so columns can scroll sideways. At 720px, `.col-secondary` is `display: none` on both tables; glanceable columns stay, and the rest lives in the expand panel (history) or is simply omitted (positions). Coarse pointers add extra vertical cell padding. Money, qty, and P/L cells use `tabular-nums` and right alignment. Symbol and Side stay left.

**The Compact Stack Rule.** At 720px: stack header and filter, two-column KPIs with `.card-span` on Total Trades, `--chart-h` 260px, hide secondary table columns, expand well padding 12px, summary grid one column. Do not add a fourth layout breakpoint besides 900px (charts), 720px (compact), and 380px (single KPI).

## Elevation & Depth

The system is flat. There are no `box-shadow` declarations. Stacking is tonal: Night Canvas behind Graphite Panel, Iron Hairline as the edge, and Night Canvas again as the inset well when a trade expands.

### Shadow Vocabulary
None. Chart fill under the equity line is a 5% accent wash, not a drop shadow.

### Named Rules
**The Hairline Depth Rule.** Surfaces are distinguished by a 1px Iron Hairline border, not by shadow or blur. Hover and `:active` on a trade row tint the surface with the blue hover veil; they do not lift.

## Shapes

Default silhouette is a 6px rounded rectangle: metric cards, chart shells, pair cards, selects, inputs, and the close-snapshot image. Side chips are the only pills (10px). Exposure bars use a 4px bar radius in Chart.js. The position P/L track in CSS was unused and has been removed. Do not reintroduce it.

Borders are 1px solid Iron Hairline. Tables collapse borders and drop the last-row rule. The expand well has no extra radius; it is a full-bleed inset under the row.

**The Shared Radius Rule.** New panels and controls use the 6px radius. Pills are for LONG, SHORT, and status chips only.

## Components

There is no button component. Actions are a native select, a native text filter, and clickable table rows.

### Filter controls
- **Shape:** Shared 6px radius, 1px Iron Hairline, Graphite Panel fill.
- **Select:** Strategy switcher in the header. Minimum height 44px. Options render strategy keys as uppercase with underscores turned to spaces.
- **Text filter:** Symbol filter in the closed-trades bar. Width capped at 240px on desktop, full width at compact.
- **Hover / Focus:** Row hover and `:active` use the blue hover veil. Selects, the symbol filter, and the caret toggle use a 2px After-Hours Blue `:focus-visible` outline, offset 2px. No glow, no box-shadow. Cards do not use `overflow: hidden`, so the ring can paint.

### Chips
- **LONG:** Green wash fill, Ledger Green text, pill radius, 10px semibold.
- **SHORT:** Red wash fill, Ledger Red text, same geometry.
- **TP1 HIT:** Amber Caution on a 10% amber wash (`.badge-tp1`). Same badge padding. Use only on open positions that have taken TP1.

### Cards / Containers
- **Metric card:** Graphite Panel, 6px, 15px padding (12px at compact). Muted uppercase title, frost headline value with tabular numerals. Max Drawdown uses Ledger Red on the value only when drawdown is greater than zero.
- **Section card:** Same class as metric cards. Wraps Open Positions and Closed Trades History.
- **Chart panel:** Same fill and radius, 20px padding (14px at compact), height from `--chart-h` (380px, 260px compact). A 12px uppercase Ash Caption sits above the canvas.
- **Pair card:** Tighter 12px padding. Header is title plus an 11px window caption. Nested table is 12px with 10px uppercase headers.
- **Shadow Strategy:** None. See Hairline Depth.
- **Border:** 1px Iron Hairline on every card and chart shell.

### Inputs / Fields
Covered under Filter controls. Placeholder copy is allowed. No error or disabled styles ship.

### Navigation
No site nav. The header is the only chrome: accent display title Bot Trader, Ash Caption sync line, strategy select on the right (stacked on compact). Bottom border is the same 1px hairline as cards. There is no header fill.

### Closed-trades expand row
Signature pattern. A history row stays a table row. The caret in the first cell is the keyboard control (`button.trade-toggle` with `aria-expanded` and `aria-controls`). Clicking the row still toggles on pointer. The caret rotates 90deg over 0.2s when open. Hover and `:active` use the blue hover veil (0.1s background). Toggle opens an adjacent detail row: `max-height` 0 to 2000px over 0.3s ease, Night Canvas well, 20px padding when open (12px and no max-height cap at 720px). Inside: a definition-list summary grid (`auto-fit`, min 140px; one column at 720px) then a lazy-loaded close snapshot (6px image, hairline) or an italic 12px empty message. Only one row is expanded at a time. Chart bytes load from `report_charts.js` on first open, never on first paint.

### Tables
13px, left-aligned labels, 10px cells (8px horizontal at compact). Headers are 11px uppercase Ash Caption. Symbols are semibold Pewter. Signed P/L is semibold Ledger Green or Red, with a smaller percent sibling. Money, qty, days, and P/L columns are right-aligned tabular numerals. Wrap every data table in `.table-scroll`. Empty states are centered Ash Caption with 20px padding.

## Do's and Don'ts

### Do:
- **Do** paint signed P/L and side chips with Ledger Green or Ledger Red, and unsigned KPIs with Frost Value.
- **Do** put new panels on Graphite Panel with a 1px Iron Hairline and the 6px radius.
- **Do** keep region names uppercase Ash Caption and values in sentence case.
- **Do** hide `.col-secondary` at 720px and put extra trade fields in the expand well.
- **Do** wrap wide tables in `.table-scroll` and lazy-load close snapshots only after expand.
- **Do** right-align money, qty, and P/L with tabular numerals. Keep Symbol and Side left.
- **Do** use a 2px After-Hours Blue `:focus-visible` outline on selects, inputs, and the caret toggle.

### Don't:
- **Don't** add drop shadows, backdrop blur, or lifted hover states.
- **Don't** load a display or mono webfont; the system stack is the type system.
- **Don't** use After-Hours Blue for P/L, body copy, or as a card fill.
- **Don't** introduce a primary button. The desk uses select, filter, and row expand.
- **Don't** reintroduce `--header-bg`, a P/L bar, or an Insights subtitle.
- **Don't** put secondary trade columns in the compact table; the expand panel is the detail surface.
- **Don't** paint Max Drawdown red when the value is zero.
