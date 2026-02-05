"""
Enhanced logging configuration module for AXPOC application.

This module provides a central place to configure logging for the application,
with support for environment variable configuration, module-specific log levels,
log rotation, and custom log levels.

Example usage in a Python script:

```python
# Import the custom logger
from src.utils.log_config import get_logger, configure_logging

# Optional: Configure logging with specific settings (usually done in app startup)
# configure_logging(
#     level="INFO",                # Console log level
#     file_level="DEBUG",          # File log level
#     use_extended_format=True,    # Enable thread ID and caller info
#     enable_file_logging=True     # Enable logging to file with rotation
# )

# Get a logger for your module
logger = get_logger(__name__)

# Now you can use all standard log levels plus custom levels
logger.trace("Very detailed debugging information")  # Most verbose
logger.debug("Standard debugging information")
logger.info("Informational message")
logger.notice("Important information that doesn't indicate a problem")
logger.warning("Warning message")
logger.error("Error message")
logger.critical("Critical error message")

# The trace() and notice() methods are automatically added to the logger
# Custom log levels are also available as logging.TRACE and logging.NOTICE
# No extra imports or configuration needed to use them
```

Environment variables:
- Set AXPOC_LOG_LEVEL to control the default log level (DEBUG, INFO, etc.)
- Set AXPOC_LOG_LEVEL_<MODULE> to control specific module's log level
  Example: AXPOC_LOG_LEVEL_SRC_SERVICES=DEBUG for src.services module
- Set AXPOC_CONSOLE_FORMAT to "SIMPLE", "DETAILED", or "EXTENDED" to control console format
- Set AXPOC_FILE_FORMAT to "SIMPLE", "DETAILED", or "EXTENDED" to control file format
"""

import datetime
import inspect
import logging
import logging.handlers
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Optional

# Define custom log levels
TRACE = 5  # Lower than DEBUG
logging.addLevelName(TRACE, "TRACE")
# Add TRACE attribute to the logging module
setattr(logging, "TRACE", TRACE)

# Define NOTICE level
NOTICE = 25  # Between INFO and WARNING
logging.addLevelName(NOTICE, "NOTICE")
# Add NOTICE attribute to the logging module
setattr(logging, "NOTICE", NOTICE)


