# Migration Playbook

## Goal
Replace existing logging interfaces with `extended_python_logger` while preserving behavior and avoiding duplicate handlers or broken observability.

## Baseline Integration
1. Add package dependency.
2. Configure once at process startup:
   - call `configure_logging(...)` in application entrypoint
   - otherwise rely on env configuration with `PYTHON_LOG_*`
3. Replace direct `logging.getLogger(__name__)` with `get_logger(__name__)`.
4. Keep console default `stderr` unless a deployment contract requires `stdout`.

## Replacement Mapping
- `logging.debug(...)` -> `logger.debug(...)`
- `logging.info(...)` -> `logger.info(...)`
- `logging.warning(...)` -> `logger.warning(...)`
- `logging.error(...)` -> `logger.error(...)`
- `logging.exception(...)` -> `logger.exception(...)`
- very noisy debug -> `logger.trace(...)`
- important non-warning operational events -> `logger.notice(...)`
- must always emit -> `logger.log(ALWAYS, ...)`
- ring-only forensic entry -> `logger.log(NEVER, ...)`

## Level Selection Rules
- `ALWAYS`:
  - Use for mandatory operational markers that must always be visible regardless of thresholds.
  - Examples: startup boundary markers, shutdown markers, irreversible state transitions.
- `CRITICAL`:
  - Use for system-level failure where process/service health is at risk or immediate intervention is required.
- `ERROR`:
  - Use for failed operations that did not complete correctly and are not expected in normal flow.
- `WARNING`:
  - Use for abnormal but recoverable conditions requiring attention.
- `NOTICE`:
  - Use for important normal-operation events that should stand out but are not warnings.
  - Examples: config source selected, fallback mode enabled by design, major phase completed.
- `INFO`:
  - Use for normal operational progress without urgency.
- `DEBUG`:
  - Use for developer-focused diagnostic detail useful during active debugging.
- `TRACE`:
  - Use for very high-volume fine-grained flow/state tracing, typically file-only.
- `NEVER`:
  - Use only for ring-buffer forensic breadcrumbs that should never go to console/file.

## Exception Policy
- In `except` blocks, default to `logger.exception(...)`.
- Use `INFO` or `NOTICE` only when the exception is expected and fully handled.
- Do not downgrade unexpected exceptions to `INFO`/`NOTICE`.

## Safe Rollout Strategy
1. Adapter phase:
   - keep old logger wrapper API, route internals to `extended_python_logger`.
   - preserve call sites first, change semantics second.
2. Direct call phase:
   - gradually replace wrapper usage with direct `get_logger()` and standard methods.
3. Cleanup phase:
   - remove legacy wrapper and dead env vars.

## Validation Checklist
- no duplicate handlers attached to root logger
- console level and file level match env/runtime expectation
- per-logger overrides work for both console and file
- `NEVER` does not appear on console or file
- `ALWAYS` emits regardless of threshold
- ring buffer dumps on unhandled exceptions only
- PITSCSV includes caller field (`function:file:line`)

## Common Pitfalls
- calling `configure_logging()` repeatedly in multiple modules
- mixing app-specific env prefixes with `PYTHON_LOG_*`
- forcing `stdout` in environments expecting error logs on `stderr`
- replacing `logger.exception()` with `logger.error(..., exc_info=False)`
