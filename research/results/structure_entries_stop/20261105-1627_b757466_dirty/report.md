# Experiment: structure_entries_stop

Same confirmation levels as structure_entries, but bought with a buy-stop order resting at the level (fills intrabar at the level, or at the open on a gap) instead of waiting for a close above it. The signal stop is kept. The fill bar is stepped stop-first, so a same-bar reversal is a loss. Wide USDT list on Yahoo daily (pairs without Yahoo data are skipped).

- Ran 2026-11-05T16:27:21+00:00 at git b757466 (uncommitted changes)
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

### Exit: baseline (0 of 38 modes beat the signal entry)

| Variant | Trades | Losers blocked | False starts blocked | Winners kept | Winner R kept | 3R+ kept | New trades | IS total | OOS total | IS max DD | Lift vs random | Beats signal IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 448 | - | - | - | - | - | - | +191.6R | +62.0R | 78.3R | - | no |
| hh_sig_w5_stop+baseline | 356 | 26% | 38% | 93% | 94% | 91% | 3 | +150.3R | +34.6R | 51.9R | -16.6R | no |
| hh_sig_w10_stop+baseline | 366 | 24% | 36% | 95% | 96% | 94% | 4 | +146.7R | +44.9R | 54.3R | -15.5R | no |
| hh_sig_w1_stop+baseline | 289 | 40% | 50% | 75% | 78% | 73% | 3 | +143.2R | +25.9R | 54.3R | +5.5R | no |
| hh_sig_w3_stop+baseline | 344 | 27% | 39% | 88% | 88% | 83% | 2 | +142.1R | +35.7R | 49.8R | -17.0R | no |
| hh_sig_w2_stop+baseline | 332 | 29% | 41% | 82% | 85% | 80% | 2 | +136.0R | +33.4R | 48.8R | -18.5R | no |
| res_piv3_L60_w10_enter_stop+baseline | 285 | 48% | 64% | 95% | 96% | 94% | 5 | +134.8R | +30.3R | 36.1R | +3.8R | no |
| res_piv3_L120_w10_enter_stop+baseline | 298 | 44% | 60% | 95% | 96% | 94% | 4 | +126.4R | +38.8R | 43.5R | -3.5R | no |
| res_piv3_L60_w5_enter_stop+baseline | 266 | 51% | 66% | 86% | 88% | 84% | 5 | +126.3R | +20.2R | 31.0R | -4.1R | no |
| res_piv3_L120_w5_enter_stop+baseline | 282 | 46% | 61% | 88% | 89% | 86% | 4 | +116.6R | +28.7R | 39.4R | -14.4R | no |
| hh_swing3_w10_stop+baseline | 298 | 44% | 58% | 94% | 95% | 92% | 6 | +115.7R | +33.3R | 41.0R | -19.7R | no |
| res_piv3_L60_w3_enter_stop+baseline | 239 | 54% | 68% | 72% | 71% | 69% | 3 | +110.9R | +12.4R | 29.7R | -12.0R | no |
| res_piv5_L60_w10_enter_stop+baseline | 238 | 61% | 75% | 91% | 94% | 92% | 7 | +105.3R | +17.1R | 26.0R | -12.3R | no |
| hh_swing3_w5_stop+baseline | 276 | 46% | 59% | 80% | 84% | 77% | 6 | +100.6R | +18.9R | 45.4R | -36.6R | no |
| res_piv3_L120_w3_enter_stop+baseline | 260 | 49% | 63% | 76% | 75% | 72% | 4 | +100.0R | +28.8R | 37.9R | -18.4R | no |
| res_piv5_L120_w10_enter_stop+baseline | 251 | 57% | 72% | 92% | 95% | 92% | 7 | +98.3R | +32.3R | 33.8R | -11.5R | no |

Most losers blocked while keeping at least 80% of winner R:

