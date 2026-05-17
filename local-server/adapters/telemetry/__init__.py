"""
Telemetry adapter for OTLP trace and log export.

Provides setup_telemetry() to initialize tracing with auto-instrumentation
for FastAPI, SQLAlchemy, and httpx. Integrates into the app lifespan.
"""

import logging
from typing import Optional
from fastapi import FastAPI
from sqlalchemy.engine import Engine

from config import TelemetryConfig
from adapters.telemetry.provider_setup import TelemetryProvider
from adapters.telemetry.instrumentors import (
    instrument_fastapi,
    instrument_sqlalchemy,
    instrument_httpx,
)

_logger = logging.getLogger(__name__)


class TelemetryLifecycle:
    """Manages telemetry initialization and shutdown."""

    def __init__(self, provider: Optional[TelemetryProvider]):
        """
        Initialize telemetry lifecycle.

        Args:
            provider: TelemetryProvider instance, or None if disabled
        """
        self.provider = provider
        self._instrumented = False

    def instrument_app(self, app: FastAPI, db_engine: Optional[Engine] = None) -> bool:
        """
        Activate auto-instrumentation for FastAPI, SQLAlchemy, and httpx.

        Args:
            app: FastAPI application instance
            db_engine: Optional SQLAlchemy engine for database instrumentation

        Returns:
            True if instrumentation succeeded (or telemetry is disabled), False on error
        """
        if not self.provider:
            _logger.debug("Telemetry disabled; skipping instrumentation")
            return True

        try:
            instrument_fastapi(app)
            if db_engine:
                instrument_sqlalchemy(db_engine)
            instrument_httpx()
            self._instrumented = True
            _logger.info("All instrumentors activated")
            return True
        except Exception as e:
            _logger.error(f"Failed to activate instrumentors: {e}")
            return False

    def shutdown(self) -> bool:
        """
        Shut down telemetry and flush pending data.

        Returns:
            True if shutdown succeeded (or telemetry is disabled), False on error
        """
        if not self.provider:
            return True
        return self.provider.shutdown()


def setup_telemetry(config: TelemetryConfig) -> TelemetryLifecycle:
    """
    Set up telemetry from configuration.

    If telemetry.enabled is False, returns a no-op lifecycle.
    Otherwise, initializes TracerProvider and exporters.
    Exporter failures are logged but non-fatal.

    Args:
        config: TelemetryConfig instance

    Returns:
        TelemetryLifecycle for use in app.lifespan
    """
    if not config.enabled:
        _logger.info("Telemetry disabled in configuration")
        return TelemetryLifecycle(None)

    _logger.info(f"Setting up telemetry for service '{config.service_name}'")

    provider = TelemetryProvider(
        service_name=config.service_name,
        otlp_endpoint_grpc=config.otlp_endpoint_grpc,
        otlp_endpoint_http=config.otlp_endpoint_http,
        protocol=config.protocol.value,
        sample_rate=config.sample_rate,
        export_traces=config.export_traces,
    )

    tracer_ok = provider.setup_tracer_provider()

    if tracer_ok:
        _logger.info("Telemetry initialized successfully")
        return TelemetryLifecycle(provider)
    else:
        _logger.error("Telemetry initialization failed; running without telemetry")
        return TelemetryLifecycle(None)
