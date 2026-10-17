"""Walk-forward retune: champion (locked template) vs challenger on an unseen holdout.

Two bots are curated separately: 'live' (templates) and 'hold' (hold_templates: fixed holding
horizon + per-symbol profit gate). With timeframes=True the search also picks which timeframe
(daily/weekly/monthly, resampled from daily) drives trend, entry cross, ATR sizing and exit.

Trade feedback only widens the search grid. Live params change only through promote(),
which requires the holdout gates (or an explicit force) and is logged for rollback.
"""
from __future__ import annotations

import copy
import itertools
import json
import os
import random
import statistics
import sys
from collections import OrderedDict
from datetime import datetime

import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
for p in (REPO_ROOT, os.path.join(REPO_ROOT, 'src'), os.path.join(REPO_ROOT, 'scratch')):
    if p not in sys.path:
        sys.path.insert(0, p)

import curate_params as cp  # noqa: E402  (chdirs to repo root)
from config import HOLD_DEFAULTS  # noqa: E402
from shared.curated_params import (  # noqa: E402
    BOT_HOLD, BOT_LIVE, load_curated_params, save_curated_params, template_params,
)
from shared.path_sim import MTF_DEFAULTS, curator_score, simulate_long_portfolio  # noqa: E402
from shared.profit_gate import gate_tuple  # noqa: E402

LOG_PATH = os.path.join(REPO_ROOT, 'data', 'evolution_log.json')
LEDGER_PATH = os.path.join(REPO_ROOT, 'data', 'ledger.json')
SIX = ('short_window', 'long_window', 'trend_window', 'atr_period', 'sl_atr', 'trail_atr')
TF_KEYS = tuple(MTF_DEFAULTS)  # trend_tf, cross_tf, atr_tf, exit_tf, exit_mode
HOLD_KEYS = ('hold_days', 'gate_window', 'gate_min_trades', 'gate_min_pf')
IND_KEYS = SIX[:4] + TF_KEYS  # what the indicator series depend on (sl/trail/hold do not)
TF_MARGIN = 1.20  # a challenger that changes timeframe roles must win by more
MIN_STABLE_PERIODS = 2  # of 3 train sub-periods must be profitable
MAX_SIMS = 1500
HOLD_DAYS_OPTIONS = (7, 14, 30, 60, 90, 180)
# Window grids in bars of the timeframe they apply to.
TF_GRIDS = {
    'D': {'short': (10, 15, 20, 25, 30), 'ratio': (1.5, 2.0, 2.5, 3.0, 4.0), 'trend': (100, 150, 200),
          'atr': (10, 14, 21)},
    'W': {'short': (3, 5, 8, 10), 'ratio': (2.0, 2.5, 3.0, 4.0), 'trend': (10, 20, 30, 40), 'atr': (4, 8, 13)},
    'M': {'short': (2, 3, 4), 'ratio': (2.0, 3.0), 'trend': (6, 10, 12), 'atr': (3, 6)},
}
MIN_LEGS = 20
MARGIN = 1.10
MAX_DD_SLACK = 2.0
COOLDOWN_DAYS = 28
MIN_HOLDOUT_TRADES = 5
INF = float('inf')
BOT_FILE_KEY = {BOT_LIVE: 'templates', BOT_HOLD: 'hold_templates'}


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
    keys = ('close', 'low', 'atr', 'entry', 'exit', 'days', 'has_bar')
    return [{**s, **{k: s[k][a:b] for k in keys if k in s}} for s in series]


def _score(m: dict, spec: dict, years: float) -> float:
    return curator_score(m, target_trades_per_year=float(spec['target_trades_per_year']), years=years)


def _file_key(bot: str) -> str:
    return BOT_FILE_KEY[bot]


