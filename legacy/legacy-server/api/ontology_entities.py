"""
Ontology Entities API Endpoints

This module implements the new ontology_entities API endpoints using new terminology  # noqa: E501
(taxonomy, concept_scheme, class) alongside the existing structure_nodes API.

Endpoints:
- POST /api/ontology_entities/ - Create a new entity
- GET /api/ontology_entities/{entity_id} - Get a specific entity
- GET /api/ontology_entities/ - List entities with filtering and pagination
- PUT /api/ontology_entities/{entity_id} - Update an entity
- DELETE /api/ontology_entities/{entity_id} - Delete an entity and its children
- POST /api/ontology_entities/find - Vector search across entities
- POST /api/ontology_entities/relationships - Create an entity relationship
- GET /api/ontology_entities/relationships - List entity relationships
- PUT /api/ontology_entities/relationships/{rel_id} - Update an entity relationship  # noqa: E501
- DELETE /api/ontology_entities/relationships/{rel_id} - Delete an entity relationship  # noqa: E501
"""

from uuid import UUID

from database.sql_builders import build_max_similarity_case_when
from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Path,
    Query,
    Response,
)
from services.exceptions import ConflictError, NotFoundError, ValidationError
from services.node_link_service import NodeLinkService
from services.node_service import NodeService

from api.api_errors import conflict_error_response
from api.dependencies.structure_nodes import (
    get_node_link_service,
    get_node_service,
    get_node_service_simple,
)
from api.models.ontology_entities import (
    EntityCreate,
    EntityOut,
    EntitySearchRequest,
    EntitySearchResult,
    EntityTypeEnum,
    EntityUpdate,
    PaginatedEntitiesResponse,
    PaginatedRelationshipsResponse,
    RelationshipCreate,
    RelationshipOut,
)
from api.utils.node_conversion import normalize_legacy_node_type_to_db, uuid_to_str

router = APIRouter(prefix="/api/ontology_entities", tags=["ontology_entities"])


def _normalize_entity_type(entity_type: str) -> str:
    """
    Normalize entity type to new ontology terminology.
    Accepts both old and new terminology, returns new terminology.
    """
    return normalize_legacy_node_type_to_db(entity_type)


def _to_entity_out(node_orm_object) -> EntityOut:
    """
    Convert a Node ORM object to EntityOut response model using new terminology.  # noqa: E501
    """
    return EntityOut(
        id=(
            UUID(str(node_orm_object.id))
            if hasattr(node_orm_object.id, "__str__")
            else node_orm_object.id
        ),
        node_type=EntityTypeEnum(
            _normalize_entity_type(node_orm_object.node_type)
        ),
        parent_entity_id=(
            UUID(str(node_orm_object.parent_node_id))
            if node_orm_object.parent_node_id
            else None
        ),
        title=node_orm_object.title,
        definition=node_orm_object.definition,
        structural_predicate_id=(
            UUID(str(node_orm_object.structural_predicate_id))
            if node_orm_object.structural_predicate_id
            else None
        ),
        created_at=(
            node_orm_object.created_at.isoformat()
            if hasattr(node_orm_object.created_at, "isoformat")
            else str(node_orm_object.created_at)
        ),
        version=node_orm_object.version,
        last_modified=(
            node_orm_object.last_modified.isoformat()
            if hasattr(node_orm_object.last_modified, "isoformat")
            else str(node_orm_object.last_modified)
        ),
    )


def _to_relationship_out(link_orm_object) -> RelationshipOut:
    """
    Convert a NodeLink ORM object to RelationshipOut response model using new terminology.  # noqa: E501
    """
    return RelationshipOut(
        id=(
            UUID(str(link_orm_object.id))
            if hasattr(link_orm_object.id, "__str__")
            else link_orm_object.id
        ),
        source_entity_id=(
            UUID(str(link_orm_object.source_node_id))
            if hasattr(link_orm_object.source_node_id, "__str__")
            else link_orm_object.source_node_id
        ),
        target_entity_id=(
            UUID(str(link_orm_object.target_node_id))
            if hasattr(link_orm_object.target_node_id, "__str__")
            else link_orm_object.target_node_id
        ),
        predicate=link_orm_object.predicate,
        predicate_id=(
            UUID(str(link_orm_object.predicate_id))
            if link_orm_object.predicate_id
            else None
        ),
        created_at=(
            link_orm_object.created_at.isoformat()
            if hasattr(link_orm_object.created_at, "isoformat")
            else str(link_orm_object.created_at)
        ),
    )


