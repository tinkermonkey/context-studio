"""
Nodes API Endpoints

This module implements the unified nodes API endpoints that replace the
separate layers, domains, and terms endpoints as part of the Great Normalization.

Endpoints:
- POST /api/nodes/ - Create a new node
- GET /api/nodes/{node_id} - Get a specific node
- GET /api/nodes/ - List nodes with filtering and pagination
- PUT /api/nodes/{node_id} - Update a node
- DELETE /api/nodes/{node_id} - Delete a node and its children
- POST /api/nodes/find - Vector search across nodes
- POST /api/nodes/links - Create a node link
- GET /api/nodes/links - List node links
- PUT /api/nodes/links/{link_id} - Update a node link
- DELETE /api/nodes/links/{link_id} - Delete a node link
"""

from fastapi import APIRouter, HTTPException, Query, Depends, Path
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from database.models import Node, NodeLink
from database.enums import NodeType
from database.utils import get_db
from services.node_service import NodeService
from services.node_link_service import NodeLinkService
from api.models.nodes import (
    NodeCreate, NodeUpdate, NodeOut, NodeLinkCreate, NodeLinkOut,
    NodeSearchRequest, NodeSearchResult, PaginatedNodesResponse, NodeTypeEnum
)
from api.utils.node_conversion import (
    to_node_out, to_node_link_out, nodes_to_paginated_response,
    convert_api_node_type_to_db, uuid_to_str
)
from api.dependencies.nodes import get_node_service, get_node_link_service

router = APIRouter(prefix="/api/nodes", tags=["nodes"])


@router.post("/", response_model=NodeOut, status_code=201)
def create_node(
    node: NodeCreate,
    node_service: NodeService = Depends(get_node_service)
):
    """
    Create a new node.
    
    This endpoint handles creation of layers, domains, and terms through
    the unified nodes interface. Type-specific validation is enforced:
    - Layers cannot have parent nodes
    - Domains must have a layer parent
    - Terms must have a domain parent
    """
    try:
        # Convert API model to service data
        node_data = {
            "node_type": node.node_type.value,
            "parent_node_id": uuid_to_str(node.parent_node_id),
            "title": node.title,
            "definition": node.definition,
            "structural_predicate_id": uuid_to_str(node.structural_predicate_id)
        }
        
        created_node = node_service.create_node(node_data)
        return to_node_out(created_node)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/", response_model=PaginatedNodesResponse)
def list_nodes(
    node_type: Optional[NodeTypeEnum] = Query(None, description="Filter by node type"),
    parent_node_id: Optional[UUID] = Query(None, description="Filter by parent node ID"),
    skip: int = Query(0, ge=0, description="Number of nodes to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of nodes to return"),
    sort_by: str = Query("title", pattern="^(title|created_at)$", description="Sort field"),
    db: Session = Depends(get_db)
):
    """
    List nodes with filtering and pagination.
    
    Supports filtering by node type and parent, with configurable pagination
    and sorting. This replaces the separate endpoints for layers, domains, and terms.
    """
    try:
        query = db.query(Node)
        
        # Apply filters
        if node_type:
            db_node_type = convert_api_node_type_to_db(node_type.value)
            query = query.filter(Node.node_type == db_node_type)
            
        if parent_node_id:
            query = query.filter(Node.parent_node_id == str(parent_node_id))
        
        # Get total count before pagination
        total = query.count()
        
        # Apply sorting
        if sort_by == "title":
            query = query.order_by(Node.title)
        elif sort_by == "created_at":
            query = query.order_by(Node.created_at.desc())
        
        # Apply pagination
        nodes = query.offset(skip).limit(limit).all()
        
        return PaginatedNodesResponse(**nodes_to_paginated_response(nodes, total, skip, limit))
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/find", response_model=List[NodeSearchResult])
def search_nodes(
    search_request: NodeSearchRequest,
    db: Session = Depends(get_db)
):
    """
    Vector search across nodes.
    
    This endpoint replaces the separate find endpoints for layers, domains, and terms.
    Supports semantic search across node titles and definitions with optional
    type filtering and configurable similarity thresholds.
    
    Note: Implementation depends on vector search infrastructure being available.
    """
    # TODO: Implement vector search functionality
    # This would integrate with the existing vector search infrastructure
    # and work with the nodes_vec virtual table
    
    # Placeholder implementation - would need to be completed based on
    # existing vector search patterns in the codebase
    raise HTTPException(
        status_code=501, 
        detail="Vector search implementation pending - requires integration with existing vector search infrastructure"
    )


