"""
OTLP log handler that bridges Python logging to OTLP log export.

Injects trace_id and span_id into log records when emitted inside an active span,
enabling log-trace correlation in observability backends like SigNoz.

Uses a custom implementation compatible with current OpenTelemetry versions.
"""

import logging
from typing import Optional, Protocol

from opentelemetry import trace


_logger = logging.getLogger(__name__)


class LogExporter(Protocol):
    """Protocol for log exporters."""

    def export(self, logs: list) -> int:
        """Export log records."""
        ...

    def shutdown(self) -> None:
        """Shutdown the exporter."""
        ...


class OTLPLogHandler(logging.Handler):
    """
    Bridges Python logging output to OTLP log export.

    Converts Python LogRecords and injects trace context (trace_id, span_id)
    when emitted inside an active span.
    """

    def __init__(self, log_exporter: LogExporter):
        """
        Initialize the OTLP log handler.

        Args:
            log_exporter: Log exporter instance (e.g., GRPCLogExporter, HTTPLogExporter)
        """
        super().__init__()
        self.exporter = log_exporter

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record to OTLP.

        Injects trace_id and span_id if emitted inside an active span.

        Args:
            record: Python LogRecord to emit
        """
        try:
            # Get current active span context
            span_context = trace.get_current_span().get_span_context()

            # Build attributes dict
            attributes = {}

            # Only inject trace_id and span_id if inside an active span with valid trace
            if span_context and span_context.is_valid:
                attributes["trace_id"] = format(span_context.trace_id, "032x")
                attributes["span_id"] = format(span_context.span_id, "016x")

            # Create OTLP log record
            log_record = {
                "timestamp": int(record.created * 1e9),  # Convert to nanoseconds
                "severity_number": _severity_number(record.levelno),
                "severity_text": record.levelname,
                "body": record.getMessage(),
                "attributes": {
                    "logger.name": record.name,
                    **attributes,
                },
            }

            # Export the log record
            self.exporter.export([log_record])
        except Exception as e:
            # Fail gracefully — do not let logging errors crash the app
            self.handleError(record)


def _severity_number(level: int) -> int:
    """
    Map Python logging level to OpenTelemetry severity number.

    Args:
        level: Python logging level (DEBUG=10, INFO=20, etc.)

    Returns:
        OpenTelemetry severity number
    """
    # OpenTelemetry severity numbers
    # TRACE=1, DEBUG=5, INFO=9, WARN=13, ERROR=17, FATAL=21
    mapping = {
        logging.DEBUG: 5,
        logging.INFO: 9,
        logging.WARNING: 13,
        logging.ERROR: 17,
        logging.CRITICAL: 21,
    }
    return mapping.get(level, 9)  # Default to INFO


class SimpleOTLPLogExporter:
    """
    Simple OTLP log exporter that sends logs directly via HTTP.

    Falls back to no-op if exporting is not possible.
    """

    def __init__(self, endpoint: str):
        """
        Initialize the exporter.

        Args:
            endpoint: OTLP HTTP endpoint (e.g., http://localhost:4318)
        """
        self.endpoint = endpoint

    def export(self, logs: list) -> int:
        """
        Export log records (stub implementation).

        For now, this is a no-op. In a full implementation, this would
        batch and send logs to the OTLP collector.

        Args:
            logs: List of log records

        Returns:
            0 (success)
        """
        # TODO: Implement actual OTLP HTTP POST when logs SDK stabilizes
        return 0

    def shutdown(self) -> None:
        """Shutdown the exporter."""
        pass


def create_otlp_log_exporter(
    protocol: str, grpc_endpoint: str, http_endpoint: str
) -> Optional[LogExporter]:
    """
    Create an OTLP log exporter based on protocol.

    Args:
        protocol: "grpc" or "http"
        grpc_endpoint: gRPC collector endpoint URL
        http_endpoint: HTTP collector endpoint URL

    Returns:
        LogExporter instance, or None if creation fails
    """
    try:
        # Use the simple implementation for now
        # This will be replaced when OpenTelemetry logs SDK is stable
        endpoint = http_endpoint if protocol.lower() == "http" else grpc_endpoint
        exporter = SimpleOTLPLogExporter(endpoint)
        _logger.debug(f"Created log exporter for {endpoint}")
        return exporter
    except Exception as e:
        _logger.warning(
            f"Failed to create log exporter: {e}. Logs will not be exported to OTLP."
        )
        return None
