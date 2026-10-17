"""Walk-forward retune: champion (locked template) vs challenger on an unseen holdout.

Trade feedback only widens the search grid. Live params change only through promote(),
which requires the holdout gates (or an explicit force) and is logged for rollback.
"""
from __future__ import annotations

import copy
import json
import os
import statistics
import sys
from datetime import datetime

import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
for p in (REPO_ROOT, os.path.join(REPO_ROOT, 'src'), os.path.join(REPO_ROOT, 'scratch')):
    if p not in sys.path:
        sys.path.insert(0, p)

import curate_params as cp  # noqa: E402  (chdirs to repo root)
from shared.curated_params import load_curated_params, save_curated_params, template_params  # noqa: E402
from shared.path_sim import curator_score, simulate_long_portfolio  # noqa: E402

LOG_PATH = os.path.join(REPO_ROOT, 'data', 'evolution_log.json')
LEDGER_PATH = os.path.join(REPO_ROOT, 'data', 'ledger.json')
SIX = ('short_window', 'long_window', 'trend_window', 'atr_period', 'sl_atr', 'trail_atr')
MIN_LEGS = 20
MARGIN = 1.10
MAX_DD_SLACK = 2.0
COOLDOWN_DAYS = 28
MIN_HOLDOUT_TRADES = 5
INF = float('inf')


def load_log() -> list[dict]:
    if not os.path.exists(LOG_PATH):
        return []
    with open(LOG_PATH, encoding='utf-8') as f:
        return json.load(f)


def _save_log(log: list[dict]) -> None:
    with open(LOG_PATH, 'w', encoding='utf-8') as f:
        json.dump(log, f, indent=2)
        f.write('\n')


def _clean(x):
    """JSON-safe: inf/nan become None."""
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, float) and (x != x or x in (INF, -INF)):
        return None
    return x


def feedback(market: str) -> dict:
    """Summarize completed legs of the long asset-trail wallet and derive grid bias."""
    prefix = 'ma_crypto' if market == 'crypto' else f'ma_{market}'
    with open(LEDGER_PATH, encoding='utf-8') as f:
        hist = json.load(f)['strategies'].get(f'{prefix}_long_trail', {}).get('history', [])
    opens: dict[str, dict] = {}
    legs = []
    for e in hist:
        if e['side'] == 'OPEN_LONG':
            opens[e['symbol']] = e
        elif e['side'] == 'CLOSE_LONG' and e['symbol'] in opens:
            o = opens.pop(e['symbol'])
            days = (datetime.fromisoformat(e['timestamp']) - datetime.fromisoformat(o['timestamp'])).days
            legs.append({
                'symbol': e['symbol'], 'pnl': e['pnl'], 'days': days,
                'exit_kind': e.get('exit_kind'),
                'ret_pct': (e['price'] / e['entry_price'] - 1) * 100,
            })
    n = len(legs)
    out = {'legs': n, 'notes': [], 'sl_extra': False, 'trail_extra': False}
    if not n:
        out['notes'].append('No completed legs for this market yet: search grid unchanged.')
        return out
    wins = [g for g in legs if g['pnl'] > 0]
    quick = [g for g in legs if g['exit_kind'] == 'stop_loss' and g['days'] <= 2]
    trailed = [g for g in legs if g['exit_kind'] == 'trailed_stop']
    out.update({
        'win_rate': round(len(wins) / n * 100, 1),
        'quick_stop_rate': round(len(quick) / n * 100, 1),
        'trailed_share': round(len(trailed) / n * 100, 1),
        'median_hold_days': statistics.median(g['days'] for g in legs),
        'avg_win_ret_pct': round(statistics.mean(g['ret_pct'] for g in wins), 2) if wins else 0.0,
    })
    if n < MIN_LEGS:
        out['notes'].append(f'{n} legs, need {MIN_LEGS}: search grid unchanged.')
        return out
    if out['quick_stop_rate'] > 40:
        out['sl_extra'] = True
        out['notes'].append(f"Quick-stop rate {out['quick_stop_rate']}%: adding a wider stop step to the grid.")
    if out['trailed_share'] > 50 and out['avg_win_ret_pct'] < 5:
        out['trail_extra'] = True
        out['notes'].append(
            f"Winners average {out['avg_win_ret_pct']}% with mostly trailed exits: adding a wider trail step.")
    if not out['notes']:
        out['notes'].append('No rule triggered: search grid unchanged.')
    return out


