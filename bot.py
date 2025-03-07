import os
import json
import logging
import re
from datetime import datetime, timedelta
import requests
import asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler

# Configure logging - set to DEBUG for more verbose output
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG  # Changed from INFO to DEBUG
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# File to store user data and signals
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

# Initialize data
if os.path.exists(USER_DATA_FILE):
    with open(USER_DATA_FILE, 'r') as f:
        try:
            user_data = json.load(f)
        except json.JSONDecodeError:
            user_data = {"users": {}}
else:
    user_data = {"users": {}}

if os.path.exists(SIGNALS_FILE):
    with open(SIGNALS_FILE, 'r') as f:
        try:
            signals_data = json.load(f)
        except json.JSONDecodeError:
            signals_data = {"signals": []}
else:
    signals_data = {"signals": []}

if os.path.exists(COINS_FILE):
    with open(COINS_FILE, 'r') as f:
        try:
            coins_data = json.load(f)
        except json.JSONDecodeError:
            coins_data = {"coins": {}}
else:
    coins_data = {"coins": {}}

async def save_user_data():
    """Save user data to file"""
    with open(USER_DATA_FILE, 'w') as f:
        json.dump(user_data, f)

async def save_signals_data():
    """Save signals data to file"""
    with open(SIGNALS_FILE, 'w') as f:
        json.dump(signals_data, f)

async def save_coins_data():
    """Save coins data to file"""
    with open(COINS_FILE, 'w') as f:
        json.dump(coins_data, f)

# Function to parse price values (handle k/K notation)
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

