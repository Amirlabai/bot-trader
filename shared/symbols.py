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


def asset_type_for_symbol(symbol: str) -> str:
    if is_commodity_symbol(symbol):
        return 'commodity'
    if is_forex_symbol(symbol):
        return 'forex'
    return 'crypto'
