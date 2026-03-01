"""
FastAPI router for RAG Pipeline API endpoints.

This module provides REST API endpoints for:
- Entity extraction using the RAG pipeline
- Metrics retrieval for specific requests
- Trace data access for debugging
- Configuration management
- Manual trace cleanup
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import Dict, Any

from rag.models import RAGExtractionRequest, RAGExtractionResponse
from rag.rag_pipeline_service import RAGPipelineService
from rag.observability_store import RAGObservabilityStore
from api.dependencies.rag_services import get_rag_pipeline_service, get_rag_observability_store
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/extract",
    response_model=RAGExtractionResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Invalid request parameters"},
        500: {"description": "Pipeline execution failed"}
    }
)
async def extract_entities(
    request: RAGExtractionRequest,
    pipeline_service: RAGPipelineService = Depends(get_rag_pipeline_service)
):
    """
    Extract entities from text using the RAG pipeline.

    The pipeline processes text through four layers:
    - Layer 0: Knowledge Graph Context Preparation
    - Layer 1: LLM-based Entity Extraction
    - Layer 2: spaCy Syntactic Gap Analysis
    - Layer 3: Concept Resolution via KG and Web Search

    Args:
        request: RAGExtractionRequest containing text and trace enablement flag
        pipeline_service: Injected RAG pipeline service

    Returns:
        RAGExtractionResponse with extracted entities, metrics, and request ID

    Raises:
        HTTPException 400: If text is empty or invalid
        HTTPException 500: If pipeline execution fails
    """
    try:
        # Determine if LLM layer should be enabled (request overrides config default)
        from config import get_settings
        settings = get_settings()
        enable_llm_layer = request.enable_llm_layer if request.enable_llm_layer is not None else settings.rag_pipeline.enable_llm_layer

        logger.info(f"Received RAG extraction request, text_length={len(request.text)}, enable_trace={request.enable_trace}, enable_llm_layer={enable_llm_layer}")

        # Execute pipeline
        response = await pipeline_service.extract_entities(
            text=request.text,
            enable_trace=request.enable_trace,
            enable_llm_layer=enable_llm_layer
        )

        logger.info(
            f"RAG extraction completed: request_id={response.request_id}, "
            f"entities={len(response.entities)}, "
            f"total_time_ms={response.metrics.total_execution_time_ms:.2f}"
        )

        return response

    except ValueError as ve:
        logger.warning(f"Invalid request parameters: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {str(ve)}"
        )
    except Exception as e:
        logger.error(f"RAG pipeline execution failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline execution failed: {str(e)}"
        )


@router.get(
    "/metrics/{request_id}",
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "Request ID not found"},
        500: {"description": "Failed to retrieve metrics"}
    }
)
async def get_metrics(
    request_id: str,
    observability_store: RAGObservabilityStore = Depends(get_rag_observability_store)
):
    """
    Retrieve processing metrics for a specific RAG extraction request.

    Returns timing data and entity counts for all pipeline layers.

    Args:
        request_id: Unique identifier for the extraction request
        observability_store: Injected observability store

    Returns:
        Dictionary containing metrics for all layers and total execution time

    Raises:
        HTTPException 404: If request_id is not found
        HTTPException 500: If metrics retrieval fails
    """
    try:
        logger.info(f"Retrieving metrics for request_id={request_id}")

        metrics = observability_store.get_metrics(request_id)

        if metrics is None:
            logger.warning(f"Metrics not found for request_id={request_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No metrics found for request ID: {request_id}"
            )

        logger.info(f"Retrieved metrics for request_id={request_id}")
        return metrics

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve metrics for request_id={request_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve metrics: {str(e)}"
        )


@router.get(
    "/trace/{request_id}",
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "Request ID not found or trace not enabled"},
        500: {"description": "Failed to retrieve trace data"}
    }
)
async def get_trace(
    request_id: str,
    observability_store: RAGObservabilityStore = Depends(get_rag_observability_store)
):
    """
    Retrieve all trace entries for a specific RAG extraction request.

    Trace data includes detailed input/output information for each layer,
    useful for debugging and algorithm tuning.

    Args:
        request_id: Unique identifier for the extraction request
        observability_store: Injected observability store

    Returns:
        List of trace entries ordered by sentence index and timestamp

    Raises:
        HTTPException 404: If request_id has no trace data
        HTTPException 500: If trace retrieval fails
    """
    try:
        logger.info(f"Retrieving trace data for request_id={request_id}")

        traces = observability_store.get_traces(request_id)

        if not traces:
            logger.warning(f"No trace data found for request_id={request_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No trace data found for request ID: {request_id}. Ensure enable_trace was set to true."
            )

        logger.info(f"Retrieved {len(traces)} trace entries for request_id={request_id}")
        return {"request_id": request_id, "traces": traces}

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve trace data for request_id={request_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve trace data: {str(e)}"
        )


@router.get(
    "/trace/{request_id}/layer/{layer_name}",
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "Request ID or layer not found"},
        500: {"description": "Failed to retrieve trace data"}
    }
)
async def get_trace_by_layer(
    request_id: str,
    layer_name: str,
    observability_store: RAGObservabilityStore = Depends(get_rag_observability_store)
):
    """
    Retrieve trace entries for a specific layer of a RAG extraction request.

    Args:
        request_id: Unique identifier for the extraction request
        layer_name: Name of the layer (kg_context, llm_extraction, spacy_gap, concept_resolution)
        observability_store: Injected observability store

    Returns:
        List of trace entries for the specified layer

    Raises:
        HTTPException 404: If request_id or layer has no trace data
        HTTPException 500: If trace retrieval fails
    """
    try:
        logger.info(f"Retrieving trace data for request_id={request_id}, layer={layer_name}")

        # Validate layer name
        valid_layers = {"kg_context", "llm_extraction", "spacy_gap", "concept_resolution"}
        if layer_name not in valid_layers:
            logger.warning(f"Invalid layer name: {layer_name}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid layer name. Must be one of: {', '.join(valid_layers)}"
            )

        # Get all traces and filter by layer
        all_traces = observability_store.get_traces(request_id)

        if not all_traces:
            logger.warning(f"No trace data found for request_id={request_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No trace data found for request ID: {request_id}"
            )

        # Filter traces by layer name
        layer_traces = [trace for trace in all_traces if trace["layer_name"] == layer_name]

        if not layer_traces:
            logger.warning(f"No trace data found for request_id={request_id}, layer={layer_name}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No trace data found for layer: {layer_name}"
            )

        logger.info(f"Retrieved {len(layer_traces)} trace entries for request_id={request_id}, layer={layer_name}")
        return {
            "request_id": request_id,
            "layer_name": layer_name,
            "traces": layer_traces
        }

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(
            f"Failed to retrieve trace data for request_id={request_id}, layer={layer_name}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve trace data: {str(e)}"
        )


@router.delete(
    "/trace/{request_id}",
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "Request ID not found"},
        500: {"description": "Failed to delete trace data"}
    }
)
async def delete_trace(
    request_id: str,
    observability_store: RAGObservabilityStore = Depends(get_rag_observability_store)
):
    """
    Manually delete trace data for a specific RAG extraction request.

    This is useful for immediate cleanup of sensitive data or testing purposes.
    Note that trace data is automatically cleaned up after the retention period.

    Args:
        request_id: Unique identifier for the extraction request
        observability_store: Injected observability store

    Returns:
        Success message with deletion confirmation

    Raises:
        HTTPException 404: If request_id has no trace data
        HTTPException 500: If deletion fails
    """
    try:
        logger.info(f"Deleting trace data for request_id={request_id}")

        # Check if trace data exists
        traces = observability_store.get_traces(request_id)
        if not traces:
            logger.warning(f"No trace data found for request_id={request_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No trace data found for request ID: {request_id}"
            )

        # Delete traces using raw SQL
        from sqlalchemy import text
        result = observability_store.db_session.execute(
            text("DELETE FROM rag_observability_trace WHERE request_id = :request_id"),
            {"request_id": request_id}
        )
        observability_store.db_session.commit()

        deleted_count = result.rowcount
        logger.info(f"Deleted {deleted_count} trace entries for request_id={request_id}")

        return {
            "message": "Trace data deleted successfully",
            "request_id": request_id,
            "traces_deleted": deleted_count
        }

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        observability_store.db_session.rollback()
        logger.error(f"Failed to delete trace data for request_id={request_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete trace data: {str(e)}"
        )


@router.post(
    "/config/update",
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Invalid configuration parameters"},
        500: {"description": "Failed to update configuration"}
    }
)
async def update_config(
    config_updates: Dict[str, Any],
    pipeline_service: RAGPipelineService = Depends(get_rag_pipeline_service)
):
    """
    Update RAG pipeline configuration settings.

    Accepts partial updates to pipeline configuration, including:
    - timeout_layer_0: Timeout for Layer 0 (KG context) in seconds
    - timeout_layer_1: Timeout for Layer 1 (LLM extraction) in seconds
    - timeout_layer_2: Timeout for Layer 2 (spaCy gap) in seconds
    - timeout_layer_3: Timeout for Layer 3 (concept resolution) in seconds
    - timeout_total: Total pipeline timeout in seconds
    - dedup_similarity_threshold: Entity deduplication similarity threshold (0.0-1.0)
    - kg_top_k: Number of top KG nodes to retrieve

    Args:
        config_updates: Dictionary of configuration parameters to update
        pipeline_service: Injected RAG pipeline service

    Returns:
        Updated configuration values

    Raises:
        HTTPException 400: If configuration parameters are invalid
        HTTPException 500: If configuration update fails
    """
    try:
        logger.info(f"Updating RAG pipeline configuration: {config_updates}")

        # Validate and apply configuration updates
        updated_config = {}

        # Valid configuration keys
        valid_keys = {
            "timeout_layer_0", "timeout_layer_1", "timeout_layer_2", "timeout_layer_3",
            "timeout_total", "dedup_similarity_threshold", "kg_top_k"
        }

        # Check for invalid keys
        invalid_keys = set(config_updates.keys()) - valid_keys
        if invalid_keys:
            logger.warning(f"Invalid configuration keys: {invalid_keys}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid configuration keys: {', '.join(invalid_keys)}. Valid keys: {', '.join(valid_keys)}"
            )

        # Apply timeout updates
        for timeout_key in ["timeout_layer_0", "timeout_layer_1", "timeout_layer_2", "timeout_layer_3", "timeout_total"]:
            if timeout_key in config_updates:
                value = config_updates[timeout_key]
                if not isinstance(value, (int, float)) or value <= 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"{timeout_key} must be a positive number"
                    )
                setattr(pipeline_service, timeout_key.upper(), float(value))
                updated_config[timeout_key] = float(value)

        # Apply deduplication threshold update
        if "dedup_similarity_threshold" in config_updates:
            value = config_updates["dedup_similarity_threshold"]
            if not isinstance(value, (int, float)) or not (0.0 <= value <= 1.0):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="dedup_similarity_threshold must be a number between 0.0 and 1.0"
                )
            pipeline_service.DEDUP_SIMILARITY_THRESHOLD = float(value)
            updated_config["dedup_similarity_threshold"] = float(value)

        # Apply KG top-k update
        if "kg_top_k" in config_updates:
            value = config_updates["kg_top_k"]
            if not isinstance(value, int) or value <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="kg_top_k must be a positive integer"
                )
            pipeline_service.kg_processor.top_k = value
            updated_config["kg_top_k"] = value

        logger.info(f"Configuration updated successfully: {updated_config}")

        return {
            "message": "Configuration updated successfully",
            "updated_config": updated_config,
            "current_config": {
                "timeout_layer_0": pipeline_service.TIMEOUT_LAYER_0,
                "timeout_layer_1": pipeline_service.TIMEOUT_LAYER_1,
                "timeout_layer_2": pipeline_service.TIMEOUT_LAYER_2,
                "timeout_layer_3": pipeline_service.TIMEOUT_LAYER_3,
                "timeout_total": pipeline_service.TIMEOUT_TOTAL,
                "dedup_similarity_threshold": pipeline_service.DEDUP_SIMILARITY_THRESHOLD,
                "kg_top_k": pipeline_service.kg_processor.top_k
            }
        }

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Failed to update configuration: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update configuration: {str(e)}"
        )
