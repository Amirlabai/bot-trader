# Experiment: false_start_filter

Walk-forward entry filter. A model trained only on earlier closed trades scores each entry signal; the riskiest share of entries is skipped. Label false_start = closed at the initial stop and never reached +1R. Wide USDT list on Yahoo daily (pairs without Yahoo data are skipped).

- Ran 2026-11-05T16:24:20+00:00 at git b757466 (uncommitted changes)
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
| gbm_skip30+baseline | -0.1R | 56.6R | -0.00 | +61.4R | 19.1R | 24% | +0.35R | 1.45 | 42% | no |
| gbm_skip20+baseline | -0.4R | 62.3R | -0.01 | +66.2R | 20.7R | 23% | +0.33R | 1.42 | 44% | yes |
| logistic_skip10+baseline | -3.1R | 68.1R | -0.05 | +63.2R | 21.8R | 23% | +0.29R | 1.37 | 44% | yes |
| gbm_skip50+baseline | -3.5R | 34.8R | -0.10 | +44.1R | 14.3R | 25% | +0.35R | 1.48 | 42% | no |
| logistic_skip20+baseline | -7.6R | 66.0R | -0.12 | +67.4R | 20.6R | 23% | +0.32R | 1.42 | 43% | yes |
| gbm_skip40+baseline | -11.0R | 47.9R | -0.23 | +53.0R | 14.7R | 24% | +0.28R | 1.38 | 41% | no |
| gbm_skip10+baseline | -11.7R | 73.6R | -0.16 | +62.0R | 23.9R | 22% | +0.23R | 1.29 | 44% | no |
| logistic_skip40+baseline | -13.7R | 44.2R | -0.31 | +69.0R | 13.7R | 26% | +0.41R | 1.56 | 40% | yes |
| baseline | -20.6R | 78.3R | -0.26 | +62.0R | 23.9R | 21% | +0.18R | 1.23 | 44% | no |
| logistic_skip50+baseline | -24.6R | 32.3R | -0.76 | +62.5R | 11.1R | 28% | +0.35R | 1.49 | 37% | no |
| logistic_skip30+baseline | -27.6R | 58.2R | -0.47 | +73.3R | 16.3R | 24% | +0.27R | 1.35 | 41% | no |

## Entry filter (walk-forward, out-of-sample)

Label `false_start`. First 18 months train only; refit every 3 months on trades closed before each block. The skip threshold is a quantile of training probabilities.

### logistic

- Out-of-sample baseline trades: 226 (false-start rate 50%), entry signals scored: 232
- AUC 0.613 (0.5 = no skill)

| Skip riskiest | Removed | False starts removed | Precision | Winners removed | Winner R removed | R removed | R kept |
|---|---|---|---|---|---|---|---|
| 10% | 18 | 11 of 112 | 61% | 0 | +0.0R | -18.6R | +60.1R |
| 20% | 39 | 25 of 112 | 64% | 4 | +18.1R | -18.3R | +59.8R |
| 30% | 58 | 34 of 112 | 59% | 8 | +47.8R | -3.8R | +45.3R |
| 40% | 94 | 60 of 112 | 64% | 13 | +69.2R | -13.8R | +55.2R |
| 50% | 119 | 71 of 112 | 60% | 18 | +109.2R | +6.5R | +35.0R |

Logistic weights (standardized; positive = more likely a false start, last refit):

- trend_ext_atr: +0.86
- btc_above_trend: -0.42
- ret_6_bars: +0.38
- ret_30_bars: -0.35
- atr_change_30: +0.27
- ext_ema300_atr: -0.26
- cross_gap_atr: -0.25
- dist_high_50_atr: +0.24
- trend_slope_pct: -0.20
- btc_ret_30: -0.19

### gbm

- Out-of-sample baseline trades: 226 (false-start rate 50%), entry signals scored: 232
- AUC 0.528 (0.5 = no skill)

| Skip riskiest | Removed | False starts removed | Precision | Winners removed | Winner R removed | R removed | R kept |
|---|---|---|---|---|---|---|---|
| 10% | 9 | 7 of 112 | 78% | 0 | +0.0R | -8.9R | +50.3R |
| 20% | 24 | 15 of 112 | 62% | 0 | +0.0R | -24.4R | +65.8R |
| 30% | 49 | 27 of 112 | 55% | 5 | +24.9R | -19.8R | +61.3R |
| 40% | 78 | 41 of 112 | 53% | 11 | +67.6R | -0.5R | +42.0R |
| 50% | 111 | 58 of 112 | 52% | 18 | +95.5R | +0.9R | +40.6R |