def champion_params(curated: dict, market: str, bot: str = BOT_LIVE) -> dict:
    """Full param set the live wallets trade now: six-pack, timeframe roles, and for hold the horizon."""
    live = template_params(curated, market)
    out = {k: live[k] for k in SIX if k in live}
    for k in TF_KEYS:
        if k in live:
            out[k] = live[k]
    if 'trend_tf' not in out:
        out['trend_tf'] = 'W' if live.get('trend_weekly') else 'D'
    for k, v in MTF_DEFAULTS.items():
        out.setdefault(k, v)
    if bot == BOT_HOLD:
        out.update({k: HOLD_DEFAULTS[k] for k in HOLD_KEYS})
        own = template_params(curated, market, BOT_HOLD)
        out.update({k: own[k] for k in SIX + TF_KEYS + HOLD_KEYS if k in own})
    return out


def _tf_combos() -> list[dict]:
    combos = []
    for trend_tf, cross_tf, atr_tf, mode in itertools.product('DWM', 'DW', 'DW', ('stop_only', 'cross', 'trend')):
        exit_tf = cross_tf if mode == 'cross' else trend_tf
        combos.append({'trend_tf': trend_tf, 'cross_tf': cross_tf, 'atr_tf': atr_tf,
                       'exit_tf': exit_tf, 'exit_mode': mode})
    return combos


