"""Logging configuration for strava-backup.

Provides structured logging to console and file with configurable levels.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from strava_backup.config import Config

# Module logger
logger = logging.getLogger("strava_backup")


def setup_logging(
    config: "Config | None" = None,
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
        if config is not None:
            log_dir = config.data.directory / "logs"
        else:
            log_dir = Path("logs")

    # Create log directory if it doesn't exist
    log_dir.mkdir(parents=True, exist_ok=True)

    # File handler with timestamp-based filename (ISO 8601 basic format)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    log_file = log_dir / f"strava-backup-{timestamp}.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(file_level)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Also capture stravalib logs
    stravalib_logger = logging.getLogger("stravalib")
    stravalib_logger.setLevel(logging.DEBUG)
    stravalib_logger.addHandler(file_handler)

    logger.debug("Logging initialized. Log file: %s", log_file)

    return logger


def get_logger(name: str = "strava_backup") -> logging.Logger:
    """Get a logger for a module.

    Args:
        name: Logger name (usually __name__).

    Returns:
        Logger instance.
    """
    return logging.getLogger(name)
