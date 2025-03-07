import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv

# Configure logging - set to DEBUG for more verbose output
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG  # Changed from INFO to DEBUG
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# File paths
USER_DATA_FILE = "user_data.json"
SIGNALS_FILE = "signals.json"
COINS_FILE = "coins.json"

# Define timeframes and risk levels
TIMEFRAMES = ["SHORT", "MID", "LONG"]  # Short-term, Mid-term, Long-term
RISK_LEVELS = ["LOW", "MEDIUM", "HIGH"]  # Risk levels for signals

# Signal performance status constants
PENDING = "PENDING"
HIT_TARGET = "HIT_TARGET"
HIT_STOPLOSS = "HIT_STOPLOSS"
EXPIRED = "EXPIRED"

# Signal timeframe durations (in days)
TIMEFRAME_DURATIONS = {
    "SHORT": 1,    # 1 day for short-term signals
    "MID": 7,      # 7 days for mid-term signals
    "LONG": 30     # 30 days for long-term signals
}

# Price cache to reduce API calls
price_cache = {}
# Cache expiry in seconds (5 minutes)
PRICE_CACHE_EXPIRY = 5 * 60

# Load data from files
def load_data():
    global user_data, signals_data, coins_data
    
    # Initialize user data
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r') as f:
            try:
                user_data = json.load(f)
            except json.JSONDecodeError:
                user_data = {"users": {}, "settings": {}, "subscribers": []}
    else:
        user_data = {"users": {}, "settings": {}, "subscribers": []}

    # Initialize signals data
    if os.path.exists(SIGNALS_FILE):
        with open(SIGNALS_FILE, 'r') as f:
            try:
                signals_data = json.load(f)
            except json.JSONDecodeError:
                signals_data = {"signals": []}
    else:
        signals_data = {"signals": []}

    # Initialize coins data
    if os.path.exists(COINS_FILE):
        with open(COINS_FILE, 'r') as f:
            try:
                coins_data = json.load(f)
            except json.JSONDecodeError:
                coins_data = {"coins": {}}
    else:
        coins_data = {"coins": {}}
        
    return user_data, signals_data, coins_data

# Initialize global data variables
user_data, signals_data, coins_data = load_data() 