# Experiment: structure_entries

Confirmation entries: after the EMA crossover, wait for a close above the signal high or swing high (higher high), or above resistance (swing pivots or the N-bar band high). Each crossed with the current exit and two scale-out ladders. Wide USDT list on Yahoo daily (pairs without Yahoo data are skipped).

- Ran 2026-11-05T16:26:42+00:00 at git b757466 (uncommitted changes)
- 29 pairs, bars 2020-11-05 00:00:00 to 2026-11-04 00:00:00
- Fee 0.10% per side on every fill. All R below is net of fees.
- In-sample: trades opened before 2025-05-04. Out-of-sample: opened after (last 18 months).
- A variant beats the baseline only if its total R is higher in-sample and out-of-sample.
- Same-bar rule: when one bar touches both the stop and a ladder level, the stop fills first.

## Baseline (live daily exit, no scale-out)

- 448 trades, net +253.6R (gross +272.2R), win 24%, mean +0.57R, PF 1.75
- In-sample +191.6R with max drawdown 78.3R; out-of-sample +62.0R with max drawdown 23.9R

Pairs without data (skipped): UNI/USDT

## Exit variants without a filter (top 15)

| Variant | IS total | IS max DD | IS total/DD | OOS total | OOS max DD | Win rate | Mean R | PF | Capture | Beats baseline IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | +191.6R | 78.3R | 2.45 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |
| r3_sell10 | +157.5R | 74.5R | 2.11 | +55.9R | 22.9R | 25% | +0.48R | 1.64 | 44% | no |
| r1_sell50 | +10.0R | 51.3R | 0.20 | +5.9R | 18.5R | 35% | +0.04R | 1.07 | 28% | no |

## Confirmation entries

Blocked and kept are measured against the signal-entry trades with the same exit, matched by the crossover bar. Lift vs random = R of the mode minus its trade count times the signal mean R. A mode beats the signal entry only with higher total R in both periods and positive lift.

### Exit: baseline (0 of 54 modes beat the signal entry)

| Variant | Trades | Losers blocked | False starts blocked | Winners kept | Winner R kept | 3R+ kept | New trades | IS total | OOS total | IS max DD | Lift vs random | Beats signal IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 448 | - | - | - | - | - | - | +191.6R | +62.0R | 78.3R | - | no |
| hh_swing3_w10+baseline | 223 | 66% | 85% | 92% | 92% | 91% | 8 | +164.6R | +71.5R | 25.5R | +109.8R | no |
| res_piv3_L60_w10_skip+baseline | 208 | 69% | 89% | 90% | 92% | 91% | 7 | +154.0R | +60.3R | 26.4R | +96.6R | no |
| hh_sig_w10+baseline | 275 | 51% | 73% | 94% | 95% | 94% | 8 | +153.7R | +49.6R | 36.9R | +47.6R | no |
| res_piv5_L60_w10_skip+baseline | 174 | 78% | 92% | 83% | 88% | 86% | 8 | +152.6R | +51.5R | 20.5R | +105.7R | no |
| res_piv3_L120_w10_skip+baseline | 218 | 66% | 86% | 90% | 92% | 91% | 7 | +152.1R | +50.9R | 29.2R | +79.6R | no |
| res_piv3_L60_w10_enter+baseline | 228 | 65% | 84% | 94% | 94% | 92% | 7 | +151.4R | +58.1R | 25.5R | +80.4R | no |
| res_piv5_L60_w10_enter+baseline | 196 | 72% | 87% | 87% | 90% | 88% | 8 | +148.0R | +49.3R | 21.5R | +86.4R | no |
| res_piv5_L120_w10_skip+baseline | 187 | 75% | 89% | 86% | 90% | 89% | 8 | +147.0R | +44.6R | 22.0R | +85.7R | no |
| res_piv3_L120_w10_enter+baseline | 237 | 62% | 80% | 93% | 93% | 91% | 7 | +144.2R | +48.7R | 30.2R | +58.7R | no |
| res_piv5_L120_w10_enter+baseline | 207 | 70% | 84% | 89% | 91% | 89% | 8 | +138.0R | +42.4R | 23.0R | +63.2R | no |
| hh_sig_w5+baseline | 253 | 56% | 78% | 91% | 90% | 88% | 6 | +132.9R | +19.5R | 33.7R | +9.2R | no |
| res_band_L20_w10+baseline | 219 | 66% | 81% | 87% | 90% | 88% | 8 | +128.8R | +62.2R | 26.9R | +67.0R | no |
| hh_swing3_w5+baseline | 187 | 70% | 88% | 73% | 73% | 69% | 7 | +118.6R | +17.4R | 23.6R | +30.1R | no |
| res_piv3_L60_w5_skip+baseline | 181 | 73% | 92% | 76% | 75% | 75% | 6 | +118.2R | +15.2R | 22.2R | +30.9R | no |
| res_piv3_L60_w5_enter+baseline | 201 | 68% | 87% | 80% | 77% | 77% | 6 | +115.6R | +13.0R | 21.3R | +14.8R | no |

