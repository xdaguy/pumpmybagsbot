from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime
from collections import Counter

from src.config import user_data, signals_data, coins_data, logger, TIMEFRAMES, RISK_LEVELS, PENDING, HIT_TARGET, HIT_STOPLOSS, EXPIRED
from src.services.data_handlers import save_user_data, save_signals_data
from src.services.price_service import get_crypto_price, parse_price

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the command /start is issued."""
    user = update.effective_user
    user_id = str(user.id)
    chat_id = update.effective_chat.id
    
    # Add user to user_data if not exists
    if user_id not in user_data["users"]:
        user_data["users"][user_id] = {
            "user_id": user_id,
            "username": user.username,
            "chat_id": chat_id,
            "subscribed": False,
            "favorite_coins": []
        }
        await save_user_data()
    
    welcome_message = (
        f"👋 Hello {user.first_name}!\n\n"
        f"I'm PumpMyBagsBot, your assistant for tracking crypto trading signals.\n\n"
        f"*Commands:*\n"
        f"/subscribe - Subscribe to signal notifications\n"
        f"/unsubscribe - Unsubscribe from notifications\n"
        f"/signals - Show recent signals\n"
        f"/price <coin> - Check current price of a coin\n"
        f"/coins - View and manage your favorite coins\n"
        f"/stat - View signal statistics\n"
        f"/settings - Configure your notification preferences\n"
        f"/help - Show this help message\n\n"
        f"Tag me in a message or use /s to share a trading signal!"
    )
    
    await update.message.reply_text(welcome_message, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a help message when the command /help is issued."""
    help_message = (
        f"*PumpMyBagsBot Commands:*\n\n"
        f"/subscribe - Subscribe to signal notifications\n"
        f"/unsubscribe - Unsubscribe from notifications\n"
        f"/signals - Show recent signals\n"
        f"/price <coin> - Check current price of a coin\n"
        f"/coins - View and manage your favorite coins\n"
        f"/stat - View signal statistics\n"
        f"/settings - Configure your notification preferences\n"
        f"/help - Show this help message\n\n"
        f"*Sharing signals:*\n"
        f"1. Tag me in a message: @pumpmybagsbot\n"
        f"2. Use the /s command followed by your signal\n\n"
        f"*Example signals:*\n"
        f"`@pumpmybagsbot short btc at 85k, tp1 is 84k, tp2 is 83k, risk is low.`\n\n"
        f"`/s long eth at 2210, tp is 2500, high risk, long frame`"
    )
    
    await update.message.reply_text(help_message, parse_mode="Markdown")

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Subscribe user to signal notifications."""
    user = update.effective_user
    user_id = str(user.id)
    chat_id = update.effective_chat.id
    
    # Add user to user_data if not exists
    if user_id not in user_data["users"]:
        user_data["users"][user_id] = {
            "user_id": user_id,
            "username": user.username,
            "chat_id": chat_id,
            "subscribed": True,
            "favorite_coins": []
        }
        await save_user_data()
        await update.message.reply_text("✅ You are now subscribed to signal notifications!")
    else:
        # Update subscription status
        if user_data["users"][user_id].get("subscribed", False):
            await update.message.reply_text("ℹ️ You are already subscribed to signal notifications.")
        else:
            user_data["users"][user_id]["subscribed"] = True
            user_data["users"][user_id]["chat_id"] = chat_id  # Update chat_id in case it changed
            await save_user_data()
            await update.message.reply_text("✅ You are now subscribed to signal notifications!")

async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unsubscribe user from signal notifications."""
    user = update.effective_user
    user_id = str(user.id)
    
    if user_id in user_data["users"]:
        user_data["users"][user_id]["subscribed"] = False
        await save_user_data()
        await update.message.reply_text("✅ You have been unsubscribed from signal notifications.")
    else:
        await update.message.reply_text("ℹ️ You are not currently subscribed.")

