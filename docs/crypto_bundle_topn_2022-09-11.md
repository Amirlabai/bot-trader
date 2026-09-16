# Crypto top-N bundle sweep

Generated: 2026-09-16T11:54:57
Window: `2022-09-11` .. `2026-09-16` | Start cash: **$10,000** | Risk: **1%** | Frozen entry ATR trail

Long-only shared-cash `simulate_long_portfolio` with each symbol's locked curated params.
Same-bar entry order: higher curator score first (gets cash priority).

**Max equity (incl. all):** N=14 → $39,817 (pnl $29,817)

**Quality pick (N=3..10, PF ≥ median):** N=6 → $23,300

| N | Final eq | PnL | Ret% | PF | Trades | WR% | Bundle |
|--:|--:|--:|--:|--:|--:|--:|---|
| 3 | $16,883 | $6,883 | 68.8% | 12.32 | 13 | 46.1 | ZEC, ADA, AVAX |
| 4 | $18,066 | $8,066 | 80.7% | 12.07 | 17 | 52.9 | ZEC, ADA, AVAX, DOT |
| 5 | $19,108 | $9,108 | 91.1% | 13.30 | 19 | 57.9 | ZEC, ADA, AVAX, DOT, LEO |
| 6 * | $23,300 | $13,300 | 133.0% | 12.46 | 27 | 59.3 | ZEC, ADA, AVAX, DOT, LEO, BTC |
| 7 | $25,076 | $15,076 | 150.8% | 10.01 | 33 | 54.5 | ZEC, ADA, AVAX, DOT, LEO, BTC, LINK |
| 8 | $28,885 | $18,885 | 188.8% | 9.74 | 41 | 56.1 | ZEC, ADA, AVAX, DOT, LEO, BTC, LINK, BNB |
| 9 | $33,541 | $23,541 | 235.4% | 7.17 | 53 | 50.9 | ZEC, ADA, AVAX, DOT, LEO, BTC, LINK, BNB, XRP |
| 10 | $34,165 | $24,165 | 241.7% | 6.15 | 62 | 45.2 | ZEC, ADA, AVAX, DOT, LEO, BTC, LINK, BNB, XRP, SOL |
| 14 | $39,817 | $29,817 | 298.2% | 4.02 | 90 | 35.6 | ZEC, ADA, AVAX, DOT, LEO, BTC, LINK, BNB, XRP, SOL, DOGE, TRX, ETH, XMR |

## Rank order (curator score)

1. `ZEC/USDT` score=8.2421
2. `ADA/USDT` score=8.1557
3. `AVAX/USDT` score=8.131
4. `DOT/USDT` score=8.1132
5. `LEO/USDT` score=8.1093
6. `BTC/USDT` score=6.438
7. `LINK/USDT` score=6.1463
8. `BNB/USDT` score=6.1366
9. `XRP/USDT` score=5.694
10. `SOL/USDT` score=5.6598
11. `DOGE/USDT` score=5.4107
12. `TRX/USDT` score=5.3482
13. `ETH/USDT` score=4.9365
14. `XMR/USDT` score=4.2484