Most losers blocked while keeping at least 80% of winner R:

| Variant | Trades | Losers blocked | False starts blocked | Winners kept | Winner R kept | 3R+ kept | New trades | IS total | OOS total | IS max DD | Lift vs random | Beats signal IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| res_piv5_L60_w10_skip+baseline | 174 | 78% | 92% | 83% | 88% | 86% | 8 | +152.6R | +51.5R | 20.5R | +105.7R | no |
| res_piv5_L120_w10_skip+baseline | 187 | 75% | 89% | 86% | 90% | 89% | 8 | +147.0R | +44.6R | 22.0R | +85.7R | no |
| res_piv5_L60_w10_enter+baseline | 196 | 72% | 87% | 87% | 90% | 88% | 8 | +148.0R | +49.3R | 21.5R | +86.4R | no |
| res_piv5_L120_w10_enter+baseline | 207 | 70% | 84% | 89% | 91% | 89% | 8 | +138.0R | +42.4R | 23.0R | +63.2R | no |
| res_piv3_L60_w10_skip+baseline | 208 | 69% | 89% | 90% | 92% | 91% | 7 | +154.0R | +60.3R | 26.4R | +96.6R | no |
| res_piv3_L120_w10_skip+baseline | 218 | 66% | 86% | 90% | 92% | 91% | 7 | +152.1R | +50.9R | 29.2R | +79.6R | no |
| hh_swing3_w10+baseline | 223 | 66% | 85% | 92% | 92% | 91% | 8 | +164.6R | +71.5R | 25.5R | +109.8R | no |
| res_band_L20_w10+baseline | 219 | 66% | 81% | 87% | 90% | 88% | 8 | +128.8R | +62.2R | 26.9R | +67.0R | no |

### Exit: r1_sell50 (9 of 54 modes beat the signal entry)

