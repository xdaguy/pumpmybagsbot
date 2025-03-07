# Pump My Bags Bot

A Telegram bot that forwards crypto trading signals to subscribers when tagged in a group chat, with advanced features for tracking coins, analyzing performance, and more.

## Features

- 📢 **Signal Forwarding**: Automatically forwards tagged trading signals to all subscribers
- 💰 **Price Checking**: Get real-time cryptocurrency prices with the `/price` command
- ⏱️ **Signal Timeframes**: Support for SHORT, MID, and LONG timeframe classifications
- ⚠️ **Risk Levels**: Categorize signals by LOW, MEDIUM, or HIGH risk
- 👍 **Voting System**: Users can upvote or downvote signals to rate their quality
- 📊 **Performance Tracking**: Track signal performance and view statistics by coin
- ⭐ **Favorite Coins**: Users can track their favorite coins and get highlighted notifications
- 🔍 **Coin Detection**: Automatically detects coin symbols in signals (format: $BTC)
- 💎 **Coin Database**: Maintains a database of all coins mentioned in signals

## Setup Instructions

### 1. Prerequisites

- Python 3.7 or higher
- A Telegram account
- Server for hosting the bot

### 2. Create a Bot on Telegram

1. Open Telegram and search for `@BotFather`
2. Start a chat with BotFather and send `/newbot`
3. Follow the instructions to create a new bot
4. Note down the HTTP API token provided by BotFather

### 3. Install Dependencies

```bash
# Clone the repository
git clone <your-repository-url>
cd pumpmybagsbot

# Install required packages
pip install -r requirements.txt
```

### 4. Configuration

1. Create a `.env` file in the project directory
2. Add your bot token to the `.env` file:
```
BOT_TOKEN=your_bot_token_here
```

### 5. Start the Bot

```bash
python bot.py
```

## Usage

### Bot Commands

- `/start` - Start the bot and subscribe to signals
- `/help` - Display help information
- `/subscribe` - Subscribe to crypto signals
- `/unsubscribe` - Unsubscribe from crypto signals
- `/signals` - View recent trading signals
- `/price [symbol]` - Check current price of a cryptocurrency
- `/coins [symbol]` - Track your favorite coins
- `/performance` - View signal performance statistics

### How to Use in Groups

1. Add the bot to your Telegram group
2. When posting a trading signal, tag the bot with the following format:
   ```
   @YourBotUsername $BTC SHORT HIGH Buy BTC at 80K, target 100K 🚀
   ```
   Where:
   - `$BTC` is the coin symbol (required for auto-detection)
   - `SHORT/MID/LONG` indicates the timeframe (optional)
   - `LOW/MEDIUM/HIGH` indicates the risk level (optional)

3. The bot will forward this signal to all subscribers and track its performance
4. Users can vote on signals with the 👍 and 👎 buttons

### Favorite Coins Feature

1. Use `/coins BTC` to add Bitcoin to your favorites
2. Use `/coins` to view all your favorites with current prices
3. When a signal mentions one of your favorite coins, you'll receive an additional notification
4. Manage your favorite coins list with the provided buttons

## Running on a Server

For the bot to work continuously, you need to run it on a server. Here are some options:

- Use a simple systemd service on Linux
- Use screen or tmux to keep the process running
- Set up a Docker container

Example systemd service file (`/etc/systemd/system/pumpbags.service`):

```
[Unit]
Description=Pump My Bags Telegram Bot
After=network.target

[Service]
User=yourusername
WorkingDirectory=/path/to/pumpmybagsbot
ExecStart=/usr/bin/python3 /path/to/pumpmybagsbot/bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

To set up as a service:
```bash
sudo systemctl enable pumpbags.service
sudo systemctl start pumpbags.service
sudo systemctl status pumpbags.service
```

## Data Storag

The bot stores data in three JSON files:
- `user_data.json`: Stores user information and favorite coins
- `signals.json`: Stores all signals with their voting history
- `coins.json`: Tracks all coins mentioned in signals and their statistics

## Disclaimer

This bot is for educational purposes only. Cryptocurrency trading involves substantial risk of loss and is not suitable for all investors. Always do your own research before making any investment decisions. 