class AXPOCLogger(logging.Logger):
    """Custom logger type exposing trace() and notice() for type checkers."""

    def trace(self, message: str, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("stacklevel", 2)
        if self.isEnabledFor(TRACE):
            self._log(TRACE, message, args, **kwargs)

    def notice(self, message: str, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("stacklevel", 2)
        if self.isEnabledFor(NOTICE):
            self._log(NOTICE, message, args, **kwargs)


# Register custom logger class so future getLogger() calls return AXPOCLogger
logging.setLoggerClass(AXPOCLogger)

# Default log level for the application
DEFAULT_LOG_LEVEL = "INFO"

# Environment variable that controls the global log level (console default)
LOG_LEVEL_ENV_VAR = "AXPOC_LOG_LEVEL"
# Explicit console/file level env vars
CONSOLE_LEVEL_ENV_VAR = "AXPOC_CONSOLE_LOG_LEVEL"
FILE_LEVEL_ENV_VAR = "AXPOC_FILE_LOG_LEVEL"

# Environment variable prefix for module-specific log levels
MODULE_LOG_LEVEL_PREFIX = "AXPOC_LOG_LEVEL_"

# Environment variables for formatting
CONSOLE_FORMAT_ENV_VAR = "AXPOC_CONSOLE_FORMAT"
FILE_FORMAT_ENV_VAR = "AXPOC_FILE_FORMAT"

# Default format types (default both to EXTENDED for all levels)
DEFAULT_CONSOLE_FORMAT = "EXTENDED"
DEFAULT_FILE_FORMAT = "EXTENDED"

# Configure format based on log level
EXTENDED_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s:%(thread)d] - [%(funcName)s:%(lineno)d] - [%(caller_func)s:%(caller_line)d] - %(message)s"
DETAILED_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - [%(caller_func)s:%(caller_line)d] - %(message)s"
STANDARD_LOG_FORMAT = (
    "%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s"
)
SIMPLE_LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
USELESS_LOG_FORMAT = "%(levelname)s: %(message)s"

# Format mappings by level
LOG_FORMAT_BY_LEVEL = {
    TRACE: EXTENDED_LOG_FORMAT,
    logging.DEBUG: DETAILED_LOG_FORMAT,
    logging.INFO: DETAILED_LOG_FORMAT,
    logging.WARNING: DETAILED_LOG_FORMAT,
    NOTICE: DETAILED_LOG_FORMAT,
    logging.ERROR: EXTENDED_LOG_FORMAT,
    logging.CRITICAL: EXTENDED_LOG_FORMAT,
}

# File logging configuration (adjusted for container environment)
# All can be overridden via env
LOG_FILE_PATH = os.environ.get("AXPOC_LOG_FILE_PATH", "/app/logs/axpoc.log")
LOG_FILE_MAX_SIZE = int(
    os.environ.get("AXPOC_LOG_FILE_MAX_BYTES", str(100 * 1024 * 1024))
)  # 100 MB
LOG_FILE_BACKUP_COUNT = int(os.environ.get("AXPOC_LOG_FILE_BACKUP_COUNT", "10"))
DEFAULT_FILE_LOG_LEVEL = os.environ.get(
    "AXPOC_FILE_LOG_LEVEL", "DEBUG"
)  # Default level for file logging

# Track if initialization has already happened
_initialized = False


class CallerInfoFilter(logging.Filter):
    """Adds caller-of-caller function and line to the record as:
    record.caller_func / record.caller_line
    """

    SKIP_PREFIXES = ("logging", "gunicorn.", "uvicorn.")
    SKIP_MODULES = {__name__}  # this log_config module

    def filter(self, record):
        import os
        import sys

        try:
            # Normalize the callsite we already have from logging.findCaller()
            target_path = os.path.normcase(record.pathname)
            target_func = record.funcName

            f = sys._getframe(0)  # we're inside logging right now
            callsite = None

            # Walk back until we hit the *actual* log call frame
            while f:
                co = f.f_code
                if (
                    os.path.normcase(co.co_filename) == target_path
                    and co.co_name == target_func
                ):
                    callsite = f
                    break
                f = f.f_back

            # Now step one frame up to the caller of the function that logged
            parent = callsite.f_back if callsite else None

            # Skip logging internals, this module, gunicorn/uvicorn wrappers, etc.
            while parent:
                mod = parent.f_globals.get("__name__", "")
                if (
                    mod in self.SKIP_MODULES
                    or mod.startswith(self.SKIP_PREFIXES)
                    or mod == target_func == "handle"
                ):  # extra guard for Handler.handle
                    parent = parent.f_back
                    continue
                break

            if parent:
                record.caller_func = parent.f_code.co_name
                record.caller_line = parent.f_lineno
            else:
                record.caller_func = "-"
                record.caller_line = 0

        except Exception:
            record.caller_func = "-"
            record.caller_line = 0
        finally:
            # avoid reference cycles
            f = callsite = parent = None

        return True


class LevelBasedFormatter(logging.Formatter):
    """Formatter that can use different formats based on record level."""

    def __init__(
        self,
        default_fmt: str,
        level_formats: Optional[Dict[int, str]] = None,
    ):
        """
        Initialize the formatter with default and level-specific formats.

        Args:
            default_fmt: The default format string to use
            level_formats: Dict mapping log levels to format strings
        """
        super().__init__(fmt=default_fmt)
        self.default_fmt = default_fmt
        self.level_formats = level_formats or {}

        # Create formatters for each level
        self.formatters = {
            level: logging.Formatter(fmt=fmt_str)
            for level, fmt_str in self.level_formats.items()
        }
        self.default_formatter = logging.Formatter(fmt=default_fmt)

    def format(self, record):
        """
        Format the specified record using the appropriate format string.

        Args:
            record: The log record to format

        Returns:
            The formatted log record
        """
        # Choose formatter based on record level
        formatter = self.formatters.get(record.levelno, self.default_formatter)
        return formatter.format(record)


def get_log_level(level_name: str) -> int:
    """
    Convert a string log level to the corresponding logging level.

    Args:
        level_name: The name of the log level (e.g., "DEBUG", "INFO")

    Returns:
        The corresponding logging level
    """
    level_name = level_name.upper()
    level_map = {
        "TRACE": TRACE,
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "NOTICE": NOTICE,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    return level_map.get(level_name, logging.INFO)


def get_log_format(format_name: Optional[str] = None) -> str:
    """
    Get the log format string based on the format name.

    Args:
        format_name: The name of the format to use. If None, uses the default format.

    Returns:
        The log format string.
    """
    if not format_name:
        return STANDARD_LOG_FORMAT

    # Try to map from level name to level
    format_name = format_name.upper()
    level_map = {
        "TRACE": TRACE,
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "NOTICE": NOTICE,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    if format_name in level_map:
        level = level_map[format_name]
        return LOG_FORMAT_BY_LEVEL.get(level, STANDARD_LOG_FORMAT)

    # Fallback to explicit format names
    if format_name == "EXTENDED":
        return EXTENDED_LOG_FORMAT
    elif format_name == "DETAILED":
        return DETAILED_LOG_FORMAT
    elif format_name == "SIMPLE":
        return SIMPLE_LOG_FORMAT

    # Default
    return STANDARD_LOG_FORMAT


def get_module_log_levels() -> Dict[str, int]:
    """
    Parse environment variables for module-specific log levels.

    Returns:
        A dictionary mapping module names to log levels
    """
    module_levels = {}

    for key, value in os.environ.items():
        if key.startswith(MODULE_LOG_LEVEL_PREFIX):
            module_name = key[len(MODULE_LOG_LEVEL_PREFIX) :].lower().replace("_", ".")
            module_levels[module_name] = get_log_level(value)

    return module_levels


def configure_logging(
    level: Optional[str] = None,
    file_level: Optional[str] = None,
    console_format: Optional[str] = None,
    file_format: Optional[str] = None,
    enable_file_logging: bool = True,
    level_specific_formats: Optional[Dict[str, str]] = None,
    rotate_on_startup: bool = False,
) -> None:
    """
    Configure the application's logging system.

    Args:
        level: Override the console log level (if None, uses environment variable or default)
        file_level: Override the file log level (if None, uses DEFAULT_FILE_LOG_LEVEL)
        console_format: Override console format ("SIMPLE", "DETAILED", or "EXTENDED")
        file_format: Override file format ("SIMPLE", "DETAILED", or "EXTENDED")
        enable_file_logging: Whether to enable logging to a file
        level_specific_formats: Dict mapping level names to format names for level-specific formatting
        rotate_on_startup: Whether to rotate log files on application startup.
            Defaults to ``False`` because session-based rotation is handled by
            entrypoint.sh BEFORE Gunicorn starts. This avoids issues with:
            - Multiple Gunicorn workers each trying to rotate (pre-fork model)
            - Worker crashes/restarts causing repeated rotation attempts
            - Race conditions between workers accessing the same log file
            The Python RotatingFileHandler handles SIZE-based rotation at runtime,
            while entrypoint.sh handles SESSION-based rotation at container start.
    """
    global _initialized

    if _initialized:
        logging.getLogger(__name__).debug(
            "Logging already initialized, skipping configuration"
        )
        return

    # Determine the console log level (prioritize explicit env for console)
    if level is None:
        level = os.environ.get(
            CONSOLE_LEVEL_ENV_VAR, os.environ.get(LOG_LEVEL_ENV_VAR, DEFAULT_LOG_LEVEL)
        )

    # Resolve numeric levels for console and file
    console_level_num = get_log_level(level)

    # Configure the root logger
    root_logger = logging.getLogger()
    # Determine file level from parameter or env
    env_file_level = os.environ.get(FILE_LEVEL_ENV_VAR)
    eff_file_level = file_level or env_file_level or DEFAULT_FILE_LOG_LEVEL
    file_level_num = get_log_level(eff_file_level)

    # Set root logger to the most permissive (lowest numeric) of both
    root_logger.setLevel(min(console_level_num, file_level_num))

    # Clear any existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Get console format from environment if not specified
    if console_format is None:
        console_format = os.environ.get(CONSOLE_FORMAT_ENV_VAR, DEFAULT_CONSOLE_FORMAT)

    # Get file format from environment if not specified
    if file_format is None:
        file_format = os.environ.get(FILE_FORMAT_ENV_VAR, DEFAULT_FILE_FORMAT)

    # Get format strings
    console_format_str = get_log_format(console_format)
    file_format_str = get_log_format(file_format)

    # Create caller filter for extended format
    caller_filter = CallerInfoFilter()

    # Configure level-specific formats if needed
    if console_format:
        # Use the chosen console format for all levels (including errors)
        console_level_formats = {
            TRACE: console_format_str,
            logging.DEBUG: console_format_str,
            logging.INFO: console_format_str,
            NOTICE: console_format_str,
            logging.WARNING: console_format_str,
            logging.ERROR: console_format_str,
            logging.CRITICAL: console_format_str,
        }
    else:
        # Default: EXTENDED for all levels
        console_level_formats = {
            TRACE: EXTENDED_LOG_FORMAT,
            logging.DEBUG: EXTENDED_LOG_FORMAT,
            logging.INFO: EXTENDED_LOG_FORMAT,
            NOTICE: EXTENDED_LOG_FORMAT,
            logging.WARNING: EXTENDED_LOG_FORMAT,
            logging.ERROR: EXTENDED_LOG_FORMAT,
            logging.CRITICAL: EXTENDED_LOG_FORMAT,
        }

    # Create and configure console handler
    # Use stderr for compatibility with Gunicorn and Docker log capture
    console_handler = logging.StreamHandler(sys.stderr)
    console_formatter = LevelBasedFormatter(console_format_str, console_level_formats)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(console_level_num)

    # Add caller filter if extended format is used anywhere
    if console_format == "EXTENDED" or any(
        fmt == EXTENDED_LOG_FORMAT for fmt in console_level_formats.values()
    ):
        console_handler.addFilter(caller_filter)

    root_logger.addHandler(console_handler)

    # Configure file handler if enabled
    if enable_file_logging:
        # Configure level-specific formats if needed
        if file_format:
            # Use the chosen file format for all levels (including errors)
            file_level_formats = {
                TRACE: file_format_str,
                logging.DEBUG: file_format_str,
                logging.INFO: file_format_str,
                NOTICE: file_format_str,
                logging.WARNING: file_format_str,
                logging.ERROR: file_format_str,
                logging.CRITICAL: file_format_str,
            }
        else:
            # Default: EXTENDED for all levels
            file_level_formats = {
                TRACE: EXTENDED_LOG_FORMAT,
                logging.DEBUG: EXTENDED_LOG_FORMAT,
                logging.INFO: EXTENDED_LOG_FORMAT,
                NOTICE: EXTENDED_LOG_FORMAT,
                logging.WARNING: EXTENDED_LOG_FORMAT,
                logging.ERROR: EXTENDED_LOG_FORMAT,
                logging.CRITICAL: EXTENDED_LOG_FORMAT,
            }

        try:
            # Ensure log directory exists
            log_dir = os.path.dirname(LOG_FILE_PATH)
            os.makedirs(log_dir, exist_ok=True)

            # Check if log file exists and needs rotation on startup
            log_exists = os.path.exists(LOG_FILE_PATH)

            # Create the file handler
            file_handler = RotatingFileHandler(
                os.environ.get("AXPOC_LOG_FILE_PATH", LOG_FILE_PATH),
                maxBytes=int(
                    os.environ.get("AXPOC_LOG_FILE_MAX_BYTES", str(LOG_FILE_MAX_SIZE))
                ),
                backupCount=int(
                    os.environ.get(
                        "AXPOC_LOG_FILE_BACKUP_COUNT", str(LOG_FILE_BACKUP_COUNT)
                    )
                ),
            )

            # Force rotation on startup if requested and file exists
            rotate_env = os.environ.get("AXPOC_LOG_ROTATE_ON_STARTUP")
            rotate_flag = (
                rotate_on_startup
                if rotate_env is None
                else rotate_env.lower() in ("1", "true", "yes", "on")
            )
            if rotate_flag and log_exists:
                file_handler.doRollover()
                logging.getLogger(__name__).info(
                    f"Rotated log file on application startup: {LOG_FILE_PATH}"
                )

            file_handler.setLevel(file_level_num)

            # Use level-based formatter for file handler too
            file_formatter = LevelBasedFormatter(file_format_str, file_level_formats)
            file_handler.setFormatter(file_formatter)

            # Add caller filter if needed
            if file_format == "EXTENDED" or any(
                fmt == EXTENDED_LOG_FORMAT for fmt in file_level_formats.values()
            ):
                file_handler.addFilter(caller_filter)

            root_logger.addHandler(file_handler)
        except (IOError, PermissionError) as e:
            # Don't fail if file logging can't be set up
            logging.getLogger(__name__).error(f"Failed to configure file logging: {e}")

    # Configure module-specific log levels
    module_levels = get_module_log_levels()
    for module_name, module_level in module_levels.items():
        logging.getLogger(module_name).setLevel(module_level)

    # Log the configuration
    logger = logging.getLogger(__name__)
    logger.info(
        f"AXPOC logging configured with console level: {logging.getLevelName(console_level_num)}"
    )
    logger.info(f"Console format: {console_format}, File format: {file_format}")

    if enable_file_logging:
        file_log_level = file_level_num
        logger.info(
            f"File logging configured at {LOG_FILE_PATH} with level: {logging.getLevelName(file_log_level)}"
        )

    if console_level_formats:
        level_format_names = {
            logging.getLevelName(level): (
                "EXTENDED"
                if fmt == EXTENDED_LOG_FORMAT
                else "DETAILED" if fmt == DETAILED_LOG_FORMAT else "SIMPLE"
            )
            for level, fmt in console_level_formats.items()
        }
        logger.info(
            f"Level-specific formats: {', '.join(f'{level}={fmt}' for level, fmt in level_format_names.items())}"
        )

    if module_levels:
        logger.info(
            f"Module-specific log levels: {', '.join(f'{m}={logging.getLevelName(l)}' for m, l in module_levels.items())}"
        )

    # Write a session start marker to help identify session boundaries in logs
    # This is especially useful when rotation is disabled and logs accumulate
    session_marker = (
        "\n"
        "=" * 80 + "\n"
        f"=== NEW SESSION STARTED: {datetime.datetime.now().isoformat()} ===\n"
        f"=== PID: {os.getpid()} ===\n"
        "=" * 80
    )
    logger.info(session_marker)

    _initialized = True


def get_logger(name: str) -> AXPOCLogger:
    """
    Get a logger with the given name, ensuring logging is configured.

    Args:
        name: The name for the logger (typically __name__ from the calling module)

    Returns:
        A configured logger instance
    """
    if not _initialized:
        configure_logging()

    return logging.getLogger(name)  # type: ignore[return-value]


def get_current_log_level(
    target_logger: Optional[str] = None, handler_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get the current log level for a logger and its handlers.

    Args:
        target_logger: The name of the logger to check (None for root logger)
        handler_type: If provided, only return levels for this handler type ('console' or 'file')

    Returns:
        A dictionary with logger and handler levels (values can be strings or dicts)
    """
    # Get the target logger
    logger = logging.getLogger(target_logger) if target_logger else logging.getLogger()

    result: Dict[str, Any] = {
        "logger": logging.getLevelName(logger.getEffectiveLevel())
    }

    # Check handlers
    handlers_info = {}
    for handler in logger.handlers:
        # Determine handler type
        if isinstance(handler, logging.handlers.RotatingFileHandler):
            h_type = "file"
        elif isinstance(handler, logging.StreamHandler):
            h_type = "console"
        else:
            h_type = "other"

        # Skip if we're filtering by handler type
        if handler_type and handler_type != h_type:
            continue

        # Add handler info
        handlers_info[h_type] = logging.getLevelName(handler.level)

    # Add handlers to result
    if handlers_info:
        result["handlers"] = handlers_info

    return result


def change_log_level(
    level: str,
    console_only: bool = False,
    file_only: bool = False,
    target_logger: Optional[str] = None,
) -> None:
    """
    Dynamically change the log level at runtime.

    Args:
        level: The new log level as a string (e.g., "DEBUG", "INFO", "TRACE", etc.)
        console_only: If True, only change console handler levels
        file_only: If True, only change file handler levels
        target_logger: If provided, only change this specific logger; otherwise change root logger

    Returns:
        None
    """
    # Convert level name to numeric level
    numeric_level = get_log_level(level)
    level_name = logging.getLevelName(numeric_level)

    # Get the target logger (root logger by default)
    logger = logging.getLogger(target_logger) if target_logger else logging.getLogger()

    # Only change the logger's level if we're changing both handlers or there are no handlers
    if not console_only and not file_only:
        logger.setLevel(numeric_level)

    # Keep track of what we changed
    changes = []

    # Update handlers
    for handler in logger.handlers:
        # Skip handlers based on flags
        if console_only and not isinstance(handler, logging.StreamHandler):
            continue
        if file_only and not isinstance(handler, logging.handlers.RotatingFileHandler):
            continue

        old_level = logging.getLevelName(handler.level)
        handler.setLevel(numeric_level)

        # Track what kind of handler was updated
        handler_type = (
            "console" if isinstance(handler, logging.StreamHandler) else "file"
        )
        changes.append(f"{handler_type}:{old_level}->{level_name}")

    # Log the change
    change_msg = f"Log level changed to {level_name}"
    if target_logger:
        change_msg += f" for logger '{target_logger}'"
    if changes:
        change_msg += f" (handlers: {', '.join(changes)})"

    # Use a separate logger to avoid potential issues with the logger being modified
    logging.getLogger(__name__).info(change_msg)

    return None
