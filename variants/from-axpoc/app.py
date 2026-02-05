#!/usr/bin/env python3
"""
AXPOC Assessment Report Generator - Step 8 ENHANCED DEBUG VERSION
Enhanced debugging with advanced logging system for troubleshooting startup issues.
"""

import os
import sys
import traceback

try:
    # Set up logging environment variables (default to DEBUG for normal operation)
    os.environ.setdefault("AXPOC_LOG_LEVEL", "DEBUG")
    os.environ.setdefault("AXPOC_CONSOLE_FORMAT", "EXTENDED")
    os.environ.setdefault("AXPOC_FILE_FORMAT", "EXTENDED")

    # Import and configure our enhanced logging system
    from src.utils.log_config import configure_logging, get_logger

    log_level = os.environ.get(
        "AXPOC_CONSOLE_LOG_LEVEL", os.environ.get("AXPOC_LOG_LEVEL", "DEBUG")
    )
    file_level = os.environ.get("AXPOC_FILE_LOG_LEVEL", log_level)
    console_fmt = os.environ.get("AXPOC_CONSOLE_FORMAT", "EXTENDED")
    file_fmt = os.environ.get("AXPOC_FILE_FORMAT", "EXTENDED")
    configure_logging(
        level=log_level,
        file_level=file_level,
        console_format=console_fmt,
        file_format=file_fmt,
        enable_file_logging=True,
    )

    # Suppress noisy third-party loggers (httpx/httpcore log every HTTP request at INFO)
    import logging as _logging
    _logging.getLogger("httpx").setLevel(_logging.WARNING)
    _logging.getLogger("httpcore").setLevel(_logging.WARNING)
    _logging.getLogger("httpcore.connection").setLevel(_logging.WARNING)
    _logging.getLogger("httpcore.http11").setLevel(_logging.WARNING)

    # Get our logger
    logger = get_logger(__name__)
    logger.notice("🚀 Logging system initialized")
    logger.debug("Logger created successfully with configured level")

    # Ensure a file log handler exists (Gunicorn may replace handlers). If missing, reattach.
    try:
        import logging as _logging
        from logging import handlers as _handlers

        from src.utils.log_config import CallerInfoFilter as _CallerInfoFilter
        from src.utils.log_config import LevelBasedFormatter as _LevelBasedFormatter
        from src.utils.log_config import get_log_format as _get_log_format
        from src.utils.log_config import get_log_level as _get_log_level

        _root = _logging.getLogger()
        _has_file = any(
            isinstance(h, _handlers.RotatingFileHandler) for h in _root.handlers
        )
        if not _has_file:
            _path = os.environ.get("AXPOC_LOG_FILE_PATH", "/app/logs/axpoc.log")
            try:
                _dir = os.path.dirname(_path)
                if _dir:
                    os.makedirs(_dir, exist_ok=True)
            except Exception as e:
                logger.exception("Error creating log directory | error=%s", str(e))

            _max_bytes = int(
                os.environ.get("AXPOC_LOG_FILE_MAX_BYTES", str(100 * 1024 * 1024))
            )
            _backup_count = int(os.environ.get("AXPOC_LOG_FILE_BACKUP_COUNT", "10"))
            _fh = _handlers.RotatingFileHandler(
                _path, maxBytes=_max_bytes, backupCount=_backup_count
            )

            _eff_file_level = os.environ.get("AXPOC_FILE_LOG_LEVEL", "DEBUG")
            _fh.setLevel(_get_log_level(_eff_file_level))

            _file_format_name = os.environ.get("AXPOC_FILE_FORMAT", "EXTENDED")
            _fmt_str = _get_log_format(_file_format_name)
            _level_map = {
                getattr(_logging, "TRACE", 5): _fmt_str,
                _logging.DEBUG: _fmt_str,
                _logging.INFO: _fmt_str,
                getattr(_logging, "NOTICE", 25): _fmt_str,
                _logging.WARNING: _fmt_str,
                _logging.ERROR: _fmt_str,
                _logging.CRITICAL: _fmt_str,
            }
            _fh.setFormatter(_LevelBasedFormatter(_fmt_str, _level_map))
            _fh.addFilter(_CallerInfoFilter())

            _root.addHandler(_fh)
            logger.notice("File log handler attached at runtime (missing at startup)")
    except Exception as _e:
        logger.exception(f"File logging verify/attach skipped: {_e}")

    # Ensure a console log handler exists (Gunicorn dictConfig may clear handlers)
    try:
        import sys as _sys

        import logging as _logging2

        from src.utils.log_config import CallerInfoFilter as _CallerInfoFilter2
        from src.utils.log_config import LevelBasedFormatter as _LevelBasedFormatter2
        from src.utils.log_config import get_log_format as _get_log_format2
        from src.utils.log_config import get_log_level as _get_log_level2

        _root2 = _logging2.getLogger()
        # Check if there's a StreamHandler writing to stderr
        _has_console = any(
            isinstance(h, _logging2.StreamHandler)
            and getattr(h, "stream", None) is _sys.stderr
            for h in _root2.handlers
        )
        if not _has_console:
            _eff_console_level = os.environ.get(
                "AXPOC_CONSOLE_LOG_LEVEL",
                os.environ.get("AXPOC_LOG_LEVEL", "DEBUG"),
            )
            _ch = _logging2.StreamHandler(_sys.stderr)
            _ch.setLevel(_get_log_level2(_eff_console_level))

            _console_format_name = os.environ.get("AXPOC_CONSOLE_FORMAT", "EXTENDED")
            _fmt_str2 = _get_log_format2(_console_format_name)
            _level_map2 = {
                getattr(_logging2, "TRACE", 5): _fmt_str2,
                _logging2.DEBUG: _fmt_str2,
                _logging2.INFO: _fmt_str2,
                getattr(_logging2, "NOTICE", 25): _fmt_str2,
                _logging2.WARNING: _fmt_str2,
                _logging2.ERROR: _fmt_str2,
                _logging2.CRITICAL: _fmt_str2,
            }
            _ch.setFormatter(_LevelBasedFormatter2(_fmt_str2, _level_map2))
            _ch.addFilter(_CallerInfoFilter2())

            _root2.addHandler(_ch)
            logger.notice("Console log handler attached at runtime (missing at startup)")
    except Exception as _e2:
        logger.exception(f"Console logging verify/attach skipped: {_e2}")

    # Import version utility AFTER logging is configured to avoid early reconfiguration
    from src.utils.version import get_version as _get_version


