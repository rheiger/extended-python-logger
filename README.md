### 1. The Generic Logging Script

The script has been updated to remove all references to `EventIQ`. The environment variable prefix has been changed to `PYTHON_LOG_` for consistency, and more configuration options (like file path and rotation settings) are now exposed as environment variables. The default log file path is now in the current directory to avoid permission issues.

**File: `enhanced_logging.py`**
```python
"""
Enhanced and generic logging configuration module for Python applications.

This module provides a centralized and powerful way to configure logging.
It is designed to be a drop-in utility for any Python project, offering
features like environment variable configuration, custom log levels (TRACE and NOTICE),
module-specific log levels, automatic log rotation, and inclusion of caller info.

Example usage in your Python script:
------------------------------------

# 1. Import the logger utility
from enhanced_logging import get_logger, configure_logging

# 2. (Optional) Programmatically configure logging upon application startup.
#    If not called, logging is configured automatically on the first call
#    to get_logger() using environment variables or sane defaults.
#
# configure_logging(
#     level="INFO",                # Console log level
#     file_level="DEBUG",          # File log level
#     console_format="DETAILED",   # Console format
#     enable_file_logging=True     # Enable logging to file with rotation
# )

# 3. Get a logger instance for your current module
logger = get_logger(__name__)

# 4. Use the logger with standard and custom levels
logger.trace("This is for highly detailed diagnostic information.")
logger.debug("Standard debugging information.")
logger.info("An informational message.")
logger.notice("A noteworthy event occurred, but it isn't a warning.")
logger.warning("Something unexpected happened that might need attention.")
logger.error("An error occurred that prevented a function from completing.")
logger.critical("A critical error that might cause the application to terminate.")

Main features:
--------------
- Custom Log Levels: Adds TRACE (level 5) and NOTICE (level 25) for more
  granular logging.
- Environment Variable Control: Almost every aspect can be configured using
  environment variables with the prefix `PYTHON_LOG_`.
- Module-Specific Levels: Set different log levels for different parts of your
  application (e.g., `PYTHON_LOG_LEVEL_MYAPP_DATABASE=DEBUG`).
- Rich Formatting: Includes SIMPLE, DETAILED, and EXTENDED formats out of the box,
  which can show caller function and line number.
- Level-Based Formatting: Automatically use more detailed formats for error
  and critical messages.
- Log Rotation: Built-in support for rotating log files based on size.
- Dynamic Configuration: Change log levels at runtime without restarting the
  application.
"""

import os
import logging
import sys
import inspect
from logging.handlers import RotatingFileHandler
from typing import Dict, Optional, Any, cast, Mapping, Union

# Define custom log levels
TRACE = 5  # Lower than DEBUG
NOTICE = 25  # Between INFO and WARNING

# Register custom levels with the logging module
logging.addLevelName(TRACE, "TRACE")
setattr(logging, 'TRACE', TRACE)
logging.addLevelName(NOTICE, "NOTICE")
setattr(logging, 'NOTICE', NOTICE)

def trace(self, message, *args, **kwargs):
    """Log a message with severity 'TRACE' on this logger."""
    if self.isEnabledFor(TRACE):
        self._log(TRACE, message, args, **kwargs)

def notice(self, message, *args, **kwargs):
    """Log a message with severity 'NOTICE' on this logger."""
    if self.isEnabledFor(NOTICE):
        self._log(NOTICE, message, args, **kwargs)

# Add methods to the Logger class
logging.Logger.trace = trace
logging.Logger.notice = notice


# --- Environment Variable Naming Scheme ---
ENV_PREFIX = "PYTHON_LOG_"

# General settings
LOG_LEVEL_ENV_VAR = f"{ENV_PREFIX}LEVEL"
MODULE_LOG_LEVEL_PREFIX = f"{ENV_PREFIX}LEVEL_"

# Console handler settings
CONSOLE_FORMAT_ENV_VAR = f"{ENV_PREFIX}CONSOLE_FORMAT"

# File handler settings
FILE_LOGGING_ENV_VAR = f"{ENV_PREFIX}FILE_ENABLED"
FILE_LEVEL_ENV_VAR = f"{ENV_PREFIX}FILE_LEVEL"
FILE_FORMAT_ENV_VAR = f"{ENV_PREFIX}FILE_FORMAT"
FILE_PATH_ENV_VAR = f"{ENV_PREFIX}FILE_PATH"
FILE_MAX_SIZE_ENV_VAR = f"{ENV_PREFIX}FILE_MAX_BYTES"
FILE_BACKUP_COUNT_ENV_VAR = f"{ENV_PREFIX}FILE_BACKUP_COUNT"
ROTATE_ON_STARTUP_ENV_VAR = f"{ENV_PREFIX}ROTATE_ON_STARTUP"


# --- Default Configuration Values ---
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_CONSOLE_FORMAT = "DETAILED"
DEFAULT_FILE_LOG_LEVEL = "DEBUG"
DEFAULT_FILE_FORMAT = "EXTENDED"
DEFAULT_LOG_FILE_PATH = 'app.log'
DEFAULT_LOG_FILE_MAX_SIZE = 10 * 1024 * 1024  # 10 MB
DEFAULT_LOG_FILE_BACKUP_COUNT = 5


# --- Log Formats ---
EXTENDED_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s:%(thread)d] - [%(funcName)s:%(lineno)d] - [%(caller_func)s:%(caller_line)d] - %(message)s'
DETAILED_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s'
STANDARD_LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
SIMPLE_LOG_FORMAT = '%(levelname)s: %(message)s'

# Default formats used when a specific format isn't requested
DEFAULT_FORMATS_BY_LEVEL = {
    TRACE: EXTENDED_LOG_FORMAT,
    logging.DEBUG: DETAILED_LOG_FORMAT,
    logging.INFO: STANDARD_LOG_FORMAT,
    NOTICE: STANDARD_LOG_FORMAT,
    logging.WARNING: DETAILED_LOG_FORMAT,
    logging.ERROR: EXTENDED_LOG_FORMAT,
    logging.CRITICAL: EXTENDED_LOG_FORMAT,
}

# Track if initialization has already happened
_initialized = False


class CallerInfoFilter(logging.Filter):
    """A logging filter that adds caller function information to log records."""

    def filter(self, record):
        """
        Adds 'caller_func' and 'caller_line' attributes to the log record.

        This inspects the call stack to find the frame that issued the logging
        call and extracts the function name and line number from it.
        """
        # Default values if caller info cannot be found
        record.caller_func = "unknown"
        record.caller_line = 0
        
        # The depth of the stack trace to find the original caller.
        # This may need adjustment if the logging infrastructure changes.
        # 0: this filter method
        # 1: logging.Handler.handle
        # 2: logging.Logger.callHandlers
        # 3: logging.Logger.handle
        # 4: logging.Logger._log
        # 5: logging.Logger.debug/info/etc. or our custom trace/notice
        # 6: The actual caller's frame
        stack_depth = 6
        
        current_frame = inspect.currentframe()
        if current_frame is None:
            return True
            
        try:
            frame = current_frame
            for _ in range(stack_depth):
                if frame is None:
                    break
                frame = frame.f_back

            if frame:
                record.caller_func = frame.f_code.co_name
                record.caller_line = frame.f_lineno
        finally:
            # Avoid reference cycles
            del current_frame
            del frame
            
        return True


class LevelBasedFormatter(logging.Formatter):
    """A formatter that uses different formats based on the log record's level."""

    def __init__(self, level_formats: Dict[int, str], default_fmt: Optional[str] = None):
        """
        Initializes the formatter.

        Args:
            level_formats: A dictionary mapping log levels (e.g., logging.INFO)
                           to format strings.
            default_fmt: The default format string to use if a level is not
                         found in level_formats. If None, a standard format is used.
        """
        super().__init__()
        if default_fmt is None:
            default_fmt = STANDARD_LOG_FORMAT
            
        self._formatters = {
            level: logging.Formatter(fmt) for level, fmt in level_formats.items()
        }
        self._default_formatter = logging.Formatter(default_fmt)

    def format(self, record: logging.LogRecord) -> str:
        """
        Formats the log record using the appropriate level-specific formatter.

        Args:
            record: The log record to format.

        Returns:
            The formatted log string.
        """
        formatter = self._formatters.get(record.levelno, self._default_formatter)
        return formatter.format(record)


def get_log_level(level_name: str) -> int:
    """
    Converts a log level name (string) to its corresponding integer value.

    Args:
        level_name: The name of the log level (e.g., "DEBUG", "TRACE").

    Returns:
        The integer value of the log level.
    """
    return {
        "TRACE": TRACE,
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "NOTICE": NOTICE,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }.get(level_name.upper(), logging.INFO)


def get_log_format_by_name(format_name: str) -> str:
    """
    Retrieves a format string based on a short name (e.g., "EXTENDED").

    Args:
        format_name: The short name of the format.

    Returns:
        The full log format string.
    """
    return {
        "SIMPLE": SIMPLE_LOG_FORMAT,
        "STANDARD": STANDARD_LOG_FORMAT,
        "DETAILED": DETAILED_LOG_FORMAT,
        "EXTENDED": EXTENDED_LOG_FORMAT,
    }.get(format_name.upper(), STANDARD_LOG_FORMAT)


def get_module_log_levels() -> Dict[str, int]:
    """
    Parses environment variables for module-specific log levels.

    Environment variables should be in the format:
    PYTHON_LOG_LEVEL_<MODULE_NAME>=<LEVEL>
    Example: PYTHON_LOG_LEVEL_MYAPP_API=DEBUG

    Returns:
        A dictionary mapping module names to log level integers.
    """
    module_levels = {}
    for key, value in os.environ.items():
        if key.startswith(MODULE_LOG_LEVEL_PREFIX):
            module_name = key[len(MODULE_LOG_LEVEL_PREFIX):].lower().replace("_", ".")
            module_levels[module_name] = get_log_level(value)
    return module_levels


def _str_to_bool(value: str) -> bool:
    """Helper to convert string representations of bool to a boolean value."""
    return value.lower() in ('true', '1', 'yes', 'y')


def configure_logging(
    level: Optional[str] = None,
    console_format: Optional[str] = None,
    enable_file_logging: Optional[bool] = None,
    file_level: Optional[str] = None,
    file_format: Optional[str] = None,
    file_path: Optional[str] = None,
    file_max_bytes: Optional[int] = None,
    file_backup_count: Optional[int] = None,
    rotate_on_startup: Optional[bool] = None
) -> None:
    """
    Configures the root logger for the application.

    This function is idempotent and will only configure logging once.
    Configuration is determined by parameters, falling back to environment
    variables, and finally to hardcoded defaults.

    Args:
        level: The default log level for the console handler.
        console_format: The format for the console handler ('SIMPLE', 'DETAILED', etc.).
        enable_file_logging: Whether to enable file logging.
        file_level: The log level for the file handler.
        file_format: The format for the file handler.
        file_path: The path to the log file.
        file_max_bytes: The maximum size of the log file before rotation.
        file_backup_count: The number of backup log files to keep.
        rotate_on_startup: If True, performs a log rotation when the app starts.
    """
    global _initialized
    if _initialized:
        logging.getLogger(__name__).debug("Logging already initialized, skipping configuration.")
        return

    # --- Determine Configuration from Args -> Env Vars -> Defaults ---
    console_level_str = level or os.getenv(LOG_LEVEL_ENV_VAR, DEFAULT_LOG_LEVEL)
    console_level = get_log_level(console_level_str)

    is_file_logging_enabled = enable_file_logging if enable_file_logging is not None else \
        _str_to_bool(os.getenv(FILE_LOGGING_ENV_VAR, 'True'))
    
    file_level_str = file_level or os.getenv(FILE_LEVEL_ENV_VAR, DEFAULT_FILE_LOG_LEVEL)
    file_log_level = get_log_level(file_level_str)

    # --- Configure Root Logger ---
    # Set root logger level to the most verbose of its handlers to capture all messages.
    root_logger = logging.getLogger()
    effective_root_level = min(console_level, file_log_level) if is_file_logging_enabled else console_level
    root_logger.setLevel(effective_root_level)

    # Clear any existing handlers to prevent duplicates
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # --- Configure Console Handler ---
    console_format_name = console_format or os.getenv(CONSOLE_FORMAT_ENV_VAR, DEFAULT_CONSOLE_FORMAT)
    console_format_str = get_log_format_by_name(console_format_name)
    
    # Create a level-based formatter for the console
    console_formats = DEFAULT_FORMATS_BY_LEVEL.copy()
    console_formats[logging.INFO] = console_format_str # Allow user to set standard INFO format
    console_formats[NOTICE] = console_format_str
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(LevelBasedFormatter(console_formats))

    # Add caller filter if any format requires it
    if "caller_func" in str(console_formats.values()):
        console_handler.addFilter(CallerInfoFilter())

    root_logger.addHandler(console_handler)

    # --- Configure File Handler ---
    if is_file_logging_enabled:
        log_path = file_path or os.getenv(FILE_PATH_ENV_VAR, DEFAULT_LOG_FILE_PATH)
        max_bytes = file_max_bytes or int(os.getenv(FILE_MAX_SIZE_ENV_VAR, DEFAULT_LOG_FILE_MAX_SIZE))
        backup_count = file_backup_count or int(os.getenv(FILE_BACKUP_COUNT_ENV_VAR, DEFAULT_LOG_FILE_BACKUP_COUNT))
        should_rotate = rotate_on_startup if rotate_on_startup is not None else \
            _str_to_bool(os.getenv(ROTATE_ON_STARTUP_ENV_VAR, 'False'))

        file_format_name = file_format or os.getenv(FILE_FORMAT_ENV_VAR, DEFAULT_FILE_FORMAT)
        file_format_str = get_log_format_by_name(file_format_name)

        try:
            log_dir = os.path.dirname(log_path)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            
            log_exists = os.path.exists(log_path)

            file_handler = RotatingFileHandler(
                log_path, maxBytes=max_bytes, backupCount=backup_count
            )
            
            if should_rotate and log_exists:
                file_handler.doRollover()

            file_handler.setLevel(file_log_level)
            
            # File logger typically uses a consistent, detailed format for all levels
            file_formatter = logging.Formatter(file_format_str)
            file_handler.setFormatter(file_formatter)

            if "caller_func" in file_format_str:
                file_handler.addFilter(CallerInfoFilter())
            
            root_logger.addHandler(file_handler)

        except (IOError, PermissionError) as e:
            root_logger.error(f"Failed to configure file logging at '{log_path}': {e}", exc_info=True)

    # --- Configure Module-Specific Levels ---
    module_levels = get_module_log_levels()
    for module_name, module_level in module_levels.items():
        logging.getLogger(module_name).setLevel(module_level)

    # --- Finalize ---
    _initialized = True
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured. Console level: {logging.getLevelName(console_level)}")
    if is_file_logging_enabled:
        logger.info(f"File logging enabled at '{log_path}', level: {logging.getLevelName(file_log_level)}")
    if module_levels:
        logger.info(f"Module-specific levels: {', '.join(f'{m}={logging.getLevelName(l)}' for m, l in module_levels.items())}")


def get_logger(name: str) -> logging.Logger:
    """
    Gets a logger instance by name.

    If logging has not been configured yet, this function will trigger the
    default configuration.

    Args:
        name: The name for the logger (typically __name__ from the calling module).

    Returns:
        A configured logger instance.
    """
    if not _initialized:
        configure_logging()
    return logging.getLogger(name)


def change_log_level(level: str, logger_name: Optional[str] = None) -> None:
    """
    Dynamically changes the log level of a specific logger and its handlers at runtime.

    Args:
        level: The new log level as a string (e.g., "DEBUG", "TRACE").
        logger_name: The name of the logger to modify. If None, modifies the root logger.
    """
    numeric_level = get_log_level(level)
    level_name = logging.getLevelName(numeric_level)
    
    logger_to_change = logging.getLogger(logger_name)
    logger_to_change.setLevel(numeric_level)

    for handler in logger_to_change.handlers:
        handler.setLevel(numeric_level)
        
    logging.getLogger(__name__).info(
        f"Log level for logger '{logger_to_change.name or 'root'}' "
        f"and its handlers changed to {level_name}."
    )
```

