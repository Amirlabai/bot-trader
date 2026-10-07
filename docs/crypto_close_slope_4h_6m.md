# Crypto book, 4h 6m close slope (shared wallet)

Generated: 2026-10-07T16:42:07
Source: `docs/btc_close_slope_4h_6m.md` composite #1 (n=40, trend=100, ATR=14, SL=1, trail=1.5).
Window: `2026-03-24` .. `2026-09-22` | Interval: `4h` | Symbols: 14 | Start cash: $10,000
Elapsed: **2.3s**

One shared wallet. A new long is sized off cash plus open positions at entry cost, then capped by free cash. Symbols are not given their own $10k.
Structure: slope of close is positive and close is above the trend EMA. After an exit, that symbol must see the close slope go negative and then positive before it can enter again.
The later BTC dollar slope floor is not applied. A floor of 160 dollars per bar only fits BTC.
Risk: no TP1. SL = 1 x ATR. Trail from the close = 1.5 x current ATR.
Ambiguous trail bars resolved on 1h for **14** of 14 symbols.

## Shared wallet

- Net PnL: **$+8,135**
- Equity: **$18,135**
- WR: **37%** | Trades: **278** | PF: **2.21**
- Open positions: **3** | Cash: **$8,777**
- Still open: ADA/USDT, XMR/USDT, LINK/USDT

## Contribution inside the shared wallet

Closed-trade PnL only. These are not separate accounts.

| Symbol | PnL | Trades | WR% |
|---|---:|---:|---:|
| ZEC/USDT | $+3,542 | 19 | 58 |
| ETH/USDT | $+980 | 26 | 46 |
| DOGE/USDT | $+878 | 18 | 39 |
| SOL/USDT | $+612 | 18 | 44 |
| BTC/USDT | $+496 | 17 | 47 |
| ADA/USDT | $+457 | 15 | 40 |
| AVAX/USDT | $+434 | 22 | 27 |
| LINK/USDT | $+403 | 20 | 45 |
| BNB/USDT | $+316 | 26 | 35 |
| XRP/USDT | $+217 | 14 | 36 |
| TRX/USDT | $+125 | 20 | 55 |
| LEO/USDT | $-39 | 18 | 22 |
| DOT/USDT | $-83 | 16 | 31 |
| XMR/USDT | $-830 | 29 | 10 |

Skipped (no 4h bars in the window): HYPE/USDT
