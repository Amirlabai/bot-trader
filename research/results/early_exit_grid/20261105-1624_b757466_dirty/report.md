# Experiment: early_exit_grid

No-progress exit: after N bars, sell at the close if the best high so far is below entry + x R. The trail and initial stop are unchanged. Wide USDT list on Yahoo daily (pairs without Yahoo data are skipped).

- Ran 2026-11-05T16:24:03+00:00 at git b757466 (uncommitted changes)
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
| early7b1r | +203.6R | 72.7R | 2.80 | +57.1R | 22.2R | 25% | +0.58R | 1.80 | 45% | no |
| early7b0.75r | +198.1R | 74.5R | 2.66 | +55.5R | 23.9R | 24% | +0.56R | 1.76 | 45% | no |
| early10b1r | +196.6R | 75.0R | 2.62 | +63.0R | 22.9R | 24% | +0.58R | 1.78 | 45% | yes |
| early3b0.25r | +195.7R | 78.3R | 2.50 | +54.4R | 23.2R | 24% | +0.56R | 1.75 | 45% | no |
| early10b0.75r | +195.2R | 76.4R | 2.56 | +62.0R | 23.9R | 24% | +0.57R | 1.77 | 45% | no |
| early7b0.5r | +193.4R | 77.6R | 2.49 | +62.0R | 23.9R | 24% | +0.57R | 1.76 | 46% | no |
| early10b0.5r | +192.6R | 78.3R | 2.46 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |
| early15b0.75r | +192.4R | 78.3R | 2.46 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |
| early15b1r | +192.4R | 78.3R | 2.46 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |
| early7b0.25r | +192.3R | 78.3R | 2.46 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |
| early5b0.25r | +192.3R | 78.3R | 2.46 | +58.9R | 23.9R | 24% | +0.56R | 1.74 | 46% | no |
| early15b0.5r | +191.6R | 78.3R | 2.45 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |
| early10b0.25r | +191.6R | 78.3R | 2.45 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |
| early15b0.25r | +191.6R | 78.3R | 2.45 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |
| baseline | +191.6R | 78.3R | 2.45 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |
| early2b0.25r | +184.3R | 75.0R | 2.46 | +50.4R | 23.5R | 23% | +0.52R | 1.72 | 45% | no |

1 of 24 variants beat the baseline in both periods.

## Top 15 by in-sample total R

| Variant | IS total | IS max DD | IS total/DD | OOS total | OOS max DD | Win rate | Mean R | PF | Capture | Beats baseline IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | +191.6R | 78.3R | 2.45 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |
| early7b1r | +203.6R | 72.7R | 2.80 | +57.1R | 22.2R | 25% | +0.58R | 1.80 | 45% | no |
| early7b0.75r | +198.1R | 74.5R | 2.66 | +55.5R | 23.9R | 24% | +0.56R | 1.76 | 45% | no |
| early10b1r | +196.6R | 75.0R | 2.62 | +63.0R | 22.9R | 24% | +0.58R | 1.78 | 45% | yes |
| early3b0.25r | +195.7R | 78.3R | 2.50 | +54.4R | 23.2R | 24% | +0.56R | 1.75 | 45% | no |
| early10b0.75r | +195.2R | 76.4R | 2.56 | +62.0R | 23.9R | 24% | +0.57R | 1.77 | 45% | no |
| early7b0.5r | +193.4R | 77.6R | 2.49 | +62.0R | 23.9R | 24% | +0.57R | 1.76 | 46% | no |
| early10b0.5r | +192.6R | 78.3R | 2.46 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |
| early15b1r | +192.4R | 78.3R | 2.46 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |
| early15b0.75r | +192.4R | 78.3R | 2.46 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |
| early7b0.25r | +192.3R | 78.3R | 2.46 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |
| early5b0.25r | +192.3R | 78.3R | 2.46 | +58.9R | 23.9R | 24% | +0.56R | 1.74 | 46% | no |
| early15b0.5r | +191.6R | 78.3R | 2.45 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |
| early15b0.25r | +191.6R | 78.3R | 2.45 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |
| early10b0.25r | +191.6R | 78.3R | 2.45 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |
| early2b0.25r | +184.3R | 75.0R | 2.46 | +50.4R | 23.5R | 23% | +0.52R | 1.72 | 45% | no |

## Top 15 by in-sample return over drawdown

Total R divided by max drawdown. Higher means a smoother equity curve for the same return.

| Variant | IS total | IS max DD | IS total/DD | OOS total | OOS max DD | Win rate | Mean R | PF | Capture | Beats baseline IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | +191.6R | 78.3R | 2.45 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |
| early7b1r | +203.6R | 72.7R | 2.80 | +57.1R | 22.2R | 25% | +0.58R | 1.80 | 45% | no |
| early7b0.75r | +198.1R | 74.5R | 2.66 | +55.5R | 23.9R | 24% | +0.56R | 1.76 | 45% | no |
| early10b1r | +196.6R | 75.0R | 2.62 | +63.0R | 22.9R | 24% | +0.58R | 1.78 | 45% | yes |
| early10b0.75r | +195.2R | 76.4R | 2.56 | +62.0R | 23.9R | 24% | +0.57R | 1.77 | 45% | no |
| early3b0.25r | +195.7R | 78.3R | 2.50 | +54.4R | 23.2R | 24% | +0.56R | 1.75 | 45% | no |
| early7b0.5r | +193.4R | 77.6R | 2.49 | +62.0R | 23.9R | 24% | +0.57R | 1.76 | 46% | no |
| early10b0.5r | +192.6R | 78.3R | 2.46 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |
| early15b1r | +192.4R | 78.3R | 2.46 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |
| early15b0.75r | +192.4R | 78.3R | 2.46 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |
| early7b0.25r | +192.3R | 78.3R | 2.46 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |
| early5b0.25r | +192.3R | 78.3R | 2.46 | +58.9R | 23.9R | 24% | +0.56R | 1.74 | 46% | no |
| early2b0.25r | +184.3R | 75.0R | 2.46 | +50.4R | 23.5R | 23% | +0.52R | 1.72 | 45% | no |
| early15b0.25r | +191.6R | 78.3R | 2.45 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |
| early10b0.25r | +191.6R | 78.3R | 2.45 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |
| early15b0.5r | +191.6R | 78.3R | 2.45 | +62.0R | 23.9R | 24% | +0.57R | 1.75 | 46% | no |

Most same-bar stop/level conflicts in any one variant: 0 bars.
