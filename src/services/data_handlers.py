import json
from src.config import USER_DATA_FILE, SIGNALS_FILE, COINS_FILE, user_data, signals_data, coins_data, logger

async def save_user_data():
    """Save user data to JSON file"""
    try:
        with open(USER_DATA_FILE, 'w') as file:
            json.dump(user_data, file, indent=4)
        logger.info("User data saved successfully")
        return True
    except Exception as e:
        logger.error(f"Error saving user data: {e}")
        return False

async def save_signals_data():
    """Save signals data to JSON file"""
    try:
        with open(SIGNALS_FILE, 'w') as file:
            json.dump(signals_data, file, indent=4)
        logger.info("Signals data saved successfully")
        return True
    except Exception as e:
        logger.error(f"Error saving signals data: {e}")
        return False

async def save_coins_data():
    """Save coins data to JSON file"""
    try:
        with open(COINS_FILE, 'w') as file:
            json.dump(coins_data, file, indent=4)
        logger.info("Coins data saved successfully")
        return True
    except Exception as e:
        logger.error(f"Error saving coins data: {e}")
        return False 