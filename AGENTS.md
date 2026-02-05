# AI Agent Guidance - extended-python-logger

## Purpose
Provide consistent, high-fidelity logging with TRACE/NOTICE levels, ring-buffer support, and structured PITSCSV output for post-mortem debugging.

## Exception Handling
- Use `logger.exception()` inside `except` blocks unless the exception is expected and handled gracefully.
- For expected/handled exceptions, log at `INFO` or `NOTICE`.

## Log Levels
- `TRACE`: very noisy, prefer file logging.
- `NOTICE`: important but not a warning.
- `ALWAYS`: must always emit to console/file.
- `NEVER`: ring-buffer only (never console/file).

## Ring Buffer
- Enabled by default.
- Dumps to file on **unhandled exceptions only**.
- Configure with:
  - `PYTHON_LOG_RING_ENABLED`
  - `PYTHON_LOG_RING_SIZE`
  - `PYTHON_LOG_RING_DUMP_PATH`
  - `PYTHON_LOG_RING_DUMP_ON_UNHANDLED`

## Configuration (Env)
- Global: `PYTHON_LOG_LEVEL`, `PYTHON_LOG_CONSOLE_LEVEL`, `PYTHON_LOG_FILE_LEVEL`
- Per-logger overrides:
  - `PYTHON_LOG_LEVEL_<LOGGER>`
  - `PYTHON_LOG_CONSOLE_LEVEL_<LOGGER>`
  - `PYTHON_LOG_FILE_LEVEL_<LOGGER>`
- Formats:
  - `PYTHON_LOG_CONSOLE_FORMAT`, `PYTHON_LOG_FILE_FORMAT`
- Console stream:
  - `PYTHON_LOG_CONSOLE_STREAM=stderr|stdout`

## PITSCSV
When `PITSCSV` format is selected, ensure the caller field is available (function:file:line). This format is intended for structured ingestion and post-mortem analysis.
