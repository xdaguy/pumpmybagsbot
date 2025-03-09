# PumpMyBagsBot Project Information

## Project Overview
PumpMyBagsBot is a Telegram bot designed to help cryptocurrency traders track and evaluate trading signals. The bot can parse natural language trading signals, track their performance over time, and notify users when targets are hit or stop losses are triggered. It also tracks the performance of signal providers and allows users to customize their notification preferences.

## Core Features

### 1. Natural Language Signal Processing
- Users can tag the bot (@pumpmybagsbot) or use the `/s` command to share trading signals
- The bot parses natural language text to extract:
  - Coin symbol (BTC, ETH, etc.)
  - Position (long/short)
  - Entry price/limit order
  - Multiple take profit targets (TP1, TP2, etc.)
  - Stop loss
  - Risk level (low/medium/high)
  - Timeframe (short/mid/long)

Example signals:
```
@pumpmybagsbot short btc at 85k, tp1 is 84k, tp2 is 83k, risk is low.
/s long eth at 2210, tp is 2500, high risk, long frame
```

### 2. Signal Tracking & Performance Monitoring
- Track each signal's performance over time
- Check if targets are hit or stop losses are triggered using current market prices
- Set expiration based on timeframe (short/mid/long)
- Send notifications when signals reach targets or stop losses
- Clearly indicate which take profit target was hit (TP1, TP2, etc.)
- Calculate performance percentages for each signal

### 3. Signal Provider Performance Tracking
- Track success rates for each signal provider
- Calculate statistics (win rate, average profit, etc.)
- Rate providers based on their historical performance
- Display performance data via `/stat` command
- Track performance by timeframe and risk level

### 4. User Preferences & Notifications
- Allow users to subscribe/unsubscribe from the bot
- Configure notification preferences (all signals, favorites only)
- Filter signals by risk level or timeframe
- Save favorite coins for targeted notifications
- Manage settings via `/settings` command

### 5. Price Service
- Fetch cryptocurrency prices from external APIs
- Cache prices to avoid excessive API calls
- Parse price formats (e.g., "85k" to 85000)
- Handle price history for performance evaluation

## Project Structure

```
pumpmybagsbot/
├── main.py                    # Entry point for the bot
├── requirements.txt           # Project dependencies
├── .env                       # Environment variables (BOT_TOKEN, etc.)
├── src/
│   ├── config.py              # Configuration, constants, and shared variables
│   │   └── signal_processor.py # Core signal parsing and evaluation logic
│   ├── handlers/
│   │   ├── command_handlers.py # Handle bot commands (/start, /help, etc.)
│   │   ├── message_handlers.py # Handle user messages and signal parsing
│   │   └── callback_handlers.py # Handle button callbacks
│   └── utils/                 # Utility functions
└── data/                      # Stored data (signals, user preferences, etc.)
    ├── user_data.json         # User subscription status and preferences
    ├── signals_data.json      # Tracked signals and their performance
    └── coins_data.json        # Information about tracked coins
```

## Key Components and Their Functions

### 1. Signal Processing
The `extract_signal_data` function in `signal_processor.py` is the core component that parses natural language text to extract trading signal parameters. It uses regex patterns to identify:
- Coin symbols (with or without $ prefix)
- Position (long/short)
- Entry prices (various formats including k notation)
- Take profit targets (multiple TPs with different formats)
- Stop loss values
- Risk levels (from explicit mentions or context)
- Timeframes (from explicit mentions or context)

### 2. Performance Tracking
The `check_signal_performance` function in `signal_processor.py` evaluates signals by:
- Fetching current prices for the coin
- Comparing against entry price, take profit targets, and stop loss
- Determining if a target has been hit or stop loss triggered
- Calculating performance percentages
- Updating signal status (PENDING, HIT_TARGET, HIT_STOPLOSS, EXPIRED)
- Tracking which specific take profit target was hit (for multiple TPs)

### 3. Job Queue
The `periodic_signal_check` function in `job_queue.py` runs periodically to:
- Check the performance of all pending signals
- Send notifications to users when signals complete
- Format notifications to show which take profit target was hit
- Apply user preferences for notifications

### 4. User Settings
User settings are managed through:
- `/settings` command which displays an interactive keyboard
- Callback handlers that process user preference changes
- Settings dictionary stored in user_data.json with options for:
  - notify_all_signals: Whether to notify for all signals
  - notify_favorites_only: Whether to notify only for favorite coins
  - risk_filter: Filter by risk level (LOW, MEDIUM, HIGH, ALL)
  - timeframe_filter: Filter by timeframe (SHORT, MID, LONG, ALL)

### 5. Statistics and Performance
The `/stat` command displays:
- Total number of signals tracked
- Success rates and performance metrics
- Breakdown by timeframe and risk level
- Number of unique coins tracked
- Number of subscribers

