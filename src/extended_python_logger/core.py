"""Extended logging utilities with TRACE/NOTICE, ring buffer, and PITSCSV format."""
from __future__ import annotations

import csv
import datetime as _dt
import io
import logging
import os
import sys
import tempfile
import threading
from collections import deque
from dataclasses import dataclass, field
from logging.handlers import RotatingFileHandler
from typing import Dict, Iterable, Optional

# --- Custom log levels ---
NEVER = -100
TRACE = 5
NOTICE = 25
ALWAYS = 100

logging.addLevelName(NEVER, "NEVER")
logging.addLevelName(TRACE, "TRACE")
logging.addLevelName(NOTICE, "NOTICE")
logging.addLevelName(ALWAYS, "ALWAYS")
setattr(logging, "NEVER", NEVER)
setattr(logging, "TRACE", TRACE)
setattr(logging, "NOTICE", NOTICE)
setattr(logging, "ALWAYS", ALWAYS)


class ExtendedLogger(logging.Logger):
    """Logger exposing trace() and notice() methods."""

    def trace(self, message, *args, **kwargs):
        kwargs.setdefault("stacklevel", 2)
        if self.isEnabledFor(TRACE):
            self._log(TRACE, message, args, **kwargs)

    def notice(self, message, *args, **kwargs):
        kwargs.setdefault("stacklevel", 2)
        if self.isEnabledFor(NOTICE):
            self._log(NOTICE, message, args, **kwargs)


# Register custom logger class for all future loggers.
logging.setLoggerClass(ExtendedLogger)


# Fallback compatibility for already-created loggers.
def _trace(self, message, *args, **kwargs):
    kwargs.setdefault("stacklevel", 2)
    if self.isEnabledFor(TRACE):
        self._log(TRACE, message, args, **kwargs)


def _notice(self, message, *args, **kwargs):
    kwargs.setdefault("stacklevel", 2)
    if self.isEnabledFor(NOTICE):
        self._log(NOTICE, message, args, **kwargs)


logging.Logger.trace = _trace  # type: ignore[attr-defined]
logging.Logger.notice = _notice  # type: ignore[attr-defined]


ENV_PREFIX = "PYTHON_LOG_"

# Global level envs
LOG_LEVEL_ENV = f"{ENV_PREFIX}LEVEL"
CONSOLE_LEVEL_ENV = f"{ENV_PREFIX}CONSOLE_LEVEL"
FILE_LEVEL_ENV = f"{ENV_PREFIX}FILE_LEVEL"

# Per-logger (class) overrides
PER_LOGGER_LEVEL_PREFIX = f"{ENV_PREFIX}LEVEL_"
PER_LOGGER_CONSOLE_PREFIX = f"{ENV_PREFIX}CONSOLE_LEVEL_"
PER_LOGGER_FILE_PREFIX = f"{ENV_PREFIX}FILE_LEVEL_"

# Formats
CONSOLE_FORMAT_ENV = f"{ENV_PREFIX}CONSOLE_FORMAT"
FILE_FORMAT_ENV = f"{ENV_PREFIX}FILE_FORMAT"

# Console stream
CONSOLE_STREAM_ENV = f"{ENV_PREFIX}CONSOLE_STREAM"

# File logging
FILE_ENABLED_ENV = f"{ENV_PREFIX}FILE_ENABLED"
FILE_PATH_ENV = f"{ENV_PREFIX}FILE_PATH"
FILE_MAX_BYTES_ENV = f"{ENV_PREFIX}FILE_MAX_BYTES"
FILE_BACKUP_COUNT_ENV = f"{ENV_PREFIX}FILE_BACKUP_COUNT"
ROTATE_ON_STARTUP_ENV = f"{ENV_PREFIX}ROTATE_ON_STARTUP"

