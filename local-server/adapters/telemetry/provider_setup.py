"""
OpenTelemetry SDK provider setup.

Configures TracerProvider and Resource with proper sampling and batching.
"""

import logging
import socket
from typing import Optional

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
from opentelemetry.trace import set_tracer_provider

from adapters.telemetry.exporters import create_span_exporter

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
        """
        self.service_name = service_name
        self.service_version = service_version
        self.environment = environment
        self.otlp_endpoint_grpc = otlp_endpoint_grpc
        self.otlp_endpoint_http = otlp_endpoint_http
        self.protocol = protocol
        self.sample_rate = sample_rate
        self.export_traces = export_traces

        self.tracer_provider: Optional[TracerProvider] = None

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
                    batch_processor = BatchSpanProcessor(span_exporter, schedule_delay_millis=5000)
                    tracer_provider.add_span_processor(batch_processor)
                    _logger.info("Span exporter configured with batch processor")
                else:
                    _logger.warning("Span exporter creation failed; spans will not be exported")

            set_tracer_provider(tracer_provider)
            self.tracer_provider = tracer_provider
            _logger.info(f"TracerProvider set up for service '{self.service_name}'")
            return True
        except Exception as e:
            _logger.error(f"Failed to set up TracerProvider: {e}")
            return False

    def shutdown(self) -> bool:
        """
        Shut down provider and flush pending data.

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.tracer_provider:
                self.tracer_provider.shutdown(timeout_millis=5000)
                _logger.info("TracerProvider shut down")
            return True
        except Exception as e:
            _logger.error(f"Failed to shut down provider: {e}")
            return False
