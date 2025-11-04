"""
Service for managing reference data links on structure nodes.

This service handles JSON serialization, validation, and business logic for
reference links that connect structure nodes to external knowledge sources.
"""

import json
from typing import List, Optional
from sqlalchemy.orm import Session

from database.models import StructureNode
from api.models.structure_nodes import ReferenceLink
from reference_db.manager import get_reference_manager
from utils.logger import get_logger

logger = get_logger(__name__)


class ReferenceLinkService:
    """Service for managing reference links on structure nodes."""

    def __init__(self, db: Session):
        """
        Initialize the ReferenceLinkService.

        Args:
            db: SQLAlchemy database session for local.db
        """
        self.db = db

    def add_reference_links(
        self, node_id: str, links: List[ReferenceLink]
    ) -> List[ReferenceLink]:
        """
        Add reference links to a structure node.

        Validates that each reference exists in reference.db before adding.
        Prevents duplicate links from being added.

        Args:
            node_id: ID of the structure node
            links: List of ReferenceLink instances to add

        Returns:
            List of all reference links after addition (including pre-existing)

        Raises:
            ValueError: If node not found, reference doesn't exist, or validation fails
        """
        logger.info(f"Adding {len(links)} reference links to node {node_id}")

        # Get the node
        node = self.db.query(StructureNode).filter(StructureNode.id == node_id).first()
        if not node:
            raise ValueError(f"StructureNode not found: {node_id}")

        # Validate all links exist in reference.db before proceeding
        for link in links:
            self._validate_reference_link(link.source, link.external_id)

        # Get existing links
        existing_links = self.get_reference_links(node_id)

        # Create a set of existing link tuples for efficient lookup
        existing_set = {(link.source, link.external_id) for link in existing_links}

        # Add only new links (avoid duplicates)
        new_links_added = 0
        for link in links:
            link_tuple = (link.source, link.external_id)
            if link_tuple not in existing_set:
                existing_links.append(link)
                existing_set.add(link_tuple)
                new_links_added += 1

        # Serialize to JSON
        links_json = json.dumps([link.model_dump() for link in existing_links])

        # Update node
        node.reference_links = links_json
        node.version = node.version + 1

        try:
            self.db.commit()
            logger.info(
                f"Successfully added {new_links_added} new reference links to node {node_id} "
                f"(total: {len(existing_links)})"
            )
            return existing_links
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to add reference links to node {node_id}: {e}")
            raise ValueError(f"Failed to add reference links: {e}")

    def remove_reference_links(
        self, node_id: str, links: List[ReferenceLink]
    ) -> List[ReferenceLink]:
        """
        Remove reference links from a structure node.

        Args:
            node_id: ID of the structure node
            links: List of ReferenceLink instances to remove

        Returns:
            List of remaining reference links after removal

        Raises:
            ValueError: If node not found or update fails
        """
        logger.info(f"Removing {len(links)} reference links from node {node_id}")

        # Get the node
        node = self.db.query(StructureNode).filter(StructureNode.id == node_id).first()
        if not node:
            raise ValueError(f"StructureNode not found: {node_id}")

        # Get existing links
        existing_links = self.get_reference_links(node_id)

        # Create set of links to remove
        remove_set = {(link.source, link.external_id) for link in links}

        # Filter out links to remove
        remaining_links = [
            link
            for link in existing_links
            if (link.source, link.external_id) not in remove_set
        ]

        removed_count = len(existing_links) - len(remaining_links)

        # Serialize to JSON (empty array if no links remain)
        links_json = json.dumps([link.model_dump() for link in remaining_links])

        # Update node
        node.reference_links = links_json
        node.version = node.version + 1

        try:
            self.db.commit()
            logger.info(
                f"Successfully removed {removed_count} reference links from node {node_id} "
                f"(remaining: {len(remaining_links)})"
            )
            return remaining_links
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to remove reference links from node {node_id}: {e}")
            raise ValueError(f"Failed to remove reference links: {e}")

    def get_reference_links(self, node_id: str) -> List[ReferenceLink]:
        """
        Get all reference links for a structure node.

        Args:
            node_id: ID of the structure node

        Returns:
            List of ReferenceLink instances (empty list if none)

        Raises:
            ValueError: If node not found or JSON parsing fails
        """
        # Get the node
        node = self.db.query(StructureNode).filter(StructureNode.id == node_id).first()
        if not node:
            raise ValueError(f"StructureNode not found: {node_id}")

        # Parse JSON field (handle null, empty string, and malformed JSON)
        if not node.reference_links:
            return []

        try:
            links_data = json.loads(node.reference_links)

            # Handle case where field is not an array
            if not isinstance(links_data, list):
                logger.warning(
                    f"reference_links field for node {node_id} is not an array, returning empty list"
                )
                return []

            # Parse each link into a ReferenceLink model
            links = []
            for link_dict in links_data:
                try:
                    links.append(ReferenceLink(**link_dict))
                except Exception as e:
                    logger.warning(
                        f"Failed to parse reference link for node {node_id}: {e}. Skipping."
                    )
                    continue

            return links

        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse reference_links JSON for node {node_id}: {e}. "
                f"Returning empty list."
            )
            return []

    def validate_reference_link(self, source: str, external_id: str) -> bool:
        """
        Validate that a reference link exists in reference.db.

        Args:
            source: Source identifier (e.g., 'schema.org')
            external_id: Source-specific identifier

        Returns:
            True if reference exists

        Raises:
            ValueError: If reference doesn't exist in reference.db
        """
        self._validate_reference_link(source, external_id)
        return True

    def _validate_reference_link(self, source: str, external_id: str):
        """
        Internal method to validate reference link existence.

        Args:
            source: Source identifier
            external_id: Source-specific identifier

        Raises:
            ValueError: If reference doesn't exist
        """
        try:
            # Get reference manager and check if node exists
            ref_manager = get_reference_manager()
            ref_node = ref_manager.get_reference_node_by_source(source, external_id)

            if not ref_node:
                raise ValueError(
                    f"Reference not found in reference.db: source='{source}', "
                    f"external_id='{external_id}'"
                )

            logger.debug(
                f"Validated reference link: source='{source}', external_id='{external_id}'"
            )

        except Exception as e:
            # Re-raise ValueError as-is, wrap other exceptions
            if isinstance(e, ValueError):
                raise
            logger.error(f"Error validating reference link: {e}")
            raise ValueError(f"Failed to validate reference link: {e}")

    def get_nodes_with_reference_link(
        self, source: str, external_id: str, limit: Optional[int] = None
    ) -> List[StructureNode]:
        """
        Find all structure nodes that link to a specific reference.

        Args:
            source: Source identifier
            external_id: Source-specific identifier
            limit: Optional limit on number of results

        Returns:
            List of StructureNode instances that reference the given external node
        """
        logger.debug(
            f"Finding nodes with reference link: source='{source}', external_id='{external_id}'"
        )

        # Query nodes where reference_links JSON contains the reference
        # Using SQLite JSON functions for efficient querying
        query = self.db.query(StructureNode).filter(
            StructureNode.reference_links.isnot(None),
            StructureNode.reference_links != "",
            StructureNode.reference_links != "[]",
        )

        nodes = query.all()

        # Filter in Python (more reliable than SQLite JSON queries which can be finicky)
        matching_nodes = []
        for node in nodes:
            links = self.get_reference_links(str(node.id))
            if any(link.source == source and link.external_id == external_id for link in links):
                matching_nodes.append(node)
                if limit and len(matching_nodes) >= limit:
                    break

        logger.debug(
            f"Found {len(matching_nodes)} nodes with reference link source='{source}', "
            f"external_id='{external_id}'"
        )

        return matching_nodes
