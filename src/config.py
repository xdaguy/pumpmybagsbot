import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token from environment variables
BOT_TOKEN = os.getenv('BOT_TOKEN')
PRICE_API_KEY = os.getenv('PRICE_API_KEY')

# Constants for signal statuses
PENDING = "PENDING"
HIT_TARGET = "HIT TARGET"
HIT_STOPLOSS = "HIT STOPLOSS"
EXPIRED = "EXPIRED"

# Valid timeframes and risk levels
TIMEFRAMES = ["SHORT", "MID", "LONG"]
RISK_LEVELS = ["LOW", "MEDIUM", "HIGH"]

# Timeframe durations in days
TIMEFRAME_DURATIONS = {
    "SHORT": 1,  # 1 day
    "MID": 7,    # 1 week
    "LONG": 30   # 1 month
}

# File paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
USER_DATA_FILE = DATA_DIR / "user_data.json"
SIGNALS_FILE = DATA_DIR / "signals_data.json"
COINS_FILE = DATA_DIR / "coins_data.json"

# Price cache expiry in seconds (5 minutes)
PRICE_CACHE_EXPIRY = 300
price_cache = {}  # In-memory cache for prices

# Data storage
user_data = {
    "users": {},    # User information and preferences
    "settings": {}  # User settings
}

signals_data = {
    "signals": []   # Signal information
}

coins_data = {
    "coins": []     # Tracked coins information
}

def load_data():
    """Load data from JSON files"""
    global user_data, signals_data, coins_data
    
    # Ensure data directory exists
    DATA_DIR.mkdir(exist_ok=True)
    
    try:
        # Load user data
        if USER_DATA_FILE.exists():
            with open(USER_DATA_FILE, 'r') as file:
                user_data = json.load(file)
        else:
            # Initialize user data file if it doesn't exist
            with open(USER_DATA_FILE, 'w') as file:
                json.dump(user_data, file, indent=4)
        
        # Load signals data
        if SIGNALS_FILE.exists():
            with open(SIGNALS_FILE, 'r') as file:
                signals_data = json.load(file)
        else:
            # Initialize signals data file if it doesn't exist
            with open(SIGNALS_FILE, 'w') as file:
                json.dump(signals_data, file, indent=4)
        
        # Load coins data
        if COINS_FILE.exists():
            with open(COINS_FILE, 'r') as file:
                coins_data = json.load(file)
        else:
            # Initialize coins data file if it doesn't exist
            with open(COINS_FILE, 'w') as file:
                json.dump(coins_data, file, indent=4)
                
        logger.info("Data loaded successfully")
    except Exception as e:
        logger.error(f"Error loading data: {e}") 