### 2. The `README.md` File

This README provides a comprehensive guide to using and configuring your new logging module.

---

# Enhanced Python Logging Module

A powerful, generic, and highly configurable logging utility for any Python application.

This module provides a centralized way to configure logging. It is designed to be a drop-in utility for any Python project, offering features like comprehensive environment variable configuration, custom log levels, module-specific log levels, automatic log rotation, and inclusion of detailed caller info.

## Features

-   **Custom Log Levels**: Adds `TRACE` (for extreme verbosity) and `NOTICE` (for important, non-warning events) to the standard log levels.
-   **Environment Variable Configuration**: Configure almost every aspect of logging through environment variables—no code changes needed to adjust logging in different environments (dev, staging, prod).
-   **Module-Specific Levels**: Easily set different log levels for different parts of your application to reduce noise and focus on specific areas during debugging.
-   **Automatic Caller Info**: The `EXTENDED` log format automatically includes the function name and line number of the code that issued the log message, making debugging much faster.
-   **Level-Based Formatting**: Automatically uses more detailed formats for `ERROR` and `CRITICAL` messages, providing more context when it matters most.
-   **Log Rotation**: Built-in support for rotating log files based on size, preventing log files from growing indefinitely.
-   **Runtime Log Level Changes**: Dynamically change the log level of any logger without restarting the application.

