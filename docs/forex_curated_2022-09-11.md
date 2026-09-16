# Forex curated EMA params

Generated: 2026-09-16T10:18:47
Window: `2022-09-11` .. `2026-09-16` | Elapsed: **231.5s**

Long-only path sim (`shared.path_sim`) with risk invariants (≤ equity risk at SL fill, max notional, cash, fill-at-SL).

## Template centroid

```json
{'short_window': 10, 'long_window': 30, 'trend_window': 100, 'atr_period': 21, 'sl_atr': 1.5, 'trail_atr': 2.0, 'adx_min': 0.0, 'atr_buffer': 0.0, 'trail_arm_r': 1.0, 'adx_period': 14, 'vol_mult': 0.0}
```

## Per-symbol winners

| Symbol | Score | PnL | PF | Trades | Params |
|---|---:|---:|---:|---:|---|
| AUD/USD | 1.642 | $129 | 1.66 | 15 | `11/33/90 · ATR21 · SL1.0 · trail2.0` |
| EUR/GBP | 1.185 | $-68 | 0.50 | 13 | `11/33/90 · ATR21 · SL1.0 · trail1.5` |
| EUR/JPY | 1.706 | $206 | 2.02 | 10 | `10/27/90 · ATR21 · SL2.0 · trail1.5` |
| EUR/USD | 8.180 | $194 | ∞ | 10 | `10/30/100 · ATR21 · SL1.5 · trail1.5` |
| GBP/JPY | 3.537 | $424 | 5.47 | 12 | `9/30/90 · ATR21 · SL1.5 · trail2.0` |
| GBP/USD | 2.257 | $149 | 3.54 | 13 | `9/30/90 · ATR21 · SL1.0 · trail1.5` |
| USD/CAD | 1.979 | $49 | 1.42 | 11 | `11/33/100 · ATR21 · SL1.0 · trail2.5` |
| USD/CHF | 2.264 | $85 | 3.57 | 3 | `11/33/110 · ATR21 · SL1.5 · trail2.5` |
| USD/JPY | 8.415 | $556 | ∞ | 9 | `9/33/90 · ATR21 · SL2.0 · trail1.5` |
