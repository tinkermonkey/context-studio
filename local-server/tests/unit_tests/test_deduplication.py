"""Unit tests for deduplication engine"""

import pytest
from unittest.mock import Mock

# Add parent directories to path to find modules
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from enrichment.unified.models import UnifiedNode, ReferenceSource
from enrichment.unified.deduplication import DeduplicationEngine


class TestDeduplicationEngine:
    """Test deduplication engine functionality"""

    def setup_method(self):
        """Setup test fixtures"""
        self.engine = DeduplicationEngine(similarity_threshold=0.85)

    def test_empty_list(self):
        """Test deduplication with empty list"""
        result = await self.engine.deduplicate([])
        assert result == []

    def test_single_node(self):
        """Test deduplication with single node"""
        node = UnifiedNode(
            id="test1",
            source=ReferenceSource.CONCEPTNET,
            source_id="/c/en/apple",
            title="Apple",
            definition="A fruit"
        )

        result = await self.engine.deduplicate([node])
        assert len(result) == 1
        assert result[0] == node

    def test_no_duplicates(self):
        """Test deduplication with completely different nodes"""
        nodes = [
            UnifiedNode(
                id="test1",
                source=ReferenceSource.CONCEPTNET,
                source_id="/c/en/apple",
                title="Apple",
                definition="A fruit"
            ),
            UnifiedNode(
                id="test2",
                source=ReferenceSource.WORDNET,
                source_id="car.n.01",
                title="Car",
                definition="A vehicle"
            ),
            UnifiedNode(
                id="test3",
                source=ReferenceSource.DBPEDIA,
                source_id="http://dbpedia.org/resource/Computer",
                title="Computer",
                definition="An electronic device"
            )
        ]

        result = await self.engine.deduplicate(nodes)
        assert len(result) == 3
        # Results should be in same order for deterministic non-duplicates
        assert all(node in result for node in nodes)

    def test_exact_title_duplicates(self):
        """Test deduplication with exact title matches"""
        nodes = [
            UnifiedNode(
                id="test1",
                source=ReferenceSource.CONCEPTNET,
                source_id="/c/en/apple",
                title="Apple",
                definition="A fruit"
            ),
            UnifiedNode(
                id="test2",
                source=ReferenceSource.WIKIDATA,
                source_id="Q89",
                title="Apple",
                definition="Pomaceous fruit"
            )
        ]

        result = await self.engine.deduplicate(nodes)
        assert len(result) == 1

        # Check that the result is a merged node
        merged = result[0]
        assert merged.title == "Apple"
        assert merged.merged_from is not None
        assert len(merged.merged_from) == 2
        assert "merged_from_sources" in merged.attributes
        assert len(merged.attributes["merged_from_sources"]) == 2

    def test_similar_title_duplicates(self):
        """Test deduplication with similar titles"""
        nodes = [
            UnifiedNode(
                id="test1",
                source=ReferenceSource.CONCEPTNET,
                source_id="/c/en/automobile",
                title="Automobile",
                definition="A vehicle"
            ),
            UnifiedNode(
                id="test2",
                source=ReferenceSource.WORDNET,
                source_id="car.n.01",
                title="Car",
                definition="A motor vehicle"
            )
        ]

        result = await self.engine.deduplicate(nodes)
        # These should be detected as similar and merged
        assert len(result) == 1

    def test_different_sources_same_id_not_merged(self):
        """Test that nodes from same source with same ID are not merged"""
        nodes = [
            UnifiedNode(
                id="test1",
                source=ReferenceSource.CONCEPTNET,
                source_id="/c/en/apple",
                title="Apple",
                definition="A fruit"
            ),
            UnifiedNode(
                id="test2",
                source=ReferenceSource.CONCEPTNET,
                source_id="/c/en/apple",
                title="Apple",
                definition="A fruit"
            )
        ]

        result = await self.engine.deduplicate(nodes)
        # Same source, same ID should not be merged
        assert len(result) == 2

    def test_similarity_threshold_respected(self):
        """Test that similarity threshold is respected"""
        # Use a high threshold that should prevent merging
        engine = DeduplicationEngine(similarity_threshold=0.95)

        nodes = [
            UnifiedNode(
                id="test1",
                source=ReferenceSource.CONCEPTNET,
                source_id="/c/en/automobile",
                title="Automobile",
                definition="A vehicle"
            ),
            UnifiedNode(
                id="test2",
                source=ReferenceSource.WORDNET,
                source_id="car.n.01",
                title="Car",
                definition="A motor vehicle"
            )
        ]

        result = await engine.deduplicate(nodes)
        # With high threshold, these should not be merged
        assert len(result) == 2

    def test_merged_node_attributes(self):
        """Test that merged nodes have correct attributes"""
        nodes = [
            UnifiedNode(
                id="test1",
                source=ReferenceSource.CONCEPTNET,
                source_id="/c/en/apple",
                title="Apple",
                definition="A fruit",
                confidence_score=0.8,
                attributes={"source_specific": "conceptnet_data"}
            ),
            UnifiedNode(
                id="test2",
                source=ReferenceSource.WIKIDATA,
                source_id="Q89",
                title="Apple",
                definition="Pomaceous fruit of apple tree",
                confidence_score=0.9,
                attributes={"wikidata_id": "Q89"}
            )
        ]

        result = await self.engine.deduplicate(nodes)
        assert len(result) == 1

        merged = result[0]
        # Should have merged attributes
        assert "source_specific" in merged.attributes
        assert "wikidata_id" in merged.attributes
        assert "merged_from_sources" in merged.attributes
        assert "merged_from_ids" in merged.attributes

        # Should use better definition (longer one)
        assert merged.definition == "Pomaceous fruit of apple tree"

        # Should have boosted confidence (average * 1.1, capped at 1.0)
        expected_confidence = min((0.8 + 0.9) / 2 * 1.1, 1.0)
        assert merged.confidence_score == expected_confidence

    def test_choose_primary_node_logic(self):
        """Test primary node selection logic"""
        # Node with higher confidence and more complete data should be primary
        complete_node = UnifiedNode(
            id="complete",
            source=ReferenceSource.WIKIDATA,  # Higher source preference
            source_id="Q89",
            title="Apple",
            definition="A detailed definition",
            confidence_score=0.9,
            attributes={"key1": "value1", "key2": "value2"}
        )

        minimal_node = UnifiedNode(
            id="minimal",
            source=ReferenceSource.CONCEPTNET,
            source_id="/c/en/apple",
            title="Apple",
            confidence_score=0.7
        )

        nodes = [minimal_node, complete_node]
        result = await self.engine.deduplicate(nodes)
        assert len(result) == 1

        # The merged node should use the complete node's ID as primary
        merged = result[0]
        assert merged.id == complete_node.id
        assert merged.source == complete_node.source

    def test_normalize_text(self):
        """Test text normalization"""
        test_cases = [
            ("Apple", "apple"),
            ("Apple Inc.", "apple inc"),
            ("Multi-word   Title", "multi word title"),
            ("Title_with_underscores", "title with underscores"),
            ("  Padded  ", "padded"),
            ("", ""),
        ]

        for input_text, expected in test_cases:
            result = self.engine._normalize_text(input_text)
            assert result == expected

    def test_title_similarity_exact_match(self):
        """Test title similarity with exact matches"""
        similarity = self.engine._title_similarity("Apple", "Apple")
        assert similarity == 1.0

        similarity = self.engine._title_similarity("apple", "Apple")
        assert similarity == 1.0

    def test_title_similarity_contains(self):
        """Test title similarity with containment"""
        similarity = self.engine._title_similarity("Apple", "Apple Inc")
        assert similarity == 0.8  # Containment score

        similarity = self.engine._title_similarity("Car", "Racing Car")
        assert similarity == 0.8

    def test_title_similarity_jaccard(self):
        """Test title similarity with Jaccard index"""
        # "Red Apple" vs "Green Apple" should have good similarity
        similarity = self.engine._title_similarity("Red Apple", "Green Apple")
        assert similarity > 0.3  # Should have decent similarity due to "Apple"

        # Completely different should have low similarity
        similarity = self.engine._title_similarity("Apple", "Computer")
        assert similarity == 0.0

    def test_title_similarity_edge_cases(self):
        """Test title similarity edge cases"""
        # Empty strings
        similarity = self.engine._title_similarity("", "")
        assert similarity == 0.0

        similarity = self.engine._title_similarity("Apple", "")
        assert similarity == 0.0

        # None values
        similarity = self.engine._title_similarity(None, "Apple")
        assert similarity == 0.0

    def test_definition_similarity(self):
        """Test definition similarity"""
        # Exact match
        similarity = self.engine._definition_similarity(
            "A fruit from a tree",
            "A fruit from a tree"
        )
        assert similarity == 1.0

        # Similar definitions
        similarity = self.engine._definition_similarity(
            "A red fruit",
            "A fruit that is red"
        )
        assert similarity > 0.5

        # Different definitions
        similarity = self.engine._definition_similarity(
            "A fruit",
            "A vehicle"
        )
        assert similarity < 0.2

    def test_are_duplicates_logic(self):
        """Test the overall duplicate detection logic"""
        # Same source, same ID should not be duplicates
        node1 = UnifiedNode(
            id="test1",
            source=ReferenceSource.CONCEPTNET,
            source_id="/c/en/apple",
            title="Apple"
        )
        node2 = UnifiedNode(
            id="test2",
            source=ReferenceSource.CONCEPTNET,
            source_id="/c/en/apple",
            title="Apple"
        )

        assert not self.engine._are_duplicates(node1, node2)

        # Different sources, similar content should be duplicates
        node3 = UnifiedNode(
            id="test3",
            source=ReferenceSource.WIKIDATA,
            source_id="Q89",
            title="Apple",
            definition="A fruit"
        )

        assert self.engine._are_duplicates(node1, node3)

    def test_large_dataset_performance(self):
        """Test deduplication with larger dataset"""
        # Create 50 nodes with some duplicates
        nodes = []
        for i in range(50):
            # Every 5th node is a duplicate of "Apple"
            if i % 5 == 0:
                node = UnifiedNode(
                    id=f"apple_{i}",
                    source=ReferenceSource(list(ReferenceSource)[i % len(ReferenceSource)]),
                    source_id=f"apple_source_{i}",
                    title="Apple",
                    definition="A fruit"
                )
            else:
                node = UnifiedNode(
                    id=f"unique_{i}",
                    source=ReferenceSource(list(ReferenceSource)[i % len(ReferenceSource)]),
                    source_id=f"unique_source_{i}",
                    title=f"Unique Item {i}",
                    definition=f"Definition for item {i}"
                )
            nodes.append(node)

        result = await self.engine.deduplicate(nodes)

        # Should have fewer results due to Apple duplicates being merged
        assert len(result) < len(nodes)
        # But should still have the unique items
        assert len(result) >= 40  # At least the unique items should remain