| Variant | Trades | Losers blocked | False starts blocked | Winners kept | Winner R kept | 3R+ kept | New trades | IS total | OOS total | IS max DD | Lift vs random | Beats signal IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| r1_sell50 | 448 | - | - | - | - | - | - | +10.0R | +5.9R | 51.3R | - | no |
| res_piv5_L120_w10_skip+r1_sell50 | 187 | 83% | 89% | 81% | 84% | - | 8 | +27.3R | +10.5R | 16.8R | +31.1R | yes |
| res_piv3_L120_w10_skip+r1_sell50 | 218 | 76% | 86% | 89% | 90% | - | 7 | +25.7R | +10.1R | 22.4R | +28.0R | yes |
| res_piv3_L60_w10_skip+r1_sell50 | 208 | 79% | 89% | 88% | 89% | - | 7 | +24.0R | +7.7R | 22.9R | +24.4R | yes |
| res_piv5_L60_w10_skip+r1_sell50 | 174 | 86% | 92% | 79% | 81% | - | 8 | +22.3R | +12.0R | 18.0R | +28.1R | yes |
| res_piv5_L120_w10_enter+r1_sell50 | 207 | 77% | 84% | 84% | 87% | - | 8 | +21.6R | +9.2R | 16.8R | +23.5R | yes |
| res_piv3_L60_w10_enter+r1_sell50 | 228 | 74% | 84% | 91% | 93% | - | 7 | +20.3R | +6.5R | 20.9R | +18.7R | yes |
| res_piv3_L120_w10_enter+r1_sell50 | 237 | 71% | 80% | 91% | 92% | - | 7 | +20.1R | +8.9R | 22.5R | +20.5R | yes |
| res_piv3_L60_w5_skip+r1_sell50 | 181 | 82% | 92% | 77% | 77% | - | 6 | +18.8R | -4.0R | 21.3R | +8.3R | no |
| res_piv3_L120_w5_skip+r1_sell50 | 193 | 79% | 89% | 79% | 79% | - | 6 | +18.4R | +1.2R | 22.9R | +12.8R | no |
| res_piv5_L60_w10_enter+r1_sell50 | 196 | 80% | 87% | 82% | 85% | - | 8 | +17.5R | +10.8R | 16.1R | +21.4R | yes |
| res_piv3_L60_w5_enter+r1_sell50 | 201 | 76% | 87% | 80% | 80% | - | 6 | +15.1R | -5.2R | 19.4R | +2.7R | no |
| res_piv3_L120_w5_enter+r1_sell50 | 212 | 74% | 84% | 82% | 82% | - | 6 | +12.8R | -0.0R | 22.9R | +5.2R | no |
| res_band_L20_w10+r1_sell50 | 219 | 74% | 81% | 85% | 86% | - | 8 | +11.3R | +10.2R | 14.9R | +13.8R | yes |
| res_piv5_L120_w5_skip+r1_sell50 | 145 | 86% | 93% | 62% | 62% | - | 6 | +5.5R | +4.6R | 16.6R | +5.0R | no |
| res_piv5_L60_w5_skip+r1_sell50 | 128 | 89% | 95% | 56% | 56% | - | 6 | +1.3R | +2.5R | 15.7R | -0.8R | no |

Most losers blocked while keeping at least 80% of winner R:

| Variant | Trades | Losers blocked | False starts blocked | Winners kept | Winner R kept | 3R+ kept | New trades | IS total | OOS total | IS max DD | Lift vs random | Beats signal IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| res_piv5_L60_w10_skip+r1_sell50 | 174 | 86% | 92% | 79% | 81% | - | 8 | +22.3R | +12.0R | 18.0R | +28.1R | yes |
| res_piv5_L120_w10_skip+r1_sell50 | 187 | 83% | 89% | 81% | 84% | - | 8 | +27.3R | +10.5R | 16.8R | +31.1R | yes |
| res_piv5_L60_w10_enter+r1_sell50 | 196 | 80% | 87% | 82% | 85% | - | 8 | +17.5R | +10.8R | 16.1R | +21.4R | yes |
| res_piv3_L60_w10_skip+r1_sell50 | 208 | 79% | 89% | 88% | 89% | - | 7 | +24.0R | +7.7R | 22.9R | +24.4R | yes |
| res_piv5_L120_w10_enter+r1_sell50 | 207 | 77% | 84% | 84% | 87% | - | 8 | +21.6R | +9.2R | 16.8R | +23.5R | yes |
| res_piv3_L60_w5_enter+r1_sell50 | 201 | 76% | 87% | 80% | 80% | - | 6 | +15.1R | -5.2R | 19.4R | +2.7R | no |
| res_piv3_L120_w10_skip+r1_sell50 | 218 | 76% | 86% | 89% | 90% | - | 7 | +25.7R | +10.1R | 22.4R | +28.0R | yes |
| hh_swing3_w10+r1_sell50 | 223 | 75% | 85% | 90% | 91% | - | 8 | -2.5R | +16.7R | 23.0R | +6.2R | no |

### Exit: r3_sell10 (0 of 54 modes beat the signal entry)

