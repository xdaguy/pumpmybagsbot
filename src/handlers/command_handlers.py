from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.config import user_data, signals_data, coins_data, logger, TIMEFRAMES, RISK_LEVELS, PENDING, HIT_TARGET, HIT_STOPLOSS, EXPIRED
from src.services.price_service import get_crypto_price
from src.services.signal_processor import update_all_signals_performance
from src.services.data_handlers import save_user_data, save_signals_data, save_coins_data

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
        
        # Add to subscribers list if not already there
        if "subscribers" not in user_data:
            user_data["subscribers"] = []
        if str(chat_id) not in user_data["subscribers"]:
            user_data["subscribers"].append(str(chat_id))
            
        await save_user_data()
        
        await update.message.reply_text(
            f"👋 Hello {user.full_name}! Welcome to Pump My Bags Bot!\n\n"
            f"I'll forward crypto trading signals to you when tagged in groups.\n\n"
            f"Use /help to see all available commands."
        )
    else:
        await update.message.reply_text(
            f"Welcome back {user.full_name}! You're already subscribed to signals.\n\n"
            f"Use /help to see all available commands."
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = (
        "🤖 *Pump My Bags Bot Commands* 🤖\n\n"
        
        "*Basic Commands:*\n"
        "/start - Start the bot and subscribe to signals\n"
        "/help - Show this help message\n"
        "/subscribe - Subscribe to signals\n"
        "/unsubscribe - Unsubscribe from signals\n\n"
        
        "*Signal Commands:*\n"
        "/signals - Show recent signals\n"
        "/performance - View signal performance stats\n\n"
        
        "*Coin Commands:*\n"
        "/price BTC - Check current price of a coin\n"
        "/coins BTC - Add/remove coins from favorites\n\n"
        
        "*Settings & Stats:*\n"
        "/settings - Configure notification preferences\n"
        "/stat - View bot usage statistics\n\n"
        
        "*How to use in groups:*\n"
        "Tag me in a group message with a coin symbol to create a signal:\n"
        "@PumpMyBagsBot $BTC Buy at 80k, target 100k\n\n"
        
        "⚠️ *DISCLAIMER:* Trading involves risk. Do your own research."
    )
    
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Subscribe to signals"""
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
    else:
        user_data["users"][str(chat_id)]["subscribed"] = True
    
    # Add to subscribers list if not already there
    if "subscribers" not in user_data:
        user_data["subscribers"] = []
    if str(chat_id) not in user_data["subscribers"]:
        user_data["subscribers"].append(str(chat_id))
    
    await save_user_data()
    
    await update.message.reply_text(
        f"✅ You are now subscribed to trading signals!\n\n"
        f"You'll receive notifications when new signals are posted."
    )

async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unsubscribe from signals"""
    chat_id = update.effective_chat.id
    
    if str(chat_id) in user_data["users"]:
        user_data["users"][str(chat_id)]["subscribed"] = False
        
        # Remove from subscribers list
        if "subscribers" in user_data and str(chat_id) in user_data["subscribers"]:
            user_data["subscribers"].remove(str(chat_id))
        
        await save_user_data()
        
        await update.message.reply_text(
            f"❌ You have unsubscribed from trading signals.\n\n"
            f"You won't receive any more notifications. Use /subscribe to resubscribe."
        )
    else:
        await update.message.reply_text(
            f"You weren't subscribed to begin with. Use /subscribe to subscribe."
        )

async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get current price of a cryptocurrency"""
    if not context.args:
        await update.message.reply_text(
            "Please specify a coin symbol. Example: /price BTC"
        )
        return
    
    coin = context.args[0].upper()
    price = await get_crypto_price(coin)
    
    if price:
        await update.message.reply_text(
            f"💰 *{coin} Price*: ${price:,.2f} USD",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"❌ Couldn't find price for {coin}. Please check the symbol and try again."
        )

async def signals_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show recent signals"""
    # Update signal performance before showing
    await update_all_signals_performance()
    
    # Get the 5 most recent signals
    recent_signals = sorted(signals_data["signals"], key=lambda x: x.get("id", 0), reverse=True)[:5]
    
    if not recent_signals:
        await update.message.reply_text("No signals found yet.")
        return
    
    # Send a header message
    header = "📊 *Recent Trading Signals* 📊\n\nHere are the last 5 signals:\n"
    await update.message.reply_text(header, parse_mode="Markdown")
    
    # Send each signal as a separate message with vote buttons
    for signal in recent_signals:
        signal_id = signal.get("id")
        coin = signal.get("coin", "Unknown")
        sender = signal.get("sender", "Unknown")
        timestamp = signal.get("timestamp", "Unknown")
        status = signal.get("status", PENDING)
        
        # Get current price
        current_price = None
        if coin:
            current_price = await get_crypto_price(coin)
        
        # Format status with emoji
        status_emoji = "⏳"
        if status == HIT_TARGET:
            status_emoji = "✅"
        elif status == HIT_STOPLOSS:
            status_emoji = "❌"
        elif status == EXPIRED:
            status_emoji = "⏰"
        
        # Create vote buttons
        keyboard = [
            [
                InlineKeyboardButton(f"👍 {signal.get('upvotes', 0)}", callback_data=f"vote_{signal_id}_up"),
                InlineKeyboardButton(f"👎 {signal.get('downvotes', 0)}", callback_data=f"vote_{signal_id}_down")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Format message
        message = f"*Signal #{signal_id}*\n\n"
        
        if coin:
            message += f"*Coin:* {coin}\n"
            if current_price:
                message += f"*Current Price:* ${current_price:,.2f}\n"
        
        if "limit_order" in signal:
            position = signal.get("position", "Long")
            if position.lower() == "short":
                message += f"*Limit Order:* Sell at {signal['limit_order']}\n"
            else:
                message += f"*Limit Order:* Buy at {signal['limit_order']}\n"
        
        if "take_profit" in signal:
            message += f"*TP:* {signal['take_profit']}\n"
        
        if "position" in signal:
            message += f"*Position:* {signal['position']}\n"
        
        if "timeframe" in signal:
            message += f"*Timeframe:* {signal['timeframe']}\n"
        
        if "risk" in signal:
            message += f"*Risk:* {signal['risk']}\n"
        
        message += f"*Status:* {status_emoji} {status}\n"
        
        if "performance" in signal:
            perf = signal["performance"]
            perf_sign = "+" if perf >= 0 else ""
            message += f"*Performance:* {perf_sign}{perf:.2f}%\n"
        elif "unrealized_performance" in signal:
            perf = signal["unrealized_performance"]
            perf_sign = "+" if perf >= 0 else ""
            message += f"*Unrealized P/L:* {perf_sign}{perf:.2f}%\n"
        
        message += f"\n*From:* {signal.get('sender', 'Unknown')}\n"
        message += f"*Time:* {timestamp}\n"
        
        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode="Markdown"
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

async def stat_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display statistics about signals, subscribers, and success rates."""
    logger.debug("stat_command called by user_id: %s", update.effective_user.id)
    
    try:
        # Count total signals
        total_signals = len(signals_data.get("signals", []))
        logger.debug("Total signals: %d", total_signals)
        
        # Count subscribers
        subscribers_count = len(user_data.get("subscribers", []))
        logger.debug("Subscribers count: %d", subscribers_count)
        
        # Calculate success rates
        successful_signals = 0
        failed_signals = 0
        pending_signals = 0
        
        # Debug: Print signal status counts
        status_counts = {"PENDING": 0, "HIT_TARGET": 0, "HIT_STOPLOSS": 0, "EXPIRED": 0, "None": 0}
        
        if "signals" in signals_data:
            for signal in signals_data["signals"]:
                status = signal.get("status", PENDING)
                if status in status_counts:
                    status_counts[status] += 1
                else:
                    status_counts["None"] += 1
                    
                if status == HIT_TARGET:
                    successful_signals += 1
                elif status in [HIT_STOPLOSS, EXPIRED]:
                    failed_signals += 1
                else:
                    pending_signals += 1
        
        logger.debug("Signal status counts: %s", status_counts)
        logger.debug("Successful: %d, Failed: %d, Pending: %d", successful_signals, failed_signals, pending_signals)
        
        # Calculate success rate safely
        completed_signals = successful_signals + failed_signals
        success_rate = round((successful_signals / completed_signals * 100), 2) if completed_signals > 0 else 0
        
        # Count unique coins
        unique_coins = set()
        if "signals" in signals_data:
            for signal in signals_data["signals"]:
                if "coin" in signal:
                    unique_coins.add(signal["coin"])
        
        logger.debug("Unique coins: %s", unique_coins)
        
        # Count by timeframe
        timeframe_counts = {tf: 0 for tf in TIMEFRAMES}
        if "signals" in signals_data:
            for signal in signals_data["signals"]:
                tf = signal.get("timeframe")
                if tf in timeframe_counts and tf is not None:
                    timeframe_counts[tf] += 1
        
        logger.debug("Timeframe counts: %s", timeframe_counts)
        
        # Count by risk level
        risk_counts = {risk: 0 for risk in RISK_LEVELS}
        if "signals" in signals_data:
            for signal in signals_data["signals"]:
                risk = signal.get("risk")
                if risk in risk_counts and risk is not None:
                    risk_counts[risk] += 1
        
        logger.debug("Risk counts: %s", risk_counts)
        
        # Format message
        message = (
            f"📊 *Bot Statistics* 📊\n\n"
            f"*Total Signals:* {total_signals}\n"
            f"*Subscribers:* {subscribers_count}\n\n"
            
            f"*Signal Performance:*\n"
            f"✅ Successful: {successful_signals}" + (f" ({success_rate}%)" if completed_signals > 0 else "") + f"\n"
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
        
        logger.debug("Sending stat message: %s", message)
        await update.message.reply_text(message, parse_mode="Markdown")
    
    except Exception as e:
        logger.error(f"Error in stat_command: {e}", exc_info=True)
        await update.message.reply_text(f"⚠️ Error generating statistics: {str(e)}")

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

async def coins_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add or remove coins from favorites"""
    chat_id = str(update.effective_chat.id)
    
    # Initialize user if not exists
    if chat_id not in user_data["users"]:
        user = update.effective_user
        user_data["users"][chat_id] = {
            "name": user.full_name,
            "username": user.username,
            "chat_id": update.effective_chat.id,
            "subscribed": True,
            "joined_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "favorite_coins": []
        }
    
    # Initialize favorite_coins if not exists
    if "favorite_coins" not in user_data["users"][chat_id]:
        user_data["users"][chat_id]["favorite_coins"] = []
    
    # If no arguments, show current favorites and options
    if not context.args:
        favorite_coins = user_data["users"][chat_id]["favorite_coins"]
        
        if favorite_coins:
            coins_list = ", ".join(favorite_coins)
            message = f"Your favorite coins: {coins_list}\n\n"
        else:
            message = "You don't have any favorite coins yet.\n\n"
        
        message += "To add a coin: /coins BTC\nTo remove a coin: /coins remove BTC"
        
        # Add buttons for adding/removing coins
        keyboard = [
            [InlineKeyboardButton("Add Coin", callback_data="add_coins")],
            [InlineKeyboardButton("Remove Coin", callback_data="remove_coins")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup)
        return
    
    # Handle adding/removing coins
    action = context.args[0].lower()
    
    if action == "remove" and len(context.args) > 1:
        # Remove a coin
        coin = context.args[1].upper()
        if coin in user_data["users"][chat_id]["favorite_coins"]:
            user_data["users"][chat_id]["favorite_coins"].remove(coin)
            await save_user_data()
            await update.message.reply_text(f"Removed {coin} from your favorite coins!")
        else:
            await update.message.reply_text(f"{coin} is not in your favorites.")
    else:
        # Add a coin
        coin = context.args[0].upper()
        
        # Check if coin exists by getting its price
        price = await get_crypto_price(coin)
        
        if price:
            if coin not in user_data["users"][chat_id]["favorite_coins"]:
                user_data["users"][chat_id]["favorite_coins"].append(coin)
                await save_user_data()
                await update.message.reply_text(
                    f"Added {coin} to your favorite coins! Current price: ${price:,.2f}"
                )
            else:
                await update.message.reply_text(f"{coin} is already in your favorites.")
        else:
            await update.message.reply_text(
                f"Couldn't find price for {coin}. Please check the symbol and try again."
            )

async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Debug command for admins"""
    user_id = update.effective_user.id
    
    # Only allow specific users (replace with your user ID)
    allowed_users = [123456789]  # Add your Telegram user ID here
    
    if user_id not in allowed_users:
        await update.message.reply_text("You don't have permission to use this command.")
        return
    
    # Send debug info
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    
    # Send a response with details about the current chat
    debug_info = (
        f"*Debug Information*\n\n"
        f"Chat ID: `{chat_id}`\n"
        f"Chat Type: {chat_type}\n"
        f"User ID: `{user_id}`\n"
        f"Username: @{update.effective_user.username}\n"
        f"Full Name: {update.effective_user.full_name}\n\n"
        f"Total Signals: {len(signals_data['signals'])}\n"
        f"Total Users: {len(user_data['users'])}\n"
        f"Total Subscribers: {len(user_data.get('subscribers', []))}\n"
    )
    
    await update.message.reply_text(debug_info, parse_mode="Markdown")

async def privacy_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send instructions for fixing privacy settings"""
    privacy_text = (
        "🔒 *How to Fix Privacy Settings in Groups* 🔒\n\n"
        "If the bot can't see messages in your group, follow these steps:\n\n"
        "1. Go to your group settings\n"
        f"2. Send /mybots command\n"
        f"3. Select @{context.bot.username}\n"
        f"4. Go to 'Privacy Settings'\n"
        f"5. Select 'Turn off'\n"
        f"6. Click 'Apply'\n\n"
        f"*Note:* After changing this setting, please send /test in your group to verify it's working."
    )
    
    await update.message.reply_text(privacy_text, parse_mode="Markdown") 