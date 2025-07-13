"""
Common error response helpers for API endpoints.
"""
from fastapi.responses import JSONResponse


def validation_error_response(detail: str, loc=None):
    """Return a 422 Unprocessable Entity error in FastAPI's expected format, including 'loc'."""
    if loc is None:
        loc = ["body"]
    return JSONResponse(
        status_code=422,
        content={"detail": [{"loc": loc, "msg": detail, "type": "value_error"}]}
    )

def conflict_error_response(detail: str, loc=None):
    """Return a 409 Conflict error in FastAPI's expected format, including 'loc'."""
    if loc is None:
        loc = ["body"]
    return JSONResponse(
        status_code=409,
        content={"detail": [{"loc": loc, "msg": detail, "type": "conflict_error"}]}
    )

def bad_request_error_response(detail: str, loc=None):
    """Return a 400 Bad Request error in FastAPI's expected format, including 'loc'."""
    if loc is None:
        loc = ["body"]
    return JSONResponse(
        status_code=400,
        content={"detail": [{"loc": loc, "msg": detail, "type": "bad_request"}]}
    )
