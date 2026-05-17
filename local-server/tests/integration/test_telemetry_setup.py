"""
Integration tests for telemetry setup including log handling.
"""

import sys
import os
import logging
from unittest.mock import Mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import TelemetryConfig, TelemetryProtocol
from adapters.telemetry import setup_telemetry
from adapters.telemetry.log_bridge import OTLPLogHandler


def test_telemetry_disabled_no_log_exporter():
    """Test that log exporter is None when telemetry is disabled."""
    config = TelemetryConfig(enabled=False)
    lifecycle = setup_telemetry(config)

    assert lifecycle.get_log_exporter() is None


def test_telemetry_enabled_with_log_export():
    """Test that log exporter is created when telemetry is enabled."""
    config = TelemetryConfig(
        enabled=True,
        export_logs=True,
        export_traces=False,
        protocol=TelemetryProtocol.HTTP,
        otlp_endpoint_http="http://localhost:4318",
        otlp_endpoint_grpc="http://localhost:4317",
    )
    lifecycle = setup_telemetry(config)

    assert lifecycle.get_log_exporter() is not None


def test_otlp_log_handler_registration():
    """Test that OTLP log handler can be registered with loggers."""
    mock_exporter = Mock()
    mock_exporter.export = Mock(return_value=0)
    mock_exporter.shutdown = Mock()

    handler = OTLPLogHandler(mock_exporter)
    logger = logging.getLogger("test_integration_logger")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    logger.info("Test log message")

    # Verify exporter was called
    assert mock_exporter.export.called
    exported_logs = mock_exporter.export.call_args[0][0]
    assert len(exported_logs) == 1
    assert exported_logs[0]["body"] == "Test log message"


def test_rotating_file_handler_still_active():
    """Test that rotating file handler is still registered."""
    from utils.logger import _get_handler

    handler = _get_handler()
    assert handler is not None
    assert hasattr(handler, "baseFilename") or hasattr(handler, "stream")