## Quick Start

1.  Save the code above as `enhanced_logging.py` in your project's utility directory.
2.  In any module, import and use the logger.

```python
# In your main application file (e.g., app.py)
from enhanced_logging import get_logger

# Get a logger for the current module
# This will automatically configure logging on its first call
logger = get_logger(__name__)

def my_function():
    logger.info("Starting my_function.")
    # Use custom levels for more context
    logger.trace("This is a very detailed trace message.")
    for i in range(3):
        logger.debug(f"Processing item {i+1}...")
    logger.notice("All items have been processed successfully.")
    logger.warning("The function completed, but one value was unexpected.")

my_function()
```

## Configuration

You can configure logging in two ways: via environment variables (recommended for flexibility) or programmatically.

### Via Environment Variables (Recommended)

This is the most flexible way to manage logging. Set these variables in your shell, `.env` file, or container environment.

#### General Settings

| Variable                      | Description                                                                                                                              | Default   |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | --------- |
| `PYTHON_LOG_LEVEL`            | The log level for the console output.                                                                                                    | `INFO`    |
| `PYTHON_LOG_LEVEL_<MODULE>` | Sets the log level for a specific module. Replace `<MODULE>` with the module path in uppercase, using underscores (e.g., `MYAPP_API_CLIENTS`). | (none)    |

