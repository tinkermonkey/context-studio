"""Deduplication engine for unified reference facade"""

import re
from typing import List, Dict, Set, Tuple
from collections import defaultdict
import logging

from .models import UnifiedNode

logger = logging.getLogger(__name__)

class DeduplicationEngine:
    """Engine for deduplicating nodes across different sources"""

    def __init__(self, similarity_threshold: float = 0.85):
        """
        Initialize deduplication engine

        Args:
            similarity_threshold: Threshold for considering nodes as duplicates
        """
        self.similarity_threshold = similarity_threshold

    async def deduplicate(self, nodes: List[UnifiedNode]) -> List[UnifiedNode]:
        """
        Deduplicate a list of nodes

        Args:
            nodes: List of nodes to deduplicate

        Returns:
            List of deduplicated nodes
        """
        if not nodes:
            return []

        # Group nodes by normalized title for efficient comparison
        title_groups = self._group_by_normalized_title(nodes)

        # Find duplicates within and across groups
        duplicate_groups = self._find_duplicate_groups(title_groups)

        # Merge duplicate groups
        merged_nodes = self._merge_duplicate_groups(duplicate_groups)

        logger.info(f"Deduplicated {len(nodes)} nodes to {len(merged_nodes)} unique nodes")
        return merged_nodes

    def _group_by_normalized_title(self, nodes: List[UnifiedNode]) -> Dict[str, List[UnifiedNode]]:
        """Group nodes by normalized title for efficient comparison"""
        groups = defaultdict(list)

        for node in nodes:
            normalized_title = self._normalize_text(node.title)
            groups[normalized_title].append(node)

        return dict(groups)

    def _find_duplicate_groups(self, title_groups: Dict[str, List[UnifiedNode]]) -> List[List[UnifiedNode]]:
        """Find groups of duplicate nodes"""
        all_nodes = []
        for group in title_groups.values():
            all_nodes.extend(group)

        # Use Union-Find data structure to group duplicates
        parent = {i: i for i in range(len(all_nodes))}

        def find(x):
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        # Compare all pairs of nodes
        for i in range(len(all_nodes)):
            for j in range(i + 1, len(all_nodes)):
                if self._are_duplicates(all_nodes[i], all_nodes[j]):
                    union(i, j)

        # Group nodes by their root parent
        groups = defaultdict(list)
        for i, node in enumerate(all_nodes):
            root = find(i)
            groups[root].append(node)

        return list(groups.values())

    def _are_duplicates(self, node1: UnifiedNode, node2: UnifiedNode) -> bool:
        """Check if two nodes are duplicates"""
        # Don't merge nodes from the same source with the same ID
        if node1.source == node2.source and node1.source_id == node2.source_id:
            return False

        # Calculate similarity scores
        title_sim = self._title_similarity(node1.title, node2.title)
        definition_sim = self._definition_similarity(node1.definition, node2.definition)

        # Weighted similarity score
        if node1.definition and node2.definition:
            overall_sim = 0.6 * title_sim + 0.4 * definition_sim
        else:
            overall_sim = title_sim

        return overall_sim >= self.similarity_threshold

    def _title_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two titles"""
        if not title1 or not title2:
            return 0.0

        # Normalize titles
        norm1 = self._normalize_text(title1)
        norm2 = self._normalize_text(title2)

        # Exact match
        if norm1 == norm2:
            return 1.0

        # Fuzzy matching using Jaccard similarity on words
        words1 = set(norm1.split())
        words2 = set(norm2.split())

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        jaccard = len(intersection) / len(union)

        # Also check if one title contains the other
        containment = 0.0
        if norm1 in norm2 or norm2 in norm1:
            containment = 0.8

        return max(jaccard, containment)

    def _definition_similarity(self, def1: str, def2: str) -> float:
        """Calculate similarity between two definitions"""
        if not def1 or not def2:
            return 0.0

        # Normalize definitions
        norm1 = self._normalize_text(def1)
        norm2 = self._normalize_text(def2)

        # Exact match
        if norm1 == norm2:
            return 1.0

        # Fuzzy matching using Jaccard similarity on words
        words1 = set(norm1.split())
        words2 = set(norm2.split())

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union)

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        if not text:
            return ""

        # Convert to lowercase
        text = text.lower()

        # Remove punctuation and extra whitespace
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text)

        # Strip whitespace
        return text.strip()

    def _merge_duplicate_groups(self, duplicate_groups: List[List[UnifiedNode]]) -> List[UnifiedNode]:
        """Merge groups of duplicate nodes"""
        merged_nodes = []

        for group in duplicate_groups:
            if len(group) == 1:
                # No duplicates in this group
                merged_nodes.append(group[0])
            else:
                # Merge duplicates
                merged_node = self._merge_nodes(group)
                merged_nodes.append(merged_node)

        return merged_nodes

    def _merge_nodes(self, nodes: List[UnifiedNode]) -> UnifiedNode:
        """Merge multiple nodes into a single node"""
        if len(nodes) == 1:
            return nodes[0]

        # Choose the best node as the primary (highest confidence, most complete)
        primary_node = self._choose_primary_node(nodes)

        # Collect information from all nodes
        merged_sources = [node.source_id for node in nodes]
        merged_attributes = {}

        # Merge attributes from all nodes
        for node in nodes:
            merged_attributes.update(node.attributes)

        # Add source tracking
        merged_attributes["merged_from_sources"] = [node.source.value for node in nodes]
        merged_attributes["merged_from_ids"] = merged_sources

        # Use the best available title and definition
        best_title = self._choose_best_title([node.title for node in nodes])
        best_definition = self._choose_best_definition([node.definition for node in nodes if node.definition])

        # Calculate average confidence
        avg_confidence = sum(node.confidence_score for node in nodes) / len(nodes)

        return UnifiedNode(
            id=primary_node.id,  # Keep primary node's ID
            source=primary_node.source,
            source_id=primary_node.source_id,
            title=best_title,
            definition=best_definition,
            attributes=merged_attributes,
            source_url=primary_node.source_url,
            confidence_score=min(avg_confidence * 1.1, 1.0),  # Slight boost for merged nodes
            merged_from=merged_sources
        )

    def _choose_primary_node(self, nodes: List[UnifiedNode]) -> UnifiedNode:
        """Choose the best node as the primary for merging"""
        # Score nodes based on completeness and confidence
        def score_node(node):
            score = node.confidence_score

            # Boost for having definition
            if node.definition:
                score += 0.2

            # Boost for having more attributes
            score += min(len(node.attributes) * 0.01, 0.1)

            # Source preference (can be configured)
            source_preference = {
                "wikidata": 0.3,
                "dbpedia": 0.2,
                "schema_org": 0.15,
                "conceptnet": 0.1,
                "wordnet": 0.05
            }
            score += source_preference.get(node.source.value, 0)

            return score

        return max(nodes, key=score_node)

    def _choose_best_title(self, titles: List[str]) -> str:
        """Choose the best title from a list"""
        if not titles:
            return ""

        # Filter out empty titles
        valid_titles = [t for t in titles if t and t.strip()]
        if not valid_titles:
            return ""

        # Prefer longer, more descriptive titles
        return max(valid_titles, key=lambda t: (len(t.split()), len(t)))

    def _choose_best_definition(self, definitions: List[str]) -> str:
        """Choose the best definition from a list"""
        if not definitions:
            return None

        # Filter out empty definitions
        valid_definitions = [d for d in definitions if d and d.strip()]
        if not valid_definitions:
            return None

        # Prefer longer, more descriptive definitions
        return max(valid_definitions, key=len)