@router.post("/", response_model=EntityOut, status_code=201)
def create_entity(
    entity: EntityCreate,
    response: Response,
    node_service: NodeService = Depends(get_node_service),
):
    """
    Create a new ontology entity.

    This endpoint handles creation of taxonomies, concept_schemes, and classes through  # noqa: E501
    the unified ontology_entities interface. Type-specific validation is enforced:  # noqa: E501
    - Taxonomies cannot have parent entities
    - Concept schemes must have a taxonomy parent
    - Classes must have a concept_scheme parent
    """
    from utils.logger import get_logger

    from api.graph import invalidate_graph_cache

    logger = get_logger(__name__)

    try:
        # Convert API model to service data using new terminology
        node_data = {
            "node_type": _normalize_entity_type(entity.node_type.value),
            "parent_node_id": uuid_to_str(entity.parent_entity_id),
            "title": entity.title,
            "definition": entity.definition,
            "structural_predicate_id": uuid_to_str(
                entity.structural_predicate_id
            ),
        }

        created_node = node_service.create_node(node_data)

        # Invalidate graph cache so hierarchy updates are immediately visible
        invalidate_graph_cache()

        return _to_entity_out(created_node)

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConflictError as e:
        return conflict_error_response(str(e))
    except ValueError as e:
        error_msg = str(e)
        if "unique" in error_msg.lower():
            return conflict_error_response(error_msg)
        else:
            raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        logger.error(
            f"Unexpected error creating entity: {type(e).__name__}: {e!s}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {e!s}"
        )


@router.get("/", response_model=PaginatedEntitiesResponse)
def list_entities(
    node_type: EntityTypeEnum | None = Query(
        None, description="Filter by entity type"
    ),
    parent_entity_id: UUID | None = Query(
        None, description="Filter by parent entity ID"
    ),
    skip: int = Query(0, ge=0, description="Number of entities to skip"),
    limit: int = Query(
        50, ge=1, le=1000, description="Maximum number of entities to return"
    ),
    sort_by: str = Query(
        "title", pattern="^(title|created_at)$", description="Sort field"
    ),
    node_service: NodeService = Depends(get_node_service_simple),
):
    """
    List ontology entities with filtering and pagination.

    Supports filtering by entity type and parent, with configurable pagination
    and sorting.
    """
    try:
        import time

        from utils.logger import get_logger

        logger = get_logger(__name__)
        request_start = time.time()

        # Normalize API entity type to new terminology
        db_node_type = None
        if node_type:
            db_node_type = _normalize_entity_type(node_type.value)

        # Convert UUID to string for parent_entity_id
        parent_entity_id_str = (
            str(parent_entity_id) if parent_entity_id else None
        )

        setup_time = time.time() - request_start
        logger.debug(f"API setup time: {setup_time*1000:.2f}ms")

        # Get total count
        count_start = time.time()
        total = node_service.count_nodes(
            node_type=db_node_type, parent_node_id=parent_entity_id_str
        )
        count_time = time.time() - count_start
        logger.debug(f"Count query time: {count_time*1000:.2f}ms")

        # Get entities using NodeService with pagination
        list_start = time.time()
        entities = node_service.list_nodes(
            node_type=db_node_type,
            parent_node_id=parent_entity_id_str,
            skip=skip,
            limit=limit,
        )
        list_time = time.time() - list_start
        logger.debug(f"List query time: {list_time*1000:.2f}ms")

        # Convert to response format
        serialization_start = time.time()
        response_data = {
            "data": [_to_entity_out(entity) for entity in entities],
            "total": total,
            "skip": skip,
            "limit": limit,
        }
        serialization_time = time.time() - serialization_start
        logger.debug(
            f"Response serialization time: {serialization_time*1000:.2f}ms"
        )

        pydantic_start = time.time()
        result = PaginatedEntitiesResponse(**response_data)
        pydantic_time = time.time() - pydantic_start
        logger.debug(f"Pydantic model time: {pydantic_time*1000:.2f}ms")

        total_time = time.time() - request_start
        logger.debug(
            f"Total API endpoint time: {total_time*1000:.2f}ms (skip={skip})"
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {e!s}"
        )


