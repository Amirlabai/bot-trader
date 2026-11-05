# Experiment: scale_out_grid

Scale-out ladder in R. At each level sell a share of what is still held: a constant share swept in 10% steps (50% = keep selling half), or a share that rises at each level. The remainder keeps the live 3x entry-ATR trail.

- Ran 2026-11-05T16:07:38+00:00 at git b757466 (uncommitted changes)
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
| r3_sell10 | +64.7R | 42.3R | 1.53 | +37.7R | 7.5R | 28% | +0.54R | 1.74 | 43% | no |
| r3_sell10_plus5 | +61.7R | 41.6R | 1.48 | +34.8R | 7.5R | 28% | +0.51R | 1.69 | 43% | no |
| r3_sell10_plus10 | +58.7R | 40.9R | 1.44 | +32.0R | 7.5R | 28% | +0.48R | 1.65 | 43% | no |
| r2_sell10 | +57.5R | 41.0R | 1.40 | +33.3R | 7.5R | 27% | +0.48R | 1.66 | 42% | no |
| r3_sell20 | +54.9R | 40.7R | 1.35 | +32.0R | 7.5R | 30% | +0.46R | 1.63 | 41% | no |
| r3_sell10_plus20 | +54.3R | 39.8R | 1.36 | +27.1R | 7.5R | 28% | +0.43R | 1.58 | 43% | no |
| r3_sell10_be | +53.0R | 41.9R | 1.27 | +38.2R | 7.5R | 30% | +0.48R | 1.66 | 39% | no |
| r3_sell20_plus5 | +52.5R | 40.1R | 1.31 | +29.7R | 7.5R | 30% | +0.43R | 1.59 | 41% | no |
| r1.5_sell10_be | +52.5R | 28.0R | 1.88 | +27.7R | 7.4R | 40% | +0.42R | 1.67 | 28% | no |
| r1_sell10_be | +51.9R | 22.1R | 2.35 | +15.4R | 7.4R | 46% | +0.34R | 1.63 | 23% | no |
| r1.5_sell10 | +51.9R | 39.1R | 1.33 | +30.2R | 7.2R | 29% | +0.43R | 1.61 | 40% | no |
| r2_sell10_be | +51.8R | 35.5R | 1.46 | +33.0R | 7.5R | 35% | +0.45R | 1.65 | 33% | no |
| r3_sell20_plus10 | +50.3R | 39.6R | 1.27 | +27.5R | 7.5R | 30% | +0.41R | 1.56 | 41% | no |
| r3_sell10_plus5_be | +50.0R | 41.1R | 1.22 | +35.3R | 7.5R | 30% | +0.45R | 1.62 | 39% | no |
| r2_sell10_plus5 | +49.6R | 39.6R | 1.25 | +26.7R | 7.5R | 27% | +0.40R | 1.56 | 42% | no |

0 of 180 variants beat the baseline in both periods.

## Top 15 by in-sample total R

| Variant | IS total | IS max DD | IS total/DD | OOS total | OOS max DD | Win rate | Mean R | PF | Capture | Beats baseline IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | +75.7R | 44.3R | 1.71 | +44.7R | 7.5R | 26% | +0.64R | 1.85 | 46% | no |
| r3_sell10 | +64.7R | 42.3R | 1.53 | +37.7R | 7.5R | 28% | +0.54R | 1.74 | 43% | no |
| r3_sell10_plus5 | +61.7R | 41.6R | 1.48 | +34.8R | 7.5R | 28% | +0.51R | 1.69 | 43% | no |
| r3_sell10_plus10 | +58.7R | 40.9R | 1.44 | +32.0R | 7.5R | 28% | +0.48R | 1.65 | 43% | no |
| r2_sell10 | +57.5R | 41.0R | 1.40 | +33.3R | 7.5R | 27% | +0.48R | 1.66 | 42% | no |
| r3_sell20 | +54.9R | 40.7R | 1.35 | +32.0R | 7.5R | 30% | +0.46R | 1.63 | 41% | no |
| r3_sell10_plus20 | +54.3R | 39.8R | 1.36 | +27.1R | 7.5R | 28% | +0.43R | 1.58 | 43% | no |
| r3_sell10_be | +53.0R | 41.9R | 1.27 | +38.2R | 7.5R | 30% | +0.48R | 1.66 | 39% | no |
| r3_sell20_plus5 | +52.5R | 40.1R | 1.31 | +29.7R | 7.5R | 30% | +0.43R | 1.59 | 41% | no |
| r1.5_sell10_be | +52.5R | 28.0R | 1.88 | +27.7R | 7.4R | 40% | +0.42R | 1.67 | 28% | no |
| r1_sell10_be | +51.9R | 22.1R | 2.35 | +15.4R | 7.4R | 46% | +0.34R | 1.63 | 23% | no |
| r1.5_sell10 | +51.9R | 39.1R | 1.33 | +30.2R | 7.2R | 29% | +0.43R | 1.61 | 40% | no |
| r2_sell10_be | +51.8R | 35.5R | 1.46 | +33.0R | 7.5R | 35% | +0.45R | 1.65 | 33% | no |
| r3_sell20_plus10 | +50.3R | 39.6R | 1.27 | +27.5R | 7.5R | 30% | +0.41R | 1.56 | 41% | no |
| r3_sell10_plus5_be | +50.0R | 41.1R | 1.22 | +35.3R | 7.5R | 30% | +0.45R | 1.62 | 39% | no |
| r2_sell10_plus5 | +49.6R | 39.6R | 1.25 | +26.7R | 7.5R | 27% | +0.40R | 1.56 | 42% | no |

