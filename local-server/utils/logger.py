"""
Logging configuration for Context Studio.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from config import get_settings


_file_handler: logging.Handler | None = None
_handler_init_attempted = False


def _get_handler() -> logging.Handler:
    """
    Initialize and return a shared handler for all loggers.

    The handler is created once on first call. If file handler setup fails
    (e.g., read-only filesystem), falls back to stderr handler.

    Returns:
        A logging.Handler instance (either RotatingFileHandler or StreamHandler)
    """
    global _file_handler, _handler_init_attempted
    if _handler_init_attempted:
        assert _file_handler is not None
        return _file_handler

    _handler_init_attempted = True

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        settings = get_settings()
        logging_config = settings.logging

        log_level = getattr(logging, logging_config.log_level.value)

        log_dir = Path(__file__).parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)

        log_file = log_dir / "context_studio.log"

        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=logging_config.max_bytes,
            backupCount=logging_config.backup_count,
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)

        _file_handler = file_handler
    except OSError as e:
        # If file handler setup fails (e.g., read-only filesystem),
        # fall back to stderr handler and print diagnostic message
        print(f"Warning: Could not set up file logging: {e}", file=sys.stderr)
        fallback_handler = logging.StreamHandler(sys.stderr)
        fallback_handler.setFormatter(formatter)
        fallback_handler.setLevel(logging.INFO)
        _file_handler = fallback_handler

    return _file_handler


def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger instance.

    Logger handlers are initialized lazily on first use to avoid
    filesystem access during test collection.

    Args:
        name: The name of the logger, typically __name__

    Returns:
        A configured logging.Logger instance with handlers attached
    """
    logger = logging.getLogger(name)

    # Attach handler if logger doesn't already have one
    if not logger.handlers:
        handler = _get_handler()
        if handler:
            logger.addHandler(handler)
            logger.setLevel(handler.level)

    return logger
