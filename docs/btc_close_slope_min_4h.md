# BTC close slope (4h min pass)

Generated: 2026-10-07T16:20:53
Window: `2024-11-22` .. `2026-09-22` | Interval: `4h` | Symbols: `BTC/USDT` | Start cash: $10,000
Elapsed: **9m 34s** (573.8s) for **99750** configs

Structure: **slope of close above the floor** and close > trend EMA. No open-close or high-low averages. Entry also requires slope >= min (20..200 step 20, dollars per bar). After an exit the slope must still go negative, then positive, before the next entry. Dropping under the floor is not the reset. slope = (close now - close n bars ago) / n. Trend EMA **100/150/200**. ATR period **14..20**. n is 10..100 step 5.
Risk: no TP1; SL = `sl_atr` x ATR; trail from entry = `trail_atr` x current ATR. Long only.
Bars: **4h**. Ambiguous trail bars (`S0 < low <= S1`) resolved on **1h**.

Configs: **99750** | Eligible (n>=3): **96600**

## Top 10 by composite (eligible)

| # | PnL | Equity | WR% | Trades | PF | n | min | trend | atr | SL× | trail× |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | $+840 | $10,840 | 71 | 14 | 8.47 | 100 | 60 | 150 | 15 | 3 | 2 |
| 2 | $+865 | $10,865 | 71 | 14 | 8.23 | 100 | 60 | 150 | 15 | 2.5 | 2 |
| 3 | $+842 | $10,842 | 79 | 14 | 7.42 | 100 | 60 | 150 | 18 | 2.5 | 2.5 |
| 4 | $+816 | $10,816 | 79 | 14 | 7.53 | 100 | 60 | 150 | 18 | 3 | 2.5 |
| 5 | $+834 | $10,834 | 79 | 14 | 7.40 | 100 | 60 | 150 | 19 | 2.5 | 2.5 |
| 6 | $+1,302 | $11,302 | 67 | 30 | 6.29 | 55 | 60 | 100 | 20 | 3 | 1.5 |
| 7 | $+1,295 | $11,295 | 67 | 30 | 6.31 | 55 | 60 | 100 | 19 | 3 | 1.5 |
| 8 | $+805 | $10,805 | 79 | 14 | 7.44 | 100 | 60 | 150 | 19 | 3 | 2.5 |
| 9 | $+863 | $10,863 | 71 | 14 | 7.60 | 100 | 60 | 150 | 19 | 2.5 | 2 |
| 10 | $+860 | $10,860 | 71 | 14 | 7.60 | 100 | 60 | 150 | 18 | 2.5 | 2 |

## Best by net PnL (top 10, any trade count)

| # | PnL | Equity | WR% | Trades | PF | n | min | trend | atr | SL× | trail× |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | $+1,716 | $11,716 | 42 | 55 | 2.53 | 35 | 20 | 150 | 17 | 1.5 | 2 |
| 2 | $+1,648 | $11,648 | 44 | 54 | 2.39 | 35 | 20 | 150 | 16 | 2 | 2 |
| 3 | $+1,647 | $11,647 | 43 | 54 | 2.38 | 35 | 20 | 150 | 17 | 2 | 2 |
| 4 | $+1,602 | $11,602 | 44 | 54 | 2.37 | 35 | 20 | 150 | 15 | 2 | 2 |
| 5 | $+1,586 | $11,586 | 42 | 55 | 2.39 | 35 | 20 | 150 | 16 | 1.5 | 2 |
| 6 | $+1,574 | $11,574 | 45 | 56 | 2.31 | 40 | 20 | 150 | 16 | 2 | 2 |
| 7 | $+1,568 | $11,568 | 42 | 55 | 2.23 | 35 | 20 | 150 | 18 | 2 | 2 |
| 8 | $+1,568 | $11,568 | 43 | 54 | 2.25 | 35 | 20 | 150 | 17 | 2.5 | 2 |
| 9 | $+1,567 | $11,567 | 44 | 54 | 2.26 | 35 | 20 | 150 | 16 | 2.5 | 2 |
| 10 | $+1,559 | $11,559 | 44 | 54 | 2.30 | 35 | 20 | 150 | 17 | 1.5 | 2.5 |