## Top 15 by in-sample return over drawdown

Total R divided by max drawdown. Higher means a smoother equity curve for the same return.

| Variant | IS total | IS max DD | IS total/DD | OOS total | OOS max DD | Win rate | Mean R | PF | Capture | Beats baseline IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | +75.7R | 44.3R | 1.71 | +44.7R | 7.5R | 26% | +0.64R | 1.85 | 46% | no |
| r1_sell10_be | +51.9R | 22.1R | 2.35 | +15.4R | 7.4R | 46% | +0.34R | 1.63 | 23% | no |
| r1.5_sell10_be | +52.5R | 28.0R | 1.88 | +27.7R | 7.4R | 40% | +0.42R | 1.67 | 28% | no |
| r1_sell10_plus5_be | +33.6R | 20.9R | 1.61 | +8.0R | 7.4R | 47% | +0.21R | 1.39 | 24% | no |
| r1.5_sell10_plus5_be | +40.9R | 26.4R | 1.55 | +17.6R | 7.4R | 40% | +0.30R | 1.49 | 28% | no |
| r3_sell10 | +64.7R | 42.3R | 1.53 | +37.7R | 7.5R | 28% | +0.54R | 1.74 | 43% | no |
| r3_sell10_plus5 | +61.7R | 41.6R | 1.48 | +34.8R | 7.5R | 28% | +0.51R | 1.69 | 43% | no |
| r2_sell10_be | +51.8R | 35.5R | 1.46 | +33.0R | 7.5R | 35% | +0.45R | 1.65 | 33% | no |
| r1_sell20_be | +30.2R | 21.0R | 1.44 | +8.8R | 7.2R | 49% | +0.20R | 1.37 | 25% | no |
| r3_sell10_plus10 | +58.7R | 40.9R | 1.44 | +32.0R | 7.5R | 28% | +0.48R | 1.65 | 43% | no |
| r1.5_sell20_be | +36.5R | 25.9R | 1.41 | +18.0R | 7.2R | 41% | +0.28R | 1.46 | 30% | no |
| r2_sell10 | +57.5R | 41.0R | 1.40 | +33.3R | 7.5R | 27% | +0.48R | 1.66 | 42% | no |
| r1.5_sell10_plus10_be | +35.3R | 25.8R | 1.37 | +13.5R | 7.4R | 40% | +0.25R | 1.41 | 29% | no |
| r3_sell10_plus20 | +54.3R | 39.8R | 1.36 | +27.1R | 7.5R | 28% | +0.43R | 1.58 | 43% | no |
| r3_sell20 | +54.9R | 40.7R | 1.35 | +32.0R | 7.5R | 30% | +0.46R | 1.63 | 41% | no |
| r1.5_sell10 | +51.9R | 39.1R | 1.33 | +30.2R | 7.2R | 29% | +0.43R | 1.61 | 40% | no |

## Sell half at every step

| Variant | IS total | IS max DD | IS total/DD | OOS total | OOS max DD | Win rate | Mean R | PF | Capture | Beats baseline IS+OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | +75.7R | 44.3R | 1.71 | +44.7R | 7.5R | 26% | +0.64R | 1.85 | 46% | no |
| r0.5_sell50 | -10.5R | 19.8R | -0.53 | -0.3R | 5.2R | 50% | -0.06R | 0.86 | 21% | no |
| r1_sell50 | -1.4R | 21.9R | -0.07 | +5.1R | 6.5R | 35% | +0.02R | 1.04 | 28% | no |
| r1.5_sell50 | +8.1R | 28.0R | 0.29 | +10.3R | 6.2R | 41% | +0.10R | 1.16 | 29% | no |
| r2_sell50 | +15.3R | 33.2R | 0.46 | +12.2R | 7.5R | 35% | +0.15R | 1.21 | 35% | no |
| r3_sell50 | +32.4R | 37.4R | 0.87 | +21.3R | 7.5R | 30% | +0.28R | 1.39 | 44% | no |
| r0.5_sell50_be | -12.4R | 17.4R | -0.71 | -2.5R | 5.4R | 64% | -0.07R | 0.81 | 31% | no |
| r1_sell50_be | +0.6R | 19.5R | 0.03 | +2.7R | 6.6R | 49% | +0.02R | 1.03 | 33% | no |
| r1.5_sell50_be | +10.4R | 23.3R | 0.45 | +6.9R | 6.8R | 41% | +0.09R | 1.14 | 36% | no |
| r2_sell50_be | +13.1R | 30.2R | 0.43 | +11.4R | 7.5R | 35% | +0.13R | 1.19 | 38% | no |
| r3_sell50_be | +26.5R | 37.2R | 0.71 | +21.6R | 7.5R | 30% | +0.25R | 1.35 | 44% | no |

Most same-bar stop/level conflicts in any one variant: 17 bars.
