from datetime import datetime, timedelta
from telegram.ext import ContextTypes

from src.config import signals_data, user_data, logger, PENDING, HIT_TARGET, HIT_STOPLOSS
from src.services.signal_processor import update_all_signals_performance
from src.services.price_service import parse_price

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

def setup_jobs(application):
    """Set up periodic jobs"""
    job_queue = application.job_queue
    
    # Add periodic job to check signal performance every hour
    job_queue.run_repeating(periodic_signal_check, interval=3600, first=10)  # Check every hour
    
    logger.info("Job queue setup complete") 