# Ring buffer
RING_ENABLED_ENV = f"{ENV_PREFIX}RING_ENABLED"
RING_SIZE_ENV = f"{ENV_PREFIX}RING_SIZE"
RING_DUMP_PATH_ENV = f"{ENV_PREFIX}RING_DUMP_PATH"
RING_DUMP_ON_UNHANDLED_ENV = f"{ENV_PREFIX}RING_DUMP_ON_UNHANDLED"

DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_CONSOLE_FORMAT = "DETAILED"
DEFAULT_FILE_FORMAT = "EXTENDED"
DEFAULT_FILE_ENABLED = True
DEFAULT_FILE_PATH = "app.log"
DEFAULT_FILE_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_FILE_BACKUP_COUNT = 5
DEFAULT_CONSOLE_STREAM = "stderr"
DEFAULT_RING_ENABLED = True
DEFAULT_RING_SIZE = 1024
DEFAULT_RING_DUMP_ON_UNHANDLED = True


SIMPLE_LOG_FORMAT = "%(levelname)s: %(message)s"
STANDARD_LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
DETAILED_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - [%(caller_func)s:%(caller_line)d] - %(message)s"
EXTENDED_LOG_FORMAT = (
    "%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s:%(thread)d] - "
    "[%(funcName)s:%(lineno)d] - [%(caller_func)s:%(caller_line)d] - %(message)s"
)


def _str_to_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def get_log_level(level_name: str) -> int:
    """Convert log level name to numeric level."""
    if isinstance(level_name, int):
        return level_name
    name = str(level_name).strip().upper()
    if name.isdigit() or (name.startswith("-") and name[1:].isdigit()):
        return int(name)
    mapping = {
        "NEVER": NEVER,
        "TRACE": TRACE,
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "NOTICE": NOTICE,
        "WARNING": logging.WARNING,
        "WARN": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
        "FATAL": logging.CRITICAL,
        "ALWAYS": ALWAYS,
        "NOTSET": logging.NOTSET,
    }
    return mapping.get(name, logging.INFO)


def get_log_format_by_name(format_name: str) -> str:
    """Return a format string (or PITSCSV marker) for the given format name."""
    name = str(format_name).strip().upper()
    if name == "PITSCSV":
        return "PITSCSV"
    return {
        "SIMPLE": SIMPLE_LOG_FORMAT,
        "STANDARD": STANDARD_LOG_FORMAT,
        "DETAILED": DETAILED_LOG_FORMAT,
        "EXTENDED": EXTENDED_LOG_FORMAT,
    }.get(name, STANDARD_LOG_FORMAT)


def _normalize_logger_key(raw: str) -> str:
    return raw.lower().replace("_", ".")


def _iter_logger_hierarchy(name: str) -> Iterable[str]:
    current = name
    while current:
        yield current
        if "." not in current:
            break
        current = current.rsplit(".", 1)[0]


def _get_effective_level(
    logger_name: str,
    default_level: int,
    overrides: Dict[str, int],
) -> int:
    key = logger_name.lower()
    for candidate in _iter_logger_hierarchy(key):
        if candidate in overrides:
            return overrides[candidate]
    return default_level


def _get_effective_level_with_fallback(
    logger_name: str,
    default_level: int,
    primary: Dict[str, int],
    fallback: Dict[str, int],
) -> int:
    key = logger_name.lower()
    for candidate in _iter_logger_hierarchy(key):
        if candidate in primary:
            return primary[candidate]
    for candidate in _iter_logger_hierarchy(key):
        if candidate in fallback:
            return fallback[candidate]
    return default_level


class CallerInfoFilter(logging.Filter):
    """Adds caller function and line information to log records."""

    SKIP_PREFIXES = ("logging",)
    SKIP_MODULES = {__name__}

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            target_path = os.path.normcase(record.pathname)
            target_func = record.funcName

            f = sys._getframe(0)
            callsite = None
            while f:
                co = f.f_code
                if os.path.normcase(co.co_filename) == target_path and co.co_name == target_func:
                    callsite = f
                    break
                f = f.f_back

            parent = callsite.f_back if callsite else None
            while parent:
                mod = parent.f_globals.get("__name__", "")
                if mod in self.SKIP_MODULES or mod.startswith(self.SKIP_PREFIXES):
                    parent = parent.f_back
                    continue
                break

            if parent:
                record.caller_func = parent.f_code.co_name
                record.caller_line = parent.f_lineno
                record.caller_file = os.path.basename(parent.f_code.co_filename)
            else:
                record.caller_func = "-"
                record.caller_line = 0
                record.caller_file = "-"
        except Exception:
            record.caller_func = "-"
            record.caller_line = 0
            record.caller_file = "-"
        return True