| Variant | Trades | Losers blocked | False starts blocked | Winners kept | Winner R kept | 3R+ kept | New trades | IS total | OOS total | IS max DD | Lift vs random | Beats signal IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| r3_sell10 | 448 | - | - | - | - | - | - | +157.5R | +55.9R | 74.5R | - | no |
| res_piv3_L60_w10_skip+r3_sell10 | 208 | 70% | 89% | 90% | 91% | 90% | 7 | +134.9R | +53.7R | 27.3R | +89.4R | no |
| hh_swing3_w10+r3_sell10 | 223 | 67% | 85% | 92% | 92% | 90% | 8 | +134.8R | +64.4R | 24.6R | +93.0R | no |
| res_piv3_L120_w10_skip+r3_sell10 | 218 | 67% | 86% | 90% | 91% | 90% | 7 | +134.4R | +47.6R | 29.7R | +78.1R | no |
| res_piv3_L60_w10_enter+r3_sell10 | 228 | 66% | 84% | 94% | 93% | 93% | 7 | +133.6R | +51.5R | 24.7R | +76.4R | no |
| res_piv5_L60_w10_skip+r3_sell10 | 174 | 79% | 92% | 83% | 87% | 84% | 8 | +130.9R | +47.9R | 19.9R | +95.9R | no |
| res_piv3_L120_w10_enter+r3_sell10 | 237 | 63% | 80% | 93% | 92% | 91% | 7 | +127.7R | +45.4R | 30.7R | +60.1R | no |
| res_piv5_L60_w10_enter+r3_sell10 | 196 | 73% | 87% | 87% | 90% | 87% | 8 | +127.6R | +45.7R | 20.9R | +79.9R | no |
| res_piv5_L120_w10_skip+r3_sell10 | 187 | 76% | 89% | 86% | 89% | 88% | 8 | +126.6R | +42.8R | 21.4R | +80.3R | no |
| hh_sig_w10+r3_sell10 | 275 | 52% | 73% | 95% | 95% | 93% | 8 | +126.3R | +46.2R | 37.8R | +41.5R | no |
| res_piv5_L120_w10_enter+r3_sell10 | 207 | 70% | 84% | 88% | 91% | 90% | 8 | +118.9R | +40.6R | 22.4R | +60.9R | no |
| res_band_L20_w10+r3_sell10 | 219 | 67% | 81% | 88% | 89% | 87% | 8 | +111.8R | +55.6R | 26.4R | +63.1R | no |
| hh_sig_w5+r3_sell10 | 253 | 57% | 78% | 90% | 89% | 87% | 6 | +109.5R | +18.6R | 34.7R | +7.5R | no |
| res_piv3_L60_w5_skip+r3_sell10 | 181 | 73% | 92% | 76% | 74% | 74% | 6 | +104.9R | +13.6R | 23.1R | +32.3R | no |
| res_piv3_L60_w5_enter+r3_sell10 | 201 | 69% | 87% | 80% | 77% | 76% | 6 | +103.7R | +11.4R | 20.4R | +19.3R | no |
| res_piv3_L120_w5_skip+r3_sell10 | 193 | 71% | 89% | 79% | 78% | 76% | 6 | +103.4R | +20.1R | 26.5R | +31.5R | no |

Most losers blocked while keeping at least 80% of winner R:

| Variant | Trades | Losers blocked | False starts blocked | Winners kept | Winner R kept | 3R+ kept | New trades | IS total | OOS total | IS max DD | Lift vs random | Beats signal IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| res_piv5_L60_w10_skip+r3_sell10 | 174 | 79% | 92% | 83% | 87% | 84% | 8 | +130.9R | +47.9R | 19.9R | +95.9R | no |
| res_piv5_L120_w10_skip+r3_sell10 | 187 | 76% | 89% | 86% | 89% | 88% | 8 | +126.6R | +42.8R | 21.4R | +80.3R | no |
| res_piv5_L60_w10_enter+r3_sell10 | 196 | 73% | 87% | 87% | 90% | 87% | 8 | +127.6R | +45.7R | 20.9R | +79.9R | no |
| res_piv3_L60_w10_skip+r3_sell10 | 208 | 70% | 89% | 90% | 91% | 90% | 7 | +134.9R | +53.7R | 27.3R | +89.4R | no |
| res_piv5_L120_w10_enter+r3_sell10 | 207 | 70% | 84% | 88% | 91% | 90% | 8 | +118.9R | +40.6R | 22.4R | +60.9R | no |
| res_piv3_L120_w10_skip+r3_sell10 | 218 | 67% | 86% | 90% | 91% | 90% | 7 | +134.4R | +47.6R | 29.7R | +78.1R | no |
| hh_swing3_w10+r3_sell10 | 223 | 67% | 85% | 92% | 92% | 90% | 8 | +134.8R | +64.4R | 24.6R | +93.0R | no |
| res_band_L20_w10+r3_sell10 | 219 | 67% | 81% | 88% | 89% | 87% | 8 | +111.8R | +55.6R | 26.4R | +63.1R | no |

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

