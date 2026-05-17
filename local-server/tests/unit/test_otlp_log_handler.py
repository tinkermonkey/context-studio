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

    def emit(self, record):
        """Emit a log record."""
        # Handle OTel LogRecord (from SDK's LoggingHandler translation)
        attributes = record.attributes or {}

        self.logged_messages.append({
            "message": record.body,
            "severity_text": record.severity_text,
            "severity_number": record.severity_number,
            "trace_id": record.trace_id,
            "span_id": record.span_id,
            "attributes": attributes
        })


class MockLoggerProvider:
    """Mock OpenTelemetry logger provider for testing."""

    def __init__(self):
        """Initialize the mock provider."""
        self.logger = MockLogger()

    def get_logger(self, name, version=None, schema_url=None, attributes=None):
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
    assert logged["severity_text"] == "INFO"


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
    # trace_id and span_id should be 0 (invalid) when not in a span
    assert logged["trace_id"] == 0
    assert logged["span_id"] == 0


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

    # Check level mapping (OTel SDK normalizes WARNING to WARN)
    expected_levels = ["DEBUG", "INFO", "WARN", "ERROR", "FATAL"]

    for idx, expected_level in enumerate(expected_levels):
        logged = provider.logger.logged_messages[idx]
        assert logged["severity_text"] == expected_level
