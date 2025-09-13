from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
import datetime
import json

from api.dependencies.llm_services import get_default_llm_service
from llm.service import LLMService
from llm.models import (
    DefinitionSuggestionRequest, 
    LayerDefinitionRequest,
    DomainDefinitionRequest,
    GenericPipelineExecutionRequest,
    GenericPipelineExecutionResponse,
    LLMHealthResponse,
    LLMErrorResponse,
    LLMSuccessResponse,
    LayerLLMSuccessResponse,
    DomainLLMSuccessResponse,
    StreamingLLMResponse
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
        raise


@router.post("/llm/suggest_term_definition/stream")
async def suggest_term_definition_stream(
    request: DefinitionSuggestionRequest,
    llm_service: LLMService = Depends(get_default_llm_service)
):
    """Stream term definition suggestion using specified flavor with Server-Side Events"""
    
    async def generate_stream():
        try:
            logger.info(f"Starting streaming term definition for term: '{request.term}' with flavor: {request.flavor or 'default'}")
            
            # Validate request
            if not request.term.strip():
                error_chunk = StreamingLLMResponse(
                    flavor_id="unknown",
                    done=True,
                    error="Term cannot be empty"
                )
                yield f"data: {json.dumps(error_chunk.model_dump())}\n\n"
                return
            
            # Stream the response
            async for chunk in llm_service.suggest_term_definition_streaming(request, request.flavor):
                data = chunk.model_dump()
                yield f"data: {json.dumps(data)}\n\n"
                
        except Exception as e:
            logger.error(f"Error in streaming term definition: {e}")
            error_chunk = StreamingLLMResponse(
                flavor_id="unknown",
                done=True,
                error=str(e)
            )
            yield f"data: {json.dumps(error_chunk.model_dump())}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/plain; charset=utf-8"
        }
    )


@router.post("/llm/suggest_layer_definition/stream")
async def suggest_layer_definition_stream(
    request: LayerDefinitionRequest,
    llm_service: LLMService = Depends(get_llm_service)
):
    """Stream layer definition suggestion using specified flavor with Server-Side Events"""
    
    async def generate_stream():
        try:
            logger.info(f"Starting streaming layer definition for layer: '{request.layer_title}' with flavor: {request.flavor or 'default'}")
            
            # Validate request
            if not request.layer_title.strip():
                error_chunk = StreamingLLMResponse(
                    flavor_id="unknown",
                    done=True,
                    error="Layer title cannot be empty"
                )
                yield f"data: {json.dumps(error_chunk.model_dump())}\n\n"
                return
            
            # Stream the response
            async for chunk in llm_service.suggest_layer_definition_streaming(request, request.flavor):
                data = chunk.model_dump()
                yield f"data: {json.dumps(data)}\n\n"
                
        except Exception as e:
            logger.error(f"Error in streaming layer definition: {e}")
            error_chunk = StreamingLLMResponse(
                flavor_id="unknown",
                done=True,
                error=str(e)
            )
            yield f"data: {json.dumps(error_chunk.model_dump())}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/plain; charset=utf-8"
        }
    )


@router.post("/llm/suggest_domain_definition/stream")
async def suggest_domain_definition_stream(
    request: DomainDefinitionRequest,
    llm_service: LLMService = Depends(get_llm_service)
):
    """Stream domain definition suggestion using specified flavor with Server-Side Events"""
    
    async def generate_stream():
        try:
            logger.info(f"Starting streaming domain definition for domain: '{request.domain_title}' with flavor: {request.flavor or 'default'}")
            
            # Validate request
            if not request.domain_title.strip():
                error_chunk = StreamingLLMResponse(
                    flavor_id="unknown",
                    done=True,
                    error="Domain title cannot be empty"
                )
                yield f"data: {json.dumps(error_chunk.model_dump())}\n\n"
                return
            
            # Stream the response
            async for chunk in llm_service.suggest_domain_definition_streaming(request, request.flavor):
                data = chunk.model_dump()
                yield f"data: {json.dumps(data)}\n\n"
                
        except Exception as e:
            logger.error(f"Error in streaming domain definition: {e}")
            error_chunk = StreamingLLMResponse(
                flavor_id="unknown",
                done=True,
                error=str(e)
            )
            yield f"data: {json.dumps(error_chunk.model_dump())}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/plain; charset=utf-8"
        }
    )


