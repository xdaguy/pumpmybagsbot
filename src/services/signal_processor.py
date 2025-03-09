import re
from datetime import datetime, timedelta

from src.config import (
    PENDING, HIT_TARGET, HIT_STOPLOSS, EXPIRED, 
    TIMEFRAMES, RISK_LEVELS, TIMEFRAME_DURATIONS,
    signals_data, logger
)
from src.services.price_service import get_crypto_price, parse_price
from src.services.data_handlers import save_signals_data

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
    
    # Get explicit stop loss if defined, otherwise use default
    explicit_stop_loss = parse_price(signal.get("stop_loss"))
    
    # Position and default stop loss
    position = signal.get("position", "Long")
    stop_loss_pct = 0.2  # 20% default stop loss
    
    # Check for multiple take profit targets
    tp_targets = {}
    if "take_profit_targets" in signal and signal["take_profit_targets"]:
        for tp_num, tp_val in signal["take_profit_targets"].items():
            tp_targets[int(tp_num)] = parse_price(tp_val)
        logger.debug(f"Found multiple TP targets: {tp_targets}")
    
    if entry_price:
        # Calculate stop loss value
        if explicit_stop_loss:
            stop_loss = explicit_stop_loss
            logger.debug(f"Using explicit stop loss: {stop_loss}")
        elif position.lower() == "long":
            stop_loss = entry_price * (1 - stop_loss_pct)
            logger.debug(f"Using calculated long stop loss: {stop_loss}")
        else:  # Short position
            stop_loss = entry_price * (1 + stop_loss_pct)
            logger.debug(f"Using calculated short stop loss: {stop_loss}")
        
        # Check if any TP targets were hit for long positions
        if position.lower() == "long":
            # Sort TP targets from lowest to highest (for long positions we hit the closest ones first)
            hit_tp = None
            hit_tp_num = None
            if tp_targets:
                for tp_num, tp_price in sorted(tp_targets.items(), key=lambda x: x[1]):
                    if current_price >= tp_price:
                        hit_tp = tp_price
                        hit_tp_num = tp_num
                        logger.debug(f"Hit TP{tp_num} at {tp_price}")
                        break
            
            # Check if target hit (price went up to target)
            if hit_tp:
                signal["status"] = HIT_TARGET
                signal["hit_tp"] = hit_tp_num
                signal["performance"] = ((hit_tp - entry_price) / entry_price) * 100
                signal["exit_price"] = hit_tp
                signal["exit_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            elif target_price and current_price >= target_price:
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
            # Sort TP targets from highest to lowest (for short positions we hit the closest ones first)
            hit_tp = None
            hit_tp_num = None
            if tp_targets:
                for tp_num, tp_price in sorted(tp_targets.items(), key=lambda x: x[1], reverse=True):
                    if current_price <= tp_price:
                        hit_tp = tp_price
                        hit_tp_num = tp_num
                        logger.debug(f"Hit TP{tp_num} at {tp_price}")
                        break
            
            # Check if target hit (price went down to target)
            if hit_tp:
                signal["status"] = HIT_TARGET
                signal["hit_tp"] = hit_tp_num
                signal["performance"] = ((entry_price - hit_tp) / entry_price) * 100
                signal["exit_price"] = hit_tp
                signal["exit_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            elif target_price and current_price <= target_price:
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
        
        # Only check pending signals
        if signal["status"] == PENDING:
            original_status = signal.get("status")
            updated_signal = await check_signal_performance(signal)
            
            # Update if status changed
            if updated_signal.get("status") != original_status:
                updated = True
    
    if updated:
        await save_signals_data()
    
    return updated

async def extract_signal_data(text):
    """Extract coin symbol, timeframe, risk level and trading details from natural language text"""
    logger.info(f"Extracting data from text: {text}")
    
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
    
    # Extract entry price (limit order)
    entry_price = None
    limit_order = None
    entry_patterns = [
        r'(?:entry|enter|buy|long|short|sell)[^0-9]*(?:at|@|:)?\s*(\d+(?:,\d+)*(?:\.\d+)?[kK]?)',  # entry at 88k, buy at 88k
        r'(?:at|@)\s*(\d+(?:,\d+)*(?:\.\d+)?[kK]?)',  # at 88k
        r'\b(\d+(?:,\d+)*(?:\.\d+)?[kK]?)\s*(?:entry|enter|buy|long|short|sell)',  # 88k entry
        r'\blimit\s*[:-]?\s*(\d+(?:,\d+)*(?:\.\d+)?[kK]?)',  # limit: 88k
        r'\border\s*[:-]?\s*(\d+(?:,\d+)*(?:\.\d+)?[kK]?)'  # order: 88k
    ]
    
    for pattern in entry_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            entry_price = match.group(1)
            # Remove commas from numbers like 1,000
            entry_price = entry_price.replace(',', '')
            limit_order = entry_price
            break
    
    # Extract multiple take profit targets
    take_profit_dict = {}
    take_profit = None
    
    logger.info("Searching for take profit targets...")
    
    # First look for specific TP1, TP2, TP3 format - use a stronger pattern with word boundaries
    tp_numbered_pattern = r'\b(?:tp|take profit|target|t\.p\.)\s*(\d+)\s*(?:is|are|at|@|:|=|\s+)?\s*(\d+(?:,\d+)*(?:\.\d+)?[kK]?)'
    logger.debug(f"Using TP numbered pattern: {tp_numbered_pattern}")
    
    # Find all matches in the text - allows for finding multiple TP targets
    for match in re.finditer(tp_numbered_pattern, text, re.IGNORECASE):
        tp_number = int(match.group(1))
        tp_value = match.group(2).replace(',', '')
        take_profit_dict[tp_number] = tp_value
        logger.info(f"Found TP{tp_number}: {tp_value} using numbered pattern")
    
    # Look for multiple take profits in other formats
    tp_patterns = [
        # Main TP/target patterns
        r'(?:tp|take profit|target|t\.p\.|price target)\s*(?:is|are|at|@|:|=)?\s*(\d+(?:,\d+)*(?:\.\d+)?[kK]?)',  # tp: 146k, target: 146k, tp is 146k
        r'(?:tp|take profit|target|t\.p\.)[^0-9]*(\d+(?:,\d+)*(?:\.\d+)?[kK]?)',  # tp at 146k, target 146k
        r'(?:to reach|reach)[^0-9]*(\d+(?:,\d+)*(?:\.\d+)?[kK]?)',  # to reach 85k
        
        # Common variations
        r'\btp\b\s*(\d+(?:,\d+)*(?:\.\d+)?[kK]?)',  # tp 146k
        r'\btarget\b\s*(\d+(?:,\d+)*(?:\.\d+)?[kK]?)',  # target 146k
        r'\btarget price\b\s*[:-]?\s*(\d+(?:,\d+)*(?:\.\d+)?[kK]?)',  # target price: 146k
    ]
    
    for pattern in tp_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            take_profit = match.group(1).replace(',', '')
            logger.info(f"Found general take profit: {take_profit} using pattern: {pattern}")
            # If we found a general TP and don't already have a TP1, save it as TP1
            if 1 not in take_profit_dict:
                take_profit_dict[1] = take_profit
                logger.info(f"Setting TP1 to {take_profit} from general take profit")
            break
    
    # If we found multiple TPs, use the first one as the primary TP
    if take_profit_dict:
        sorted_tps = sorted(take_profit_dict.items())
        if sorted_tps:
            take_profit = sorted_tps[0][1]
            logger.debug(f"Found multiple TPs: {take_profit_dict}, using {take_profit} as primary")
    
    # Extract stop loss
    stop_loss = None
    logger.info("Searching for stop loss...")
    
    sl_patterns = [
        # Common SL formats
        r'\b(?:sl|stop loss|stop|s\.l\.)\s*(?:is|are|at|@|:|=)?\s*(\d+(?:,\d+)*(?:\.\d+)?[kK]?)',  # sl: 75k, sl is 75k
        r'\b(?:sl|stop loss|stop|s\.l\.)[^0-9]*(\d+(?:,\d+)*(?:\.\d+)?[kK]?)',  # sl at 75k, stop loss at 75k
        
        # Additional formats
        r'\bstoploss\s*(?:is|at|:|=)?\s*(\d+(?:,\d+)*(?:\.\d+)?[kK]?)',  # stoploss: 75k
        r'\b(?:cut loss|exit if)\s*(?:at|below|above)?\s*(\d+(?:,\d+)*(?:\.\d+)?[kK]?)',  # cut loss at 75k, exit if below 75k
    ]
    
    for pattern in sl_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            stop_loss = match.group(1).replace(',', '')
            logger.info(f"Found stop loss: {stop_loss} using pattern: {pattern}")
            break
    
    if not stop_loss:
        logger.info("No explicit stop loss found in text")
    
    # Extract timeframe from words or context
    timeframe = None
    
    # First use specific timeframe-related terms that won't be confused with position
    timeframe_patterns = {
        "SHORT": [
            r'\b(short[\s-]?term|hourly|hour[s]?|short[\s-]?frame|day|daily|intraday|scalp|scalping|quick|1h|4h)\b',
            r'\btimeframe[\s-:]+short\b',
            r'\bshort[\s-]?timeframe\b'
        ],
        "MID": [
            r'\b(mid[\s-]?term|weekly|week[s]?|medium[\s-]?term|swing|1d|mid[\s-]?timeframe)\b',
            r'\btimeframe[\s-:]+mid\b',
            r'\bmid[\s-]?timeframe\b'
        ],
        "LONG": [
            r'\b(long[\s-]?term|month|monthly|year|yearly|hodl|holding|investment|long[\s-]?timeframe)\b',
            r'\btimeframe[\s-:]+long\b',
            r'\blong[\s-]?timeframe\b'
        ]
    }
    
    # Check each pattern
    for tf, patterns in timeframe_patterns.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                timeframe = tf
                logger.info(f"Found timeframe {timeframe} using pattern: {pattern}")
                break
        if timeframe:
            break
            
    # Don't use the exact word fallback, as it can confuse with position
    # Instead, set a default based on signal characteristics
    if not timeframe:
        # Set default timeframe if none is detected
        # Determine default timeframe based on signal characteristics
        # Short positions usually have shorter timeframes
        if position and position.lower() == "short":
            timeframe = "SHORT"
            logger.info(f"No explicit timeframe found, defaulting to SHORT based on short position")
        # If we have a very high take profit target compared to entry, likely longer timeframe
        elif take_profit and entry_price and parse_price(take_profit) > parse_price(entry_price) * 1.5:
            timeframe = "LONG"
            logger.info(f"No explicit timeframe found, defaulting to LONG based on high take profit target")
        else:
            # Default to MID if we can't determine
            timeframe = "MID"
            logger.info(f"No explicit timeframe found, defaulting to MID as fallback")
    
    # Extract risk level from various wordings
    risk_level = None
    if re.search(r'\b(low[- ]?risk|safe|conservative|small risk|minimal risk)\b', text, re.IGNORECASE):
        risk_level = "LOW"
    elif re.search(r'\b(medium[- ]?risk|moderate|mid[- ]?risk|average risk|balanced)\b', text, re.IGNORECASE):
        risk_level = "MEDIUM"
    elif re.search(r'\b(high[- ]?risk|risky|aggressive|speculative|yolo|dangerous)\b', text, re.IGNORECASE):
        risk_level = "HIGH"
    
    # Fallback: If a timeframe/risk level is not specified in context words,
    # check for the exact words SHORT, MID, LONG, LOW, MEDIUM, HIGH in the message
    if not risk_level:
        for risk in RISK_LEVELS:
            if risk in text.upper():
                risk_level = risk
                break
    
    # Set default risk level if none is detected
    if not risk_level:
        # Determine default risk level based on signal characteristics
        # Determine risk by comparing stop loss to entry (larger distance = lower risk)
        if stop_loss and entry_price:
            entry = parse_price(entry_price)
            sl = parse_price(stop_loss)
            
            # Calculate stop loss percentage
            if position and position.lower() == "long":
                if entry > 0:
                    sl_pct = (entry - sl) / entry * 100
                    if sl_pct <= 3:  # Low risk: tight stop loss (3% or less)
                        risk_level = "LOW"
                    elif sl_pct <= 10:  # Medium risk: moderate stop loss (3-10%)
                        risk_level = "MEDIUM"
                    else:  # High risk: wide stop loss (>10%)
                        risk_level = "HIGH"
            else:  # Short position
                if entry > 0:
                    sl_pct = (sl - entry) / entry * 100
                    if sl_pct <= 3:
                        risk_level = "LOW"
                    elif sl_pct <= 10:
                        risk_level = "MEDIUM"
                    else:
                        risk_level = "HIGH"
        
        # If we still don't have a risk level, set based on timeframe
        if not risk_level:
            if timeframe == "SHORT":
                risk_level = "MEDIUM"  # Short timeframe usually medium risk
            elif timeframe == "LONG":
                risk_level = "LOW"  # Longer timeframe usually lower risk
            else:
                risk_level = "MEDIUM"  # Default to medium risk
        
        logger.debug(f"No risk level found in text, defaulting to {risk_level}")
    
    # Store all extracted data for easy access and extension
    extracted_data = {
        "coin": coin,
        "position": position,
        "entry_price": entry_price,
        "take_profit": take_profit,
        "take_profit_targets": take_profit_dict,
        "stop_loss": stop_loss,
        "timeframe": timeframe,
        "risk_level": risk_level
    }
    
    return coin, timeframe, risk_level, limit_order, take_profit, position, stop_loss, extracted_data 