async def signals_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show recent signals."""
    # Get the most recent 5 signals
    recent_signals = signals_data["signals"][-5:] if signals_data["signals"] else []
    
    if not recent_signals:
        await update.message.reply_text("No signals found yet.")
        return
    
    # Create header for signals
    header = "*Recent Trading Signals:*\n\n"
    
    # Create individual signal messages
    signal_messages = []
    for i, signal in enumerate(recent_signals, 1):
        coin = signal.get("coin", "Unknown")
        position = signal.get("position", "Unknown")
        entry = signal.get("limit_order", "Unknown")
        tp = signal.get("take_profit", "Unknown")
        status = signal.get("status", PENDING)
        date = signal.get("timestamp", "Unknown date")
        
        # Add status emoji
        status_emoji = "✅" if status == HIT_TARGET else "❌" if status == HIT_STOPLOSS else "⏰" if status == EXPIRED else "🔍"
        
        # Format message
        signal_msg = (
            f"*Signal {i}:*\n"
            f"{status_emoji} {position} {coin} at {entry}\n"
            f"Target: {tp}\n"
            f"Status: {status}\n"
            f"Added: {date}\n"
        )
        
        # Add performance if available
        if "performance" in signal and status != PENDING:
            perf = signal["performance"]
            perf_sign = "+" if perf >= 0 else ""
            signal_msg += f"Performance: {perf_sign}{perf:.2f}%\n"
        elif "unrealized_performance" in signal and status == PENDING:
            perf = signal["unrealized_performance"]
            perf_sign = "+" if perf >= 0 else ""
            signal_msg += f"Current: {perf_sign}{perf:.2f}%\n"
        
        signal_messages.append(signal_msg)
    
    # Combine all messages
    full_message = header + "\n".join(signal_messages)
    
    await update.message.reply_text(full_message, parse_mode="Markdown")

async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get current price of a cryptocurrency."""
    if not context.args:
        await update.message.reply_text("Please provide a coin symbol. Example: /price btc")
        return
    
    coin = context.args[0].upper()
    
    # Get price
    price = await get_crypto_price(coin)
    
    if price:
        await update.message.reply_text(f"Current price of {coin}: ${price:,.2f}")
    else:
        await update.message.reply_text(f"Could not fetch price for {coin}. Please check the symbol and try again.")

async def coins_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View and manage favorite coins."""
    user = update.effective_user
    user_id = str(user.id)
    
    # Ensure user exists in user_data
    if user_id not in user_data["users"]:
        user_data["users"][user_id] = {
            "user_id": user_id,
            "username": user.username,
            "chat_id": update.effective_chat.id,
            "subscribed": False,
            "favorite_coins": []
        }
        await save_user_data()
    
    # Check if adding a coin to favorites
    if context.args:
        coin = context.args[0].upper()
        favorite_coins = user_data["users"][user_id].get("favorite_coins", [])
        
        if coin in favorite_coins:
            favorite_coins.remove(coin)
            await update.message.reply_text(f"{coin} removed from your favorites!")
        else:
            favorite_coins.append(coin)
            await update.message.reply_text(f"{coin} added to your favorites!")
        
        user_data["users"][user_id]["favorite_coins"] = favorite_coins
        await save_user_data()
    
    # Display favorite coins
    favorite_coins = user_data["users"][user_id].get("favorite_coins", [])
    
    if favorite_coins:
        coins_text = "Your favorite coins:\n\n" + "\n".join([f"• {coin}" for coin in favorite_coins])
        coins_text += "\n\nTo add or remove a coin, use /coins <symbol>"
    else:
        coins_text = "You don't have any favorite coins yet. Add one with /coins <symbol>"
    
    await update.message.reply_text(coins_text)

async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Debug command to show internal data (for admins only)."""
    user = update.effective_user
    # List of admin user IDs (add your Telegram ID here)
    admin_ids = ["12345678"]  # Replace with actual admin IDs
    
    if str(user.id) not in admin_ids:
        await update.message.reply_text("⚠️ This command is restricted to admins only.")
        return
    
    debug_text = (
        f"*Debug Information:*\n\n"
        f"Users: {len(user_data['users'])}\n"
        f"Subscribers: {sum(1 for user in user_data['users'].values() if user.get('subscribed', False))}\n"
        f"Signals: {len(signals_data['signals'])}\n"
        f"Pending Signals: {sum(1 for signal in signals_data['signals'] if signal.get('status') == PENDING)}\n"
    )
    
    await update.message.reply_text(debug_text, parse_mode="Markdown")

