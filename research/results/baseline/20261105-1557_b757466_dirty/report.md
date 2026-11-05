# Experiment: baseline

Live daily exit (ma_crypto_long_trail): 1x ATR initial stop, 3x ATR trail from entry using ATR frozen at entry, no TP1, no scale-out.

- Ran 2026-11-05T15:57:32+00:00 at git b757466 (uncommitted changes)
- 14 pairs, bars 2022-11-05 00:00:00 to 2026-11-04 00:00:00
- Fee 0.10% per side on every fill. All R below is net of fees.
- In-sample: trades opened before 2025-11-04. Out-of-sample: opened after (last 12 months).
- A variant beats the baseline only if its total R is higher in-sample and out-of-sample.
- Same-bar rule: when one bar touches both the stop and a ladder level, the stop fills first.

## Baseline (live daily exit, no scale-out)

- 189 trades, net +120.3R (gross +132.0R), win 26%, mean +0.64R, PF 1.85
- In-sample +75.7R with max drawdown 44.3R; out-of-sample +44.7R with max drawdown 7.5R

Pairs without data (skipped): HYPE/USDT
