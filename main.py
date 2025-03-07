from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
)

from src.config import BOT_TOKEN, logger, load_data
from src.handlers.command_handlers import (
    start, help_command, subscribe, unsubscribe, signals_command, 
    price_command, coins_command, debug_command, privacy_help,
    stat_command, settings_command, performance_command, test_command
)
from src.handlers.callback_handlers import button_callback, handle_performance_callback
from src.handlers.message_handlers import handle_message
from src.services.job_queue import periodic_signal_check, setup_jobs

def main() -> None:
    """Start the bot."""
    # Load data
    load_data()
    
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
    
    # Set up job queue
    setup_jobs(application)
    
    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)
    
    logger.info("Bot started!")

if __name__ == "__main__":
    main() 