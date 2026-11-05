# Experiment: filtered_scale_out

Combined retest. Entry filter arms: none and gbm skip 20%. Exit arms: current trail and early exit (7 days, 0.25R), each with and without a scale-out ladder. Tests whether selling off pays once likely false starts are removed. Wide USDT list on Yahoo daily (pairs without Yahoo data are skipped).

- Ran 2026-11-05T16:25:42+00:00 at git b757466 (uncommitted changes)
- 29 pairs, bars 2020-11-05 00:00:00 to 2026-11-04 00:00:00
- Fee 0.10% per side on every fill. All R below is net of fees.
- In-sample: trades opened before 2025-05-04. Out-of-sample: opened after (last 18 months).
- A variant beats the baseline only if its total R is higher in-sample and out-of-sample.
- Same-bar rule: when one bar touches both the stop and a ladder level, the stop fills first.

## Baseline (live daily exit, no scale-out)

- 226 trades, net +41.5R (gross +53.4R), win 21%, mean +0.18R, PF 1.23
- In-sample -20.6R with max drawdown 78.3R; out-of-sample +62.0R with max drawdown 23.9R

Pairs without data (skipped): UNI/USDT

All arms, baseline included, trade only from 2022-05-06 (first walk-forward block), so they cover the same period.

## Entry filters with the current exit

| Variant | IS total | IS max DD | IS total/DD | OOS total | OOS max DD | Win rate | Mean R | PF | Capture | Beats baseline IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| gbm_skip20+baseline | -0.4R | 62.3R | -0.01 | +66.2R | 20.7R | 23% | +0.33R | 1.42 | 44% | yes |
| baseline | -20.6R | 78.3R | -0.26 | +62.0R | 23.9R | 21% | +0.18R | 1.23 | 44% | no |

## Exit variants without a filter (top 15)

| Variant | IS total | IS max DD | IS total/DD | OOS total | OOS max DD | Win rate | Mean R | PF | Capture | Beats baseline IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| early7b0.25r | -19.8R | 78.3R | -0.25 | +62.0R | 23.9R | 21% | +0.19R | 1.24 | 44% | no |
| baseline | -20.6R | 78.3R | -0.26 | +62.0R | 23.9R | 21% | +0.18R | 1.23 | 44% | no |
| early7b0.25r_r3_sell10 | -22.2R | 74.5R | -0.30 | +55.9R | 22.9R | 23% | +0.15R | 1.19 | 41% | no |
| r3_sell10 | -22.9R | 74.5R | -0.31 | +55.9R | 22.9R | 23% | +0.15R | 1.19 | 41% | no |
| early7b0.25r_r1_sell50 | -23.1R | 33.2R | -0.69 | +5.9R | 18.5R | 31% | -0.08R | 0.86 | 30% | no |
| r1_sell50 | -23.8R | 33.2R | -0.72 | +5.9R | 18.5R | 31% | -0.08R | 0.86 | 30% | no |
| early7b0.25r_r3_sell10_plus10 | -24.1R | 73.1R | -0.33 | +53.4R | 22.4R | 23% | +0.13R | 1.17 | 41% | no |
| early7b0.25r_r2_sell10 | -24.1R | 72.0R | -0.33 | +51.3R | 22.9R | 23% | +0.12R | 1.16 | 40% | no |
| early7b0.25r_r3_sell20 | -24.2R | 71.2R | -0.34 | +50.1R | 22.2R | 24% | +0.11R | 1.15 | 40% | no |
| r3_sell10_plus10 | -24.8R | 73.1R | -0.34 | +53.4R | 22.4R | 23% | +0.13R | 1.16 | 41% | no |
| r2_sell10 | -24.8R | 72.0R | -0.34 | +51.3R | 22.9R | 23% | +0.12R | 1.15 | 40% | no |
| r3_sell20 | -24.9R | 71.2R | -0.35 | +50.1R | 22.2R | 24% | +0.11R | 1.14 | 40% | no |
| early7b0.25r_r1_sell10 | -25.4R | 63.5R | -0.40 | +40.5R | 21.6R | 24% | +0.07R | 1.09 | 36% | no |
| early7b0.25r_r3_sell30 | -25.8R | 68.1R | -0.38 | +44.8R | 21.6R | 25% | +0.08R | 1.11 | 40% | no |
| early7b0.25r_r3_sell20_plus10 | -25.9R | 70.1R | -0.37 | +47.8R | 21.8R | 24% | +0.10R | 1.13 | 40% | no |
| r1_sell10 | -26.2R | 63.5R | -0.41 | +40.5R | 21.6R | 24% | +0.06R | 1.09 | 36% | no |

## Entry filter (walk-forward, out-of-sample)

