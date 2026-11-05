# Experiment: structure_audit

Loser audit: price structure at each baseline signal (resistance, open air, band breakout, later higher close). Wide USDT list on Yahoo daily (pairs without Yahoo data are skipped).

- Ran 2026-11-05T16:25:53+00:00 at git b757466 (uncommitted changes)
- 29 pairs, bars 2020-11-05 00:00:00 to 2026-11-04 00:00:00
- Fee 0.10% per side on every fill. All R below is net of fees.
- In-sample: trades opened before 2025-05-04. Out-of-sample: opened after (last 18 months).
- A variant beats the baseline only if its total R is higher in-sample and out-of-sample.
- Same-bar rule: when one bar touches both the stop and a ladder level, the stop fills first.

## Baseline (live daily exit, no scale-out)

- 448 trades, net +253.6R (gross +272.2R), win 24%, mean +0.57R, PF 1.75
- In-sample +191.6R with max drawdown 78.3R; out-of-sample +62.0R with max drawdown 23.9R

Pairs without data (skipped): UNI/USDT

## Loser audit (price structure at the signal bar)

448 baseline trades: 108 winners, 340 losers, 215 false starts, 64 of 3R or more. Mean +0.57R.

### Share of each group by structure

| Condition | All | Winners | Losers | False starts | 3R+ | Mean R |
|---|---|---|---|---|---|---|
| Open air (no swing high above) | 4% | 3% | 5% | 5% | 0% | -0.53R |
| Resistance within 1 ATR | 66% | 74% | 63% | 61% | 75% | +0.72R |
| Resistance 1 to 3 ATR | 27% | 21% | 29% | 29% | 22% | +0.44R |
| Resistance 3+ ATR | 3% | 2% | 4% | 4% | 3% | -0.15R |
| Resistance touched 2+ times | 49% | 56% | 46% | 44% | 61% | +0.92R |
| Close above 20-bar high | 14% | 11% | 15% | 14% | 6% | -0.09R |
| Close above 55-bar high | 3% | 3% | 3% | 2% | 2% | -0.03R |
| Higher close within 1 bars (look-ahead) | 30% | 52% | 23% | 9% | 50% | +1.91R |
| Higher close within 2 bars (look-ahead) | 44% | 70% | 35% | 17% | 69% | +1.68R |
| Higher close within 3 bars (look-ahead) | 51% | 81% | 41% | 20% | 81% | +1.59R |
| Higher close within 6 bars (look-ahead) | 61% | 99% | 49% | 28% | 98% | +1.56R |
| Higher close within 12 bars (look-ahead) | 71% | 100% | 62% | 46% | 100% | +1.21R |

### Would block

Look-ahead rows use later bars, so they are not tradable as written. They show the most a wait-for-a-higher-high rule could achieve before paying the higher entry price, which the confirmation-entry experiment measures.

| Rule | Blocked | Losers blocked | False starts blocked | Winners kept | Winner R kept | 3R+ kept | R kept | Lift vs random |
|---|---|---|---|---|---|---|---|---|
| Block unless open air | 429 | 95% | 95% | 3% | 1% | 0% | -10.1R | -20.9R |
| Block if resistance within 1 ATR | 295 | 63% | 61% | 26% | 28% | 25% | +40.2R | -46.4R |
| Block if resistance within 2 ATR | 392 | 86% | 85% | 6% | 5% | 6% | -21.5R | -53.2R |
| Block if resistance touched 2+ times | 219 | 46% | 44% | 44% | 40% | 39% | +52.5R | -77.1R |
| Block unless close above 20-bar high | 384 | 85% | 86% | 11% | 8% | 6% | -5.5R | -41.7R |
| Block unless close above 55-bar high | 436 | 97% | 98% | 3% | 2% | 2% | -0.4R | -7.2R |
| Block unless higher close within 1 bars (look-ahead ceiling) | 314 | 77% | 91% | 52% | 56% | 50% | +256.5R | +180.7R |
| Block unless higher close within 2 bars (look-ahead ceiling) | 252 | 65% | 83% | 70% | 75% | 69% | +330.1R | +219.1R |
| Block unless higher close within 3 bars (look-ahead ceiling) | 219 | 59% | 80% | 81% | 84% | 81% | +363.4R | +233.8R |
| Block unless higher close within 6 bars (look-ahead ceiling) | 174 | 51% | 72% | 99% | 99% | 98% | +426.4R | +271.3R |
| Block unless higher close within 12 bars (look-ahead ceiling) | 129 | 38% | 54% | 100% | 100% | 100% | +387.5R | +206.9R |
