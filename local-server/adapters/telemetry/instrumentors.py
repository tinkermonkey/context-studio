"""
Auto-instrumentation setup for standard libraries.

Activates OpenTelemetry instrumentors for FastAPI, SQLAlchemy, and httpx
to provide automatic spans without code changes.
"""

import logging

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from sqlalchemy.engine import Engine

_logger = logging.getLogger(__name__)


def instrument_fastapi(app: FastAPI) -> bool:
    """
    Instrument a FastAPI application for tracing.

    Args:
        app: FastAPI application instance

    Returns:
        True if successful, False otherwise
    """
    try:
        FastAPIInstrumentor.instrument_app(app)
        _logger.info("FastAPI instrumentation activated")
        return True
    except Exception as e:
        _logger.error(f"Failed to instrument FastAPI: {e}")
        return False


def instrument_sqlalchemy(engine: Engine) -> bool:
    """
    Instrument a SQLAlchemy engine for tracing.

    Args:
        engine: SQLAlchemy engine instance

    Returns:
        True if successful, False otherwise
    """
    try:
        SQLAlchemyInstrumentor().instrument(engine=engine)
        _logger.info("SQLAlchemy instrumentation activated")
        return True
    except Exception as e:
        _logger.error(f"Failed to instrument SQLAlchemy: {e}")
        return False


def instrument_httpx() -> bool:
    """
    Instrument httpx for tracing outbound HTTP calls.

    Returns:
        True if successful, False otherwise
    """
    try:
        HTTPXClientInstrumentor().instrument()
        _logger.info("httpx instrumentation activated")
        return True
    except Exception as e:
        _logger.error(f"Failed to instrument httpx: {e}")
        return False