*Example of a module-specific level:*
`export PYTHON_LOG_LEVEL_MYAPP_DATABASE=DEBUG` will set the logger for the `myapp.database` module to `DEBUG` level.

#### Console Logging

| Variable                 | Description                                                               | Default    |
| ------------------------ | ------------------------------------------------------------------------- | ---------- |
| `PYTHON_LOG_CONSOLE_FORMAT` | The format for console logs: `SIMPLE`, `STANDARD`, `DETAILED`, `EXTENDED`. | `DETAILED` |

#### File Logging

| Variable                      | Description                                                        | Default                |
| ----------------------------- | ------------------------------------------------------------------ | ---------------------- |
| `PYTHON_LOG_FILE_ENABLED`     | Set to `true` or `false` to enable/disable logging to a file.      | `true`                 |
| `PYTHON_LOG_FILE_LEVEL`       | The log level for the file output.                                 | `DEBUG`                |
| `PYTHON_LOG_FILE_FORMAT`      | The format for file logs: `SIMPLE`, `STANDARD`, `DETAILED`, `EXTENDED`. | `EXTENDED`             |
| `PYTHON_LOG_FILE_PATH`        | The full path to the log file.                                     | `app.log`              |
| `PYTHON_LOG_FILE_MAX_BYTES`   | Maximum file size in bytes before rotation.                        | `10485760` (10 MB)     |
| `PYTHON_LOG_FILE_BACKUP_COUNT`| Number of backup files to keep.                                    | `5`                    |
| `PYTHON_LOG_ROTATE_ON_STARTUP`| Set to `true` to rotate the log file every time the app starts.    | `false`                |

