import pandas as pd
import requests
import time
from datetime import datetime

class DataFetcher:
    def __init__(self, config):
        self.config = config
        self.cache = {}
    
    def fetch_fmp_history(self, symbol, asset_type='forex'):
        """
        Fetches historical data using Financial Modeling Prep API.
        Works for both Forex (e.g., 'EURUSD') and Crypto (e.g., 'BTCUSD').
        """
        api_key = self.config.FMP_API_KEY
        if not api_key:
            print("FMP API Key missing.")
            return pd.DataFrame()

        # Normalize symbol
        # Forex: EUR/USD -> EURUSD
        # Crypto: BTC/USDT -> BTCUSD (FMP usually uses BTCUSD)
        clean_symbol = symbol.replace('/', '')
        
        # Handle USDT -> USD for Crypto (FMP uses BTCUSD, ETHUSD)
        if clean_symbol.endswith('USDT'):
            clean_symbol = clean_symbol.replace('USDT', 'USD')
            
        # Check Cache
        if clean_symbol in self.cache:
            # print(f"DEBUG: Using cached data for {symbol} ({clean_symbol})")
            return self.cache[clean_symbol].copy()
        
        # URL construction
        # FMP Stable Endpoint: https://financialmodelingprep.com/stable/historical-price-eod/full?symbol={symbol}
        url = f"https://financialmodelingprep.com/stable/historical-price-eod/full?symbol={clean_symbol}&apikey={api_key}"
        
        try:
            response = requests.get(url)
            # Check for non-200 responses
            if response.status_code != 200:
                print(f"FMP API returned status {response.status_code} for {clean_symbol}")
                return pd.DataFrame()

            try:
                data = response.json()
            except ValueError:
                print(f"FMP API returned invalid JSON for {clean_symbol}")
                return pd.DataFrame()
            
            # Handle potential dictionary response with 'historical' key (older versions) or list response (stable)
            if isinstance(data, dict):
                if 'historical' in data:
                    data = data['historical']
                elif 'Error Message' in data:
                     print(f"FMP API Error for {clean_symbol}: {data['Error Message']}")
                     return pd.DataFrame()
                else:
                    # Unexpected dict response
                    print(f"Unexpected FMP response format for {clean_symbol}: {data.keys()}")
                    return pd.DataFrame()
            
            if not isinstance(data, list) or not data:
                print(f"No historical data found for {clean_symbol} in FMP response.")
                return pd.DataFrame()
            
            df = pd.DataFrame(data)
            
            # FMP returns: date, open, high, low, close...
            if 'date' not in df.columns:
                 print(f"Date column missing in FMP data for {clean_symbol}. Columns: {df.columns}")
                 return pd.DataFrame()
                 
            df['timestamp'] = pd.to_datetime(df['date'])
            df.set_index('timestamp', inplace=True)
            df.sort_index(inplace=True)
            
            # Select and order columns
            cols_to_keep = ['open', 'high', 'low', 'close', 'volume']
            
            # Ensure columns exist
            existing_cols = [c for c in cols_to_keep if c in df.columns]
            if not existing_cols:
                 print(f"Required columns missing in FMP data for {clean_symbol}.")
                 return pd.DataFrame()
                 
            df = df[existing_cols]
            
            # Fill volume with 0 if missing
            if 'volume' not in df.columns:
                df['volume'] = 0.0
                
            df = df.astype(float)
            
            # Update Cache
            self.cache[clean_symbol] = df.copy()
            
            # Filter out Today's candle if present (Incomplete daily candle)
            # FMP 'historical-price-eod' sometimes includes the current incomplete day.
            if not df.empty:
                last_date = df.index[-1].date()
                today_date = pd.Timestamp.utcnow().date()
                if last_date == today_date:
                    # print(f"DEBUG: Dropping incomplete candle for {clean_symbol} ({last_date})")
                    df = df.iloc[:-1]

            return df
            
        except Exception as e:
            print(f"Error fetching FMP data for {symbol}: {e}")
            return pd.DataFrame()

    def get_data(self, symbol, asset_type='crypto'):
        """
        Unified method to get data.
        asset_type: 'crypto' or 'forex'.
        """
        if asset_type == 'crypto':
             # User requested to switch Binance to FMP if it works.
             # Initial plan: "if it works switch the binance one too"
             return self.fetch_fmp_history(symbol, asset_type='crypto')
        elif asset_type == 'forex':
             return self.fetch_fmp_history(symbol, asset_type='forex')
        else:
            print(f"Unknown asset type: {asset_type}")
            return pd.DataFrame()
