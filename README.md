# PumpMyBagsBot

A Telegram bot for tracking cryptocurrency trading signals, monitoring their performance, and providing notifications when targets are hit.

## Features

- Parse natural language trading signals
- Track signal performance over time
- Multiple take profit targets support
- Signal provider performance tracking
- User notification preferences
- Interactive settings management
- Performance statistics and leaderboards

## Prerequisites

- Python 3.9 or higher
- A Telegram Bot Token (obtained from @BotFather)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/pumpmybagsbot.git
cd pumpmybagsbot
```

2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the root directory with your Telegram Bot Token:
```
BOT_TOKEN=your_telegram_bot_token_here
```

## Usage

1. Start the bot:
```bash
python main.py
```

2. Interact with the bot on Telegram using the following commands:
   - `/start` - Start the bot and see available commands
   - `/help` - Show help information
   - `/subscribe` - Subscribe to signal notifications
   - `/unsubscribe` - Unsubscribe from notifications
   - `/signals` - Show recent signals
   - `/price <coin>` - Check current price of a coin
   - `/coins` - View and manage your favorite coins
   - `/stat` - View signal statistics
   - `/settings` - Configure your notification preferences

3. Share trading signals by:
   - Tagging the bot: `@pumpmybagsbot short btc at 85k, tp1 is 84k, tp2 is 83k, risk is low.`
   - Using the `/s` command: `/s long eth at 2210, tp is 2500, high risk, long frame`

## Data Storage

The bot stores data in the `data/` directory:
- `user_data.json` - User subscriptions and preferences
- `signals_data.json` - Tracked signals and their performance
- `coins_data.json` - Information about tracked coins

## Project Structure

```
pumpmybagsbot/
├── main.py                    # Entry point for the bot
├── requirements.txt           # Project dependencies
├── .env                       # Environment variables (BOT_TOKEN, etc.)
├── src/
│   ├── config.py              # Configuration, constants, and shared variables
│   ├── services/
│   │   ├── data_handlers.py   # Functions for loading/saving data
│   │   ├── job_queue.py       # Periodic jobs for checking signal performance
│   │   ├── price_service.py   # Functions to fetch and parse cryptocurrency prices
│   │   └── signal_processor.py # Core signal parsing and evaluation logic
│   ├── handlers/
│   │   ├── command_handlers.py # Handle bot commands (/start, /help, etc.)
│   │   ├── message_handlers.py # Handle user messages and signal parsing
│   │   └── callback_handlers.py # Handle button callbacks
│   └── utils/                 # Utility functions
└── data/                      # Stored data (signals, user preferences, etc.)
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 