# BTC midpoint slope (4h min pass)

Generated: 2026-10-07T16:20:39
Window: `2024-11-22` .. `2026-09-22` | Interval: `4h` | Symbols: `BTC/USDT` | Start cash: $10,000
Elapsed: **9m 19s** (559.0s) for **99750** configs

Structure: **HL avg crosses above OC avg**, both slopes meet the floor, close > trend EMA. Entry also requires slope >= min (20..200 step 20, dollars per bar). After an exit the slope must still go negative, then positive, before the next entry. Dropping under the floor is not the reset. avg = raw midpoint. slope = (midpoint now - midpoint n bars ago) / n. Trend EMA **100/150/200**. ATR period **14..20**. n is 10..100 step 5.
Risk: no TP1; SL = `sl_atr` x ATR; trail from entry = `trail_atr` x current ATR. Long only.
Bars: **4h**. Ambiguous trail bars (`S0 < low <= S1`) resolved on **1h**.

Configs: **99750** | Eligible (n>=3): **93975**

## Top 10 by composite (eligible)

| # | PnL | Equity | WR% | Trades | PF | n | min | trend | atr | SL× | trail× |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | $+721 | $10,721 | 73 | 11 | 9.97 | 100 | 60 | 200 | 14 | 3 | 1.5 |
| 2 | $+694 | $10,694 | 73 | 11 | 10.10 | 100 | 60 | 200 | 15 | 3 | 1.5 |
| 3 | $+720 | $10,720 | 73 | 11 | 9.71 | 100 | 60 | 200 | 16 | 3 | 1.5 |
| 4 | $+848 | $10,848 | 64 | 11 | 11.03 | 100 | 60 | 200 | 19 | 1 | 2 |
| 5 | $+847 | $10,847 | 64 | 11 | 10.51 | 100 | 60 | 200 | 17 | 1 | 2 |
| 6 | $+847 | $10,847 | 64 | 11 | 10.89 | 100 | 60 | 200 | 18 | 1 | 2 |
| 7 | $+846 | $10,846 | 64 | 11 | 10.51 | 100 | 60 | 200 | 16 | 1 | 2 |
| 8 | $+843 | $10,843 | 64 | 11 | 11.05 | 100 | 60 | 200 | 20 | 1 | 2 |
| 9 | $+838 | $10,838 | 64 | 11 | 10.35 | 100 | 60 | 200 | 15 | 1 | 2 |
| 10 | $+794 | $10,794 | 73 | 11 | 8.92 | 100 | 60 | 200 | 16 | 1.5 | 2.5 |

## Best by net PnL (top 10, any trade count)

| # | PnL | Equity | WR% | Trades | PF | n | min | trend | atr | SL× | trail× |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | $+1,868 | $11,868 | 54 | 37 | 3.46 | 40 | 20 | 150 | 16 | 3 | 2 |
| 2 | $+1,867 | $11,867 | 54 | 37 | 3.39 | 40 | 20 | 150 | 17 | 3 | 2 |
| 3 | $+1,864 | $11,864 | 54 | 37 | 3.42 | 40 | 20 | 150 | 15 | 2.5 | 2 |
| 4 | $+1,854 | $11,854 | 54 | 37 | 3.32 | 40 | 20 | 150 | 18 | 3 | 2 |
| 5 | $+1,851 | $11,851 | 53 | 36 | 3.78 | 40 | 20 | 200 | 16 | 3 | 2 |
| 6 | $+1,848 | $11,848 | 53 | 36 | 3.70 | 40 | 20 | 200 | 17 | 3 | 2 |
| 7 | $+1,847 | $11,847 | 54 | 37 | 3.26 | 40 | 20 | 150 | 19 | 3 | 2 |
| 8 | $+1,847 | $11,847 | 54 | 37 | 3.24 | 40 | 20 | 150 | 20 | 3 | 2 |
| 9 | $+1,839 | $11,839 | 53 | 36 | 3.61 | 40 | 20 | 200 | 19 | 3 | 2 |
| 10 | $+1,839 | $11,839 | 53 | 36 | 3.64 | 40 | 20 | 200 | 18 | 3 | 2 |
