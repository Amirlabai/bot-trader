# BTC midpoint slope (4h 6m pass)

Generated: 2026-10-07T15:59:29
Window: `2026-03-24` .. `2026-09-22` | Interval: `4h` | Symbols: `BTC/USDT` | Start cash: $10,000
Elapsed: **17.1s** (17.1s) for **9975** configs

Structure: **HL avg crosses above OC avg**, both slopes positive, close > trend EMA. After an exit, both slopes must go negative and then both positive before the next entry. avg = raw midpoint. slope = (midpoint now - midpoint n bars ago) / n. Trend EMA **100/150/200**. ATR period **14..20**. n is 10..100 step 5.
Risk: no TP1; SL = `sl_atr` x ATR; trail from entry = `trail_atr` x current ATR. Long only.
Bars: **4h**. Ambiguous trail bars (`S0 < low <= S1`) resolved on **1h**.

Configs: **9975** | Eligible (n>=3): **9975**

## Top 10 by composite (eligible)

| # | PnL | Equity | WR% | Trades | PF | n | trend | atr | SL× | trail× |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | $+797 | $10,797 | 71 | 7 | 12.93 | 95 | 100 | 14 | 3 | 1.5 |
| 2 | $+793 | $10,793 | 71 | 7 | 12.16 | 95 | 100 | 14 | 2.5 | 1.5 |
| 3 | $+790 | $10,790 | 71 | 7 | 11.65 | 95 | 100 | 14 | 1.5 | 1.5 |
| 4 | $+790 | $10,790 | 71 | 7 | 11.65 | 95 | 100 | 14 | 2 | 1.5 |
| 5 | $+857 | $10,857 | 67 | 6 | 8.53 | 95 | 100 | 14 | 3 | 2 |
| 6 | $+856 | $10,856 | 67 | 6 | 8.40 | 95 | 100 | 14 | 1.5 | 2 |
| 7 | $+862 | $10,862 | 67 | 6 | 8.28 | 95 | 100 | 18 | 3 | 2 |
| 8 | $+865 | $10,865 | 67 | 6 | 8.21 | 95 | 100 | 17 | 3 | 2 |
| 9 | $+858 | $10,858 | 67 | 6 | 8.28 | 95 | 100 | 19 | 1.5 | 2 |
| 10 | $+864 | $10,864 | 67 | 6 | 8.10 | 95 | 100 | 17 | 1.5 | 2 |

## Best by net PnL (top 10, any trade count)

| # | PnL | Equity | WR% | Trades | PF | n | trend | atr | SL× | trail× |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | $+865 | $10,865 | 67 | 6 | 8.21 | 95 | 100 | 17 | 3 | 2 |
| 2 | $+864 | $10,864 | 67 | 6 | 8.08 | 95 | 100 | 16 | 3 | 2 |
| 3 | $+864 | $10,864 | 67 | 6 | 8.10 | 95 | 100 | 17 | 1.5 | 2 |
| 4 | $+862 | $10,862 | 67 | 6 | 8.28 | 95 | 100 | 18 | 3 | 2 |
| 5 | $+861 | $10,861 | 67 | 6 | 7.85 | 95 | 100 | 16 | 1.5 | 2 |
| 6 | $+860 | $10,860 | 67 | 6 | 8.06 | 95 | 100 | 18 | 1.5 | 2 |
| 7 | $+858 | $10,858 | 67 | 6 | 8.28 | 95 | 100 | 19 | 1.5 | 2 |
| 8 | $+858 | $10,858 | 67 | 6 | 7.59 | 95 | 100 | 17 | 2.5 | 2 |
| 9 | $+857 | $10,857 | 67 | 6 | 8.53 | 95 | 100 | 14 | 3 | 2 |
| 10 | $+856 | $10,856 | 67 | 6 | 7.49 | 95 | 100 | 17 | 2 | 2 |
