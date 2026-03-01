"""
StructureNodes API Endpoints

This module implements the unified structure_nodes API endpoints that replace the
separate layers, domains, and terms endpoints as part of the Great Normalization.

Endpoints:
- POST /api/structure_nodes/ - Create a new structure_node
- GET /api/structure_nodes/{node_id} - Get a specific structure_node
- GET /api/structure_nodes/ - List structure_nodes with filtering and pagination
- PUT /api/structure_nodes/{node_id} - Update a structure_node
- DELETE /api/structure_nodes/{node_id} - Delete a structure_node and its children
- POST /api/structure_nodes/find - Vector search across structure_nodes
- POST /api/structure_nodes/links - Create a structure_node link
- GET /api/structure_nodes/links - List structure_node links
- PUT /api/structure_nodes/links/{link_id} - Update a structure_node link
- DELETE /api/structure_nodes/links/{link_id} - Delete a structure_node link
- POST /api/structure_nodes/{node_id}/reference_links - Add reference links to a structure_node
- DELETE /api/structure_nodes/{node_id}/reference_links - Remove reference links from a structure_node
- GET /api/structure_nodes/{node_id}/reference_links - Get reference links for a structure_node
- GET /api/structure_nodes/{node_id}/word_senses - Get word senses for a structure_node
"""

from fastapi import APIRouter, HTTPException, Query, Depends, Path
from typing import List, Optional
from uuid import UUID

from services.node_service import NodeService
from services.node_link_service import NodeLinkService
from services.reference_link_service import ReferenceLinkService
from services.word_sense_service import WordSenseService
from services.exceptions import NotFoundError, ValidationError, ConflictError, ReferenceNotFoundError
from api.models.structure_nodes import (
    NodeCreate, NodeUpdate, NodeOut, NodeLinkCreate, NodeLinkOut,
    NodeSearchRequest, NodeSearchResult, PaginatedNodesResponse, PaginatedNodeLinksResponse, NodeTypeEnum,
    MoveNodesRequest, MoveNodesResponse, ReferenceLink, WordSense, SelectedWordSensesUpdate,
    ResolvedAttribute, SetNodeAttributesRequest
)
from api.utils.node_conversion import (
    to_node_out, to_node_link_out, nodes_to_paginated_response,
    convert_api_node_type_to_db, uuid_to_str
)
from api.dependencies.structure_nodes import (
    get_node_service, get_node_service_simple, get_node_link_service,
    get_reference_link_service, get_word_sense_service
)
from api.api_errors import conflict_error_response

router = APIRouter(prefix="/api/structure_nodes", tags=["structure_nodes"])


@router.post("/", response_model=NodeOut, status_code=201)
def create_node(
    structure_node: NodeCreate,
    node_service: NodeService = Depends(get_node_service)
):
    """
    Create a new structure_node.

    This endpoint handles creation of layers, domains, and terms through
    the unified structure_nodes interface. Type-specific validation is enforced:
    - Layers cannot have parent structure_nodes
    - Domains must have a layer parent
    - Terms must have a domain parent
    """
    from utils.logger import get_logger
    from api.graph import invalidate_graph_cache
    logger = get_logger(__name__)

    try:
        # Convert API model to service data
        node_data = {
            "node_type": structure_node.node_type.value,
            "parent_node_id": uuid_to_str(structure_node.parent_node_id),
            "title": structure_node.title,
            "definition": structure_node.definition,
            "structural_predicate_id": uuid_to_str(structure_node.structural_predicate_id)
        }

        created_node = node_service.create_node(node_data)

        # Invalidate graph cache so hierarchy updates are immediately visible
        invalidate_graph_cache()

        return to_node_out(created_node)

    except ValidationError as e:
        # Handle all validation errors (including InvalidHierarchyError) with 400
        raise HTTPException(status_code=400, detail=str(e))
    except ConflictError as e:
        # Handle conflict errors with 409
        return conflict_error_response(str(e))
    except ValueError as e:
        error_msg = str(e)
        # Check if this is a uniqueness constraint violation
        if "unique" in error_msg.lower():
            return conflict_error_response(error_msg)
        else:
            raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        logger.error(f"Unexpected error creating structure_node: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/", response_model=PaginatedNodesResponse)
