# Migration Guide: From Monolithic to Modular Structure

This guide explains how to migrate from the original monolithic `bot.py` file to the new modular structure.

## Why Refactor?

The original `bot.py` file had grown to nearly 2000 lines, making it difficult to maintain and extend. The refactored structure offers several benefits:

1. **Better organization**: Code is grouped by functionality
2. **Improved maintainability**: Easier to find and fix bugs
3. **Enhanced readability**: Smaller files are easier to understand
4. **Easier collaboration**: Multiple developers can work on different modules
5. **Simplified testing**: Modules can be tested independently

## Migration Steps

### 1. Create Directory Structure

```bash
mkdir -p src/handlers src/services src/utils
touch src/__init__.py src/handlers/__init__.py src/services/__init__.py src/utils/__init__.py
```

### 2. Move Configuration and Constants

Create `src/config.py` and move all constants, global variables, and configuration from the top of `bot.py`.

### 3. Move Data Handling Functions

Create `src/services/data_handlers.py` and move functions like:
- `save_user_data()`
- `save_signals_data()`
- `save_coins_data()`

### 4. Move Price Service Functions

Create `src/services/price_service.py` and move functions like:
- `parse_price()`
- `get_crypto_price()`
- `get_historical_price()`

### 5. Move Signal Processing Functions

Create `src/services/signal_processor.py` and move functions like:
- `check_signal_performance()`
- `update_all_signals_performance()`
- `extract_signal_data()`

### 6. Move Command Handlers

Create `src/handlers/command_handlers.py` and move all command handler functions like:
- `start()`
- `help_command()`
- `subscribe()`
- etc.

### 7. Move Callback Handlers

Create `src/handlers/callback_handlers.py` and move callback handler functions like:
- `button_callback()`
- `handle_performance_callback()`

### 8. Move Message Handlers

Create `src/handlers/message_handlers.py` and move message handling functions like:
- `handle_message()`

### 9. Move Job Queue Functions

Create `src/services/job_queue.py` and move periodic task functions like:
- `periodic_signal_check()`
- Add a `setup_jobs()` function

### 10. Create Main Entry Point

Create `main.py` in the root directory to initialize the bot and register all handlers.

## Import Adjustments

When moving functions to different files, you'll need to update imports. For example:

```python
# In src/services/signal_processor.py
from src.config import PENDING, HIT_TARGET, HIT_STOPLOSS, EXPIRED
from src.services.price_service import get_crypto_price, parse_price
from src.services.data_handlers import save_signals_data
```

## Running the New Structure

After completing the migration, you can run the bot with:

```bash
python main.py
```

## Troubleshooting

If you encounter import errors or missing functions, check:

1. That all necessary imports are included in each file
2. That function names are consistent across files
3. That circular imports are avoided
4. That the correct paths are used in imports

## Future Improvements

With the new modular structure, you can more easily:

1. Add new commands without cluttering the main file
2. Implement unit tests for individual modules
3. Add new features in a more organized way
4. Refactor specific parts without affecting the whole system 