@router.post("/llm/suggest_term_definition", 
            response_model=LLMSuccessResponse,
            responses={
                400: {"model": LLMErrorResponse},
                422: {"model": LLMErrorResponse, "description": "Request validation failure"},
                429: {"model": LLMErrorResponse},
                500: {"model": LLMErrorResponse},
                504: {"model": LLMErrorResponse}
            })
async def suggest_term_definition(
    request: DefinitionSuggestionRequest,
    llm_service: LLMService = Depends(get_default_llm_service)
):
    """
    Generate a term definition suggestion based on provided context using LLM.
    
    This endpoint uses a Langchain pipeline with OpenAI GPT models to generate
    contextually-aware term definitions based on domain context, hierarchical
    relationships, component terms, and reference source information.
    Supports optional flavor parameter to use different LLM configurations.
    """
    try:
        logger.info(f"Processing term definition suggestion request for term: '{request.term}' with flavor: {request.flavor or 'default'}")
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
        result = await llm_service.suggest_term_definition(request)
        
        logger.info(f"Successfully generated term definition for term: '{request.term}'")
        return LLMSuccessResponse(data=result, execution_id=result.execution_id)
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error in suggest_term_definition endpoint for term '{request.term}': {e}")
        raise handle_llm_error(e)


@router.post("/llm/suggest_layer_definition", 
            response_model=LayerLLMSuccessResponse,
            responses={
                400: {"model": LLMErrorResponse},
                422: {"model": LLMErrorResponse, "description": "Request validation failure"},
                429: {"model": LLMErrorResponse},
                500: {"model": LLMErrorResponse},
                504: {"model": LLMErrorResponse}
            })
async def suggest_layer_definition(
    request: LayerDefinitionRequest,
    llm_service: LLMService = Depends(get_llm_service)
):
    """
    Generate a layer definition suggestion based on provided context using LLM.
    
    This endpoint uses a Langchain pipeline with OpenAI GPT models to generate
    contextually-aware layer definitions based on organizational context, hierarchical
    relationships, contained domains, and layer purpose information.
    Supports optional flavor parameter to use different LLM configurations.
    """
    try:
        logger.info(f"Processing layer definition suggestion request for layer: '{request.layer_title}' with flavor: {request.flavor or 'default'}")
        logger.debug(f"Request details - Parent: {request.parent_layer_title}, Domains: {len(request.contained_domains)}")
        
        # Validate request
        if not request.layer_title.strip():
            logger.warning("Empty layer title provided in request")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Layer title cannot be empty"
            )
        
        # Additional validation
        if len(request.layer_title) > 1000:  # Reasonable limit
            logger.warning(f"Layer title too long: {len(request.layer_title)} characters")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Layer title is too long (maximum 1000 characters)"
            )
        
        # Process the request
        result = await llm_service.suggest_layer_definition(request)
        
        logger.info(f"Successfully generated layer definition for layer: '{request.layer_title}'")
        return LayerLLMSuccessResponse(data=result, execution_id=result.execution_id)
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error in suggest_layer_definition endpoint for layer '{request.layer_title}': {e}")
        raise handle_llm_error(e)


@router.post("/llm/suggest_domain_definition", 
            response_model=DomainLLMSuccessResponse,
            responses={
                400: {"model": LLMErrorResponse},
                422: {"model": LLMErrorResponse, "description": "Request validation failure"},
                429: {"model": LLMErrorResponse},
                500: {"model": LLMErrorResponse},
                504: {"model": LLMErrorResponse}
            })
