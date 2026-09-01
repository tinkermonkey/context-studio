"""Result aggregation utilities for reference service.

This module provides aggregation logic to deduplicate, cross-reference,
and merge search results from multiple sources.
"""

import re
from collections import defaultdict

from utils.logger import get_logger

from .models import MultiSourceSearchResponse, SearchLink, SearchNode, SourceType

logger = get_logger(__name__)


class ResultAggregator:
    """Aggregates and processes search results from multiple sources."""

    def __init__(self):
        pass

    def deduplicate_nodes(self, nodes: list[SearchNode]) -> list[SearchNode]:
        """
        Deduplicate nodes by ID, keeping the first occurrence.

        Args:
            nodes: List of SearchNode objects to deduplicate

        Returns:
            List of unique SearchNode objects
        """
        seen_ids = set()
        unique_nodes = []

        for node in nodes:
            if node.id not in seen_ids:
                seen_ids.add(node.id)
                unique_nodes.append(node)

        logger.debug(
            f"Deduplicated {len(nodes)} nodes to {len(unique_nodes)} unique nodes"
        )
        return unique_nodes

    def deduplicate_links(
        self, links: list[SearchLink], valid_node_ids: set[str]
    ) -> list[SearchLink]:
        """
        Deduplicate links by ID and filter to only include links between valid nodes.

        Args:
            links: List of SearchLink objects to deduplicate
            valid_node_ids: Set of valid node IDs to filter against

        Returns:
            List of unique SearchLink objects with valid node references
        """
        seen_ids = set()
        unique_links = []

        for link in links:
            # Only include links where both subject and object nodes are in our results
            if (
                link.id not in seen_ids
                and link.subject in valid_node_ids
                and link.object in valid_node_ids
            ):
                seen_ids.add(link.id)
                unique_links.append(link)

        logger.debug(
            f"Deduplicated {len(links)} links to {len(unique_links)} unique valid links"
        )
        return unique_links

    def discover_cross_references(self, nodes: list[SearchNode]) -> list[SearchLink]:
        """
        Discover cross-references between nodes from different sources based on title matching.
        Creates 'sameAs' links when nodes from different sources likely refer to the same concept.

        Args:
            nodes: List of SearchNode objects to analyze

        Returns:
            List of SearchLink objects representing cross-references
        """
        cross_links = []

        # Group nodes by normalized title for matching
        title_groups = defaultdict(list)
        for node in nodes:
            normalized_title = self._normalize_title(node.title)
            title_groups[normalized_title].append(node)

        # Find groups with nodes from multiple sources
        for normalized_title, matching_nodes in title_groups.items():
            if len(matching_nodes) < 2:
                continue

            # Group by source
            sources_present = defaultdict(list)
            for node in matching_nodes:
                sources_present[node.source].append(node)

            # Only create cross-references between different sources
            if len(sources_present) < 2:
                continue

            # Create cross-reference links between nodes from different sources
            sources = list(sources_present.keys())
            for i in range(len(sources)):
                for j in range(i + 1, len(sources)):
                    source1, source2 = sources[i], sources[j]
                    nodes1 = sources_present[source1]
                    nodes2 = sources_present[source2]

                    # Create links between the best matching nodes from each source
                    for node1 in nodes1[:1]:  # Take best match from each source
                        for node2 in nodes2[:1]:
                            # Calculate confidence based on title similarity
                            confidence = self._calculate_title_similarity(
                                node1.title, node2.title
                            )

                            if (
                                confidence >= 0.8
                            ):  # High confidence threshold for cross-references
                                cross_links.append(
                                    SearchLink(
                                        id=f"cross_ref:{node1.source.value}:{node2.source.value}:{hash(node1.id + node2.id)}",
                                        source=SourceType.CONCEPTNET,  # Use ConceptNet as the source for cross-references
                                        subject=node1.id,
                                        predicate="sameAs",
                                        object=node2.id,
                                        weight=confidence,
                                        attributes={
                                            "link_type": "cross_reference",
                                            "confidence": confidence,
                                            "matching_title": normalized_title,
                                            "source1": node1.source.value,
                                            "source2": node2.source.value,
                                        },
                                    )
                                )

        logger.debug(f"Discovered {len(cross_links)} cross-reference links")
        return cross_links

    def merge_responses(
        self, responses: list[MultiSourceSearchResponse]
    ) -> MultiSourceSearchResponse:
        """
        Merge multiple MultiSourceSearchResponse objects into a single aggregated response.

        Args:
            responses: List of MultiSourceSearchResponse objects to merge

        Returns:
            Merged MultiSourceSearchResponse object
        """
        if not responses:
            return MultiSourceSearchResponse(
                query="",
                results=[],
                links=[],
                total_results=0,
                total_links=0,
                sources_queried=[],
                source_errors={},
                offset=0,
                limit=0,
                search_time_ms=0.0,
            )

        # Use the first response as a template
        base_response = responses[0]

        # Aggregate all nodes and links
        all_nodes = []
        all_links = []
        all_source_errors = {}
        all_sources_queried = []
        total_search_time = 0.0

        for response in responses:
            all_nodes.extend(response.results)
            all_links.extend(response.links)
            all_source_errors.update(response.source_errors)
            all_sources_queried.extend(response.sources_queried)
            total_search_time += response.search_time_ms

        # Remove duplicate sources from sources_queried
        unique_sources_queried = list(dict.fromkeys(all_sources_queried))

        # Deduplicate nodes and links
        unique_nodes = self.deduplicate_nodes(all_nodes)
        valid_node_ids = {node.id for node in unique_nodes}
        unique_links = self.deduplicate_links(all_links, valid_node_ids)

        # Discover cross-references
        cross_links = self.discover_cross_references(unique_nodes)

        # Filter cross-links to ensure both nodes exist in our results
        filtered_cross_links = []
        seen_cross_link_ids = {link.id for link in unique_links}

        for cross_link in cross_links:
            if (
                cross_link.subject in valid_node_ids
                and cross_link.object in valid_node_ids
                and cross_link.id not in seen_cross_link_ids
            ):
                seen_cross_link_ids.add(cross_link.id)
                filtered_cross_links.append(cross_link)

        # Combine regular links with cross-links
        all_final_links = unique_links + filtered_cross_links

        return MultiSourceSearchResponse(
            query=base_response.query,
            results=unique_nodes,
            links=all_final_links,
            total_results=len(unique_nodes),
            total_links=len(all_final_links),
            sources_queried=unique_sources_queried,
            source_errors=all_source_errors,
            offset=base_response.offset,
            limit=base_response.limit,
            search_time_ms=total_search_time,
        )

    def aggregate_source_results(
        self,
        source_results: list[
            tuple[SourceType, tuple[list[SearchNode], list[SearchLink]]]
        ],
        query: str,
        limit: int,
        offset: int,
        search_time_ms: float,
        source_errors: dict[str, str],
    ) -> MultiSourceSearchResponse:
        """
        Aggregate results from multiple sources into a single MultiSourceSearchResponse.

        Args:
            source_results: List of tuples containing (source_type, (nodes, links))
            query: Original search query
            limit: Search limit used
            offset: Search offset used
            search_time_ms: Total search time in milliseconds
            source_errors: Dictionary of source errors

        Returns:
            Aggregated MultiSourceSearchResponse
        """
        all_nodes = []
        all_links = []
        sources_queried = []

        for source_type, (nodes, links) in source_results:
            sources_queried.append(source_type.value)
            all_nodes.extend(nodes)
            all_links.extend(links)

        # Deduplicate nodes and get valid node IDs
        unique_nodes = self.deduplicate_nodes(all_nodes)
        valid_node_ids = {node.id for node in unique_nodes}

        # Deduplicate links and filter to valid nodes
        unique_links = self.deduplicate_links(all_links, valid_node_ids)

        # Discover cross-references
        cross_links = self.discover_cross_references(unique_nodes)

        # Filter cross-links to ensure both nodes exist in our results
        filtered_cross_links = []
        seen_link_ids = {link.id for link in unique_links}

        for cross_link in cross_links:
            if (
                cross_link.subject in valid_node_ids
                and cross_link.object in valid_node_ids
                and cross_link.id not in seen_link_ids
            ):
                seen_link_ids.add(cross_link.id)
                filtered_cross_links.append(cross_link)

        # Combine regular links with cross-links
        all_final_links = unique_links + filtered_cross_links

        logger.info(
            f"Aggregated results: {len(unique_nodes)} nodes, {len(all_final_links)} links "
            f"({len(filtered_cross_links)} cross-references) from {len(sources_queried)} sources"
        )

        return MultiSourceSearchResponse(
            query=query,
            results=unique_nodes,
            links=all_final_links,
            total_results=len(unique_nodes),
            total_links=len(all_final_links),
            sources_queried=sources_queried,
            source_errors=source_errors,
            offset=offset,
            limit=limit,
            search_time_ms=search_time_ms,
        )

    def _normalize_title(self, title: str) -> str:
        """
        Normalize title for cross-reference matching.

        Args:
            title: Title string to normalize

        Returns:
            Normalized title string
        """
        if not title:
            return ""

        # Convert to lowercase and strip whitespace
        normalized = title.lower().strip()

        # Remove common variations and articles
        normalized = normalized.replace("the ", "").replace("a ", "").replace("an ", "")

        # Handle file extensions for file nodes
        if normalized in ["image file", "document file", "media file", "file"]:
            return normalized

        # Remove parenthetical content that might differ between sources
        normalized = re.sub(r"\([^)]*\)", "", normalized).strip()

        return normalized

    def _calculate_title_similarity(self, title1: str, title2: str) -> float:
        """
        Calculate similarity between two titles (0.0 to 1.0).

        Args:
            title1: First title to compare
            title2: Second title to compare

        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not title1 or not title2:
            return 0.0

        title1_norm = self._normalize_title(title1)
        title2_norm = self._normalize_title(title2)

        if title1_norm == title2_norm:
            return 1.0

        # Use simple character-based similarity for now
        # Could be enhanced with more sophisticated matching
        shorter = min(len(title1_norm), len(title2_norm))
        longer = max(len(title1_norm), len(title2_norm))

        if longer == 0:
            return 1.0 if shorter == 0 else 0.0

        # Count matching characters
        matches = sum(
            1
            for i in range(min(len(title1_norm), len(title2_norm)))
            if title1_norm[i] == title2_norm[i]
        )

        return matches / longer
