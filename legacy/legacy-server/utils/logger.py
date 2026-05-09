import logging
from logging.handlers import TimedRotatingFileHandler
import os


class ColorFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[94m",  # Blue
        "INFO": "\033[92m",  # Green
        "WARNING": "\033[93m",  # Yellow
        "ERROR": "\033[91m",  # Red
        "CRITICAL": "\033[95m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        msg = super().format(record)
        return f"{color}{msg}{self.RESET}"


def get_logger(name: str = "context_studio"):
    logger = logging.getLogger(name)
    if not logger.handlers:
        # Console handler with color
        stream_handler = logging.StreamHandler()
        formatter = ColorFormatter(
            "[%(asctime)s] %(levelname)s in %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"
        )  # noqa: E501
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

        # File handler with daily rotation, keep 5 days
        log_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs"
        )  # noqa: E501
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "context_studio.log")
        file_handler = TimedRotatingFileHandler(
            log_file, when="midnight", backupCount=5, encoding="utf-8"
        )  # noqa: E501
        file_formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s in %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"
        )  # noqa: E501
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    logger.setLevel(logging.INFO)
    return logger
