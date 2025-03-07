# Pump My Bags Bot - Refactored Structure

This document explains the refactored structure of the Pump My Bags Bot codebase. The original monolithic `bot.py` file has been split into multiple modules for better maintainability and readability.

## Directory Structure

```
pumpmybagsbot/
├── main.py                  # Entry point for the bot
├── src/                     # Source code directory
│   ├── __init__.py          # Makes src a Python package
│   ├── config.py            # Configuration, constants, and data loading
│   ├── handlers/            # Command and callback handlers
│   │   ├── __init__.py
│   │   ├── command_handlers.py  # Bot command handlers
│   │   ├── callback_handlers.py # Button callback handlers
│   │   └── message_handlers.py  # Message handling
│   ├── services/            # Core services
│   │   ├── __init__.py
│   │   ├── data_handlers.py     # Data saving/loading
│   │   ├── price_service.py     # Cryptocurrency price services
│   │   ├── signal_processor.py  # Signal processing and analysis
│   │   └── job_queue.py         # Periodic tasks
│   └── utils/               # Utility functions
│       └── __init__.py
├── signals.json             # Signal data storage
├── user_data.json           # User data storage
├── coins.json               # Coin data storage
└── .env                     # Environment variables
```

## Module Descriptions

### Main Files

- **main.py**: The entry point for the bot. Sets up command handlers, callback handlers, and starts the bot.

### Configuration

- **src/config.py**: Contains configuration variables, constants, and data loading functions.

### Handlers

- **src/handlers/command_handlers.py**: Contains all command handlers for the bot (e.g., /start, /help, /signals).
- **src/handlers/callback_handlers.py**: Contains handlers for button callbacks and interactive features.
- **src/handlers/message_handlers.py**: Contains the handler for processing messages in groups.

### Services

- **src/services/data_handlers.py**: Functions for saving and loading data from JSON files.
- **src/services/price_service.py**: Functions for retrieving cryptocurrency prices.
- **src/services/signal_processor.py**: Functions for processing signals, extracting data, and checking performance.
- **src/services/job_queue.py**: Periodic tasks for checking signal performance.

## Running the Bot

To run the bot, simply execute:

```bash
python main.py
```

Make sure you have all the required dependencies installed:

```bash
pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file with the following variables:

```
BOT_TOKEN=your_telegram_bot_token
```

## Data Files

- **signals.json**: Stores all trading signals.
- **user_data.json**: Stores user information, subscriptions, and settings.
- **coins.json**: Stores information about tracked coins.

## Features

- Signal forwarding from groups to subscribers
- Performance tracking for signals
- User notification preferences
- Favorite coins management
- Signal voting system
- Performance statistics by trader, coin, and timeframe
- Customizable notification settings 