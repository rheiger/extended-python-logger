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

## Level decision policy
- `ALWAYS`: mandatory operational markers that must be visible regardless of thresholds.
- `CRITICAL`: service/process health at risk.
- `ERROR`: operation failed unexpectedly.
- `WARNING`: abnormal but recoverable condition.
- `NOTICE`: important normal-operation event, no fault implied.
- `INFO`: normal progress without urgency.
- `DEBUG`: developer diagnostics.
- `TRACE`: high-volume low-level tracing.
- `NEVER`: ring-only forensic breadcrumb, never console/file.

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

## Integration and replacement
- Configure logging once in the process entrypoint with `configure_logging(...)` or `PYTHON_LOG_*`.
- Use `get_logger(__name__)` in modules instead of direct `logging.getLogger(...)`.
- For phased replacement of legacy wrappers/interfaces, follow `skills/extended-python-logger/references/migration.md`.
- Prefer adapter-first migration to reduce risk:
  - keep old API shape, route internals to `extended_python_logger`
  - migrate callsites incrementally
  - remove legacy wrapper only after behavior parity is verified

## Rollout validation
- Check there are no duplicate root handlers.
- Verify per-logger console/file overrides work as expected.
- Verify `ALWAYS` emits regardless of thresholds.
- Verify `NEVER` is ring-buffer only.
- Verify ring dumps occur for unhandled exceptions only.