# Node Links endpoints
@router.post("/links", response_model=NodeLinkOut, status_code=201)
def create_node_link(
    link: NodeLinkCreate,
    link_service: NodeLinkService = Depends(get_node_link_service)
):
    """
    Create a new node link.
    
    Links can only be created between nodes of the same type (layers to layers,
    domains to domains, terms to terms) as per the Great Normalization requirements.
    """
    try:
        # Convert API model to service data
        link_data = {
            "source_node_id": uuid_to_str(link.source_node_id),
            "target_node_id": uuid_to_str(link.target_node_id),
            "predicate": link.predicate,
            "predicate_id": uuid_to_str(link.predicate_id)
        }
        
        created_link = link_service.create_link(link_data)
        return to_node_link_out(created_link)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/links", response_model=List[NodeLinkOut])
def list_node_links(
    source_node_id: Optional[UUID] = Query(None, description="Filter by source node ID"),
    target_node_id: Optional[UUID] = Query(None, description="Filter by target node ID"),
    predicate: Optional[str] = Query(None, description="Filter by predicate"),
    skip: int = Query(0, ge=0, description="Number of links to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of links to return"),
    db: Session = Depends(get_db)
):
    """
    List node links with filtering.
    
    Supports filtering by source node, target node, and predicate.
    Returns all relationships in the unified node graph.
    """
    try:
        query = db.query(NodeLink)
        
        # Apply filters
        if source_node_id:
            query = query.filter(NodeLink.source_node_id == str(source_node_id))
        if target_node_id:
            query = query.filter(NodeLink.target_node_id == str(target_node_id))
        if predicate:
            query = query.filter(NodeLink.predicate == predicate)
        
        # Apply pagination
        links = query.offset(skip).limit(limit).all()
        
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
    Update a node link.
    
    Allows updating the predicate and predicate_id of an existing link.
    Source and target nodes can also be updated if the new configuration is valid.
    """
    try:
        # Convert API model to service data
        update_data = {
            "source_node_id": uuid_to_str(link_update.source_node_id),
            "target_node_id": uuid_to_str(link_update.target_node_id),
            "predicate": link_update.predicate,
            "predicate_id": uuid_to_str(link_update.predicate_id)
        }
        
        updated_link = link_service.update_link(str(link_id), update_data)
        return to_node_link_out(updated_link)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/links/{link_id}")
def delete_node_link(
    link_id: UUID = Path(..., description="The ID of the link to delete"),
    link_service: NodeLinkService = Depends(get_node_link_service)
):
    """
    Delete a node link.
    
    Removes the relationship between two nodes. This operation cannot be undone.
    """
    try:
        success = link_service.delete_link(str(link_id))
        if success:
            return {"success": True, "message": "Node link deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Node link not found")
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{node_id}", response_model=NodeOut)
def get_node(
    node_id: UUID = Path(..., description="The ID of the node to retrieve"),
    db: Session = Depends(get_db)
):
    """
    Get a specific node by ID.
    
    Returns the complete node information including embeddings,
    hierarchy information, and metadata.
    """
    node = db.query(Node).filter(Node.id == str(node_id)).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    return to_node_out(node)


@router.put("/{node_id}", response_model=NodeOut)
def update_node(
    node_id: UUID = Path(..., description="The ID of the node to update"),
    node_update: NodeUpdate = ...,
    node_service: NodeService = Depends(get_node_service)
):
    """
    Update a node.
    
    Supports updating title, definition, parent relationships, and structural predicates.
    Circular reference validation is automatically enforced.
    """
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
        return to_node_out(updated_node)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/{node_id}")
def delete_node(
    node_id: UUID = Path(..., description="The ID of the node to delete"),
    node_service: NodeService = Depends(get_node_service)
):
    """
    Delete a node and its children.
    
    This operation cascades to all child nodes and their relationships.
    Use with caution as this operation cannot be undone.
    """
    try:
        success = node_service.delete_node(str(node_id))
        if success:
            return {"success": True, "message": "Node and children deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Node not found")
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# Additional utility endpoints
@router.get("/{node_id}/children", response_model=List[NodeOut])
def get_node_children(
    node_id: UUID = Path(..., description="The ID of the parent node"),
    node_service: NodeService = Depends(get_node_service)
):
    """
    Get all direct children of a node.
    
    Useful for building hierarchical views of the node structure.
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
    node_id: UUID = Path(..., description="The ID of the node"),
    node_service: NodeService = Depends(get_node_service)
):
    """
    Get all ancestors of a node up to the root.
    
    Returns the path from the root layer down to the specified node's parent.
    Useful for breadcrumb navigation and understanding node context.
    """
    try:
        ancestors = node_service.get_node_ancestors(str(node_id))
        return [to_node_out(ancestor) for ancestor in ancestors]
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