0 of 164 variants beat the baseline in both periods.

## Top 15 by in-sample total R

| Variant | IS total | IS max DD | IS total/DD | OOS total | OOS max DD | Win rate | Mean R | PF | Capture | Beats baseline IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | +191.6R | 78.3R | 2.45 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |
| hh_swing3_w10+baseline | +164.6R | 25.5R | 6.45 | +71.5R | 8.8R | 28% | +1.06R | 2.47 | 50% | no |
| r3_sell10 | +157.5R | 74.5R | 2.11 | +55.9R | 22.9R | 25% | +0.48R | 1.64 | 44% | no |
| res_piv3_L60_w10_skip+baseline | +154.0R | 26.4R | 5.83 | +60.3R | 10.7R | 30% | +1.03R | 2.47 | 48% | no |
| hh_sig_w10+baseline | +153.7R | 36.9R | 4.17 | +49.6R | 15.3R | 25% | +0.74R | 1.99 | 47% | no |
| res_piv5_L60_w10_skip+baseline | +152.6R | 20.5R | 7.46 | +51.5R | 9.8R | 33% | +1.17R | 2.74 | 47% | no |
| res_piv3_L120_w10_skip+baseline | +152.1R | 29.2R | 5.22 | +50.9R | 11.9R | 30% | +0.93R | 2.34 | 46% | no |
| res_piv3_L60_w10_enter+baseline | +151.4R | 25.5R | 5.93 | +58.1R | 10.7R | 29% | +0.92R | 2.29 | 47% | no |
| res_piv5_L60_w10_enter+baseline | +148.0R | 21.5R | 6.88 | +49.3R | 9.8R | 32% | +1.01R | 2.45 | 46% | no |
| res_piv5_L120_w10_skip+baseline | +147.0R | 22.0R | 6.68 | +44.6R | 11.4R | 32% | +1.02R | 2.49 | 46% | no |
| res_piv3_L120_w10_enter+baseline | +144.2R | 30.2R | 4.78 | +48.7R | 14.1R | 29% | +0.81R | 2.15 | 46% | no |
| res_piv5_L120_w10_enter+baseline | +138.0R | 23.0R | 5.99 | +42.4R | 13.6R | 30% | +0.87R | 2.24 | 45% | no |
| res_piv3_L60_w10_skip+r3_sell10 | +134.9R | 27.3R | 4.93 | +53.7R | 10.5R | 32% | +0.91R | 2.32 | 45% | no |
| hh_swing3_w10+r3_sell10 | +134.8R | 24.6R | 5.48 | +64.4R | 8.4R | 30% | +0.89R | 2.25 | 45% | no |
| res_piv3_L120_w10_skip+r3_sell10 | +134.4R | 29.7R | 4.52 | +47.6R | 11.6R | 32% | +0.83R | 2.22 | 44% | no |
| res_piv3_L60_w10_enter+r3_sell10 | +133.6R | 24.7R | 5.41 | +51.5R | 10.5R | 31% | +0.81R | 2.16 | 45% | no |

## Top 15 by in-sample return over drawdown

Total R divided by max drawdown. Higher means a smoother equity curve for the same return.

