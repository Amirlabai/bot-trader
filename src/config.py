from __future__ import annotations

import os
from dotenv import load_dotenv

# Load environment variables from .env file (if it exists)
load_dotenv()


def _env_float(name, default):
    raw = os.getenv(name, str(default))
    try:
        return float(raw)
    except ValueError as e:
        raise ValueError(f"Invalid {name} in environment: {raw!r}") from e


class Config:
    # API Keys
    CCXT_API_KEY = os.getenv("CCXT_API_KEY")
    CCXT_SECRET = os.getenv("CCXT_SECRET")
    ALPHAVANTAGE_KEY = os.getenv("ALPHAVANTAGE_KEY")
    CMP_API_KEY = os.getenv("CMP_API_KEY") or os.getenv("CMC_API_KEY")
    
    # GitHub Token for pushing (optional if using GITHUB_TOKEN in CI)
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

    # Data Settings
    DATA_DIR = os.path.join(os.getcwd(), 'data')
    LEDGER_FILE = os.path.join(DATA_DIR, 'ledger.json')

    # Defaults
    DEFAULT_TIMEFRAME = '1d'
    INITIAL_STRATEGY_CASH = _env_float("INITIAL_STRATEGY_CASH", 10000)


def _load_risk_settings():
    defaults = {
        'equity_risk_pct': 0.01,
        'min_risk_fraction': 0.25,
        'min_notional_usd': 10.0,
        'max_notional_pct': 0.25,
    }
    settings = {
        'equity_risk_pct': _env_float('EQUITY_RISK_PCT', defaults['equity_risk_pct']),
        'min_risk_fraction': _env_float('MIN_RISK_FRACTION', defaults['min_risk_fraction']),
        'min_notional_usd': _env_float('MIN_NOTIONAL_USD', defaults['min_notional_usd']),
        'max_notional_pct': _env_float('MAX_NOTIONAL_PCT', defaults['max_notional_pct']),
    }
    pct = settings['equity_risk_pct']
    if not 0 < pct <= 1:
        raise ValueError(f"equity_risk_pct must be in (0, 1], got {pct}")
    frac = settings['min_risk_fraction']
    if not 0 < frac < 1:
        raise ValueError(f"min_risk_fraction must be in (0, 1), got {frac}")
    if settings['min_notional_usd'] <= 0:
        raise ValueError(f"min_notional_usd must be > 0, got {settings['min_notional_usd']}")
    max_notional = settings['max_notional_pct']
    if not 0 < max_notional <= 1:
        raise ValueError(f"max_notional_pct must be in (0, 1], got {max_notional}")
    return settings


RISK_SETTINGS = _load_risk_settings()

# Seed crypto book. Daily CMC sync may append new top-15 alts as */USDT
# into data/crypto_universe.json (never removes; open positions stay tradeable).
BASE_CRYPTO_PAIRS = [
    'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT', 'SOL/USDT',
    'ADA/USDT', 'DOGE/USDT', 'AVAX/USDT', 'DOT/USDT', 'TRX/USDT',
]
CRYPTO_UNIVERSE_FILE = os.path.join(os.getcwd(), 'data', 'crypto_universe.json')
CMP_API_KEY = os.getenv('CMP_API_KEY') or os.getenv('CMC_API_KEY')


def load_crypto_pairs(universe_file: str | None = None) -> list:
    from shared.cmc_universe import load_universe, merge_crypto_pairs

    path = universe_file or CRYPTO_UNIVERSE_FILE
    universe = load_universe(path)
    return merge_crypto_pairs(BASE_CRYPTO_PAIRS, universe.get('pairs') or [])


CRYPTO_PAIRS = load_crypto_pairs()
FOREX_PAIRS = [
    'EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'USD/CAD',
    'USD/CHF', 'EUR/GBP', 'EUR/JPY', 'GBP/JPY',
]
COMMODITY_PAIRS = [
    'XAU/USD', 'XAG/USD', 'CL/USD', 'NG/USD', 'HG/USD', 'PL/USD', 'PA/USD',
]

# Frozen mid-cap sim set for EMA/ATR grid (see docs/stocks_ema_grid_*.md).
from shared.stocks_universe import STOCK_SIM_TICKERS  # noqa: E402

STOCKS_UNIVERSE_FILE = os.path.join(os.getcwd(), 'data', 'stocks_universe.json')
STOCKS_FUNDAMENTALS_CACHE = os.path.join(os.getcwd(), 'data', 'stocks_fundamentals_cache.json')
BASE_STOCK_PAIRS = list(STOCK_SIM_TICKERS)