| Variant | Trades | Losers blocked | False starts blocked | Winners kept | Winner R kept | 3R+ kept | New trades | IS total | OOS total | IS max DD | Lift vs random | Beats signal IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| res_piv5_L60_w10_enter_stop+baseline | 238 | 61% | 75% | 91% | 94% | 92% | 7 | +105.3R | +17.1R | 26.0R | -12.3R | no |
| res_piv5_L120_w10_enter_stop+baseline | 251 | 57% | 72% | 92% | 95% | 92% | 7 | +98.3R | +32.3R | 33.8R | -11.5R | no |
| res_band_L20_w10_stop+baseline | 263 | 54% | 71% | 91% | 93% | 91% | 8 | +79.9R | +37.0R | 47.2R | -32.0R | no |
| res_piv3_L60_w5_enter_stop+baseline | 266 | 51% | 66% | 86% | 88% | 84% | 5 | +126.3R | +20.2R | 31.0R | -4.1R | no |
| res_piv3_L60_w10_enter_stop+baseline | 285 | 48% | 64% | 95% | 96% | 94% | 5 | +134.8R | +30.3R | 36.1R | +3.8R | no |
| res_piv3_L120_w5_enter_stop+baseline | 282 | 46% | 61% | 88% | 89% | 86% | 4 | +116.6R | +28.7R | 39.4R | -14.4R | no |
| hh_swing3_w5_stop+baseline | 276 | 46% | 59% | 80% | 84% | 77% | 6 | +100.6R | +18.9R | 45.4R | -36.6R | no |
| hh_swing3_w10_stop+baseline | 298 | 44% | 58% | 94% | 95% | 92% | 6 | +115.7R | +33.3R | 41.0R | -19.7R | no |

### Exit: r1_sell50 (5 of 38 modes beat the signal entry)

| Variant | Trades | Losers blocked | False starts blocked | Winners kept | Winner R kept | 3R+ kept | New trades | IS total | OOS total | IS max DD | Lift vs random | Beats signal IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| r1_sell50 | 448 | - | - | - | - | - | - | +10.0R | +5.9R | 51.3R | - | no |
| res_piv5_L60_w10_enter_stop+r1_sell50 | 238 | 69% | 75% | 88% | 90% | - | 7 | +45.7R | +6.9R | 20.2R | +44.1R | yes |
| res_piv3_L60_w5_enter_stop+r1_sell50 | 266 | 57% | 66% | 86% | 87% | - | 5 | +45.2R | +3.1R | 23.0R | +38.9R | no |
| res_piv3_L60_w10_enter_stop+r1_sell50 | 285 | 55% | 64% | 94% | 95% | - | 5 | +45.2R | +10.6R | 28.1R | +45.6R | yes |
| res_piv5_L120_w10_enter_stop+r1_sell50 | 251 | 65% | 72% | 89% | 91% | - | 7 | +42.3R | +11.0R | 22.3R | +44.4R | yes |
| res_piv3_L120_w10_enter_stop+r1_sell50 | 298 | 51% | 60% | 95% | 95% | - | 4 | +40.9R | +12.9R | 28.3R | +43.2R | yes |
| res_piv3_L120_w5_enter_stop+r1_sell50 | 282 | 53% | 61% | 89% | 88% | - | 4 | +40.8R | +5.5R | 25.7R | +36.2R | no |
| res_band_L20_w10_stop+r1_sell50 | 263 | 62% | 71% | 91% | 91% | - | 8 | +40.7R | +10.7R | 20.7R | +42.0R | yes |
| res_piv3_L60_w3_enter_stop+r1_sell50 | 239 | 60% | 68% | 75% | 74% | - | 3 | +36.1R | -0.9R | 21.7R | +26.7R | no |
| res_piv5_L60_w5_enter_stop+r1_sell50 | 206 | 70% | 77% | 71% | 71% | - | 6 | +34.5R | +2.2R | 17.6R | +29.4R | no |
| res_piv5_L120_w5_enter_stop+r1_sell50 | 223 | 66% | 73% | 74% | 75% | - | 6 | +31.0R | +5.7R | 22.0R | +28.7R | no |
| res_piv3_L60_w2_enter_stop+r1_sell50 | 221 | 62% | 70% | 69% | 67% | - | 3 | +30.7R | +0.1R | 19.4R | +23.0R | no |
| res_piv3_L120_w3_enter_stop+r1_sell50 | 260 | 55% | 63% | 79% | 78% | - | 4 | +29.7R | +4.6R | 26.3R | +25.0R | no |
| res_band_L20_w5_stop+r1_sell50 | 231 | 64% | 72% | 75% | 73% | - | 7 | +27.5R | +4.9R | 25.2R | +24.2R | no |
| res_piv5_L60_w3_enter_stop+r1_sell50 | 177 | 72% | 79% | 59% | 58% | - | 2 | +24.7R | -1.7R | 15.2R | +16.8R | no |
| res_piv3_L120_w2_enter_stop+r1_sell50 | 243 | 57% | 65% | 73% | 71% | - | 3 | +22.3R | +3.8R | 27.3R | +17.3R | no |

