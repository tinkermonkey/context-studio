"""
OTLP log handler that bridges Python logging to OTLP log export.

Wraps OpenTelemetry SDK's LoggingHandler to inject trace_id and span_id
into log records when emitted inside an active span, enabling log-trace
correlation in observability backends like SigNoz.

Integrates with OpenTelemetry SDK's LoggerProvider and BatchLogRecordProcessor
for non-blocking, batched log export.
"""

import logging
from typing import TYPE_CHECKING, Any, Optional

from opentelemetry import trace

if TYPE_CHECKING:
    from opentelemetry.sdk._logs import LoggerProvider as LoggerProviderType
    from opentelemetry.sdk._logs import LoggingHandler as BaseOTLPLogHandler
else:
    BaseOTLPLogHandler: Any = None

    try:
        from opentelemetry.sdk._logs import LoggingHandler as BaseOTLPLogHandler
    except ImportError:
        pass

_logger = logging.getLogger(__name__)


class OTLPLogHandler(BaseOTLPLogHandler):
    """
    Bridges Python logging output to OTLP log export via OpenTelemetry LoggerProvider.

    Extends SDK's LoggingHandler to inject trace context (trace_id, span_id)
    when emitted inside an active span. Routes through LoggerProvider with
    BatchLogRecordProcessor for batched, non-blocking export.
    """

    def __init__(self, logger_provider: Optional["LoggerProviderType"]):
        """
        Initialize the OTLP log handler.

        Args:
            logger_provider: OpenTelemetry LoggerProvider instance with BatchLogRecordProcessor
        """
        if BaseOTLPLogHandler is None:
            raise ImportError("OpenTelemetry logging SDK is not available")

        super().__init__(logger_provider=logger_provider)
        self.logger_provider = logger_provider

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record to OTLP via LoggerProvider with BatchLogRecordProcessor.

        Injects trace_id and span_id if emitted inside an active span.
        Logs are batched and sent non-blocking by BatchLogRecordProcessor.

        Args:
            record: Python LogRecord to emit
        """
        if not self.logger_provider:
            return

        try:
            # Get current active span context
            span_context = trace.get_current_span().get_span_context()

            # Only inject trace_id and span_id if inside an active span with valid trace
            if span_context and span_context.is_valid:
                # Add trace context to record attributes
                if not hasattr(record, "trace_id"):
                    record.trace_id = format(span_context.trace_id, "032x")
                if not hasattr(record, "span_id"):
                    record.span_id = format(span_context.span_id, "016x")

            # Call parent's emit to handle the actual OTLP export
            super().emit(record)
        except Exception:
            # Fail gracefully — do not let logging errors crash the app
            self.handleError(record)