def list_nodes(
    node_type: Optional[NodeTypeEnum] = Query(None, description="Filter by structure_node type"),
    parent_node_id: Optional[UUID] = Query(None, description="Filter by parent structure_node ID"),
    skip: int = Query(0, ge=0, description="Number of structure_nodes to skip"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of structure_nodes to return"),
    sort_by: str = Query("title", pattern="^(title|created_at)$", description="Sort field"),
    node_service: NodeService = Depends(get_node_service_simple)
):
    """
    List structure_nodes with filtering and pagination.
    
    Supports filtering by structure_node type and parent, with configurable pagination
    and sorting. This replaces the separate endpoints for layers, domains, and terms.
    """
    try:
        import time
        from utils.logger import get_logger

        logger = get_logger(__name__)
        request_start = time.time()

        # Convert API node type to database node type
        db_node_type = None
        if node_type:
            db_node_type = convert_api_node_type_to_db(node_type.value)

        # Convert UUID to string for parent_node_id
        parent_node_id_str = str(parent_node_id) if parent_node_id else None

        setup_time = time.time() - request_start
        logger.debug(f"API setup time: {setup_time*1000:.2f}ms")

        # Get total count using NodeService
        count_start = time.time()
        total = node_service.count_nodes(
            node_type=db_node_type,
            parent_node_id=parent_node_id_str
        )
        count_time = time.time() - count_start
        logger.debug(f"Count query time: {count_time*1000:.2f}ms")

        # Get nodes using NodeService with pagination
        list_start = time.time()
        structure_nodes = node_service.list_nodes(
            node_type=db_node_type,
            parent_node_id=parent_node_id_str,
            skip=skip,
            limit=limit
        )
        list_time = time.time() - list_start
        logger.debug(f"List query time: {list_time*1000:.2f}ms")

        # Convert to response format
        serialization_start = time.time()
        response_data = nodes_to_paginated_response(structure_nodes, total, skip, limit)
        serialization_time = time.time() - serialization_start
        logger.debug(f"Response serialization time: {serialization_time*1000:.2f}ms")

        pydantic_start = time.time()
        result = PaginatedNodesResponse(**response_data)
        pydantic_time = time.time() - pydantic_start
        logger.debug(f"Pydantic model time: {pydantic_time*1000:.2f}ms")

        total_time = time.time() - request_start
        logger.debug(f"Total API endpoint time: {total_time*1000:.2f}ms (skip={skip})")

        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/find", response_model=List[NodeSearchResult])
def search_nodes(
    search_request: NodeSearchRequest,
    node_service: NodeService = Depends(get_node_service)
):
    """
    Vector search across structure_nodes.

    This endpoint replaces the separate find endpoints for layers, domains, and terms.
    Supports semantic search across structure_node titles and definitions with optional
    type filtering and configurable similarity thresholds.
    """
    from utils.logger import get_logger
    from sqlalchemy import text
    from embeddings.generate_embeddings import generate_embedding
    from api.utils.node_conversion import convert_api_node_type_to_db

    logger = get_logger(__name__)

    try:
        # Generate embedding for query
        query_embedding = generate_embedding(search_request.query)

        # Build query with optional node_type filter
        type_filter = ""
        params = {
            'query_vec': query_embedding,
            'threshold': search_request.threshold,
            'limit': search_request.limit
        }

        if search_request.node_type:
            db_node_type = convert_api_node_type_to_db(search_request.node_type.value)
            type_filter = "AND node_type = :node_type"
            params['node_type'] = db_node_type

        query = text(f"""
            WITH similarities AS (
                SELECT
                    id,
                    title,
                    node_type,
                    definition,
                    parent_node_id,
                    structural_predicate_id,
                    created_at,
                    last_modified,
                    title_embedding,
                    definition_embedding,
                    CASE
                        WHEN title_embedding IS NOT NULL AND definition_embedding IS NOT NULL THEN
                            MAX(
                                (1.0 - vec_distance_cosine(title_embedding, :query_vec)),
                                (1.0 - vec_distance_cosine(definition_embedding, :query_vec))
                            )
                        WHEN title_embedding IS NOT NULL THEN
                            (1.0 - vec_distance_cosine(title_embedding, :query_vec))
                        WHEN definition_embedding IS NOT NULL THEN
                            (1.0 - vec_distance_cosine(definition_embedding, :query_vec))
                        ELSE 0.0
                    END as similarity
                FROM structure_nodes
                WHERE (title_embedding IS NOT NULL OR definition_embedding IS NOT NULL)
                {type_filter}
            )
            SELECT
                id,
                title,
                node_type,
                definition,
                parent_node_id,
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

        # Convert results to NodeSearchResult objects
        search_results = []
        for row in results:
            result = NodeSearchResult(
                id=row.id,
                node_type=row.node_type,
                parent_node_id=row.parent_node_id,
                title=row.title,
                definition=row.definition,
                structural_predicate_id=row.structural_predicate_id,
                created_at=row.created_at.isoformat() if hasattr(row.created_at, 'isoformat') else str(row.created_at),
                version=1,  # Use version 1 as placeholder for search results
                last_modified=row.last_modified.isoformat() if hasattr(row.last_modified, 'isoformat') else str(row.last_modified),
                score=float(row.similarity),
                distance=1.0 - float(row.similarity)  # distance is inverse of similarity
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
        raise HTTPException(status_code=500, detail=f"Vector search failed: {str(e)}")


# StructureNode Links endpoints
@router.post("/links", response_model=NodeLinkOut, status_code=201)
def create_node_link(
    link: NodeLinkCreate,
    link_service: NodeLinkService = Depends(get_node_link_service)
):
    """
    Create a new structure_node link.

    Links can only be created between structure_nodes of the same type (layers to layers,
    domains to domains, terms to terms) as per the Great Normalization requirements.
    """
    from api.graph import invalidate_graph_cache

    try:
        # Convert API model to service data
        link_data = {
            "source_node_id": uuid_to_str(link.source_node_id),
            "target_node_id": uuid_to_str(link.target_node_id),
            "predicate": link.predicate,
            "predicate_id": uuid_to_str(link.predicate_id)
        }

        created_link = link_service.create_link(link_data)

        # Invalidate graph cache so new links are immediately visible
        invalidate_graph_cache()

        return to_node_link_out(created_link)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/links", response_model=PaginatedNodeLinksResponse)
def list_node_links(
    source_node_id: Optional[UUID] = Query(None, description="Filter by source structure_node ID"),
    target_node_id: Optional[UUID] = Query(None, description="Filter by target structure_node ID"),
    predicate: Optional[str] = Query(None, description="Filter by predicate"),
    skip: int = Query(0, ge=0, description="Number of links to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of links to return"),
    link_service: NodeLinkService = Depends(get_node_link_service)
):
    """
    List structure_node links with filtering and pagination.

    Supports filtering by source structure_node, target structure_node, and predicate.
    Returns all relationships in the unified structure_node graph with pagination metadata.
    """
    try:
        # Convert UUID to string for filtering
        source_node_id_str = str(source_node_id) if source_node_id else None
        target_node_id_str = str(target_node_id) if target_node_id else None

        # Get total count
        total = link_service.count_links(
            source_node_id=source_node_id_str,
            target_node_id=target_node_id_str,
            predicate=predicate
        )

        # Get links with pagination
        links = link_service.list_links(
            source_node_id=source_node_id_str,
            target_node_id=target_node_id_str,
            predicate=predicate,
            skip=skip,
            limit=limit
        )

        # Convert to response format
        return PaginatedNodeLinksResponse(
            data=[to_node_link_out(link) for link in links],
            total=total,
            skip=skip,
            limit=limit
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.put("/links/{link_id}", response_model=NodeLinkOut)
def update_node_link(
    link_id: UUID = Path(..., description="The ID of the link to update"),
    link_update: NodeLinkCreate = ...,  # Reuse create model for updates
    link_service: NodeLinkService = Depends(get_node_link_service)
):
    """
    Update a structure_node link.

    Allows updating the predicate and predicate_id of an existing link.
    Source and target structure_nodes can also be updated if the new configuration is valid.
    """
    from api.graph import invalidate_graph_cache

    try:
        # Convert API model to service data
        update_data = {
            "source_node_id": uuid_to_str(link_update.source_node_id),
            "target_node_id": uuid_to_str(link_update.target_node_id),
            "predicate": link_update.predicate,
            "predicate_id": uuid_to_str(link_update.predicate_id)
        }

        updated_link = link_service.update_link(str(link_id), update_data)

        # Invalidate graph cache so link updates are immediately visible
        invalidate_graph_cache()

        return to_node_link_out(updated_link)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/links/{link_id}", status_code=204)
def delete_node_link(
    link_id: UUID = Path(..., description="The ID of the link to delete"),
    link_service: NodeLinkService = Depends(get_node_link_service)
):
    """
    Delete a structure_node link.

    Removes the relationship between two structure_nodes. This operation cannot be undone.
    """
    from api.graph import invalidate_graph_cache

    try:
        success = link_service.delete_link(str(link_id))
        if success:
            # Invalidate graph cache so link deletions are immediately visible
            invalidate_graph_cache()
            return  # Return empty response with 204 status
        else:
            raise HTTPException(status_code=404, detail="StructureNode link not found")
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{node_id}", response_model=NodeOut)
def get_node(
    node_id: UUID = Path(..., description="The ID of the structure_node to retrieve"),
    node_service: NodeService = Depends(get_node_service_simple)
):
    """
    Get a specific structure_node by ID.
    
    Returns the complete structure_node information including embeddings,
    hierarchy information, and metadata.
    """
    try:
        structure_node = node_service.get_node(str(node_id))
        if not structure_node:
            raise HTTPException(status_code=404, detail="StructureNode not found")
        
        return to_node_out(structure_node)
        
    except ValueError as e:
        error_msg = str(e).lower()
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        # Re-raise HTTPException without catching it
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.put("/{node_id}", response_model=NodeOut)
def update_node(
    node_id: UUID = Path(..., description="The ID of the structure_node to update"),
    node_update: NodeUpdate = ...,
    node_service: NodeService = Depends(get_node_service)
):
    """
    Update a structure_node.

    Supports updating title, definition, parent relationships, and structural predicates.
    Circular reference validation is automatically enforced.
    """
    from api.graph import invalidate_graph_cache

    try:
        # Convert API model to service data, excluding unset values
        update_data = {}
        if node_update.title is not None:
            update_data["title"] = node_update.title
        if node_update.definition is not None:
            update_data["definition"] = node_update.definition
        if node_update.parent_node_id is not None:
            update_data["parent_node_id"] = uuid_to_str(node_update.parent_node_id)
        if node_update.structural_predicate_id is not None:
            update_data["structural_predicate_id"] = uuid_to_str(node_update.structural_predicate_id)

        updated_node = node_service.update_node(str(node_id), update_data)

        # Invalidate graph cache so hierarchy updates are immediately visible
        invalidate_graph_cache()

        return to_node_out(updated_node)

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        # Handle all validation errors (including CircularReferenceError and InvalidHierarchyError) with 400
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        error_msg = str(e).lower()
        # Check if this is a uniqueness constraint violation
        if "unique" in error_msg:
            return conflict_error_response(str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        # Re-raise HTTPException without catching it
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/{node_id}", status_code=204)
def delete_node(
    node_id: UUID = Path(..., description="The ID of the structure_node to delete"),
    node_service: NodeService = Depends(get_node_service)
):
    """
    Delete a structure_node and its children.

    This operation cascades to all child structure_nodes and their relationships.
    Use with caution as this operation cannot be undone.
    """
    from api.graph import invalidate_graph_cache

    try:
        success = node_service.delete_node(str(node_id))
        if success:
            # Invalidate graph cache so hierarchy updates are immediately visible
            invalidate_graph_cache()
            return  # Return empty response with 204 status
        else:
            raise HTTPException(status_code=404, detail="StructureNode not found")

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        error_message = str(e)
        if "unique" in error_message.lower() or "already exists" in error_message.lower():
            return conflict_error_response(error_message)
        else:
            raise HTTPException(status_code=400, detail=error_message)
    except HTTPException:
        # Re-raise HTTPException without catching it
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# Attribute endpoints
@router.get("/{node_id}/attributes", response_model=List[ResolvedAttribute])
def get_node_attributes(
    node_id: UUID = Path(..., description="The ID of the structure node"),
    node_service: NodeService = Depends(get_node_service)
):
    """
    Get resolved attributes for a node (local + inherited).

    Returns all attributes for this node, including those inherited from ancestors.
    Each resolved attribute includes an `inherited` flag and `source_node_id` indicating
    where the attribute was defined in the hierarchy.

    Args:
        node_id: UUID of the structure node

    Returns:
        List of resolved attributes with inheritance information

    Raises:
        404: If structure node not found
        500: If an unexpected error occurs
    """
    from utils.logger import get_logger
    logger = get_logger(__name__)

    try:
        return node_service.resolve_node_attributes(node_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error resolving attributes for node {node_id}: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve attributes. Please try again.")


@router.post("/{node_id}/attributes", response_model=NodeOut)
def set_node_attributes(
    node_id: UUID = Path(..., description="The ID of the structure node"),
    request: SetNodeAttributesRequest = ...,
    node_service: NodeService = Depends(get_node_service)
):
    """
    Set local attributes on a node (replaces existing attributes).

    Replaces all local attributes on this node with the provided list.
    Inherited attributes from ancestors are not affected. This operation
    increments the node's version number.

    Supports optimistic locking via the expected_version field. If provided,
    the update will only succeed if the current node version matches. This prevents
    lost updates in concurrent modification scenarios.

    Args:
        node_id: UUID of the structure node
        request: SetNodeAttributesRequest containing:
            - attributes: List of StructureNodeAttribute instances to set
            - expected_version: Optional version for optimistic locking

    Returns:
        Updated structure node

    Raises:
        400: If validation fails on attribute values or types
        404: If structure node not found
        409: If expected_version is provided and doesn't match current version (conflict)
        500: If an unexpected error occurs
    """
    from utils.logger import get_logger
    logger = get_logger(__name__)

    try:
        node = node_service.set_node_attributes(
            node_id,
            request.attributes,
            expected_version=request.expected_version
        )
        return to_node_out(node)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ConflictError as e:
        return conflict_error_response(str(e))
    except Exception as e:
        logger.error(f"Unexpected error setting attributes for node {node_id}: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to set attributes. Please try again.")


@router.delete("/{node_id}/attributes/{key}", response_model=NodeOut)
def remove_node_attribute(
    node_id: UUID = Path(..., description="The ID of the structure node"),
    key: str = Path(..., description="The attribute key to remove"),
    node_service: NodeService = Depends(get_node_service)
):
    """
    Remove a specific attribute by key.

    Removes a single attribute from the node's local attributes by its key.
    Has no effect if the key doesn't exist. Inherited attributes are not affected.
    This operation increments the node's version number.

    Args:
        node_id: UUID of the structure node
        key: Attribute key to remove

    Returns:
        Updated structure node

    Raises:
        404: If structure node not found
        500: If an unexpected error occurs
    """
    from utils.logger import get_logger
    logger = get_logger(__name__)

    try:
        node = node_service.remove_node_attribute(node_id, key)
        return to_node_out(node)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error removing attribute {key} from node {node_id}: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to remove attribute. Please try again.")


# Reference Links endpoints
@router.post("/{node_id}/reference_links", response_model=List[ReferenceLink], status_code=200)
def add_reference_links(
    node_id: UUID = Path(..., description="The ID of the structure node"),
    links: List[ReferenceLink] = ...,
    reference_link_service: ReferenceLinkService = Depends(get_reference_link_service)
):
    """
    Add reference links to a structure node.

    Links the structure node to external knowledge sources such as schema.org,
    Wikidata, or ConceptNet. Each link is validated against the reference database
    before being added. Duplicate links are ignored.

    Args:
        node_id: UUID of the structure node
        links: List of reference links to add (source + external_id pairs)

    Returns:
        List of all reference links after addition (including pre-existing ones)

    Raises:
        400: If validation fails or reference doesn't exist in reference.db
        404: If structure node not found
        500: If an unexpected error occurs
    """
    from utils.logger import get_logger
    logger = get_logger(__name__)

    try:
        result = reference_link_service.add_reference_links(str(node_id), links)
        return result

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ReferenceNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error adding reference links to node {node_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/{node_id}/reference_links", response_model=List[ReferenceLink], status_code=200)
def remove_reference_links(
    node_id: UUID = Path(..., description="The ID of the structure node"),
    links: List[ReferenceLink] = ...,
    reference_link_service: ReferenceLinkService = Depends(get_reference_link_service)
):
    """
    Remove reference links from a structure node.

    Removes specified reference links from the structure node. Links that don't
    exist are silently ignored.

    Args:
        node_id: UUID of the structure node
        links: List of reference links to remove (source + external_id pairs)

    Returns:
        List of remaining reference links after removal

    Raises:
        404: If structure node not found
        500: If an unexpected error occurs
    """
    from utils.logger import get_logger
    logger = get_logger(__name__)

    try:
        result = reference_link_service.remove_reference_links(str(node_id), links)
        return result

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error removing reference links from node {node_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{node_id}/reference_links", response_model=List[ReferenceLink])
def get_reference_links(
    node_id: UUID = Path(..., description="The ID of the structure node"),
    reference_link_service: ReferenceLinkService = Depends(get_reference_link_service)
):
    """
    Get all reference links for a structure node.

    Returns all external knowledge source links associated with this structure node.
    Returns an empty list if no links exist.

    Args:
        node_id: UUID of the structure node

    Returns:
        List of reference links (may be empty)

    Raises:
        404: If structure node not found
        500: If an unexpected error occurs
    """
    from utils.logger import get_logger
    logger = get_logger(__name__)

    try:
        result = reference_link_service.get_reference_links(str(node_id))
        return result

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting reference links for node {node_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{node_id}/word_senses", response_model=List[WordSense])
def get_word_senses(
    node_id: UUID = Path(..., description="The ID of the structure node"),
    word_sense_service: WordSenseService = Depends(get_word_sense_service)
):
    """
    Get all word senses for a structure node.

    Returns word sense identifiers from NLP analysis (e.g., WordNet synsets) that
    have been associated with this structure node through title analysis.
    Returns an empty list if no word senses exist.

    Word senses are automatically updated when the structure node's title changes,
    via the event processor system.

    Args:
        node_id: UUID of the structure node

    Returns:
        List of word senses (may be empty)

    Raises:
        404: If structure node not found
        500: If an unexpected error occurs
    """
    from utils.logger import get_logger
    logger = get_logger(__name__)

    try:
        result = word_sense_service.get_word_senses(str(node_id))
        return result

    except ValueError as e:
        error_msg = str(e).lower()
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting word senses for node {node_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.put("/{node_id}/word_senses", response_model=List[WordSense])
def update_word_senses(
    node_id: UUID = Path(..., description="The ID of the structure node"),
    update_request: SelectedWordSensesUpdate = ...,
    word_sense_service: WordSenseService = Depends(get_word_sense_service)
):
    """
    Update selected word senses for a structure node.

    Allows user to persist their selected word senses from NLP analysis.
    Uses a conservative merge strategy: preserves existing word senses for words
    not included in this update, while replacing senses for words that are included.

    For example, if a node has existing senses for words "bank" and "account", and
    you update only "bank", the existing "account" senses will be preserved.

    Args:
        node_id: UUID of the structure node
        update_request: Selected word senses to persist

    Returns:
        List of all word senses after update (including preserved senses)

    Raises:
        400: If validation fails (invalid sense_id format)
        404: If structure node not found
        500: If an unexpected error occurs
    """
    from utils.logger import get_logger
    logger = get_logger(__name__)

    try:
        result = word_sense_service.update_selected_senses(
            str(node_id),
            update_request.selected_senses
        )
        return result

    except ValueError as e:
        error_msg = str(e).lower()
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error updating word senses for node {node_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# Reference Link Validation endpoints
@router.post("/reference_links/validate", response_model=dict)
def validate_all_reference_links(
    check_existence: bool = Query(True, description="Check if references exist in reference.db"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Limit number of nodes to validate"),
    batch_size: int = Query(100, ge=10, le=1000, description="Number of nodes to process per batch"),
    reference_link_service: ReferenceLinkService = Depends(get_reference_link_service)
):
    """
    Validate all reference links across all structure nodes.

    Performs bulk validation of reference links to identify:
    - Orphaned links (references that no longer exist in reference.db)
    - Malformed links (invalid JSON or missing required fields)
    - Nodes with problematic links

    Uses batching to efficiently handle large datasets without loading all nodes into memory.
    This endpoint is useful for maintenance and data integrity checking.
    Gracefully degrades if reference.db is unavailable.

    Args:
        check_existence: If True, validates each link exists in reference.db
        limit: Optional limit on number of nodes to check
        batch_size: Number of nodes to process per batch (default: 100, min: 10, max: 1000)

    Returns:
        Validation results with statistics and list of problematic nodes
    """
    from utils.logger import get_logger
    logger = get_logger(__name__)

    try:
        logger.info(f"Starting bulk reference link validation (check_existence={check_existence}, limit={limit}, batch_size={batch_size})")
        result = reference_link_service.validate_all_reference_links(
            check_existence=check_existence,
            limit=limit,
            batch_size=batch_size
        )

        return result

    except Exception as e:
        logger.error(f"Error during bulk validation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Validation error: {str(e)}")


@router.post("/{node_id}/reference_links/validate", response_model=dict)
def validate_node_reference_links(
    node_id: UUID = Path(..., description="The ID of the structure node"),
    check_existence: bool = Query(True, description="Check if references exist in reference.db"),
    reference_link_service: ReferenceLinkService = Depends(get_reference_link_service)
):
    """
    Validate reference links for a specific structure node.

    Checks all reference links on a single node to identify:
    - Orphaned links (references that no longer exist in reference.db)
    - Malformed links (invalid JSON or missing required fields)
    - Valid links

    Args:
        node_id: UUID of the structure node
        check_existence: If True, validates each link exists in reference.db

    Returns:
        Validation results with counts of valid, invalid, and malformed links

    Raises:
        404: If structure node not found
        500: If an unexpected error occurs
    """
    from utils.logger import get_logger
    logger = get_logger(__name__)

    try:
        result = reference_link_service.validate_node_reference_links(
            str(node_id),
            check_existence=check_existence
        )
        return result

    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating reference links for node {node_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Validation error: {str(e)}")


# Additional utility endpoints
@router.post("/move", response_model=MoveNodesResponse)
def move_nodes(
    move_request: MoveNodesRequest,
    node_service: NodeService = Depends(get_node_service)
):
    """
    Move structure_nodes to a new parent location with automatic type conversion.

    **Type Conversion Rules:**
    - Moving to root (null parent) → becomes Layer
    - Moving under Layer → becomes Domain
    - Moving under Domain or Term → becomes Term

    **Recursive Conversion:**
    When a node's type changes, all descendants are recursively converted:
    - Layer's children become Domains
    - Domain's/Term's children become Terms

    This endpoint supports:
    - Moving multiple structure_nodes at once
    - Automatic type conversion based on target parent
    - Moving all child structure_nodes along with parents
    - Handling title conflicts through warnings, renaming, or errors
    - Maintaining referential integrity throughout the operation

    The move operation is atomic - either all structure_nodes are moved successfully,
    or the entire operation is rolled back.
    """
    try:
        # Convert UUID objects to strings for service
        node_ids = [str(node_id) for node_id in move_request.node_ids]
        target_parent_id = str(move_request.target_parent_id) if move_request.target_parent_id else None

        result = node_service.move_nodes(
            node_ids=node_ids,
            target_parent_id=target_parent_id,
            move_children=move_request.move_children,
            handle_conflicts=move_request.handle_conflicts
        )

        return MoveNodesResponse(
            moved_nodes=[to_node_out(node) for node in result['moved_nodes']],
            updated_children=[to_node_out(child) for child in result['updated_children']],
            converted_nodes=[to_node_out(node) for node in result.get('converted_nodes', [])],
            warnings=result['warnings'],
            errors=result['errors']
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{node_id}/children", response_model=List[NodeOut])
def get_node_children(
    node_id: UUID = Path(..., description="The ID of the parent structure_node"),
    node_service: NodeService = Depends(get_node_service_simple)
):
    """
    Get all direct children of a structure_node.
    
    Useful for building hierarchical views of the structure_node structure.
    """
    try:
        children = node_service.get_node_children(str(node_id))
        return [to_node_out(child) for child in children]
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{node_id}/ancestors", response_model=List[NodeOut])
def get_node_ancestors(
    node_id: UUID = Path(..., description="The ID of the structure_node"),
    node_service: NodeService = Depends(get_node_service_simple)
):
    """
    Get all ancestors of a structure_node up to the root.
    
    Returns the path from the root layer down to the specified structure_node's parent.
    Useful for breadcrumb navigation and understanding structure_node context.
    """
    try:
        ancestors = node_service.get_node_ancestors(str(node_id))
        return [to_node_out(ancestor) for ancestor in ancestors]
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