Most losers blocked while keeping at least 80% of winner R:

| Variant | Trades | Losers blocked | False starts blocked | Winners kept | Winner R kept | 3R+ kept | New trades | IS total | OOS total | IS max DD | Lift vs random | Beats signal IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| res_piv5_L60_w10_enter_stop+r1_sell50 | 238 | 69% | 75% | 88% | 90% | - | 7 | +45.7R | +6.9R | 20.2R | +44.1R | yes |
| res_piv5_L120_w10_enter_stop+r1_sell50 | 251 | 65% | 72% | 89% | 91% | - | 7 | +42.3R | +11.0R | 22.3R | +44.4R | yes |
| res_band_L20_w10_stop+r1_sell50 | 263 | 62% | 71% | 91% | 91% | - | 8 | +40.7R | +10.7R | 20.7R | +42.0R | yes |
| res_piv3_L60_w5_enter_stop+r1_sell50 | 266 | 57% | 66% | 86% | 87% | - | 5 | +45.2R | +3.1R | 23.0R | +38.9R | no |
| res_piv3_L60_w10_enter_stop+r1_sell50 | 285 | 55% | 64% | 94% | 95% | - | 5 | +45.2R | +10.6R | 28.1R | +45.6R | yes |
| res_piv3_L120_w5_enter_stop+r1_sell50 | 282 | 53% | 61% | 89% | 88% | - | 4 | +40.8R | +5.5R | 25.7R | +36.2R | no |
| hh_swing3_w5_stop+r1_sell50 | 276 | 51% | 59% | 81% | 81% | - | 6 | +1.2R | +8.5R | 42.1R | -0.1R | no |
| res_piv3_L120_w10_enter_stop+r1_sell50 | 298 | 51% | 60% | 95% | 95% | - | 4 | +40.9R | +12.9R | 28.3R | +43.2R | yes |

### Exit: r3_sell10 (0 of 38 modes beat the signal entry)

| Variant | Trades | Losers blocked | False starts blocked | Winners kept | Winner R kept | 3R+ kept | New trades | IS total | OOS total | IS max DD | Lift vs random | Beats signal IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| r3_sell10 | 448 | - | - | - | - | - | - | +157.5R | +55.9R | 74.5R | - | no |
| hh_sig_w5_stop+r3_sell10 | 356 | 26% | 38% | 92% | 94% | 90% | 3 | +125.2R | +34.0R | 52.6R | -10.4R | no |
| res_piv3_L60_w10_enter_stop+r3_sell10 | 285 | 49% | 64% | 96% | 96% | 94% | 5 | +124.2R | +29.4R | 35.6R | +17.8R | no |
| hh_sig_w10_stop+r3_sell10 | 366 | 24% | 36% | 96% | 95% | 93% | 4 | +121.7R | +44.0R | 55.1R | -8.7R | no |
| hh_sig_w1_stop+r3_sell10 | 289 | 40% | 50% | 74% | 77% | 74% | 3 | +118.7R | +26.5R | 52.7R | +7.5R | no |
| res_piv3_L60_w5_enter_stop+r3_sell10 | 266 | 51% | 66% | 86% | 88% | 84% | 5 | +117.6R | +19.1R | 30.5R | +9.9R | no |
| res_piv3_L120_w10_enter_stop+r3_sell10 | 298 | 44% | 60% | 96% | 96% | 94% | 4 | +115.9R | +37.3R | 43.2R | +11.3R | no |
| hh_sig_w3_stop+r3_sell10 | 344 | 27% | 39% | 88% | 87% | 82% | 2 | +115.6R | +35.1R | 50.6R | -13.2R | no |
| hh_sig_w2_stop+r3_sell10 | 332 | 29% | 41% | 82% | 84% | 79% | 2 | +109.6R | +32.7R | 49.6R | -15.9R | no |
| res_piv3_L120_w5_enter_stop+r3_sell10 | 282 | 47% | 61% | 88% | 88% | 85% | 4 | +107.9R | +27.1R | 39.1R | +0.6R | no |
| res_piv5_L60_w10_enter_stop+r3_sell10 | 238 | 62% | 75% | 91% | 94% | 91% | 7 | +102.7R | +17.0R | 25.7R | +6.3R | no |
| res_piv3_L60_w3_enter_stop+r3_sell10 | 239 | 54% | 68% | 73% | 70% | 68% | 3 | +102.2R | +11.5R | 29.2R | -0.2R | no |
| res_piv5_L120_w10_enter_stop+r3_sell10 | 251 | 58% | 72% | 92% | 94% | 93% | 7 | +95.7R | +31.6R | 33.9R | +7.7R | no |
| hh_swing3_w10_stop+r3_sell10 | 298 | 44% | 58% | 94% | 94% | 91% | 6 | +93.3R | +33.3R | 41.3R | -15.5R | no |
| res_piv3_L120_w3_enter_stop+r3_sell10 | 260 | 49% | 63% | 76% | 74% | 72% | 4 | +91.3R | +27.2R | 37.6R | -5.4R | no |
| res_piv3_L60_w2_enter_stop+r3_sell10 | 221 | 57% | 70% | 65% | 63% | 60% | 3 | +87.7R | +12.5R | 28.7R | -5.1R | no |