## Implementation Details

### Constants
Key constants defined in `config.py`:
- `PENDING`, `HIT_TARGET`, `HIT_STOPLOSS`, `EXPIRED`: Signal status values
- `TIMEFRAMES`: List of valid timeframes (SHORT, MID, LONG)
- `RISK_LEVELS`: List of valid risk levels (LOW, MEDIUM, HIGH)
- `TIMEFRAME_DURATIONS`: Mapping of timeframes to durations in days

### Data Storage
Data is stored in JSON files:
- `user_data.json`: Stores user subscriptions and preferences
- `signals_data.json`: Stores all signals and their performance
- `coins_data.json`: Stores information about tracked coins

### Price Handling
- Prices are fetched from cryptocurrency APIs
- A cache system avoids excessive API calls (5-minute expiry)
- The `parse_price` function handles various price formats (e.g., "85k" to 85000)

### Critical Components for Multiple Take Profit Targets
1. **Parsing Multiple TPs**:
   ```python
   # First look for specific TP1, TP2, TP3 format
   tp_numbered_pattern = r'(?:tp|take profit|target|t\.p\.|tp target)\s*(\d+)\s*[:-]?\s*(\d+(?:,\d+)*(?:\.\d+)?[kK]?)'
   for match in re.finditer(tp_numbered_pattern, text, re.IGNORECASE):
       tp_number = int(match.group(1))
       tp_value = match.group(2).replace(',', '')
       take_profit_dict[tp_number] = tp_value
   ```

2. **Checking which TP is Hit**:
   ```python
   # For long positions
   if position.lower() == "long":
       # Sort TP targets from lowest to highest (for long positions we hit the closest ones first)
       hit_tp = None
       hit_tp_num = None
       if tp_targets:
           for tp_num, tp_price in sorted(tp_targets.items(), key=lambda x: x[1]):
               if current_price >= tp_price:
                   hit_tp = tp_price
                   hit_tp_num = tp_num
                   break
       
       if hit_tp:
           signal["status"] = HIT_TARGET
           signal["hit_tp"] = hit_tp_num
           signal["performance"] = ((hit_tp - entry_price) / entry_price) * 100
           signal["exit_price"] = hit_tp
   ```

3. **Displaying Hit TP in Notification**:
   ```python
   # Enhance message to show which take profit target was hit
   hit_tp_info = ""
   if status == HIT_TARGET and "hit_tp" in signal:
       tp_num = signal['hit_tp']
       tp_price = signal.get('exit_price', 0)
       hit_tp_info = f"\n*Hit Take Profit:* TP{tp_num} at ${tp_price:,.2f}"
   
   # Check for multiple take profit targets to display
   tp_targets_info = ""
   if "take_profit_targets" in signal and signal["take_profit_targets"] and len(signal["take_profit_targets"]) > 1:
       tp_targets_info = "\n*Take Profit Targets:*"
       for tp_num, tp_val in sorted(signal["take_profit_targets"].items()):
           # Mark the hit TP with a checkmark
           hit_marker = "✅ " if status == HIT_TARGET and "hit_tp" in signal and int(tp_num) == signal['hit_tp'] else ""
           # Parse the price value before displaying
           formatted_val = f"${parse_price(tp_val):,.2f}"
           tp_targets_info += f"\n• {hit_marker}TP{tp_num}: {formatted_val}"
   ```

## Common Issues and Solutions

### 1. Natural Language Parsing
**Issue**: Different users express signals in various formats.
**Solution**: Use multiple regex patterns for each parameter, from specific to general, with fallbacks for common variations.

### 2. Take Profit Display
**Issue**: Raw values displayed instead of formatted prices.
**Solution**: Always parse price values before displaying them in notifications:
```python
formatted_val = f"${parse_price(tp_val):,.2f}"
```

### 3. Multiple Take Profit Targets
**Issue**: Inconsistent handling of which TP was hit.
**Solution**: Sort TPs appropriately (ascending for long, descending for short) and store the hit TP number in the signal data.

### 4. Price Fetching Delays
**Issue**: Slow response time due to API calls.
**Solution**: Implement price caching with a 5-minute expiry to reduce API calls.

## Future Enhancements
1. Support for more complex signal parameters (trailing stop loss, DCA levels)
2. Enhanced statistics and visualizations for signal provider performance
3. Integration with more price APIs for better reliability
4. User interface improvements for settings and statistics
5. Support for more cryptocurrencies and trading pairs

## Development Guidelines
1. Always parse and format prices consistently
2. Handle edge cases in natural language parsing
3. Ensure clear notification messages that indicate exactly which TP was hit
4. Maintain a modular codebase with clear separation of concerns
5. Log important events for debugging and monitoring 