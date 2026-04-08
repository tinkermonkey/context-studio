"""Root conftest for test configuration."""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Register RequestValidationError exception handler for all FastAPI apps in tests
from fastapi import FastAPI, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

_original_fastapi_init = FastAPI.__init__

def _patched_fastapi_init(self, *args, **kwargs):
    """Patched FastAPI.__init__ that adds RequestValidationError handler."""
    _original_fastapi_init(self, *args, **kwargs)

    @self.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc):
        """
        Handle Pydantic validation errors from request bodies.
        Return HTTP 400 (BAD_REQUEST) instead of the default 422 (UNPROCESSABLE_ENTITY).
        """
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "Invalid request body"},
        )

FastAPI.__init__ = _patched_fastapi_init