| Variant | IS total | IS max DD | IS total/DD | OOS total | OOS max DD | Win rate | Mean R | PF | Capture | Beats baseline IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | +191.6R | 78.3R | 2.45 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |
| res_piv5_L60_w10_skip+baseline | +152.6R | 20.5R | 7.46 | +51.5R | 9.8R | 33% | +1.17R | 2.74 | 47% | no |
| res_piv5_L60_w10_enter+baseline | +148.0R | 21.5R | 6.88 | +49.3R | 9.8R | 32% | +1.01R | 2.45 | 46% | no |
| res_piv5_L120_w10_skip+baseline | +147.0R | 22.0R | 6.68 | +44.6R | 11.4R | 32% | +1.02R | 2.49 | 46% | no |
| hh_swing3_w1+baseline | +88.7R | 13.3R | 6.67 | +9.2R | 8.9R | 22% | +1.11R | 2.43 | 53% | no |
| res_piv5_L60_w10_skip+r3_sell10 | +130.9R | 19.9R | 6.57 | +47.9R | 9.4R | 35% | +1.03R | 2.54 | 44% | no |
| hh_swing3_w10+baseline | +164.6R | 25.5R | 6.45 | +71.5R | 8.8R | 28% | +1.06R | 2.47 | 50% | no |
| res_piv5_L60_w10_enter+r3_sell10 | +127.6R | 20.9R | 6.09 | +45.7R | 9.4R | 33% | +0.88R | 2.29 | 44% | no |
| res_piv5_L120_w10_enter+baseline | +138.0R | 23.0R | 5.99 | +42.4R | 13.6R | 30% | +0.87R | 2.24 | 45% | no |
| res_piv5_L120_w10_skip+r3_sell10 | +126.6R | 21.4R | 5.93 | +42.8R | 10.6R | 33% | +0.91R | 2.35 | 44% | no |
| res_piv3_L60_w10_enter+baseline | +151.4R | 25.5R | 5.93 | +58.1R | 10.7R | 29% | +0.92R | 2.29 | 47% | no |
| res_piv3_L60_w10_skip+baseline | +154.0R | 26.4R | 5.83 | +60.3R | 10.7R | 30% | +1.03R | 2.47 | 48% | no |
| hh_swing3_w10+r3_sell10 | +134.8R | 24.6R | 5.48 | +64.4R | 8.4R | 30% | +0.89R | 2.25 | 45% | no |
| res_piv3_L60_w5_enter+baseline | +115.6R | 21.3R | 5.43 | +13.0R | 12.9R | 27% | +0.64R | 1.87 | 45% | no |
| res_piv3_L60_w10_enter+r3_sell10 | +133.6R | 24.7R | 5.41 | +51.5R | 10.5R | 31% | +0.81R | 2.16 | 45% | no |
| res_piv3_L60_w5_skip+baseline | +118.2R | 22.2R | 5.33 | +15.2R | 10.7R | 28% | +0.74R | 2.02 | 45% | no |

## Sell half at every step