@router.post("/find", response_model=list[EntitySearchResult])
def search_entities(
    search_request: EntitySearchRequest,
    node_service: NodeService = Depends(get_node_service),
):
    """
    Vector search across ontology entities.

    Supports semantic search across entity titles and definitions with optional
    type filtering and configurable similarity thresholds.
    """
    from embeddings.generate_embeddings import generate_embedding
    from sqlalchemy import text
    from utils.logger import get_logger

    logger = get_logger(__name__)

    try:
        # Generate embedding for query
        query_embedding = generate_embedding(search_request.query)

        # Build query with optional node_type filter
        type_filter = ""
        params = {
            "query_vec": query_embedding,
            "threshold": search_request.threshold,
            "limit": search_request.limit,
        }

        if search_request.node_type:
            db_node_type = _normalize_entity_type(
                search_request.node_type.value
            )
            type_filter = "AND node_type = :node_type"
            params["node_type"] = db_node_type

        similarity_case = build_max_similarity_case_when()
        query = text(f"""
            WITH similarities AS (
                SELECT
                    id,
                    title,
                    node_type,
                    definition,
                    parent_entity_id,
                    structural_predicate_id,
                    created_at,
                    last_modified,
                    title_embedding,
                    definition_embedding,
                    {similarity_case} as similarity
                FROM ontology_entities
                WHERE (title_embedding IS NOT NULL OR definition_embedding IS NOT NULL)  # noqa: E501
                {type_filter}
            )
            SELECT
                id,
                title,
                node_type,
                definition,
                parent_entity_id,
                structural_predicate_id,
                created_at,
                last_modified,
                similarity
            FROM similarities
            WHERE similarity >= :threshold
            ORDER BY similarity DESC
            LIMIT :limit
        """)

        results = node_service.db.execute(query, params).fetchall()

        # Convert results to EntitySearchResult objects
        search_results = []
        for row in results:
            result = EntitySearchResult(
                id=row.id,
                node_type=EntityTypeEnum(
                    _normalize_entity_type(row.node_type)
                ),
                parent_entity_id=row.parent_entity_id,
                title=row.title,
                definition=row.definition,
                structural_predicate_id=row.structural_predicate_id,
                created_at=(
                    row.created_at.isoformat()
                    if hasattr(row.created_at, "isoformat")
                    else str(row.created_at)
                ),
                version=1,  # Use version 1 as placeholder for search results
                last_modified=(
                    row.last_modified.isoformat()
                    if hasattr(row.last_modified, "isoformat")
                    else str(row.last_modified)
                ),
                score=float(row.similarity),
                distance=1.0 - float(row.similarity),
            )
            search_results.append(result)

        return search_results

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Invalid search parameters: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Vector search failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Vector search failed: {e!s}"
        )


# Entity Relationships endpoints
@router.post("/relationships", response_model=RelationshipOut, status_code=201)
def create_relationship(
    link: RelationshipCreate,
    link_service: NodeLinkService = Depends(get_node_link_service),
):
    """
    Create a new entity relationship.

    Links can only be created between entities of the same type (taxonomies to taxonomies,  # noqa: E501
    concept_schemes to concept_schemes, classes to classes).
    """
    from api.graph import invalidate_graph_cache

    try:
        # Convert API model to service data
        link_data = {
            "source_node_id": uuid_to_str(link.source_entity_id),
            "target_node_id": uuid_to_str(link.target_entity_id),
            "predicate": link.predicate,
            "predicate_id": uuid_to_str(link.predicate_id),
        }

        created_link = link_service.create_link(link_data)

        # Invalidate graph cache
        invalidate_graph_cache()

        return _to_relationship_out(created_link)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {e!s}"
        )


@router.get("/relationships", response_model=PaginatedRelationshipsResponse)
def list_relationships(
    source_entity_id: UUID | None = Query(
        None, description="Filter by source entity ID"
    ),
    target_entity_id: UUID | None = Query(
        None, description="Filter by target entity ID"
    ),
    predicate: str | None = Query(None, description="Filter by predicate"),
    skip: int = Query(0, ge=0, description="Number of relationships to skip"),
    limit: int = Query(
        100, ge=1, le=500, description="Maximum number of relationships to return"
    ),
    link_service: NodeLinkService = Depends(get_node_link_service),
):
    """
    List entity relationships with filtering and pagination.

    Supports filtering by source entity, target entity, and predicate.
    Returns all relationships in the unified entity graph with pagination metadata.  # noqa: E501
    """
    try:
        # Convert UUID to string for filtering
        source_entity_id_str = (
            str(source_entity_id) if source_entity_id else None
        )
        target_entity_id_str = (
            str(target_entity_id) if target_entity_id else None
        )

        # Get total count
        total = link_service.count_links(
            source_node_id=source_entity_id_str,
            target_node_id=target_entity_id_str,
            predicate=predicate,
        )

        # Get relationships with pagination
        links = link_service.list_links(
            source_node_id=source_entity_id_str,
            target_node_id=target_entity_id_str,
            predicate=predicate,
            skip=skip,
            limit=limit,
        )

        # Convert to response format
        return PaginatedRelationshipsResponse(
            data=[_to_relationship_out(link) for link in links],
            total=total,
            skip=skip,
            limit=limit,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {e!s}"
        )