Most losers blocked while keeping at least 80% of winner R:

| Variant | Trades | Losers blocked | False starts blocked | Winners kept | Winner R kept | 3R+ kept | New trades | IS total | OOS total | IS max DD | Lift vs random | Beats signal IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| res_piv5_L60_w10_enter_stop+r3_sell10 | 238 | 62% | 75% | 91% | 94% | 91% | 7 | +102.7R | +17.0R | 25.7R | +6.3R | no |
| res_piv5_L120_w10_enter_stop+r3_sell10 | 251 | 58% | 72% | 92% | 94% | 93% | 7 | +95.7R | +31.6R | 33.9R | +7.7R | no |
| res_band_L20_w10_stop+r3_sell10 | 263 | 55% | 71% | 91% | 92% | 90% | 8 | +75.4R | +35.2R | 44.7R | -14.8R | no |
| res_piv3_L60_w5_enter_stop+r3_sell10 | 266 | 51% | 66% | 86% | 88% | 84% | 5 | +117.6R | +19.1R | 30.5R | +9.9R | no |
| res_piv3_L60_w10_enter_stop+r3_sell10 | 285 | 49% | 64% | 96% | 96% | 94% | 5 | +124.2R | +29.4R | 35.6R | +17.8R | no |
| res_piv3_L120_w5_enter_stop+r3_sell10 | 282 | 47% | 61% | 88% | 88% | 85% | 4 | +107.9R | +27.1R | 39.1R | +0.6R | no |
| hh_swing3_w5_stop+r3_sell10 | 276 | 46% | 59% | 80% | 83% | 76% | 6 | +79.8R | +18.9R | 45.6R | -32.8R | no |
| res_piv3_L120_w10_enter_stop+r3_sell10 | 298 | 44% | 60% | 96% | 96% | 94% | 4 | +115.9R | +37.3R | 43.2R | +11.3R | no |

0 of 116 variants beat the baseline in both periods.

## Top 15 by in-sample total R