async def privacy_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Privacy information."""
    privacy_text = (
        "*Privacy Information:*\n\n"
        "This bot collects the following data:\n"
        "• Your Telegram user ID\n"
        "• Your username\n"
        "• Your chat ID\n"
        "• Your favorite coins (if you add any)\n"
        "• Your subscription status\n\n"
        "This data is used solely for the purpose of sending you signal notifications "
        "based on your preferences.\n\n"
        "You can delete your data by unsubscribing using /unsubscribe."
    )
    
    await update.message.reply_text(privacy_text, parse_mode="Markdown")

async def stat_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show statistics about signals, subscribers, and success rates."""
    if not signals_data["signals"]:
        await update.message.reply_text("No signals data available yet.")
        return
    
    # Count signals
    total_signals = len(signals_data["signals"])
    successful_signals = sum(1 for s in signals_data["signals"] if s.get("status") == HIT_TARGET)
    failed_signals = sum(1 for s in signals_data["signals"] if s.get("status") == HIT_STOPLOSS)
    expired_signals = sum(1 for s in signals_data["signals"] if s.get("status") == EXPIRED)
    pending_signals = sum(1 for s in signals_data["signals"] if s.get("status") == PENDING)
    
    # Success rate calculation
    completed_signals = successful_signals + failed_signals + expired_signals
    success_rate = (successful_signals / completed_signals * 100) if completed_signals > 0 else 0
    
    # Count subscribers
    subscribers = sum(1 for user in user_data["users"].values() if user.get("subscribed", False))
    
    # Count unique coins
    unique_coins = set(s.get("coin") for s in signals_data["signals"] if s.get("coin"))
    
    # Count by timeframe
    timeframe_counts = {}
    for tf in TIMEFRAMES:
        timeframe_counts[tf] = sum(1 for s in signals_data["signals"] if s.get("timeframe") == tf)
    
    # Count by risk level
    risk_counts = {}
    for risk in RISK_LEVELS:
        risk_counts[risk] = sum(1 for s in signals_data["signals"] if s.get("risk_level") == risk)
    
    # Format statistics message
    stats_text = (
        f"*Signal Bot Statistics:*\n\n"
        f"*Signals:*\n"
        f"Total: {total_signals}\n"
        f"Successful: {successful_signals}\n"
        f"Failed: {failed_signals}\n"
        f"Expired: {expired_signals}\n"
        f"Pending: {pending_signals}\n"
        f"Success Rate: {success_rate:.1f}%\n\n"
        
        f"*By Timeframe:*\n"
    )
    
    for tf, count in timeframe_counts.items():
        tf_success = sum(1 for s in signals_data["signals"] 
                     if s.get("timeframe") == tf and s.get("status") == HIT_TARGET)
        tf_total = sum(1 for s in signals_data["signals"] 
                    if s.get("timeframe") == tf and s.get("status") != PENDING)
        tf_rate = (tf_success / tf_total * 100) if tf_total > 0 else 0
        stats_text += f"{tf}: {count} signals, {tf_rate:.1f}% success\n"
    
    stats_text += f"\n*By Risk Level:*\n"
    for risk, count in risk_counts.items():
        risk_success = sum(1 for s in signals_data["signals"] 
                       if s.get("risk_level") == risk and s.get("status") == HIT_TARGET)
        risk_total = sum(1 for s in signals_data["signals"] 
                      if s.get("risk_level") == risk and s.get("status") != PENDING)
        risk_rate = (risk_success / risk_total * 100) if risk_total > 0 else 0
        stats_text += f"{risk}: {count} signals, {risk_rate:.1f}% success\n"
    
    stats_text += (
        f"\n*Summary:*\n"
        f"Unique Coins: {len(unique_coins)}\n"
        f"Subscribers: {subscribers}\n"
    )
    
    await update.message.reply_text(stats_text, parse_mode="Markdown")

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Configure user notification settings."""
    user = update.effective_user
    user_id = str(user.id)
    
    # Ensure user exists in user_data
    if user_id not in user_data["users"]:
        user_data["users"][user_id] = {
            "user_id": user_id,
            "username": user.username,
            "chat_id": update.effective_chat.id,
            "subscribed": False,
            "favorite_coins": []
        }
        await save_user_data()
    
    # Initialize settings if they don't exist
    if "settings" not in user_data:
        user_data["settings"] = {}
    
    if user_id not in user_data["settings"]:
        user_data["settings"][user_id] = {
            "notify_all_signals": True,
            "notify_favorites_only": False,
            "risk_filter": "ALL",
            "timeframe_filter": "ALL"
        }
        await save_user_data()
    
    # Get current settings
    settings = user_data["settings"][user_id]
    
    # Create inline keyboard
    keyboard = [
        [
            InlineKeyboardButton("All Signals: " + ("ON ✅" if settings["notify_all_signals"] else "OFF ❌"), 
                                 callback_data="settings_toggle_all"),
            InlineKeyboardButton("Favorites Only: " + ("ON ✅" if settings["notify_favorites_only"] else "OFF ❌"), 
                                 callback_data="settings_toggle_favorites")
        ],
        [
            InlineKeyboardButton("Risk Filter: " + settings["risk_filter"], 
                                 callback_data="settings_cycle_risk"),
            InlineKeyboardButton("Timeframe Filter: " + settings["timeframe_filter"], 
                                 callback_data="settings_cycle_timeframe")
        ],
        [
            InlineKeyboardButton("💾 Save Settings", callback_data="settings_save")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    settings_text = (
        f"*Notification Settings:*\n\n"
        f"Here you can customize what signal notifications you receive.\n\n"
        f"• All Signals: Receive updates for all signals\n"
        f"• Favorites Only: Only receive updates for your favorite coins\n"
        f"• Risk Filter: Filter signals by risk level\n"
        f"• Timeframe Filter: Filter signals by timeframe\n\n"
        f"Use the buttons below to configure your preferences:"
    )
    
    await update.message.reply_text(settings_text, reply_markup=reply_markup, parse_mode="Markdown")

async def performance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show detailed performance statistics and leaderboards."""
    # Create inline keyboard for performance options
    keyboard = [
        [
            InlineKeyboardButton("Signal Performance", callback_data="perf_signals"),
            InlineKeyboardButton("Trader Leaderboard", callback_data="perf_traders")
        ],
        [
            InlineKeyboardButton("Coin Performance", callback_data="perf_coins"),
            InlineKeyboardButton("Timeframe Analysis", callback_data="perf_timeframe")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    perf_text = (
        f"*Performance Dashboard:*\n\n"
        f"Select a category to view detailed performance statistics:"
    )
    
    await update.message.reply_text(perf_text, reply_markup=reply_markup, parse_mode="Markdown")

async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Test command for developers to test features."""
    # Check if this is an admin user
    user = update.effective_user
    admin_ids = ["12345678"]  # Replace with actual admin IDs
    
    if str(user.id) not in admin_ids:
        await update.message.reply_text("⚠️ This command is restricted to admins only.")
        return
    
    # Simple test message
    await update.message.reply_text("Test command executed successfully. The bot is operational.")

async def parser_test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Test the signal parser with the provided text"""
    if not context.args:
        await update.message.reply_text("Please provide text to test the parser. Usage: /parser_test your signal text here")
        return
    
    # Get the text to parse
    text = " ".join(context.args)
    
    try:
        # Extract signal data
        from src.services.signal_processor import extract_signal_data
        coin, timeframe, risk_level, limit_order, take_profit, position, stop_loss, extracted_data = await extract_signal_data(text)
        
        # Format the results
        result = "📊 *Parser Test Results:*\n\n"
        result += f"*Text:* {text}\n\n"
        result += f"*Coin:* {coin}\n"
        result += f"*Position:* {position}\n"
        result += f"*Entry:* {limit_order}\n"
        result += f"*Take Profit:* {take_profit}\n"
        
        # Show all take profit targets
        if extracted_data["take_profit_targets"]:
            result += "*Take Profit Targets:*\n"
            for tp_num, tp_val in sorted(extracted_data["take_profit_targets"].items()):
                result += f"• TP{tp_num}: {tp_val}\n"
        
        result += f"*Stop Loss:* {stop_loss}\n"
        result += f"*Timeframe:* {timeframe}\n"
        result += f"*Risk Level:* {risk_level}\n"
        
        # Show all extracted data for reference
        result += "\n*Raw Extracted Data:*\n"
        result += str(extracted_data)
        
        await update.message.reply_text(result, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error parsing signal: {str(e)}") 