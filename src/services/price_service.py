import re
import time
import requests
from src.config import price_cache, PRICE_CACHE_EXPIRY, logger, PRICE_API_KEY

async def get_crypto_price(symbol):
    """Get current price for a cryptocurrency symbol"""
    if not symbol:
        return None
    
    # Standardize symbol format
    symbol = symbol.upper()
    
    # Check cache first
    current_time = time.time()
    if symbol in price_cache and current_time - price_cache[symbol]["timestamp"] < PRICE_CACHE_EXPIRY:
        logger.info(f"Using cached price for {symbol}")
        return price_cache[symbol]["price"]
    
    # If not in cache or expired, fetch new price
    try:
        # Primary API: CoinGecko (free tier, no API key needed for basic usage)
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol.lower()}&vs_currencies=usd"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            # CoinGecko uses lowercase symbol as ID
            if symbol.lower() in data and "usd" in data[symbol.lower()]:
                price = float(data[symbol.lower()]["usd"])
                # Cache the result
                price_cache[symbol] = {
                    "price": price,
                    "timestamp": current_time
                }
                logger.info(f"Fetched price for {symbol}: ${price}")
                return price
        
        # Fallback API: Binance (public API)
        binance_url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT"
        binance_response = requests.get(binance_url, timeout=10)
        
        if binance_response.status_code == 200:
            binance_data = binance_response.json()
            if "price" in binance_data:
                price = float(binance_data["price"])
                # Cache the result
                price_cache[symbol] = {
                    "price": price,
                    "timestamp": current_time
                }
                logger.info(f"Fetched price from Binance for {symbol}: ${price}")
                return price
        
        logger.warning(f"Failed to get price for {symbol}")
        return None
    
    except Exception as e:
        logger.error(f"Error fetching price for {symbol}: {e}")
        return None

def parse_price(price_str):
    """Parse price string to float, handling 'k' notation (e.g., '85k' to 85000)"""
    if not price_str:
        return 0.0
    
    try:
        # If it's already a number, return it
        if isinstance(price_str, (int, float)):
            return float(price_str)
        
        # Convert string to lowercase for easier handling
        price_str = str(price_str).lower().strip()
        
        # Handle 'k' notation (e.g., '85k' to 85000)
        if 'k' in price_str:
            price_str = price_str.replace('k', '')
            return float(price_str) * 1000
        
        return float(price_str)
    except (ValueError, TypeError):
        logger.warning(f"Failed to parse price: {price_str}")
        return 0.0 