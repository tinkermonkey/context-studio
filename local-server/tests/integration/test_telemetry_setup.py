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
    """Test that logger provider is None when telemetry is disabled."""
    config = TelemetryConfig(enabled=False)
    lifecycle = setup_telemetry(config)

    assert lifecycle.get_logger_provider() is None


def test_telemetry_enabled_with_log_export():
    """Test that logger provider is created when telemetry is enabled with log export."""
    config = TelemetryConfig(
        enabled=True,
        export_logs=True,
        export_traces=False,
        protocol=TelemetryProtocol.HTTP,
        otlp_endpoint_http="http://localhost:4318",
        otlp_endpoint_grpc="http://localhost:4317",
    )
    lifecycle = setup_telemetry(config)

    assert lifecycle.get_logger_provider() is not None


def test_otlp_log_handler_registration():
    """Test that OTLP log handler can be registered with loggers."""
    mock_logger_provider = Mock()
    mock_logger = Mock()
    mock_logger_provider.get_logger = Mock(return_value=mock_logger)

    handler = OTLPLogHandler(mock_logger_provider)
    logger = logging.getLogger("test_integration_logger")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    logger.info("Test log message")

    # Verify logger provider was called
    assert mock_logger_provider.get_logger.called
    assert mock_logger.info.called
    call_args = mock_logger.info.call_args
    assert call_args[0][0] == "Test log message"


def test_rotating_file_handler_still_active():
    """Test that rotating file handler is still registered."""
    from utils.logger import _get_handler

    handler = _get_handler()
    assert handler is not None
    assert hasattr(handler, "baseFilename") or hasattr(handler, "stream")
