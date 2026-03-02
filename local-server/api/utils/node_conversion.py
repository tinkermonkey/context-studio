"""
Model conversion utilities for StructureNodes API

This module contains functions for converting between database models
and API models for the structure_nodes endpoints.
"""

from typing import List, Optional
from database.models import StructureNode, StructureNodeLink
from database.enums import NodeType
from api.models.structure_nodes import NodeOut, NodeLinkOut, NodeTypeEnum
from uuid import UUID
import numpy as np


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
                # Embeddings are stored as raw numpy float32 bytes via np.float32.tobytes()
                title_embedding = np.frombuffer(bytes(structure_node.title_embedding), dtype=np.float32).tolist()
            except Exception:
                # If deserialization fails, leave as None
                title_embedding = None

        if hasattr(structure_node, 'definition_embedding') and structure_node.definition_embedding:
            try:
                # Embeddings are stored as raw numpy float32 bytes via np.float32.tobytes()
                definition_embedding = np.frombuffer(bytes(structure_node.definition_embedding), dtype=np.float32).tolist()
            except Exception:
                # If deserialization fails, leave as None
                definition_embedding = None
    
    # Handle the ID field - ensure it's properly converted to UUID
    # During tests, if refresh() is mocked, the id field might not be populated correctly
    try:
        if isinstance(structure_node.id, UUID):
            node_id = structure_node.id
        elif isinstance(structure_node.id, str):
            node_id = UUID(structure_node.id)
        else:
            # This case handles Mock objects or other unexpected types in test scenarios
            # Try to convert to string first, then to UUID
            id_str = str(structure_node.id)
            node_id = UUID(id_str)
    except (TypeError, ValueError, AttributeError) as e:
        # Provide detailed error message for debugging
        error_msg = (
            f"Invalid structure_node ID: {repr(structure_node.id)} "
            f"(type: {type(structure_node.id).__name__}). "
            f"This may indicate that db.refresh() was mocked or the database default "
            f"value generation failed."
        )
        raise ValueError(error_msg) from e
    
    return NodeOut(
        id=node_id,
        node_type=NodeTypeEnum(structure_node.node_type.value),  # Convert to NodeTypeEnum
        parent_node_id=UUID(str(structure_node.parent_node_id)) if structure_node.parent_node_id else None,
        title=str(structure_node.title),
        definition=str(structure_node.definition) if structure_node.definition else None,
        structural_predicate_id=UUID(str(structure_node.structural_predicate_id)) if structure_node.structural_predicate_id else None,
        title_embedding=title_embedding,
        definition_embedding=definition_embedding,
        created_at=str(structure_node.created_at.isoformat()) if structure_node.created_at else None,  # type: ignore
        version=int(structure_node.version),
        last_modified=str(structure_node.last_modified.isoformat()) if structure_node.last_modified else None  # type: ignore
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
        id=UUID(str(link.id)),
        source_node_id=UUID(str(link.source_node_id)),
        target_node_id=UUID(str(link.target_node_id)),
        predicate=str(link.predicate),
        predicate_id=UUID(str(link.predicate_id)) if link.predicate_id else None,
        created_at=str(link.created_at.isoformat()) if link.created_at else None  # type: ignore
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
