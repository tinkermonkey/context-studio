"""API endpoints for predicate management."""

import datetime
import json
import time
import asyncio
from fastapi import APIRouter, HTTPException, Query, Depends, BackgroundTasks
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from database import models
from database.utils import get_db
from database.predicate_utils import generate_identifier_from_title, import_conceptnet_predicates, get_conceptnet_relation_for_predicate, validate_predicate_identifier
from database.mapping_validation import validate_mapping, validate_mapping_json
from config import get_settings, get_config_manager
from api.api_errors import validation_error_response, conflict_error_response, bad_request_error_response
from utils.logger import get_logger

logger = get_logger("predicates_api")
router = APIRouter()

# Store background task status
_discovery_tasks = {}


def validate_uuid_format(uuid_string: str) -> bool:
    """Validate that a string is a valid UUID format."""
    try:
        UUID(uuid_string)
        return True
    except ValueError:
        return False


# Pydantic models for Predicate
class PredicateBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    definition: Optional[str] = None
    mapping: Optional[dict] = None  # Will be serialized to JSON


class PredicateCreate(PredicateBase):
    identifier: Optional[str] = None  # Auto-generated if not provided


class PredicateUpdate(BaseModel):
    title: Optional[str] = None
    definition: Optional[str] = None
    mapping: Optional[dict] = None
    identifier: Optional[str] = None  # Allow identifier updates with validation
    is_relevant: Optional[bool] = None  # For marking predicate relevance


class PredicateOut(PredicateBase):
    id: str  # UUID as string to match database storage
    identifier: str
    date_created: str  # ISO8601
    date_modified: str  # ISO8601

    model_config = ConfigDict(from_attributes=True)


class PaginatedPredicatesResponse(BaseModel):
    data: List[PredicateOut]
    total: int
    skip: int
    limit: int


def to_predicate_out(predicate: models.Predicate) -> PredicateOut:
    """Convert database model to API response model."""
    mapping_dict = None
    if predicate.mapping:
        try:
            mapping_dict = json.loads(predicate.mapping)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in predicate {predicate.id} mapping: {predicate.mapping}")
            mapping_dict = None
    
    return PredicateOut(
        id=predicate.id,
        identifier=predicate.identifier,
        title=predicate.title,
        definition=predicate.definition,
        mapping=mapping_dict,
        date_created=predicate.date_created.isoformat(),
        date_modified=predicate.date_modified.isoformat()
    )


