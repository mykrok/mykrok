"""Logging configuration for MyKrok.

Provides structured logging to console and file with configurable levels.
"""

from __future__ import annotations

import atexit
import contextlib
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mykrok.config import Config

# Module logger
logger = logging.getLogger("mykrok")

# Track current log file for cleanup
_current_log_file: Path | None = None
_file_handler: logging.FileHandler | None = None
_cleanup_registered: bool = False


def setup_logging(
    config: Config | None = None,
    log_dir: Path | None = None,
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
    quiet: bool = False,
) -> logging.Logger:
    """Set up logging for strava-backup.

    Creates handlers for:
    - Console output at INFO level (or WARNING if quiet)
    - File output at DEBUG level in logs/ directory

    Args:
        config: Application config (for log_dir from data directory).
        log_dir: Explicit log directory path.
        console_level: Log level for console output.
        file_level: Log level for file output.
        quiet: If True, console only shows warnings and errors.

    Returns:
        Configured logger.
    """
    # Clear existing handlers
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.WARNING if quiet else console_level)
    console_formatter = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # Determine log directory
    if log_dir is None:
        log_dir = config.data.directory / "logs" if config is not None else Path("logs")

    # Create log directory if it doesn't exist
    log_dir.mkdir(parents=True, exist_ok=True)

    # File handler with timestamp-based filename (ISO 8601 basic format)
    global _current_log_file, _file_handler

    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    log_file = log_dir / f"mykrok-{timestamp}.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(file_level)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Track for cleanup
    _current_log_file = log_file
    _file_handler = file_handler

    # Register cleanup on exit (only once)
    global _cleanup_registered
    if not _cleanup_registered:
        atexit.register(cleanup_empty_log)
        _cleanup_registered = True

    # Also capture stravalib logs
    stravalib_logger = logging.getLogger("stravalib")
    stravalib_logger.setLevel(logging.DEBUG)
    stravalib_logger.addHandler(file_handler)

    logger.debug("Logging initialized. Log file: %s", log_file)

    return logger


def get_logger(name: str = "mykrok") -> logging.Logger:
    """Get a logger for a module.

    Args:
        name: Logger name (usually __name__).

    Returns:
        Logger instance.
    """
    return logging.getLogger(name)


def cleanup_empty_log() -> None:
    """Remove log file if it only contains the initialization message.

    This prevents accumulation of empty log files when commands complete
    without logging anything meaningful.
    """
    global _current_log_file, _file_handler

    if _current_log_file is None or _file_handler is None:
        return

    if not _current_log_file.exists():
        return

    # Close the file handler first to ensure all writes are flushed
    _file_handler.close()
    logger.removeHandler(_file_handler)

    # Also remove from stravalib logger
    stravalib_logger = logging.getLogger("stravalib")
    stravalib_logger.removeHandler(_file_handler)

    # Check if log file has only the initialization line
    try:
        with open(_current_log_file, encoding="utf-8") as f:
            lines = f.readlines()

        # If only one line and it's the init message, remove the file
        if len(lines) == 1 and "Logging initialized" in lines[0]:
            _current_log_file.unlink()
    except OSError:
        # If we can't read/remove the file, just leave it
        pass

    # Reset globals
    _current_log_file = None
    _file_handler = None


def force_cleanup_log() -> None:
    """Force removal of the current log file regardless of content.

    Used by lean_update mode to remove log files when sync completes
    with no meaningful changes (no new activities, photos, etc.).
    """
    global _current_log_file, _file_handler

    if _current_log_file is None or _file_handler is None:
        return

    if not _current_log_file.exists():
        return

    # Close the file handler first to ensure all writes are flushed
    _file_handler.close()
    logger.removeHandler(_file_handler)

    # Also remove from stravalib logger
    stravalib_logger = logging.getLogger("stravalib")
    stravalib_logger.removeHandler(_file_handler)

    # Remove the log file (ignore errors if we can't)
    with contextlib.suppress(OSError):
        _current_log_file.unlink()

    # Reset globals
    _current_log_file = None
    _file_handler = None
