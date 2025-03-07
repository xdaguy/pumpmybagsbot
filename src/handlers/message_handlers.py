from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.config import user_data, signals_data, coins_data, logger
from src.services.price_service import get_crypto_price
from src.services.signal_processor import extract_signal_data
from src.services.data_handlers import save_signals_data, save_coins_data

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