async def check_signal_performance(signal):
    """Check if a signal has hit its target or failed"""
    if "status" in signal and signal["status"] != PENDING:
        # Already evaluated
        return signal
    
    coin = signal.get("coin")
    if not coin:
        return signal  # Can't evaluate without a coin
    
    # Get current price
    current_price = await get_crypto_price(coin)
    if not current_price:
        return signal  # Can't evaluate without current price
    
    # Get entry price, target price and stop loss
    entry_price = parse_price(signal.get("limit_order"))
    target_price = parse_price(signal.get("take_profit"))
    
    # Default stop loss (20% in opposite direction of trade)
    position = signal.get("position", "Long")
    stop_loss_pct = 0.2  # 20% default stop loss
    
    if entry_price:
        if position.lower() == "long":
            # For long positions, stop loss is below entry price
            stop_loss = entry_price * (1 - stop_loss_pct)
            # Check if target hit (price went up to target)
            if target_price and current_price >= target_price:
                signal["status"] = HIT_TARGET
                signal["performance"] = ((target_price - entry_price) / entry_price) * 100
                signal["exit_price"] = target_price
                signal["exit_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Check if stop loss hit (price went down to stop loss)
            elif current_price <= stop_loss:
                signal["status"] = HIT_STOPLOSS
                signal["performance"] = ((stop_loss - entry_price) / entry_price) * 100
                signal["exit_price"] = stop_loss
                signal["exit_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:  # Short position
            # For short positions, stop loss is above entry price
            stop_loss = entry_price * (1 + stop_loss_pct)
            # Check if target hit (price went down to target)
            if target_price and current_price <= target_price:
                signal["status"] = HIT_TARGET
                signal["performance"] = ((entry_price - target_price) / entry_price) * 100
                signal["exit_price"] = target_price
                signal["exit_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Check if stop loss hit (price went up to stop loss)
            elif current_price >= stop_loss:
                signal["status"] = HIT_STOPLOSS
                signal["performance"] = ((entry_price - stop_loss) / entry_price) * 100
                signal["exit_price"] = stop_loss
                signal["exit_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Check for expiration based on timeframe
    signal_date = datetime.strptime(signal.get("timestamp"), "%Y-%m-%d %H:%M:%S")
    timeframe = signal.get("timeframe", "MID")
    expiration_days = TIMEFRAME_DURATIONS.get(timeframe, 7)  # Default to 7 days if timeframe not specified
    
    if datetime.now() > signal_date + timedelta(days=expiration_days) and signal.get("status") == PENDING:
        signal["status"] = EXPIRED
        # Calculate performance at expiration
        if entry_price:
            if position.lower() == "long":
                signal["performance"] = ((current_price - entry_price) / entry_price) * 100
            else:  # Short position
                signal["performance"] = ((entry_price - current_price) / entry_price) * 100
            signal["exit_price"] = current_price
            signal["exit_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # If still pending, calculate current unrealized performance
    if signal.get("status") == PENDING and entry_price:
        if position.lower() == "long":
            signal["unrealized_performance"] = ((current_price - entry_price) / entry_price) * 100
        else:  # Short position
            signal["unrealized_performance"] = ((entry_price - current_price) / entry_price) * 100
    
    return signal

async def update_all_signals_performance():
    """Update performance status for all signals"""
    updated = False
    for signal in signals_data["signals"]:
        # Initialize status if not present
        if "status" not in signal:
            signal["status"] = PENDING
        
        # Skip signals that are already completed
        if signal["status"] in [HIT_TARGET, HIT_STOPLOSS, EXPIRED]:
            continue
        
        # Check and update signal performance
        updated_signal = await check_signal_performance(signal)
        if updated_signal.get("status") != PENDING:
            updated = True
    
    if updated:
        await save_signals_data()
    
    return updated

async def periodic_signal_check(context: ContextTypes.DEFAULT_TYPE):
    """Periodically check signal performance"""
    logger.info("Running periodic signal performance check")
    updated = await update_all_signals_performance()
    if updated:
        logger.info("Signal performances updated")
        
        # Send notifications for updated signals
        completed_signals = []
        for signal in signals_data["signals"]:
            # Check if signal was just completed (has exit_date within the last hour)
            if "exit_date" in signal and signal.get("status") != PENDING:
                exit_date = datetime.strptime(signal["exit_date"], "%Y-%m-%d %H:%M:%S")
                if datetime.now() - exit_date < timedelta(hours=1):
                    completed_signals.append(signal)
        
        # Send notifications for each completed signal
        for signal in completed_signals:
            coin = signal.get("coin")
            status = signal.get("status")
            timeframe = signal.get("timeframe")
            risk_level = signal.get("risk")
            
            status_emoji = "✅" if status == HIT_TARGET else "❌" if status == HIT_STOPLOSS else "⏰"
            performance = signal.get("performance", 0)
            perf_sign = "+" if performance >= 0 else ""
            
            message = (
                f"{status_emoji} *Signal Update* {status_emoji}\n\n"
                f"*Coin:* {coin}\n"
                f"*Status:* {status}\n"
                f"*Performance:* {perf_sign}{performance:.2f}%\n"
                f"*Entry Price:* ${parse_price(signal.get('limit_order', '0')):,.2f}\n"
                f"*Exit Price:* ${signal.get('exit_price', 0):,.2f}\n"
                f"*Exit Date:* {signal.get('exit_date', 'Unknown')}\n\n"
                f"*Original Signal:*\n{signal.get('text', 'N/A')}"
            )
            
            # Send to subscribers based on their settings
            for user_id, user_info in user_data["users"].items():
                # Check if user is subscribed
                is_subscribed = user_info.get("subscribed", False)
                if not is_subscribed:
                    continue
                
                # Check if signal mentions one of user's favorite coins
                favorite_coins = user_info.get("favorite_coins", [])
                is_favorite = coin in favorite_coins if coin else False
                
                # Check user settings
                settings = user_data.get("settings", {}).get(user_id, {
                    "notify_all_signals": True,
                    "notify_favorites_only": False,
                    "risk_filter": "ALL",
                    "timeframe_filter": "ALL"
                })
                
                # Apply user settings filters
                should_notify = False
                
                # Check notification preferences
                if settings["notify_all_signals"] and not settings["notify_favorites_only"]:
                    should_notify = True
                elif settings["notify_favorites_only"] and is_favorite:
                    should_notify = True
                else:
                    continue  # Skip this user based on notification settings
                
                # Apply risk level filter if set
                if settings["risk_filter"] != "ALL" and risk_level != settings["risk_filter"]:
                    continue  # Skip if risk level doesn't match filter
                
                # Apply timeframe filter if set
                if settings["timeframe_filter"] != "ALL" and timeframe != settings["timeframe_filter"]:
                    continue  # Skip if timeframe doesn't match filter
                
                try:
                    await context.bot.send_message(
                        chat_id=user_info["chat_id"],
                        text=message,
                        parse_mode="Markdown"
                    )
                    logger.info(f"Signal update sent to user {user_id}")
                except Exception as e:
                    logger.error(f"Failed to send signal update to user {user_id}: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    if str(chat_id) not in user_data["users"]:
        user_data["users"][str(chat_id)] = {
            "name": user.full_name,
            "username": user.username,
            "chat_id": chat_id,
            "subscribed": True,
            "joined_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "favorite_coins": []
        }
        await save_user_data()
    
    # Create keyboard with main commands
    keyboard = [
        [KeyboardButton("/signals"), KeyboardButton("/performance")],
        [KeyboardButton("/coins"), KeyboardButton("/traders")],
        [KeyboardButton("/price BTC"), KeyboardButton("/help")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"🚀 *Welcome to Pump My Bags Bot!* 🚀\n\n"
        f"Hi {user.full_name}! I'll forward crypto trading signals from groups where I'm tagged, and track their performance.\n\n"
        f"📊 Now with *Signal Performance Tracking* to automatically monitor which signals hit their targets!\n\n"
        f"Use the buttons below to navigate:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

    # Add debug info about bot's username
    my_bot_info = await context.bot.get_me()
    await update.message.reply_text(
        f"🛠️ *Bot Info*\n\n"
        f"My username: @{my_bot_info.username}\n"
        f"To tag me correctly in groups, use: @{my_bot_info.username} Your signal text\n\n"
        f"Examples:\n"
        f"• @{my_bot_info.username} Long BTC at 88k, target 97k\n"
        f"• @{my_bot_info.username} Short BTC at 95k, tp 89k, high risk\n\n",
        parse_mode="Markdown"
    )

async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Test command to verify the bot is working in the current chat"""
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    user = update.effective_user
    
    # Get bot information
    bot_info = await context.bot.get_me()
    
    # Send a response with details about the current chat
    response = (
        f"✅ *Bot Test Successful!*\n\n"
        f"I can see and respond to messages in this {chat_type}.\n\n"
        f"*Chat Details:*\n"
        f"- Chat ID: `{chat_id}`\n"
        f"- Chat Type: {chat_type}\n"
        f"- Your Name: {user.full_name}\n"
        f"- Bot Username: @{bot_info.username}\n\n"
    )
    
    if chat_type in ["group", "supergroup"]:
        response += (
            f"*Group Instructions:*\n"
            f"1. To create a signal, tag me like this:\n"
            f"   `@{bot_info.username} $BTC SHORT HIGH Your signal text`\n\n"
            f"2. Make sure I have permission to read all messages\n"
            f"3. If tagging doesn't work, try adding me as an admin\n"
            f"4. Privacy mode must be disabled via BotFather\n\n"
            f"Use /debug for more detailed diagnostics"
        )
    
    await update.message.reply_text(response, parse_mode="Markdown")

async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Debug command to check bot status and data"""
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    
    # Get bot info
    my_bot_info = await context.bot.get_me()
    
    # Count data
    user_count = len(user_data.get("users", {}))
    signal_count = len(signals_data.get("signals", []))
    coin_count = len(coins_data.get("coins", {}))
    
    debug_text = (
        f"🛠️ *Debug Information* 🛠️\n\n"
        f"*Bot Username:* @{my_bot_info.username}\n"
        f"*Bot ID:* {my_bot_info.id}\n\n"
        f"*Current Chat:*\n"
        f"- ID: `{chat_id}`\n"
        f"- Type: {chat_type}\n\n"
        f"*Database Stats:*\n"
        f"- Users: {user_count}\n"
        f"- Signals: {signal_count}\n"
        f"- Coins tracked: {coin_count}\n\n"
    )
    
    if str(chat_id) in user_data.get("users", {}):
        user_info = user_data["users"][str(chat_id)]
        debug_text += (
            f"*Your Info:*\n"
            f"- Name: {user_info.get('name', 'Unknown')}\n"
            f"- Subscribed: {user_info.get('subscribed', False)}\n"
            f"- Favorite coins: {', '.join(user_info.get('favorite_coins', [])) or 'None'}\n\n"
        )
    
    debug_text += (
        f"*Common Issues:*\n"
        f"1. Bot privacy mode is enabled (disable via BotFather)\n"
        f"2. Bot doesn't have permission to read messages\n"
        f"3. Tag format is incorrect (use @{my_bot_info.username} $BTC...)\n"
        f"4. Bot needs to be re-added to the group\n\n"
        f"*Try these solutions:*\n"
        f"1. Chat with @BotFather, select your bot, then /mybots > Bot Settings > Group Privacy > Turn off\n"
        f"2. Make the bot an admin in the group\n"
        f"3. Remove and re-add the bot to the group\n"
        f"4. Try the /test command in your group"
    )
    
    await update.message.reply_text(debug_text, parse_mode="Markdown")

async def privacy_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send instructions for fixing privacy settings"""
    await update.message.reply_text(
        f"*How to Fix Bot Privacy Settings*\n\n"
        f"By default, Telegram bots can only see messages that directly mention them. "
        f"To make your bot see all messages in a group:\n\n"
        f"1. Open a chat with @BotFather on Telegram\n"
        f"2. Send /mybots command\n"
        f"3. Select your bot from the list\n"
        f"4. Click 'Bot Settings'\n"
        f"5. Select 'Group Privacy'\n"
        f"6. Click 'Turn off'\n\n"
        f"After that, you'll need to remove and re-add your bot to any groups for the change to take effect.\n\n"
        f"*Note:* After changing this setting, please send /test in your group to verify it's working.",
        parse_mode="Markdown"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    # Get bot info for correct tagging example
    my_bot_info = await context.bot.get_me()
    
    help_text = (
        f"⚡ *Pump My Bags Bot Help* ⚡\n\n"
        f"*Basic Commands:*\n"
        f"• /start - Start the bot\n"
        f"• /help - Show this help message\n"
        f"• /subscribe - Subscribe to signals\n"
        f"• /unsubscribe - Unsubscribe from signals\n\n"
        f"*Advanced Features:*\n"
        f"• /signals - View recent signals\n"
        f"• /coins - Track your favorite coins\n"
        f"• /price [symbol] - Check current price\n"
        f"• /performance - View signal performance\n"
        f"• /debug - Show debug information\n"
        f"• /test - Test if bot is working properly\n"
        f"• /privacy - How to fix privacy settings\n\n"
        f"*How to use in groups:*\n"
        f"1. Add me to your group\n"
        f"2. Just tag me and describe your signal in plain language:\n\n"
        f"   Examples:\n"
        f"   @{my_bot_info.username} Long BTC at 88k and tp at 146k, is low risk\n"
        f"   @{my_bot_info.username} Short BTC at 91k, target 85k, high risk\n\n"
        f"3. I'll automatically detect the coin, position, entry price, target price, and risk level\n\n"
        f"*Troubleshooting:*\n"
        f"If I'm not responding in groups, use /privacy for instructions on fixing bot privacy settings."
    )
    
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Subscribe user to trading signals."""
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    if str(chat_id) not in user_data["users"]:
        user_data["users"][str(chat_id)] = {
            "name": user.full_name,
            "username": user.username,
            "chat_id": chat_id,
            "subscribed": True,
            "joined_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "favorite_coins": []
        }
    else:
        user_data["users"][str(chat_id)]["subscribed"] = True
    
    await save_user_data()
    await update.message.reply_text("✅ You've successfully subscribed to crypto signals! 📈")

async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unsubscribe user from trading signals."""
    chat_id = update.effective_chat.id
    
    if str(chat_id) in user_data["users"]:
        user_data["users"][str(chat_id)]["subscribed"] = False
        await save_user_data()
        await update.message.reply_text("You've unsubscribed from signals. You can resubscribe anytime with /subscribe.")
    else:
        await update.message.reply_text("You weren't subscribed. Use /subscribe to receive crypto signals.")

async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check the current price of a cryptocurrency"""
    if not context.args:
        await update.message.reply_text(
            "Please provide a cryptocurrency symbol.\n"
            "Example: /price BTC"
        )
        return
    
    symbol = context.args[0].upper().replace("$", "")
    price = await get_crypto_price(symbol)
    
    if price:
        await update.message.reply_text(
            f"💰 *{symbol} Price*\n\n"
            f"Current price: ${price:,.2f} USD\n\n"
            f"_Data from CoinGecko_",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"Sorry, couldn't find price information for {symbol}.\n"
            f"Please check the symbol and try again."
        )

async def coins_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Track favorite coins"""
    chat_id = str(update.effective_chat.id)
    
    if chat_id not in user_data["users"]:
        await update.message.reply_text("Please use /start first to set up your account.")
        return
    
    # If no arguments, show current favorite coins
    if not context.args:
        favorite_coins = user_data["users"][chat_id].get("favorite_coins", [])
        
        if not favorite_coins:
            keyboard = [
                [InlineKeyboardButton("➕ Add Coins", callback_data="add_coins")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "You don't have any favorite coins yet.\n"
                "Add coins to track them:",
                reply_markup=reply_markup
            )
        else:
            # Get prices for all favorite coins
            coin_prices = []
            for coin in favorite_coins:
                price = await get_crypto_price(coin)
                coin_prices.append((coin, price))
            
            # Create message with prices
            message = "💎 *Your Favorite Coins* 💎\n\n"
            for coin, price in coin_prices:
                if price:
                    message += f"*{coin}*: ${price:,.2f} USD\n"
                else:
                    message += f"*{coin}*: Price unavailable\n"
            
            # Add buttons to manage coins
            keyboard = [
                [InlineKeyboardButton("➕ Add Coin", callback_data="add_coins"),
                 InlineKeyboardButton("➖ Remove Coin", callback_data="remove_coins")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                message,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    else:
        # Add a coin to favorites
        coin = context.args[0].upper().replace("$", "")
        favorite_coins = user_data["users"][chat_id].get("favorite_coins", [])
        
        if coin in favorite_coins:
            await update.message.reply_text(f"{coin} is already in your favorites.")
        else:
            # Check if coin exists by getting its price
            price = await get_crypto_price(coin)
            if price:
                favorite_coins.append(coin)
                user_data["users"][chat_id]["favorite_coins"] = favorite_coins
                await save_user_data()
                await update.message.reply_text(f"Added {coin} to your favorite coins!")
            else:
                await update.message.reply_text(
                    f"Couldn't find {coin}. Please check the symbol and try again."
                )

async def performance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show signal performance stats and overall metrics"""
    # First update all signal performances
    await update_all_signals_performance()
    
    # Create keyboard for performance views
    keyboard = [
        [InlineKeyboardButton("📈 Signals", callback_data="perf_signals"),
         InlineKeyboardButton("👨‍💼 Traders", callback_data="perf_traders")],
        [InlineKeyboardButton("🪙 By Coin", callback_data="perf_coins"),
         InlineKeyboardButton("⏱️ By Timeframe", callback_data="perf_timeframe")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Calculate overall stats
    total_signals = len(signals_data["signals"])
    pending_count = sum(1 for s in signals_data["signals"] if s.get("status") == PENDING)
    success_count = sum(1 for s in signals_data["signals"] if s.get("status") == HIT_TARGET)
    failed_count = sum(1 for s in signals_data["signals"] if s.get("status") == HIT_STOPLOSS)
    expired_count = sum(1 for s in signals_data["signals"] if s.get("status") == EXPIRED)
    
    # Calculate success rate
    completed_count = success_count + failed_count + expired_count
    success_rate = (success_count / completed_count * 100) if completed_count > 0 else 0
    
    # Calculate average performance
    performances = [s.get("performance", 0) for s in signals_data["signals"] 
                    if "performance" in s and s.get("status") != PENDING]
    avg_performance = sum(performances) / len(performances) if performances else 0
    
    # Build performance summary
    performance_text = (
        f"📊 *Signal Performance Summary* 📊\n\n"
        f"*Total Signals:* {total_signals}\n"
        f"*Pending:* {pending_count}\n"
        f"*Successful:* {success_count}\n"
        f"*Failed:* {failed_count}\n"
        f"*Expired:* {expired_count}\n\n"
        f"*Success Rate:* {success_rate:.1f}%\n"
        f"*Average Return:* {avg_performance:.2f}%\n\n"
        f"*Select a detailed view:*"
    )
    
    await update.message.reply_text(
        performance_text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def handle_performance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback for different performance views"""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    
    if callback_data == "perf_traders":
        # Show trader performance
        # Get stats by trader
        trader_stats = {}
        
        # Only consider signals with final status
        completed_signals = [s for s in signals_data["signals"] 
                            if s.get("status") in [HIT_TARGET, HIT_STOPLOSS, EXPIRED]]
        
        if not completed_signals:
            await query.edit_message_text("No completed signals yet to show trader performance stats.")
            return
        
        for signal in completed_signals:
            trader = signal.get("sender", "Unknown")
            
            if trader not in trader_stats:
                trader_stats[trader] = {
                    "total_signals": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "expired_count": 0,
                    "total_profit": 0,
                    "avg_profit": 0
                }
            
            # Update counts
            trader_stats[trader]["total_signals"] += 1
            
            if signal.get("status") == HIT_TARGET:
                trader_stats[trader]["success_count"] += 1
            elif signal.get("status") == HIT_STOPLOSS:
                trader_stats[trader]["failure_count"] += 1
            elif signal.get("status") == EXPIRED:
                trader_stats[trader]["expired_count"] += 1
            
            # Add profit/loss percentage
            if "performance" in signal:
                trader_stats[trader]["total_profit"] += signal["performance"]
        
        # Calculate averages and success rates
        for trader, stats in trader_stats.items():
            if stats["total_signals"] > 0:
                stats["avg_profit"] = stats["total_profit"] / stats["total_signals"]
                stats["success_rate"] = (stats["success_count"] / stats["total_signals"]) * 100
        
        # Sort traders by success rate
        sorted_traders = sorted(
            trader_stats.items(), 
            key=lambda x: (x[1]["success_rate"], x[1]["avg_profit"]), 
            reverse=True
        )
        
        # Create trader performance report
        report = "👨‍💼 *Trader Performance* 👨‍💼\n\n"
        
        for i, (trader, stats) in enumerate(sorted_traders[:5], 1):  # Show top 5
            report += (
                f"*{i}. {trader}*\n"
                f"Success Rate: {stats['success_rate']:.1f}%\n"
                f"Signals: {stats['total_signals']} "
                f"(✅{stats['success_count']} "
                f"❌{stats['failure_count']} "
                f"⏳{stats['expired_count']})\n"
                f"Avg Profit: {stats['avg_profit']:.2f}%\n\n"
            )
        
        # Add back button
        keyboard = [[InlineKeyboardButton("◀️ Back", callback_data="perf_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            report,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    elif callback_data == "perf_coins":
        # Show performance by coin
        coin_stats = {}
        
        # Collect data by coin
        for signal in signals_data["signals"]:
            coin = signal.get("coin", "Unknown")
            
            if coin not in coin_stats:
                coin_stats[coin] = {
                    "total_signals": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "expired_count": 0,
                    "pending_count": 0,
                    "total_profit": 0
                }
            
            coin_stats[coin]["total_signals"] += 1
            
            if signal.get("status") == HIT_TARGET:
                coin_stats[coin]["success_count"] += 1
                if "performance" in signal:
                    coin_stats[coin]["total_profit"] += signal["performance"]
            elif signal.get("status") == HIT_STOPLOSS:
                coin_stats[coin]["failure_count"] += 1
                if "performance" in signal:
                    coin_stats[coin]["total_profit"] += signal["performance"]
            elif signal.get("status") == EXPIRED:
                coin_stats[coin]["expired_count"] += 1
                if "performance" in signal:
                    coin_stats[coin]["total_profit"] += signal["performance"]
            else:  # PENDING
                coin_stats[coin]["pending_count"] += 1
        
        # Calculate average profit and success rate for each coin
        for coin, stats in coin_stats.items():
            completed = stats["success_count"] + stats["failure_count"] + stats["expired_count"]
            stats["completed_signals"] = completed
            
            if completed > 0:
                stats["success_rate"] = (stats["success_count"] / completed) * 100
                stats["avg_profit"] = stats["total_profit"] / completed
            else:
                stats["success_rate"] = 0
                stats["avg_profit"] = 0
        
        # Sort coins by number of signals
        sorted_coins = sorted(
            coin_stats.items(),
            key=lambda x: x[1]["total_signals"],
            reverse=True
        )
        
        # Create coin performance report
        report = "🪙 *Performance by Coin* 🪙\n\n"
        
        for coin, stats in sorted_coins[:10]:  # Show top 10 coins
            if stats["completed_signals"] > 0:
                report += (
                    f"*{coin}*\n"
                    f"Signals: {stats['total_signals']} "
                    f"(✅{stats['success_count']} "
                    f"❌{stats['failure_count']} "
                    f"⏳{stats['expired_count']} "
                    f"⏱️{stats['pending_count']})\n"
                    f"Success Rate: {stats['success_rate']:.1f}%\n"
                    f"Avg Profit: {stats['avg_profit']:.2f}%\n\n"
                )
        
        # Add back button
        keyboard = [[InlineKeyboardButton("◀️ Back", callback_data="perf_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            report,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    elif callback_data == "perf_timeframe":
        # Show performance by timeframe
        timeframe_stats = {tf: {"total": 0, "success": 0, "failure": 0, "expired": 0, "profit": 0} 
                         for tf in TIMEFRAMES}
        
        # Collect data by timeframe
        for signal in signals_data["signals"]:
            timeframe = signal.get("timeframe", "MID")  # Default to MID if not specified
            
            if timeframe not in timeframe_stats:
                timeframe_stats[timeframe] = {"total": 0, "success": 0, "failure": 0, "expired": 0, "profit": 0}
            
            timeframe_stats[timeframe]["total"] += 1
            
            if signal.get("status") == HIT_TARGET:
                timeframe_stats[timeframe]["success"] += 1
                if "performance" in signal:
                    timeframe_stats[timeframe]["profit"] += signal["performance"]
            elif signal.get("status") == HIT_STOPLOSS:
                timeframe_stats[timeframe]["failure"] += 1
                if "performance" in signal:
                    timeframe_stats[timeframe]["profit"] += signal["performance"]
            elif signal.get("status") == EXPIRED:
                timeframe_stats[timeframe]["expired"] += 1
                if "performance" in signal:
                    timeframe_stats[timeframe]["profit"] += signal["performance"]
        
        # Calculate success rates and average profits
        for tf, stats in timeframe_stats.items():
            completed = stats["success"] + stats["failure"] + stats["expired"]
            if completed > 0:
                stats["success_rate"] = (stats["success"] / completed) * 100
                stats["avg_profit"] = stats["profit"] / completed
            else:
                stats["success_rate"] = 0
                stats["avg_profit"] = 0
        
        # Create timeframe performance report
        report = "⏱️ *Performance by Timeframe* ⏱️\n\n"
        
        for tf, stats in timeframe_stats.items():
            if stats["total"] > 0:
                report += (
                    f"*{tf} Timeframe*\n"
                    f"Total Signals: {stats['total']}\n"
                    f"Success Rate: {stats['success_rate']:.1f}%\n"
                    f"Avg Profit: {stats['avg_profit']:.2f}%\n"
                    f"✅ {stats['success']} | ❌ {stats['failure']} | ⏳ {stats['expired']}\n\n"
                )
        
        # Add back button
        keyboard = [[InlineKeyboardButton("◀️ Back", callback_data="perf_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            report,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
    elif callback_data == "perf_signals":
        # Show recent signal performances
        # First update all signal statuses
        await update_all_signals_performance()
        
        # Get recent signals that have completed
        completed_signals = [s for s in signals_data["signals"] 
                            if s.get("status") != PENDING]
        
        # Sort by timestamp (most recent first)
        sorted_signals = sorted(
            completed_signals,
            key=lambda x: datetime.strptime(x.get("timestamp", "2000-01-01 00:00:00"), "%Y-%m-%d %H:%M:%S"),
            reverse=True
        )
        
        if not sorted_signals:
            await query.edit_message_text(
                "No completed signals yet to show performance.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="perf_back")]])
            )
            return
        
        # Create signal performance report
        report = "📈 *Recent Signal Results* 📈\n\n"
        
        for signal in sorted_signals[:5]:  # Show 5 most recent completed signals
            status_emoji = "✅" if signal.get("status") == HIT_TARGET else "❌" if signal.get("status") == HIT_STOPLOSS else "⏳"
            position = signal.get("position", "Unknown")
            coin = signal.get("coin", "Unknown")
            perf = signal.get("performance", 0)
            perf_str = f"+{perf:.2f}%" if perf >= 0 else f"{perf:.2f}%"
            
            report += (
                f"*{status_emoji} {position} {coin}*\n"
                f"Entry: {signal.get('limit_order', 'Unknown')}\n"
                f"Target: {signal.get('take_profit', 'Unknown')}\n"
                f"Result: {perf_str}\n"
                f"From: {signal.get('sender', 'Unknown')}\n"
                f"Date: {signal.get('timestamp', 'Unknown')}\n\n"
            )
        
        # Add back button
        keyboard = [[InlineKeyboardButton("◀️ Back", callback_data="perf_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            report,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    elif callback_data == "perf_back":
        # Go back to main performance menu
        keyboard = [
            [InlineKeyboardButton("📈 Signals", callback_data="perf_signals"),
             InlineKeyboardButton("👨‍💼 Traders", callback_data="perf_traders")],
            [InlineKeyboardButton("🪙 By Coin", callback_data="perf_coins"),
             InlineKeyboardButton("⏱️ By Timeframe", callback_data="perf_timeframe")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Calculate overall stats
        total_signals = len(signals_data["signals"])
        pending_count = sum(1 for s in signals_data["signals"] if s.get("status") == PENDING)
        success_count = sum(1 for s in signals_data["signals"] if s.get("status") == HIT_TARGET)
        failed_count = sum(1 for s in signals_data["signals"] if s.get("status") == HIT_STOPLOSS)
        expired_count = sum(1 for s in signals_data["signals"] if s.get("status") == EXPIRED)
        
        # Calculate success rate
        completed_count = success_count + failed_count + expired_count
        success_rate = (success_count / completed_count * 100) if completed_count > 0 else 0
        
        # Calculate average performance
        performances = [s.get("performance", 0) for s in signals_data["signals"] 
                        if "performance" in s and s.get("status") != PENDING]
        avg_performance = sum(performances) / len(performances) if performances else 0
        
        # Build performance summary
        performance_text = (
            f"📊 *Signal Performance Summary* 📊\n\n"
            f"*Total Signals:* {total_signals}\n"
            f"*Pending:* {pending_count}\n"
            f"*Successful:* {success_count}\n"
            f"*Failed:* {failed_count}\n"
            f"*Expired:* {expired_count}\n\n"
            f"*Success Rate:* {success_rate:.1f}%\n"
            f"*Average Return:* {avg_performance:.2f}%\n\n"
            f"*Select a detailed view:*"
        )
        
        await query.edit_message_text(
            performance_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

async def signals_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show recent signals to the user."""
    if not signals_data["signals"]:
        await update.message.reply_text("No signals have been posted yet.")
        return
    
    # Get the 5 most recent signals
    recent_signals = sorted(signals_data["signals"], key=lambda x: x["timestamp"], reverse=True)[:5]
    
    # Send a header message
    await update.message.reply_text("📊 *Last 5 Signals*\n\nShowing the most recent signals:", parse_mode="Markdown")
    
    for signal in recent_signals:
        # Create vote keyboard
        keyboard = [
            [
                InlineKeyboardButton(f"👍 {signal['upvotes']}", callback_data=f"vote_{signal['id']}_up"),
                InlineKeyboardButton(f"👎 {signal['downvotes']}", callback_data=f"vote_{signal['id']}_down")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Get current price if available
        current_price = None
        if "coin" in signal:
            current_price = await get_crypto_price(signal["coin"])
        
        # Extract info from signal
        coin = signal.get("coin", "Unknown")
        timeframe = signal.get("timeframe", "")
        risk = signal.get("risk", "")
        limit_order = signal.get("limit_order", "")
        take_profit = signal.get("take_profit", "")
        position = signal.get("position", "")
        
        # Format the signal with the new format
        signal_text = (
            f"🚀 *PMB Trading SIGNAL* 🚀\n\n"
            f"*Coin:* {coin}\n"
        )
        
        if limit_order:
            signal_text += f"*Limit Order:* Buy at {limit_order}\n"
        
        if take_profit:
            signal_text += f"*TP:* {take_profit}\n"
        
        if position:
            signal_text += f"*Position:* {position}\n"
        
        if timeframe:
            signal_text += f"*Timeframe:* {timeframe}\n"
        
        if risk:
            signal_text += f"*Risk Level:* {risk}\n"
        
        if current_price:
            signal_text += f"*Current Price:* ${current_price:,.2f} USD\n"
        
        signal_text += (
            f"*From:* {signal['sender']}\n"
            f"*Group:* {signal['group']}\n"
            f"*Time:* {signal['timestamp']}\n\n"
            f"*Signal:*\n{signal['text']}\n\n"
            f"⚠️ *DISCLAIMER:* Trading involves risk. DYOR."
        )
        
        await update.message.reply_text(
            signal_text, 
            reply_markup=reply_markup, 
            parse_mode="Markdown"
        )

async def extract_signal_data(text):
    """Extract coin symbol, timeframe, risk level and trading details from natural language text"""
    # Extract coin symbols - try various patterns
    coin = None
    
    # First try standard $BTC format
    dollar_match = re.search(r'\$([A-Za-z0-9]+)', text)
    if dollar_match:
        coin = dollar_match.group(1).upper()
    else:
        # Try without $ prefix - common coins
        common_coins = ['BTC', 'ETH', 'XRP', 'LTC', 'ADA', 'DOT', 'DOGE', 'SOL', 'SHIB', 'AVAX', 'MATIC', 'LINK', 
                      'BNB', 'UNI', 'XLM', 'ATOM', 'ALGO', 'FIL', 'AAVE', 'EOS', 'XTZ', 'NEO', 'COMP', 'ZEC']
        
        # Convert text to uppercase for case-insensitive matching
        upper_text = text.upper()
        
        # Check for each coin symbol in the text
        for coin_symbol in common_coins:
            # Use word boundary to ensure we match whole words
            pattern = r'\b' + coin_symbol + r'\b'
            if re.search(pattern, upper_text):
                coin = coin_symbol
                logger.debug(f"Found coin: {coin} using pattern matching")
                break
    
    # Detect position (Long/Short) - check for the words at the start of message
    position = None
    if re.search(r'\b[Ll]ong\b', text):
        position = "Long"
    elif re.search(r'\b[Ss]hort\b', text):
        position = "Short"
    elif re.search(r'\b[Bb]uy\b', text):
        position = "Long"
    elif re.search(r'\b[Ss]ell\b', text):
        position = "Short"
    
    # Extract entry price (more flexible patterns)
    entry_price = None
    # Try patterns like "at 88k", "entry 88k", "price 88k", "88k"
    entry_patterns = [
        r'(?:at|entry|price|@)\s*(\d+(?:\.\d+)?[kK]?)',  # at 88k, entry 88k, price 88k
        r'(?:buy|long|short|sell).*?(\d+(?:\.\d+)?[kK]?)' # long BTC at 88k, short at 91k
    ]
    
    for pattern in entry_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            entry_price = match.group(1)
            break
    
    # Extract take profit/target (more patterns)
    take_profit = None
    tp_patterns = [
        r'(?:tp|target|take profit|price target|expecting).*?(\d+(?:\.\d+)?[kK]?)',  # tp at 146k, target 146k
        r'(?:to reach|reach).*?(\d+(?:\.\d+)?[kK]?)'  # to reach 85k
    ]
    
    for pattern in tp_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            take_profit = match.group(1)
            break
    
    # Extract timeframe from words or context
    timeframe = None
    if re.search(r'\b(short(-|\s)?term|hourly|hours|short(\s)?frame|day|daily|intraday)\b', text, re.IGNORECASE):
        timeframe = "SHORT"
    elif re.search(r'\b(mid(-|\s)?term|mid|week|weekly|days|medium)\b', text, re.IGNORECASE):
        timeframe = "MID"
    elif re.search(r'\b(long(-|\s)?term|long(\s)?frame|month|monthly|year|yearly)\b', text, re.IGNORECASE):
        timeframe = "LONG"
    
    # Extract risk level from various wordings
    risk_level = None
    if re.search(r'\b(low[- ]?risk|safe|conservative)\b', text, re.IGNORECASE):
        risk_level = "LOW"
    elif re.search(r'\b(medium[- ]?risk|moderate|mid[- ]?risk)\b', text, re.IGNORECASE):
        risk_level = "MEDIUM"
    elif re.search(r'\b(high[- ]?risk|risky|aggressive)\b', text, re.IGNORECASE):
        risk_level = "HIGH"
    
    # Fallback: If a timeframe/risk level is not specified in context words,
    # check for the exact words SHORT, MID, LONG, LOW, MEDIUM, HIGH in the message
    if not timeframe:
        for tf in TIMEFRAMES:
            if tf in text.upper():
                timeframe = tf
                break
    
    if not risk_level:
        for risk in RISK_LEVELS:
            if risk in text.upper():
                risk_level = risk
                break
    
    logger.debug(f"Extracted signal data: coin={coin}, position={position}, entry={entry_price}, tp={take_profit}, timeframe={timeframe}, risk={risk_level}")
    return coin, timeframe, risk_level, entry_price, take_profit, position

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle messages that tag the bot in groups."""
    # Check if message exists and has text
    if not update.message or not update.message.text:
        logger.debug("Message has no text or is None")
        return
        
    # Log all messages in groups for debugging
    message = update.message
    chat_type = update.effective_chat.type
    
    if chat_type in ["group", "supergroup"]:
        logger.debug(f"Group message received: {message.text}")
        
        # Get bot's username
        bot_username = context.bot.username
        
        # Check for mentions
        mentions = []
        if message.entities:
            for entity in message.entities:
                if entity.type == "mention":
                    mention = message.text[entity.offset:entity.offset + entity.length]
                    mentions.append(mention)
                    logger.debug(f"Found mention: {mention}")
        
        logger.debug(f"All mentions: {mentions}")
        logger.debug(f"Bot username: @{bot_username}")
        
        # Check if bot is mentioned
        if f"@{bot_username}" in mentions:
            logger.info(f"✅ Bot mentioned correctly in group {update.effective_chat.title}")
            signal_text = message.text
            sender = message.from_user.full_name
            group_name = update.effective_chat.title
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Extract coin, timeframe, risk level, and other signal details
            coin, timeframe, risk_level, limit_order, take_profit, position = await extract_signal_data(signal_text)
            logger.info(f"Extracted data: coin={coin}, timeframe={timeframe}, risk={risk_level}, limit={limit_order}, tp={take_profit}, position={position}")
            
            # Respond in the group to confirm detection
            if coin:
                confirmation_msg = f"✅ Signal detected!\n• Coin: {coin}\n"
                
                if position:
                    confirmation_msg += f"• Position: {position}\n"
                
                if limit_order:
                    confirmation_msg += f"• Entry: {limit_order}\n"
                
                if take_profit:
                    confirmation_msg += f"• Target: {take_profit}\n"
                
                if timeframe:
                    confirmation_msg += f"• Timeframe: {timeframe}\n"
                
                if risk_level:
                    confirmation_msg += f"• Risk: {risk_level}\n"
                
                confirmation_msg += f"\nForwarding to {len(user_data['users'])} subscribers..."
                await message.reply_text(confirmation_msg)
            else:
                await message.reply_text(
                    f"⚠️ I detected your tag, but couldn't find a coin symbol.\n"
                    f"Please include a coin name like BTC in your signal."
                )
                return
            
            # If coin was found, update coin tracking data
            if coin:
                if coin not in coins_data["coins"]:
                    coins_data["coins"][coin] = {
                        "first_seen": timestamp,
                        "signal_count": 1,
                        "signals": []
                    }
                else:
                    coins_data["coins"][coin]["signal_count"] += 1
                
                # Add this signal ID to the coin's signal list
                signal_id = len(signals_data["signals"]) + 1
                coins_data["coins"][coin]["signals"].append(signal_id)
                await save_coins_data()
            
            # Generate a unique signal ID
            signal_id = len(signals_data["signals"]) + 1
            
            # Create a new signal record
            new_signal = {
                "id": signal_id,
                "text": signal_text,
                "sender": sender,
                "group": group_name,
                "timestamp": timestamp,
                "upvotes": 0,
                "downvotes": 0,
                "voters": {}
            }
            
            # Add all extracted data to the signal record
            if coin:
                new_signal["coin"] = coin
            if timeframe:
                new_signal["timeframe"] = timeframe
            if risk_level:
                new_signal["risk"] = risk_level
            if limit_order:
                new_signal["limit_order"] = limit_order
            if take_profit:
                new_signal["take_profit"] = take_profit
            if position:
                new_signal["position"] = position
            
            # Add to signals database
            signals_data["signals"].append(new_signal)
            await save_signals_data()
            
            # Check current price if coin is identified
            current_price = None
            if coin:
                current_price = await get_crypto_price(coin)
            
            # Create vote buttons
            keyboard = [
                [
                    InlineKeyboardButton("👍 0", callback_data=f"vote_{signal_id}_up"),
                    InlineKeyboardButton("👎 0", callback_data=f"vote_{signal_id}_down")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Format the signal message with the new format
            formatted_signal = (
                f"🚀 *PMB Trading SIGNAL* 🚀\n\n"
            )
            
            if coin:
                formatted_signal += f"*Coin:* {coin}\n"
            
            # Entry price (Buy/Sell price)
            if limit_order:
                if position and position.lower() == "short":
                    formatted_signal += f"*Limit Order:* Sell at {limit_order}\n"
                else:
                    formatted_signal += f"*Limit Order:* Buy at {limit_order}\n"
            
            if take_profit:
                formatted_signal += f"*TP:* {take_profit}\n"
            
            if position:
                formatted_signal += f"*Position:* {position}\n"
            
            if timeframe:
                formatted_signal += f"*Timeframe:* {timeframe}\n"
            
            if risk_level:
                formatted_signal += f"*Risk Level:* {risk_level}\n"
            
            if current_price:
                formatted_signal += f"*Current Price:* ${current_price:,.2f} USD\n"
            
            formatted_signal += (
                f"*From:* {sender}\n"
                f"*Group:* {group_name}\n"
                f"*Time:* {timestamp}\n\n"
                f"*Signal:*\n{signal_text}\n\n"
                f"⚠️ *DISCLAIMER:* Trading involves risk. Do your own research."
            )
            
            # Forward to all subscribed users
            sent_count = 0
            for user_id, user_info in user_data["users"].items():
                # Check if user is subscribed
                is_subscribed = user_info.get("subscribed", False)
                
                # Check if signal mentions one of user's favorite coins
                favorite_coins = user_info.get("favorite_coins", [])
                is_favorite = coin in favorite_coins if coin else False
                
                # Check user settings
                settings = user_data.get("settings", {}).get(user_id, {
                    "notify_all_signals": True,
                    "notify_favorites_only": False,
                    "risk_filter": "ALL",
                    "timeframe_filter": "ALL"
                })
                
                # Apply user settings filters
                should_notify = False
                
                # Check notification preferences
                if settings["notify_all_signals"] and not settings["notify_favorites_only"]:
                    should_notify = True
                elif settings["notify_favorites_only"] and is_favorite:
                    should_notify = True
                else:
                    continue  # Skip this user based on notification settings
                
                # Apply risk level filter if set
                if settings["risk_filter"] != "ALL" and risk_level != settings["risk_filter"]:
                    continue  # Skip if risk level doesn't match filter
                
                # Apply timeframe filter if set
                if settings["timeframe_filter"] != "ALL" and timeframe != settings["timeframe_filter"]:
                    continue  # Skip if timeframe doesn't match filter
                
                if is_subscribed and should_notify:
                    try:
                        await context.bot.send_message(
                            chat_id=user_info["chat_id"],
                            text=formatted_signal,
                            parse_mode="Markdown",
                            reply_markup=reply_markup
                        )
                        sent_count += 1
                        
                        # Send additional notification for favorite coins
                        if is_favorite:
                            await context.bot.send_message(
                                chat_id=user_info["chat_id"],
                                text=f"⭐ This signal contains one of your favorite coins: {coin} ⭐"
                            )
                    except Exception as e:
                        logger.error(f"Failed to send message to user {user_id}: {e}")
            
            logger.info(f"Signal forwarded to {sent_count} users")
            
            # Reply in the group to confirm
            confirmation = f"✅ Signal forwarded to {sent_count} subscribers!"
            if coin:
                confirmation += f" Coin: {coin}"
                if current_price:
                    confirmation += f" (${current_price:,.2f})"
            await message.reply_text(confirmation)
        else:
            logger.debug(f"Bot username mismatch: @{bot_username} not found in {mentions}")
    else:
        logger.debug(f"Message not in a group: {chat_type}")

async def trader_performance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show performance statistics for traders"""
    # Run update before showing stats
    await update_all_signals_performance()
    
    # Get stats by trader
    trader_stats = {}
    
    # Only consider signals with final status
    completed_signals = [s for s in signals_data["signals"] 
                         if s.get("status") in [HIT_TARGET, HIT_STOPLOSS, EXPIRED]]
    
    if not completed_signals:
        await update.message.reply_text("No completed signals yet to show performance stats.")
        return
    
    for signal in completed_signals:
        trader = signal.get("sender", "Unknown")
        
        if trader not in trader_stats:
            trader_stats[trader] = {
                "total_signals": 0,
                "success_count": 0,
                "failure_count": 0,
                "expired_count": 0,
                "total_profit": 0,
                "avg_profit": 0
            }
        
        # Update counts
        trader_stats[trader]["total_signals"] += 1
        
        if signal.get("status") == HIT_TARGET:
            trader_stats[trader]["success_count"] += 1
        elif signal.get("status") == HIT_STOPLOSS:
            trader_stats[trader]["failure_count"] += 1
        elif signal.get("status") == EXPIRED:
            trader_stats[trader]["expired_count"] += 1
        
        # Add profit/loss percentage
        if "performance" in signal:
            trader_stats[trader]["total_profit"] += signal["performance"]
    
    # Calculate averages and success rates
    for trader, stats in trader_stats.items():
        if stats["total_signals"] > 0:
            stats["avg_profit"] = stats["total_profit"] / stats["total_signals"]
            stats["success_rate"] = (stats["success_count"] / stats["total_signals"]) * 100
    
    # Sort traders by success rate
    sorted_traders = sorted(
        trader_stats.items(), 
        key=lambda x: (x[1]["success_rate"], x[1]["avg_profit"]), 
        reverse=True
    )
    
    # Create performance report
    report = "📊 *Trader Performance Stats* 📊\n\n"
    
    for i, (trader, stats) in enumerate(sorted_traders[:10], 1):  # Show top 10
        report += (
            f"*{i}. {trader}*\n"
            f"Success Rate: {stats['success_rate']:.1f}%\n"
            f"Signals: {stats['total_signals']} "
            f"(✅{stats['success_count']} "
            f"❌{stats['failure_count']} "
            f"⏳{stats['expired_count']})\n"
            f"Avg Profit: {stats['avg_profit']:.2f}%\n\n"
        )
    
    await update.message.reply_text(report, parse_mode="Markdown")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks for voting and other interactive features."""
    query = update.callback_query
    callback_data = query.data
    user_id = str(update.effective_user.id)
    
    # Acknowledge the callback
    await query.answer()
    
    # Settings-related callbacks
    if callback_data.startswith("settings_"):
        # Initialize settings if needed
        if "settings" not in user_data:
            user_data["settings"] = {}
        if user_id not in user_data["settings"]:
            user_data["settings"][user_id] = {
                "notify_all_signals": True,
                "notify_favorites_only": False,
                "risk_filter": "ALL",
                "timeframe_filter": "ALL"
            }
        
        settings = user_data["settings"][user_id]
        
        if callback_data == "settings_toggle_all":
            # Toggle all signals notification
            settings["notify_all_signals"] = not settings["notify_all_signals"]
            # If enabling all signals, disable favorites only
            if settings["notify_all_signals"]:
                settings["notify_favorites_only"] = False
                
        elif callback_data == "settings_toggle_favorites":
            # Toggle favorites only notification
            settings["notify_favorites_only"] = not settings["notify_favorites_only"]
            # If enabling favorites only, disable all signals
            if settings["notify_favorites_only"]:
                settings["notify_all_signals"] = False
                
        elif callback_data == "settings_risk":
            # Cycle through risk filters: ALL -> LOW -> MEDIUM -> HIGH -> ALL
            current = settings["risk_filter"]
            if current == "ALL":
                settings["risk_filter"] = "LOW"
            elif current == "LOW":
                settings["risk_filter"] = "MEDIUM"
            elif current == "MEDIUM":
                settings["risk_filter"] = "HIGH"
            else:
                settings["risk_filter"] = "ALL"
                
        elif callback_data == "settings_timeframe":
            # Cycle through timeframe filters: ALL -> SHORT -> MID -> LONG -> ALL
            current = settings["timeframe_filter"]
            if current == "ALL":
                settings["timeframe_filter"] = "SHORT"
            elif current == "SHORT":
                settings["timeframe_filter"] = "MID"
            elif current == "MID":
                settings["timeframe_filter"] = "LONG"
            else:
                settings["timeframe_filter"] = "ALL"
                
        elif callback_data == "settings_save":
            await save_user_data()
            await query.edit_message_text(
                "✅ Settings saved successfully!\n\nUse /settings to view or change your settings again.",
                parse_mode="Markdown"
            )
            return
        
        # Update message with new settings
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{'✅' if settings['notify_all_signals'] else '❌'} All Signals", 
                    callback_data="settings_toggle_all"
                ),
                InlineKeyboardButton(
                    f"{'✅' if settings['notify_favorites_only'] else '❌'} Favorites Only",
                    callback_data="settings_toggle_favorites"
                )
            ],
            [
                InlineKeyboardButton(
                    f"Risk Filter: {settings['risk_filter']}",
                    callback_data="settings_risk"
                )
            ],
            [
                InlineKeyboardButton(
                    f"Timeframe Filter: {settings['timeframe_filter']}",
                    callback_data="settings_timeframe"
                )
            ],
            [
                InlineKeyboardButton("Save Settings", callback_data="settings_save")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            f"⚙️ *User Settings* ⚙️\n\n"
            f"Configure your notification preferences:\n\n"
            f"*Receive Notifications:*\n"
            f"{'✅' if settings['notify_all_signals'] else '❌'} All signals\n"
            f"{'✅' if settings['notify_favorites_only'] else '❌'} Favorites only\n\n"
            f"*Risk Level Filter:* {settings['risk_filter']}\n"
            f"*Timeframe Filter:* {settings['timeframe_filter']}\n\n"
            f"Use the buttons below to change your settings."
        )
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
        return
    
    # Handle other button actions
    chat_id = str(query.message.chat_id)
    
    if callback_data == "add_coins":
        await query.edit_message_text(
            "To add a coin to your favorites, use:\n"
            "/coins BTC\n\n"
            "Replace BTC with any cryptocurrency symbol."
        )
    
    elif callback_data == "remove_coins":
        if chat_id in user_data["users"] and "favorite_coins" in user_data["users"][chat_id]:
            coins = user_data["users"][chat_id]["favorite_coins"]
            if not coins:
                await query.edit_message_text("You don't have any favorite coins to remove.")
                return
            
            # Create keyboard with all coins to remove
            keyboard = []
            row = []
            for i, coin in enumerate(coins):
                row.append(InlineKeyboardButton(coin, callback_data=f"remove_{coin}"))
                if (i + 1) % 3 == 0 or i == len(coins) - 1:
                    keyboard.append(row)
                    row = []
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "Select a coin to remove from favorites:",
                reply_markup=reply_markup
            )
        else:
            await query.edit_message_text("You don't have any favorite coins yet.")
    
    elif callback_data.startswith("remove_"):
        coin = callback_data.split("_")[1]
        if chat_id in user_data["users"] and "favorite_coins" in user_data["users"][chat_id]:
            if coin in user_data["users"][chat_id]["favorite_coins"]:
                user_data["users"][chat_id]["favorite_coins"].remove(coin)
                await save_user_data()
                await query.edit_message_text(f"Removed {coin} from your favorite coins!")
            else:
                await query.edit_message_text(f"{coin} is not in your favorites.")
        else:
            await query.edit_message_text("You don't have any favorite coins yet.")
    
    elif callback_data.startswith("vote_"):
        # Handle signal voting
        parts = callback_data.split("_")
        if len(parts) != 3:
            return
            
        signal_id = parts[1]
        vote_type = parts[2]  # "up" or "down"
        
        # Find the signal
        for signal in signals_data["signals"]:
            if str(signal["id"]) == signal_id:
                # Check if user already voted
                if "voters" not in signal:
                    signal["voters"] = {}
                
                prev_vote = signal["voters"].get(chat_id)
                
                # Update votes
                if vote_type == "up":
                    if prev_vote == "up":
                        # Removing upvote
                        signal["upvotes"] -= 1
                        del signal["voters"][chat_id]
                    else:
                        # Adding upvote
                        signal["upvotes"] += 1
                        if prev_vote == "down":
                            signal["downvotes"] -= 1
                        signal["voters"][chat_id] = "up"
                elif vote_type == "down":
                    if prev_vote == "down":
                        # Removing downvote
                        signal["downvotes"] -= 1
                        del signal["voters"][chat_id]
                    else:
                        # Adding downvote
                        signal["downvotes"] += 1
                        if prev_vote == "up":
                            signal["upvotes"] -= 1
                        signal["voters"][chat_id] = "down"
                
                # Update the keyboard with new vote counts
                keyboard = [
                    [
                        InlineKeyboardButton(f"👍 {signal['upvotes']}", callback_data=f"vote_{signal_id}_up"),
                        InlineKeyboardButton(f"👎 {signal['downvotes']}", callback_data=f"vote_{signal_id}_down")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_reply_markup(reply_markup=reply_markup)
                await save_signals_data()
                break

async def stat_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display statistics about signals, subscribers, and success rates."""
    
    # Count total signals
    total_signals = len(signals_data["signals"])
    
    # Count subscribers
    subscribers_count = len(user_data.get("subscribers", []))
    
    # Calculate success rates
    successful_signals = 0
    failed_signals = 0
    pending_signals = 0
    
    for signal in signals_data["signals"]:
        status = signal.get("status", PENDING)
        if status == HIT_TARGET:
            successful_signals += 1
        elif status in [HIT_STOPLOSS, EXPIRED]:
            failed_signals += 1
        else:
            pending_signals += 1
    
    success_rate = round((successful_signals / total_signals * 100), 2) if total_signals > 0 else 0
    
    # Count unique coins
    unique_coins = set()
    for signal in signals_data["signals"]:
        if "coin" in signal:
            unique_coins.add(signal["coin"])
    
    # Count by timeframe
    timeframe_counts = {tf: 0 for tf in TIMEFRAMES}
    for signal in signals_data["signals"]:
        tf = signal.get("timeframe")
        if tf in timeframe_counts and tf is not None:
            timeframe_counts[tf] += 1
    
    # Count by risk level
    risk_counts = {risk: 0 for risk in RISK_LEVELS}
    for signal in signals_data["signals"]:
        risk = signal.get("risk")
        if risk in risk_counts and risk is not None:
            risk_counts[risk] += 1
    
    # Format message
    message = (
        f"📊 *Bot Statistics* 📊\n\n"
        f"*Total Signals:* {total_signals}\n"
        f"*Subscribers:* {subscribers_count}\n\n"
        
        f"*Signal Performance:*\n"
        f"✅ Successful: {successful_signals} ({success_rate}%)\n"
        f"❌ Failed: {failed_signals}\n"
        f"⏳ Pending: {pending_signals}\n\n"
        
        f"*Unique Coins:* {len(unique_coins)}\n\n"
        
        f"*By Timeframe:*\n"
        f"SHORT: {timeframe_counts['SHORT']}\n"
        f"MID: {timeframe_counts['MID']}\n"
        f"LONG: {timeframe_counts['LONG']}\n\n"
        
        f"*By Risk Level:*\n"
        f"LOW: {risk_counts['LOW']}\n"
        f"MEDIUM: {risk_counts['MEDIUM']}\n"
        f"HIGH: {risk_counts['HIGH']}\n\n"
        
        f"*Most Recent Update:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    await update.message.reply_text(message, parse_mode="Markdown")

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Allow users to configure their notification settings."""
    user_id = str(update.effective_user.id)
    
    # Initialize settings if needed
    if "settings" not in user_data:
        user_data["settings"] = {}
    if user_id not in user_data["settings"]:
        user_data["settings"][user_id] = {
            "notify_all_signals": True,
            "notify_favorites_only": False,
            "risk_filter": "ALL",
            "timeframe_filter": "ALL"
        }
    
    settings = user_data["settings"][user_id]
    
    # Create keyboard for settings
    keyboard = [
        [
            InlineKeyboardButton(
                f"{'✅' if settings['notify_all_signals'] else '❌'} All Signals", 
                callback_data="settings_toggle_all"
            ),
            InlineKeyboardButton(
                f"{'✅' if settings['notify_favorites_only'] else '❌'} Favorites Only",
                callback_data="settings_toggle_favorites"
            )
        ],
        [
            InlineKeyboardButton(
                f"Risk Filter: {settings['risk_filter']}",
                callback_data="settings_risk"
            )
        ],
        [
            InlineKeyboardButton(
                f"Timeframe Filter: {settings['timeframe_filter']}",
                callback_data="settings_timeframe"
            )
        ],
        [
            InlineKeyboardButton("Save Settings", callback_data="settings_save")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        f"⚙️ *User Settings* ⚙️\n\n"
        f"Configure your notification preferences:\n\n"
        f"*Receive Notifications:*\n"
        f"{'✅' if settings['notify_all_signals'] else '❌'} All signals\n"
        f"{'✅' if settings['notify_favorites_only'] else '❌'} Favorites only\n\n"
        f"*Risk Level Filter:* {settings['risk_filter']}\n"
        f"*Timeframe Filter:* {settings['timeframe_filter']}\n\n"
        f"Use the buttons below to change your settings."
    )
    
    await update.message.reply_text(
        message,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

def main() -> None:
    """Start the bot."""
    if not BOT_TOKEN:
        logger.error("No BOT_TOKEN found. Set it in the .env file.")
        return
    
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("subscribe", subscribe))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe))
    application.add_handler(CommandHandler("signals", signals_command))
    application.add_handler(CommandHandler("price", price_command))
    application.add_handler(CommandHandler("coins", coins_command))
    application.add_handler(CommandHandler("performance", performance_command))
    application.add_handler(CommandHandler("debug", debug_command))
    application.add_handler(CommandHandler("test", test_command))
    application.add_handler(CommandHandler("privacy", privacy_help))
    application.add_handler(CommandHandler("stat", stat_command))
    application.add_handler(CommandHandler("settings", settings_command))
    
    # Add callback query handler for button interactions
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Add callback handler for performance-specific buttons
    for pattern in ["perf_signals", "perf_traders", "perf_coins", "perf_timeframe", "perf_back"]:
        application.add_handler(CallbackQueryHandler(handle_performance_callback, pattern=pattern))
    
    # Add message handler for group messages that tag the bot
    application.add_handler(MessageHandler(filters.ChatType.GROUPS, handle_message))
    
    # Add periodic job to check signal performance
    job_queue = application.job_queue
    job_queue.run_repeating(periodic_signal_check, interval=3600, first=10)  # Check every hour
    
    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)
    
    logger.info("Bot started!")

if __name__ == "__main__":
    main() 