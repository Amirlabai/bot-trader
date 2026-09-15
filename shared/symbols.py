"""Bot symbols, asset classes, and Yahoo ticker mapping."""

# Bot pair -> Yahoo futures ticker (daily OHLCV via yfinance).
COMMODITY_YAHOO_TICKERS = {
    'XAU/USD': 'GC=F',  # Gold
    'XAG/USD': 'SI=F',  # Silver
    'CL/USD': 'CL=F',   # Crude oil (WTI)
    'NG/USD': 'NG=F',   # Natural gas
    'HG/USD': 'HG=F',   # Copper
    'PL/USD': 'PL=F',   # Platinum
    'PA/USD': 'PA=F',   # Palladium
}

FOREX_CURRENCIES = frozenset(['EUR', 'USD', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF'])


def is_commodity_symbol(symbol: str) -> bool:
    return symbol in COMMODITY_YAHOO_TICKERS


def is_forex_symbol(symbol: str) -> bool:
    if is_commodity_symbol(symbol):
        return False
    return (
        any(cur in symbol for cur in FOREX_CURRENCIES)
        and '/' in symbol
        and len(symbol) == 7
    )


def is_stock_symbol(symbol: str) -> bool:
    """US equity tickers are plain symbols without a slash (e.g. NVDA, BRK-B)."""
    if not symbol or '/' in symbol:
        return False
    if is_commodity_symbol(symbol):
        return False
    return True


def asset_type_for_symbol(symbol: str) -> str:
    if is_commodity_symbol(symbol):
        return 'commodity'
    if is_forex_symbol(symbol):
        return 'forex'
    if is_stock_symbol(symbol):
        return 'stock'
    return 'crypto'
