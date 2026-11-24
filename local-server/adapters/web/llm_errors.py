"""
The API's answer when a call needs a model and no LLM provider key is configured.

A route that catches the error maps it itself (see pipelines_routes); this handler
answers for every other route, so none of them turns it into a generic 500.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from domain.pipelines.exceptions import LLMNotConfiguredError


async def _llm_not_configured(request: Request, error: LLMNotConfiguredError) -> JSONResponse:
    """503 with the message that names the settings to fill in."""
    return JSONResponse({"detail": str(error)}, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


def add_llm_error_handlers(app: FastAPI) -> None:
    """Answer LLMNotConfiguredError with 503 and its message."""
    app.add_exception_handler(LLMNotConfiguredError, _llm_not_configured)  # type: ignore[arg-type]
