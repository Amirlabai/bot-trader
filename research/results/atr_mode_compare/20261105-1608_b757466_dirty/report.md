# Experiment: atr_mode_compare

Trail rule: live (trail_atr x ATR frozen at entry) against asset-trail (current ATR, widened to the initial stop), across trail widths and arm levels.

- Ran 2026-11-05T16:08:05+00:00 at git b757466 (uncommitted changes)
- 14 pairs, bars 2022-11-05 00:00:00 to 2026-11-04 00:00:00
- Fee 0.10% per side on every fill. All R below is net of fees.
- In-sample: trades opened before 2025-11-04. Out-of-sample: opened after (last 12 months).
- A variant beats the baseline only if its total R is higher in-sample and out-of-sample.
- Same-bar rule: when one bar touches both the stop and a ladder level, the stop fills first.

## Baseline (live daily exit, no scale-out)

- 189 trades, net +120.3R (gross +132.0R), win 26%, mean +0.64R, PF 1.85
- In-sample +75.7R with max drawdown 44.3R; out-of-sample +44.7R with max drawdown 7.5R

Pairs without data (skipped): HYPE/USDT

## Exit variants without a filter (top 15)

| Variant | IS total | IS max DD | IS total/DD | OOS total | OOS max DD | Win rate | Mean R | PF | Capture | Beats baseline IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| atrcurrent_trail4 | +222.9R | 24.0R | 9.31 | +13.4R | 14.4R | 22% | +1.48R | 2.83 | 42% | no |
| trail4 | +106.4R | 35.1R | 3.03 | +42.2R | 7.7R | 24% | +0.84R | 2.07 | 47% | no |
| atrcurrent | +105.0R | 34.9R | 3.01 | +34.0R | 7.5R | 24% | +0.76R | 1.99 | 42% | no |
| baseline | +75.7R | 44.3R | 1.71 | +44.7R | 7.5R | 26% | +0.64R | 1.85 | 46% | no |
| arm0.5 | +75.7R | 44.3R | 1.71 | +44.7R | 7.5R | 26% | +0.64R | 1.85 | 46% | no |
| arm1 | +75.7R | 44.3R | 1.71 | +44.7R | 7.5R | 26% | +0.64R | 1.85 | 46% | no |
| arm2 | +75.7R | 44.3R | 1.71 | +44.7R | 7.5R | 26% | +0.64R | 1.85 | 46% | no |
| trail2 | +59.3R | 36.5R | 1.62 | +15.1R | 7.1R | 31% | +0.38R | 1.56 | 44% | no |
| atrcurrent_trail2 | +55.6R | 41.0R | 1.36 | +27.9R | 8.1R | 30% | +0.43R | 1.62 | 40% | no |

0 of 8 variants beat the baseline in both periods.

## Top 15 by in-sample total R

| Variant | IS total | IS max DD | IS total/DD | OOS total | OOS max DD | Win rate | Mean R | PF | Capture | Beats baseline IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | +75.7R | 44.3R | 1.71 | +44.7R | 7.5R | 26% | +0.64R | 1.85 | 46% | no |
| atrcurrent_trail4 | +222.9R | 24.0R | 9.31 | +13.4R | 14.4R | 22% | +1.48R | 2.83 | 42% | no |
| trail4 | +106.4R | 35.1R | 3.03 | +42.2R | 7.7R | 24% | +0.84R | 2.07 | 47% | no |
| atrcurrent | +105.0R | 34.9R | 3.01 | +34.0R | 7.5R | 24% | +0.76R | 1.99 | 42% | no |
| arm0.5 | +75.7R | 44.3R | 1.71 | +44.7R | 7.5R | 26% | +0.64R | 1.85 | 46% | no |
| arm1 | +75.7R | 44.3R | 1.71 | +44.7R | 7.5R | 26% | +0.64R | 1.85 | 46% | no |
| arm2 | +75.7R | 44.3R | 1.71 | +44.7R | 7.5R | 26% | +0.64R | 1.85 | 46% | no |
| trail2 | +59.3R | 36.5R | 1.62 | +15.1R | 7.1R | 31% | +0.38R | 1.56 | 44% | no |
| atrcurrent_trail2 | +55.6R | 41.0R | 1.36 | +27.9R | 8.1R | 30% | +0.43R | 1.62 | 40% | no |

## Top 15 by in-sample return over drawdown

Total R divided by max drawdown. Higher means a smoother equity curve for the same return.

| Variant | IS total | IS max DD | IS total/DD | OOS total | OOS max DD | Win rate | Mean R | PF | Capture | Beats baseline IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | +75.7R | 44.3R | 1.71 | +44.7R | 7.5R | 26% | +0.64R | 1.85 | 46% | no |
| atrcurrent_trail4 | +222.9R | 24.0R | 9.31 | +13.4R | 14.4R | 22% | +1.48R | 2.83 | 42% | no |
| trail4 | +106.4R | 35.1R | 3.03 | +42.2R | 7.7R | 24% | +0.84R | 2.07 | 47% | no |
| atrcurrent | +105.0R | 34.9R | 3.01 | +34.0R | 7.5R | 24% | +0.76R | 1.99 | 42% | no |
| arm0.5 | +75.7R | 44.3R | 1.71 | +44.7R | 7.5R | 26% | +0.64R | 1.85 | 46% | no |
| arm1 | +75.7R | 44.3R | 1.71 | +44.7R | 7.5R | 26% | +0.64R | 1.85 | 46% | no |
| arm2 | +75.7R | 44.3R | 1.71 | +44.7R | 7.5R | 26% | +0.64R | 1.85 | 46% | no |
| trail2 | +59.3R | 36.5R | 1.62 | +15.1R | 7.1R | 31% | +0.38R | 1.56 | 44% | no |
| atrcurrent_trail2 | +55.6R | 41.0R | 1.36 | +27.9R | 8.1R | 30% | +0.43R | 1.62 | 40% | no |

Most same-bar stop/level conflicts in any one variant: 0 bars.