Label `false_start`. First 18 months train only; refit every 3 months on trades closed before each block. The skip threshold is a quantile of training probabilities.

### gbm

- Out-of-sample baseline trades: 226 (false-start rate 50%), entry signals scored: 232
- AUC 0.528 (0.5 = no skill)

| Skip riskiest | Removed | False starts removed | Precision | Winners removed | Winner R removed | R removed | R kept |
|---|---|---|---|---|---|---|---|
| 20% | 24 | 15 of 112 | 62% | 0 | +0.0R | -24.4R | +65.8R |

2 of 75 variants beat the baseline in both periods.

## Top 15 by in-sample total R

| Variant | IS total | IS max DD | IS total/DD | OOS total | OOS max DD | Win rate | Mean R | PF | Capture | Beats baseline IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | -20.6R | 78.3R | -0.26 | +62.0R | 23.9R | 21% | +0.18R | 1.23 | 44% | no |
| gbm_skip20+early7b0.25r | +0.3R | 62.3R | 0.01 | +66.2R | 20.7R | 23% | +0.33R | 1.43 | 44% | yes |
| gbm_skip20+baseline | -0.4R | 62.3R | -0.01 | +66.2R | 20.7R | 23% | +0.33R | 1.42 | 44% | yes |
| gbm_skip20+early7b0.25r_r3_sell10 | -2.4R | 58.9R | -0.04 | +60.1R | 19.8R | 25% | +0.29R | 1.38 | 41% | no |
| gbm_skip20+r3_sell10 | -3.1R | 58.9R | -0.05 | +60.1R | 19.8R | 25% | +0.28R | 1.37 | 41% | no |
| gbm_skip20+early7b0.25r_r3_sell10_plus10 | -4.3R | 57.5R | -0.07 | +57.6R | 19.3R | 25% | +0.26R | 1.35 | 41% | no |
| gbm_skip20+early7b0.25r_r3_sell20 | -4.8R | 55.9R | -0.09 | +54.3R | 19.1R | 27% | +0.25R | 1.33 | 40% | no |
| gbm_skip20+r3_sell10_plus10 | -5.0R | 57.5R | -0.09 | +57.6R | 19.3R | 25% | +0.26R | 1.34 | 41% | no |
| gbm_skip20+early7b0.25r_r2_sell10 | -5.1R | 57.2R | -0.09 | +55.5R | 19.7R | 25% | +0.25R | 1.34 | 40% | no |
| gbm_skip20+r3_sell20 | -5.5R | 55.9R | -0.10 | +54.3R | 19.1R | 27% | +0.24R | 1.32 | 40% | no |
| gbm_skip20+r2_sell10 | -5.8R | 57.2R | -0.10 | +55.5R | 19.7R | 25% | +0.25R | 1.33 | 40% | no |
| gbm_skip20+early7b0.25r_r3_sell20_plus10 | -6.5R | 54.8R | -0.12 | +52.0R | 18.6R | 27% | +0.23R | 1.30 | 40% | no |
| gbm_skip20+early7b0.25r_r3_sell30 | -6.8R | 53.2R | -0.13 | +49.0R | 18.5R | 28% | +0.21R | 1.28 | 41% | no |
| gbm_skip20+r3_sell20_plus10 | -7.2R | 54.8R | -0.13 | +52.0R | 18.6R | 27% | +0.22R | 1.29 | 40% | no |
| gbm_skip20+r3_sell30 | -7.6R | 53.2R | -0.14 | +49.0R | 18.5R | 28% | +0.21R | 1.27 | 41% | no |
| gbm_skip20+early7b0.25r_r1_sell10 | -8.0R | 50.0R | -0.16 | +44.5R | 18.7R | 27% | +0.18R | 1.26 | 36% | no |

## Top 15 by in-sample return over drawdown

Total R divided by max drawdown. Higher means a smoother equity curve for the same return.

