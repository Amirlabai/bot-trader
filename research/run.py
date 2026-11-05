"""Run one experiment spec and write a results directory.

    python -m research.run research/experiments/scale_out_grid.json [--refresh] [--pairs BTC/USDT ...]

Output: research/results/<experiment>/<YYYYmmdd-HHMM>_<git sha>/
    spec.json      the spec plus what actually ran (pairs, bar ranges, cutoff, git sha)
    variants.csv   one row of metrics per variant (net R after fees unless stated)
    report.md      ranked comparison against the baseline
    trades.csv.gz  every simulated trade (not tracked in git)
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import subprocess
import time
from datetime import datetime, timezone

import pandas as pd

import research  # noqa: F401  (sets sys.path)
from research.engine import simulate
from research.history import get_history
from research.metrics import split_date, variant_metrics
from research.settings import (
    DEFAULT_FEE_RATE,
    DEFAULT_OOS_MONTHS,
    DEFAULT_YEARS,
    REPO_ROOT,
    RESULTS_DIR,
    STRATEGY_ID,
)
from research.signals import get_signals
from research.features import BTC_SYMBOL
from research.exit_policy import ExitPolicy

BASELINE = 'baseline'


def _git(*args) -> str:
    try:
        return subprocess.check_output(['git', *args], cwd=REPO_ROOT, text=True).strip()
    except Exception:
        return ''


def variant_name(p: dict) -> str:
    parts = []
    if p.get('early_exit_bars'):
        parts.append(f"early{int(p['early_exit_bars'])}b{p.get('early_exit_min_r', 0.5):g}r")
    if p.get('step_r') and p.get('fraction'):
        name = f"r{p['step_r']:g}_sell{round(p['fraction'] * 100):d}"
        if p.get('fraction_step'):
            name += f"_plus{round(p['fraction_step'] * 100):d}"
        if p.get('first_r') is not None and p.get('first_r') != p.get('step_r'):
            name += f"_first{p['first_r']:g}"
        if p.get('max_steps'):
            name += f"_max{p['max_steps']}"
        if p.get('breakeven_after_first'):
            name += '_be'
        parts.append(name)
    return '_'.join(parts) if parts else BASELINE


def base_exit(strategy_params: dict) -> dict:
    """ExitPolicy fields that reproduce the live wallet's exit."""
    tp1 = not (strategy_params.get('skip_tp1') or strategy_params.get('trail_from_entry'))
    trail = float(strategy_params.get('trail_atr', 3.0))
    if not strategy_params.get('use_trailing', True):
        trail = 0.0
    return {
        'sl_atr': float(strategy_params.get('sl_atr', 1.0)),
        'trail_atr': trail,
        'trail_arm_r': float(strategy_params.get('trail_arm_r', 0.0) or 0.0),
        'tp1_live': bool(tp1),
    }


_EXTRA_NAMES = (
    ('atr_mode', lambda v: f'atr{v}'),
    ('tp1_live', lambda v: 'tp1' if v else 'notp1'),
    ('sl_atr', lambda v: f'sl{v:g}'),
    ('trail_atr', lambda v: f'trail{v:g}'),
    ('trail_arm_r', lambda v: f'arm{v:g}'),
    ('tp1_fraction', lambda v: f'tp1x{round(v * 100):d}'),
)
_NAME_DEFAULTS = {'atr_mode': 'frozen', 'tp1_fraction': 0.5}


def _full_name(params: dict, base: dict) -> str:
    """variant_name plus a tag for every live-exit field that differs from the live wallet."""
    name = variant_name(params)
    tags = []
    for key, fmt in _EXTRA_NAMES:
        default = base.get(key, _NAME_DEFAULTS.get(key))
        if key in params and params[key] != default:
            tags.append(fmt(params[key]))
    if not tags:
        return name
    return '_'.join(tags) if name == BASELINE else name + '_' + '_'.join(tags)


def expand_variants(spec: dict, strategy_params: dict) -> list[ExitPolicy]:
    base = base_exit(strategy_params)
    raw = []
    if spec.get('include_baseline', True):
        raw.append({})
    raw.extend(spec.get('variants') or [])
    for block in spec.get('grid') or []:
        keys = list(block)
        for combo in itertools.product(*(block[k] for k in keys)):
            raw.append(dict(zip(keys, combo)))
    policies, seen = [], set()
    for item in raw:
        params = {**base, **item}
        params['name'] = item.get('name') or _full_name(params, base)
        if params['name'] in seen:
            continue
        seen.add(params['name'])
        policies.append(ExitPolicy.from_dict(params))
    return policies


