# BTC midpoint slope (4h 6m min pass)

Generated: 2026-10-07T16:23:56
Window: `2026-03-24` .. `2026-09-22` | Interval: `4h` | Symbols: `BTC/USDT` | Start cash: $10,000
Elapsed: **2m 44s** (163.8s) for **99750** configs

Structure: **HL avg crosses above OC avg**, both slopes meet the floor, close > trend EMA. Entry also requires slope >= min (20..200 step 20, dollars per bar). After an exit the slope must still go negative, then positive, before the next entry. Dropping under the floor is not the reset. avg = raw midpoint. slope = (midpoint now - midpoint n bars ago) / n. Trend EMA **100/150/200**. ATR period **14..20**. n is 10..100 step 5.
Risk: no TP1; SL = `sl_atr` x ATR; trail from entry = `trail_atr` x current ATR. Long only.
Bars: **4h**. Ambiguous trail bars (`S0 < low <= S1`) resolved on **1h**.

Configs: **99750** | Eligible (n>=3): **52335**

## Top 10 by composite (eligible)

| # | PnL | Equity | WR% | Trades | PF | n | min | trend | atr | SL× | trail× |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | $+566 | $10,566 | 100 | 4 | inf | 25 | 160 | 100 | 17 | 2.5 | 2 |
| 2 | $+566 | $10,566 | 100 | 4 | inf | 25 | 160 | 150 | 17 | 2.5 | 2 |
| 3 | $+566 | $10,566 | 100 | 4 | inf | 25 | 160 | 200 | 17 | 2.5 | 2 |
| 4 | $+564 | $10,564 | 100 | 4 | inf | 25 | 140 | 150 | 17 | 2.5 | 2 |
| 5 | $+564 | $10,564 | 100 | 4 | inf | 25 | 140 | 200 | 17 | 2.5 | 2 |
| 6 | $+563 | $10,563 | 100 | 4 | inf | 25 | 160 | 100 | 17 | 3 | 2 |
| 7 | $+563 | $10,563 | 100 | 4 | inf | 25 | 160 | 150 | 17 | 3 | 2 |
| 8 | $+563 | $10,563 | 100 | 4 | inf | 25 | 160 | 200 | 17 | 3 | 2 |
| 9 | $+561 | $10,561 | 100 | 4 | inf | 25 | 140 | 150 | 17 | 3 | 2 |
| 10 | $+561 | $10,561 | 100 | 4 | inf | 25 | 140 | 200 | 17 | 3 | 2 |

## Best by net PnL (top 10, any trade count)

| # | PnL | Equity | WR% | Trades | PF | n | min | trend | atr | SL× | trail× |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | $+759 | $10,759 | 38 | 13 | 3.65 | 10 | 100 | 200 | 15 | 1 | 2.5 |
| 2 | $+757 | $10,757 | 38 | 13 | 3.57 | 10 | 100 | 200 | 14 | 1 | 2.5 |
| 3 | $+751 | $10,751 | 29 | 17 | 2.78 | 10 | 80 | 200 | 15 | 1 | 2.5 |
| 4 | $+746 | $10,746 | 50 | 12 | 3.33 | 10 | 120 | 200 | 15 | 1.5 | 2.5 |
| 5 | $+746 | $10,746 | 50 | 12 | 3.30 | 10 | 120 | 200 | 14 | 1.5 | 2.5 |
| 6 | $+743 | $10,743 | 38 | 13 | 3.59 | 10 | 100 | 200 | 18 | 1 | 2.5 |
| 7 | $+743 | $10,743 | 32 | 19 | 2.52 | 10 | 80 | 200 | 15 | 1 | 2 |
| 8 | $+742 | $10,742 | 46 | 13 | 3.12 | 10 | 100 | 200 | 15 | 1.5 | 2.5 |
| 9 | $+741 | $10,741 | 46 | 13 | 3.08 | 10 | 100 | 200 | 14 | 1.5 | 2.5 |
| 10 | $+739 | $10,739 | 58 | 12 | 3.20 | 10 | 120 | 200 | 18 | 2 | 2.5 |
