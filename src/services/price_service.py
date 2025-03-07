import requests
from datetime import datetime
from src.config import price_cache, PRICE_CACHE_EXPIRY, logger

def parse_price(price_str):
    """Convert price string like '88k' or '100K' to numeric value"""
    if not price_str:
        return None
    
    # Remove any commas or spaces
    price_str = price_str.replace(',', '').replace(' ', '')
    
    # Check if ends with k or K
    if price_str.lower().endswith('k'):
        # Remove the 'k' and multiply by 1000
        try:
            return float(price_str[:-1]) * 1000
        except ValueError:
            return None
    else:
        # Just convert to float
        try:
            return float(price_str)
        except ValueError:
            return None

async def get_crypto_price(symbol):
    """Get current crypto price from an API with caching"""
    try:
        # Remove $ if present and convert to lowercase
        clean_symbol = symbol.replace("$", "").lower()
        
        # Check cache first
        current_time = datetime.now().timestamp()
        if clean_symbol in price_cache:
            cache_time, price = price_cache[clean_symbol]
            # If cache is still valid (less than PRICE_CACHE_EXPIRY seconds old)
            if current_time - cache_time < PRICE_CACHE_EXPIRY:
                logger.debug(f"Using cached price for {clean_symbol}: ${price}")
                return price
        
        # Common mapping for popular coins
        coin_mapping = {
            "btc": "bitcoin",
            "eth": "ethereum",
            "ada": "cardano",
            "bnb": "binancecoin",
            "sol": "solana",
            "xrp": "ripple",
            "doge": "dogecoin",
            "dot": "polkadot",
            "avax": "avalanche-2",
            "shib": "shiba-inu",
            "matic": "polygon",
            "link": "chainlink",
            "ltc": "litecoin",
            "uni": "uniswap",
            "atom": "cosmos",
            "algo": "algorand",
            "xlm": "stellar",
            "etc": "ethereum-classic"
        }
        
        # Try with mapping first
        coin_id = coin_mapping.get(clean_symbol, clean_symbol)
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data and coin_id in data:
            price = data[coin_id]["usd"]
            # Store in cache
            price_cache[clean_symbol] = (current_time, price)
            return price
        
        # If not found with mapping, try direct ID
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={clean_symbol}&vs_currencies=usd"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data and clean_symbol in data:
            price = data[clean_symbol]["usd"]
            # Store in cache
            price_cache[clean_symbol] = (current_time, price)
            return price
        
        # If still not found, try search
        search_url = f"https://api.coingecko.com/api/v3/search?query={clean_symbol}"
        search_response = requests.get(search_url, timeout=10)
        search_data = search_response.json()
        
        if search_data and "coins" in search_data and search_data["coins"]:
            coin_id = search_data["coins"][0]["id"]
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
            response = requests.get(url, timeout=10)
            data = response.json()
            if data and coin_id in data:
                price = data[coin_id]["usd"]
                # Store in cache
                price_cache[clean_symbol] = (current_time, price)
                return price
        
        return None
    except Exception as e:
        logger.error(f"Error fetching crypto price: {e}")
        return None

async def get_historical_price(coin, timestamp):
    """Get historical price for a coin at a specific timestamp"""
    try:
        # Format date for CoinGecko API (UNIX timestamp in seconds)
        date_obj = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        date_unix = int(date_obj.timestamp())
        
        # Use CoinGecko API to get historical price
        coin_id = "bitcoin" if coin.upper() == "BTC" else coin.lower()
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart/range"
        params = {
            "vs_currency": "usd",
            "from": date_unix - 3600,  # 1 hour before
            "to": date_unix + 3600     # 1 hour after
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if "prices" in data and len(data["prices"]) > 0:
            # Return the closest price to the timestamp
            return data["prices"][0][1]  # Price in USD
        
        return None
    except Exception as e:
        logger.error(f"Error fetching historical price: {e}")
        return None 