@router.put("/relationships/{rel_id}", response_model=RelationshipOut)
def update_relationship(
    rel_id: UUID = Path(
        ..., description="The ID of the relationship to update"
    ),
    link_update: RelationshipCreate = Body(...),
    link_service: NodeLinkService = Depends(get_node_link_service),
):
    """
    Update an entity relationship.

    Allows updating the predicate and predicate_id of an existing relationship.
    Source and target entities can also be updated if the new configuration is valid.  # noqa: E501
    """
    from api.graph import invalidate_graph_cache

    try:
        # Convert API model to service data
        update_data = {
            "source_node_id": uuid_to_str(link_update.source_entity_id),
            "target_node_id": uuid_to_str(link_update.target_entity_id),
            "predicate": link_update.predicate,
            "predicate_id": uuid_to_str(link_update.predicate_id),
        }

        updated_link = link_service.update_link(str(rel_id), update_data)

        # Invalidate graph cache
        invalidate_graph_cache()

        return _to_relationship_out(updated_link)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {e!s}"
        )


@router.delete("/relationships/{rel_id}", status_code=204)
def delete_relationship(
    rel_id: UUID = Path(
        ..., description="The ID of the relationship to delete"
    ),
    link_service: NodeLinkService = Depends(get_node_link_service),
):
    """
    Delete an entity relationship.

    Removes the relationship between two entities.
    """
    from api.graph import invalidate_graph_cache

    try:
        success = link_service.delete_link(str(rel_id))
        if success:
            invalidate_graph_cache()
            return
        else:
            raise HTTPException(
                status_code=404, detail="Entity relationship not found"
            )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {e!s}"
        )


@router.get("/{entity_id}", response_model=EntityOut)
def get_entity(
    entity_id: UUID = Path(
        ..., description="The ID of the entity to retrieve"
    ),
    node_service: NodeService = Depends(get_node_service_simple),
):
    """
    Get a specific ontology entity by ID.

    Returns the complete entity information including embeddings,
    hierarchy information, and metadata.
    """
    try:
        entity = node_service.get_node(str(entity_id))
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")

        return _to_entity_out(entity)

    except ValueError as e:
        error_msg = str(e).lower()
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {e!s}"
        )


@router.put("/{entity_id}", response_model=EntityOut)
def update_entity(
    entity_id: UUID = Path(..., description="The ID of the entity to update"),
    entity_update: EntityUpdate = Body(...),
    node_service: NodeService = Depends(get_node_service),
):
    """
    Update an ontology entity.

    Supports updating title, definition, parent relationships, and structural predicates.  # noqa: E501
    Circular reference validation is automatically enforced.
    """
    from api.graph import invalidate_graph_cache

    try:
        # Convert API model to service data, excluding unset values
        update_data = {}
        if entity_update.title is not None:
            update_data["title"] = entity_update.title
        if entity_update.definition is not None:
            update_data["definition"] = entity_update.definition
        if entity_update.parent_entity_id is not None:
            update_data["parent_node_id"] = uuid_to_str(entity_update.parent_entity_id)  # type: ignore[assignment]
        if entity_update.structural_predicate_id is not None:
            update_data["structural_predicate_id"] = uuid_to_str(entity_update.structural_predicate_id)  # type: ignore[assignment]

        updated_node = node_service.update_node(str(entity_id), update_data)

        # Invalidate graph cache
        invalidate_graph_cache()

        return _to_entity_out(updated_node)

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        error_msg = str(e).lower()
        if "unique" in error_msg:
            return conflict_error_response(str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {e!s}"
        )


@router.delete("/{entity_id}", status_code=204)
def delete_entity(
    entity_id: UUID = Path(..., description="The ID of the entity to delete"),
    node_service: NodeService = Depends(get_node_service),
):
    """
    Delete an ontology entity and its children.

    This operation cascades to all child entities and their relationships.
    Use with caution as this operation cannot be undone.
    """
    from api.graph import invalidate_graph_cache

    try:
        success = node_service.delete_node(str(entity_id))
        if success:
            invalidate_graph_cache()
            return
        else:
            raise HTTPException(status_code=404, detail="Entity not found")

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        error_message = str(e)
        if (
            "unique" in error_message.lower()
            or "already exists" in error_message.lower()
        ):
            return conflict_error_response(error_message)
        else:
            raise HTTPException(status_code=400, detail=error_message)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {e!s}"
        )
