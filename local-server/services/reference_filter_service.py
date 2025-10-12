"""
Reference Link Filtering Service

This service handles filtering of reference links based on predicate relevance mappings.
When predicates are marked as relevant/irrelevant in the global predicates table,
this service applies those filters to reference query results.
"""

import json
import logging
from typing import List, Dict, Any, Optional, Set
from sqlalchemy.orm import Session
from sqlalchemy import text

from database.models import Predicate
from reference_db.models import ReferenceLink, ReferenceNode
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

    def _get_predicate_mappings(self) -> Dict[str, Any]:
        """
        Get all predicate mappings with relevance flags.

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
        predicates = self.local_session.query(Predicate).all()

        mappings = {}
        for pred in predicates:
            pred_info = {
                "is_relevant": pred.is_relevant,
                "external_predicates": []
            }

            # Parse mapping JSON if present
            if pred.mapping:
                try:
                    mapping_data = json.loads(pred.mapping)
                    # Handle both list and dict formats
                    if isinstance(mapping_data, list):
                        pred_info["external_predicates"] = mapping_data
                    elif isinstance(mapping_data, dict) and "external_predicates" in mapping_data:
                        pred_info["external_predicates"] = mapping_data["external_predicates"]
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Failed to parse mapping for predicate {pred.id}: {e}")

            mappings[pred.id] = pred_info

        return mappings

    def _build_relevance_sets(self) -> tuple[Set[str], Set[str]]:
        """
        Build sets of relevant and irrelevant external predicate identifiers.

        Returns:
            Tuple of (relevant_predicates, irrelevant_predicates) where each is a set
            of strings in format "source:external_id" (e.g., "schema.org:subClassOf")
        """
        mappings = self._get_predicate_mappings()

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

    def filter_links(
        self,
        links: List[ReferenceLink],
        include_relevant: bool = True,
        exclude_irrelevant: bool = True
    ) -> tuple[List[ReferenceLink], Dict[str, Any]]:
        """
        Filter reference links based on predicate relevance.

        Args:
            links: List of ReferenceLink objects to filter
            include_relevant: If True, include links using relevant predicates
            exclude_irrelevant: If True, exclude links using irrelevant predicates

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

        # Get relevance sets
        relevant = self.get_relevant_predicates()
        irrelevant = self.get_irrelevant_predicates()

        # If no predicates marked relevant or irrelevant, return all links
        if not relevant and not irrelevant:
            return links, {
                "total_before": total_before,
                "total_after": total_before,
                "filtered_count": 0,
                "predicates_used": [],
                "filtering_active": False
            }

        # Filter links
        filtered_links = []
        predicates_used = set()

        # Determine filtering mode:
        # - If relevant predicates exist, use whitelist mode (only include relevant)
        # - If only irrelevant predicates exist, use blacklist mode (exclude irrelevant, include others)
        whitelist_mode = len(relevant) > 0

        for link in links:
            # Find all external predicates matching this link's predicate across all sources
            # Use list_external_predicates and filter by external_id
            all_ext_preds = self.ref_manager.list_external_predicates()
            matching_predicates = [ep for ep in all_ext_preds if ep.external_id == link.predicate]

            if matching_predicates:
                # Check if any of the matching predicates are relevant/irrelevant
                should_include = False
                found_relevant = False

                for ext_pred in matching_predicates:
                    pred_key = f"{ext_pred.source}:{ext_pred.external_id}"

                    if whitelist_mode:
                        # Whitelist mode: include if ANY matching predicate is relevant
                        if include_relevant and pred_key in relevant:
                            should_include = True
                            found_relevant = True
                            predicates_used.add(pred_key)
                    else:
                        # Blacklist mode: exclude if ANY matching predicate is irrelevant
                        if exclude_irrelevant and pred_key in irrelevant:
                            should_include = False
                            break
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
            "filtering_active": True
        }

        logger.info(
            f"Filtered {filtered_count} links ({total_before} -> {total_after}), "
            f"used {len(predicates_used)} predicates"
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
        mappings = self._get_predicate_mappings()
        relevant = self.get_relevant_predicates(force_refresh=True)
        irrelevant = self.get_irrelevant_predicates()

        # Count predicates by relevance status
        relevant_count = sum(1 for info in mappings.values() if info["is_relevant"] is True)
        irrelevant_count = sum(1 for info in mappings.values() if info["is_relevant"] is False)
        unmapped_count = sum(1 for info in mappings.values() if info["is_relevant"] is None)

        return {
            "total_predicates": len(mappings),
            "relevant_count": relevant_count,
            "irrelevant_count": irrelevant_count,
            "unmapped_count": unmapped_count,
            "relevant_external_predicates": sorted(list(relevant)),
            "irrelevant_external_predicates": sorted(list(irrelevant))
        }