| Variant | IS total | IS max DD | IS total/DD | OOS total | OOS max DD | Win rate | Mean R | PF | Capture | Beats baseline IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | -20.6R | 78.3R | -0.26 | +62.0R | 23.9R | 21% | +0.18R | 1.23 | 44% | no |
| gbm_skip20+early7b0.25r | +0.3R | 62.3R | 0.01 | +66.2R | 20.7R | 23% | +0.33R | 1.43 | 44% | yes |
| gbm_skip20+baseline | -0.4R | 62.3R | -0.01 | +66.2R | 20.7R | 23% | +0.33R | 1.42 | 44% | yes |
| gbm_skip20+early7b0.25r_r3_sell10 | -2.4R | 58.9R | -0.04 | +60.1R | 19.8R | 25% | +0.29R | 1.38 | 41% | no |
| gbm_skip20+r3_sell10 | -3.1R | 58.9R | -0.05 | +60.1R | 19.8R | 25% | +0.28R | 1.37 | 41% | no |
| gbm_skip20+early7b0.25r_r3_sell10_plus10 | -4.3R | 57.5R | -0.07 | +57.6R | 19.3R | 25% | +0.26R | 1.35 | 41% | no |
| gbm_skip20+early7b0.25r_r3_sell20 | -4.8R | 55.9R | -0.09 | +54.3R | 19.1R | 27% | +0.25R | 1.33 | 40% | no |
| gbm_skip20+r3_sell10_plus10 | -5.0R | 57.5R | -0.09 | +57.6R | 19.3R | 25% | +0.26R | 1.34 | 41% | no |
| gbm_skip20+early7b0.25r_r2_sell10 | -5.1R | 57.2R | -0.09 | +55.5R | 19.7R | 25% | +0.25R | 1.34 | 40% | no |
| gbm_skip20+r3_sell20 | -5.5R | 55.9R | -0.10 | +54.3R | 19.1R | 27% | +0.24R | 1.32 | 40% | no |
| gbm_skip20+r2_sell10 | -5.8R | 57.2R | -0.10 | +55.5R | 19.7R | 25% | +0.25R | 1.33 | 40% | no |
| gbm_skip20+early7b0.25r_r3_sell20_plus10 | -6.5R | 54.8R | -0.12 | +52.0R | 18.6R | 27% | +0.23R | 1.30 | 40% | no |
| gbm_skip20+early7b0.25r_r3_sell30 | -6.8R | 53.2R | -0.13 | +49.0R | 18.5R | 28% | +0.21R | 1.28 | 41% | no |
| gbm_skip20+r3_sell20_plus10 | -7.2R | 54.8R | -0.13 | +52.0R | 18.6R | 27% | +0.22R | 1.29 | 40% | no |
| gbm_skip20+r3_sell30 | -7.6R | 53.2R | -0.14 | +49.0R | 18.5R | 28% | +0.21R | 1.27 | 41% | no |
| gbm_skip20+early7b0.25r_r1_sell10 | -8.0R | 50.0R | -0.16 | +44.5R | 18.7R | 27% | +0.18R | 1.26 | 36% | no |

## Sell half at every step

| Variant | IS total | IS max DD | IS total/DD | OOS total | OOS max DD | Win rate | Mean R | PF | Capture | Beats baseline IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | -20.6R | 78.3R | -0.26 | +62.0R | 23.9R | 21% | +0.18R | 1.23 | 44% | no |
| r1_sell50 | -23.8R | 33.2R | -0.72 | +5.9R | 18.5R | 31% | -0.08R | 0.86 | 30% | no |
| early7b0.25r_r1_sell50 | -23.1R | 33.2R | -0.69 | +5.9R | 18.5R | 31% | -0.08R | 0.86 | 30% | no |
| gbm_skip20+r1_sell50 | -13.7R | 26.2R | -0.52 | +9.1R | 16.4R | 33% | -0.02R | 0.96 | 29% | no |
| gbm_skip20+early7b0.25r_r1_sell50 | -12.9R | 26.2R | -0.49 | +9.1R | 16.4R | 33% | -0.02R | 0.96 | 29% | no |
| r2_sell50 | -32.8R | 54.7R | -0.60 | +21.9R | 22.4R | 31% | -0.05R | 0.93 | 34% | no |
| early7b0.25r_r2_sell50 | -32.0R | 54.7R | -0.59 | +21.9R | 22.4R | 31% | -0.04R | 0.94 | 34% | no |
| gbm_skip20+r2_sell50 | -18.3R | 44.4R | -0.41 | +26.1R | 19.3R | 33% | +0.04R | 1.05 | 35% | no |
| gbm_skip20+early7b0.25r_r2_sell50 | -17.6R | 44.4R | -0.40 | +26.1R | 19.3R | 33% | +0.04R | 1.06 | 35% | no |
| r3_sell50 | -28.7R | 62.6R | -0.46 | +35.6R | 20.8R | 25% | +0.03R | 1.04 | 44% | no |
| early7b0.25r_r3_sell50 | -27.9R | 62.6R | -0.45 | +35.6R | 20.8R | 25% | +0.03R | 1.04 | 44% | no |
| gbm_skip20+r3_sell50 | -10.5R | 48.6R | -0.22 | +39.8R | 17.7R | 28% | +0.15R | 1.19 | 44% | no |
| gbm_skip20+early7b0.25r_r3_sell50 | -9.7R | 48.6R | -0.20 | +39.8R | 17.7R | 28% | +0.15R | 1.20 | 44% | no |

Most same-bar stop/level conflicts in any one variant: 8 bars.
