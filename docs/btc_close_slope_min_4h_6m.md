# BTC close slope (4h 6m min pass)

Generated: 2026-10-07T16:23:53
Window: `2026-03-24` .. `2026-09-22` | Interval: `4h` | Symbols: `BTC/USDT` | Start cash: $10,000
Elapsed: **2m 45s** (165.3s) for **99750** configs

Structure: **slope of close above the floor** and close > trend EMA. No open-close or high-low averages. Entry also requires slope >= min (20..200 step 20, dollars per bar). After an exit the slope must still go negative, then positive, before the next entry. Dropping under the floor is not the reset. slope = (close now - close n bars ago) / n. Trend EMA **100/150/200**. ATR period **14..20**. n is 10..100 step 5.
Risk: no TP1; SL = `sl_atr` x ATR; trail from entry = `trail_atr` x current ATR. Long only.
Bars: **4h**. Ambiguous trail bars (`S0 < low <= S1`) resolved on **1h**.

Configs: **99750** | Eligible (n>=3): **63450**

## Top 10 by composite (eligible)

| # | PnL | Equity | WR% | Trades | PF | n | min | trend | atr | SL× | trail× |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | $+559 | $10,559 | 86 | 7 | 48.16 | 30 | 120 | 100 | 17 | 1.5 | 2 |
| 2 | $+559 | $10,559 | 86 | 7 | 48.16 | 30 | 120 | 100 | 17 | 2 | 2 |
| 3 | $+559 | $10,559 | 86 | 7 | 48.16 | 30 | 120 | 100 | 17 | 2.5 | 2 |
| 4 | $+558 | $10,558 | 86 | 7 | 48.11 | 30 | 120 | 100 | 17 | 3 | 2 |
| 5 | $+553 | $10,553 | 86 | 7 | 49.27 | 30 | 120 | 100 | 18 | 1.5 | 2 |
| 6 | $+553 | $10,553 | 86 | 7 | 49.27 | 30 | 120 | 100 | 18 | 2 | 2 |
| 7 | $+553 | $10,553 | 86 | 7 | 49.27 | 30 | 120 | 100 | 18 | 2.5 | 2 |
| 8 | $+553 | $10,553 | 86 | 7 | 49.25 | 30 | 120 | 100 | 18 | 3 | 2 |
| 9 | $+553 | $10,553 | 86 | 7 | 46.56 | 30 | 120 | 100 | 16 | 1.5 | 2 |
| 10 | $+553 | $10,553 | 86 | 7 | 46.56 | 30 | 120 | 100 | 16 | 2 | 2 |

## Best by net PnL (top 10, any trade count)

| # | PnL | Equity | WR% | Trades | PF | n | min | trend | atr | SL× | trail× |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | $+752 | $10,752 | 45 | 20 | 3.33 | 20 | 20 | 100 | 18 | 1 | 2.5 |
| 2 | $+744 | $10,744 | 44 | 18 | 3.42 | 20 | 20 | 150 | 18 | 1 | 2.5 |
| 3 | $+740 | $10,740 | 40 | 20 | 3.26 | 20 | 20 | 100 | 19 | 1 | 2.5 |
| 4 | $+735 | $10,735 | 39 | 18 | 3.40 | 20 | 20 | 150 | 19 | 1 | 2.5 |
| 5 | $+726 | $10,726 | 40 | 20 | 3.10 | 20 | 20 | 100 | 20 | 1 | 2.5 |
| 6 | $+722 | $10,722 | 39 | 18 | 3.21 | 20 | 20 | 150 | 20 | 1 | 2.5 |
| 7 | $+720 | $10,720 | 43 | 14 | 3.90 | 35 | 20 | 100 | 19 | 1 | 2 |
| 8 | $+713 | $10,713 | 47 | 15 | 4.31 | 40 | 20 | 100 | 15 | 1 | 2 |
| 9 | $+710 | $10,710 | 40 | 15 | 4.24 | 40 | 20 | 100 | 16 | 1 | 2 |
| 10 | $+710 | $10,710 | 47 | 15 | 4.30 | 40 | 20 | 100 | 14 | 1 | 2 |
