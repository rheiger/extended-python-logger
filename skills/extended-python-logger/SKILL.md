---
name: extended-python-logger
description: Use when working with the extended-python-logger package (TRACE/NOTICE, ring buffer, PITSCSV, env configuration).
---

# Extended Python Logger Skill

## When to use
Use this skill for any task involving `extended-python-logger`: configuration, usage examples, troubleshooting logging output, or adding new features.

For integration and replacement of an existing logging interface, use `/Users/rheiger/Dev/extended_python_logger/skills/extended-python-logger/references/migration.md`.

## Quick usage
```python
from extended_python_logger import configure_logging, get_logger

configure_logging(console_level="NOTICE", file_level="TRACE")
logger = get_logger(__name__)
logger.notice("Service ready")
```

## Exceptions
- Inside `except` blocks, use `logger.exception()` unless the exception is expected and handled gracefully.
- Expected exceptions should be `INFO` or `NOTICE`.

## Levels
- `TRACE`: very noisy, prefer file logging.
- `NOTICE`: important but not a warning.
- `ALWAYS`: must always emit to console/file.
- `NEVER`: ring-buffer only.

## Environment configuration
Prefix: `PYTHON_LOG_`

- Global: `LEVEL`, `CONSOLE_LEVEL`, `FILE_LEVEL`
- Per-logger overrides: `LEVEL_<LOGGER>`, `CONSOLE_LEVEL_<LOGGER>`, `FILE_LEVEL_<LOGGER>`
- Formats: `CONSOLE_FORMAT`, `FILE_FORMAT` (`SIMPLE|STANDARD|DETAILED|EXTENDED|PITSCSV`)
- Console stream: `CONSOLE_STREAM=stderr|stdout`
- File logging: `FILE_ENABLED`, `FILE_PATH`, `FILE_MAX_BYTES`, `FILE_BACKUP_COUNT`, `ROTATE_ON_STARTUP`
- Ring buffer: `RING_ENABLED`, `RING_SIZE`, `RING_DUMP_PATH`, `RING_DUMP_ON_UNHANDLED`

## PITSCSV format
Field order is fixed and includes a caller field (function:file:line) between function and message. Use this for structured ingestion and post-mortem analysis.

## Integration and migration
- Use startup-time `configure_logging(...)` at application entrypoints.
- Use `get_logger(__name__)` in modules and avoid direct root logger access.
- For migration from legacy wrappers, follow `/Users/rheiger/Dev/extended_python_logger/skills/extended-python-logger/references/migration.md`.
