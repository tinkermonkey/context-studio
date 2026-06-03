"""
OpenTelemetry SDK provider setup.

Configures TracerProvider, LoggerProvider, and Resource with proper sampling and batching.
"""

import logging
import socket
from typing import TYPE_CHECKING, Optional

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
from opentelemetry.trace import set_tracer_provider

try:
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

    LOGGING_SDK_AVAILABLE = True
except ImportError:
    LOGGING_SDK_AVAILABLE = False

from adapters.telemetry.exporters import create_log_exporter, create_span_exporter

if TYPE_CHECKING:
    from opentelemetry.sdk._logs import LoggerProvider as LoggerProviderType

_logger = logging.getLogger(__name__)


class TelemetryProvider:
    """Manages OpenTelemetry provider lifecycle."""

    def __init__(
        self,
        service_name: str,
        service_version: str,
        environment: str,
        otlp_endpoint_grpc: str,
        otlp_endpoint_http: str,
        protocol: str,
        sample_rate: float,
        export_traces: bool,
        export_logs: bool,
    ):
        """
        Initialize telemetry provider.

        Args:
            service_name: Service name for resource attributes
            service_version: Service version for resource attributes
            environment: Deployment environment (development, staging, production)
            otlp_endpoint_grpc: gRPC collector endpoint
            otlp_endpoint_http: HTTP collector endpoint
            protocol: "grpc" or "http"
            sample_rate: Sampling rate (0.0 to 1.0)
            export_traces: Whether to export traces
            export_logs: Whether to export logs
        """
        self.service_name = service_name
        self.service_version = service_version
        self.environment = environment
        self.otlp_endpoint_grpc = otlp_endpoint_grpc
        self.otlp_endpoint_http = otlp_endpoint_http
        self.protocol = protocol
        self.sample_rate = sample_rate
        self.export_traces = export_traces
        self.export_logs = export_logs

        self.tracer_provider: Optional[TracerProvider] = None
        self.logger_provider: Optional["LoggerProviderType"] = None

    def _create_resource(self) -> Resource:
        """Create a Resource with service attributes."""
        return Resource.create(
            {
                "service.name": self.service_name,
                "service.version": self.service_version,
                "deployment.environment": self.environment,
                "service.instance.id": socket.gethostname(),
            }
        )

    def setup_tracer_provider(self) -> bool:
        """
        Set up and configure the TracerProvider.

        Returns:
            True if successful, False otherwise
        """
        try:
            resource = self._create_resource()
            sampler = TraceIdRatioBased(self.sample_rate)

            tracer_provider = TracerProvider(resource=resource, sampler=sampler)

            if self.export_traces:
                span_exporter = create_span_exporter(
                    self.protocol, self.otlp_endpoint_grpc, self.otlp_endpoint_http
                )
                if span_exporter:
                    batch_processor = BatchSpanProcessor(
                        span_exporter, schedule_delay_millis=5000
                    )
                    tracer_provider.add_span_processor(batch_processor)
                    _logger.info("Span exporter configured with batch processor")
                else:
                    _logger.warning(
                        "Span exporter creation failed; spans will not be exported"
                    )

            set_tracer_provider(tracer_provider)
            self.tracer_provider = tracer_provider
            _logger.info(f"TracerProvider set up for service '{self.service_name}'")
            return True
        except Exception as e:
            _logger.error(f"Failed to set up TracerProvider: {e}")
            return False

    def setup_log_exporter(self) -> bool:
        """
        Set up and configure the log exporter using OpenTelemetry SDK's LoggerProvider
        with BatchLogRecordProcessor for non-blocking, batched log export.

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.export_logs:
                if not LOGGING_SDK_AVAILABLE:
                    _logger.warning(
                        "OpenTelemetry logging SDK not available; logs will not be"
                        " exported. Ensure opentelemetry-sdk is installed with logging"
                        " support."
                    )
                    return False

                log_exporter = create_log_exporter(
                    self.protocol, self.otlp_endpoint_grpc, self.otlp_endpoint_http
                )
                if not log_exporter:
                    _logger.warning(
                        "Log exporter creation failed; logs will not be exported to"
                        " OTLP"
                    )
                    return False

                resource = self._create_resource()
                logger_provider = LoggerProvider(resource=resource)

                batch_processor = BatchLogRecordProcessor(
                    log_exporter, schedule_delay_millis=5000
                )
                logger_provider.add_log_record_processor(batch_processor)

                self.logger_provider = logger_provider
                _logger.info("Log exporter configured with batch processor")
                return True
            return True
        except Exception as e:
            _logger.error(f"Failed to set up log exporter: {e}")
            return False

    def shutdown(self) -> bool:
        """
        Shut down provider and flush pending data.

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.tracer_provider:
                self.tracer_provider.shutdown()
                _logger.info("TracerProvider shut down")
            if self.logger_provider:
                self.logger_provider.shutdown()
                _logger.info("LoggerProvider shut down")
            return True
        except Exception as e:
            _logger.error(f"Failed to shut down provider: {e}")
            return False