def _slice(series: list[dict], a: int, b: int) -> list[dict]:
    keys = ('close', 'low', 'atr', 'entry', 'has_bar')
    return [{**s, **{k: s[k][a:b] for k in keys}} for s in series]


def _score(m: dict, spec: dict, years: float) -> float:
    return curator_score(m, target_trades_per_year=float(spec['target_trades_per_year']), years=years)


def run_cycle(market: str, train_years: int = 3, holdout_months: int = 6, progress=None) -> dict:
    spec = copy.deepcopy(cp.MARKET_SPECS[market])
    pairs = {'crypto': cp.CRYPTO_PAIRS, 'commodities': cp.COMMODITY_PAIRS, 'forex': cp.FOREX_PAIRS}.get(
        market, cp.STOCK_SIM_TICKERS)
    risk = cp._risk_for(spec)
    arm = float(cp.FIXED_GATES['trail_arm_r'])
    say = progress or (lambda *a: None)

    fb = feedback(market)
    if fb['sl_extra']:
        spec['sl_atrs'] = spec['sl_atrs'] + [round(max(spec['sl_atrs']) + 0.5, 1)]
    if fb['trail_extra']:
        spec['trail_atrs'] = spec['trail_atrs'] + [round(max(spec['trail_atrs']) + 0.5, 1)]

    say('Loading prices', 0, 1, '')
    fetcher = cp.DataFetcher(cp.Config)
    frames = {}
    for sym in pairs:
        atype = 'stock' if market == 'stocks' else cp.asset_type_for_symbol(sym)
        df = cp._load_ohlcv(fetcher, sym, atype)
        if not df.empty:
            frames[sym] = df
    if len(frames) < 2:
        raise RuntimeError(f'Need at least 2 symbols with data, got {len(frames)}')
    cal = pd.DatetimeIndex(sorted({t for d in frames.values() for t in d.index}))
    end = cal[-1]
    hold_start = end - pd.DateOffset(months=holdout_months)
    train_start = hold_start - pd.DateOffset(years=train_years)
    i_tr = int(cal.searchsorted(train_start))
    i_ho = int(cal.searchsorted(hold_start))
    train_yrs = (cal[i_ho - 1] - cal[i_tr]).days / 365.25
    hold_yrs = max((end - cal[i_ho]).days / 365.25, 0.25)

    cache: dict[tuple, list[dict]] = {}

    def series_for(p: dict) -> list[dict]:
        k = (p['short_window'], p['long_window'], p['trend_window'], p['atr_period'])
        if k not in cache:  # indicators warm up on full history, windows are sliced afterwards
            cache[k] = cp._build_wallet_series(frames, p, cal, start=cal[0].date())
        return [{**s, 'sl_atr': float(p['sl_atr']), 'trail_atr': float(p['trail_atr'])} for s in cache[k]]

    def run(p: dict, a: int, b: int) -> dict:
        return simulate_long_portfolio(
            _slice(series_for(p), a, b), sl_atr=float(p['sl_atr']), trail_atr=float(p['trail_atr']),
            start_cash=float(cp.Config.INITIAL_STRATEGY_CASH), risk_settings=risk,
            trail_arm_r=arm, assert_invariants=False,
        )

    curated = load_curated_params()
    champ = {k: template_params(curated, market)[k] for k in SIX}

    def search(cands: list[dict], label: str):
        best = (None, None, -1e18)
        for i, p in enumerate(cands, 1):
            m = run(p, i_tr, i_ho)
            s = _score(m, spec, train_yrs) - (100.0 if not m['closed_trades'] else 0.0)
            if s > best[2]:
                best = (p, m, s)
            if i % 10 == 0 or i == len(cands):
                say(label, i, len(cands), f'best train score {best[2]:.3f}')
        return best

    bp, bm, bs = search(cp._coarse_grid(spec) + [champ], 'Coarse search')
    ref = [bp] + [p for p in cp._refine_neighbors(bp, crypto_bias=(market == 'crypto')) if p != bp]
    rp, rm, rs = search(ref, 'Refine')
    if rs >= bs:
        bp, bm, bs = rp, rm, rs
    chall = {k: bp[k] for k in SIX}

    c_tr = run(champ, i_tr, i_ho)
    c_ho = run(champ, i_ho, len(cal))
    h_ho = run(chall, i_ho, len(cal))
    c_s, h_s = _score(c_ho, spec, hold_yrs), _score(h_ho, spec, hold_yrs)
    last = next((e for e in reversed(load_log()) if e['market'] == market and e['decision'] == 'promoted'), None)
    age = (datetime.utcnow() - datetime.fromisoformat(last['at'])).days if last else None
    pf = h_ho['profit_factor']
    gates = [
        ('Holdout score beats champion by 10%', h_s >= c_s + abs(c_s) * (MARGIN - 1), f'{h_s:.2f} vs {c_s:.2f}'),
        ('Holdout profit factor above 1', pf > 1.0, 'inf' if pf == INF else f'{pf:.2f}'),
        (f'At least {MIN_HOLDOUT_TRADES} holdout trades', h_ho['closed_trades'] >= MIN_HOLDOUT_TRADES,
         str(h_ho['closed_trades'])),
        (f'Max drawdown within champion + {MAX_DD_SLACK:g} pts',
         h_ho['max_drawdown'] <= c_ho['max_drawdown'] + MAX_DD_SLACK,
         f"{h_ho['max_drawdown']}% vs {c_ho['max_drawdown']}%"),
        ('Holdout score at least half of train score', h_s >= 0.5 * bs, f'{h_s:.2f} vs {bs:.2f}'),
        (f'No promotion in last {COOLDOWN_DAYS} days', age is None or age >= COOLDOWN_DAYS,
         'none yet' if age is None else f'{age} days ago'),
    ]
    same = champ == chall
    return _clean({
        'market': market, 'at': datetime.utcnow().isoformat(timespec='seconds'),
        'windows': {'train': [str(cal[i_tr].date()), str(cal[i_ho - 1].date())],
                    'holdout': [str(cal[i_ho].date()), str(end.date())]},
        'symbols': len(frames), 'feedback': fb,
        'champion': {'params': champ, 'train': c_tr, 'holdout': c_ho, 'holdout_score': c_s},
        'challenger': {'params': chall, 'train': bm, 'holdout': h_ho, 'holdout_score': h_s, 'train_score': bs},
        'gates': [{'name': n, 'ok': bool(ok), 'detail': d} for n, ok, d in gates],
        'same_as_champion': same,
        'passed': all(ok for _, ok, _ in gates) and not same,
    })


