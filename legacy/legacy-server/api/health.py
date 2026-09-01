"""
Health check endpoint for monitoring and E2E testing.

This module provides a simple health check endpoint that can be used to verify
the server is running and responding to requests.
"""


from fastapi import APIRouter

router = APIRouter()


@router.get("/health", response_model=dict[str, str])
async def health_check():
    """
    Health check endpoint.

    Returns a simple status message to indicate the server is running.
    This endpoint is used by:
    - E2E test infrastructure to verify server startup
    - Monitoring systems to check service availability
    - Load balancers for health checks

    Returns:
        dict: Status message with "status": "ok"
    """
    return {"status": "ok"}
