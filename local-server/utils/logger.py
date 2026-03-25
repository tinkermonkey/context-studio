"""
Logging configuration for Context Studio.
"""

import logging
import logging.handlers
from pathlib import Path
from config import get_settings


def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger instance.

    Args:
        name: The name of the logger, typically __name__

    Returns:
        A configured logging.Logger instance
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        settings = get_settings()
        logging_config = settings.logging

        log_level = getattr(logging, logging_config.log_level.value)
        logger.setLevel(log_level)

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
        logger.addHandler(file_handler)

    return logger
