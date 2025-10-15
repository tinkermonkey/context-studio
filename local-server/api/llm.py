from logging import config
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
import datetime
import json

from api.dependencies.llm_services import get_default_llm_service
from llm.service import LLMService
from llm.models import (
    PipelineExecutionRequest,
    PipelineExecutionResponse,
    LLMHealthResponse,
    LLMErrorResponse,
    StreamingLLMResponse,
)
from llm.exceptions import LLMConfigurationError, LLMProcessingError, LLMTimeoutError, LLMQuotaExceededError
from utils.logger import get_logger
from config import get_settings

logger = get_logger("llm_api")
router = APIRouter()

# Global service instance (kept for backward compatibility)
_llm_service: LLMService = None


def get_llm_service() -> LLMService:
    """Legacy dependency to get LLM service instance (kept for backward compatibility)"""
    global _llm_service
    if _llm_service is None:
        try:
            settings = get_settings()
            # Get LLM configuration from centralized settings
            model_name = settings.llm.model_name
            temperature = settings.llm.temperature

            logger.info(f"Initializing legacy LLM service with model: {model_name}")
            _llm_service = LLMService(model_name=model_name, temperature=temperature)
            logger.info("Legacy LLM service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize LLM service: {e}")
            raise
    return _llm_service


def handle_llm_error(e: Exception) -> HTTPException:
    """Convert LLM service errors to appropriate HTTP exceptions"""
    error_type = type(e).__name__

    if isinstance(e, LLMConfigurationError):
        logger.error(f"LLM configuration error: {e}")
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"LLM configuration error: {str(e)}"
        )
    elif isinstance(e, LLMQuotaExceededError):
        logger.warning(f"API quota exceeded: {e}")
        return HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"API quota exceeded: {str(e)}")
    elif isinstance(e, LLMTimeoutError):
        logger.warning(f"LLM request timeout: {e}")
        return HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=f"LLM request timeout: {str(e)}")
    elif isinstance(e, LLMProcessingError):
        logger.error(f"LLM processing error: {e}")
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"LLM processing error: {str(e)}")
    else:
        logger.error(f"Unexpected LLM error ({error_type}): {e}")
        return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")
        raise


@router.post(
    "/llm/execute_pipeline",
    response_model=PipelineExecutionResponse,
    responses={
        400: {"model": LLMErrorResponse},
        422: {"model": LLMErrorResponse, "description": "Request validation failure"},
        429: {"model": LLMErrorResponse},
        500: {"model": LLMErrorResponse},
        504: {"model": LLMErrorResponse},
    },
)
async def execute_pipeline(
    request: PipelineExecutionRequest, llm_service: LLMService = Depends(get_default_llm_service)
):
    """
    Execute a generic pipeline with arbitrary context data.

    This endpoint provides a unified interface for executing any pipeline type
    with flexible context data. It supports all pipeline types and flavors
    while maintaining full execution tracking.

    Use this endpoint for custom pipeline implementations or when you need
    fine-grained control over context data.
    """
    try:
        logger.info(
            f"Processing generic pipeline execution request - Type: {request.pipeline_type}, Flavor: {request.flavor_id}"
        )
        logger.debug(f"Context data keys: {list(request.context_data.keys())}")

        # Validate request
        if not request.context_data:
            logger.warning("Empty context_data provided in request")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="context_data cannot be empty")

        # Additional validation - check for reasonable context data size
        context_str = str(request.context_data)
        if len(context_str) > 50000:  # Reasonable limit
            logger.warning(f"Context data too large: {len(context_str)} characters")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Context data is too large (maximum 50000 characters)"
            )

        # Process the request
        result = await llm_service.execute_pipeline_flavor(request)

        logger.info(
            f"Successfully executed generic pipeline - Type: {request.pipeline_type}, execution: {result.execution_id}"
        )
        return result

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error in execute_pipeline endpoint for pipeline {request.pipeline_type}: {e}")
        raise handle_llm_error(e)


@router.post("/llm/execute_pipeline/stream")
async def execute_pipeline_stream(
    request: PipelineExecutionRequest, llm_service: LLMService = Depends(get_default_llm_service)
):
    """
    Execute a generic pipeline with streaming response.

    This endpoint provides streaming execution for any pipeline type with
    flexible context data. The response is streamed as Server-Sent Events (SSE)
    with execution tracking.

    Use this endpoint when you need real-time streaming responses for
    custom pipeline implementations.
    """
    try:
        logger.info(
            f"Processing streaming generic pipeline execution request - Type: {request.pipeline_type}, Flavor: {request.flavor_id}"
        )
        logger.debug(f"Context data keys: {list(request.context_data.keys())}")

        # Validate request (same validation as non-streaming)
        if not request.context_data:
            logger.warning("Empty context_data provided in request")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="context_data cannot be empty")

        context_str = str(request.context_data)
        if len(context_str) > 50000:
            logger.warning(f"Context data too large: {len(context_str)} characters")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Context data is too large (maximum 50000 characters)"
            )

        async def stream_generator():
            try:
                async for chunk in llm_service.execute_pipeline_flavor_streaming(request):
                    # Convert to JSON and add SSE formatting
                    data = chunk.model_dump_json()
                    yield f"data: {data}\n\n"

                    # Log completion
                    if chunk.done:
                        if chunk.error:
                            logger.error(f"Streaming generic pipeline execution failed: {chunk.error}")
                        else:
                            logger.info(
                                f"Successfully completed streaming generic pipeline execution - Type: {request.pipeline_type}"
                            )
                        break
            except Exception as e:
                logger.error(f"Error during streaming generic pipeline execution: {e}")
                error_chunk = StreamingLLMResponse(flavor_id="unknown", done=True, error=str(e))
                yield f"data: {error_chunk.model_dump_json()}\n\n"

        return StreamingResponse(
            stream_generator(),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error in execute_pipeline/stream endpoint for pipeline {request.pipeline_type}: {e}")
        raise handle_llm_error(e)


@router.get("/llm/health", response_model=LLMHealthResponse)
async def health_check(llm_service: LLMService = Depends(get_llm_service)):
    """
    Check the health status of the LLM service.
    """
    try:
        logger.debug("Performing LLM health check")
        service_initialized = llm_service.is_initialized()
        service_configured = llm_service.is_configured()

        status_value = "healthy" if service_initialized and service_configured else "unhealthy"
        logger.info(f"LLM health check completed: {status_value}")

        return LLMHealthResponse(
            status=status_value,
            model_info={"initialized": service_initialized, "configured": service_configured},
            timestamp=datetime.datetime.utcnow().isoformat(),
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return LLMHealthResponse(
            status="unhealthy", model_info={"error": str(e)}, timestamp=datetime.datetime.utcnow().isoformat()
        )
