"""
Tests for the OTLP log handler.
"""

import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from adapters.telemetry.log_bridge import OTLPLogHandler


class MockLogger:
    """Mock OpenTelemetry logger for testing."""

    def __init__(self):
        """Initialize the mock logger."""
        self.logged_messages = []

    def debug(self, message, attributes=None):
        """Log a debug message."""
        self.logged_messages.append({"message": message, "level": "DEBUG", "attributes": attributes or {}})

    def info(self, message, attributes=None):
        """Log an info message."""
        self.logged_messages.append({"message": message, "level": "INFO", "attributes": attributes or {}})

    def warning(self, message, attributes=None):
        """Log a warning message."""
        self.logged_messages.append({"message": message, "level": "WARNING", "attributes": attributes or {}})

    def error(self, message, attributes=None):
        """Log an error message."""
        self.logged_messages.append({"message": message, "level": "ERROR", "attributes": attributes or {}})

    def critical(self, message, attributes=None):
        """Log a critical message."""
        self.logged_messages.append({"message": message, "level": "CRITICAL", "attributes": attributes or {}})


class MockLoggerProvider:
    """Mock OpenTelemetry logger provider for testing."""

    def __init__(self):
        """Initialize the mock provider."""
        self.logger = MockLogger()

    def get_logger(self, name):
        """Get a logger."""
        return self.logger


def test_otlp_log_handler_exports_logs():
    """Test that OTLP log handler exports log records through logger provider."""
    provider = MockLoggerProvider()
    handler = OTLPLogHandler(provider)

    logger = logging.getLogger("test_logger")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    logger.info("Test message")

    assert len(provider.logger.logged_messages) == 1
    logged = provider.logger.logged_messages[0]
    assert logged["message"] == "Test message"
    assert logged["level"] == "INFO"


def test_otlp_log_handler_without_trace_context():
    """Test that log handler doesn't inject trace_id/span_id outside a span."""
    provider = MockLoggerProvider()
    handler = OTLPLogHandler(provider)

    logger = logging.getLogger("test_logger_no_trace")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    logger.warning("No trace")

    assert len(provider.logger.logged_messages) == 1
    logged = provider.logger.logged_messages[0]
    assert "trace_id" not in logged["attributes"]
    assert "span_id" not in logged["attributes"]


def test_otlp_log_handler_different_levels():
    """Test that OTLP log handler handles different log levels."""
    provider = MockLoggerProvider()
    handler = OTLPLogHandler(provider)

    logger = logging.getLogger("test_levels")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
    logger.critical("Critical message")

    assert len(provider.logger.logged_messages) == 5

    # Check level mapping
    levels = [
        (0, "DEBUG"),
        (1, "INFO"),
        (2, "WARNING"),
        (3, "ERROR"),
        (4, "CRITICAL"),
    ]

    for idx, expected_level in levels:
        logged = provider.logger.logged_messages[idx]
        assert logged["level"] == expected_level