def load_stock_pairs(universe_file: str | None = None) -> list:
    from shared.stocks_universe import load_universe

    path = universe_file or STOCKS_UNIVERSE_FILE
    universe = load_universe(path)
    active = [str(t).upper() for t in (universe.get('active') or []) if t]
    if active:
        return active
    return list(BASE_STOCK_PAIRS)


STOCK_PAIRS = load_stock_pairs()
ALL_MARKET_PAIRS = CRYPTO_PAIRS + FOREX_PAIRS + COMMODITY_PAIRS + STOCK_PAIRS

# Desk market tabs (forex kept visible but untraded until a separate approach).
DASHBOARD_MARKETS = ['crypto', 'forex', 'commodities', 'stocks']

# EMA grid 4y winners (docs/crypto_ema_grid_6m.md / docs/commodities_ema_grid_4y.md).
# ADX/vol off to match the vectorized grid entry path.
_CRYPTO_EMA = {
    'short_window': 20,
    'long_window': 35,
    'trend_window': 100,
    'atr_period': 15,
    'adx_period': 14,
    'adx_min': 0,
    'vol_ma_period': 20,
    'vol_mult': 0.0,
    'atr_buffer': 0.0,
    'sl_atr': 1.0,
    'trail_atr': 2.5,
}
_COMMODITIES_EMA = {
    'short_window': 20,
    'long_window': 25,
    'trend_window': 200,
    'atr_period': 16,
    'adx_period': 14,
    'adx_min': 0,
    'vol_ma_period': 20,
    'vol_mult': 0.0,
    'atr_buffer': 0.0,
    'sl_atr': 3.0,
    'trail_atr': 3.0,
}
# Locked from scratch/tune_stocks_ema_grid.py (10y, 7% risk, ATR20):
# 1) phase atr EMA fixed 20/45/150 → SL10 · trail24
# 2) phase ema risk fixed → 20/40/150
# Reports: docs/stocks_ema_grid_10y_atr.md, docs/stocks_ema_grid_10y_ema.md
_STOCKS_EMA = {
    'short_window': 20,
    'long_window': 40,
    'trend_window': 150,
    'atr_period': 20,
    'adx_period': 14,
    'adx_min': 0,
    'vol_ma_period': 20,
    'vol_mult': 0.0,
    'atr_buffer': 0.0,
    'sl_atr': 10.0,
    'trail_atr': 24.0,
}
# Stocks paper wallets size at 7% equity risk (tuner default).
STOCKS_EQUITY_RISK_PCT = 0.07


def _asset_trail_params(base: dict, *, long_only: bool) -> dict:
    """Full size: trail from entry, no TP1."""
    return {
        **base,
        'long_only': long_only,
        'use_trailing': True,
        'trail_from_entry': True,
        'skip_tp1': True,
        'trend_exit': False,
    }


def _tp1_trail_params(base: dict, *, long_only: bool) -> dict:
    """50% TP1 at 1 ATR, then trail the remainder."""
    return {
        **base,
        'long_only': long_only,
        'use_trailing': True,
        'trail_from_entry': False,
        'skip_tp1': False,
        'trend_exit': False,
    }


def _wallet(market, pairs, rank, label, params):
    return {
        'strategy_module': 'strategies.moving_average',
        'strategy_class': 'MovingAverageStrategy',
        'pairs': list(pairs),
        'params': params,
        'market': market,
        'param_rank': rank,
        'param_label': label,
    }


def _book_wallets(market, pairs, ema):
    """Four exit/side modes per traded book."""
    if market == 'crypto':
        prefix = 'ma_crypto'
    elif market == 'stocks':
        prefix = 'ma_stocks'
    else:
        prefix = f'ma_{market}'
    return {
        f'{prefix}_long_trail': _wallet(
            market, pairs, 1, 'Long · asset trail',
            _asset_trail_params(ema, long_only=True),
        ),
        f'{prefix}_long_tp1': _wallet(
            market, pairs, 2, 'Long · TP1 trail',
            _tp1_trail_params(ema, long_only=True),
        ),
        f'{prefix}_ls_trail': _wallet(
            market, pairs, 3, 'Long/Short · asset trail',
            _asset_trail_params(ema, long_only=False),
        ),
        f'{prefix}_ls_tp1': _wallet(
            market, pairs, 4, 'Long/Short · TP1 trail',
            _tp1_trail_params(ema, long_only=False),
        ),
    }


