"""
Model conversion utilities for Nodes API

This module contains functions for converting between database models
and API models for the nodes endpoints.
"""

from typing import List, Optional
from database.models import Node, NodeLink
from database.enums import NodeType
from api.models.nodes import NodeOut, NodeLinkOut
from uuid import UUID


def to_node_out(node: Node) -> NodeOut:
    """
    Convert a database Node model to API NodeOut model.
    
    Args:
        node: Database Node instance
        
    Returns:
        NodeOut model for API response
    """
    # Convert embeddings from binary blob to list of floats if they exist
    title_embedding = None
    definition_embedding = None
    
    if node.title_embedding:
        try:
            import pickle
            title_embedding = pickle.loads(node.title_embedding)
            # Ensure it's a list of floats
            if isinstance(title_embedding, (list, tuple)):
                title_embedding = [float(x) for x in title_embedding]
        except Exception:
            # If unpickling fails, leave as None
            title_embedding = None
    
    if node.definition_embedding:
        try:
            import pickle
            definition_embedding = pickle.loads(node.definition_embedding)
            # Ensure it's a list of floats
            if isinstance(definition_embedding, (list, tuple)):
                definition_embedding = [float(x) for x in definition_embedding]
        except Exception:
            # If unpickling fails, leave as None
            definition_embedding = None
    
    return NodeOut(
        id=UUID(node.id),
        node_type=node.node_type.value,  # Convert enum to string
        parent_node_id=UUID(node.parent_node_id) if node.parent_node_id else None,
        title=node.title,
        definition=node.definition,
        structural_predicate_id=UUID(node.structural_predicate_id) if node.structural_predicate_id else None,
        title_embedding=title_embedding,
        definition_embedding=definition_embedding,
        created_at=node.created_at.isoformat() if node.created_at else None,
        version=node.version,
        last_modified=node.last_modified.isoformat() if node.last_modified else None
    )


def to_node_link_out(link: NodeLink) -> NodeLinkOut:
    """
    Convert a database NodeLink model to API NodeLinkOut model.
    
    Args:
        link: Database NodeLink instance
        
    Returns:
        NodeLinkOut model for API response
    """
    return NodeLinkOut(
        id=UUID(link.id),
        source_node_id=UUID(link.source_node_id),
        target_node_id=UUID(link.target_node_id),
        predicate=link.predicate,
        predicate_id=UUID(link.predicate_id) if link.predicate_id else None,
        created_at=link.created_at.isoformat() if link.created_at else None
    )


def nodes_to_paginated_response(nodes: List[Node], total: int, skip: int, limit: int) -> dict:
    """
    Convert a list of nodes and pagination info to a paginated response.
    
    Args:
        nodes: List of database Node instances
        total: Total number of nodes matching the query
        skip: Number of nodes skipped
        limit: Maximum number of nodes returned
        
    Returns:
        Dictionary for PaginatedNodesResponse
    """
    return {
        "data": [to_node_out(node) for node in nodes],
        "total": total,
        "skip": skip,
        "limit": limit
    }


def convert_api_node_type_to_db(api_node_type: str) -> NodeType:
    """
    Convert API NodeTypeEnum string to database NodeType enum.
    
    Args:
        api_node_type: String value from API
        
    Returns:
        Database NodeType enum
    """
    return NodeType(api_node_type)


def uuid_to_str(uuid_val: Optional[UUID]) -> Optional[str]:
    """
    Convert UUID to string, handling None values.
    
    Args:
        uuid_val: UUID value or None
        
    Returns:
        String representation or None
    """
    return str(uuid_val) if uuid_val else None
