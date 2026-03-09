"""
DiffGenerator Service - Generate structured diffs between entity versions

This service provides comprehensive diff generation capabilities using DeepDiff for JSON
comparison, enabling detailed analysis of changes between entity versions.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from deepdiff import DeepDiff
from datetime import datetime

from services.version_manager import EntityVersion, VersionManager
from services.working_tree_manager import WorkingTreeManager
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class EntityDiff:
    """Data class representing a diff between two entity versions."""

    entity_type: str
    entity_id: str
    before_version: Optional[EntityVersion]
    after_version: EntityVersion
    changes: Dict[str, Any]
    summary: Dict[str, int]
    generated_at: datetime

    def has_changes(self) -> bool:
        """Check if there are any changes in this diff."""
        return bool(self.changes)

    def get_change_count(self) -> int:
        """Get total number of changes."""
        return sum(self.summary.values())


@dataclass
class DiffSummary:
    """Summary of changes in a diff."""

    added_items: int = 0
    removed_items: int = 0
    modified_items: int = 0
    type_changes: int = 0
    moved_items: int = 0
    total_changes: int = 0


class DiffGenerator:
    """Generates structured diffs between entity versions using DeepDiff."""

    def __init__(
        self, version_manager: VersionManager, working_tree_manager: WorkingTreeManager
    ):
        """
        Initialize the DiffGenerator.

        Args:
            version_manager: VersionManager instance for version operations
            working_tree_manager: WorkingTreeManager instance for working tree operations
        """
        self.version_manager = version_manager
        self.working_tree_manager = working_tree_manager
        logger.info("DiffGenerator initialized")

    def generate_diff(
        self,
        before_content: Dict[str, Any],
        after_content: Dict[str, Any],
        ignore_keys: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate structured diff using DeepDiff.

        Args:
            before_content: Content before changes
            after_content: Content after changes
            ignore_keys: Optional list of keys to ignore in comparison

        Returns:
            Dictionary containing DeepDiff results
        """
        logger.debug("Generating diff between contents")

        # Default keys to ignore (timestamps, IDs that change automatically)
        default_ignore_keys = {"last_modified", "created_at", "version"}
        if ignore_keys:
            ignore_keys.extend(default_ignore_keys)
        else:
            ignore_keys = list(default_ignore_keys)

        try:
            # Configure DeepDiff with appropriate settings
            diff = DeepDiff(
                before_content,
                after_content,
                ignore_order=True,
                exclude_paths=ignore_keys,
                verbose_level=2,
            )

            # Convert to regular dict for JSON serialization
            diff_dict = dict(diff)

            logger.debug(f"Generated diff with {len(diff_dict)} change categories")
            return diff_dict

        except Exception as e:
            logger.error(f"Failed to generate diff: {e}")
            return {"error": f"Diff generation failed: {str(e)}"}

    def generate_version_diff(
        self,
        entity_type: str,
        entity_id: str,
        before_version_number: Optional[int],
        after_version_number: int,
    ) -> EntityDiff:
        """
        Generate diff between two specific versions of an entity.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            before_version_number: Version number to compare from (None for creation)
            after_version_number: Version number to compare to

        Returns:
            EntityDiff instance

        Raises:
            ValueError: If versions don't exist
        """
        logger.info(
            f"Generating version diff for {entity_type}:{entity_id} "
            f"({before_version_number} -> {after_version_number})"
        )

        # Get the after version
        after_version = self.version_manager.get_version_by_number(
            entity_type, entity_id, after_version_number
        )
        if not after_version:
            raise ValueError(f"After version {after_version_number} not found")

        # Get the before version (if specified)
        before_version = None
        before_content = {}

        if before_version_number is not None:
            before_version = self.version_manager.get_version_by_number(
                entity_type, entity_id, before_version_number
            )
            if not before_version:
                raise ValueError(f"Before version {before_version_number} not found")
            before_content = before_version.content

        # Generate diff
        changes = self.generate_diff(before_content, after_version.content)
        summary = self._analyze_diff_summary(changes)

        return EntityDiff(
            entity_type=entity_type,
            entity_id=entity_id,
            before_version=before_version,
            after_version=after_version,
            changes=changes,
            summary=summary,
            generated_at=datetime.utcnow(),
        )

    def generate_working_diff(self, entity_type: str, entity_id: str) -> EntityDiff:
        """
        Generate diff between working and canonical versions using working tree.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity

        Returns:
            EntityDiff instance

        Raises:
            ValueError: If entity not in working tree or versions don't exist
        """
        logger.info(f"Generating working diff for {entity_type}:{entity_id}")

        # Get working tree entry
        working_entry = self.working_tree_manager.get_working_tree_entry(
            entity_type, entity_id
        )
        if not working_entry:
            raise ValueError(
                f"Entity {entity_type}:{entity_id} not found in working tree"
            )

        # Get canonical version content
        canonical_version = self._get_version_by_id(working_entry.canonical_version_id)
        if not canonical_version:
            raise ValueError(
                f"Canonical version {working_entry.canonical_version_id} not found"
            )

        # Get current working version content
        current_version = self._get_version_by_id(working_entry.current_version_id)
        if not current_version:
            raise ValueError(
                f"Current version {working_entry.current_version_id} not found"
            )

        # Generate diff
        changes = self.generate_diff(canonical_version.content, current_version.content)
        summary = self._analyze_diff_summary(changes)

        return EntityDiff(
            entity_type=entity_type,
            entity_id=entity_id,
            before_version=canonical_version,
            after_version=current_version,
            changes=changes,
            summary=summary,
            generated_at=datetime.utcnow(),
        )

    def generate_all_working_diffs(self) -> List[EntityDiff]:
        """
        Generate diffs for all entities with working changes.

        Returns:
            List of EntityDiff instances for entities with changes
        """
        logger.info("Generating diffs for all entities with working changes")

        working_changes = self.working_tree_manager.get_working_changes()
        diffs = []

        for entry in working_changes:
            try:
                diff = self.generate_working_diff(entry.entity_type, entry.entity_id)
                if diff.has_changes():
                    diffs.append(diff)
            except Exception as e:
                logger.error(
                    f"Failed to generate diff for {entry.entity_type}:{entry.entity_id}: {e}"
                )
                continue

        logger.info(f"Generated {len(diffs)} working diffs")
        return diffs

    def generate_commit_preview(self) -> List[EntityDiff]:
        """
        Generate preview of what would be committed (staged changes).

        Returns:
            List of EntityDiff instances for staged entities
        """
        logger.info("Generating commit preview for staged changes")

        staged_entities = self.working_tree_manager.get_staged_entities()
        diffs = []

        for entry in staged_entities:
            try:
                diff = self.generate_working_diff(entry.entity_type, entry.entity_id)
                if diff.has_changes():
                    diffs.append(diff)
            except Exception as e:
                logger.error(
                    f"Failed to generate commit preview for {entry.entity_type}:{entry.entity_id}: {e}"
                )
                continue

        logger.info(f"Generated commit preview with {len(diffs)} diffs")
        return diffs

    def get_change_summary(self, entity_type: str, entity_id: str) -> DiffSummary:
        """
        Get a summary of changes for an entity.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity

        Returns:
            DiffSummary with change counts
        """
        try:
            diff = self.generate_working_diff(entity_type, entity_id)
            return self._create_diff_summary(diff.summary)
        except Exception as e:
            logger.error(
                f"Failed to get change summary for {entity_type}:{entity_id}: {e}"
            )
            return DiffSummary()

    def format_diff_for_display(
        self, diff: EntityDiff, format_type: str = "summary"
    ) -> Dict[str, Any]:
        """
        Format diff for human-readable display.

        Args:
            diff: EntityDiff to format
            format_type: Format type ("summary", "detailed", "json")

        Returns:
            Formatted diff data
        """
        if format_type == "summary":
            return self._format_diff_summary(diff)
        elif format_type == "detailed":
            return self._format_diff_detailed(diff)
        elif format_type == "json":
            return {
                "entity_type": diff.entity_type,
                "entity_id": diff.entity_id,
                "before_version": (
                    diff.before_version.version_number if diff.before_version else None
                ),
                "after_version": diff.after_version.version_number,
                "changes": diff.changes,
                "summary": diff.summary,
                "generated_at": diff.generated_at.isoformat(),
            }
        else:
            raise ValueError(f"Unsupported format type: {format_type}")

    def _get_version_by_id(self, version_id: str) -> Optional[EntityVersion]:
        """Get version by ID from the database."""
        from sqlalchemy import text

        try:
            result = self.version_manager.db.execute(
                text("""
                SELECT id, entity_type, entity_id, version_number, content, state,
                       parent_version_id, changeset_id, author_id, created_at, metadata
                FROM entity_versions WHERE id = :version_id
            """),
                {"version_id": version_id},
            ).fetchone()

            if result:
                return self.version_manager._row_to_entity_version(result)
            return None
        except Exception as e:
            logger.error(f"Failed to get version by ID {version_id}: {e}")
            return None

    def _analyze_diff_summary(self, changes: Dict[str, Any]) -> Dict[str, int]:
        """Analyze diff changes and create summary counts."""
        summary = {
            "values_changed": 0,
            "dictionary_item_added": 0,
            "dictionary_item_removed": 0,
            "type_changes": 0,
            "iterable_item_added": 0,
            "iterable_item_removed": 0,
        }

        for change_type, change_data in changes.items():
            if isinstance(change_data, dict):
                summary[change_type] = len(change_data)
            elif isinstance(change_data, list):
                summary[change_type] = len(change_data)
            else:
                summary[change_type] = 1

        return summary

    def _create_diff_summary(self, summary_dict: Dict[str, int]) -> DiffSummary:
        """Create DiffSummary from summary dictionary."""
        added = summary_dict.get("dictionary_item_added", 0) + summary_dict.get(
            "iterable_item_added", 0
        )
        removed = summary_dict.get("dictionary_item_removed", 0) + summary_dict.get(
            "iterable_item_removed", 0
        )
        modified = summary_dict.get("values_changed", 0)
        type_changes = summary_dict.get("type_changes", 0)

        return DiffSummary(
            added_items=added,
            removed_items=removed,
            modified_items=modified,
            type_changes=type_changes,
            moved_items=0,  # DeepDiff doesn't track moves separately by default
            total_changes=added + removed + modified + type_changes,
        )

    def _format_diff_summary(self, diff: EntityDiff) -> Dict[str, Any]:
        """Format diff as a summary."""
        return {
            "entity": f"{diff.entity_type}:{diff.entity_id}",
            "versions": {
                "before": (
                    diff.before_version.version_number if diff.before_version else None
                ),
                "after": diff.after_version.version_number,
            },
            "summary": self._create_diff_summary(diff.summary).__dict__,
            "has_changes": diff.has_changes(),
            "generated_at": diff.generated_at.isoformat(),
        }

    def _format_diff_detailed(self, diff: EntityDiff) -> Dict[str, Any]:
        """Format diff with detailed change information."""
        formatted = self._format_diff_summary(diff)
        formatted["changes"] = diff.changes
        return formatted