4 of 10 variants beat the baseline in both periods.

## Top 15 by in-sample total R

| Variant | IS total | IS max DD | IS total/DD | OOS total | OOS max DD | Win rate | Mean R | PF | Capture | Beats baseline IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | -20.6R | 78.3R | -0.26 | +62.0R | 23.9R | 21% | +0.18R | 1.23 | 44% | no |
| gbm_skip30+baseline | -0.1R | 56.6R | -0.00 | +61.4R | 19.1R | 24% | +0.35R | 1.45 | 42% | no |
| gbm_skip20+baseline | -0.4R | 62.3R | -0.01 | +66.2R | 20.7R | 23% | +0.33R | 1.42 | 44% | yes |
| logistic_skip10+baseline | -3.1R | 68.1R | -0.05 | +63.2R | 21.8R | 23% | +0.29R | 1.37 | 44% | yes |
| gbm_skip50+baseline | -3.5R | 34.8R | -0.10 | +44.1R | 14.3R | 25% | +0.35R | 1.48 | 42% | no |
| logistic_skip20+baseline | -7.6R | 66.0R | -0.12 | +67.4R | 20.6R | 23% | +0.32R | 1.42 | 43% | yes |
| gbm_skip40+baseline | -11.0R | 47.9R | -0.23 | +53.0R | 14.7R | 24% | +0.28R | 1.38 | 41% | no |
| gbm_skip10+baseline | -11.7R | 73.6R | -0.16 | +62.0R | 23.9R | 22% | +0.23R | 1.29 | 44% | no |
| logistic_skip40+baseline | -13.7R | 44.2R | -0.31 | +69.0R | 13.7R | 26% | +0.41R | 1.56 | 40% | yes |
| logistic_skip50+baseline | -24.6R | 32.3R | -0.76 | +62.5R | 11.1R | 28% | +0.35R | 1.49 | 37% | no |
| logistic_skip30+baseline | -27.6R | 58.2R | -0.47 | +73.3R | 16.3R | 24% | +0.27R | 1.35 | 41% | no |

## Top 15 by in-sample return over drawdown

Total R divided by max drawdown. Higher means a smoother equity curve for the same return.

| Variant | IS total | IS max DD | IS total/DD | OOS total | OOS max DD | Win rate | Mean R | PF | Capture | Beats baseline IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | -20.6R | 78.3R | -0.26 | +62.0R | 23.9R | 21% | +0.18R | 1.23 | 44% | no |
| gbm_skip30+baseline | -0.1R | 56.6R | -0.00 | +61.4R | 19.1R | 24% | +0.35R | 1.45 | 42% | no |
| gbm_skip20+baseline | -0.4R | 62.3R | -0.01 | +66.2R | 20.7R | 23% | +0.33R | 1.42 | 44% | yes |
| logistic_skip10+baseline | -3.1R | 68.1R | -0.05 | +63.2R | 21.8R | 23% | +0.29R | 1.37 | 44% | yes |
| gbm_skip50+baseline | -3.5R | 34.8R | -0.10 | +44.1R | 14.3R | 25% | +0.35R | 1.48 | 42% | no |
| logistic_skip20+baseline | -7.6R | 66.0R | -0.12 | +67.4R | 20.6R | 23% | +0.32R | 1.42 | 43% | yes |
| gbm_skip10+baseline | -11.7R | 73.6R | -0.16 | +62.0R | 23.9R | 22% | +0.23R | 1.29 | 44% | no |
| gbm_skip40+baseline | -11.0R | 47.9R | -0.23 | +53.0R | 14.7R | 24% | +0.28R | 1.38 | 41% | no |
| logistic_skip40+baseline | -13.7R | 44.2R | -0.31 | +69.0R | 13.7R | 26% | +0.41R | 1.56 | 40% | yes |
| logistic_skip30+baseline | -27.6R | 58.2R | -0.47 | +73.3R | 16.3R | 24% | +0.27R | 1.35 | 41% | no |
| logistic_skip50+baseline | -24.6R | 32.3R | -0.76 | +62.5R | 11.1R | 28% | +0.35R | 1.49 | 37% | no |

Most same-bar stop/level conflicts in any one variant: 0 bars.
