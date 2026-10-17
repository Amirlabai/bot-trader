"""Headless lab run for CI: retune every market/bot on fresh data and log the result as 'proposed'.

Never promotes. Review proposals in the lab UI (server.py) or the decision log and promote by hand.
Usage: python scratch/evolve_lab/weekly.py [--markets crypto,forex] [--bots live,hold] [--no-timeframes]
"""
from __future__ import annotations

import argparse
import traceback

import engine


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--markets', default='crypto,commodities,forex,stocks')
    ap.add_argument('--bots', default='live,hold')
    ap.add_argument('--no-timeframes', action='store_true')
    a = ap.parse_args()
    for market in a.markets.split(','):
        for bot in a.bots.split(','):
            try:
                r = engine.run_cycle(market, bot=bot, timeframes=not a.no_timeframes)
                engine.propose(r)
                verdict = 'PASSED gates' if r['passed'] else ('same as champion' if r['same_as_champion'] else 'failed gates')
                print(f'{market}/{bot}: {verdict}; holdout score '
                      f"{r['challenger']['holdout_score']} vs {r['champion']['holdout_score']}")
            except Exception:  # one market failing must not stop the rest
                print(f'{market}/{bot}: error')
                traceback.print_exc()


if __name__ == '__main__':
    main()
