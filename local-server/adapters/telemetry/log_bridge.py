"""
OTLP log handler that bridges Python logging to OTLP log export.

Injects trace_id and span_id into log records when emitted inside an active span,
enabling log-trace correlation in observability backends like SigNoz.

Integrates with OpenTelemetry SDK's LoggerProvider and BatchLogRecordProcessor
for non-blocking, batched log export.
"""

import logging
from typing import Optional, TYPE_CHECKING

from opentelemetry import trace

try:
    from opentelemetry.sdk._logs import LoggerProvider
except ImportError:
    LoggerProvider = None

if TYPE_CHECKING:
    from opentelemetry.sdk._logs import LoggerProvider as LoggerProviderType

_logger = logging.getLogger(__name__)


class OTLPLogHandler(logging.Handler):
    """
    Bridges Python logging output to OTLP log export via OpenTelemetry LoggerProvider.

    Converts Python LogRecords and injects trace context (trace_id, span_id)
    when emitted inside an active span. Routes through LoggerProvider with
    BatchLogRecordProcessor for batched, non-blocking export.
    """

    def __init__(self, logger_provider: Optional["LoggerProviderType"]):
        """
        Initialize the OTLP log handler.

        Args:
            logger_provider: OpenTelemetry LoggerProvider instance with BatchLogRecordProcessor
        """
        super().__init__()
        self.logger_provider = logger_provider
        self.logger = logger_provider.get_logger(__name__) if logger_provider else None

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record to OTLP via LoggerProvider with BatchLogRecordProcessor.

        Injects trace_id and span_id if emitted inside an active span.
        Logs are batched and sent non-blocking by BatchLogRecordProcessor.

        Args:
            record: Python LogRecord to emit
        """
        try:
            if not self.logger:
                return

            # Get current active span context
            span_context = trace.get_current_span().get_span_context()

            # Build attributes dict
            attributes = {
                "logger.name": record.name,
            }

            # Only inject trace_id and span_id if inside an active span with valid trace
            if span_context and span_context.is_valid:
                attributes["trace_id"] = format(span_context.trace_id, "032x")
                attributes["span_id"] = format(span_context.span_id, "016x")

            # Emit to OTL logger with attributes
            # The LoggerProvider's BatchLogRecordProcessor will handle batching and export
            log_method = getattr(
                self.logger,
                record.levelname.lower(),
                self.logger.info,
            )
            log_method(record.getMessage(), attributes=attributes)
        except Exception:
            # Fail gracefully — do not let logging errors crash the app
            self.handleError(record)


