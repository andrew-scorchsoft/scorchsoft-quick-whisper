"""
Application logging for QuickWhisper.

The packaged (windowed) build has no console, so every ``print()`` in the
application used to vanish - which meant user bug reports arrived with no
evidence attached. This module sets up a rotating log file alongside the
existing console output, so a user can be asked for their log.

Usage from any module::

    from utils.app_logging import get_logger
    logger = get_logger(__name__)
    logger.info("Recording started")

Call :func:`setup_logging` once, as early as possible during startup.
"""

import logging
import logging.handlers
import platform
import sys
from pathlib import Path

from utils.paths import get_log_dir

LOG_FILENAME = "quickwhisper.log"
MAX_BYTES = 1_000_000  # ~1 MB per file
BACKUP_COUNT = 3  # keep 3 rotated files, so ~4 MB total

_configured = False
_log_file_path: Path | None = None


def setup_logging(level: int = logging.INFO, console: bool = True) -> Path | None:
    """Configure root logging with a rotating file handler.

    Safe to call more than once; subsequent calls are no-ops.

    Returns:
        The path of the log file, or None if file logging could not be set up.
    """
    global _configured, _log_file_path
    if _configured:
        return _log_file_path

    root = logging.getLogger()
    root.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)-28s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if console and sys.stderr is not None:
        try:
            stream = logging.StreamHandler(sys.stderr)
            stream.setFormatter(formatter)
            root.addHandler(stream)
        except Exception:
            pass

    try:
        log_path = get_log_dir() / LOG_FILENAME
        file_handler = logging.handlers.RotatingFileHandler(
            log_path, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
        _log_file_path = log_path
    except Exception as exc:  # pragma: no cover - logging must never be fatal
        root.warning("Could not create log file: %s", exc)
        _log_file_path = None

    # Third-party libraries are noisy at INFO; keep them at WARNING.
    for noisy in ("openai", "httpx", "httpcore", "urllib3", "PIL", "comtypes"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True

    root.info("=" * 60)
    root.info("QuickWhisper starting - %s %s / Python %s",
              platform.system(), platform.release(), platform.python_version())
    if _log_file_path:
        root.info("Log file: %s", _log_file_path)
    return _log_file_path


def get_logger(name: str) -> logging.Logger:
    """Get a module-scoped logger."""
    return logging.getLogger(name)


def get_log_file_path() -> Path | None:
    """Path of the active log file, if file logging is configured."""
    return _log_file_path


def log_exception(logger: logging.Logger, message: str, exc: BaseException) -> None:
    """Log an exception with a traceback, at error level."""
    logger.error("%s: %s", message, exc, exc_info=True)
