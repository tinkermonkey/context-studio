"""
FastAPI routes for the Knowledge Extraction bounded context.

This module implements HTTP endpoints for knowledge extraction:
- POST /api/extract — Extract entities from text through coordinated layers
- POST /api/analyze_text — Analyze text for linguistic features and named entities
- POST /api/enrich_from_references — Enrich extracted entities with external knowledge
- POST /api/extraction/extract — Extract RDF triples from text scoped to an ontology

Each endpoint is a thin adapter that:
1. Receives HTTP request + parsed Pydantic schema
2. Calls domain service with domain entities
3. Catches domain exceptions and maps to HTTP status codes
4. Returns response schema serialized as JSON

No business logic lives here—all validation and constraints are in the domain service.
Error handling translates domain exceptions to appropriate HTTP responses.
"""

import time

from fastapi import APIRouter, Depends, HTTPException, status

from adapters.web.dependencies import get_extraction_service
from adapters.web.schemas.extraction import (
    AnalyzeTextRequest,
    EnrichFromReferencesRequest,
    ExtractedEntitySchema,
    ExtractionLayerResultSchema,
    ExtractionResultSchema,
    ExtractRequest,
    ExtractTripleRequest,
    ExtractTripleResponse,
    Triple,
    TripleNode,
    TriplePredicate,
    TripleProvenance,
)
from domain.extraction.entities import ExtractedEntity
from domain.extraction.exceptions import (
    ExtractionError,
    InvalidInputError,
    LayerExecutionError,
)
from domain.extraction.services import ExtractionService
from utils.async_executor import run_sync_in_executor
from utils.logger import get_logger

router = APIRouter(prefix="/api", tags=["extraction"])

_logger = get_logger(__name__)


# ==================== Error Handler Utilities ====================


def _handle_domain_error(exc: Exception) -> tuple[int, str]:
    """
    Map domain exceptions to HTTP status codes and error messages.

    Args:
        exc: The domain exception

    Returns:
        Tuple of (status_code, error_message)
    """
    if isinstance(exc, InvalidInputError):
        return (status.HTTP_400_BAD_REQUEST, str(exc))
    elif isinstance(exc, LayerExecutionError):
        _logger.error(f"Extraction layer execution error: {exc}", exc_info=exc)
        return (
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Extraction layer failed to execute",
        )
    elif isinstance(exc, ExtractionError):
        return (status.HTTP_400_BAD_REQUEST, str(exc))
    else:
        # Log the original exception for unexpected errors
        _logger.error(f"Unexpected error in extraction endpoint: {exc}", exc_info=exc)
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
                matched_class_id=e.matched_class_id,
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
        result = await run_sync_in_executor(service.extract, request.text)
        return _to_schema(result)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.post(
    "/analyze_text",
    response_model=ExtractionResultSchema,
    status_code=status.HTTP_200_OK,
)
async def analyze_text(
    request: AnalyzeTextRequest,
    service: ExtractionService = Depends(get_extraction_service),
) -> ExtractionResultSchema:
    """
    Analyze text for linguistic features and named entities.

    This use case focuses on NLP-based analysis including tokenization,
    entity recognition, language detection, and linguistic features.
    It may also provide context from the knowledge graph.

    Layers executed:
    - Layer 0: Knowledge graph context (uses embedding similarity)
    - Layer 2: NLP gap-filling (focused entity recognition)

    Args:
        request: AnalyzeTextRequest with text to analyze
        service: ExtractionService from dependency injection

    Returns:
        ExtractionResultSchema containing analyzed entities and linguistic metadata

    Raises:
        HTTPException: 400 if text is empty/invalid, 500 for internal errors
    """
    try:
        result = await run_sync_in_executor(service.analyze_text, request.text)
        return _to_schema(result)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.post(
    "/enrich_from_references",
    response_model=ExtractionResultSchema,
    status_code=status.HTTP_200_OK,
)
async def enrich_from_references(
    request: EnrichFromReferencesRequest,
    service: ExtractionService = Depends(get_extraction_service),
) -> ExtractionResultSchema:
    """
    Enrich extracted entities with external reference knowledge.

    This use case takes already-extracted entities and enriches them with
    URIs, metadata, and relationships from external knowledge sources such as
    ConceptNet, DBpedia, Wikidata, and schema.org.

    Layers executed:
    - Layer 3: Reference source enrichment (adds URIs and metadata)

    Args:
        request: EnrichFromReferencesRequest with text and entities to enrich
        service: ExtractionService from dependency injection

    Returns:
        ExtractionResultSchema with enriched entities and reference metadata

    Raises:
        HTTPException: 400 if text is empty/invalid, 500 for internal errors
    """
    try:
        extracted_entities = [
            ExtractedEntity(
                id=entity.id,
                label=entity.label,
                entity_type=entity.entity_type,
                source_layer=entity.source_layer,
                confidence=entity.confidence,
                uri=entity.uri,
                description=entity.description,
                matched_class_id=entity.matched_class_id,
                properties=entity.properties,
            )
            for entity in request.extracted_entities
        ]

        result = await run_sync_in_executor(
            service.enrich_from_references, request.text, extracted_entities
        )
        return _to_schema(result)
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)


@router.post(
    "/extraction/extract",
    response_model=ExtractTripleResponse,
    status_code=status.HTTP_200_OK,
)
async def extract_triples(
    request: ExtractTripleRequest,
    service: ExtractionService = Depends(get_extraction_service),
) -> ExtractTripleResponse:
    """
    Extract RDF triples from text scoped to an ontology.

    This endpoint accepts text and an ontology ID, then returns extracted RDF triples
    with subject-predicate-object structure for knowledge graph construction.

    Args:
        request: ExtractTripleRequest with text, ontology_id, and options
        service: ExtractionService from dependency injection

    Returns:
        ExtractTripleResponse containing extracted triples, warnings, and metadata

    Raises:
        HTTPException: 400 for invalid input, 422 for validation errors, 500 for internal errors
    """
    try:
        # Validate text is not whitespace-only
        if not request.text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Text cannot be empty or whitespace-only",
            )

        # Get extraction options with defaults
        options = request.options or {}
        model = options.get("model", "gpt-4")
        temperature = float(options.get("temperature", 0.0))

        # Extract triples using domain service
        result = await run_sync_in_executor(
            service.extract_triples,
            request.text,
            request.ontology_id,
            model,
            temperature,
        )

        # Convert domain result to API response
        triples = [
            Triple(
                subject=TripleNode(
                    kind=t["subject"]["kind"],
                    id=t["subject"].get("id"),
                    label=t["subject"].get("label"),
                ),
                predicate=TriplePredicate(
                    property_definition_id=t["predicate"].get("property_definition_id"),
                    label=t["predicate"].get("label", ""),
                ),
                object=TripleNode(
                    kind=t["object"]["kind"],
                    id=t["object"].get("id"),
                    label=t["object"].get("label"),
                    value=t["object"].get("value"),
                    datatype=t["object"].get("datatype"),
                ),
                confidence=t.get("confidence", 0.0),
                provenance=TripleProvenance(
                    text_offset_start=t["provenance"].get("text_offset_start", 0),
                    text_offset_end=t["provenance"].get("text_offset_end", 0),
                    raw=t["provenance"].get("raw", ""),
                ),
            )
            for t in result.triples
        ]

        return ExtractTripleResponse(
            triples=triples,
            warnings=result.warnings,
            metadata=result.metadata,
        )
    except HTTPException:
        raise
    except Exception as exc:
        status_code, message = _handle_domain_error(exc)
        raise HTTPException(status_code=status_code, detail=message)
