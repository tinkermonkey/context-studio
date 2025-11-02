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
"""

from fastapi import APIRouter, HTTPException, Query, Depends, Path
from typing import List, Optional
from uuid import UUID

from services.node_service import NodeService
from services.node_link_service import NodeLinkService
from api.models.structure_nodes import (
    NodeCreate, NodeUpdate, NodeOut, NodeLinkCreate, NodeLinkOut,
    NodeSearchRequest, NodeSearchResult, PaginatedNodesResponse, NodeTypeEnum,
    MoveNodesRequest, MoveNodesResponse
)
from api.utils.node_conversion import (
    to_node_out, to_node_link_out, nodes_to_paginated_response,
    convert_api_node_type_to_db, uuid_to_str
)
from api.dependencies.structure_nodes import get_node_service, get_node_service_simple, get_node_link_service
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
                version=1,  # Version tracking would come from working tree
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


@router.get("/links", response_model=List[NodeLinkOut])
def list_node_links(
    source_node_id: Optional[UUID] = Query(None, description="Filter by source structure_node ID"),
    target_node_id: Optional[UUID] = Query(None, description="Filter by target structure_node ID"),
    predicate: Optional[str] = Query(None, description="Filter by predicate"),
    skip: int = Query(0, ge=0, description="Number of links to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of links to return"),
    link_service: NodeLinkService = Depends(get_node_link_service)
):
    """
    List structure_node links with filtering.
    
    Supports filtering by source structure_node, target structure_node, and predicate.
    Returns all relationships in the unified structure_node graph.
    """
    try:
        # Convert UUID to string for filtering
        source_node_id_str = str(source_node_id) if source_node_id else None
        target_node_id_str = str(target_node_id) if target_node_id else None
        
        links = link_service.list_links(
            source_node_id=source_node_id_str,
            target_node_id=target_node_id_str,
            predicate=predicate,
            skip=skip,
            limit=limit
        )
        
        return [to_node_link_out(link) for link in links]
        
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

    except ValueError as e:
        error_msg = str(e).lower()
        # Check for not found errors first
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail=str(e))
        # Check if this is a uniqueness constraint violation
        elif "unique" in error_msg:
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
            
    except ValueError as e:
        error_message = str(e)
        if "not found" in error_message.lower():
            raise HTTPException(status_code=404, detail=error_message)
        elif "unique" in error_message.lower() or "already exists" in error_message.lower():
            return conflict_error_response(error_message)
        else:
            raise HTTPException(status_code=400, detail=error_message)
    except HTTPException:
        # Re-raise HTTPException without catching it
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# Additional utility endpoints
@router.post("/move", response_model=MoveNodesResponse)
def move_nodes(
    move_request: MoveNodesRequest,
    node_service: NodeService = Depends(get_node_service)
):
    """
    Move structure_nodes to a new parent location.
    
    This endpoint supports moving multiple structure_nodes at once, with options for:
    - Moving all child structure_nodes along with parents
    - Handling title conflicts through warnings, renaming, or errors
    - Maintaining referential integrity throughout the move operation
    
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