### Programmatic Configuration

You can call the `configure_logging()` function at the start of your application to set up logging in code. This is useful for projects where environment variable configuration is not ideal.

```python
from enhanced_logging import configure_logging, get_logger

# This is typically done once when your application starts
configure_logging(
    level="INFO",
    console_format="DETAILED",
    enable_file_logging=True,
    file_level="DEBUG",
    file_path="/var/log/my_app.log",
    file_max_bytes=5000000, # 5 MB
    file_backup_count=3,
    rotate_on_startup=True
)

logger = get_logger(__name__)
logger.info("Logging has been programmatically configured.")
```

## Advanced Usage

### Custom Log Levels

-   `logger.trace(msg)`: For extremely detailed, low-level information. More verbose than `DEBUG`.
-   `logger.notice(msg)`: For significant events that are part of normal operation but are worth noting. Sits between `INFO` and `WARNING`.

### Log Formats

You can choose from four built-in formats:

-   **SIMPLE**: `LEVELNAME: message`
-   **STANDARD**: `timestamp - LEVELNAME - logger_name - message`
-   **DETAILED**: `timestamp - logger_name - LEVELNAME - [function:lineno] - message`
-   **EXTENDED**: `timestamp - logger_name - LEVELNAME - [thread_info] - [function:lineno] - [caller_function:caller_lineno] - message`

The `EXTENDED` format is especially useful for debugging complex, multi-threaded applications, as it shows you exactly where a log message originated.

### Changing Log Levels at Runtime

You can change log levels on the fly, which is incredibly useful for debugging a running application without needing to restart it.

```python
from enhanced_logging import change_log_level, get_logger

logger = get_logger('my_app.feature')

# Initially, the level might be INFO
logger.debug("This message will not appear.")

# Now, let's change it
change_log_level("DEBUG", logger_name='my_app.feature')
logger.info("Log level for 'my_app.feature' was changed to DEBUG.")
logger.debug("This message will now appear!")
```
