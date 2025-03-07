from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.config import (
    user_data, signals_data, TIMEFRAMES, PENDING, 
    HIT_TARGET, HIT_STOPLOSS, EXPIRED, logger
)
from src.services.data_handlers import save_user_data, save_signals_data
from src.services.signal_processor import update_all_signals_performance

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