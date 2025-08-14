"""
Custom middleware for logging API access requests in Apache Common Log Format style.
"""
import time
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from utils.logger import get_logger

logger = get_logger(__name__)


class AccessLogMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log HTTP requests in Apache Common Log Format style.
    
    Log format: {client_ip}:{client_port} - "{method} {path} {protocol}" {status_code} {status_text} {response_time}ms
    Example: 127.0.0.1:53359 - "GET /api/graph/terms/8f38d52e-938f-4314-9898-fe76aaa59b5e/hierarchy HTTP/1.1" 200 OK 275ms
    """
    
    async def dispatch(self, request: Request, call_next):
        # Record start time
        start_time = time.time()
        
        # Get client information
        client_host = request.client.host if request.client else "unknown"
        client_port = request.client.port if request.client else 0
        
        # Process the request
        response: Response = await call_next(request)
        
        # Calculate response time
        process_time = time.time() - start_time
        response_time_ms = int(process_time * 1000)
        
        # Get HTTP version from scope
        http_version = f"HTTP/{request.scope.get('http_version', '1.1')}"
        
        # Get status text
        status_text = self._get_status_text(response.status_code)
        
        # Format the log message
        log_message = (
            f"{client_host}:{client_port} - "
            f'"{request.method} {request.url.path}'
            f'{f"?{request.url.query}" if request.url.query else ""} {http_version}" '
            f"{response.status_code} {status_text} {response_time_ms}ms"
        )
        
        # Log at INFO level
        logger.info(log_message)
        
        return response
    
    def _get_status_text(self, status_code: int) -> str:
        """Get the standard HTTP status text for a given status code."""
        status_texts = {
            200: "OK",
            201: "Created",
            202: "Accepted",
            204: "No Content",
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            405: "Method Not Allowed",
            409: "Conflict",
            422: "Unprocessable Entity",
            500: "Internal Server Error",
            501: "Not Implemented",
            502: "Bad Gateway",
            503: "Service Unavailable",
        }
        return status_texts.get(status_code, "Unknown")
