from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from collections import Counter, defaultdict

from src.config import (
    user_data, signals_data, logger, 
    TIMEFRAMES, RISK_LEVELS, PENDING, HIT_TARGET, HIT_STOPLOSS, EXPIRED
)
from src.services.data_handlers import save_user_data

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks for settings and voting"""
    query = update.callback_query
    user = query.from_user
    user_id = str(user.id)
    
    # Acknowledge the query
    await query.answer()
    
    if query.data.startswith("settings_"):
        # Settings related callbacks
        
        # Initialize user settings if they don't exist
        if "settings" not in user_data:
            user_data["settings"] = {}
        
        if user_id not in user_data["settings"]:
            user_data["settings"][user_id] = {
                "notify_all_signals": True,
                "notify_favorites_only": False,
                "risk_filter": "ALL",
                "timeframe_filter": "ALL"
            }
        
        # Get current settings
        settings = user_data["settings"][user_id]
        
        # Toggle settings based on callback
        if query.data == "settings_toggle_all":
            settings["notify_all_signals"] = not settings["notify_all_signals"]
        elif query.data == "settings_toggle_favorites":
            settings["notify_favorites_only"] = not settings["notify_favorites_only"]
        elif query.data == "settings_cycle_risk":
            # Cycle through risk filters: ALL -> LOW -> MEDIUM -> HIGH -> ALL
            all_risks = ["ALL"] + RISK_LEVELS
            current_index = all_risks.index(settings["risk_filter"])
            settings["risk_filter"] = all_risks[(current_index + 1) % len(all_risks)]
        elif query.data == "settings_cycle_timeframe":
            # Cycle through timeframe filters: ALL -> SHORT -> MID -> LONG -> ALL
            all_timeframes = ["ALL"] + TIMEFRAMES
            current_index = all_timeframes.index(settings["timeframe_filter"])
            settings["timeframe_filter"] = all_timeframes[(current_index + 1) % len(all_timeframes)]
        elif query.data == "settings_save":
            # Save settings
            await save_user_data()
            await query.message.edit_text(
                "✅ Your notification settings have been saved!\n\n"
                "Use /settings to change them again anytime.",
                parse_mode="Markdown"
            )
            return
        
        # Update keyboard with new settings
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
        
        await query.message.edit_reply_markup(reply_markup=reply_markup)
    
    elif query.data.startswith("vote_"):
        # Voting related callbacks
        signal_id = query.data.split("_")[1]
        vote_type = query.data.split("_")[2]  # up or down
        
        # Find the signal by ID
        signal = None
        for s in signals_data["signals"]:
            if str(s.get("id")) == signal_id:
                signal = s
                break
        
        if not signal:
            await query.message.edit_text("Signal not found.")
            return
        
        # Initialize votes if not present
        if "votes" not in signal:
            signal["votes"] = {"up": [], "down": []}
        
        # Check if user already voted
        already_voted_up = user_id in signal["votes"]["up"]
        already_voted_down = user_id in signal["votes"]["down"]
        
        # Process the vote
        if vote_type == "up":
            if already_voted_up:
                # Remove upvote
                signal["votes"]["up"].remove(user_id)
            else:
                # Add upvote, remove downvote if exists
                signal["votes"]["up"].append(user_id)
                if already_voted_down:
                    signal["votes"]["down"].remove(user_id)
        elif vote_type == "down":
            if already_voted_down:
                # Remove downvote
                signal["votes"]["down"].remove(user_id)
            else:
                # Add downvote, remove upvote if exists
                signal["votes"]["down"].append(user_id)
                if already_voted_up:
                    signal["votes"]["up"].remove(user_id)
        
        # Update button counts
        upvotes = len(signal["votes"]["up"])
        downvotes = len(signal["votes"]["down"])
        
        # Create updated keyboard
        keyboard = [
            [
                InlineKeyboardButton(f"👍 {upvotes}", callback_data=f"vote_{signal_id}_up"),
                InlineKeyboardButton(f"👎 {downvotes}", callback_data=f"vote_{signal_id}_down")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Update message with new vote counts
        await query.message.edit_reply_markup(reply_markup=reply_markup)

async def handle_performance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle performance dashboard callbacks"""
    query = update.callback_query
    
    # Acknowledge the query
    await query.answer()
    
    if query.data == "perf_signals":
        # Signal performance analysis
        if not signals_data["signals"]:
            await query.message.edit_text("No signal data available yet.")
            return
        
        # Count by status
        status_counts = Counter(s.get("status", PENDING) for s in signals_data["signals"])
        
        # Calculate average performance
        hit_signals = [s for s in signals_data["signals"] if s.get("status") == HIT_TARGET]
        avg_performance = sum(s.get("performance", 0) for s in hit_signals) / len(hit_signals) if hit_signals else 0
        
        # Calculate best performance
        best_performance = max((s.get("performance", 0) for s in signals_data["signals"] if "performance" in s), default=0)
        best_signal = next((s for s in signals_data["signals"] if s.get("performance", 0) == best_performance), None)
        
        # Format performance message
        perf_text = (
            f"*Signal Performance Analysis:*\n\n"
            f"Total Signals: {len(signals_data['signals'])}\n"
            f"Hit Target: {status_counts.get(HIT_TARGET, 0)}\n"
            f"Hit Stop Loss: {status_counts.get(HIT_STOPLOSS, 0)}\n"
            f"Expired: {status_counts.get(EXPIRED, 0)}\n"
            f"Pending: {status_counts.get(PENDING, 0)}\n\n"
            f"Average Performance: {avg_performance:.2f}%\n"
        )
        
        if best_signal:
            perf_text += (
                f"\n*Best Performing Signal:*\n"
                f"Coin: {best_signal.get('coin')}\n"
                f"Performance: +{best_performance:.2f}%\n"
                f"Date: {best_signal.get('timestamp')}\n"
            )
        
        # Add back button
        keyboard = [[InlineKeyboardButton("◀️ Back", callback_data="perf_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(perf_text, reply_markup=reply_markup, parse_mode="Markdown")
    
    elif query.data == "perf_traders":
        # Trader leaderboard
        if not signals_data["signals"]:
            await query.message.edit_text("No signal data available yet.")
            return
        
        # Group signals by trader
        traders = defaultdict(list)
        for signal in signals_data["signals"]:
            trader = signal.get("username", "Anonymous")
            traders[trader].append(signal)
        
        # Calculate stats for each trader
        trader_stats = []
        for trader, signals in traders.items():
            completed = [s for s in signals if s.get("status") != PENDING]
            if not completed:
                continue
                
            successful = [s for s in completed if s.get("status") == HIT_TARGET]
            success_rate = len(successful) / len(completed) * 100 if completed else 0
            avg_performance = sum(s.get("performance", 0) for s in completed) / len(completed) if completed else 0
            
            trader_stats.append({
                "name": trader,
                "signals": len(signals),
                "success_rate": success_rate,
                "avg_performance": avg_performance
            })
        
        # Sort traders by success rate
        trader_stats.sort(key=lambda x: x["success_rate"], reverse=True)
        
        # Format leaderboard message
        leaderboard_text = "*Trader Leaderboard:*\n\n"
        
        for i, trader in enumerate(trader_stats[:10], 1):  # Top 10 traders
            leaderboard_text += (
                f"{i}. {trader['name']}\n"
                f"   Signals: {trader['signals']}\n"
                f"   Success Rate: {trader['success_rate']:.1f}%\n"
                f"   Avg. Performance: {trader['avg_performance']:.2f}%\n\n"
            )
        
        if not trader_stats:
            leaderboard_text += "No trader data available yet."
        
        # Add back button
        keyboard = [[InlineKeyboardButton("◀️ Back", callback_data="perf_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(leaderboard_text, reply_markup=reply_markup, parse_mode="Markdown")
    
    elif query.data == "perf_coins":
        # Coin performance analysis
        if not signals_data["signals"]:
            await query.message.edit_text("No signal data available yet.")
            return
        
        # Group signals by coin
        coins = defaultdict(list)
        for signal in signals_data["signals"]:
            coin = signal.get("coin")
            if coin:
                coins[coin].append(signal)
        
        # Calculate stats for each coin
        coin_stats = []
        for coin, signals in coins.items():
            completed = [s for s in signals if s.get("status") != PENDING]
            if not completed:
                continue
                
            successful = [s for s in completed if s.get("status") == HIT_TARGET]
            success_rate = len(successful) / len(completed) * 100 if completed else 0
            avg_performance = sum(s.get("performance", 0) for s in completed) / len(completed) if completed else 0
            
            coin_stats.append({
                "name": coin,
                "signals": len(signals),
                "success_rate": success_rate,
                "avg_performance": avg_performance
            })
        
        # Sort coins by average performance
        coin_stats.sort(key=lambda x: x["avg_performance"], reverse=True)
        
        # Format coin performance message
        coins_text = "*Coin Performance Analysis:*\n\n"
        
        for i, coin in enumerate(coin_stats[:10], 1):  # Top 10 coins
            coins_text += (
                f"{i}. {coin['name']}\n"
                f"   Signals: {coin['signals']}\n"
                f"   Success Rate: {coin['success_rate']:.1f}%\n"
                f"   Avg. Performance: {coin['avg_performance']:.2f}%\n\n"
            )
        
        if not coin_stats:
            coins_text += "No coin performance data available yet."
        
        # Add back button
        keyboard = [[InlineKeyboardButton("◀️ Back", callback_data="perf_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(coins_text, reply_markup=reply_markup, parse_mode="Markdown")
    
    elif query.data == "perf_timeframe":
        # Timeframe analysis
        if not signals_data["signals"]:
            await query.message.edit_text("No signal data available yet.")
            return
        
        # Group signals by timeframe
        timeframes = defaultdict(list)
        for signal in signals_data["signals"]:
            tf = signal.get("timeframe", "Unknown")
            timeframes[tf].append(signal)
        
        # Calculate stats for each timeframe
        timeframe_stats = []
        for tf, signals in timeframes.items():
            completed = [s for s in signals if s.get("status") != PENDING]
            if not completed:
                continue
                
            successful = [s for s in completed if s.get("status") == HIT_TARGET]
            success_rate = len(successful) / len(completed) * 100 if completed else 0
            avg_performance = sum(s.get("performance", 0) for s in completed) / len(completed) if completed else 0
            
            timeframe_stats.append({
                "name": tf,
                "signals": len(signals),
                "success_rate": success_rate,
                "avg_performance": avg_performance
            })
        
        # Format timeframe analysis message
        timeframe_text = "*Timeframe Analysis:*\n\n"
        
        for tf in timeframe_stats:
            timeframe_text += (
                f"*{tf['name']}:*\n"
                f"Signals: {tf['signals']}\n"
                f"Success Rate: {tf['success_rate']:.1f}%\n"
                f"Avg. Performance: {tf['avg_performance']:.2f}%\n\n"
            )
        
        if not timeframe_stats:
            timeframe_text += "No timeframe data available yet."
        
        # Add back button
        keyboard = [[InlineKeyboardButton("◀️ Back", callback_data="perf_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(timeframe_text, reply_markup=reply_markup, parse_mode="Markdown")
    
    elif query.data == "perf_back":
        # Return to main performance dashboard
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
        
        await query.message.edit_text(perf_text, reply_markup=reply_markup, parse_mode="Markdown") 