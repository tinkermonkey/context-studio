"""
Node Link Service - Centralized business logic for node link operations

This service implements the business logic for node relationships,
ensuring that only compatible nodes can be linked together.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from database.models import Node, NodeLink
from database.enums import NodeType
from services.node_event_handler import NodeEventHandler
from utils.logger import get_logger

logger = get_logger(__name__)


class NodeLinkService:
    """Centralized business logic for node link operations"""
    
    def __init__(self, db: Session):
        """
        Initialize the NodeLinkService.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.event_handler = NodeEventHandler(db)
        logger.info("NodeLinkService initialized with event handling")
    
    def create_link(self, link_data: Dict[str, Any]) -> NodeLink:
        """
        Create a new node link with validation.
        
        Args:
            link_data: Dictionary containing link data
            
        Returns:
            Created NodeLink instance
            
        Raises:
            ValueError: If validation fails
        """
        logger.info(f"Creating node link: {link_data.get('source_node_id')} -> {link_data.get('target_node_id')}")
        
        # Validate required fields
        required_fields = ['source_node_id', 'target_node_id', 'predicate']
        for field in required_fields:
            if field not in link_data:
                raise ValueError(f"{field} is required")
        
        source_id = link_data['source_node_id']
        target_id = link_data['target_node_id']
        predicate = link_data['predicate']
        
        # Validate that source and target are different
        if source_id == target_id:
            raise ValueError("Source and target nodes cannot be the same")
        
        # Get source and target nodes
        source = self.db.query(Node).filter(Node.id == source_id).first()
        target = self.db.query(Node).filter(Node.id == target_id).first()
        
        if not source:
            raise ValueError(f"Source node not found: {source_id}")
        if not target:
            raise ValueError(f"Target node not found: {target_id}")
        
        # Validate same node type constraint
        if source.node_type != target.node_type:
            raise ValueError(
                f"Nodes can only be linked to nodes of the same type. "
                f"Source is {source.node_type}, target is {target.node_type}"
            )
        
        # Check for duplicate links
        existing = self.db.query(NodeLink).filter(
            NodeLink.source_node_id == source_id,
            NodeLink.target_node_id == target_id,
            NodeLink.predicate == predicate
        ).first()
        
        if existing:
            raise ValueError(f"Link already exists: {source_id} -> {target_id} ({predicate})")
        
        # Create link
        link = NodeLink(
            source_node_id=source_id,
            target_node_id=target_id,
            predicate=predicate,
            predicate_id=link_data.get('predicate_id')
        )
        
        try:
            self.db.add(link)
            self.db.commit()
            self.db.refresh(link)
            
            logger.info(f"Successfully created node link: {link.id}")
            
            # Fire node link created event
            link_dict = self._node_link_to_dict(link)
            self.event_handler.fire_node_created_event('node_link', link_dict)
            
            return link
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create node link: {e}")
            raise ValueError(f"Failed to create node link: {e}")
    
    def update_link(self, link_id: str, link_data: Dict[str, Any]) -> NodeLink:
        """
        Update an existing node link.
        
        Args:
            link_id: ID of the link to update
            link_data: Dictionary containing updated link data
            
        Returns:
            Updated NodeLink instance
            
        Raises:
            ValueError: If validation fails or link not found
        """
        logger.info(f"Updating node link: {link_id}")
        
        # Get existing link
        link = self.db.query(NodeLink).filter(NodeLink.id == link_id).first()
        if not link:
            raise ValueError(f"Node link not found: {link_id}")
        
        # Validate updated fields
        if 'source_node_id' in link_data or 'target_node_id' in link_data:
            source_id = link_data.get('source_node_id', link.source_node_id)
            target_id = link_data.get('target_node_id', link.target_node_id)
            
            if source_id == target_id:
                raise ValueError("Source and target nodes cannot be the same")
            
            # Get nodes to validate
            source = self.db.query(Node).filter(Node.id == source_id).first()
            target = self.db.query(Node).filter(Node.id == target_id).first()
            
            if not source:
                raise ValueError(f"Source node not found: {source_id}")
            if not target:
                raise ValueError(f"Target node not found: {target_id}")
            
            # Validate same node type constraint
            if source.node_type != target.node_type:
                raise ValueError(
                    f"Nodes can only be linked to nodes of the same type. "
                    f"Source is {source.node_type}, target is {target.node_type}"
                )
            
            # Check for duplicate links (excluding current link)
            predicate = link_data.get('predicate', link.predicate)
            existing = self.db.query(NodeLink).filter(
                NodeLink.source_node_id == source_id,
                NodeLink.target_node_id == target_id,
                NodeLink.predicate == predicate,
                NodeLink.id != link_id
            ).first()
            
            if existing:
                raise ValueError(f"Link already exists: {source_id} -> {target_id} ({predicate})")
        
        # Store old data for event
        old_link_data = self._node_link_to_dict(link)
        
        # Update fields
        if 'source_node_id' in link_data:
            link.source_node_id = link_data['source_node_id']
        
        if 'target_node_id' in link_data:
            link.target_node_id = link_data['target_node_id']
        
        if 'predicate' in link_data:
            link.predicate = link_data['predicate']
        
        if 'predicate_id' in link_data:
            link.predicate_id = link_data['predicate_id']
        
        try:
            self.db.commit()
            self.db.refresh(link)
            
            logger.info(f"Successfully updated node link: {link.id}")
            
            # Fire node link updated event
            new_link_data = self._node_link_to_dict(link)
            self.event_handler.fire_node_updated_event('node_link', old_link_data, new_link_data)
            
            return link
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update node link: {e}")
            raise ValueError(f"Failed to update node link: {e}")
    
    def delete_link(self, link_id: str) -> bool:
        """
        Delete a node link.
        
        Args:
            link_id: ID of the link to delete
            
        Returns:
            True if deleted successfully
            
        Raises:
            ValueError: If link not found
        """
        logger.info(f"Deleting node link: {link_id}")
        
        link = self.db.query(NodeLink).filter(NodeLink.id == link_id).first()
        if not link:
            raise ValueError(f"Node link not found: {link_id}")
        
        # Store link data for event before deletion
        link_data = self._node_link_to_dict(link)
        
        try:
            self.db.delete(link)
            self.db.commit()
            
            logger.info(f"Successfully deleted node link: {link_id}")
            
            # Fire node link deleted event
            self.event_handler.fire_node_deleted_event('node_link', link_data)
            
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete node link: {e}")
            raise ValueError(f"Failed to delete node link: {e}")
    
    def get_link(self, link_id: str) -> Optional[NodeLink]:
        """
        Get a node link by ID.
        
        Args:
            link_id: ID of the link to retrieve
            
        Returns:
            NodeLink instance or None if not found
        """
        return self.db.query(NodeLink).filter(NodeLink.id == link_id).first()
    
    def list_links(self, source_node_id: Optional[str] = None,
                   target_node_id: Optional[str] = None,
                   predicate: Optional[str] = None,
                   skip: int = 0, limit: int = 50) -> List[NodeLink]:
        """
        List node links with optional filtering.
        
        Args:
            source_node_id: Optional source node ID to filter by
            target_node_id: Optional target node ID to filter by
            predicate: Optional predicate to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of NodeLink instances
        """
        query = self.db.query(NodeLink)
        
        if source_node_id:
            query = query.filter(NodeLink.source_node_id == source_node_id)
        
        if target_node_id:
            query = query.filter(NodeLink.target_node_id == target_node_id)
        
        if predicate:
            query = query.filter(NodeLink.predicate == predicate)
        
        return query.order_by(NodeLink.created_at.desc()).offset(skip).limit(limit).all()
    
    def count_links(self, source_node_id: Optional[str] = None,
                    target_node_id: Optional[str] = None,
                    predicate: Optional[str] = None) -> int:
        """
        Count node links with optional filtering.
        
        Args:
            source_node_id: Optional source node ID to filter by
            target_node_id: Optional target node ID to filter by
            predicate: Optional predicate to filter by
            
        Returns:
            Count of matching links
        """
        query = self.db.query(NodeLink)
        
        if source_node_id:
            query = query.filter(NodeLink.source_node_id == source_node_id)
        
        if target_node_id:
            query = query.filter(NodeLink.target_node_id == target_node_id)
        
        if predicate:
            query = query.filter(NodeLink.predicate == predicate)
        
        return query.count()
    
    def get_node_links(self, node_id: str, direction: str = "both") -> List[NodeLink]:
        """
        Get all links for a specific node.
        
        Args:
            node_id: Node ID to get links for
            direction: Direction of links to get ("outgoing", "incoming", "both")
            
        Returns:
            List of NodeLink instances
            
        Raises:
            ValueError: If direction is invalid
        """
        if direction not in ["outgoing", "incoming", "both"]:
            raise ValueError("direction must be 'outgoing', 'incoming', or 'both'")
        
        query = self.db.query(NodeLink)
        
        if direction == "outgoing":
            query = query.filter(NodeLink.source_node_id == node_id)
        elif direction == "incoming":
            query = query.filter(NodeLink.target_node_id == node_id)
        else:  # both
            query = query.filter(
                (NodeLink.source_node_id == node_id) | 
                (NodeLink.target_node_id == node_id)
            )
        
        return query.order_by(NodeLink.created_at.desc()).all()
    
    def get_linked_nodes(self, node_id: str, direction: str = "both", 
                        node_type: Optional[NodeType] = None) -> List[Node]:
        """
        Get all nodes linked to a specific node.
        
        Args:
            node_id: Node ID to get linked nodes for
            direction: Direction of links ("outgoing", "incoming", "both")
            node_type: Optional node type to filter results by
            
        Returns:
            List of linked Node instances
            
        Raises:
            ValueError: If direction is invalid
        """
        if direction not in ["outgoing", "incoming", "both"]:
            raise ValueError("direction must be 'outgoing', 'incoming', or 'both'")
        
        # Get the links first
        links = self.get_node_links(node_id, direction)
        
        # Extract linked node IDs
        linked_node_ids = set()
        for link in links:
            if direction == "outgoing":
                linked_node_ids.add(link.target_node_id)
            elif direction == "incoming":
                linked_node_ids.add(link.source_node_id)
            else:  # both
                if link.source_node_id != node_id:
                    linked_node_ids.add(link.source_node_id)
                if link.target_node_id != node_id:
                    linked_node_ids.add(link.target_node_id)
        
        # Get the actual nodes
        query = self.db.query(Node).filter(Node.id.in_(linked_node_ids))
        
        if node_type:
            query = query.filter(Node.node_type == node_type)
        
        return query.order_by(Node.title).all()
    
    def validate_link_compatibility(self, source_node_id: str, target_node_id: str) -> bool:
        """
        Validate if two nodes can be linked together.
        
        Args:
            source_node_id: Source node ID
            target_node_id: Target node ID
            
        Returns:
            True if nodes can be linked, False otherwise
        """
        if source_node_id == target_node_id:
            return False
        
        # Get nodes
        source = self.db.query(Node).filter(Node.id == source_node_id).first()
        target = self.db.query(Node).filter(Node.id == target_node_id).first()
        
        if not source or not target:
            return False
        
        # Must be same node type
        return source.node_type == target.node_type
    
    def get_link_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about node links in the system.
        
        Returns:
            Dictionary containing link statistics
        """
        # Total links
        total_links = self.db.query(NodeLink).count()
        
        # Links by predicate
        predicate_stats = {}
        predicates = self.db.query(NodeLink.predicate).distinct().all()
        for (predicate,) in predicates:
            count = self.db.query(NodeLink).filter(NodeLink.predicate == predicate).count()
            predicate_stats[predicate] = count
        
        # Links by node type (source)
        node_type_stats = {}
        for node_type in NodeType:
            count = (self.db.query(NodeLink)
                    .join(Node, NodeLink.source_node_id == Node.id)
                    .filter(Node.node_type == node_type)
                    .count())
            node_type_stats[node_type.value] = count
        
        return {
            "total_links": total_links,
            "links_by_predicate": predicate_stats,
            "links_by_source_node_type": node_type_stats
        }

    def _node_link_to_dict(self, link: NodeLink) -> Dict[str, Any]:
        """Convert a NodeLink instance to a dictionary"""
        return {
            'id': link.id,
            'source_node_id': link.source_node_id,
            'target_node_id': link.target_node_id,
            'predicate': link.predicate,
            'predicate_id': link.predicate_id,
            'created_at': link.created_at.isoformat() if link.created_at else None
        }
