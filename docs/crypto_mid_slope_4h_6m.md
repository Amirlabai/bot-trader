# Crypto book, 4h 6m midpoint (shared wallet)

Generated: 2026-10-07T16:39:19
Source: `docs/btc_mid_slope_4h_6m.md` composite #1 (n=95, trend=100, ATR=14, SL=3, trail=1.5).
Window: `2026-03-24` .. `2026-09-22` | Interval: `4h` | Symbols: 14 | Start cash: $10,000
Elapsed: **24.2s**

One shared wallet. A new long is sized off cash plus open positions at entry cost, then capped by free cash. Symbols are not given their own $10k.
Structure: HL midpoint crosses above OC midpoint, both slopes positive, close above trend EMA. After an exit, that symbol must see both slopes go negative and then positive before it can enter again.
The later BTC dollar slope floor is not applied. A floor of 160 dollars per bar only fits BTC.
Risk: no TP1. SL = 3 x ATR. Trail from the close = 1.5 x current ATR.
Ambiguous trail bars resolved on 1h for **14** of 14 symbols.

## Shared wallet

- Net PnL: **$+2,058**
- Equity: **$12,058**
- WR: **38%** | Trades: **128** | PF: **1.65**
- Open positions: **4** | Cash: **$4,669**
- Still open: BTC/USDT, XRP/USDT, ADA/USDT, XMR/USDT

## Contribution inside the shared wallet

Closed-trade PnL only. These are not separate accounts.

| Symbol | PnL | Trades | WR% |
|---|---:|---:|---:|
| DOGE/USDT | $+670 | 7 | 57 |
| BTC/USDT | $+617 | 7 | 71 |
| XRP/USDT | $+328 | 11 | 18 |
| AVAX/USDT | $+220 | 13 | 38 |
| ADA/USDT | $+192 | 11 | 55 |
| SOL/USDT | $+109 | 9 | 44 |
| LEO/USDT | $+8 | 5 | 20 |
| TRX/USDT | $+0 | 15 | 47 |
| ETH/USDT | $-2 | 11 | 36 |
| XMR/USDT | $-19 | 6 | 50 |
| LINK/USDT | $-71 | 9 | 33 |
| BNB/USDT | $-90 | 10 | 20 |
| DOT/USDT | $-116 | 6 | 17 |
| ZEC/USDT | $-230 | 8 | 25 |

Skipped (no 4h bars in the window): HYPE/USDT
