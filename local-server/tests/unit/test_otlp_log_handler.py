"""
Tests for the OTLP log handler.
"""

import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from adapters.telemetry.log_bridge import OTLPLogHandler, SimpleOTLPLogExporter


class MockLogExporter:
    """Mock log exporter for testing."""

    def __init__(self):
        """Initialize the mock exporter."""
        self.exported_logs = []

    def export(self, logs):
        """Export logs."""
        self.exported_logs.extend(logs)
        return 0

    def shutdown(self):
        """Shutdown the exporter."""
        pass


def test_otlp_log_handler_exports_logs():
    """Test that OTLP log handler exports log records."""
    exporter = MockLogExporter()
    handler = OTLPLogHandler(exporter)

    logger = logging.getLogger("test_logger")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    logger.info("Test message")

    assert len(exporter.exported_logs) == 1
    log_record = exporter.exported_logs[0]
    assert log_record["body"] == "Test message"
    assert log_record["severity_text"] == "INFO"
    assert log_record["severity_number"] == 9  # INFO level


def test_otlp_log_handler_without_trace_context():
    """Test that log handler doesn't inject trace_id/span_id outside a span."""
    exporter = MockLogExporter()
    handler = OTLPLogHandler(exporter)

    logger = logging.getLogger("test_logger_no_trace")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    logger.warning("No trace")

    assert len(exporter.exported_logs) == 1
    log_record = exporter.exported_logs[0]
    assert "trace_id" not in log_record["attributes"]
    assert "span_id" not in log_record["attributes"]


def test_otlp_log_handler_different_levels():
    """Test that OTLP log handler handles different log levels."""
    exporter = MockLogExporter()
    handler = OTLPLogHandler(exporter)

    logger = logging.getLogger("test_levels")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
    logger.critical("Critical message")

    assert len(exporter.exported_logs) == 5

    # Check severity mapping
    levels = [
        (0, "DEBUG", 5),
        (1, "INFO", 9),
        (2, "WARNING", 13),
        (3, "ERROR", 17),
        (4, "CRITICAL", 21),
    ]

    for idx, expected_text, expected_number in levels:
        log = exporter.exported_logs[idx]
        assert log["severity_text"] == expected_text
        assert log["severity_number"] == expected_number


def test_simple_otlp_log_exporter():
    """Test that SimpleOTLPLogExporter accepts logs."""
    exporter = SimpleOTLPLogExporter("http://localhost:4318")

    # Should return 0 (success)
    result = exporter.export([{"body": "test"}])
    assert result == 0

    # Should not raise on shutdown
    exporter.shutdown()