def load_spec(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as handle:
        spec = json.load(handle)
    spec.setdefault('name', os.path.splitext(os.path.basename(path))[0])
    return spec


def resolve_pairs(spec: dict, override=None) -> list[str]:
    if override:
        return list(override)
    pairs = spec.get('pairs', 'universe')
    if pairs == 'universe':
        from config import TRADING_CONFIG
        pairs = list(TRADING_CONFIG[spec.get('strategy_id', STRATEGY_ID)]['pairs'])
    return list(pairs)


def load_live_strategy(strategy_id: str = STRATEGY_ID):
    from config import TRADING_CONFIG
    from main import load_strategy
    cfg = TRADING_CONFIG[strategy_id]
    strategy = load_strategy(cfg['strategy_module'], cfg['strategy_class'], cfg['params'])
    if strategy is None:
        raise SystemExit('Strategy failed to load.')
    return strategy


def expand_entry_modes(spec: dict):
    """'entry_modes': list of blocks; list values are crossed. 'signal' is always first."""
    from research.entries import EntryMode
    out, seen = [EntryMode()], {'signal'}
    for block in spec.get('entry_modes') or []:
        keys = list(block)
        values = [v if isinstance(v, list) else [v] for v in block.values()]
        for combo in itertools.product(*values):
            mode = EntryMode.from_dict(dict(zip(keys, combo)))
            if mode.name not in seen:
                seen.add(mode.name)
                out.append(mode)
    return out


def compare_entries(mode_trades: pd.DataFrame, base_trades: pd.DataFrame) -> dict:
    """How a confirmation mode changes the trade set, matched by the origin signal bar."""
    if base_trades is None or base_trades.empty:
        return {}
    base = base_trades.assign(_key=base_trades['symbol'] + '|' + base_trades['entry_date'])
    keys = set()
    if mode_trades is not None and not mode_trades.empty:
        keys = set(mode_trades['symbol'] + '|' + mode_trades['signal_date'])
    kept = base['_key'].isin(keys)
    win = base['r_net'] > 0
    big = base['r_net'] >= 3.0
    false_start = (base['exit_kind'] == 'stop_loss') & (base['mfe_r'] < 1.0)
    n_mode = 0 if mode_trades is None else len(mode_trades)
    mean_base = float(base['r_net'].mean())
    r_mode = 0.0 if mode_trades is None or mode_trades.empty else float(mode_trades['r_net'].sum())

    def share(mask_kept, mask_all):
        total = int(mask_all.sum())
        return float((mask_kept & mask_all).sum() / total) if total else None

    return {
        'losers_blocked': share(~kept, ~win),
        'false_starts_blocked': share(~kept, false_start),
        'winners_kept': share(kept, win),
        'big_winners_kept': share(kept, big),
        'winner_r_kept': (float(base.loc[kept & win, 'r_net'].sum() / base.loc[win, 'r_net'].sum())
                          if win.any() else None),
        'new_trades': int(n_mode - kept.sum()),
        'lift_r': r_mode - n_mode * mean_base,
    }


def build_filters(cfg: dict, signals_by_pair: dict, base_policy: ExitPolicy, fee_rate: float):
    """Walk-forward entry filters. Returns ({key: {symbol: mask}}, report lines, info).

    Every arm, including 'none', only trades from the first walk-forward block on,
    so the baseline and the filtered arms cover the same period.
    """
    from research.filters.dataset import entry_table
    from research.filters.evaluate import evaluate, format_eval
    from research.filters.walkforward import walk_forward

    label = cfg.get('label', 'false_start')
    skip_q = [float(q) for q in cfg.get('skip_q', [0.1, 0.2, 0.3, 0.4, 0.5])]
    models = cfg.get('models', ['logistic', 'gbm'])
    train_months = int(cfg.get('train_months', 18))
    refit_months = int(cfg.get('refit_months', 3))

    base_trades = []
    for symbol, sig in signals_by_pair.items():
        base_trades.extend(simulate(symbol, sig, base_policy, fee_rate))
    table = entry_table(signals_by_pair, pd.DataFrame(base_trades), label=label)
    print(f'  Entry table: {len(table)} signals, {int(table["taken"].sum())} baseline trades')

    md = ['## Entry filter (walk-forward, out-of-sample)', '',
          f'Label `{label}`. First {train_months} months train only; refit every {refit_months} months '
          'on trades closed before each block. The skip threshold is a quantile of training probabilities.', '']
    filters, info, wf_start = {}, {'label': label, 'models': {}}, None
    probs_by_model = {}
    for name in models:
        probs, windows, model = walk_forward(table, name, train_months=train_months,
                                             refit_months=refit_months, skip_q=skip_q)
        if probs.empty:
            print(f'  Filter {name}: no walk-forward blocks')
            continue
        probs_by_model[name] = probs
        start = min(w['start'] for w in windows)
        wf_start = start if wf_start is None else min(wf_start, start)
        ev = evaluate(table, probs, skip_q, model=model, model_name=name)
        md += format_eval(name, ev)
        info['models'][name] = {
            'auc': ev.get('auc'), 'windows': len(windows),
            'first_block': str(start), 'by_q': ev.get('by_q'), 'weights': ev.get('weights'),
        }
        print(f"  Filter {name}: AUC {ev.get('auc', float('nan')):.3f} over {ev.get('n_trades')} trades")
    if wf_start is None:
        return {'none': None}, md, info
    info['walk_forward_from'] = str(wf_start)

    def _masks(skip_lookup):
        out = {}
        for symbol, sig in signals_by_pair.items():
            ts = pd.Series(sig.index)
            allowed = (ts >= wf_start).to_numpy()
            if skip_lookup is not None:
                skip = skip_lookup.get(symbol, set())
                allowed = allowed & ~ts.isin(list(skip)).to_numpy()
            out[symbol] = allowed
        return out

    filters['none'] = _masks(None)
    for name, probs in probs_by_model.items():
        for q in skip_q:
            skipped = probs.loc[probs[f'skip_{q:g}']]
            lookup = {s: set(g['ts']) for s, g in skipped.groupby('symbol')}
            filters[f'{name}_skip{round(q * 100):d}'] = _masks(lookup)
    return filters, md, info


def run_experiment(spec: dict, *, refresh=False, pairs_override=None, out_root=RESULTS_DIR,
                   write=True) -> dict:
    started = time.time()
    years = float(spec.get('years', DEFAULT_YEARS))
    fee_rate = float(spec.get('fee_rate', DEFAULT_FEE_RATE))
    oos_months = int(spec.get('oos_months', DEFAULT_OOS_MONTHS))
    strategy_id = spec.get('strategy_id', STRATEGY_ID)
    strategy = load_live_strategy(strategy_id)
    policies = expand_variants(spec, strategy.params)
    pairs = resolve_pairs(spec, pairs_override)
    print(f"Experiment {spec['name']}: {len(policies)} variants, {len(pairs)} pairs, {years:g} years")

    btc_symbol = spec.get('btc_symbol', BTC_SYMBOL)
    btc = get_history(btc_symbol, refresh=refresh)
    end = btc.index[-1] if btc is not None and not btc.empty else pd.Timestamp.now()
    start = (pd.Timestamp(end) - pd.Timedelta(days=int(round(365 * years)))).normalize()
    signals_by_pair, ranges, missing, histories = {}, {}, [], {}
    for symbol in pairs:
        df = btc if symbol == btc_symbol else get_history(symbol, refresh=refresh)
        if df is None or df.empty:
            print(f'  {symbol}: no history, skipped')
            missing.append(symbol)
            continue
        sig = get_signals(symbol, df, strategy, btc, start=start)
        if sig is None or sig.empty:
            print(f'  {symbol}: no bars in the window, skipped')
            missing.append(symbol)
            continue
        signals_by_pair[symbol] = sig
        histories[symbol] = df
        ranges[symbol] = [str(sig.index[0]), str(sig.index[-1]), int(len(sig))]

    last_bar = max(pd.Timestamp(r[1]) for r in ranges.values())
    cutoff = split_date(last_bar, oos_months)

    filters = {'none': None}
    filter_md, filter_info = [], {}
    if spec.get('entry_filter'):
        base_policy = ExitPolicy.from_dict({'name': BASELINE, **base_exit(strategy.params)})
        filters, filter_md, filter_info = build_filters(
            spec['entry_filter'], signals_by_pair, base_policy, fee_rate,
        )

    modes = expand_entry_modes(spec)
    save_exits = spec.get('save_trades_for_exits')
    all_trades, rows = [], []
    signal_trades = {}  # exit name -> trades of the 'signal' entry mode (for entry comparisons)
    for mode in modes:
        contexts = {}
        if mode.type != 'signal':
            from research.entries import EntryContext
            spans = (int(strategy.params.get('short_window', 10)), int(strategy.params.get('long_window', 20)))
            contexts = {s: EntryContext(sig, mode, *spans, history=histories.get(s))
                        for s, sig in signals_by_pair.items()}
        for fkey, masks in filters.items():
            for policy in policies:
                name = policy.name if fkey == 'none' else f'{fkey}+{policy.name}'
                if mode.type != 'signal':
                    name = f'{mode.name}+{name}'
                trades = []
                for symbol, sig in signals_by_pair.items():
                    mask = None if masks is None else masks[symbol]
                    trades.extend(simulate(
                        symbol, sig, policy, fee_rate, entry_allowed=mask,
                        entry_mode=mode, entry_ctx=contexts.get(symbol),
                    ))
                for t in trades:
                    t['variant'] = name
                    t['filter'] = fkey
                    t['entry_mode'] = mode.name
                frame = pd.DataFrame(trades)
                metrics = variant_metrics(frame, cutoff) if not frame.empty else {}
                row = {'variant': name, 'filter': fkey, 'exit': policy.name, 'entry_mode': mode.name,
                       **policy.to_dict(), **metrics, 'name': name}
                if mode.type == 'signal' and fkey == 'none':
                    signal_trades[policy.name] = frame
                elif fkey == 'none' and policy.name in signal_trades:
                    row.update(compare_entries(frame, signal_trades[policy.name]))
                rows.append(row)
                if save_exits is None or policy.name in save_exits:
                    all_trades.extend(trades)
    variants = pd.DataFrame(rows)

    if spec.get('audit') and signal_trades.get(BASELINE) is not None:
        from research.audit import build_audit, structure_table
        cfg = spec['audit'] if isinstance(spec['audit'], dict) else {}
        table = structure_table(signals_by_pair, signal_trades[BASELINE],
                                pivot_k=int(cfg.get('pivot_k', 3)), lookback=int(cfg.get('lookback', 120)))
        filter_md = list(filter_md) + build_audit(table)

    sha = _git('rev-parse', '--short', 'HEAD') or 'nogit'
    dirty = bool(_git('status', '--porcelain'))
    resolved = {
        'spec': spec,
        'git_sha': sha,
        'git_dirty': dirty,
        'ran_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'strategy_id': strategy_id,
        'strategy_params': strategy.params,
        'window_start': str(start),
        'fee_rate': fee_rate,
        'oos_months': oos_months,
        'oos_from': str(cutoff),
        'pairs': ranges,
        'missing_pairs': missing,
        'btc_symbol': btc_symbol,
        'variants': [p.to_dict() for p in policies],
        'filters': filter_info,
    }
    result = {'resolved': resolved, 'variants': variants, 'trades': pd.DataFrame(all_trades)}
    if write:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')
        out_dir = os.path.join(out_root, spec['name'], f"{stamp}_{sha}{'_dirty' if dirty else ''}")
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, 'spec.json'), 'w', encoding='utf-8') as handle:
            json.dump(resolved, handle, indent=2, default=str)
            handle.write('\n')
        variants.to_csv(os.path.join(out_dir, 'variants.csv'), index=False)
        result['trades'].to_csv(os.path.join(out_dir, 'trades.csv.gz'), index=False)
        from research.report import write_report
        write_report(out_dir, resolved, variants, extra=filter_md)
        result['out_dir'] = out_dir
        print(f'Results: {out_dir}')
    print(f'Done in {time.time() - started:.0f}s')
    return result


def main():
    parser = argparse.ArgumentParser(description='Run a research experiment spec.')
    parser.add_argument('spec')
    parser.add_argument('--refresh', action='store_true', help='refetch daily history from Yahoo')
    parser.add_argument('--pairs', nargs='*', default=None)
    args = parser.parse_args()
    run_experiment(load_spec(args.spec), refresh=args.refresh, pairs_override=args.pairs)


if __name__ == '__main__':
    main()
