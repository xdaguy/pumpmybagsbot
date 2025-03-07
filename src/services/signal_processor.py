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
    
    # Default stop loss (20% in opposite direction of trade)
    position = signal.get("position", "Long")
    stop_loss_pct = 0.2  # 20% default stop loss
    
    if entry_price:
        if position.lower() == "long":
            # For long positions, stop loss is below entry price
            stop_loss = entry_price * (1 - stop_loss_pct)
            # Check if target hit (price went up to target)
            if target_price and current_price >= target_price:
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
            # For short positions, stop loss is above entry price
            stop_loss = entry_price * (1 + stop_loss_pct)
            # Check if target hit (price went down to target)
            if target_price and current_price <= target_price:
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
        
        # Skip signals that are already completed
        if signal["status"] in [HIT_TARGET, HIT_STOPLOSS, EXPIRED]:
            continue
        
        # Check and update signal performance
        updated_signal = await check_signal_performance(signal)
        if updated_signal.get("status") != PENDING:
            updated = True
    
    if updated:
        await save_signals_data()
    
    return updated

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