# 4 wallets × crypto / commodities / stocks. Forex pairs defined but untraded.
TRADING_CONFIG = {}
TRADING_CONFIG.update(_book_wallets('crypto', CRYPTO_PAIRS, _CRYPTO_EMA))
TRADING_CONFIG.update(_book_wallets('commodities', COMMODITY_PAIRS, _COMMODITIES_EMA))
TRADING_CONFIG.update(_book_wallets('stocks', STOCK_PAIRS, _STOCKS_EMA))


def apply_crypto_pairs(pairs: list) -> None:
    """Update module CRYPTO_PAIRS and crypto wallet pair lists in place."""
    global CRYPTO_PAIRS, ALL_MARKET_PAIRS
    CRYPTO_PAIRS = list(pairs)
    ALL_MARKET_PAIRS = CRYPTO_PAIRS + FOREX_PAIRS + COMMODITY_PAIRS + STOCK_PAIRS
    for sid, cfg in TRADING_CONFIG.items():
        if cfg.get('market') == 'crypto':
            cfg['pairs'] = list(pairs)


def apply_stock_pairs(pairs: list) -> None:
    """Update module STOCK_PAIRS and stocks wallet pair lists in place."""
    global STOCK_PAIRS, ALL_MARKET_PAIRS
    STOCK_PAIRS = list(pairs)
    ALL_MARKET_PAIRS = CRYPTO_PAIRS + FOREX_PAIRS + COMMODITY_PAIRS + STOCK_PAIRS
    for sid, cfg in TRADING_CONFIG.items():
        if cfg.get('market') == 'stocks':
            cfg['pairs'] = list(pairs)


def sync_crypto_universe_from_cmc(data_fetcher=None) -> dict | None:
    """Daily CMC top-15: add any new tradable alt as */USDT. No-op without API key."""
    if not CMP_API_KEY:
        print('CMP_API_KEY not set; skipping crypto universe sync.')
        return None

    from shared.cmc_universe import sync_crypto_universe

    def yahoo_ok(pair: str) -> bool:
        if data_fetcher is None:
            return True
        df = data_fetcher.get_data(pair, asset_type='crypto')
        return df is not None and not df.empty

    print('--- CMC top-15 crypto universe sync ---')
    summary = sync_crypto_universe(
        CMP_API_KEY,
        CRYPTO_UNIVERSE_FILE,
        BASE_CRYPTO_PAIRS,
        yahoo_ok=yahoo_ok,
    )
    apply_crypto_pairs(summary['pairs'])
    if summary['added']:
        print(f"Added {len(summary['added'])} pair(s): "
              f"{', '.join(a['pair'] for a in summary['added'])}")
    else:
        print('No new top-15 alts to add.')
    print(f"Crypto pairs ({len(summary['pairs'])}): {', '.join(summary['pairs'])}")
    return summary


def sync_stocks_universe_from_screen(data_fetcher=None, open_symbols=None) -> dict | None:
    """Seed mid-caps, run runner screener, update stocks wallet pairs."""
    from shared.stocks_universe import sync_stocks_universe

    def get_ohlcv(ticker: str):
        if data_fetcher is None:
            return None
        return data_fetcher.get_data(ticker, asset_type='stock')

    def blocked():
        return bool(data_fetcher and getattr(data_fetcher, 'yahoo_blocked', False))

    summary = sync_stocks_universe(
        STOCKS_UNIVERSE_FILE,
        STOCKS_FUNDAMENTALS_CACHE,
        get_ohlcv,
        open_symbols=open_symbols or [],
        yahoo_blocked=blocked,
        refresh_seed=True,
    )
    apply_stock_pairs(summary['active'])
    print(
        f"Stocks active ({len(summary['active'])}): "
        f"{', '.join(summary['active']) or '(none)'}"
    )
    return summary


def open_stock_symbols_from_ledger(ledger) -> list[str]:
    """Collect open stock tickers across stocks wallets (keep tradeable off-screen)."""
    found = []
    seen = set()
    strategies = getattr(ledger, 'ledger', {}).get('strategies', {})
    for sid, cfg in TRADING_CONFIG.items():
        if cfg.get('market') != 'stocks':
            continue
        positions = (strategies.get(sid) or {}).get('positions') or {}
        for sym, pos in positions.items():
            if not pos:
                continue
            if sym not in seen:
                seen.add(sym)
                found.append(sym)
    return found
