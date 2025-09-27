"""
Model conversion utilities for StructureNodes API

This module contains functions for converting between database models
and API models for the structure_nodes endpoints.
"""

from typing import List, Optional
from database.models import StructureNode, StructureNodeLink
from database.enums import NodeType
from api.models.structure_nodes import NodeOut, NodeLinkOut
from uuid import UUID


def to_node_out(structure_node: StructureNode, include_embeddings: bool = True) -> NodeOut:
    """
    Convert a database StructureNode model to API NodeOut model.

    Args:
        structure_node: Database StructureNode instance
        include_embeddings: Whether to include/process embedding data (expensive)

    Returns:
        NodeOut model for API response
    """
    # Convert embeddings from binary blob to list of floats if they exist
    title_embedding = None
    definition_embedding = None

    # Only process embeddings if explicitly requested (to avoid expensive operations in list views)
    if include_embeddings:
        # Check if the attribute is loaded (not deferred) before accessing
        if hasattr(structure_node, 'title_embedding') and structure_node.title_embedding:
            try:
                import pickle
                title_embedding = pickle.loads(structure_node.title_embedding)
                # Ensure it's a list of floats
                if isinstance(title_embedding, (list, tuple)):
                    title_embedding = [float(x) for x in title_embedding]
            except Exception:
                # If unpickling fails, leave as None
                title_embedding = None

        if hasattr(structure_node, 'definition_embedding') and structure_node.definition_embedding:
            try:
                import pickle
                definition_embedding = pickle.loads(structure_node.definition_embedding)
                # Ensure it's a list of floats
                if isinstance(definition_embedding, (list, tuple)):
                    definition_embedding = [float(x) for x in definition_embedding]
            except Exception:
                # If unpickling fails, leave as None
                definition_embedding = None
    
    return NodeOut(
        id=UUID(structure_node.id),
        node_type=structure_node.node_type.value,  # Convert enum to string
        parent_node_id=UUID(structure_node.parent_node_id) if structure_node.parent_node_id else None,
        title=structure_node.title,
        definition=structure_node.definition,
        structural_predicate_id=UUID(structure_node.structural_predicate_id) if structure_node.structural_predicate_id else None,
        title_embedding=title_embedding,
        definition_embedding=definition_embedding,
        created_at=structure_node.created_at.isoformat() if structure_node.created_at else None,
        version=structure_node.version,
        last_modified=structure_node.last_modified.isoformat() if structure_node.last_modified else None
    )


def to_node_link_out(link: StructureNodeLink) -> NodeLinkOut:
    """
    Convert a database StructureNodeLink model to API NodeLinkOut model.
    
    Args:
        link: Database StructureNodeLink instance
        
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


def nodes_to_paginated_response(structure_nodes: List[StructureNode], total: int, skip: int, limit: int) -> dict:
    """
    Convert a list of structure_nodes and pagination info to a paginated response.

    Args:
        structure_nodes: List of database StructureNode instances
        total: Total number of structure_nodes matching the query
        skip: Number of structure_nodes skipped
        limit: Maximum number of structure_nodes returned

    Returns:
        Dictionary for PaginatedNodesResponse
    """
    return {
        "data": [to_node_out(structure_node, include_embeddings=False) for structure_node in structure_nodes],
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
