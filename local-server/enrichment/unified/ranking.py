"""Ranking engine for unified reference facade"""

import re
import math
from typing import List, Dict, Set
from collections import Counter
import logging

from .models import UnifiedNode

logger = logging.getLogger(__name__)

class RankingEngine:
    """Engine for ranking search results"""

    def __init__(self):
        """Initialize ranking engine"""
        # Source quality weights
        self.source_weights = {
            "wikidata": 1.0,
            "dbpedia": 0.9,
            "schema_org": 0.8,
            "conceptnet": 0.7,
            "wordnet": 0.6
        }

    def rank(self, nodes: List[UnifiedNode], query: str) -> List[UnifiedNode]:
        """
        Rank nodes by relevance to the query

        Args:
            nodes: List of nodes to rank
            query: Original search query

        Returns:
            List of nodes sorted by relevance (highest first)
        """
        if not nodes:
            return []

        # Calculate relevance scores
        scored_nodes = []
        for node in nodes:
            score = self._calculate_relevance_score(node, query)
            scored_nodes.append((score, node))

        # Sort by score (descending)
        scored_nodes.sort(key=lambda x: x[0], reverse=True)

        # Extract nodes
        ranked_nodes = [node for score, node in scored_nodes]

        logger.debug(f"Ranked {len(nodes)} nodes for query: '{query}'")
        return ranked_nodes

    def _calculate_relevance_score(self, node: UnifiedNode, query: str) -> float:
        """Calculate relevance score for a node"""
        score = 0.0

        # 1. Title relevance (40% weight)
        title_score = self._calculate_text_relevance(node.title, query)
        score += 0.4 * title_score

        # 2. Definition relevance (30% weight)
        if node.definition:
            definition_score = self._calculate_text_relevance(node.definition, query)
            score += 0.3 * definition_score

        # 3. Source quality (15% weight)
        source_weight = self.source_weights.get(node.source.value, 0.5)
        score += 0.15 * source_weight

        # 4. Node confidence (10% weight)
        score += 0.1 * node.confidence_score

        # 5. Completeness bonus (5% weight)
        completeness = self._calculate_completeness(node)
        score += 0.05 * completeness

        return min(score, 1.0)  # Cap at 1.0

    def _calculate_text_relevance(self, text: str, query: str) -> float:
        """Calculate relevance between text and query"""
        if not text or not query:
            return 0.0

        # Normalize text and query
        text_norm = self._normalize_text(text)
        query_norm = self._normalize_text(query)

        # Exact match gets highest score
        if query_norm == text_norm:
            return 1.0

        # Substring match
        if query_norm in text_norm:
            return 0.8

        # Calculate TF-IDF style score
        query_words = set(query_norm.split())
        text_words = text_norm.split()

        if not query_words or not text_words:
            return 0.0

        # Term frequency for query words in text
        text_word_count = Counter(text_words)
        total_words = len(text_words)

        score = 0.0
        for query_word in query_words:
            if query_word in text_word_count:
                # Term frequency
                tf = text_word_count[query_word] / total_words

                # Position bonus (words earlier in text get higher score)
                try:
                    first_position = text_words.index(query_word)
                    position_bonus = 1.0 - (first_position / len(text_words)) * 0.3
                except ValueError:
                    position_bonus = 1.0

                # Length penalty for very long texts
                length_penalty = min(1.0, 50 / len(text_words))

                word_score = tf * position_bonus * length_penalty
                score += word_score

        # Normalize by number of query words
        score = score / len(query_words)

        # Fuzzy matching bonus for partial word matches
        fuzzy_score = self._calculate_fuzzy_match(text_norm, query_norm)
        score = max(score, fuzzy_score * 0.6)

        return min(score, 1.0)

    def _calculate_fuzzy_match(self, text: str, query: str) -> float:
        """Calculate fuzzy matching score using Jaccard similarity"""
        text_words = set(text.split())
        query_words = set(query.split())

        if not text_words or not query_words:
            return 0.0

        intersection = text_words.intersection(query_words)
        union = text_words.union(query_words)

        return len(intersection) / len(union) if union else 0.0

    def _calculate_completeness(self, node: UnifiedNode) -> float:
        """Calculate completeness score for a node"""
        score = 0.0

        # Has definition
        if node.definition:
            score += 0.4

        # Has source URL
        if node.source_url:
            score += 0.2

        # Number of attributes
        attribute_score = min(len(node.attributes) * 0.05, 0.3)
        score += attribute_score

        # Merged from multiple sources
        if node.merged_from:
            score += 0.1

        return min(score, 1.0)

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        if not text:
            return ""

        # Convert to lowercase
        text = text.lower()

        # Remove punctuation except underscores and hyphens
        text = re.sub(r'[^\w\s\-_]', ' ', text)

        # Replace underscores and hyphens with spaces
        text = re.sub(r'[_\-]', ' ', text)

        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def rank_by_similarity_to_reference(
        self,
        nodes: List[UnifiedNode],
        reference_node: UnifiedNode
    ) -> List[UnifiedNode]:
        """
        Rank nodes by similarity to a reference node

        Args:
            nodes: List of nodes to rank
            reference_node: Node to compare against

        Returns:
            List of nodes sorted by similarity to reference
        """
        if not nodes:
            return []

        scored_nodes = []
        for node in nodes:
            if node.id == reference_node.id:
                continue  # Skip the reference node itself

            similarity = self._calculate_node_similarity(node, reference_node)
            scored_nodes.append((similarity, node))

        # Sort by similarity (descending)
        scored_nodes.sort(key=lambda x: x[0], reverse=True)

        return [node for similarity, node in scored_nodes]

    def _calculate_node_similarity(self, node1: UnifiedNode, node2: UnifiedNode) -> float:
        """Calculate similarity between two nodes"""
        # Title similarity (50% weight)
        title_sim = self._calculate_text_relevance(node1.title, node2.title)

        # Definition similarity (30% weight)
        def_sim = 0.0
        if node1.definition and node2.definition:
            def_sim = self._calculate_text_relevance(node1.definition, node2.definition)

        # Attribute similarity (20% weight)
        attr_sim = self._calculate_attribute_similarity(node1.attributes, node2.attributes)

        similarity = 0.5 * title_sim + 0.3 * def_sim + 0.2 * attr_sim
        return similarity

    def _calculate_attribute_similarity(self, attr1: Dict, attr2: Dict) -> float:
        """Calculate similarity between attribute dictionaries"""
        if not attr1 or not attr2:
            return 0.0

        # Find common keys
        common_keys = set(attr1.keys()).intersection(set(attr2.keys()))
        if not common_keys:
            return 0.0

        similarities = []
        for key in common_keys:
            val1, val2 = str(attr1[key]), str(attr2[key])
            if val1 == val2:
                similarities.append(1.0)
            else:
                sim = self._calculate_text_relevance(val1, val2)
                similarities.append(sim)

        return sum(similarities) / len(similarities) if similarities else 0.0