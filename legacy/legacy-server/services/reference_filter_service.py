# mypy: ignore-errors
"""
Reference Link Filtering Service

This service handles filtering of reference links based on predicate relevance mappings.
When predicates are marked as relevant/irrelevant in the global predicates table,
this service applies those filters to reference query results.
"""

import json
import logging
from typing import List, Dict, Any, Optional, Set, Tuple
from sqlalchemy.orm import Session

from database.models import Predicate
from reference_db.models import ReferenceLink
from reference_db.manager import ReferenceManager

logger = logging.getLogger(__name__)


class ReferenceFilterService:
    """
    Service for filtering reference links based on predicate relevance.

    This service:
    - Checks global predicates for is_relevant flags
    - Maps external predicates to global predicates via mapping field
    - Filters ReferenceLinks based on relevance flags
    - Calculates statistics for filtered results
    """

    def __init__(self, local_db_session: Session, reference_manager: ReferenceManager):
        """
        Initialize the reference filter service.

        Args:
            local_db_session: Session for local database (predicates table)
            reference_manager: Manager for reference database (external predicates, links)
        """
        self.local_session = local_db_session
        self.ref_manager = reference_manager
        self._relevant_cache: Optional[Set[str]] = None
        self._irrelevant_cache: Optional[Set[str]] = None

    def _get_all_predicate_mappings_with_relevance(self) -> Dict[str, Any]:
        """
        Get all predicate mappings with relevance flags from the global predicates table.

        Returns:
            Dict mapping predicate IDs to their relevance info and external mappings:
            {
                "pred_id": {
                    "is_relevant": bool | None,
                    "external_predicates": [
                        {"source": "schema.org", "external_id": "subClassOf"},
                        ...
                    ]
                }
            }
        """
        try:
            predicates = self.local_session.query(Predicate).all()
        except Exception as e:
            logger.error(f"Database error fetching predicates: {e}", exc_info=True)
            return {}

        mappings = {}
        for pred in predicates:
            pred_info = {"is_relevant": pred.is_relevant, "external_predicates": []}

            # Parse mapping JSON if present
            mapping_str = None
            if pred.mapping is not None and pred.mapping:
                # Ensure mapping is a string and strip whitespace
                if isinstance(pred.mapping, str):
                    mapping_str = pred.mapping.strip()
                # Skip if mapping is empty after stripping
                if not mapping_str:
                    mapping_str = None

            if mapping_str:
                try:
                    mapping_data = json.loads(mapping_str)
                    # Extract reference_predicates from the mapping structure (ADR-002 schema)
                    if (
                        isinstance(mapping_data, dict)
                        and "reference_predicates" in mapping_data
                    ):
                        # New schema format: extract reference_predicates as external_predicates
                        # Map from the new schema format to the format expected by filter logic
                        ref_preds = mapping_data.get("reference_predicates", [])
                        # Convert to "source:source_id" format for compatibility
                        for ref_pred in ref_preds:
                            pred_info["external_predicates"].append(
                                {
                                    "source": ref_pred.get("source"),
                                    "external_id": ref_pred.get("source_id"),
                                }
                            )
                    elif isinstance(mapping_data, list):
                        # Legacy format: list of {"source": ..., "external_id": ...}
                        pred_info["external_predicates"] = mapping_data
                    elif (
                        isinstance(mapping_data, dict)
                        and "external_predicates" in mapping_data
                    ):
                        # Legacy dict format: {"external_predicates": [...]}
                        pred_info["external_predicates"] = mapping_data[
                            "external_predicates"
                        ]
                    else:
                        # Mapping doesn't match any expected format - log detailed warning
                        mapping_type = type(mapping_data).__name__
                        logger.warning(
                            f"Unsupported mapping format for predicate {pred.id}: "
                            f"Expected dict with 'reference_predicates' or 'external_predicates' key, "
                            f"or a list, got {mapping_type}. Mapping will be ignored."
                        )
                except json.JSONDecodeError as e:
                    # Check if mapping is just whitespace (which would indicate empty or invalid data)
                    if pred.mapping and not pred.mapping.strip():
                        logger.warning(
                            f"Predicate {pred.id} has empty or whitespace-only mapping. "
                            f"Mapping should be NULL or valid JSON. Mapping will be ignored."
                        )
                    else:
                        logger.warning(
                            f"Failed to parse mapping JSON for predicate {pred.id}: {e}. "
                            f"Mapping must be valid JSON (list or dict format). Mapping will be ignored."
                        )
                except (KeyError, TypeError) as e:
                    logger.warning(
                        f"Error processing mapping for predicate {pred.id}: {e}. "
                        f"Mapping structure may be invalid. Mapping will be ignored."
                    )

            mappings[pred.id] = pred_info

        return mappings

    def _build_relevance_sets(self) -> Tuple[Set[str], Set[str]]:
        """
        Build sets of relevant and irrelevant external predicate identifiers.

        Returns:
            Tuple of (relevant_predicates, irrelevant_predicates) where each is a set
            of strings in format "source:external_id" (e.g., "schema.org:subClassOf")
        """
        mappings = self._get_all_predicate_mappings_with_relevance()

        relevant = set()
        irrelevant = set()

        for pred_id, info in mappings.items():
            is_relevant = info["is_relevant"]

            # Skip predicates with no relevance flag set (null)
            if is_relevant is None:
                continue

            # Add all mapped external predicates to appropriate set
            for ext_pred in info["external_predicates"]:
                if "source" in ext_pred and "external_id" in ext_pred:
                    key = f"{ext_pred['source']}:{ext_pred['external_id']}"

                    if is_relevant:
                        relevant.add(key)
                    else:
                        irrelevant.add(key)

        return relevant, irrelevant

    def get_relevant_predicates(self, force_refresh: bool = False) -> Set[str]:
        """
        Get set of relevant external predicate identifiers.

        Args:
            force_refresh: If True, bypass cache and rebuild from database

        Returns:
            Set of strings in format "source:external_id"
        """
        if force_refresh or self._relevant_cache is None:
            self._relevant_cache, self._irrelevant_cache = self._build_relevance_sets()

        return self._relevant_cache

    def get_irrelevant_predicates(self, force_refresh: bool = False) -> Set[str]:
        """
        Get set of irrelevant external predicate identifiers.

        Args:
            force_refresh: If True, bypass cache and rebuild from database

        Returns:
            Set of strings in format "source:external_id"
        """
        if force_refresh or self._irrelevant_cache is None:
            self._relevant_cache, self._irrelevant_cache = self._build_relevance_sets()

        return self._irrelevant_cache

    def invalidate_cache(self):
        """Invalidate the predicate relevance cache."""
        self._relevant_cache = None
        self._irrelevant_cache = None
        logger.debug("Reference filter cache invalidated")

    def _determine_filter_mode(self, relevant: Set[str], irrelevant: Set[str]) -> str:
        """
        Determine the filtering strategy based on which predicates are marked.

        Filtering Modes:
        - WHITELIST: When relevant predicates exist, ONLY include links using those predicates
        - BLACKLIST: When only irrelevant predicates exist, EXCLUDE those and include all others

        Args:
            relevant: Set of relevant external predicate identifiers
            irrelevant: Set of irrelevant external predicate identifiers

        Returns:
            "whitelist" or "blacklist" indicating the filtering strategy
        """
        if len(relevant) > 0:
            # If any predicates are marked relevant, use whitelist mode
            # This means: only include links that use relevant predicates
            return "whitelist"
        else:
            # If only irrelevant predicates exist (no relevant ones), use blacklist mode
            # This means: exclude irrelevant predicates, include everything else
            return "blacklist"

    def _batch_fetch_predicates_for_links(
        self, links: List[ReferenceLink]
    ) -> Dict[str, List[str]]:
        """
        Batch fetch external predicates needed for the given links.

        This optimizes performance by fetching only the predicates referenced in the links,
        rather than fetching ALL external predicates from the database.

        Args:
            links: List of ReferenceLink objects to fetch predicates for

        Returns:
            Dict mapping link predicate IDs to list of "source:external_id" keys
        """
        # Collect unique predicate IDs from links
        unique_predicate_ids = {link.predicate for link in links}

        if not unique_predicate_ids:
            return {}

        # Batch fetch only the external predicates we need
        predicate_map = {}
        try:
            # Fetch all external predicates and filter in memory
            # This is more reliable across SQLite versions than IN clause with text()
            all_ext_preds = self.ref_manager.list_external_predicates()

            for ext_pred in all_ext_preds:
                if ext_pred.external_id in unique_predicate_ids:
                    if ext_pred.external_id not in predicate_map:
                        predicate_map[ext_pred.external_id] = []
                    pred_key = f"{ext_pred.source}:{ext_pred.external_id}"
                    predicate_map[ext_pred.external_id].append(pred_key)

        except Exception as e:
            logger.error(
                f"Database error fetching external predicates: {e}", exc_info=True
            )
            # Return empty map on error - will result in graceful degradation
            return {}

        return predicate_map

    def filter_links(
        self,
        links: List[ReferenceLink],
        include_relevant: bool = True,
        exclude_irrelevant: bool = True,
    ) -> Tuple[List[ReferenceLink], Dict[str, Any]]:
        """
        Filter reference links based on predicate relevance mappings.

        This method applies filtering based on the is_relevant flags set on global predicates.
        It uses two modes:
        - Whitelist mode (when relevant predicates exist): Only include links using relevant predicates
        - Blacklist mode (when only irrelevant exist): Exclude irrelevant, include everything else

        Args:
            links: List of ReferenceLink objects to filter
            include_relevant: If True, include links using relevant predicates (whitelist mode)
            exclude_irrelevant: If True, exclude links using irrelevant predicates (blacklist mode)

        Returns:
            Tuple of (filtered_links, statistics) where statistics contains:
            {
                "total_before": int,
                "total_after": int,
                "filtered_count": int,
                "predicates_used": List[str],
                "filtering_active": bool
            }
        """
        total_before = len(links)

        try:
            # Get relevance sets
            relevant = self.get_relevant_predicates()
            irrelevant = self.get_irrelevant_predicates()
        except Exception as e:
            logger.error(f"Error getting relevance sets: {e}", exc_info=True)
            # On error, return all links unfiltered
            return links, {
                "total_before": total_before,
                "total_after": total_before,
                "filtered_count": 0,
                "predicates_used": [],
                "filtering_active": False,
                "error": str(e),
            }

        # If no predicates marked relevant or irrelevant, return all links
        if not relevant and not irrelevant:
            return links, {
                "total_before": total_before,
                "total_after": total_before,
                "filtered_count": 0,
                "predicates_used": [],
                "filtering_active": False,
            }

        # Determine filtering strategy
        filter_mode = self._determine_filter_mode(relevant, irrelevant)
        whitelist_mode = filter_mode == "whitelist"

        # Batch fetch predicates for all links (performance optimization)
        predicate_map = self._batch_fetch_predicates_for_links(links)

        # Filter links
        filtered_links = []
        predicates_used = set()

        for link in links:
            # Get all external predicate keys for this link
            pred_keys = predicate_map.get(link.predicate, [])

            if pred_keys:
                # Check if any of the matching predicates are relevant/irrelevant
                should_include = False

                for pred_key in pred_keys:
                    if whitelist_mode:
                        # Whitelist mode: include if ANY matching predicate is relevant
                        if include_relevant and pred_key in relevant:
                            should_include = True
                            predicates_used.add(pred_key)
                            break  # Found a relevant match, include it
                    else:
                        # Blacklist mode: exclude if ANY matching predicate is irrelevant
                        if exclude_irrelevant and pred_key in irrelevant:
                            should_include = False
                            break  # Found irrelevant match, exclude it
                        else:
                            should_include = True

                if should_include:
                    filtered_links.append(link)
            else:
                # No external predicate mapping - include only in blacklist mode
                if not whitelist_mode:
                    filtered_links.append(link)

        total_after = len(filtered_links)
        filtered_count = total_before - total_after

        statistics = {
            "total_before": total_before,
            "total_after": total_after,
            "filtered_count": filtered_count,
            "predicates_used": sorted(list(predicates_used)),
            "filtering_active": True,
            "filter_mode": filter_mode,
        }

        logger.info(
            f"Filtered {filtered_count} links using {filter_mode} mode "
            f"({total_before} -> {total_after}), used {len(predicates_used)} predicates"
        )

        return filtered_links, statistics

    def get_filter_statistics(self) -> Dict[str, Any]:
        """
        Get current filter configuration statistics.

        Returns:
            Dictionary with:
            {
                "total_predicates": int,
                "relevant_count": int,
                "irrelevant_count": int,
                "unmapped_count": int,
                "relevant_external_predicates": List[str],
                "irrelevant_external_predicates": List[str]
            }
        """
        try:
            mappings = self._get_all_predicate_mappings_with_relevance()
            relevant = self.get_relevant_predicates(force_refresh=True)
            irrelevant = self.get_irrelevant_predicates()

            # Count predicates by relevance status
            relevant_count = sum(
                1 for info in mappings.values() if info["is_relevant"] is True
            )
            irrelevant_count = sum(
                1 for info in mappings.values() if info["is_relevant"] is False
            )
            unmapped_count = sum(
                1 for info in mappings.values() if info["is_relevant"] is None
            )

            return {
                "total_predicates": len(mappings),
                "relevant_count": relevant_count,
                "irrelevant_count": irrelevant_count,
                "unmapped_count": unmapped_count,
                "relevant_external_predicates": sorted(list(relevant)),
                "irrelevant_external_predicates": sorted(list(irrelevant)),
            }
        except Exception as e:
            logger.error(f"Error getting filter statistics: {e}", exc_info=True)
            return {
                "total_predicates": 0,
                "relevant_count": 0,
                "irrelevant_count": 0,
                "unmapped_count": 0,
                "relevant_external_predicates": [],
                "irrelevant_external_predicates": [],
                "error": str(e),
            }
