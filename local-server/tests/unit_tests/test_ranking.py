"""Unit tests for ranking engine"""

import pytest

# Add parent directories to path to find modules
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from enrichment.unified.models import UnifiedNode, ReferenceSource
from enrichment.unified.ranking import RankingEngine


class TestRankingEngine:
    """Test ranking engine functionality"""

    def setup_method(self):
        """Setup test fixtures"""
        self.engine = RankingEngine()

    def test_empty_list(self):
        """Test ranking with empty list"""
        result = self.engine.rank([], "test query")
        assert result == []

    def test_single_node(self):
        """Test ranking with single node"""
        node = UnifiedNode(
            id="test1",
            source=ReferenceSource.CONCEPTNET,
            source_id="/c/en/apple",
            title="Apple",
            definition="A fruit"
        )

        result = self.engine.rank([node], "apple")
        assert len(result) == 1
        assert result[0] == node

    def test_exact_title_match_ranks_highest(self):
        """Test that exact title matches rank highest"""
        nodes = [
            UnifiedNode(
                id="test1",
                source=ReferenceSource.CONCEPTNET,
                source_id="/c/en/apple_computer",
                title="Apple Computer",
                definition="A technology company"
            ),
            UnifiedNode(
                id="test2",
                source=ReferenceSource.WIKIDATA,
                source_id="Q89",
                title="Apple",
                definition="A fruit"
            ),
            UnifiedNode(
                id="test3",
                source=ReferenceSource.DBPEDIA,
                source_id="http://dbpedia.org/resource/Green_Apple",
                title="Green Apple",
                definition="A variety of apple"
            )
        ]

        result = self.engine.rank(nodes, "apple")

        # Exact match "Apple" should rank highest
        assert result[0].title == "Apple"

    def test_source_quality_affects_ranking(self):
        """Test that source quality affects ranking"""
        # Create identical nodes from different sources
        wikidata_node = UnifiedNode(
            id="test1",
            source=ReferenceSource.WIKIDATA,
            source_id="Q89",
            title="Computer",
            definition="Electronic device"
        )

        conceptnet_node = UnifiedNode(
            id="test2",
            source=ReferenceSource.CONCEPTNET,
            source_id="/c/en/computer",
            title="Computer",
            definition="Electronic device"
        )

        nodes = [conceptnet_node, wikidata_node]
        result = self.engine.rank(nodes, "computer")

        # Wikidata should rank higher due to source quality
        assert result[0].source == ReferenceSource.WIKIDATA

    def test_confidence_score_affects_ranking(self):
        """Test that confidence score affects ranking"""
        high_confidence = UnifiedNode(
            id="test1",
            source=ReferenceSource.CONCEPTNET,
            source_id="/c/en/apple",
            title="Apple",
            confidence_score=0.9
        )

        low_confidence = UnifiedNode(
            id="test2",
            source=ReferenceSource.CONCEPTNET,
            source_id="/c/en/apple2",
            title="Apple",
            confidence_score=0.5
        )

        nodes = [low_confidence, high_confidence]
        result = self.engine.rank(nodes, "apple")

        # High confidence should rank higher
        assert result[0].confidence_score == 0.9

    def test_completeness_affects_ranking(self):
        """Test that node completeness affects ranking"""
        complete_node = UnifiedNode(
            id="test1",
            source=ReferenceSource.CONCEPTNET,
            source_id="/c/en/apple",
            title="Apple",
            definition="A detailed definition of apple",
            source_url="http://example.com/apple",
            attributes={"key1": "value1", "key2": "value2"}
        )

        minimal_node = UnifiedNode(
            id="test2",
            source=ReferenceSource.CONCEPTNET,
            source_id="/c/en/apple2",
            title="Apple"
        )

        nodes = [minimal_node, complete_node]
        result = self.engine.rank(nodes, "apple")

        # More complete node should rank higher
        assert result[0].id == "test1"

    def test_definition_relevance_affects_ranking(self):
        """Test that definition relevance affects ranking"""
        relevant_def = UnifiedNode(
            id="test1",
            source=ReferenceSource.CONCEPTNET,
            source_id="/c/en/apple",
            title="Apple",
            definition="A red or green fruit that grows on apple trees"
        )

        irrelevant_def = UnifiedNode(
            id="test2",
            source=ReferenceSource.CONCEPTNET,
            source_id="/c/en/apple2",
            title="Apple",
            definition="A technology company in California"
        )

        nodes = [irrelevant_def, relevant_def]
        result = self.engine.rank(nodes, "fruit")

        # Node with relevant definition should rank higher
        assert result[0].id == "test1"

    def test_merged_nodes_get_bonus(self):
        """Test that merged nodes get ranking bonus"""
        merged_node = UnifiedNode(
            id="test1",
            source=ReferenceSource.WIKIDATA,
            source_id="Q89",
            title="Apple",
            merged_from=["/c/en/apple", "Q89"]
        )

        single_node = UnifiedNode(
            id="test2",
            source=ReferenceSource.CONCEPTNET,
            source_id="/c/en/apple2",
            title="Apple"
        )

        nodes = [single_node, merged_node]
        result = self.engine.rank(nodes, "apple")

        # Merged node should get completeness bonus
        # Note: This test might need adjustment based on exact scoring weights
        assert result[0].merged_from is not None

    def test_normalize_text_functionality(self):
        """Test text normalization"""
        test_cases = [
            ("Apple Inc.", "apple inc"),
            ("Multi-word_title", "multi word title"),
            ("UPPERCASE", "uppercase"),
            ("  padded  ", "padded"),
            ("special!@#chars", "special chars"),
        ]

        for input_text, expected in test_cases:
            result = self.engine._normalize_text(input_text)
            assert result == expected

    def test_text_relevance_exact_match(self):
        """Test text relevance calculation for exact matches"""
        relevance = self.engine._calculate_text_relevance("apple", "apple")
        assert relevance == 1.0

        relevance = self.engine._calculate_text_relevance("Apple", "apple")
        assert relevance == 1.0

    def test_text_relevance_substring_match(self):
        """Test text relevance for substring matches"""
        relevance = self.engine._calculate_text_relevance("apple fruit", "apple")
        assert relevance == 0.8  # Substring match score

        relevance = self.engine._calculate_text_relevance("green apple", "apple")
        assert relevance == 0.8

    def test_text_relevance_partial_word_match(self):
        """Test text relevance for partial word matches"""
        # Words that match should get high score
        relevance = self.engine._calculate_text_relevance("red apple fruit", "apple fruit")
        assert relevance > 0.5

        # No word matches should get low score
        relevance = self.engine._calculate_text_relevance("computer", "apple")
        assert relevance == 0.0

    def test_text_relevance_empty_inputs(self):
        """Test text relevance with empty inputs"""
        relevance = self.engine._calculate_text_relevance("", "apple")
        assert relevance == 0.0

        relevance = self.engine._calculate_text_relevance("apple", "")
        assert relevance == 0.0

        relevance = self.engine._calculate_text_relevance("", "")
        assert relevance == 0.0

    def test_fuzzy_matching(self):
        """Test fuzzy matching functionality"""
        # Similar words should have some similarity
        similarity = self.engine._calculate_fuzzy_match("apple fruit", "apple tree")
        assert similarity > 0.0

        # Completely different should have no similarity
        similarity = self.engine._calculate_fuzzy_match("apple", "computer")
        assert similarity == 0.0

        # Identical should have maximum similarity
        similarity = self.engine._calculate_fuzzy_match("apple fruit", "apple fruit")
        assert similarity == 1.0

    def test_completeness_calculation(self):
        """Test completeness score calculation"""
        # Minimal node
        minimal = UnifiedNode(
            id="test1",
            source=ReferenceSource.CONCEPTNET,
            source_id="/c/en/test",
            title="Test"
        )
        completeness = self.engine._calculate_completeness(minimal)
        assert completeness == 0.0

        # Complete node
        complete = UnifiedNode(
            id="test2",
            source=ReferenceSource.WIKIDATA,
            source_id="Q123",
            title="Test",
            definition="A test definition",
            source_url="http://example.com",
            attributes={"key1": "value1", "key2": "value2"},
            merged_from=["source1", "source2"]
        )
        completeness = self.engine._calculate_completeness(complete)
        assert completeness > 0.8  # Should be quite complete

    def test_rank_by_similarity_to_reference(self):
        """Test ranking by similarity to reference node"""
        reference = UnifiedNode(
            id="ref",
            source=ReferenceSource.WIKIDATA,
            source_id="Q89",
            title="Apple",
            definition="A fruit from a tree"
        )

        similar_node = UnifiedNode(
            id="similar",
            source=ReferenceSource.CONCEPTNET,
            source_id="/c/en/apple",
            title="Apple",
            definition="A tree fruit"
        )

        different_node = UnifiedNode(
            id="different",
            source=ReferenceSource.DBPEDIA,
            source_id="http://dbpedia.org/resource/Computer",
            title="Computer",
            definition="An electronic device"
        )

        nodes = [different_node, similar_node]
        result = self.engine.rank_by_similarity_to_reference(nodes, reference)

        # Similar node should rank higher
        assert result[0].id == "similar"

    def test_rank_by_similarity_excludes_reference(self):
        """Test that reference node is excluded from similarity ranking"""
        reference = UnifiedNode(
            id="ref",
            source=ReferenceSource.WIKIDATA,
            source_id="Q89",
            title="Apple"
        )

        other_node = UnifiedNode(
            id="other",
            source=ReferenceSource.CONCEPTNET,
            source_id="/c/en/banana",
            title="Banana"
        )

        nodes = [reference, other_node]
        result = self.engine.rank_by_similarity_to_reference(nodes, reference)

        # Should only contain the other node
        assert len(result) == 1
        assert result[0].id == "other"

    def test_attribute_similarity(self):
        """Test attribute similarity calculation"""
        attr1 = {"type": "fruit", "color": "red"}
        attr2 = {"type": "fruit", "color": "green"}

        similarity = self.engine._calculate_attribute_similarity(attr1, attr2)
        assert similarity > 0.5  # Should have some similarity due to "type": "fruit"

        # No common keys
        attr3 = {"shape": "round"}
        similarity = self.engine._calculate_attribute_similarity(attr1, attr3)
        assert similarity == 0.0

        # Empty attributes
        similarity = self.engine._calculate_attribute_similarity({}, attr1)
        assert similarity == 0.0

    def test_ranking_stability(self):
        """Test that ranking is stable for identical scores"""
        # Create nodes with identical relevance scores
        nodes = []
        for i in range(5):
            node = UnifiedNode(
                id=f"test{i}",
                source=ReferenceSource.CONCEPTNET,
                source_id=f"/c/en/test{i}",
                title="Test",
                definition="A test definition",
                confidence_score=0.8
            )
            nodes.append(node)

        result1 = self.engine.rank(nodes, "test")
        result2 = self.engine.rank(nodes, "test")

        # Results should be identical (stable sort)
        assert [n.id for n in result1] == [n.id for n in result2]

    def test_complex_ranking_scenario(self):
        """Test a complex ranking scenario with multiple factors"""
        nodes = [
            # High relevance, low quality source
            UnifiedNode(
                id="high_rel_low_qual",
                source=ReferenceSource.WORDNET,
                source_id="apple.n.01",
                title="Apple",
                definition="The fruit of the apple tree",
                confidence_score=0.7
            ),
            # Medium relevance, high quality source
            UnifiedNode(
                id="med_rel_high_qual",
                source=ReferenceSource.WIKIDATA,
                source_id="Q89",
                title="Malus domestica",
                definition="Species of apple tree",
                confidence_score=0.9
            ),
            # Low relevance, any source
            UnifiedNode(
                id="low_rel",
                source=ReferenceSource.DBPEDIA,
                source_id="http://dbpedia.org/resource/Apple_Inc",
                title="Apple Inc",
                definition="Technology company",
                confidence_score=0.8
            )
        ]

        result = self.engine.rank(nodes, "apple fruit")

        # The exact title match with relevant definition should rank highest
        assert result[0].id == "high_rel_low_qual"