def _tf_candidates(spec: dict, combos: list[dict], rng: random.Random, budget: int) -> list[dict]:
    """Per timeframe combo: a few indicator sets, each crossed with sl/trail pairs."""
    per_combo = max(10, budget // max(len(combos), 1))
    sets_per_combo = max(2, per_combo // 5)
    pairs_per_set = max(1, per_combo // sets_per_combo)
    out = []
    for combo in combos:
        cg, tg = TF_GRIDS[combo['cross_tf']], TF_GRIDS[combo['trend_tf']]
        ag = TF_GRIDS[combo['atr_tf']]
        if combo['atr_tf'] == 'D':
            sls, trails = spec['sl_atrs'], spec['trail_atrs']
        else:  # weekly ATR is several times the daily one: tighter multiples
            sls, trails = (0.5, 0.75, 1.0, 1.5, 2.0), (1.0, 1.5, 2.0, 3.0)
        for _ in range(sets_per_combo):
            short = rng.choice(cg['short'])
            long_ = int(round(short * rng.choice(cg['ratio'])))
            ind = {'short_window': short, 'long_window': max(long_, short + 1),
                   'trend_window': rng.choice(tg['trend']), 'atr_period': rng.choice(ag['atr'])}
            for _ in range(pairs_per_set):
                sl, tr = rng.choice(sls), rng.choice(trails)
                if tr < 0.75 * sl - 1e-12:
                    continue
                out.append({**ind, 'sl_atr': float(sl), 'trail_atr': float(tr), **combo})
    return out


def _refine(bp: dict, bot: str) -> list[dict]:
    """Neighbours of the best candidate, keeping its timeframe roles and hold settings."""
    def around(v, lo=2):
        return sorted({max(lo, int(round(v * f))) for f in (0.8, 1.0, 1.25)} | {max(lo, int(v) - 1), int(v) + 1})
    short = around(bp['short_window'])
    long_ = around(bp['long_window'])
    trend = around(bp['trend_window'])
    sls = sorted({round(max(0.25, bp['sl_atr'] + d), 2) for d in (-0.5, 0.0, 0.5)})
    trails = sorted({round(max(0.0, bp['trail_atr'] + d), 2) for d in (-0.5, 0.0, 0.5)}) if bp['trail_atr'] else [0.0]
    holds = [None]
    if bot == BOT_HOLD:
        h = int(bp['hold_days'])
        holds = sorted({max(3, int(round(h * f))) for f in (0.7, 1.0, 1.4)})
    out = []
    for s, l, t, sl, tr, h in itertools.product(short, long_, trend, sls, trails, holds):
        if l <= s or (bp['cross_tf'] == bp['trend_tf'] == 'D' and t < l):
            continue
        if tr and tr < 0.75 * sl - 1e-12:
            continue
        p = {**bp, 'short_window': s, 'long_window': l, 'trend_window': t, 'sl_atr': sl, 'trail_atr': tr}
        if h is not None:
            p['hold_days'] = h
        out.append(p)
    return out


def _tf_part(p: dict) -> dict:
    return {k: p.get(k, MTF_DEFAULTS[k]) for k in TF_KEYS}


def run_cycle(market: str, train_years: int = 3, holdout_months: int = 6, progress=None, *,
              bot: str = BOT_LIVE, timeframes: bool = False, seed: int = 7, max_sims: int = MAX_SIMS,
              max_refine: int = 400) -> dict:
    spec = copy.deepcopy(cp.MARKET_SPECS[market])
    pairs = {'crypto': cp.CRYPTO_PAIRS, 'commodities': cp.COMMODITY_PAIRS, 'forex': cp.FOREX_PAIRS}.get(
        market, cp.STOCK_SIM_TICKERS)
    risk = cp._risk_for(spec)
    say = progress or (lambda *a: None)
    rng = random.Random(seed)

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
    third = (i_ho - i_tr) // 3
    sub_windows = [(i_tr + k * third, i_tr + (k + 1) * third if k < 2 else i_ho) for k in range(3)]

    curated = load_curated_params()
    live_tmpl = template_params(curated, market)  # gates always follow the live template
    gates = {k: live_tmpl.get(k, cp.FIXED_GATES[k]) for k in ('adx_min', 'atr_buffer', 'adx_period')}
    arm = float(live_tmpl.get('trail_arm_r', cp.FIXED_GATES['trail_arm_r']))
    champ = champion_params(curated, market, bot)

    cache: OrderedDict[tuple, list[dict]] = OrderedDict()

    def series_for(p: dict) -> list[dict]:
        k = tuple(p.get(x, MTF_DEFAULTS.get(x)) for x in IND_KEYS)
        if k in cache:
            cache.move_to_end(k)
        else:  # indicators warm up on full history, windows are sliced afterwards
            cache[k] = cp._build_wallet_series(frames, p, cal, start=cal[0].date(), gates=gates)
            if len(cache) > 24:
                cache.popitem(last=False)
        return [{**s, 'sl_atr': float(p['sl_atr']), 'trail_atr': float(p['trail_atr'])} for s in cache[k]]

    def run(p: dict, a: int, b: int) -> dict:
        hold = bot == BOT_HOLD
        return simulate_long_portfolio(
            _slice(series_for(p), a, b), sl_atr=float(p['sl_atr']), trail_atr=float(p['trail_atr']),
            start_cash=float(cp.Config.INITIAL_STRATEGY_CASH), risk_settings=risk,
            trail_arm_r=1e9 if float(p['trail_atr']) == 0 else arm, assert_invariants=False,
            max_hold_days=int(p.get('hold_days', 0)) if hold else 0,
            gate=gate_tuple(p) if hold else None,
        )

    def score_train(p: dict):
        m = run(p, i_tr, i_ho)
        return _score(m, spec, train_yrs) - (100.0 if not m['closed_trades'] else 0.0), m

    def search(cands: list[dict], label: str):
        scored = []
        for i, p in enumerate(cands, 1):
            s, m = score_train(p)
            scored.append((s, p, m))
            if i % 10 == 0 or i == len(cands):
                say(label, i, len(cands), f'best train score {max(x[0] for x in scored):.3f}')
        scored.sort(key=lambda x: -x[0])
        return scored

    # Candidate pool: champion's own timeframe roles unless the timeframe search is on.
    if timeframes:
        pool = _tf_candidates(spec, _tf_combos(), rng, max_sims)
    else:
        base_tf = _tf_part(champ)
        pool = [{**p, **base_tf} for p in cp._coarse_grid(spec)]
        if len(pool) > max_sims:
            pool = rng.sample(pool, max_sims)
    if bot == BOT_HOLD:
        for p in pool:
            p.update({k: champ[k] for k in HOLD_KEYS})
            p['hold_days'] = rng.choice(HOLD_DAYS_OPTIONS)
            if rng.random() < 0.25:
                p['trail_atr'] = 0.0  # pure hold to the horizon, stop-loss only
    pool.sort(key=lambda p: str(sorted(p.items())))  # group by indicator set for the series cache
    pool.append(champ)

    coarse = search(pool, 'Coarse search')
    ref = [p for p in _refine(coarse[0][1], bot) if p != coarse[0][1]]
    if len(ref) > max_refine:
        ref = rng.sample(ref, max_refine)
    refined = search(ref, 'Refine') if ref else []
    ranked = sorted(coarse + refined, key=lambda x: -x[0])

    # Robustness rerank: of the 8 best train scores keep the one with the best median across
    # three train sub-periods, so a single lucky stretch cannot win.
    def third_scores(p: dict) -> list[float]:
        out = []
        for a, b in sub_windows:
            m = run(p, a, b)
            yrs = (cal[b - 1] - cal[a]).days / 365.25
            out.append(_score(m, spec, yrs) - (100.0 if not m['closed_trades'] else 0.0))
        return out
    say('Stability check', 0, 1, '')
    seen_keys, top = set(), []
    for s, p, m in ranked:
        key = str(sorted(p.items()))
        if key not in seen_keys:
            seen_keys.add(key)
            top.append((s, p, m))
        if len(top) == 8:
            break
    best = max(((statistics.median(third_scores(p)), s, p, m) for s, p, m in top), key=lambda x: (x[0], x[1]))
    _med, bs, bp, bm = best
    chall = {k: bp[k] for k in SIX + TF_KEYS + (HOLD_KEYS if bot == BOT_HOLD else ())}

    c_tr = run(champ, i_tr, i_ho)
    c_ho = run(champ, i_ho, len(cal))
    h_ho = run(chall, i_ho, len(cal))
    c_s, h_s = _score(c_ho, spec, hold_yrs), _score(h_ho, spec, hold_yrs)
    folds = {
        'champion': [round(x, 3) for x in third_scores(champ)],
        'challenger': [round(x, 3) for x in third_scores(chall)],
    }
    fold_pf = [run(chall, a, b)['profit_factor'] for a, b in sub_windows]
    last = next((e for e in reversed(load_log()) if e['market'] == market and e['decision'] == 'promoted'
                 and e.get('bot', BOT_LIVE) == bot), None)
    age = (datetime.utcnow() - datetime.fromisoformat(last['at'])).days if last else None
    pf = h_ho['profit_factor']
    tf_changed = _tf_part(chall) != _tf_part(champ)
    margin = TF_MARGIN if tf_changed else MARGIN
    gates_list = [
        (f'Holdout score beats champion by {round((margin - 1) * 100)}%',
         h_s >= c_s + abs(c_s) * (margin - 1), f'{h_s:.2f} vs {c_s:.2f}'),
        ('Holdout profit factor above 1', pf > 1.0, 'inf' if pf == INF else f'{pf:.2f}'),
        (f'At least {MIN_HOLDOUT_TRADES} holdout trades', h_ho['closed_trades'] >= MIN_HOLDOUT_TRADES,
         str(h_ho['closed_trades'])),
        (f'Max drawdown within champion + {MAX_DD_SLACK:g} pts',
         h_ho['max_drawdown'] <= c_ho['max_drawdown'] + MAX_DD_SLACK,
         f"{h_ho['max_drawdown']}% vs {c_ho['max_drawdown']}%"),
        ('Holdout score at least half of train score', h_s >= 0.5 * bs, f'{h_s:.2f} vs {bs:.2f}'),
        (f'Profit factor above 1 in {MIN_STABLE_PERIODS} of 3 train sub-periods',
         sum(1 for x in fold_pf if x > 1.0) >= MIN_STABLE_PERIODS,
         ' / '.join('inf' if x == INF else f'{x:.2f}' for x in fold_pf)),
        (f'No promotion in last {COOLDOWN_DAYS} days', age is None or age >= COOLDOWN_DAYS,
         'none yet' if age is None else f'{age} days ago'),
    ]
    same = {k: champ.get(k) for k in chall} == chall
    return _clean({
        'market': market, 'bot': bot, 'timeframes': timeframes, 'at': datetime.utcnow().isoformat(timespec='seconds'),
        'windows': {'train': [str(cal[i_tr].date()), str(cal[i_ho - 1].date())],
                    'holdout': [str(cal[i_ho].date()), str(end.date())]},
        'symbols': len(frames), 'feedback': fb, 'folds': folds, 'tested': len(pool) + len(ref),
        'champion': {'params': {k: champ[k] for k in chall}, 'train': c_tr, 'holdout': c_ho, 'holdout_score': c_s},
        'challenger': {'params': chall, 'train': bm, 'holdout': h_ho, 'holdout_score': h_s, 'train_score': bs},
        'gates': [{'name': n, 'ok': bool(ok), 'detail': d} for n, ok, d in gates_list],
        'same_as_champion': same,
        'passed': all(ok for _, ok, _ in gates_list) and not same,
    })


def _entry_params(report: dict) -> dict:
    params = dict(report['challenger']['params'])
    if 'trend_tf' in params:
        params['trend_weekly'] = params['trend_tf'] == 'W'  # keep the legacy flag consistent
    return params


def promote(report: dict, force: bool = False) -> dict:
    if not (report['passed'] or force):
        raise ValueError('Gates failed. Use force to override.')
    market, bot = report['market'], report.get('bot', BOT_LIVE)
    curated = load_curated_params()
    bucket = curated.setdefault(_file_key(bot), {})
    prev = copy.deepcopy(bucket.get(market))
    prev_syms = {}
    if bot == BOT_LIVE:
        prev_syms = {s: copy.deepcopy(b) for s, b in curated['symbols'].items() if b.get('market') == market}
    base = (bucket.get(market) or {}).get('params')
    if base is None:  # first hold promotion: start from the live template's gates and timeframes
        base = {k: v for k, v in template_params(curated, market).items() if k not in SIX}
    params = {**base, **_entry_params(report)}
    bucket[market] = {
        **(bucket.get(market) or {}),
        'params': params, 'score': report['challenger']['holdout_score'], 'source': 'evolve',
        'metrics': {**report['challenger']['holdout'], 'mode': 'wallet'},
    }
    if bot == BOT_LIVE:
        for b in curated['symbols'].values():  # wallet mode stamps one algo on every symbol of the book
            if b.get('market') == market:
                b['params'] = dict(params)
    curated['updated_at'] = datetime.utcnow().isoformat(timespec='seconds')
    save_curated_params(curated)
    entry = {**report, 'bot': bot, 'decision': 'promoted', 'forced': not report['passed'],
             'previous': {'template': prev, 'symbols': prev_syms}}
    _save_log(load_log() + [_clean(entry)])
    return entry


def reject(report: dict) -> dict:
    entry = {**report, 'decision': 'rejected'}
    _save_log(load_log() + [entry])
    return entry


def rollback(market: str, bot: str = BOT_LIVE) -> dict:
    log = load_log()
    last = next((e for e in reversed(log) if e['market'] == market and e['decision'] == 'promoted'
                 and e.get('bot', BOT_LIVE) == bot and not e.get('rolled_back')), None)
    if not last:
        raise ValueError(f'No promotion to roll back for {market} ({bot}).')
    curated = load_curated_params()
    bucket = curated.setdefault(_file_key(bot), {})
    if last['previous']['template'] is None:
        bucket.pop(market, None)
    else:
        bucket[market] = last['previous']['template']
    curated['symbols'].update(last['previous']['symbols'])
    curated['updated_at'] = datetime.utcnow().isoformat(timespec='seconds')
    save_curated_params(curated)
    last['rolled_back'] = True
    log.append({'market': market, 'bot': bot, 'at': datetime.utcnow().isoformat(timespec='seconds'),
                'decision': 'rolled_back'})
    _save_log(log)
    return last


def state(market: str, bot: str = BOT_LIVE) -> dict:
    cur = load_curated_params()
    champ = champion_params(cur, market, bot)
    t = cur.get(_file_key(bot), {}).get(market) or {}
    log = [{k: v for k, v in e.items() if k not in ('previous', 'feedback')}
           for e in load_log() if e['market'] == market and e.get('bot', BOT_LIVE) == bot]
    return _clean({'template': champ, 'source': t.get('source', 'curator' if bot == BOT_LIVE else 'defaults'),
                   'updated_at': cur.get('updated_at'), 'log': log[-15:], 'bot': bot})