def promote(report: dict, force: bool = False) -> dict:
    if not (report['passed'] or force):
        raise ValueError('Gates failed. Use force to override.')
    market = report['market']
    curated = load_curated_params()
    prev = copy.deepcopy(curated['templates'].get(market))
    prev_syms = {s: copy.deepcopy(b) for s, b in curated['symbols'].items() if b.get('market') == market}
    params = {**curated['templates'][market]['params'], **report['challenger']['params']}
    curated['templates'][market].update({
        'params': params, 'score': report['challenger']['holdout_score'], 'source': 'evolve',
        'metrics': {**report['challenger']['holdout'], 'mode': 'wallet'},
    })
    for b in curated['symbols'].values():  # wallet mode stamps one algo on every symbol of the book
        if b.get('market') == market:
            b['params'] = dict(params)
    curated['updated_at'] = datetime.utcnow().isoformat(timespec='seconds')
    save_curated_params(curated)
    entry = {**report, 'decision': 'promoted', 'forced': not report['passed'],
             'previous': {'template': prev, 'symbols': prev_syms}}
    _save_log(load_log() + [_clean(entry)])
    return entry


def reject(report: dict) -> dict:
    entry = {**report, 'decision': 'rejected'}
    _save_log(load_log() + [entry])
    return entry


def rollback(market: str) -> dict:
    log = load_log()
    last = next((e for e in reversed(log) if e['market'] == market and e['decision'] == 'promoted'
                 and not e.get('rolled_back')), None)
    if not last:
        raise ValueError(f'No promotion to roll back for {market}.')
    curated = load_curated_params()
    curated['templates'][market] = last['previous']['template']
    curated['symbols'].update(last['previous']['symbols'])
    curated['updated_at'] = datetime.utcnow().isoformat(timespec='seconds')
    save_curated_params(curated)
    last['rolled_back'] = True
    log.append({'market': market, 'at': datetime.utcnow().isoformat(timespec='seconds'), 'decision': 'rolled_back'})
    _save_log(log)
    return last


def state(market: str) -> dict:
    cur = load_curated_params()
    t = cur['templates'].get(market) or {}
    log = [{k: v for k, v in e.items() if k not in ('previous', 'feedback')}
           for e in load_log() if e['market'] == market]
    return _clean({'template': t.get('params'), 'source': t.get('source', 'curator'),
                   'updated_at': cur.get('updated_at'), 'log': log[-15:]})
