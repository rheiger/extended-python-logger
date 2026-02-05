# Extended Python Logger

A robust, drop-in logging utility for Python that adds `TRACE` and `NOTICE` levels, a PITS-style ring buffer, and a structured `PITSCSV` format for post-mortem debugging.

## Features
- Custom levels: `TRACE`, `NOTICE`, `ALWAYS`, `NEVER`
- Per-logger (class) level overrides via environment variables
- PITS-style in-memory ring buffer with dump on unhandled exceptions
- Structured `PITSCSV` format with caller details
- Console stream configurable (`stderr` default, `stdout` optional)
- File logging with rotation

## Installation

```bash
pip install extended-python-logger
```

## Quick Start

```python
from extended_python_logger import configure_logging, get_logger, TRACE, NOTICE

configure_logging(
    console_level="NOTICE",
    file_level="TRACE",
    console_format="DETAILED",
    file_format="EXTENDED",
)

logger = get_logger(__name__)

logger.trace("Trace detail")
logger.debug("Debug detail")
logger.info("Info message")
logger.notice("Important but not a warning")
logger.warning("Warning")
logger.error("Error")
logger.critical("Critical")
```

## Levels
- `TRACE`: very noisy, prefer file logging.
- `NOTICE`: important but not a warning.
- `ALWAYS`: always emitted to console/file regardless of thresholds.
- `NEVER`: ring-buffer only (never console/file).

### Exceptions
Use the built-in `logger.exception()` inside `except` blocks unless the exception is expected and handled gracefully.

```python
try:
    1 / 0
except ZeroDivisionError:
    logger.exception("Something went wrong")
```

## Configuration (Environment Variables)

All env vars use prefix `PYTHON_LOG_`.

### Global Levels
- `PYTHON_LOG_LEVEL`
- `PYTHON_LOG_CONSOLE_LEVEL`
- `PYTHON_LOG_FILE_LEVEL`

### Per-Logger Overrides
- `PYTHON_LOG_LEVEL_<LOGGER>`
- `PYTHON_LOG_CONSOLE_LEVEL_<LOGGER>`
- `PYTHON_LOG_FILE_LEVEL_<LOGGER>`

`<LOGGER>` maps dots to underscores. Example:

```
export PYTHON_LOG_CONSOLE_LEVEL_MYAPP_DB=DEBUG
```

### Formats
- `PYTHON_LOG_CONSOLE_FORMAT` = `SIMPLE|STANDARD|DETAILED|EXTENDED|PITSCSV`
- `PYTHON_LOG_FILE_FORMAT` = `SIMPLE|STANDARD|DETAILED|EXTENDED|PITSCSV`

Defaults: console `DETAILED`, file `EXTENDED`.

### Console Stream
- `PYTHON_LOG_CONSOLE_STREAM` = `stderr|stdout`

Default: `stderr`.

### File Logging
- `PYTHON_LOG_FILE_ENABLED`
- `PYTHON_LOG_FILE_PATH`
- `PYTHON_LOG_FILE_MAX_BYTES`
- `PYTHON_LOG_FILE_BACKUP_COUNT`
- `PYTHON_LOG_ROTATE_ON_STARTUP`

### Ring Buffer
- `PYTHON_LOG_RING_ENABLED`
- `PYTHON_LOG_RING_SIZE`
- `PYTHON_LOG_RING_DUMP_PATH`
- `PYTHON_LOG_RING_DUMP_ON_UNHANDLED`

The ring buffer dumps only on **unhandled exceptions** (terminating errors). It is not dumped for handled `try/except` blocks.

## PITSCSV Format

Field order:
1. timestamp (UTC, microseconds)
2. program name
3. thread id
4. pid
5. euid
6. egid
7. level
8. logger/class name
9. action (reserved, empty)
10. file
11. line
12. function
13. caller (function:file:line)
14. message

## Demo App
See `examples/demo_app.py` for a full usage example including TRACE/NOTICE, ring buffer, and crash dump behavior.

## Roadmap
- Multi-language implementations for Rust, Go, C++, and JS/TS using native ecosystems
- Optional cross-language logging spec

## License
MIT
