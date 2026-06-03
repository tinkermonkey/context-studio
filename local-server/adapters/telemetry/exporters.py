"""
OTLP exporter factory for traces and logs.

Provides factory functions to create OTLP exporters based on protocol configuration.
Handles graceful failure when the collector is unreachable.
"""

import logging
from typing import TYPE_CHECKING, Optional, cast

from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter as GRPCSpanExporter,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as HTTPSpanExporter,
)
from opentelemetry.sdk.trace.export import SpanExporter

if TYPE_CHECKING:
    from opentelemetry.sdk._logs.export import LogExporter

try:
    from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
        OTLPLogExporter as GRPCLogExporter,
    )
    from opentelemetry.exporter.otlp.proto.http._log_exporter import (
        OTLPLogExporter as HTTPLogExporter,
    )
    from opentelemetry.sdk._logs.export import LogExporter

    OTLP_LOG_EXPORT_AVAILABLE = True
except ImportError:
    OTLP_LOG_EXPORT_AVAILABLE = False

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
        exporter: Optional[SpanExporter] = None
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
        _logger.warning(
            f"Failed to create span exporter: {e}. Spans will not be exported."
        )
        return None


def create_log_exporter(
    protocol: str, grpc_endpoint: str, http_endpoint: str
) -> Optional["LogExporter"]:
    """
    Create an OTLP log exporter based on protocol.

    Args:
        protocol: "grpc" or "http"
        grpc_endpoint: gRPC collector endpoint URL
        http_endpoint: HTTP collector endpoint URL

    Returns:
        LogExporter instance, or None if creation fails or OTLP log export is unavailable
    """
    if not OTLP_LOG_EXPORT_AVAILABLE:
        _logger.warning(
            "OTLP log export not available; logs will not be exported to OTLP. Install"
            " opentelemetry-exporter-otlp-proto-grpc or"
            " opentelemetry-exporter-otlp-proto-http."
        )
        return None

    try:
        exporter: Optional["LogExporter"] = None
        if protocol.lower() == "grpc":
            exporter = cast(
                "LogExporter", GRPCLogExporter(endpoint=grpc_endpoint, timeout=5)
            )
            _logger.debug(f"Created gRPC log exporter for {grpc_endpoint}")
        elif protocol.lower() == "http":
            exporter = cast(
                "LogExporter", HTTPLogExporter(endpoint=http_endpoint, timeout=5)
            )
            _logger.debug(f"Created HTTP log exporter for {http_endpoint}")
        else:
            _logger.warning(f"Unknown protocol: {protocol}, defaulting to gRPC")
            exporter = cast(
                "LogExporter", GRPCLogExporter(endpoint=grpc_endpoint, timeout=5)
            )
        return exporter
    except Exception as e:
        _logger.warning(
            f"Failed to create log exporter: {e}. Logs will not be exported to OTLP."
        )
        return None