except Exception as e:
    traceback.print_exc()
    sys.exit(1)

logger.info("🔄 ENHANCED DEBUG: Starting Flask imports")

try:
    from flask import Flask

    logger.debug("Flask core imports successful")
except Exception as e:
    logger.critical(f"Failed to import Flask: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    from werkzeug.middleware.proxy_fix import ProxyFix

    logger.debug("Werkzeug imports successful")
except Exception as e:
    logger.critical(f"Failed to import Werkzeug: {e}")
    traceback.print_exc()
    sys.exit(1)

logger.info("🔄 ENHANCED DEBUG: Starting configuration imports")

try:
    from src.config import get_config

    logger.debug("Configuration imports successful")
except Exception as e:
    logger.critical(f"Failed to import configuration: {e}")
    traceback.print_exc()
    sys.exit(1)

logger.info("🔄 ENHANCED DEBUG: Starting exceptions imports")


# NOTE: Delegate version retrieval to cached utility
def get_version():
    try:
        v = _get_version()
        logger.trace(f"Version read: {v}")
        return v
    except Exception as e:
        logger.exception(f"Error reading version: {e}")
        return "unknown"


def create_app(config=None):
    """
    Application factory for creating Flask application instances.
    Enhanced with comprehensive debug logging.
    """
    logger.info("🏭 Starting application factory")

    try:
        logger.debug("Creating Flask application instance")
        app = Flask(__name__)
        # Ensure real client IP and scheme are available behind Traefik
        # ProxyFix trusts X-Forwarded-* headers that Gunicorn has been
        # configured to allow via --forwarded-allow-ips.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
        logger.notice("ProxyFix enabled: trusting X-Forwarded-* headers for client IP")
        logger.info("✅ Flask application instance created successfully")

        # Cursor debug logging (opt-in, for local development only)
        # Set CURSOR_DEBUG_ENABLED=true to enable. Logs to /app/logs/cursor_debug.log in containers
        # or .cursor/debug.log in local development.
        import os as _os
        from pathlib import Path as _Path

        _CURSOR_DEBUG_ENABLED = _os.getenv("CURSOR_DEBUG_ENABLED", "").lower() == "true"

        def _get_cursor_debug_log_path() -> str:
            """Get cursor debug log path - container-safe or local dev."""
            # Check explicit path override
            env_path = _os.getenv("CURSOR_DEBUG_LOG_PATH")
            if env_path:
                return env_path

            # In containers, use /app/logs (standard logs directory)
            container_logs = _Path("/app/logs")
            if container_logs.exists() and container_logs.is_dir():
                return str(container_logs / "cursor_debug.log")

            # Local development: try to find project root
            current = _Path(__file__).resolve()
            for parent in [current] + list(current.parents):
                if (parent / "docker-compose.yml").exists() or (parent / ".git").exists():
                    cursor_dir = parent / ".cursor"
                    return str(cursor_dir / "debug.log")

            # Fallback: /tmp (always writable)
            return "/tmp/cursor_debug.log"

        _cursor_debug_log_path = _get_cursor_debug_log_path() if _CURSOR_DEBUG_ENABLED else None

        def _agent_debug_log(
            *,
            hypothesis_id: str,
            location: str,
            message: str,
            data: dict,
            run_id: str = "run1",
        ) -> None:
            """Write a single NDJSON line for Cursor debug-mode (no secrets/PII).

            Only active if CURSOR_DEBUG_ENABLED=true. Silently does nothing otherwise.
            """
            if not _CURSOR_DEBUG_ENABLED or not _cursor_debug_log_path:
                return

            try:
                import json as _json
                import time as _time

                log_file = _Path(_cursor_debug_log_path)
                log_file.parent.mkdir(parents=True, exist_ok=True)
                payload = {
                    "sessionId": "debug-session",
                    "runId": run_id,
                    "hypothesisId": hypothesis_id,
                    "location": location,
                    "message": message,
                    "data": data,
                    "timestamp": int(_time.time() * 1000),
                }
                with open(log_file, "a", encoding="utf-8") as _f:
                    _f.write(_json.dumps(payload, ensure_ascii=False) + "\n")
            except Exception:
                # Never break request handling due to debug logging
                return

        try:
            from flask import request as _req

            @app.before_request
            def _agent_debug_before_request():  # type: ignore[misc]
                try:
                    path = str(getattr(_req, "path", "") or "")
                    if "reports" not in path:
                        return None
                    endpoint = getattr(_req, "endpoint", None)
                    rule = None
                    try:
                        rule_obj = getattr(_req, "url_rule", None)
                        rule = str(getattr(rule_obj, "rule", rule_obj) or "")
                    except Exception:
                        rule = None
                    env = getattr(_req, "environ", {}) or {}
                    # region agent log
                    _agent_debug_log(
                        hypothesis_id="H1",
                        location="src/app.py:create_app.before_request",
                        message="report_request_seen",
                        data={
                            "method": getattr(_req, "method", None),
                            "path": path,
                            "endpoint": endpoint,
                            "url_rule": rule,
                            "script_name": env.get("SCRIPT_NAME"),
                            "path_info": env.get("PATH_INFO"),
                            "raw_uri": env.get("RAW_URI"),
                        },
                    )
                    # endregion
                    return None
                except Exception:
                    return None

        except Exception as _e:
            logger.debug("Debug before_request instrumentation not installed: %s", _e)
    except Exception as e:
        logger.critical(f"Failed to create Flask instance: {e}")
        traceback.print_exc()
        raise

    try:
        logger.debug("Loading application configuration")
        app_config = get_config()
        logger.info("✅ Configuration loaded successfully")
        logger.debug(f"Configuration object type: {type(app_config)}")
    except Exception as e:
        logger.critical(f"Failed to load configuration: {e}")
        traceback.print_exc()
        raise

    # Lots of code stripped out for brevity

    return app


# For development/testing
if __name__ == "__main__":
    logger.warning("Running in development mode - use Gunicorn for production")
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=8080)
