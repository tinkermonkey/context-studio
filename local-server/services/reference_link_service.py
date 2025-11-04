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
from services.exceptions import NotFoundError, ReferenceNotFoundError, ValidationError

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
            NotFoundError: If node not found
            ReferenceNotFoundError: If reference doesn't exist in reference.db
            ValidationError: If validation fails
        """
        logger.info(f"Adding {len(links)} reference links to node {node_id}")

        # Get the node
        node = self.db.query(StructureNode).filter(StructureNode.id == node_id).first()
        if not node:
            raise NotFoundError("StructureNode", node_id)

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

        # Update node (increment version after validation, before commit)
        node.reference_links = links_json

        try:
            node.version = node.version + 1
            self.db.commit()
            logger.info(
                f"Successfully added {new_links_added} new reference links to node {node_id} "
                f"(total: {len(existing_links)})"
            )
            return existing_links
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to add reference links to node {node_id}: {e}")
            raise ValidationError(f"Failed to add reference links: {e}")

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
            NotFoundError: If node not found
            ValidationError: If update fails
        """
        logger.info(f"Removing {len(links)} reference links from node {node_id}")

        # Get the node
        node = self.db.query(StructureNode).filter(StructureNode.id == node_id).first()
        if not node:
            raise NotFoundError("StructureNode", node_id)

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

        # Update node (increment version after validation, before commit)
        node.reference_links = links_json

        try:
            node.version = node.version + 1
            self.db.commit()
            logger.info(
                f"Successfully removed {removed_count} reference links from node {node_id} "
                f"(remaining: {len(remaining_links)})"
            )
            return remaining_links
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to remove reference links from node {node_id}: {e}")
            raise ValidationError(f"Failed to remove reference links: {e}")

    def get_reference_links(self, node_id: str) -> List[ReferenceLink]:
        """
        Get all reference links for a structure node.

        Args:
            node_id: ID of the structure node

        Returns:
            List of ReferenceLink instances (empty list if none)

        Raises:
            NotFoundError: If node not found
        """
        # Get the node
        node = self.db.query(StructureNode).filter(StructureNode.id == node_id).first()
        if not node:
            raise NotFoundError("StructureNode", node_id)

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
                        f"Failed to parse reference link for node {node_id}: {e}. "
                        f"Skipping invalid entry: {link_dict}"
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
            ReferenceNotFoundError: If reference doesn't exist in reference.db
            ValidationError: If validation fails
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
            ReferenceNotFoundError: If reference doesn't exist in reference.db
            ValidationError: If validation fails
        """
        try:
            # Get reference manager and check if node exists
            ref_manager = get_reference_manager()
            ref_node = ref_manager.get_reference_node_by_source(source, external_id)

            if not ref_node:
                raise ReferenceNotFoundError(source, external_id)

            logger.debug(
                f"Validated reference link: source='{source}', external_id='{external_id}'"
            )

        except ReferenceNotFoundError:
            # Re-raise ReferenceNotFoundError as-is
            raise
        except Exception as e:
            # Wrap other exceptions in ValidationError with context
            logger.error(f"Error validating reference link: {e}")
            raise ValidationError(f"Failed to validate reference link: {e}")

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

        # Query nodes using SQLite json_extract for efficiency
        # This filters at the database level instead of fetching all nodes
        from sqlalchemy import text

        query = self.db.query(StructureNode).filter(
            StructureNode.reference_links.isnot(None),
            StructureNode.reference_links != "",
            StructureNode.reference_links != "[]",
            text(
                "EXISTS ("
                "  SELECT 1 FROM json_each(reference_links) "
                "  WHERE json_extract(value, '$.source') = :source "
                "  AND json_extract(value, '$.external_id') = :external_id"
                ")"
            )
        ).params(source=source, external_id=external_id)

        if limit:
            query = query.limit(limit)

        matching_nodes = query.all()

        logger.debug(
            f"Found {len(matching_nodes)} nodes with reference link source='{source}', "
            f"external_id='{external_id}'"
        )

        return matching_nodes

    def validate_node_reference_links(
        self, node_id: str, check_existence: bool = True
    ) -> dict:
        """
        Validate all reference links for a specific structure node.

        Args:
            node_id: ID of the structure node
            check_existence: If True, validates each link exists in reference.db

        Returns:
            Dictionary containing validation results:
            {
                "node_id": str,
                "total_links": int,
                "valid_links": int,
                "orphaned_links": List[dict],  # Links that don't exist in reference.db
                "malformed_links": List[dict]  # Links with parsing errors
            }

        Raises:
            NotFoundError: If node not found
        """
        logger.info(f"Validating reference links for node {node_id}")

        result = {
            "node_id": node_id,
            "total_links": 0,
            "valid_links": 0,
            "orphaned_links": [],  # Links that don't exist in reference.db
            "malformed_links": []
        }

        # Get the node
        node = self.db.query(StructureNode).filter(StructureNode.id == node_id).first()
        if not node:
            logger.error(f"StructureNode not found: {node_id}")
            raise NotFoundError("StructureNode", node_id)

        try:

            # Parse reference links with error handling
            if not node.reference_links:
                logger.debug(f"Node {node_id} has no reference links")
                return result

            try:
                links_data = json.loads(node.reference_links)
                if not isinstance(links_data, list):
                    logger.warning(f"reference_links for node {node_id} is not an array")
                    result["error"] = "reference_links field is not an array"
                    return result

                result["total_links"] = len(links_data)

                for link_dict in links_data:
                    try:
                        # Try to parse link
                        link = ReferenceLink(**link_dict)

                        # If check_existence is True, validate against reference.db
                        if check_existence:
                            try:
                                ref_manager = get_reference_manager()
                                ref_node = ref_manager.get_reference_node_by_source(
                                    link.source, link.external_id
                                )

                                if ref_node:
                                    result["valid_links"] += 1
                                else:
                                    # Orphaned link
                                    orphaned_entry = {
                                        "source": link.source,
                                        "external_id": link.external_id,
                                        "reason": "Reference not found in reference.db"
                                    }
                                    result["orphaned_links"].append(orphaned_entry)

                            except Exception as e:
                                # Error checking reference.db (e.g., database unavailable)
                                orphaned_entry = {
                                    "source": link.source,
                                    "external_id": link.external_id,
                                    "reason": f"Validation error: {str(e)}"
                                }
                                result["orphaned_links"].append(orphaned_entry)
                                logger.warning(
                                    f"Error validating reference link for node {node_id}: {e}"
                                )
                        else:
                            # Just count as valid if we're not checking existence
                            result["valid_links"] += 1

                    except Exception as e:
                        # Malformed link data
                        malformed_entry = {
                            "data": link_dict,
                            "reason": f"Parse error: {str(e)}"
                        }
                        result["malformed_links"].append(malformed_entry)
                        logger.warning(
                            f"Failed to parse reference link for node {node_id}: {e}"
                        )

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse reference_links JSON for node {node_id}: {e}")
                result["error"] = f"JSON decode error: {str(e)}"
                return result

        except Exception as e:
            logger.error(f"Unexpected error validating reference links for node {node_id}: {e}")
            result["error"] = f"Unexpected error: {str(e)}"

        logger.info(
            f"Validation complete for node {node_id}: "
            f"{result['valid_links']}/{result['total_links']} valid, "
            f"{len(result['orphaned_links'])} orphaned, "
            f"{len(result['malformed_links'])} malformed"
        )

        return result

    def validate_all_reference_links(
        self, check_existence: bool = True, limit: Optional[int] = None
    ) -> dict:
        """
        Validate reference links across all structure nodes.

        Args:
            check_existence: If True, validates each link exists in reference.db
            limit: Optional limit on number of nodes to validate

        Returns:
            Dictionary containing aggregate validation results:
            {
                "total_nodes_checked": int,
                "nodes_with_links": int,
                "total_links": int,
                "valid_links": int,
                "orphaned_links": int,
                "malformed_links": int,
                "problematic_nodes": List[dict],  # Nodes with orphaned/malformed links
                "reference_db_available": bool
            }
        """
        logger.info(f"Starting bulk validation of reference links (limit={limit})")

        result = {
            "total_nodes_checked": 0,
            "nodes_with_links": 0,
            "total_links": 0,
            "valid_links": 0,
            "orphaned_links": 0,
            "malformed_links": 0,
            "problematic_nodes": [],
            "reference_db_available": True
        }

        try:
            # Check if reference.db is available
            if check_existence:
                try:
                    ref_manager = get_reference_manager()
                    # Try a simple operation to check if reference.db is accessible
                    # This is a lightweight check
                    result["reference_db_available"] = ref_manager is not None
                except Exception as e:
                    logger.warning(f"reference.db appears unavailable: {e}")
                    result["reference_db_available"] = False
                    # Continue with validation but without checking existence
                    check_existence = False

            # Query all nodes that have reference_links
            query = self.db.query(StructureNode).filter(
                StructureNode.reference_links.isnot(None),
                StructureNode.reference_links != "",
                StructureNode.reference_links != "[]"
            )

            if limit:
                query = query.limit(limit)

            nodes_with_links = query.all()
            result["total_nodes_checked"] = len(nodes_with_links)
            result["nodes_with_links"] = len(nodes_with_links)

            logger.info(f"Found {len(nodes_with_links)} nodes with reference links")

            # Validate each node
            for node in nodes_with_links:
                node_result = self.validate_node_reference_links(
                    str(node.id), check_existence=check_existence
                )

                result["total_links"] += node_result.get("total_links", 0)
                result["valid_links"] += node_result.get("valid_links", 0)
                result["orphaned_links"] += len(node_result.get("orphaned_links", []))
                result["malformed_links"] += len(node_result.get("malformed_links", []))

                # Track problematic nodes
                if node_result.get("orphaned_links") or node_result.get("malformed_links"):
                    problematic_node = {
                        "node_id": str(node.id),
                        "node_title": node.title,
                        "node_type": node.node_type,
                        "total_links": node_result.get("total_links", 0),
                        "valid_links": node_result.get("valid_links", 0),
                        "orphaned_links": node_result.get("orphaned_links", []),
                        "malformed_links": node_result.get("malformed_links", [])
                    }
                    result["problematic_nodes"].append(problematic_node)

            logger.info(
                f"Bulk validation complete: {result['total_nodes_checked']} nodes checked, "
                f"{result['valid_links']}/{result['total_links']} links valid, "
                f"{result['orphaned_links']} orphaned, {result['malformed_links']} malformed"
            )

        except Exception as e:
            logger.error(f"Error during bulk validation: {e}", exc_info=True)
            result["error"] = f"Bulk validation error: {str(e)}"

        return result