@router.post("/", response_model=PredicateOut, status_code=201)
def create_predicate(predicate: PredicateCreate, db: Session = Depends(get_db)):
    """Create a new predicate."""
    if not predicate.title or not predicate.title.strip():
        raise HTTPException(status_code=400, detail="Predicate title must not be empty.")

    # Generate identifier if not provided
    identifier = predicate.identifier
    if not identifier:
        identifier = generate_identifier_from_title(predicate.title)

    # Validate identifier uniqueness
    if not validate_predicate_identifier(identifier, None, db):
        raise HTTPException(status_code=409, detail=f"Predicate with identifier '{identifier}' already exists.")

    # Validate title uniqueness
    if db.query(models.Predicate).filter_by(title=predicate.title).first():
        raise HTTPException(status_code=409, detail=f"Predicate with title '{predicate.title}' already exists.")

    # Serialize mapping to JSON if provided
    mapping_json = None
    if predicate.mapping:
        try:
            mapping_json = json.dumps(predicate.mapping)
        except (TypeError, ValueError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid mapping format: {str(e)}")

    try:
        db_predicate = models.Predicate(
            id=str(uuid4()),
            identifier=identifier,
            title=predicate.title,
            definition=predicate.definition,
            mapping=mapping_json,
            date_created=datetime.datetime.now(datetime.UTC),
            date_modified=datetime.datetime.now(datetime.UTC)
        )
        db.add(db_predicate)
        db.commit()
        db.refresh(db_predicate)

        return to_predicate_out(db_predicate)

    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Predicate with this identifier or title already exists.")


@router.get("/", response_model=PaginatedPredicatesResponse)
def list_predicates(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    sortBy: str = Query("title", pattern="^(title|identifier|date_created)$"),
    db: Session = Depends(get_db)
):
    """List predicates with pagination and sorting."""
    # Build base query
    query = db.query(models.Predicate)

    # Get total count
    total = query.count()

    # Apply sorting
    if sortBy == "title":
        query = query.order_by(models.Predicate.title)
    elif sortBy == "identifier":
        query = query.order_by(models.Predicate.identifier)
    elif sortBy == "date_created":
        query = query.order_by(models.Predicate.date_created.desc())

    # Apply pagination
    predicates = query.offset(skip).limit(limit).all()

    # Convert to response models
    result = [to_predicate_out(p) for p in predicates]

    return PaginatedPredicatesResponse(
        data=result,
        total=total,
        skip=skip,
        limit=limit
    )


# ConceptNet Integration Endpoints
@router.get("/conceptnet-relations", response_model=List[str])
def get_conceptnet_relations():
    """Get the list of ConceptNet relations configured in the system."""
    settings = get_settings()
    return settings.concepcy_config["relations_of_interest"]


@router.get("/conceptnet-mapping", response_model=Dict[str, str])
def get_conceptnet_mapping(db: Session = Depends(get_db)):
    """Get a mapping of all predicate identifiers to their ConceptNet relations."""
    predicates = db.query(models.Predicate).all()
    mapping = {}

    for predicate in predicates:
        conceptnet_relation = get_conceptnet_relation_for_predicate(predicate)
        if conceptnet_relation:
            mapping[predicate.identifier] = conceptnet_relation

    return mapping


@router.get("/by-identifier/{identifier}", response_model=PredicateOut, responses={404: {"description": "Predicate not found"}})
def get_predicate_by_identifier(identifier: str, db: Session = Depends(get_db)):
    """Get a predicate by its identifier."""
    predicate = db.query(models.Predicate).filter_by(identifier=identifier).first()
    if not predicate:
        raise HTTPException(status_code=404, detail="Predicate not found.")

    return to_predicate_out(predicate)


# External Predicate Discovery Endpoints (Phase 2)

class PredicateDiscoveryResponse(BaseModel):
    """Response for predicate discovery requests."""
    task_id: str
    status: str = "started"
    message: str


class PredicateDiscoveryStatus(BaseModel):
    """Status of a predicate discovery task."""
    task_id: str
    status: str  # "pending", "running", "completed", "failed"
    sources: Optional[List[str]] = None
    results: Optional[Dict[str, Dict[str, Any]]] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class ExternalPredicateOut(BaseModel):
    """Response model for external predicates."""
    id: str
    title: str
    definition: str
    source: str
    external_id: str
    attributes: Optional[Dict[str, Any]] = None
    created_at: str
    updated_at: str


class PaginatedExternalPredicatesResponse(BaseModel):
    """Paginated response for external predicates."""
    data: List[ExternalPredicateOut]
    total: int
    skip: int
    limit: int
    source: Optional[str] = None


@router.get("/discover/{task_id}", response_model=PredicateDiscoveryStatus)
def get_discovery_status(task_id: str):
    """
    Get the status of a predicate discovery task.

    Returns the current status and results (if completed) of the discovery task.
    """
    if task_id not in _discovery_tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    return PredicateDiscoveryStatus(**_discovery_tasks[task_id])


@router.get("/external", response_model=PaginatedExternalPredicatesResponse)
def list_external_predicates(
    source: Optional[str] = Query(None, description="Filter by source (conceptnet, dbpedia, wikidata)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
):
    """
    List external predicates with pagination.

    Returns predicates discovered from external knowledge sources with optional source filtering.
    """
    from reference_db.dependencies import reference_manager_context
    from reference_db.config import ReferenceConfig

    try:
        config = ReferenceConfig()
        with reference_manager_context(config) as manager:
            # Get all predicates (we'll paginate in memory since we need the count anyway)
            from reference_db.models import ExternalPredicate
            query = manager.session.query(ExternalPredicate)
            if source:
                query = query.filter_by(source=source)
            
            # Get all matching predicates
            all_predicates = query.all()
            total = len(all_predicates)
            
            # Paginate in memory
            paginated = all_predicates[skip:skip + limit]

            # Format response
            data = []
            for predicate in paginated:
                # Parse attributes if present
                attrs = None
                if predicate.attributes:
                    try:
                        import ast
                        attrs = ast.literal_eval(predicate.attributes)
                    except:
                        attrs = {"raw": predicate.attributes}

                data.append(ExternalPredicateOut(
                    id=predicate.id,
                    title=predicate.title,
                    definition=predicate.definition,
                    source=predicate.source,
                    external_id=predicate.external_id,
                    attributes=attrs,
                    created_at=predicate.created_at,
                    updated_at=predicate.updated_at
                ))

            return PaginatedExternalPredicatesResponse(
                data=data,
                total=total,
                skip=skip,
                limit=limit,
                source=source
            )

    except Exception as e:
        logger.error(f"Failed to list external predicates: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class ExternalPredicateSearchResult(BaseModel):
    """Search result for external predicates with similarity score."""
    id: str
    title: str
    definition: str
    source: str
    external_id: str
    attributes: Optional[Dict[str, Any]] = None
    created_at: str
    updated_at: str
    similarity_score: float


class ExternalPredicateSearchResponse(BaseModel):
    """Response for external predicate search."""
    data: List[ExternalPredicateSearchResult]
    total: int
    query: str
    source: Optional[str] = None
    threshold: float


@router.get("/external/search", response_model=ExternalPredicateSearchResponse)
def search_external_predicates(
    query: str = Query(..., min_length=1, description="Search query text"),
    source: Optional[str] = Query(None, description="Filter by source (conceptnet, dbpedia, wikidata, schema_org)"),
    limit: int = Query(20, ge=1, le=100),
    threshold: float = Query(0.6, ge=0.0, le=1.0, description="Minimum similarity threshold"),
):
    """
    Search external predicates using vector similarity.

    This endpoint performs semantic search across external predicates using embeddings.
    Returns predicates ranked by similarity to the query text.

    Args:
        query: Search query text (required, min 1 character)
        source: Optional source filter (conceptnet, dbpedia, wikidata, schema_org)
        limit: Maximum number of results (default: 20, max: 100)
        threshold: Minimum similarity threshold (default: 0.6, range: 0.0-1.0)

    Returns:
        ExternalPredicateSearchResponse with ranked similarity results
    """
    from reference_db.dependencies import reference_manager_context
    from reference_db.config import ReferenceConfig

    try:
        config = ReferenceConfig()
        with reference_manager_context(config) as manager:
            # Perform vector similarity search
            results = manager.search_external_predicates_by_similarity(
                query_text=query,
                source=source,
                limit=limit,
                threshold=threshold
            )

            # Format response
            data = []
            for predicate, similarity_score in results:
                # Parse attributes if present
                attrs = None
                if predicate.attributes:
                    try:
                        import ast
                        attrs = ast.literal_eval(predicate.attributes)
                    except:
                        attrs = {"raw": predicate.attributes}

                data.append(ExternalPredicateSearchResult(
                    id=predicate.id,
                    title=predicate.title,
                    definition=predicate.definition,
                    source=predicate.source,
                    external_id=predicate.external_id,
                    attributes=attrs,
                    created_at=predicate.created_at,
                    updated_at=predicate.updated_at,
                    similarity_score=similarity_score
                ))

            return ExternalPredicateSearchResponse(
                data=data,
                total=len(data),
                query=query,
                source=source,
                threshold=threshold
            )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to search external predicates: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{id}", response_model=PredicateOut, responses={404: {"description": "Predicate not found"}})
def get_predicate(id: str, db: Session = Depends(get_db)):
    """Get a predicate by ID."""
    # Validate UUID format
    if not validate_uuid_format(id):
        raise HTTPException(status_code=400, detail="Invalid UUID format.")

    predicate = db.query(models.Predicate).filter_by(id=id).first()
    if not predicate:
        raise HTTPException(status_code=404, detail="Predicate not found.")

    return to_predicate_out(predicate)


@router.put("/{id}", response_model=PredicateOut, responses={404: {"description": "Predicate not found"}})
def update_predicate(
    id: str,
    predicate: PredicateUpdate,
    db: Session = Depends(get_db)
):
    """
    Update an existing predicate.

    This endpoint implements JSON schema validation for mappings.
    """
    # Validate UUID format
    if not validate_uuid_format(id):
        raise HTTPException(status_code=400, detail="Invalid UUID format.")

    # Get predicate
    db_predicate = db.query(models.Predicate).filter_by(id=id).first()
    if not db_predicate:
        raise HTTPException(status_code=404, detail="Predicate not found.")

    try:
        # Update identifier if provided
        if predicate.identifier is not None:
            if predicate.identifier != db_predicate.identifier:
                # Validate identifier uniqueness
                if not validate_predicate_identifier(predicate.identifier, id, db):
                    raise HTTPException(status_code=409, detail=f"Predicate with identifier '{predicate.identifier}' already exists.")
                db_predicate.identifier = predicate.identifier

        # Update title if provided
        if predicate.title is not None:
            if not predicate.title.strip():
                raise HTTPException(status_code=400, detail="Predicate title must not be empty.")

            # Check title uniqueness (excluding current predicate)
            if predicate.title != db_predicate.title:
                existing = db.query(models.Predicate).filter(
                    models.Predicate.title == predicate.title,
                    models.Predicate.id != id
                ).first()
                if existing:
                    raise HTTPException(status_code=409, detail=f"Predicate with title '{predicate.title}' already exists.")

            db_predicate.title = predicate.title

        # Update definition if provided
        if predicate.definition is not None:
            db_predicate.definition = predicate.definition

        # Update is_relevant if provided
        if predicate.is_relevant is not None:
            db_predicate.is_relevant = predicate.is_relevant

        # Update mapping if provided with validation
        if predicate.mapping is not None:
            # Validate mapping structure
            is_valid, error_msg = validate_mapping(predicate.mapping)
            if not is_valid:
                raise HTTPException(status_code=400, detail=f"Invalid mapping structure: {error_msg}")

            try:
                mapping_json = json.dumps(predicate.mapping)
                db_predicate.mapping = mapping_json
            except (TypeError, ValueError) as e:
                raise HTTPException(status_code=400, detail=f"Invalid mapping format: {str(e)}")

        # Update modification timestamp
        db_predicate.date_modified = datetime.datetime.now(datetime.UTC)

        db.commit()
        db.refresh(db_predicate)

        # If relevance was updated, invalidate the reference filter cache
        if predicate.is_relevant is not None:
            try:
                from reference_db.dependencies import reference_manager_context
                from reference_db.config import ReferenceConfig
                from services.reference_filter_service import ReferenceFilterService

                ref_config = ReferenceConfig()
                with reference_manager_context(ref_config) as manager:
                    filter_service = ReferenceFilterService(db, manager)
                    filter_service.invalidate_cache()
                    logger.info(f"Invalidated reference filter cache after updating predicate {id} relevance")
            except Exception as cache_error:
                # Log but don't fail the update if cache invalidation fails
                logger.warning(f"Failed to invalidate reference filter cache: {cache_error}")

        return to_predicate_out(db_predicate)

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error updating predicate {id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update predicate: {str(e)}")


@router.delete("/{id}", status_code=200, responses={404: {"description": "Predicate not found"}})
def delete_predicate(id: str, db: Session = Depends(get_db)):
    """Delete a predicate."""
    # Validate UUID format
    if not validate_uuid_format(id):
        raise HTTPException(status_code=400, detail="Invalid UUID format.")
    
    db_predicate = db.query(models.Predicate).filter_by(id=id).first()
    if not db_predicate:
        raise HTTPException(status_code=404, detail="Predicate not found.")
    
    # Check if predicate is being used in structure_nodes or structure_node_links
    domain_usage = db.query(models.StructureNode).filter_by(structural_predicate_id=id).count()
    relationship_usage = db.query(models.StructureNodeLink).filter_by(predicate_id=id).count()
    
    if domain_usage > 0 or relationship_usage > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot delete predicate: it is used in {domain_usage} structure_nodes and {relationship_usage} structure_node relationships."
        )
    
    db.delete(db_predicate)
    db.commit()
    
    return {"success": True}


@router.post("/import-from-conceptnet", response_model=List[PredicateOut])
def import_predicates_from_conceptnet(
    relations: Optional[List[str]] = None,  # If None, import all configured relations
    db: Session = Depends(get_db)
):
    """Import predicates from ConceptNet relations."""
    settings = get_settings()
    available_relations = settings.concepcy_config["relations_of_interest"]

    # If specific relations are requested, validate and filter
    if relations:
        # Validate that all requested relations are available
        invalid_relations = [r for r in relations if r not in available_relations]
        if invalid_relations:
            return bad_request_error_response(f"Invalid ConceptNet relations: {invalid_relations}")

        # Temporarily update the config to only import requested relations
        # We'll create a modified session for this specific import
        original_relations = settings.concepcy_config["relations_of_interest"]
        settings.concepcy_config["relations_of_interest"] = relations

        try:
            imported_predicates = import_conceptnet_predicates(db)
        finally:
            # Restore original configuration
            settings.concepcy_config["relations_of_interest"] = original_relations
    else:
        # Import all configured relations
        imported_predicates = import_conceptnet_predicates(db)

    # Convert to response models
    result = [to_predicate_out(predicate) for predicate in imported_predicates]

    return result


@router.get("/{id}/conceptnet-relation", response_model=Optional[str])
def get_predicate_conceptnet_relation(id: str, db: Session = Depends(get_db)):
    """Get the ConceptNet relation for a specific predicate."""
    # Validate UUID format
    if not validate_uuid_format(id):
        raise HTTPException(status_code=400, detail="Invalid UUID format.")

    predicate = db.query(models.Predicate).filter_by(id=id).first()
    if not predicate:
        raise HTTPException(status_code=404, detail="Predicate not found.")

    relation = get_conceptnet_relation_for_predicate(predicate)
    return relation


async def _run_discovery_task(task_id: str, sources: Optional[List[str]] = None):
    """Background task to run predicate discovery."""
    from reference_db.predicate_discovery import PredicateDiscoveryService
    from reference_db.config import ReferenceConfig

    _discovery_tasks[task_id]["status"] = "running"
    _discovery_tasks[task_id]["started_at"] = datetime.datetime.now(datetime.UTC).isoformat()

    try:
        # Get configuration
        config_manager = get_config_manager()
        settings = config_manager.settings

        # Prepare source configs - only for sources that need API configuration
        # (schema_org uses local database, doesn't need external API config)
        source_configs = {}
        for source_name in ['conceptnet', 'dbpedia', 'wikidata']:
            try:
                source_config = settings.get_source_config(source_name)
                if source_config:
                    source_configs[source_name] = source_config
            except ValueError:
                # Source not configured, skip it
                logger.debug(f"Source {source_name} not configured, skipping")
                pass

        # Create reference config
        ref_config = ReferenceConfig()

        # Run discovery
        with PredicateDiscoveryService(ref_config, source_configs) as service:
            results = await service.discover_all_predicates(sources)

        # Format results
        formatted_results = {}
        for source, (created, updated, errors) in results.items():
            total_errors = len(errors)
            truncated_errors = errors[:10] if errors else []
            formatted_results[source] = {
                "created": created,
                "updated": updated,
                "error_count": total_errors,
                "errors": truncated_errors,
                "errors_truncated": total_errors > 10  # Indicate if errors were truncated
            }

        _discovery_tasks[task_id]["status"] = "completed"
        _discovery_tasks[task_id]["results"] = formatted_results
        _discovery_tasks[task_id]["completed_at"] = datetime.datetime.now(datetime.UTC).isoformat()

        logger.info(f"Discovery task {task_id} completed successfully")

    except Exception as e:
        logger.error(f"Discovery task {task_id} failed: {e}", exc_info=True)
        _discovery_tasks[task_id]["status"] = "failed"
        _discovery_tasks[task_id]["error"] = str(e)
        _discovery_tasks[task_id]["completed_at"] = datetime.datetime.now(datetime.UTC).isoformat()


@router.post("/discover", response_model=PredicateDiscoveryResponse)
async def discover_external_predicates(
    background_tasks: BackgroundTasks,
    sources: Optional[List[str]] = Query(None, description="Sources to discover from (conceptnet, dbpedia, wikidata, schema_org)")
):
    """
    Discover predicates from external knowledge sources.

    This endpoint starts a background task to fetch predicate metadata from:
    - ConceptNet (40 relations)
    - DBpedia (760 properties via SPARQL)
    - WikiData (10K properties via SPARQL)
    - Schema.org (properties from imported data)

    Returns a task_id that can be used to check the status of the discovery process.

    **Performance targets:**
    - ConceptNet: <2s for 40 relations
    - DBpedia: <10s for 760 properties
    - WikiData: <30s for 10K properties
    - Schema.org: <1s (reads from database)
    """
    # Validate sources if provided
    valid_sources = ['conceptnet', 'dbpedia', 'wikidata', 'schema_org']
    if sources:
        invalid = [s for s in sources if s not in valid_sources]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid sources: {invalid}. Valid sources: {valid_sources}"
            )

    # Generate task ID
    task_id = str(uuid4())

    # Initialize task status
    _discovery_tasks[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "sources": sources or valid_sources,
        "results": None,
        "error": None,
        "started_at": None,
        "completed_at": None
    }

    # Start background task
    background_tasks.add_task(_run_discovery_task, task_id, sources)

    return PredicateDiscoveryResponse(
        task_id=task_id,
        status="started",
        message=f"Discovery task started for sources: {sources or valid_sources}"
    )


# Predicate Similarity Search Endpoints (Phase 3)

class SimilarPredicateOut(BaseModel):
    """Response model for similar predicates."""
    predicate_id: str
    source: str
    source_id: str
    title: str
    definition: str
    similarity_score: float
    confidence: str  # "high", "medium", "low"


class FindSimilarResponse(BaseModel):
    """Response for find-similar endpoint."""
    predicate_id: str
    predicate_title: str
    results: List[SimilarPredicateOut]
    total_results: int
    search_time_ms: float
    cached: bool


class ClusterOut(BaseModel):
    """Response model for predicate clusters."""
    cluster_id: int
    predicate_ids: List[str]
    centroid_title: str
    avg_similarity: float
    size: int


class ClusterPredicatesResponse(BaseModel):
    """Response for cluster-predicates endpoint."""
    clusters: List[ClusterOut]
    total_clusters: int
    total_predicates: int
    cluster_time_ms: float


@router.post("/{id}/find-similar", response_model=FindSimilarResponse)
def find_similar_predicates(
    id: str,
    source: Optional[str] = Query(None, description="Filter by source (conceptnet, dbpedia, wikidata)"),
    limit: int = Query(100, ge=1, le=100),
    threshold: float = Query(0.7, ge=0.0, le=1.0),
    use_cache: bool = Query(True, description="Use cached results if available"),
    db: Session = Depends(get_db)
):
    """
    Find similar external predicates for a given predicate using vector similarity search.

    This endpoint:
    1. Retrieves the predicate by ID
    2. Performs vector similarity search against external predicates
    3. Returns ranked results with confidence scores
    4. Caches results for 1 hour (TTL-based)

    **Performance targets:**
    - <200ms p95 for 10K-50K predicates (PT-VS-001, PT-VS-002)
    - <50ms p95 for cached searches (PT-VS-006)

    **Confidence scores:**
    - High: similarity >= 0.85
    - Medium: similarity >= 0.70
    - Low: similarity >= 0.60
    - Results below 0.60 are rejected

    Args:
        id: UUID of the predicate to find similar predicates for
        source: Optional source filter
        limit: Maximum number of results (default: 100, max: 100)
        threshold: Minimum similarity threshold (default: 0.7)
        use_cache: Whether to use cached results (default: True)

    Returns:
        FindSimilarResponse with ranked similarity results
    """
    import time
    from services.predicate_similarity import PredicateSimilarityService
    from reference_db.dependencies import reference_manager_context
    from reference_db.config import ReferenceConfig

    start_time = time.perf_counter()
    cached = False

    # Validate UUID format
    if not validate_uuid_format(id):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid UUID format for predicate ID: '{id}'. Expected format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
        )

    # Get the predicate with explicit session management
    try:
        predicate = db.query(models.Predicate).filter_by(id=id).first()
        if not predicate:
            raise HTTPException(
                status_code=404,
                detail=f"Predicate with ID '{id}' not found in database"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database error while fetching predicate {id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Database error while fetching predicate: {str(e)}"
        )

    try:
        # Initialize services
        ref_config = ReferenceConfig()
        with reference_manager_context(ref_config) as manager:
            similarity_service = PredicateSimilarityService(manager)

            # Find similar predicates (CACHING TEMPORARILY DISABLED FOR DEBUGGING)
            logger.info(f"Finding similar predicates for: {predicate.title} (ID: {id})")
            results = similarity_service.find_similar_predicates(
                predicate_title=predicate.title,
                predicate_definition=predicate.definition,
                source=source,
                limit=limit,
                threshold=threshold,
                use_cache=False  # DISABLED: was use_cache
            )
            logger.info(f"Found {len(results)} similar predicates")

            # Check if results were cached (always False since caching disabled)
            cached = False  # DISABLED: was checking cache

            # Convert to response models
            similar_predicates = []
            for result in results:
                similar_predicates.append(SimilarPredicateOut(
                    predicate_id=result.predicate_id,
                    source=result.source,
                    source_id=result.source_id,
                    title=result.title,
                    definition=result.definition,
                    similarity_score=result.similarity_score,
                    confidence=result.confidence
                ))

            search_time_ms = (time.perf_counter() - start_time) * 1000

            return FindSimilarResponse(
                predicate_id=predicate.id,
                predicate_title=predicate.title,
                results=similar_predicates,
                total_results=len(similar_predicates),
                search_time_ms=search_time_ms,
                cached=cached
            )

    except ValueError as e:
        # Handle validation errors from service
        logger.warning(f"Validation error in find_similar_predicates: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Validation error: {str(e)}"
        )
    except Exception as e:
        error_context = {
            "predicate_id": id,
            "predicate_title": predicate.title if predicate else "unknown",
            "source": source,
            "limit": limit,
            "threshold": threshold
        }
        logger.error(
            f"Failed to find similar predicates: {e}. Context: {error_context}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to find similar predicates: {str(e)}. Please check logs for details."
        )


@router.post("/cluster-predicates", response_model=ClusterPredicatesResponse)
def cluster_predicates(
    predicate_ids: Optional[List[str]] = Query(None, description="Specific predicate IDs to cluster (if None, clusters all)"),
    min_similarity: float = Query(0.7, ge=0.0, le=1.0),
    min_cluster_size: int = Query(2, ge=2),
    eps: float = Query(0.3, ge=0.1, le=1.0, description="DBSCAN epsilon (distance threshold)"),
    max_predicates: int = Query(1000, ge=1, le=10000, description="Maximum predicates to process"),
    db: Session = Depends(get_db)
):
    """
    Cluster similar predicates using DBSCAN algorithm.

    This endpoint:
    1. Retrieves predicates (all or specified IDs)
    2. Generates embeddings for each predicate
    3. Performs density-based clustering (DBSCAN)
    4. Returns clusters with automatic count determination

    **Algorithm:** DBSCAN (Density-Based Spatial Clustering of Applications with Noise)
    - Automatically determines number of clusters
    - Handles noise points (outliers)
    - Does not require specifying cluster count in advance

    **Resource limits:**
    - Default max_predicates: 1000 (to prevent resource exhaustion)
    - For larger datasets, process in batches or increase max_predicates

    Args:
        predicate_ids: Optional list of specific predicate IDs to cluster
        min_similarity: Minimum similarity for cluster membership (default: 0.7)
        min_cluster_size: Minimum predicates per cluster (default: 2)
        eps: DBSCAN epsilon parameter - lower values create tighter clusters (default: 0.3)
        max_predicates: Maximum predicates to process (default: 1000, max: 10000)

    Returns:
        ClusterPredicatesResponse with clusters and statistics
    """
    import time
    from services.predicate_similarity import PredicateSimilarityService
    from reference_db.dependencies import reference_manager_context
    from reference_db.config import ReferenceConfig

    start_time = time.perf_counter()

    try:
        # Get predicates with explicit session management
        if predicate_ids:
            # Validate UUID formats
            for pred_id in predicate_ids:
                if not validate_uuid_format(pred_id):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid UUID format for predicate ID: '{pred_id}'. Expected format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                    )

            # Get specified predicates
            try:
                predicates = db.query(models.Predicate).filter(
                    models.Predicate.id.in_(predicate_ids)
                ).all()
            except Exception as e:
                logger.error(f"Database error while fetching predicates: {e}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"Database error while fetching predicates: {str(e)}"
                )

            if len(predicates) != len(predicate_ids):
                found_ids = {p.id for p in predicates}
                missing_ids = set(predicate_ids) - found_ids
                raise HTTPException(
                    status_code=404,
                    detail=f"Predicates not found with IDs: {list(missing_ids)[:10]}"  # Limit to 10 for readability
                )
        else:
            # Get all predicates (limit to max_predicates for safety)
            try:
                predicates = db.query(models.Predicate).limit(max_predicates + 1).all()
            except Exception as e:
                logger.error(f"Database error while fetching all predicates: {e}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"Database error while fetching predicates: {str(e)}"
                )

            if len(predicates) > max_predicates:
                raise HTTPException(
                    status_code=400,
                    detail=f"Too many predicates to cluster: {len(predicates)} (max: {max_predicates}). "
                           f"Please specify predicate_ids or increase max_predicates parameter."
                )

        if len(predicates) < min_cluster_size:
            raise HTTPException(
                status_code=400,
                detail=f"Not enough predicates for clustering. Need at least {min_cluster_size}, got {len(predicates)}"
            )

        # Prepare predicate data for clustering
        predicate_data = [
            (p.id, p.title, p.definition)
            for p in predicates
        ]

        # Initialize services and perform clustering
        ref_config = ReferenceConfig()
        with reference_manager_context(ref_config) as manager:
            similarity_service = PredicateSimilarityService(manager)

            cluster_results = similarity_service.cluster_predicates(
                predicates=predicate_data,
                min_similarity=min_similarity,
                min_cluster_size=min_cluster_size,
                eps=eps,
                max_predicates=max_predicates
            )

            # Convert to response models
            clusters = []
            total_clustered_predicates = 0

            for cluster in cluster_results:
                clusters.append(ClusterOut(
                    cluster_id=cluster.cluster_id,
                    predicate_ids=cluster.predicate_ids,
                    centroid_title=cluster.centroid_title,
                    avg_similarity=cluster.avg_similarity,
                    size=cluster.size
                ))
                total_clustered_predicates += cluster.size

            cluster_time_ms = (time.perf_counter() - start_time) * 1000

            return ClusterPredicatesResponse(
                clusters=clusters,
                total_clusters=len(clusters),
                total_predicates=total_clustered_predicates,
                cluster_time_ms=cluster_time_ms
            )

    except HTTPException:
        raise
    except ValueError as e:
        # Handle validation errors from service
        logger.warning(f"Validation error in cluster_predicates: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Validation error: {str(e)}"
        )
    except Exception as e:
        error_context = {
            "predicate_count": len(predicate_ids) if predicate_ids else "all",
            "min_similarity": min_similarity,
            "min_cluster_size": min_cluster_size,
            "eps": eps,
            "max_predicates": max_predicates
        }
        logger.error(
            f"Failed to cluster predicates: {e}. Context: {error_context}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cluster predicates: {str(e)}. Please check logs for details."
        )


@router.post("/invalidate-similarity-cache", status_code=200)
def invalidate_similarity_cache():
    """
    Invalidate the similarity search cache.

    This should be called when external predicates are updated to ensure
    fresh results in similarity searches.

    **Use cases:**
    - After running predicate discovery
    - After updating external predicate definitions
    - When stale cache results are suspected

    Returns:
        Success message with cache statistics
    """
    from services.predicate_similarity import PredicateSimilarityService
    from reference_db.dependencies import reference_manager_context
    from reference_db.config import ReferenceConfig

    try:
        ref_config = ReferenceConfig()
        with reference_manager_context(ref_config) as manager:
            similarity_service = PredicateSimilarityService(manager)

            # Get cache stats before invalidation
            cache_stats_before = similarity_service.get_cache_stats()

            # Invalidate cache
            similarity_service.invalidate_cache()

            return {
                "success": True,
                "message": "Similarity search cache invalidated successfully",
                "cache_entries_cleared": cache_stats_before["size"]
            }

    except Exception as e:
        logger.error(f"Failed to invalidate cache: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to invalidate similarity cache: {str(e)}"
        )
