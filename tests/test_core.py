import csv
import importlib
import logging
import os
import sys
from pathlib import Path
from typing import Dict


def reload_core(monkeypatch, env: Dict[str, str]):
    repo_root = Path(__file__).resolve().parents[1]
    src_path = str(repo_root / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    for key in list(os.environ.keys()):
        if key.startswith("PYTHON_LOG_"):
            monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    import extended_python_logger.core as core

    core = importlib.reload(core)
    logging.getLogger().handlers.clear()
    return core


def test_levels_registered(monkeypatch):
    core = reload_core(monkeypatch, {})
    assert logging.getLevelName(core.TRACE) == "TRACE"
    assert logging.getLevelName(core.NOTICE) == "NOTICE"
    assert logging.getLevelName(core.ALWAYS) == "ALWAYS"
    assert logging.getLevelName(core.NEVER) == "NEVER"


def test_always_bypasses_filter(capsys, monkeypatch):
    core = reload_core(
        monkeypatch,
        {
            "PYTHON_LOG_CONSOLE_STREAM": "stdout",
            "PYTHON_LOG_CONSOLE_LEVEL": "CRITICAL",
            "PYTHON_LOG_FILE_ENABLED": "false",
            "PYTHON_LOG_RING_ENABLED": "false",
        },
    )
    core.configure_logging()
    logger = core.get_logger("test.always")
    logger.log(core.ALWAYS, "always emitted")
    out = capsys.readouterr().out
    assert "always emitted" in out


def test_never_ring_buffer_only(tmp_path, capsys, monkeypatch):
    core = reload_core(
        monkeypatch,
        {
            "PYTHON_LOG_CONSOLE_STREAM": "stdout",
            "PYTHON_LOG_CONSOLE_LEVEL": "INFO",
            "PYTHON_LOG_FILE_ENABLED": "false",
            "PYTHON_LOG_RING_ENABLED": "true",
        },
    )
    core.configure_logging()
    logger = core.get_logger("test.never")
    logger.log(core.NEVER, "never emitted")
    out = capsys.readouterr().out
    assert "never emitted" not in out

    dump_path = tmp_path / "ring.dump"
    core.dump_ring_buffer(str(dump_path))
    assert dump_path.read_text().find("never emitted") != -1


def test_ring_buffer_size(tmp_path, monkeypatch):
    core = reload_core(
        monkeypatch,
        {
            "PYTHON_LOG_RING_ENABLED": "true",
            "PYTHON_LOG_RING_SIZE": "3",
            "PYTHON_LOG_FILE_ENABLED": "false",
        },
    )
    core.configure_logging()
    logger = core.get_logger("test.ring")
    for i in range(5):
        logger.info("msg %d", i)

    dump_path = tmp_path / "ring.dump"
    core.dump_ring_buffer(str(dump_path))
    data = dump_path.read_text()
    assert "msg 0" not in data
    assert "msg 2" in data
    assert "msg 4" in data


def test_pitscsv_format_includes_caller(capsys, monkeypatch):
    core = reload_core(
        monkeypatch,
        {
            "PYTHON_LOG_CONSOLE_STREAM": "stdout",
            "PYTHON_LOG_CONSOLE_FORMAT": "PITSCSV",
            "PYTHON_LOG_FILE_ENABLED": "false",
        },
    )
    core.configure_logging()
    logger = core.get_logger("test.csv")
    logger.info("hello csv")
    line = capsys.readouterr().out.strip()
    fields = next(csv.reader([line]))
    assert len(fields) == 14
    assert ":" in fields[12]


def test_per_logger_console_override(capsys, monkeypatch):
    core = reload_core(
        monkeypatch,
        {
            "PYTHON_LOG_CONSOLE_STREAM": "stdout",
            "PYTHON_LOG_CONSOLE_LEVEL": "INFO",
            "PYTHON_LOG_CONSOLE_LEVEL_FOO_BAR": "ERROR",
            "PYTHON_LOG_FILE_ENABLED": "false",
        },
    )
    core.configure_logging()
    logger = core.get_logger("foo.bar")
    logger.debug("debug drop")
    logger.error("error keep")
    out = capsys.readouterr().out
    assert "debug drop" not in out
    assert "error keep" in out


def test_dump_on_unhandled_exception(tmp_path, monkeypatch):
    core = reload_core(
        monkeypatch,
        {
            "PYTHON_LOG_RING_ENABLED": "true",
            "PYTHON_LOG_RING_DUMP_PATH": str(tmp_path / "unhandled.dump"),
            "PYTHON_LOG_FILE_ENABLED": "false",
        },
    )
    core._ORIGINAL_SYS_EXCEPTHOOK = lambda *args, **kwargs: None
    core.configure_logging()
    logger = core.get_logger("test.unhandled")
    logger.info("before crash")

    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        core._handle_unhandled_exception(type(exc), exc, exc.__traceback__)

    dump_path = tmp_path / "unhandled.dump"
    assert dump_path.exists()
    assert "before crash" in dump_path.read_text()