async def suggest_domain_definition(
    request: DomainDefinitionRequest,
    llm_service: LLMService = Depends(get_llm_service)
):
    """
    Generate a domain definition suggestion based on provided context using LLM.
    
    This endpoint uses a Langchain pipeline with OpenAI GPT models to generate
    contextually-aware domain definitions based on thematic scope, hierarchical
    relationships, contained terms, and domain boundaries information.
    Supports optional flavor parameter to use different LLM configurations.
    """
    try:
        logger.info(f"Processing domain definition suggestion request for domain: '{request.domain_title}' with flavor: {request.flavor or 'default'}")
        logger.debug(f"Request details - Layer: {request.layer_title}, Terms: {len(request.contained_terms)}")
        
        # Validate request
        if not request.domain_title.strip():
            logger.warning("Empty domain title provided in request")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Domain title cannot be empty"
            )
        
        # Additional validation
        if len(request.domain_title) > 1000:  # Reasonable limit
            logger.warning(f"Domain title too long: {len(request.domain_title)} characters")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Domain title is too long (maximum 1000 characters)"
            )
        
        # Process the request
        result = await llm_service.suggest_domain_definition(request)
        
        logger.info(f"Successfully generated domain definition for domain: '{request.domain_title}'")
        return DomainLLMSuccessResponse(data=result, execution_id=result.execution_id)
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error in suggest_domain_definition endpoint for domain '{request.domain_title}': {e}")
        raise handle_llm_error(e)


@router.post("/llm/execute_pipeline", 
            response_model=GenericPipelineExecutionResponse,
            responses={
                400: {"model": LLMErrorResponse},
                422: {"model": LLMErrorResponse, "description": "Request validation failure"},
                429: {"model": LLMErrorResponse},
                500: {"model": LLMErrorResponse},
                504: {"model": LLMErrorResponse}
            })
async def execute_pipeline(
    request: GenericPipelineExecutionRequest,
    llm_service: LLMService = Depends(get_default_llm_service)
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
        logger.info(f"Processing generic pipeline execution request - Type: {request.pipeline_type}, Flavor: {request.flavor_id}")
        logger.debug(f"Context data keys: {list(request.context_data.keys())}")
        
        # Validate request
        if not request.context_data:
            logger.warning("Empty context_data provided in request")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="context_data cannot be empty"
            )
        
        # Additional validation - check for reasonable context data size
        context_str = str(request.context_data)
        if len(context_str) > 50000:  # Reasonable limit
            logger.warning(f"Context data too large: {len(context_str)} characters")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Context data is too large (maximum 50000 characters)"
            )
        
        # Process the request
        result = await llm_service.execute_pipeline_flavor(request)
        
        logger.info(f"Successfully executed generic pipeline - Type: {request.pipeline_type}, execution: {result.execution_id}")
        return result
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error in execute_pipeline endpoint for pipeline {request.pipeline_type}: {e}")
        raise handle_llm_error(e)


@router.post("/llm/execute_pipeline/stream")
async def execute_pipeline_stream(
    request: GenericPipelineExecutionRequest,
    llm_service: LLMService = Depends(get_default_llm_service)
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
        logger.info(f"Processing streaming generic pipeline execution request - Type: {request.pipeline_type}, Flavor: {request.flavor_id}")
        logger.debug(f"Context data keys: {list(request.context_data.keys())}")
        
        # Validate request (same validation as non-streaming)
        if not request.context_data:
            logger.warning("Empty context_data provided in request")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="context_data cannot be empty"
            )
        
        context_str = str(request.context_data)
        if len(context_str) > 50000:
            logger.warning(f"Context data too large: {len(context_str)} characters")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Context data is too large (maximum 50000 characters)"
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
                            logger.info(f"Successfully completed streaming generic pipeline execution - Type: {request.pipeline_type}")
                        break
            except Exception as e:
                logger.error(f"Error during streaming generic pipeline execution: {e}")
                error_chunk = StreamingLLMResponse(
                    flavor_id="unknown",
                    done=True,
                    error=str(e)
                )
                yield f"data: {error_chunk.model_dump_json()}\n\n"
        
        return StreamingResponse(
            stream_generator(),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
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