class LevelBasedFormatter(logging.Formatter):
    """Formatter choosing formats based on record level."""

    def __init__(
        self,
        default_formatter: logging.Formatter,
        level_formatters: Optional[Dict[int, logging.Formatter]] = None,
    ) -> None:
        super().__init__()
        self._default_formatter = default_formatter
        self._level_formatters = level_formatters or {}

    def format(self, record: logging.LogRecord) -> str:
        formatter = self._level_formatters.get(record.levelno, self._default_formatter)
        return formatter.format(record)


class PitsCsvFormatter(logging.Formatter):
    """Structured CSV formatter inspired by the PITS format."""

    def __init__(self, program_name: Optional[str] = None) -> None:
        super().__init__()
        self._program_name = program_name or os.path.basename(sys.argv[0] or "") or "-"

    def format(self, record: logging.LogRecord) -> str:
        caller_func = getattr(record, "caller_func", "-")
        caller_line = getattr(record, "caller_line", 0)
        caller_file = getattr(record, "caller_file", "-")

        timestamp = _dt.datetime.utcfromtimestamp(record.created).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        thread_id = record.thread
        pid = record.process
        euid = os.geteuid() if hasattr(os, "geteuid") else 0
        egid = os.getegid() if hasattr(os, "getegid") else 0
        level = record.levelname
        logger_name = record.name
        action = ""
        file_name = record.filename
        line = record.lineno
        func = record.funcName
        caller = f"{caller_func}:{caller_file}:{caller_line}"
        message = record.getMessage()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                timestamp,
                self._program_name,
                thread_id,
                pid,
                euid,
                egid,
                level,
                logger_name,
                action,
                file_name,
                line,
                func,
                caller,
                message,
            ]
        )
        return output.getvalue().rstrip("\n")


