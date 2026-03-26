"""
Logging configuration for Context Studio.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from config import get_settings


_logger_cache = {}
_handlers_initialized = False


def _initialize_handlers() -> None:
    """
    Initialize file handlers for all cached loggers.

    This is deferred from module import time to avoid filesystem access
    during test collection in sandboxed environments.
    """
    global _handlers_initialized
    if _handlers_initialized:
        return

    try:
        settings = get_settings()
        logging_config = settings.logging

        log_level = getattr(logging, logging_config.log_level.value)

        log_dir = Path(__file__).parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)

        log_file = log_dir / "context_studio.log"

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=logging_config.max_bytes,
            backupCount=logging_config.backup_count,
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)

        # Add handler to all cached loggers
        for logger in _logger_cache.values():
            if not logger.handlers:
                logger.addHandler(file_handler)
            logger.setLevel(log_level)

        _handlers_initialized = True
    except Exception:
        # If file handler setup fails (e.g., read-only filesystem),
        # fall back to stderr handler for logging
        fallback_handler = logging.StreamHandler(sys.stderr)
        fallback_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        for logger in _logger_cache.values():
            if not logger.handlers:
                logger.addHandler(fallback_handler)
        _handlers_initialized = True


def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger instance.

    Logger file handlers are initialized lazily on first use to avoid
    filesystem access during test collection.

    Args:
        name: The name of the logger, typically __name__

    Returns:
        A configured logging.Logger instance
    """
    if name not in _logger_cache:
        _logger_cache[name] = logging.getLogger(name)

    logger = _logger_cache[name]

    # Ensure handlers are initialized before returning
    _initialize_handlers()

    return logger
