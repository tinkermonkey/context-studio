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
from sqlalchemy.orm import Session

from database.models import StructureNode, StructureNodeLink
from database.utils import get_db
from services.node_service import NodeService
from services.node_link_service import NodeLinkService
from api.models.structure_nodes import (
    NodeCreate, NodeUpdate, NodeOut, NodeLinkCreate, NodeLinkOut,
    NodeSearchRequest, NodeSearchResult, PaginatedNodesResponse, NodeTypeEnum
)
from api.utils.node_conversion import (
    to_node_out, to_node_link_out, nodes_to_paginated_response,
    convert_api_node_type_to_db, uuid_to_str
)
from api.dependencies.structure_nodes import get_node_service, get_node_link_service

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
        return to_node_out(created_node)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/", response_model=PaginatedNodesResponse)
def list_nodes(
    node_type: Optional[NodeTypeEnum] = Query(None, description="Filter by structure_node type"),
    parent_node_id: Optional[UUID] = Query(None, description="Filter by parent structure_node ID"),
    skip: int = Query(0, ge=0, description="Number of structure_nodes to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of structure_nodes to return"),
    sort_by: str = Query("title", pattern="^(title|created_at)$", description="Sort field"),
    db: Session = Depends(get_db)
):
    """
    List structure_nodes with filtering and pagination.
    
    Supports filtering by structure_node type and parent, with configurable pagination
    and sorting. This replaces the separate endpoints for layers, domains, and terms.
    """
    try:
        query = db.query(StructureNode)
        
        # Apply filters
        if node_type:
            db_node_type = convert_api_node_type_to_db(node_type.value)
            query = query.filter(StructureNode.node_type == db_node_type)
            
        if parent_node_id:
            query = query.filter(StructureNode.parent_node_id == str(parent_node_id))
        
        # Get total count before pagination
        total = query.count()
        
        # Apply sorting
        if sort_by == "title":
            query = query.order_by(StructureNode.title)
        elif sort_by == "created_at":
            query = query.order_by(StructureNode.created_at.desc())
        
        # Apply pagination
        structure_nodes = query.offset(skip).limit(limit).all()
        
        return PaginatedNodesResponse(**nodes_to_paginated_response(structure_nodes, total, skip, limit))
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/find", response_model=List[NodeSearchResult])
def search_nodes(
    search_request: NodeSearchRequest,
    db: Session = Depends(get_db)
):
    """
    Vector search across structure_nodes.
    
    This endpoint replaces the separate find endpoints for layers, domains, and terms.
    Supports semantic search across structure_node titles and definitions with optional
    type filtering and configurable similarity thresholds.
    
    Note: Implementation depends on vector search infrastructure being available.
    """
    # TODO: Implement vector search functionality
    # This would integrate with the existing vector search infrastructure
    # and work with the structure_nodes_vec virtual table
    
    # Placeholder implementation - would need to be completed based on
    # existing vector search patterns in the codebase
    raise HTTPException(
        status_code=501, 
        detail="Vector search implementation pending - requires integration with existing vector search infrastructure"
    )


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
    source_node_id: Optional[UUID] = Query(None, description="Filter by source structure_node ID"),
    target_node_id: Optional[UUID] = Query(None, description="Filter by target structure_node ID"),
    predicate: Optional[str] = Query(None, description="Filter by predicate"),
    skip: int = Query(0, ge=0, description="Number of links to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of links to return"),
    db: Session = Depends(get_db)
):
    """
    List structure_node links with filtering.
    
    Supports filtering by source structure_node, target structure_node, and predicate.
    Returns all relationships in the unified structure_node graph.
    """
    try:
        query = db.query(StructureNodeLink)
        
        # Apply filters
        if source_node_id:
            query = query.filter(StructureNodeLink.source_node_id == str(source_node_id))
        if target_node_id:
            query = query.filter(StructureNodeLink.target_node_id == str(target_node_id))
        if predicate:
            query = query.filter(StructureNodeLink.predicate == predicate)
        
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
    Update a structure_node link.
    
    Allows updating the predicate and predicate_id of an existing link.
    Source and target structure_nodes can also be updated if the new configuration is valid.
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
    Delete a structure_node link.
    
    Removes the relationship between two structure_nodes. This operation cannot be undone.
    """
    try:
        success = link_service.delete_link(str(link_id))
        if success:
            return {"success": True, "message": "StructureNode link deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="StructureNode link not found")
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{node_id}", response_model=NodeOut)
def get_node(
    node_id: UUID = Path(..., description="The ID of the structure_node to retrieve"),
    db: Session = Depends(get_db)
):
    """
    Get a specific structure_node by ID.
    
    Returns the complete structure_node information including embeddings,
    hierarchy information, and metadata.
    """
    structure_node = db.query(StructureNode).filter(StructureNode.id == str(node_id)).first()
    if not structure_node:
        raise HTTPException(status_code=404, detail="StructureNode not found")
    
    return to_node_out(structure_node)


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
    node_id: UUID = Path(..., description="The ID of the structure_node to delete"),
    node_service: NodeService = Depends(get_node_service)
):
    """
    Delete a structure_node and its children.
    
    This operation cascades to all child structure_nodes and their relationships.
    Use with caution as this operation cannot be undone.
    """
    try:
        success = node_service.delete_node(str(node_id))
        if success:
            return {"success": True, "message": "StructureNode and children deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="StructureNode not found")
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# Additional utility endpoints
@router.get("/{node_id}/children", response_model=List[NodeOut])
def get_node_children(
    node_id: UUID = Path(..., description="The ID of the parent structure_node"),
    node_service: NodeService = Depends(get_node_service)
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
    node_service: NodeService = Depends(get_node_service)
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
