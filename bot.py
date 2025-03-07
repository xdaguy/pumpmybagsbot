import os
import json
import logging
import re
from datetime import datetime
import requests
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
        [KeyboardButton("/signals"), KeyboardButton("/coins")],
        [KeyboardButton("/performance"), KeyboardButton("/help")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"🚀 *Welcome to Pump My Bags Bot!* 🚀\n\n"
        f"Hi {user.full_name}! I'll forward crypto trading signals from groups where I'm tagged.\n\n"
        f"📊 Use the buttons below or command menu to navigate:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

    # Add debug info about bot's username
    my_bot_info = await context.bot.get_me()
    await update.message.reply_text(
        f"🛠️ *Debug Info*\n\n"
        f"My username: @{my_bot_info.username}\n"
        f"To tag me correctly in groups, use: @{my_bot_info.username} $BTC SHORT HIGH your signal text\n\n"
        f"⚠️ IMPORTANT: Make sure the bot's privacy mode is disabled in BotFather settings.\n"
        f"If you just added me to a group, you may need to make me an admin or re-add me to the group.",
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

async def get_crypto_price(symbol):
    """Get current crypto price from an API"""
    try:
        # Using CoinGecko API (free, no API key required)
        # Remove $ if present and convert to lowercase
        clean_symbol = symbol.replace("$", "").lower()
        
        # For BTC/ETH/popular coins, try direct request
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={clean_symbol}&vs_currencies=usd"
        response = requests.get(url)
        data = response.json()
        
        if data and clean_symbol in data:
            return data[clean_symbol]["usd"]
        
        # If not found, try search
        search_url = f"https://api.coingecko.com/api/v3/search?query={clean_symbol}"
        search_response = requests.get(search_url)
        search_data = search_response.json()
        
        if search_data and "coins" in search_data and search_data["coins"]:
            coin_id = search_data["coins"][0]["id"]
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
            response = requests.get(url)
            data = response.json()
            if data and coin_id in data:
                return data[coin_id]["usd"]
        
        return None
    except Exception as e:
        logger.error(f"Error fetching crypto price: {e}")
        return None

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
    """Show signal performance stats"""
    if not signals_data["signals"]:
        await update.message.reply_text("No signals have been posted yet to show performance.")
        return
    
    # Calculate basic performance metrics
    total_signals = len(signals_data["signals"])
    coins_mentioned = {}
    timeframe_counts = {tf: 0 for tf in TIMEFRAMES}
    risk_counts = {risk: 0 for risk in RISK_LEVELS}
    
    for signal in signals_data["signals"]:
        # Count coin mentions
        coin = signal.get("coin", "UNKNOWN")
        coins_mentioned[coin] = coins_mentioned.get(coin, 0) + 1
        
        # Count timeframes
        timeframe = signal.get("timeframe", "UNKNOWN")
        if timeframe in TIMEFRAMES:
            timeframe_counts[timeframe] = timeframe_counts.get(timeframe, 0) + 1
        
        # Count risk levels
        risk = signal.get("risk", "UNKNOWN")
        if risk in RISK_LEVELS:
            risk_counts[risk] = risk_counts.get(risk, 0) + 1
    
    # Sort coins by mention count
    top_coins = sorted(coins_mentioned.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # Create performance message
    performance_text = (
        f"📊 *Signal Performance Stats* 📊\n\n"
        f"*Total Signals:* {total_signals}\n\n"
        f"*Most Mentioned Coins:*\n"
    )
    
    for coin, count in top_coins:
        performance_text += f"• {coin}: {count} signals\n"
    
    performance_text += f"\n*By Timeframe:*\n"
    for tf, count in timeframe_counts.items():
        if count > 0:
            performance_text += f"• {tf}: {count} signals\n"
    
    performance_text += f"\n*By Risk Level:*\n"
    for risk, count in risk_counts.items():
        if count > 0:
            performance_text += f"• {risk}: {count} signals\n"
    
    await update.message.reply_text(performance_text, parse_mode="Markdown")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    chat_id = str(query.message.chat_id)
    
    if data == "add_coins":
        await query.edit_message_text(
            "To add a coin to your favorites, use:\n"
            "/coins BTC\n\n"
            "Replace BTC with any cryptocurrency symbol."
        )
    
    elif data == "remove_coins":
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
    
    elif data.startswith("remove_"):
        coin = data.split("_")[1]
        if chat_id in user_data["users"] and "favorite_coins" in user_data["users"][chat_id]:
            if coin in user_data["users"][chat_id]["favorite_coins"]:
                user_data["users"][chat_id]["favorite_coins"].remove(coin)
                await save_user_data()
                await query.edit_message_text(f"Removed {coin} from your favorite coins!")
            else:
                await query.edit_message_text(f"{coin} is not in your favorites.")
        else:
            await query.edit_message_text("You don't have any favorite coins yet.")
    
    elif data.startswith("vote_"):
        # Handle signal voting
        parts = data.split("_")
        signal_id = parts[1]
        vote_type = parts[2]  # "up" or "down"
        
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

async def signals_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show recent signals to the user."""
    if not signals_data["signals"]:
        await update.message.reply_text("No signals have been posted yet.")
        return
    
    # Get the 5 most recent signals
    recent_signals = sorted(signals_data["signals"], key=lambda x: x["timestamp"], reverse=True)[:5]
    
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
                
                if is_subscribed:
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
    
    # Add callback query handler for button interactions
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Add message handler for group messages that tag the bot
    application.add_handler(MessageHandler(filters.ChatType.GROUPS, handle_message))
    
    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)
    
    logger.info("Bot started!")

if __name__ == "__main__":
    main() 