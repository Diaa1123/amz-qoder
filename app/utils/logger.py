"""AMZ_Designy - Structured logging setup."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOGGERS: dict[str, logging.Logger] = {}

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DIR = Path("logs")


def setup_logger(
    name: str,
    log_level: str = "INFO",
) -> logging.Logger:
    """Create or reconfigure a logger with console and file handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    if logger.handlers:
        return logger

    formatter = logging.Formatter(LOG_FORMAT)

    # Console handler
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # File handler (rotating)
    LOG_DIR.mkdir(exist_ok=True)
    file_handler = RotatingFileHandler(
        LOG_DIR / "app.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger


def get_logger(name: str, log_level: str = "INFO") -> logging.Logger:
    """Get or create a logger by name."""
    if name not in _LOGGERS:
        _LOGGERS[name] = setup_logger(name, log_level)
    return _LOGGERS[name]