| Variant | IS total | IS max DD | IS total/DD | OOS total | OOS max DD | Win rate | Mean R | PF | Capture | Beats baseline IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | +191.6R | 78.3R | 2.45 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |
| r3_sell10 | +157.5R | 74.5R | 2.11 | +55.9R | 22.9R | 25% | +0.48R | 1.64 | 44% | no |
| hh_sig_w5_stop+baseline | +150.3R | 51.9R | 2.90 | +34.6R | 14.4R | 27% | +0.52R | 1.73 | 47% | no |
| hh_sig_w10_stop+baseline | +146.7R | 54.3R | 2.70 | +44.9R | 13.4R | 27% | +0.52R | 1.74 | 48% | no |
| hh_sig_w1_stop+baseline | +143.2R | 54.3R | 2.64 | +25.9R | 9.3R | 27% | +0.59R | 1.83 | 46% | no |
| hh_sig_w3_stop+baseline | +142.1R | 49.8R | 2.85 | +35.7R | 14.0R | 26% | +0.52R | 1.72 | 47% | no |
| hh_sig_w2_stop+baseline | +136.0R | 48.8R | 2.79 | +33.4R | 11.0R | 25% | +0.51R | 1.70 | 47% | no |
| res_piv3_L60_w10_enter_stop+baseline | +134.8R | 36.1R | 3.74 | +30.3R | 11.0R | 34% | +0.58R | 1.94 | 47% | no |
| res_piv3_L120_w10_enter_stop+baseline | +126.4R | 43.5R | 2.90 | +38.8R | 9.7R | 33% | +0.55R | 1.88 | 47% | no |
| res_piv3_L60_w5_enter_stop+baseline | +126.3R | 31.0R | 4.08 | +20.2R | 11.8R | 32% | +0.55R | 1.88 | 46% | no |
| hh_sig_w5_stop+r3_sell10 | +125.2R | 52.6R | 2.38 | +34.0R | 13.2R | 28% | +0.45R | 1.64 | 46% | no |
| res_piv3_L60_w10_enter_stop+r3_sell10 | +124.2R | 35.6R | 3.49 | +29.4R | 10.7R | 34% | +0.54R | 1.88 | 47% | no |
| hh_sig_w10_stop+r3_sell10 | +121.7R | 55.1R | 2.21 | +44.0R | 12.2R | 28% | +0.45R | 1.65 | 47% | no |
| hh_sig_w1_stop+r3_sell10 | +118.7R | 52.7R | 2.25 | +26.5R | 8.1R | 28% | +0.50R | 1.72 | 45% | no |
| res_piv3_L60_w5_enter_stop+r3_sell10 | +117.6R | 30.5R | 3.85 | +19.1R | 11.6R | 33% | +0.51R | 1.83 | 47% | no |
| res_piv3_L120_w5_enter_stop+baseline | +116.6R | 39.4R | 2.96 | +28.7R | 11.0R | 31% | +0.51R | 1.80 | 46% | no |

## Top 15 by in-sample return over drawdown

Total R divided by max drawdown. Higher means a smoother equity curve for the same return.

| Variant | IS total | IS max DD | IS total/DD | OOS total | OOS max DD | Win rate | Mean R | PF | Capture | Beats baseline IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | +191.6R | 78.3R | 2.45 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |
| res_band_L55_w10_stop+r1_sell50 | +18.1R | 3.1R | 5.73 | +1.7R | 5.3R | 48% | +0.20R | 1.53 | 43% | no |
| res_band_L55_w10_stop+r3_sell10 | +20.8R | 4.1R | 5.01 | +1.1R | 7.3R | 44% | +0.22R | 1.50 | 42% | no |
| res_band_L55_w10_stop+baseline | +19.4R | 4.1R | 4.69 | +1.2R | 7.3R | 44% | +0.21R | 1.47 | 42% | no |
| res_piv3_L60_w5_enter_stop+baseline | +126.3R | 31.0R | 4.08 | +20.2R | 11.8R | 32% | +0.55R | 1.88 | 46% | no |
| res_piv5_L60_w10_enter_stop+baseline | +105.3R | 26.0R | 4.05 | +17.1R | 8.9R | 38% | +0.51R | 1.90 | 46% | no |
| res_piv5_L60_w10_enter_stop+r3_sell10 | +102.7R | 25.7R | 3.99 | +17.0R | 8.6R | 38% | +0.50R | 1.89 | 46% | no |
| res_piv3_L60_w5_enter_stop+r3_sell10 | +117.6R | 30.5R | 3.85 | +19.1R | 11.6R | 33% | +0.51R | 1.83 | 47% | no |
| res_piv3_L60_w3_enter_stop+baseline | +110.9R | 29.7R | 3.74 | +12.4R | 13.6R | 31% | +0.52R | 1.79 | 46% | no |
| res_piv3_L60_w10_enter_stop+baseline | +134.8R | 36.1R | 3.74 | +30.3R | 11.0R | 34% | +0.58R | 1.94 | 47% | no |
| res_piv5_L60_w5_enter_stop+r3_sell10 | +77.0R | 22.0R | 3.50 | +10.3R | 9.1R | 35% | +0.42R | 1.71 | 46% | no |
| res_piv3_L60_w3_enter_stop+r3_sell10 | +102.2R | 29.2R | 3.50 | +11.5R | 13.4R | 31% | +0.48R | 1.73 | 46% | no |
| res_piv3_L60_w10_enter_stop+r3_sell10 | +124.2R | 35.6R | 3.49 | +29.4R | 10.7R | 34% | +0.54R | 1.88 | 47% | no |
| res_piv5_L60_w5_enter_stop+baseline | +76.6R | 22.3R | 3.43 | +10.6R | 9.3R | 35% | +0.42R | 1.70 | 46% | no |
| res_piv3_L60_w2_enter_stop+baseline | +96.1R | 30.3R | 3.17 | +13.4R | 12.6R | 29% | +0.50R | 1.74 | 46% | no |
| res_piv3_L60_w2_enter_stop+r3_sell10 | +87.7R | 28.7R | 3.05 | +12.5R | 12.4R | 30% | +0.45R | 1.69 | 46% | no |

