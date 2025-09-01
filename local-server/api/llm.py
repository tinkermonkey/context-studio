from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import JSONResponse
import datetime
import os
from typing import Dict, Any

from llm.service import LLMService
from llm.models import (
    DefinitionSuggestionRequest, 
    DefinitionSuggestionResponse,
    LLMHealthResponse,
    LLMErrorResponse,
    LLMSuccessResponse
)
from llm.exceptions import (
    LLMConfigurationError, 
    LLMProcessingError, 
    LLMTimeoutError, 
    LLMQuotaExceededError
)
from utils.logger import get_logger
from config import get_settings

logger = get_logger("llm_api")
router = APIRouter()

# Global service instance
_llm_service: LLMService = None


def get_llm_service() -> LLMService:
    """Dependency to get LLM service instance"""
    global _llm_service
    if _llm_service is None:
        try:
            settings = get_settings()
            # Get LLM configuration from settings or environment
            model_name = os.getenv("LLM_MODEL_NAME", "gpt-3.5-turbo")
            temperature = float(os.getenv("LLM_TEMPERATURE", "0"))
            
            logger.info(f"Initializing LLM service with model: {model_name}")
            _llm_service = LLMService(model_name=model_name, temperature=temperature)
            logger.info("LLM service initialized successfully")
            
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
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"LLM configuration error: {str(e)}"
        )
    elif isinstance(e, LLMQuotaExceededError):
        logger.warning(f"API quota exceeded: {e}")
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"API quota exceeded: {str(e)}"
        )
    elif isinstance(e, LLMTimeoutError):
        logger.warning(f"LLM request timeout: {e}")
        return HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"LLM request timeout: {str(e)}"
        )
    elif isinstance(e, LLMProcessingError):
        logger.error(f"LLM processing error: {e}")
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"LLM processing error: {str(e)}"
        )
    else:
        logger.error(f"Unexpected LLM error ({error_type}): {e}")
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/llm/suggest_definition", 
            response_model=LLMSuccessResponse,
            responses={
                400: {"model": LLMErrorResponse},
                422: {"model": LLMErrorResponse, "description": "Request validation failure"},
                429: {"model": LLMErrorResponse},
                500: {"model": LLMErrorResponse},
                504: {"model": LLMErrorResponse}
            })
async def suggest_definition(
    request: DefinitionSuggestionRequest,
    llm_service: LLMService = Depends(get_llm_service)
):
    """
    Generate a definition suggestion based on provided context using LLM.
    
    This endpoint uses a Langchain pipeline with OpenAI GPT models to generate
    contextually-aware term definitions based on domain context, hierarchical
    relationships, component terms, and reference source information.
    """
    try:
        logger.info(f"Processing definition suggestion request for term: '{request.term}'")
        logger.debug(f"Request details - Domain: {request.domain_title}, Components: {len(request.component_terms)}")
        
        # Validate request
        if not request.term.strip():
            logger.warning("Empty term provided in request")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Term cannot be empty"
            )
        
        # Additional validation
        if len(request.term) > 1000:  # Reasonable limit
            logger.warning(f"Term too long: {len(request.term)} characters")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Term is too long (maximum 1000 characters)"
            )
        
        # Process the request
        result = await llm_service.suggest_definition(request)
        
        logger.info(f"Successfully generated definition for term: '{request.term}'")
        return LLMSuccessResponse(data=result)
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error in suggest_definition endpoint for term '{request.term}': {e}")
        raise handle_llm_error(e)


@router.get("/llm/health", response_model=LLMHealthResponse)
async def health_check(llm_service: LLMService = Depends(get_llm_service)):
    """
    Check the health status of the LLM service.
    """
    try:
        logger.debug("Performing LLM health check")
        model_info = llm_service.get_model_info()
        
        status_value = "healthy" if model_info["initialized"] else "unhealthy"
        logger.info(f"LLM health check completed: {status_value}")
        
        return LLMHealthResponse(
            status=status_value,
            model_info=model_info,
            timestamp=datetime.datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return LLMHealthResponse(
            status="unhealthy",
            model_info={"error": str(e)},
            timestamp=datetime.datetime.utcnow().isoformat()
        )
