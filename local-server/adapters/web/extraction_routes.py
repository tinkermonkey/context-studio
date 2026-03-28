"""
FastAPI routes for the Knowledge Extraction bounded context.

This module implements HTTP endpoints for knowledge extraction:
- POST /api/extract — Extract entities from text

Each endpoint is a thin adapter that:
1. Receives HTTP request + parsed Pydantic schema
2. Calls domain service with domain entities
3. Catches domain exceptions and maps to HTTP status codes
4. Returns response schema serialized as JSON

No business logic lives here—all validation and constraints are in the domain service.
Error handling translates domain exceptions to appropriate HTTP responses.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from domain.extraction.services import ExtractionService
from domain.extraction.exceptions import ExtractionError

from adapters.web.dependencies import get_extraction_service
from adapters.web.schemas.extraction import (
    ExtractRequest,
    ExtractionResultSchema,
    ExtractedEntitySchema,
    ExtractionLayerResultSchema,
)

router = APIRouter(prefix="/api", tags=["extraction"])


# ==================== Error Handler Utilities ====================

def _handle_domain_error(exc: Exception) -> tuple[int, str]:
    """
    Map domain exceptions to HTTP status codes and error messages.

    Args:
        exc: The domain exception

    Returns:
        Tuple of (status_code, error_message)
    """
    if isinstance(exc, ExtractionError):
        return (status.HTTP_400_BAD_REQUEST, str(exc))
    elif isinstance(exc, ValueError):
        return (status.HTTP_400_BAD_REQUEST, str(exc))
    else:
        return (status.HTTP_500_INTERNAL_SERVER_ERROR, "An unexpected error occurred")


def _to_schema(result) -> ExtractionResultSchema:
    """
    Convert domain ExtractionResult to response schema.

    Args:
        result: Domain ExtractionResult

    Returns:
        ExtractionResultSchema for JSON serialization
    """
    return ExtractionResultSchema(
        id=result.id,
        text=result.text,
        extracted_entities=[
            ExtractedEntitySchema(
                id=e.id,
                label=e.label,
                entity_type=e.entity_type,
                source_layer=e.source_layer,
                confidence=e.confidence,
                uri=e.uri,
                description=e.description,
                properties=e.properties,
            )
            for e in result.extracted_entities
        ],
        layers_executed=[
            ExtractionLayerResultSchema(
                layer_number=lr.layer_number,
                layer_name=lr.layer_name,
                entities_found=lr.entities_found,
                duration_ms=lr.duration_ms,
                success=lr.success,
                error_message=lr.error_message,
            )
            for lr in result.layers_executed
        ],
        total_duration_ms=result.total_duration_ms,
        created_at=result.created_at.isoformat(),
    )


# ==================== Extraction Endpoints ====================

@router.post("/extract", response_model=ExtractionResultSchema, status_code=status.HTTP_200_OK)
async def extract_entities(
    request: ExtractRequest,
    service: ExtractionService = Depends(get_extraction_service),
) -> ExtractionResultSchema:
    """
    Extract entities from text through coordinated extraction layers.

    Four layers execute sequentially:
    - Layer 0: Knowledge graph context (uses embedding similarity)
    - Layer 1: LLM extraction (structured JSON output)
    - Layer 2: NLP gap-filling (catches missed entities)
    - Layer 3: Reference source enrichment (adds URIs and metadata)

    Args:
        request: ExtractRequest with text to extract from
        service: ExtractionService from dependency injection

    Returns:
        ExtractionResultSchema containing extracted entities and layer metadata

    Raises:
        HTTPException: 400 if text is empty/invalid, 500 for internal errors
    """
    try:
        result = service.extract(request.text)
        return _to_schema(result)
    except (ExtractionError, ValueError) as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)
