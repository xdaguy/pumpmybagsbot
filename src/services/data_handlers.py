import json
from src.config import USER_DATA_FILE, SIGNALS_FILE, COINS_FILE, user_data, signals_data, coins_data, logger

async def save_user_data():
    """Save user data to file"""
    try:
        with open(USER_DATA_FILE, 'w') as f:
            json.dump(user_data, f)
        logger.debug("User data saved successfully")
    except Exception as e:
        logger.error(f"Failed to save user data: {e}")

async def save_signals_data():
    """Save signals data to file"""
    try:
        with open(SIGNALS_FILE, 'w') as f:
            json.dump(signals_data, f)
        logger.debug("Signals data saved successfully")
    except Exception as e:
        logger.error(f"Failed to save signals data: {e}")

async def save_coins_data():
    """Save coins data to file"""
    try:
        with open(COINS_FILE, 'w') as f:
            json.dump(coins_data, f)
        logger.debug("Coins data saved successfully")
    except Exception as e:
        logger.error(f"Failed to save coins data: {e}") 