class RingBuffer:
    def __init__(self, size: int) -> None:
        self._deque = deque(maxlen=max(1, size))

    def append(self, item: str) -> None:
        self._deque.append(item)

    def resize(self, size: int) -> None:
        size = max(1, size)
        items = list(self._deque)[-size:]
        self._deque = deque(items, maxlen=size)

    def snapshot(self) -> Iterable[str]:
        return list(self._deque)

    def dump(self, path: str) -> str:
        dirpath = os.path.dirname(path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            for line in self._deque:
                fh.write(line)
                fh.write("\n")
        return path


class RingBufferHandler(logging.Handler):
    def __init__(self, ring: RingBuffer) -> None:
        super().__init__(level=NEVER)
        self._ring = ring

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._ring.append(msg)
        except Exception:
            self.handleError(record)


class PerLoggerFilter(logging.Filter):
    def __init__(
        self,
        default_level: int,
        primary: Dict[str, int],
        fallback: Dict[str, int],
    ) -> None:
        super().__init__()
        self._default = default_level
        self._primary = primary
        self._fallback = fallback

    def set_defaults(
        self,
        default_level: int,
        primary: Dict[str, int],
        fallback: Dict[str, int],
    ) -> None:
        self._default = default_level
        self._primary = primary
        self._fallback = fallback

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno == NEVER:
            return False
        if record.levelno >= ALWAYS:
            return True
        threshold = _get_effective_level_with_fallback(
            record.name,
            self._default,
            self._primary,
            self._fallback,
        )
        return record.levelno >= threshold


@dataclass
class _LoggingState:
    console_level: int = field(default_factory=lambda: get_log_level(DEFAULT_LOG_LEVEL))
    file_level: int = field(default_factory=lambda: get_log_level(DEFAULT_LOG_LEVEL))
    per_logger_level: Dict[str, int] = field(default_factory=dict)
    per_logger_console: Dict[str, int] = field(default_factory=dict)
    per_logger_file: Dict[str, int] = field(default_factory=dict)
    console_format: str = DEFAULT_CONSOLE_FORMAT
    file_format: str = DEFAULT_FILE_FORMAT
    console_stream: str = DEFAULT_CONSOLE_STREAM
    file_enabled: bool = DEFAULT_FILE_ENABLED
    ring_enabled: bool = DEFAULT_RING_ENABLED
    ring_size: int = DEFAULT_RING_SIZE
    ring_dump_path: Optional[str] = None
    ring_dump_on_unhandled: bool = DEFAULT_RING_DUMP_ON_UNHANDLED
    program_name: str = field(default_factory=lambda: os.path.basename(sys.argv[0] or "") or "-")


_STATE = _LoggingState()
_INITIALIZED = False
_RING: Optional[RingBuffer] = None
_RING_HANDLER: Optional[RingBufferHandler] = None
_CONSOLE_FILTER: Optional[PerLoggerFilter] = None
_FILE_FILTER: Optional[PerLoggerFilter] = None
_ORIGINAL_SYS_EXCEPTHOOK = getattr(sys, "__excepthook__", sys.excepthook)
_ORIGINAL_THREADING_EXCEPTHOOK = getattr(threading, "excepthook", None)


def _parse_per_logger(prefix: str) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        suffix = key[len(prefix) :]
        if not suffix:
            continue
        name = _normalize_logger_key(suffix)
        result[name] = get_log_level(value)
    return result


def _format_requires_caller(format_name: str) -> bool:
    name = format_name.upper()
    return name in {"DETAILED", "EXTENDED", "PITSCSV"}


def _build_formatter(format_name: str, program_name: str) -> logging.Formatter:
    name = format_name.upper()
    if name == "PITSCSV":
        return PitsCsvFormatter(program_name=program_name)
    fmt = get_log_format_by_name(name)
    return logging.Formatter(fmt=fmt)


def _build_level_formatter(format_name: str, program_name: str) -> LevelBasedFormatter:
    base = _build_formatter(format_name, program_name)
    level_formatters = {
        NEVER: base,
        TRACE: base,
        logging.DEBUG: base,
        logging.INFO: base,
        NOTICE: base,
        logging.WARNING: base,
        logging.ERROR: base,
        logging.CRITICAL: base,
        ALWAYS: base,
    }
    return LevelBasedFormatter(base, level_formatters)


def _ensure_ring(size: int) -> RingBuffer:
    global _RING
    if _RING is None:
        _RING = RingBuffer(size=size)
    else:
        _RING.resize(size)
    return _RING


def _default_ring_dump_path() -> str:
    stamp = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    return os.path.join(tempfile.gettempdir(), f"extended-python-logger-{stamp}.dump")


def dump_ring_buffer(path: Optional[str] = None) -> Optional[str]:
    if _RING is None:
        return None
    target = path or _STATE.ring_dump_path or _default_ring_dump_path()
    return _RING.dump(target)


def _handle_unhandled_exception(exc_type, exc, tb) -> None:
    if _STATE.ring_dump_on_unhandled:
        dump_ring_buffer()
    if _ORIGINAL_SYS_EXCEPTHOOK is not None:
        _ORIGINAL_SYS_EXCEPTHOOK(exc_type, exc, tb)


def _handle_thread_exception(args) -> None:
    if _STATE.ring_dump_on_unhandled:
        dump_ring_buffer()
    if _ORIGINAL_THREADING_EXCEPTHOOK is not None and _ORIGINAL_THREADING_EXCEPTHOOK is not _handle_thread_exception:
        _ORIGINAL_THREADING_EXCEPTHOOK(args)


def configure_logging(
    level: Optional[str] = None,
    console_level: Optional[str] = None,
    file_level: Optional[str] = None,
    console_format: Optional[str] = None,
    file_format: Optional[str] = None,
    console_stream: Optional[str] = None,
    enable_file_logging: Optional[bool] = None,
    file_path: Optional[str] = None,
    file_max_bytes: Optional[int] = None,
    file_backup_count: Optional[int] = None,
    rotate_on_startup: Optional[bool] = None,
    ring_enabled: Optional[bool] = None,
    ring_size: Optional[int] = None,
    ring_dump_path: Optional[str] = None,
    ring_dump_on_unhandled: Optional[bool] = None,
) -> None:
    """Configure logging according to args/env vars. Idempotent."""
    global _INITIALIZED, _RING_HANDLER, _CONSOLE_FILTER, _FILE_FILTER

    if _INITIALIZED:
        return

    global_level = level or os.getenv(LOG_LEVEL_ENV, DEFAULT_LOG_LEVEL)
    console_level_str = console_level or os.getenv(CONSOLE_LEVEL_ENV, global_level)
    file_level_str = file_level or os.getenv(FILE_LEVEL_ENV, global_level)

    _STATE.console_level = get_log_level(console_level_str)
    _STATE.file_level = get_log_level(file_level_str)

    _STATE.per_logger_level = _parse_per_logger(PER_LOGGER_LEVEL_PREFIX)
    _STATE.per_logger_console = _parse_per_logger(PER_LOGGER_CONSOLE_PREFIX)
    _STATE.per_logger_file = _parse_per_logger(PER_LOGGER_FILE_PREFIX)

    _STATE.console_format = console_format or os.getenv(CONSOLE_FORMAT_ENV, DEFAULT_CONSOLE_FORMAT)
    _STATE.file_format = file_format or os.getenv(FILE_FORMAT_ENV, DEFAULT_FILE_FORMAT)

    _STATE.console_stream = (console_stream or os.getenv(CONSOLE_STREAM_ENV, DEFAULT_CONSOLE_STREAM)).lower()

    _STATE.file_enabled = (
        enable_file_logging
        if enable_file_logging is not None
        else _str_to_bool(os.getenv(FILE_ENABLED_ENV), DEFAULT_FILE_ENABLED)
    )

    _STATE.ring_enabled = (
        ring_enabled
        if ring_enabled is not None
        else _str_to_bool(os.getenv(RING_ENABLED_ENV), DEFAULT_RING_ENABLED)
    )
    _STATE.ring_size = int(ring_size or os.getenv(RING_SIZE_ENV, DEFAULT_RING_SIZE))
    _STATE.ring_dump_path = ring_dump_path or os.getenv(RING_DUMP_PATH_ENV)
    _STATE.ring_dump_on_unhandled = (
        ring_dump_on_unhandled
        if ring_dump_on_unhandled is not None
        else _str_to_bool(os.getenv(RING_DUMP_ON_UNHANDLED_ENV), DEFAULT_RING_DUMP_ON_UNHANDLED)
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(NEVER)
    root_logger.handlers.clear()
    logging.disable(NEVER - 1)

    # Ring buffer handler
    if _STATE.ring_enabled:
        ring = _ensure_ring(_STATE.ring_size)
        _RING_HANDLER = RingBufferHandler(ring)
        ring_formatter = _build_level_formatter(_STATE.file_format, _STATE.program_name)
        _RING_HANDLER.setFormatter(ring_formatter)
        if _format_requires_caller(_STATE.file_format):
            _RING_HANDLER.addFilter(CallerInfoFilter())
        root_logger.addHandler(_RING_HANDLER)

    # Console handler
    stream = sys.stderr if _STATE.console_stream != "stdout" else sys.stdout
    console_handler = logging.StreamHandler(stream)
    console_formatter = _build_level_formatter(_STATE.console_format, _STATE.program_name)
    console_handler.setFormatter(console_formatter)
    _CONSOLE_FILTER = PerLoggerFilter(
        _STATE.console_level,
        _STATE.per_logger_console,
        _STATE.per_logger_level,
    )
    console_handler.addFilter(_CONSOLE_FILTER)
    if _format_requires_caller(_STATE.console_format):
        console_handler.addFilter(CallerInfoFilter())
    root_logger.addHandler(console_handler)

    # File handler
    if _STATE.file_enabled:
        path = file_path or os.getenv(FILE_PATH_ENV, DEFAULT_FILE_PATH)
        max_bytes = int(file_max_bytes or os.getenv(FILE_MAX_BYTES_ENV, DEFAULT_FILE_MAX_BYTES))
        backup_count = int(file_backup_count or os.getenv(FILE_BACKUP_COUNT_ENV, DEFAULT_FILE_BACKUP_COUNT))
        should_rotate = (
            rotate_on_startup
            if rotate_on_startup is not None
            else _str_to_bool(os.getenv(ROTATE_ON_STARTUP_ENV), False)
        )

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        file_handler = RotatingFileHandler(path, maxBytes=max_bytes, backupCount=backup_count)
        if should_rotate and os.path.exists(path):
            file_handler.doRollover()

        file_formatter = _build_level_formatter(_STATE.file_format, _STATE.program_name)
        file_handler.setFormatter(file_formatter)
        _FILE_FILTER = PerLoggerFilter(
            _STATE.file_level,
            _STATE.per_logger_file,
            _STATE.per_logger_level,
        )
        file_handler.addFilter(_FILE_FILTER)
        if _format_requires_caller(_STATE.file_format):
            file_handler.addFilter(CallerInfoFilter())
        root_logger.addHandler(file_handler)

    # Install excepthooks for ring buffer dumps
    if _STATE.ring_enabled and _STATE.ring_dump_on_unhandled:
        sys.excepthook = _handle_unhandled_exception
        if hasattr(threading, "excepthook"):
            threading.excepthook = _handle_thread_exception  # type: ignore[assignment]

    _INITIALIZED = True


def get_logger(name: str) -> logging.Logger:
    if not _INITIALIZED:
        configure_logging()
    return logging.getLogger(name)


def get_current_log_level(
    target_logger: Optional[str] = None,
    handler_type: Optional[str] = None,
) -> Dict[str, object]:
    name = (target_logger or "").lower()
    result: Dict[str, object] = {}

    console_level = _get_effective_level_with_fallback(
        name, _STATE.console_level, _STATE.per_logger_console, _STATE.per_logger_level
    )
    file_level = _get_effective_level_with_fallback(
        name, _STATE.file_level, _STATE.per_logger_file, _STATE.per_logger_level
    )

    if handler_type in (None, "console"):
        result["console"] = logging.getLevelName(console_level)
    if handler_type in (None, "file"):
        result["file"] = logging.getLevelName(file_level)
    return result


def change_log_level(
    level: str,
    target_logger: Optional[str] = None,
    console_only: bool = False,
    file_only: bool = False,
) -> None:
    new_level = get_log_level(level)

    if target_logger:
        key = target_logger.lower()
        if console_only:
            _STATE.per_logger_console[key] = new_level
        elif file_only:
            _STATE.per_logger_file[key] = new_level
        else:
            _STATE.per_logger_level[key] = new_level
    else:
        if not file_only:
            _STATE.console_level = new_level
        if not console_only:
            _STATE.file_level = new_level

    if _CONSOLE_FILTER is not None:
        _CONSOLE_FILTER.set_defaults(
            _STATE.console_level, _STATE.per_logger_console, _STATE.per_logger_level
        )
    if _FILE_FILTER is not None:
        _FILE_FILTER.set_defaults(
            _STATE.file_level, _STATE.per_logger_file, _STATE.per_logger_level
        )

    logging.getLogger(__name__).info(
        "Log level updated to %s for %s",
        logging.getLevelName(new_level),
        target_logger or "root",
    )
