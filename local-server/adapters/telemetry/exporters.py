"""
OTLP exporter factory for traces.

Provides factory functions to create OTLP exporters based on protocol configuration.
Handles graceful failure when the collector is unreachable.
"""

import logging
from typing import Optional
from opentelemetry.sdk.trace.export import SpanExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as GRPCSpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as HTTPSpanExporter

_logger = logging.getLogger(__name__)


def create_span_exporter(
    protocol: str, grpc_endpoint: str, http_endpoint: str
) -> Optional[SpanExporter]:
    """
    Create an OTLP span exporter based on protocol.

    Args:
        protocol: "grpc" or "http"
        grpc_endpoint: gRPC collector endpoint URL
        http_endpoint: HTTP collector endpoint URL

    Returns:
        SpanExporter instance, or None if creation fails
    """
    try:
        if protocol.lower() == "grpc":
            exporter = GRPCSpanExporter(endpoint=grpc_endpoint, timeout=5)
            _logger.debug(f"Created gRPC span exporter for {grpc_endpoint}")
        elif protocol.lower() == "http":
            exporter = HTTPSpanExporter(endpoint=http_endpoint, timeout=5)
            _logger.debug(f"Created HTTP span exporter for {http_endpoint}")
        else:
            _logger.warning(f"Unknown protocol: {protocol}, defaulting to gRPC")
            exporter = GRPCSpanExporter(endpoint=grpc_endpoint, timeout=5)
        return exporter
    except Exception as e:
        _logger.warning(f"Failed to create span exporter: {e}. Spans will not be exported.")
        return None