| Variant | IS total | IS max DD | IS total/DD | OOS total | OOS max DD | Win rate | Mean R | PF | Capture | Beats baseline IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | +191.6R | 78.3R | 2.45 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |
| r1_sell50 | +10.0R | 51.3R | 0.20 | +5.9R | 18.5R | 35% | +0.04R | 1.07 | 28% | no |
| hh_sig_w1+r1_sell50 | -8.6R | 15.3R | -0.56 | +3.1R | 6.0R | 34% | -0.04R | 0.93 | 27% | no |
| hh_sig_w2+r1_sell50 | -15.7R | 31.1R | -0.51 | +1.5R | 7.3R | 33% | -0.07R | 0.88 | 27% | no |
| hh_sig_w3+r1_sell50 | -19.8R | 38.5R | -0.51 | +1.2R | 8.4R | 32% | -0.08R | 0.86 | 27% | no |
| hh_sig_w5+r1_sell50 | -8.4R | 34.4R | -0.24 | +2.5R | 8.4R | 35% | -0.02R | 0.96 | 28% | no |
| hh_sig_w10+r1_sell50 | -7.6R | 37.7R | -0.20 | +9.7R | 9.4R | 36% | +0.01R | 1.01 | 27% | no |
| hh_swing3_w1+r1_sell50 | -3.3R | 10.5R | -0.32 | +1.1R | 3.8R | 35% | -0.03R | 0.96 | 26% | no |
| hh_swing3_w2+r1_sell50 | -15.3R | 21.7R | -0.70 | +1.7R | 3.1R | 32% | -0.10R | 0.84 | 26% | no |
| hh_swing3_w3+r1_sell50 | -19.2R | 27.1R | -0.71 | +1.6R | 3.1R | 32% | -0.11R | 0.82 | 27% | no |
| hh_swing3_w5+r1_sell50 | -10.5R | 24.5R | -0.43 | +3.1R | 3.1R | 35% | -0.04R | 0.93 | 27% | no |
| hh_swing3_w10+r1_sell50 | -2.5R | 23.0R | -0.11 | +16.7R | 4.1R | 38% | +0.06R | 1.12 | 26% | no |
| res_piv3_L60_w2_enter+r1_sell50 | -8.6R | 17.6R | -0.49 | -2.3R | 5.8R | 32% | -0.08R | 0.87 | 26% | no |
| res_piv3_L60_w2_skip+r1_sell50 | -4.9R | 19.6R | -0.25 | -1.1R | 4.6R | 34% | -0.05R | 0.91 | 26% | no |
| res_piv3_L60_w3_enter+r1_sell50 | -7.0R | 21.8R | -0.32 | -4.5R | 8.0R | 33% | -0.07R | 0.88 | 27% | no |
| res_piv3_L60_w3_skip+r1_sell50 | -3.3R | 23.7R | -0.14 | -3.3R | 6.7R | 34% | -0.05R | 0.92 | 27% | no |
| res_piv3_L60_w5_enter+r1_sell50 | +15.1R | 19.4R | 0.78 | -5.2R | 10.1R | 38% | +0.05R | 1.09 | 28% | no |
| res_piv3_L60_w5_skip+r1_sell50 | +18.8R | 21.3R | 0.88 | -4.0R | 8.9R | 39% | +0.08R | 1.15 | 28% | no |
| res_piv3_L60_w10_enter+r1_sell50 | +20.3R | 20.9R | 0.97 | +6.5R | 10.0R | 40% | +0.12R | 1.22 | 27% | no |
| res_piv3_L60_w10_skip+r1_sell50 | +24.0R | 22.9R | 1.05 | +7.7R | 10.0R | 42% | +0.15R | 1.30 | 27% | no |
| res_piv3_L120_w2_enter+r1_sell50 | -10.4R | 19.3R | -0.54 | +1.2R | 6.6R | 33% | -0.06R | 0.90 | 27% | no |
| res_piv3_L120_w2_skip+r1_sell50 | -4.8R | 19.3R | -0.25 | +2.4R | 5.4R | 35% | -0.02R | 0.97 | 27% | no |
| res_piv3_L120_w3_enter+r1_sell50 | -6.9R | 23.5R | -0.30 | +0.8R | 8.4R | 34% | -0.03R | 0.94 | 28% | no |
| res_piv3_L120_w3_skip+r1_sell50 | -1.3R | 23.5R | -0.05 | +2.0R | 7.2R | 36% | +0.00R | 1.01 | 27% | no |
| res_piv3_L120_w5_enter+r1_sell50 | +12.8R | 22.9R | 0.56 | -0.0R | 10.6R | 37% | +0.06R | 1.11 | 28% | no |
| res_piv3_L120_w5_skip+r1_sell50 | +18.4R | 22.9R | 0.81 | +1.2R | 9.3R | 39% | +0.10R | 1.19 | 28% | no |
| res_piv3_L120_w10_enter+r1_sell50 | +20.1R | 22.5R | 0.89 | +8.9R | 10.1R | 40% | +0.12R | 1.24 | 27% | no |
| res_piv3_L120_w10_skip+r1_sell50 | +25.7R | 22.4R | 1.15 | +10.1R | 8.9R | 41% | +0.16R | 1.33 | 27% | no |
| res_piv5_L60_w2_enter+r1_sell50 | -14.5R | 14.8R | -0.98 | +1.8R | 2.3R | 32% | -0.12R | 0.80 | 29% | no |
| res_piv5_L60_w2_skip+r1_sell50 | -9.7R | 15.7R | -0.62 | +3.0R | 1.1R | 35% | -0.08R | 0.87 | 29% | no |
| res_piv5_L60_w3_enter+r1_sell50 | -13.5R | 15.3R | -0.88 | +2.7R | 2.6R | 34% | -0.09R | 0.86 | 30% | no |
| res_piv5_L60_w3_skip+r1_sell50 | -8.7R | 17.1R | -0.51 | +3.9R | 2.1R | 36% | -0.05R | 0.92 | 30% | no |
| res_piv5_L60_w5_enter+r1_sell50 | -3.5R | 13.8R | -0.25 | +1.3R | 5.2R | 36% | -0.01R | 0.98 | 29% | no |
| res_piv5_L60_w5_skip+r1_sell50 | +1.3R | 15.7R | 0.08 | +2.5R | 4.0R | 38% | +0.03R | 1.05 | 29% | no |
| res_piv5_L60_w10_enter+r1_sell50 | +17.5R | 16.1R | 1.09 | +10.8R | 7.3R | 41% | +0.14R | 1.28 | 27% | no |
| res_piv5_L60_w10_skip+r1_sell50 | +22.3R | 18.0R | 1.24 | +12.0R | 7.3R | 43% | +0.20R | 1.39 | 27% | no |
| res_piv5_L120_w2_enter+r1_sell50 | -15.4R | 16.6R | -0.93 | +3.7R | 3.4R | 33% | -0.10R | 0.83 | 29% | no |
| res_piv5_L120_w2_skip+r1_sell50 | -9.7R | 16.6R | -0.59 | +4.9R | 2.2R | 35% | -0.05R | 0.91 | 29% | no |
| res_piv5_L120_w3_enter+r1_sell50 | -12.4R | 17.0R | -0.73 | +6.4R | 3.7R | 35% | -0.04R | 0.92 | 29% | no |
| res_piv5_L120_w3_skip+r1_sell50 | -6.8R | 16.9R | -0.40 | +7.6R | 2.5R | 37% | +0.01R | 1.01 | 29% | no |
| res_piv5_L120_w5_enter+r1_sell50 | -0.2R | 16.6R | -0.01 | +3.4R | 6.9R | 37% | +0.02R | 1.04 | 29% | no |
| res_piv5_L120_w5_skip+r1_sell50 | +5.5R | 16.6R | 0.33 | +4.6R | 5.7R | 39% | +0.07R | 1.13 | 29% | no |
| res_piv5_L120_w10_enter+r1_sell50 | +21.6R | 16.8R | 1.29 | +9.2R | 7.7R | 41% | +0.15R | 1.29 | 28% | no |
| res_piv5_L120_w10_skip+r1_sell50 | +27.3R | 16.8R | 1.63 | +10.5R | 6.4R | 43% | +0.20R | 1.41 | 27% | no |
| res_band_L20_w2+r1_sell50 | -21.1R | 24.5R | -0.86 | +2.5R | 7.0R | 30% | -0.13R | 0.77 | 30% | no |
| res_band_L20_w3+r1_sell50 | -15.6R | 20.8R | -0.75 | +2.5R | 7.0R | 32% | -0.08R | 0.85 | 29% | no |
| res_band_L20_w5+r1_sell50 | -11.1R | 20.6R | -0.54 | +3.2R | 7.0R | 33% | -0.04R | 0.92 | 28% | no |
| res_band_L20_w10+r1_sell50 | +11.3R | 14.9R | 0.76 | +10.2R | 6.2R | 37% | +0.10R | 1.19 | 27% | no |
| res_band_L55_w2+r1_sell50 | -8.7R | 11.3R | -0.77 | +2.4R | 1.2R | 27% | -0.24R | 0.64 | 32% | no |
| res_band_L55_w3+r1_sell50 | -4.8R | 12.9R | -0.37 | +2.4R | 1.2R | 34% | -0.06R | 0.90 | 31% | no |
| res_band_L55_w5+r1_sell50 | -14.2R | 20.1R | -0.70 | -0.8R | 3.3R | 25% | -0.29R | 0.59 | 31% | no |
| res_band_L55_w10+r1_sell50 | -2.6R | 13.2R | -0.19 | +1.7R | 4.0R | 32% | -0.01R | 0.98 | 29% | no |
| res_band_L120_w2+r1_sell50 | -6.5R | 7.2R | -0.91 | +2.4R | 1.1R | 30% | -0.20R | 0.70 | 33% | no |
| res_band_L120_w3+r1_sell50 | -6.7R | 10.8R | -0.62 | +2.4R | 1.1R | 32% | -0.15R | 0.77 | 34% | no |
| res_band_L120_w5+r1_sell50 | -15.0R | 16.7R | -0.89 | -0.8R | 3.3R | 23% | -0.40R | 0.48 | 34% | no |
| res_band_L120_w10+r1_sell50 | -4.6R | 9.7R | -0.48 | +2.0R | 3.7R | 32% | -0.04R | 0.93 | 30% | no |

Most same-bar stop/level conflicts in any one variant: 22 bars.
