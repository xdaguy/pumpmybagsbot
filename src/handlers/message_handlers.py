import re
import uuid
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.config import user_data, signals_data, coins_data, logger
from src.services.signal_processor import extract_signal_data
from src.services.data_handlers import save_signals_data, save_coins_data
from src.services.price_service import parse_price

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages that tag the bot or use the /s command."""
    message = update.message
    
    # Add debug logging
    logger.info(f"Received message: '{message.text}' in chat type: {message.chat.type}")
    
    # Check if this is a command call from /s
    is_s_command = (context.args is not None)
    
    # Get bot username
    bot_username = context.bot.username
    bot_mentioned = False
    
    if message.text:
        bot_mentioned = f"@{bot_username}" in message.text
    
    # Log detection information
    logger.info(f"Bot username: {bot_username}, mentioned: {bot_mentioned}, is_s_command: {is_s_command}")
    
    # Determine the signal text based on the type of request
    signal_text = ""
    
    if is_s_command:
        # This is from a direct /s command, context.args contains the arguments
        signal_text = " ".join(context.args)
        logger.info(f"Processing /s command with args: {signal_text}")
    elif bot_mentioned:
        # This is a mention of the bot
        signal_text = message.text
        logger.info(f"Processing message with bot mention: {signal_text}")
    else:
        # This is a direct message to the bot, not a command
        # Only process it if it's a private chat (direct message)
        if message.chat.type == "private":
            # Special case: Handling when user types "/s signal info" as a message
            if message.text and message.text.startswith("/s "):
                signal_text = message.text[3:]  # Remove the "/s " prefix
                logger.info(f"Processing /s text message: {signal_text}")
            else:
                signal_text = message.text
                logger.info(f"Processing direct message: {signal_text}")
        else:
            # Not for us, return without processing
            logger.info("Message not relevant for signal processing, ignoring")
            return
    
    # If we have a signal text to process, do it
    if signal_text:
        try:
            # Process the signal
            await process_signal(update, context, signal_text)
        except Exception as e:
            logger.error(f"Error processing signal: {e}")
            await message.reply_text(
                "❌ Error processing your signal. Please check the format and try again.\n\n"
                "Example formats:\n"
                "- `/s long btc at 85k, tp1 is 84k, tp2 is 83k, stop loss 75k, risk is low`\n"
                "- `@pumpmybagsbot short eth at 2210, tp is 2000, high risk, long frame`",
                parse_mode="Markdown"
            )

async def process_signal(update: Update, context: ContextTypes.DEFAULT_TYPE, signal_text: str) -> None:
    """Process and store a trading signal."""
    message = update.message
    user = update.effective_user
    
    # Extract signal data using NLP processing
    coin, timeframe, risk_level, limit_order, take_profit, position, stop_loss, extracted_data = await extract_signal_data(signal_text)
    
    # Validate extracted data
    if not coin:
        await message.reply_text("❌ Could not identify a cryptocurrency symbol in your message. Please make sure to include a coin symbol like BTC, ETH, etc.")
        return
    
    if not limit_order:
        await message.reply_text("❌ Could not identify an entry price in your message. Please include an entry price like 'at 85k'.")
        return
    
    # Validate take profit - need at least one take profit target
    if not take_profit and not extracted_data["take_profit_targets"]:
        await message.reply_text("❌ Could not identify a take profit target in your message. Please include at least one take profit target like 'tp1 is 90k' or 'tp 90k'.")
        return
    
    # Format response based on extracted data
    confirmation_text = f"*Signal Detected:*\n\n"
    confirmation_text += f"*Coin:* {coin}\n"
    
    if position:
        confirmation_text += f"*Position:* {position}\n"
    else:
        confirmation_text += f"*Position:* Unknown (assuming Long)\n"
        position = "Long"  # Default to Long if not specified
    
    # Format prices nicely
    formatted_entry = f"${parse_price(limit_order):,.2f}" if limit_order else "Unknown"
    confirmation_text += f"*Entry Price:* {formatted_entry}\n"
    
    # Display take profit information
    if extracted_data["take_profit_targets"] and len(extracted_data["take_profit_targets"]) > 0:
        # If we have specific targets, show those instead of the general take profit
        confirmation_text += "*Take Profit Targets:*\n"
        tp_targets = extracted_data["take_profit_targets"]
        for tp_num, tp_val in sorted(tp_targets.items()):
            # Format the TP values properly
            formatted_val = f"${parse_price(tp_val):,.2f}"
            confirmation_text += f"• TP{tp_num}: {formatted_val}\n"
    elif take_profit:
        # Only show general take profit if we don't have specific targets
        formatted_tp = f"${parse_price(take_profit):,.2f}"
        confirmation_text += f"*Take Profit:* {formatted_tp}\n"
    
    if stop_loss:
        formatted_sl = f"${parse_price(stop_loss):,.2f}"
        confirmation_text += f"*Stop Loss:* {formatted_sl}\n"
    else:
        # Provide information about default stop loss
        confirmation_text += "*Stop Loss:* Not specified (using default 20% from entry)\n"
    
    if timeframe:
        # Check if timeframe was explicitly mentioned in text
        is_default_timeframe = not any(
            re.search(pattern, signal_text, re.IGNORECASE)
            for pattern in [
                r'timeframe', r'time frame', r'term',
                r'hourly', r'daily', r'weekly', r'monthly',
                r'short term', r'mid term', r'long term',
                r'short frame', r'mid frame', r'long frame',
                r'1h', r'4h', r'1d'
            ]
        )
        
        if is_default_timeframe:
            confirmation_text += f"*Timeframe:* {timeframe} (auto-detected)\n"
        else:
            confirmation_text += f"*Timeframe:* {timeframe}\n"
    else:
        confirmation_text += f"*Timeframe:* MID (default)\n"
    
    if risk_level:
        # Check if risk level was explicitly mentioned in text
        is_default_risk = not any(
            re.search(pattern, signal_text, re.IGNORECASE)
            for pattern in [
                r'risk', r'risky',
                r'low[- ]?risk', r'medium[- ]?risk', r'high[- ]?risk',
                r'safe', r'conservative', r'moderate', r'aggressive', r'dangerous'
            ]
        )
        
        if is_default_risk:
            confirmation_text += f"*Risk Level:* {risk_level} (auto-detected)\n"
        else:
            confirmation_text += f"*Risk Level:* {risk_level}\n"
    else:
        confirmation_text += f"*Risk Level:* MEDIUM (default)\n"
    
    # Generate a unique ID for the signal
    signal_id = str(uuid.uuid4())
    
    # Create signal object for storage - don't store redundant take_profit if we have specific targets
    new_signal = {
        "id": signal_id,
        "coin": coin,
        "position": position,
        "limit_order": limit_order,
        "stop_loss": stop_loss,
        "timeframe": timeframe,
        "risk_level": risk_level,
        "text": signal_text,
        "username": user.username,
        "user_id": str(user.id),
        "status": "PENDING",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "votes": {"up": [], "down": []}
    }
    
    # Store take profit only if we have specific targets or a general TP
    if extracted_data["take_profit_targets"]:
        tp_targets = extracted_data["take_profit_targets"]
        new_signal["take_profit_targets"] = tp_targets
        # Use TP1 as the general take profit for backward compatibility
        if 1 in tp_targets:
            new_signal["take_profit"] = tp_targets[1]
    elif take_profit:
        new_signal["take_profit"] = take_profit
    
    # Store the signal
    signals_data["signals"].append(new_signal)
    await save_signals_data()
    
    # Update coins data
    if coin not in coins_data["coins"]:
        coins_data["coins"].append(coin)
        await save_coins_data()
    
    # Add voting buttons
    keyboard = [
        [
            InlineKeyboardButton("👍 0", callback_data=f"vote_{signal_id}_up"),
            InlineKeyboardButton("👎 0", callback_data=f"vote_{signal_id}_down")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send confirmation
    await message.reply_text(
        f"{confirmation_text}\nSignal has been recorded and will be tracked for performance!",
        parse_mode="Markdown",
        reply_markup=reply_markup
    ) 