# Experiment: tp1_vs_trail

Live TP1 wallet (50% at entry + 1 entry ATR, stop to entry, then trail) against the live asset-trail wallet, plus ladder equivalents.

- Ran 2026-11-05T16:07:56+00:00 at git b757466 (uncommitted changes)
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
| baseline | +75.7R | 44.3R | 1.71 | +44.7R | 7.5R | 26% | +0.64R | 1.85 | 46% | no |
| tp1_tp1x30 | +60.5R | 20.9R | 2.89 | +20.2R | 7.0R | 51% | +0.41R | 1.78 | 26% | no |
| tp1 | +40.3R | 19.4R | 2.08 | +14.7R | 6.6R | 51% | +0.28R | 1.53 | 31% | no |
| r1_sell50_max1_be | +37.5R | 20.7R | 1.82 | +13.6R | 6.6R | 49% | +0.26R | 1.48 | 31% | no |

0 of 3 variants beat the baseline in both periods.

## Top 15 by in-sample total R

| Variant | IS total | IS max DD | IS total/DD | OOS total | OOS max DD | Win rate | Mean R | PF | Capture | Beats baseline IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | +75.7R | 44.3R | 1.71 | +44.7R | 7.5R | 26% | +0.64R | 1.85 | 46% | no |
| tp1_tp1x30 | +60.5R | 20.9R | 2.89 | +20.2R | 7.0R | 51% | +0.41R | 1.78 | 26% | no |
| tp1 | +40.3R | 19.4R | 2.08 | +14.7R | 6.6R | 51% | +0.28R | 1.53 | 31% | no |
| r1_sell50_max1_be | +37.5R | 20.7R | 1.82 | +13.6R | 6.6R | 49% | +0.26R | 1.48 | 31% | no |

## Top 15 by in-sample return over drawdown

Total R divided by max drawdown. Higher means a smoother equity curve for the same return.

| Variant | IS total | IS max DD | IS total/DD | OOS total | OOS max DD | Win rate | Mean R | PF | Capture | Beats baseline IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | +75.7R | 44.3R | 1.71 | +44.7R | 7.5R | 26% | +0.64R | 1.85 | 46% | no |
| tp1_tp1x30 | +60.5R | 20.9R | 2.89 | +20.2R | 7.0R | 51% | +0.41R | 1.78 | 26% | no |
| tp1 | +40.3R | 19.4R | 2.08 | +14.7R | 6.6R | 51% | +0.28R | 1.53 | 31% | no |
| r1_sell50_max1_be | +37.5R | 20.7R | 1.82 | +13.6R | 6.6R | 49% | +0.26R | 1.48 | 31% | no |

## Sell half at every step

| Variant | IS total | IS max DD | IS total/DD | OOS total | OOS max DD | Win rate | Mean R | PF | Capture | Beats baseline IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | +75.7R | 44.3R | 1.71 | +44.7R | 7.5R | 26% | +0.64R | 1.85 | 46% | no |
| r1_sell50_max1_be | +37.5R | 20.7R | 1.82 | +13.6R | 6.6R | 49% | +0.26R | 1.48 | 31% | no |

Most same-bar stop/level conflicts in any one variant: 3 bars.
