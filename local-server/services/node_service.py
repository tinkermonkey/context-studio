"""
Node Service - Centralized business logic for node operations

This service implements the business logic for the normalized node structure,
handling type-specific validations and constraints for layers, domains, and terms.
"""

from enum import Enum
from typing import List, Optional, Dict, Any, Union
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from database.models import Node, NodeEvent
from database.enums import NodeType
from graph.graph_service import GraphService
from embeddings.generate_embeddings import generate_embedding
from services.node_event_handler import NodeEventHandler
from utils.logger import get_logger

logger = get_logger(__name__)


class NodeService:
    """Centralized business logic for node operations"""
    
    def __init__(self, db: Session, graph_service: Optional[GraphService] = None):
        """
        Initialize the NodeService.
        
        Args:
            db: SQLAlchemy database session
            graph_service: Optional graph service for graph operations
        """
        self.db = db
        self.graph_service = graph_service  # Keep optional for now since GraphService needs updating
        self.event_handler = NodeEventHandler(db)
        logger.info("NodeService initialized with event handling")
    
    def create_node(self, node_data: Dict[str, Any]) -> Node:
        """
        Create a new node with type-specific validation.
        
        Args:
            node_data: Dictionary containing node data
            
        Returns:
            Created Node instance
            
        Raises:
            ValueError: If validation fails
        """
        logger.info(f"Creating node with type: {node_data.get('node_type')}")
        
        # Validate required fields
        if 'node_type' not in node_data:
            raise ValueError("node_type is required")
        if 'title' not in node_data:
            raise ValueError("title is required")
        
        node_type = NodeType(node_data['node_type'])
        
        # Validate node type specific rules
        self._validate_node_creation(node_data, node_type)
        
        # Check for circular references if parent is specified
        if node_data.get('parent_node_id'):
            self._validate_no_circular_reference(None, node_data['parent_node_id'])
        
        # Generate embeddings
        title_embedding = None
        definition_embedding = None
        
        if node_data.get('title'):
            try:
                title_embedding = generate_embedding(node_data['title'])
            except Exception as e:
                logger.warning(f"Failed to generate title embedding: {e}")
        
        if node_data.get('definition'):
            try:
                definition_embedding = generate_embedding(node_data['definition'])
            except Exception as e:
                logger.warning(f"Failed to generate definition embedding: {e}")
        
        # Create node
        node = Node(
            node_type=node_type,
            parent_node_id=node_data.get('parent_node_id'),
            title=node_data['title'],
            definition=node_data.get('definition'),
            structural_predicate_id=node_data.get('structural_predicate_id'),
            title_embedding=title_embedding,
            definition_embedding=definition_embedding
        )
        
        try:
            self.db.add(node)
            self.db.commit()
            self.db.refresh(node)
            
            logger.info(f"Successfully created node: {node.id} ({node.node_type})")
            
            # Fire node created event
            node_dict = self._node_to_dict(node)
            self.event_handler.fire_node_created_event(node_type.value, node_dict)
            
            return node
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create node: {e}")
            raise ValueError(f"Failed to create node: {e}")
    
    def update_node(self, node_id: str, node_data: Dict[str, Any]) -> Node:
        """
        Update an existing node with type-specific validation.
        
        Args:
            node_id: ID of the node to update
            node_data: Dictionary containing updated node data
            
        Returns:
            Updated Node instance
            
        Raises:
            ValueError: If validation fails or node not found
        """
        logger.info(f"Updating node: {node_id}")
        
        # Get existing node
        node = self.db.query(Node).filter(Node.id == node_id).first()
        if not node:
            raise ValueError(f"Node not found: {node_id}")
        
        # Store old data for validation and events
        old_node_data = self._node_to_dict(node)
        
        # Validate updates based on node type
        self._validate_node_update(node, node_data)
        
        # Check for circular references if parent is being changed
        if 'parent_node_id' in node_data and node_data['parent_node_id'] != node.parent_node_id:
            self._validate_no_circular_reference(node_id, node_data['parent_node_id'])
        
        # Update fields
        if 'title' in node_data:
            node.title = node_data['title']
            # Regenerate title embedding
            try:
                node.title_embedding = generate_embedding(node_data['title'])
            except Exception as e:
                logger.warning(f"Failed to generate title embedding: {e}")
        
        if 'definition' in node_data:
            node.definition = node_data['definition']
            # Regenerate definition embedding
            try:
                if node_data['definition']:
                    node.definition_embedding = generate_embedding(node_data['definition'])
                else:
                    node.definition_embedding = None
            except Exception as e:
                logger.warning(f"Failed to generate definition embedding: {e}")
        
        if 'parent_node_id' in node_data:
            node.parent_node_id = node_data['parent_node_id']
        
        if 'structural_predicate_id' in node_data:
            node.structural_predicate_id = node_data['structural_predicate_id']
        
        # Update version
        node.version = node.version + 1
        
        try:
            self.db.commit()
            self.db.refresh(node)
            
            logger.info(f"Successfully updated node: {node.id}")
            
            # Fire node updated event
            new_node_data = self._node_to_dict(node)
            self.event_handler.fire_node_updated_event(node.node_type.value, old_node_data, new_node_data)
            
            return node
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update node: {e}")
            raise ValueError(f"Failed to update node: {e}")
    
    def delete_node(self, node_id: str) -> bool:
        """
        Delete a node and its children (cascade delete).
        
        Args:
            node_id: ID of the node to delete
            
        Returns:
            True if deleted successfully
            
        Raises:
            ValueError: If node not found
        """
        logger.info(f"Deleting node: {node_id}")
        
        node = self.db.query(Node).filter(Node.id == node_id).first()
        if not node:
            raise ValueError(f"Node not found: {node_id}")
        
        # Store node data for event before deletion
        node_data = self._node_to_dict(node)
        node_type = node.node_type.value
        
        # Get all descendant nodes recursively
        all_descendants = self._get_all_descendants(node_id)
        total_children = len(all_descendants)
        
        try:
            # Delete all descendants first (bottom-up)
            for descendant in reversed(all_descendants):
                self.db.delete(descendant)
            
            # Then delete the node itself
            self.db.delete(node)
            self.db.commit()
            
            logger.info(f"Successfully deleted node {node_id} and {total_children} children")
            
            # Fire node deleted event
            self.event_handler.fire_node_deleted_event(node_type, node_data)
            
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete node: {e}")
            raise ValueError(f"Failed to delete node: {e}")
    
    def get_node(self, node_id: str) -> Optional[Node]:
        """
        Get a node by ID.
        
        Args:
            node_id: ID of the node to retrieve
            
        Returns:
            Node instance or None if not found
        """
        return self.db.query(Node).filter(Node.id == node_id).first()
    
    def list_nodes(self, node_type: Optional[NodeType] = None, 
                   parent_node_id: Optional[str] = None,
                   skip: int = 0, limit: int = 50) -> List[Node]:
        """
        List nodes with optional filtering.
        
        Args:
            node_type: Optional node type to filter by
            parent_node_id: Optional parent node ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of Node instances
        """
        query = self.db.query(Node)
        
        if node_type:
            query = query.filter(Node.node_type == node_type)
        
        if parent_node_id:
            query = query.filter(Node.parent_node_id == parent_node_id)
        
        return query.order_by(Node.title).offset(skip).limit(limit).all()
    
    def count_nodes(self, node_type: Optional[NodeType] = None, 
                    parent_node_id: Optional[str] = None) -> int:
        """
        Count nodes with optional filtering.
        
        Args:
            node_type: Optional node type to filter by
            parent_node_id: Optional parent node ID to filter by
            
        Returns:
            Count of matching nodes
        """
        query = self.db.query(Node)
        
        if node_type:
            query = query.filter(Node.node_type == node_type)
        
        if parent_node_id:
            query = query.filter(Node.parent_node_id == parent_node_id)
        
        return query.count()
    
    def get_nodes(self, node_type: Optional[NodeType] = None,
                  parent_node_id: Optional[str] = None,
                  limit: Optional[int] = None,
                  offset: Optional[int] = None) -> List[Node]:
        """
        Get nodes with optional filtering and pagination.
        
        Args:
            node_type: Optional node type to filter by
            parent_node_id: Optional parent node ID to filter by
            limit: Maximum number of results to return
            offset: Number of results to skip
            
        Returns:
            List of matching nodes
        """
        query = self.db.query(Node)
        
        if node_type:
            query = query.filter(Node.node_type == node_type)
        
        if parent_node_id:
            query = query.filter(Node.parent_node_id == parent_node_id)
        
        query = query.order_by(Node.title)
        
        if offset:
            query = query.offset(offset)
            
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def get_node_children(self, node_id: str, recursive: bool = False) -> List[Node]:
        """
        Get children of a node.
        
        Args:
            node_id: Parent node ID
            recursive: Whether to get all descendants or just direct children
            
        Returns:
            List of child Node instances
        """
        if not recursive:
            return self.db.query(Node).filter(Node.parent_node_id == node_id).order_by(Node.title).all()
        
        # For recursive, we need to traverse the tree
        all_children = []
        direct_children = self.db.query(Node).filter(Node.parent_node_id == node_id).all()
        
        for child in direct_children:
            all_children.append(child)
            all_children.extend(self.get_node_children(child.id, recursive=True))
        
        return all_children
    
    def get_node_ancestors(self, node_id: str) -> List[Node]:
        """
        Get all ancestors of a node (up to root).
        
        Args:
            node_id: Node ID to get ancestors for
            
        Returns:
            List of ancestor Node instances (from immediate parent to root)
        """
        ancestors = []
        current_node = self.get_node(node_id)
        
        while current_node and current_node.parent_node_id:
            parent = self.get_node(current_node.parent_node_id)
            if parent:
                ancestors.append(parent)
                current_node = parent
            else:
                break
        
        return ancestors
    
    # Private validation methods
    
    def _validate_node_creation(self, node_data: Dict[str, Any], node_type: NodeType):
        """Validate node creation based on type-specific rules"""
        if node_type == NodeType.LAYER:
            self._validate_layer_creation(node_data)
        elif node_type == NodeType.DOMAIN:
            self._validate_domain_creation(node_data)
        elif node_type == NodeType.TERM:
            self._validate_term_creation(node_data)
    
    def _validate_node_update(self, node: Node, node_data: Dict[str, Any]):
        """Validate node update based on type-specific rules"""
        if node.node_type == NodeType.LAYER:
            self._validate_layer_update(node, node_data)
        elif node.node_type == NodeType.DOMAIN:
            self._validate_domain_update(node, node_data)
        elif node.node_type == NodeType.TERM:
            self._validate_term_update(node, node_data)
    
    def _validate_layer_creation(self, node_data: Dict[str, Any]):
        """Validate layer creation rules"""
        # Layer titles must be unique globally
        existing = self.db.query(Node).filter(
            Node.node_type == NodeType.LAYER,
            Node.title == node_data['title']
        ).first()
        
        if existing:
            raise ValueError("Layer title must be unique")
        
        # Layers should not have parents
        if node_data.get('parent_node_id'):
            raise ValueError("Layers cannot have parent nodes")
    
    def _validate_layer_update(self, node: Node, node_data: Dict[str, Any]):
        """Validate layer update rules"""
        # Check title uniqueness if title is being updated
        if 'title' in node_data and node_data['title'] != node.title:
            existing = self.db.query(Node).filter(
                Node.node_type == NodeType.LAYER,
                Node.title == node_data['title'],
                Node.id != node.id
            ).first()
            
            if existing:
                raise ValueError("Layer title must be unique")
        
        # Layers should not have parents
        if 'parent_node_id' in node_data and node_data['parent_node_id'] is not None:
            raise ValueError("Layers cannot have parent nodes")
    
    def _validate_domain_creation(self, node_data: Dict[str, Any]):
        """Validate domain creation rules"""
        parent_id = node_data.get('parent_node_id')
        if not parent_id:
            raise ValueError("Domains must have a parent layer")
        
        # Parent must be a layer
        parent = self.db.query(Node).filter(Node.id == parent_id).first()
        if not parent or parent.node_type != NodeType.LAYER:
            raise ValueError("Domain parent must be a layer")
        
        # Domain titles must be unique within the layer
        existing = self.db.query(Node).filter(
            Node.node_type == NodeType.DOMAIN,
            Node.parent_node_id == parent_id,
            Node.title == node_data['title']
        ).first()
        
        if existing:
            raise ValueError("Domain title must be unique within layer")
    
    def _validate_domain_update(self, node: Node, node_data: Dict[str, Any]):
        """Validate domain update rules"""
        parent_id = node_data.get('parent_node_id', node.parent_node_id)
        
        # Parent validation if changing parent
        if 'parent_node_id' in node_data:
            if not parent_id:
                raise ValueError("Domains must have a parent layer")
            
            parent = self.db.query(Node).filter(Node.id == parent_id).first()
            if not parent or parent.node_type != NodeType.LAYER:
                raise ValueError("Domain parent must be a layer")
        
        # Check title uniqueness within layer if title or parent is changing
        check_title_uniqueness = (
            'title' in node_data and node_data['title'] != node.title
        ) or (
            'parent_node_id' in node_data and node_data['parent_node_id'] != node.parent_node_id
        )
        
        if check_title_uniqueness:
            title = node_data.get('title', node.title)
            existing = self.db.query(Node).filter(
                Node.node_type == NodeType.DOMAIN,
                Node.parent_node_id == parent_id,
                Node.title == title,
                Node.id != node.id
            ).first()
            
            if existing:
                raise ValueError("Domain title must be unique within layer")
    
    def _validate_term_creation(self, node_data: Dict[str, Any]):
        """Validate term creation rules"""
        parent_id = node_data.get('parent_node_id')
        if not parent_id:
            raise ValueError("Terms must have a parent domain or term")
        
        # Parent must be a domain or term
        parent = self.db.query(Node).filter(Node.id == parent_id).first()
        if not parent or parent.node_type not in [NodeType.DOMAIN, NodeType.TERM]:
            raise ValueError("Term parent must be a domain or term")
        
        # Get the domain (either direct parent or ancestor)
        domain = self._get_domain_ancestor(parent)
        if not domain:
            raise ValueError("Term must belong to a domain")
        
        # Term titles must be unique within the domain
        if self._check_title_uniqueness_in_domain(domain.id, node_data['title']):
            raise ValueError("Term title must be unique within domain")
    
    def _validate_term_update(self, node: Node, node_data: Dict[str, Any]):
        """Validate term update rules"""
        parent_id = node_data.get('parent_node_id', node.parent_node_id)
        
        # Parent validation if changing parent
        if 'parent_node_id' in node_data:
            if not parent_id:
                raise ValueError("Terms must have a parent domain or term")
            
            parent = self.db.query(Node).filter(Node.id == parent_id).first()
            if not parent or parent.node_type not in [NodeType.DOMAIN, NodeType.TERM]:
                raise ValueError("Term parent must be a domain or term")
        
        # Get the domain for uniqueness check
        if parent_id:
            parent = self.db.query(Node).filter(Node.id == parent_id).first()
            domain = self._get_domain_ancestor(parent) if parent else None
        else:
            domain = None
        
        if not domain:
            raise ValueError("Term must belong to a domain")
        
        # Check title uniqueness within domain if title or parent is changing
        check_title_uniqueness = (
            'title' in node_data and node_data['title'] != node.title
        ) or (
            'parent_node_id' in node_data and node_data['parent_node_id'] != node.parent_node_id
        )
        
        if check_title_uniqueness:
            title = node_data.get('title', node.title)
            if self._check_title_uniqueness_in_domain(domain.id, title, exclude_id=node.id):
                raise ValueError("Term title must be unique within domain")
    
    def _validate_no_circular_reference(self, node_id: Optional[str], parent_id: Optional[str]):
        """
        Validate no circular references.
        
        For now, this is a simple implementation. The Graph Service integration
        can be enhanced later for more sophisticated cycle detection.
        """
        if not parent_id or not node_id:
            return
        
        # Check if parent_id is the same as node_id
        if node_id == parent_id:
            raise ValueError("Node cannot be its own parent")
        
        # Check if parent_id is a descendant of node_id
        ancestors = self.get_node_ancestors(parent_id)
        ancestor_ids = [ancestor.id for ancestor in ancestors]
        
        if node_id in ancestor_ids:
            raise ValueError("Operation would create circular reference")
    
    def _get_domain_ancestor(self, node: Node) -> Optional[Node]:
        """Get the domain ancestor of a node"""
        current = node
        while current:
            if current.node_type == NodeType.DOMAIN:
                return current
            if current.parent_node_id:
                current = self.db.query(Node).filter(Node.id == current.parent_node_id).first()
            else:
                break
        return None
    
    def _check_title_uniqueness_in_domain(self, domain_id: str, title: str, exclude_id: Optional[str] = None) -> bool:
        """
        Check if title is unique within domain.
        
        Args:
            domain_id: Domain ID to check within
            title: Title to check for uniqueness
            exclude_id: Optional node ID to exclude from check (for updates)
            
        Returns:
            True if title already exists (not unique), False if unique
        """
        # Get all terms in the domain tree
        domain_terms = self._get_all_terms_in_domain(domain_id)
        
        # Check for title conflicts
        query = self.db.query(Node).filter(
            Node.node_type == NodeType.TERM,
            Node.id.in_(domain_terms),
            Node.title == title
        )
        
        if exclude_id:
            query = query.filter(Node.id != exclude_id)
        
        existing = query.first()
        return existing is not None
    
    def _get_all_terms_in_domain(self, domain_id: str) -> List[str]:
        """
        Get all term IDs that belong to a domain (including terms under other terms).
        
        Args:
            domain_id: Domain ID
            
        Returns:
            List of term IDs in the domain
        """
        # Get direct terms under the domain
        direct_terms = self.db.query(Node.id).filter(
            Node.node_type == NodeType.TERM,
            Node.parent_node_id == domain_id
        ).all()
        
        all_term_ids = [term[0] for term in direct_terms]
        
        # Recursively get terms under terms
        for term_id in all_term_ids[:]:  # Copy list to avoid modification during iteration
            child_terms = self._get_all_terms_under_term(term_id)
            all_term_ids.extend(child_terms)
        
        return all_term_ids
    
    def _get_all_terms_under_term(self, term_id: str) -> List[str]:
        """
        Recursively get all term IDs under a given term.
        
        Args:
            term_id: Parent term ID
            
        Returns:
            List of descendant term IDs
        """
        child_terms = self.db.query(Node.id).filter(
            Node.node_type == NodeType.TERM,
            Node.parent_node_id == term_id
        ).all()
        
        all_child_ids = [term[0] for term in child_terms]
        
        # Recursively get children of children
        for child_id in all_child_ids[:]:
            grandchild_terms = self._get_all_terms_under_term(child_id)
            all_child_ids.extend(grandchild_terms)
        
        return all_child_ids
    
    def _node_to_dict(self, node: Node) -> Dict[str, Any]:
        """Convert a Node instance to a dictionary"""
        return {
            'id': node.id,
            'node_type': node.node_type.value if isinstance(node.node_type, NodeType) else node.node_type,
            'parent_node_id': node.parent_node_id,
            'title': node.title,
            'definition': node.definition,
            'structural_predicate_id': node.structural_predicate_id,
            'created_at': node.created_at.isoformat() if node.created_at else None,
            'version': node.version,
            'last_modified': node.last_modified.isoformat() if node.last_modified else None
        }
    
    def _fire_node_event(self, event_type: str, node_type: str, old_data: Optional[Dict[str, Any]], new_data: Optional[Dict[str, Any]]):
        """
        Fire a node event manually (if needed).
        
        Note: Database triggers should handle this automatically, but this method
        is available for manual event firing if required.
        """
        try:
            event = NodeEvent(
                event_type=event_type,
                node_type=node_type,
                old_data=old_data,
                new_data=new_data
            )
            
            self.db.add(event)
            self.db.commit()
            
        except Exception as e:
            logger.warning(f"Failed to fire node event: {e}")

    def _get_all_descendants(self, node_id: str) -> List[Node]:
        """
        Get all descendant nodes recursively.
        
        Args:
            node_id: Parent node ID
            
        Returns:
            List of all descendant Node instances
        """
        all_descendants = []
        
        # Get direct children
        direct_children = self.db.query(Node).filter(Node.parent_node_id == node_id).all()
        
        for child in direct_children:
            # Add child to the list
            all_descendants.append(child)
            # Recursively add child's descendants
            all_descendants.extend(self._get_all_descendants(child.id))
        
        return all_descendants