## Sell half at every step

| Variant | IS total | IS max DD | IS total/DD | OOS total | OOS max DD | Win rate | Mean R | PF | Capture | Beats baseline IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | +191.6R | 78.3R | 2.45 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |
| r1_sell50 | +10.0R | 51.3R | 0.20 | +5.9R | 18.5R | 35% | +0.04R | 1.07 | 28% | no |
| hh_sig_w1_stop+r1_sell50 | +8.8R | 34.2R | 0.26 | +13.0R | 5.2R | 39% | +0.08R | 1.15 | 29% | no |
| hh_sig_w2_stop+r1_sell50 | -9.1R | 53.7R | -0.17 | +11.8R | 6.2R | 36% | +0.01R | 1.02 | 29% | no |
| hh_sig_w3_stop+r1_sell50 | -4.9R | 53.3R | -0.09 | +11.9R | 8.2R | 37% | +0.02R | 1.04 | 29% | no |
| hh_sig_w5_stop+r1_sell50 | +4.2R | 54.9R | 0.08 | +10.8R | 8.2R | 38% | +0.04R | 1.08 | 30% | no |
| hh_sig_w10_stop+r1_sell50 | +2.5R | 57.4R | 0.04 | +14.7R | 8.2R | 39% | +0.05R | 1.09 | 30% | no |
| hh_swing3_w1_stop+r1_sell50 | -6.8R | 27.0R | -0.25 | +6.7R | 3.2R | 37% | -0.00R | 1.00 | 30% | no |
| hh_swing3_w2_stop+r1_sell50 | -16.0R | 40.8R | -0.39 | +4.8R | 4.5R | 36% | -0.05R | 0.91 | 30% | no |
| hh_swing3_w3_stop+r1_sell50 | -9.0R | 38.7R | -0.23 | +3.6R | 4.5R | 38% | -0.02R | 0.96 | 30% | no |
| hh_swing3_w5_stop+r1_sell50 | +1.2R | 42.1R | 0.03 | +8.5R | 4.2R | 40% | +0.04R | 1.07 | 32% | no |
| hh_swing3_w10_stop+r1_sell50 | +8.6R | 40.9R | 0.21 | +18.4R | 5.1R | 43% | +0.09R | 1.18 | 33% | no |
| res_piv3_L60_w2_enter_stop+r1_sell50 | +30.7R | 19.4R | 1.59 | +0.1R | 8.9R | 43% | +0.14R | 1.29 | 31% | no |
| res_piv3_L60_w3_enter_stop+r1_sell50 | +36.1R | 21.7R | 1.66 | -0.9R | 9.9R | 44% | +0.15R | 1.31 | 31% | no |
| res_piv3_L60_w5_enter_stop+r1_sell50 | +45.2R | 23.0R | 1.97 | +3.1R | 8.5R | 46% | +0.18R | 1.39 | 32% | no |
| res_piv3_L60_w10_enter_stop+r1_sell50 | +45.2R | 28.1R | 1.61 | +10.6R | 8.0R | 47% | +0.20R | 1.43 | 33% | no |
| res_piv3_L120_w2_enter_stop+r1_sell50 | +22.3R | 27.3R | 0.81 | +3.8R | 6.8R | 42% | +0.11R | 1.22 | 31% | no |
| res_piv3_L120_w3_enter_stop+r1_sell50 | +29.7R | 26.3R | 1.13 | +4.6R | 7.8R | 43% | +0.13R | 1.27 | 31% | no |
| res_piv3_L120_w5_enter_stop+r1_sell50 | +40.8R | 25.7R | 1.59 | +5.5R | 8.1R | 45% | +0.16R | 1.34 | 32% | no |
| res_piv3_L120_w10_enter_stop+r1_sell50 | +40.9R | 28.3R | 1.44 | +12.9R | 7.3R | 46% | +0.18R | 1.38 | 33% | no |
| res_piv5_L60_w2_enter_stop+r1_sell50 | +16.3R | 12.0R | 1.36 | -2.3R | 7.1R | 43% | +0.09R | 1.18 | 32% | no |
| res_piv5_L60_w3_enter_stop+r1_sell50 | +24.7R | 15.2R | 1.63 | -1.7R | 8.1R | 44% | +0.13R | 1.27 | 33% | no |
| res_piv5_L60_w5_enter_stop+r1_sell50 | +34.5R | 17.6R | 1.96 | +2.2R | 8.0R | 46% | +0.18R | 1.38 | 34% | no |
| res_piv5_L60_w10_enter_stop+r1_sell50 | +45.7R | 20.2R | 2.26 | +6.9R | 7.9R | 49% | +0.22R | 1.49 | 35% | no |
| res_piv5_L120_w2_enter_stop+r1_sell50 | +10.4R | 19.7R | 0.53 | +1.1R | 6.4R | 41% | +0.07R | 1.13 | 32% | no |
| res_piv5_L120_w3_enter_stop+r1_sell50 | +18.8R | 19.9R | 0.95 | +3.7R | 7.0R | 42% | +0.11R | 1.23 | 32% | no |
| res_piv5_L120_w5_enter_stop+r1_sell50 | +31.0R | 22.0R | 1.41 | +5.7R | 7.4R | 45% | +0.16R | 1.34 | 33% | no |
| res_piv5_L120_w10_enter_stop+r1_sell50 | +42.3R | 22.3R | 1.90 | +11.0R | 6.2R | 48% | +0.21R | 1.47 | 35% | no |
| res_band_L20_w2_stop+r1_sell50 | +14.3R | 17.4R | 0.82 | +0.1R | 6.8R | 43% | +0.08R | 1.18 | 29% | no |
| res_band_L20_w3_stop+r1_sell50 | +14.8R | 21.5R | 0.69 | -0.9R | 6.8R | 42% | +0.07R | 1.15 | 30% | no |
| res_band_L20_w5_stop+r1_sell50 | +27.5R | 25.2R | 1.09 | +4.9R | 5.4R | 45% | +0.14R | 1.30 | 32% | no |
| res_band_L20_w10_stop+r1_sell50 | +40.7R | 20.7R | 1.97 | +10.7R | 7.1R | 48% | +0.20R | 1.45 | 34% | no |
| res_band_L55_w2_stop+r1_sell50 | +2.1R | 4.7R | 0.44 | +0.9R | 2.2R | 39% | +0.08R | 1.17 | 36% | no |
| res_band_L55_w3_stop+r1_sell50 | +6.3R | 4.8R | 1.30 | +0.9R | 2.2R | 45% | +0.15R | 1.35 | 40% | no |
| res_band_L55_w5_stop+r1_sell50 | +8.7R | 3.7R | 2.37 | -2.2R | 4.0R | 45% | +0.10R | 1.22 | 40% | no |
| res_band_L55_w10_stop+r1_sell50 | +18.1R | 3.1R | 5.73 | +1.7R | 5.3R | 48% | +0.20R | 1.53 | 43% | no |
| res_band_L120_w2_stop+r1_sell50 | -3.3R | 5.0R | -0.67 | +1.7R | 1.1R | 40% | -0.07R | 0.87 | 35% | no |
| res_band_L120_w3_stop+r1_sell50 | -1.7R | 5.7R | -0.30 | +1.7R | 1.1R | 45% | -0.00R | 1.00 | 40% | no |
| res_band_L120_w5_stop+r1_sell50 | -0.1R | 6.0R | -0.02 | -1.3R | 2.9R | 43% | -0.03R | 0.94 | 40% | no |
| res_band_L120_w10_stop+r1_sell50 | +9.9R | 4.0R | 2.46 | +1.7R | 4.7R | 52% | +0.15R | 1.38 | 42% | no |

Most same-bar stop/level conflicts in any one variant: 14 bars.
