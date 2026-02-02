import ccxt
import pandas as pd
import requests
import time
from datetime import datetime

class DataFetcher:
    def __init__(self, config):
        self.config = config
        self.ccxt_exchange = ccxt.binance({
            'apiKey': config.CCXT_API_KEY,
            'secret': config.CCXT_SECRET,
            'enableRateLimit': True,
            'options': {
                'adjustForTimeDifference': True,
                'recvWindow': 60000
            }
        })
        # Force time sync manually before loading markets
        self.ccxt_exchange.load_time_difference()
        self.ccxt_exchange.load_markets()
    
    def fetch_crypto_ohlcv(self, symbol, timeframe='1d', limit=100):
        """
        Fetches OHLCV data for a crypto symbol using CCXT.
        Returns a DataFrame with columns: open, high, low, close, volume.
        Timestamp is set as index.
        """
        try:
            # CCXT fetch_ohlcv returns list of lists: [timestamp, open, high, low, close, volume]
            ohlcv = self.ccxt_exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
        except Exception as e:
            print(f"Error fetching crypto data for {symbol}: {e}")
            return pd.DataFrame()

    def fetch_forex_daily(self, symbol):
        """
        Fetches daily forex data using Alpha Vantage.
        Symbol should be in format 'EURUSD' or 'EUR/USD' (will be normalized).
        Returns DataFrame with standard columns.
        """
        clean_symbol = symbol.replace('/', '')
        from_currency = clean_symbol[:3]
        to_currency = clean_symbol[3:]
        
        api_key = self.config.ALPHAVANTAGE_KEY
        if not api_key:
            print("Alpha Vantage API Key missing.")
            return pd.DataFrame()

        url = f'https://www.alphavantage.co/query?function=FX_DAILY&from_symbol={from_currency}&to_symbol={to_currency}&apikey={api_key}'
        
        try:
            response = requests.get(url)
            data = response.json()
            
            time_series = data.get('Time Series FX (Daily)', {})
            if not time_series:
                 # Try compact if full history fails or API issues, though FX_DAILY usually returns full.
                 print(f"No data returned for forex {symbol}. Response keys: {data.keys()}")
                 return pd.DataFrame()

            df = pd.DataFrame.from_dict(time_series, orient='index')
            # Columns are like "1. open", "2. high", etc. Rename them.
            df.rename(columns={
                '1. open': 'open',
                '2. high': 'high',
                '3. low': 'low',
                '4. close': 'close'
            }, inplace=True)
            
            # Alpha Vantage FX_DAILY doesn't always provide volume consistently, sometimes it's missing.
            # We will fill volume with 0 if missing.
            if '5. volume' in df.columns:
                 df.rename(columns={'5. volume': 'volume'}, inplace=True)
            else:
                 df['volume'] = 0

            df.index = pd.to_datetime(df.index)
            df = df.astype(float)
            df.sort_index(inplace=True)
            
            return df
        except Exception as e:
            print(f"Error fetching forex data for {symbol}: {e}")
            return pd.DataFrame()

    def get_data(self, symbol, asset_type='crypto'):
        """
        Unified method to get data.
        asset_type: 'crypto' or 'forex'.
        """
        if asset_type == 'crypto':
            return self.fetch_crypto_ohlcv(symbol)
        elif asset_type == 'forex':
             return self.fetch_forex_daily(symbol)
        else:
            print(f"Unknown asset type: {asset_type}")
            return pd.DataFrame()
