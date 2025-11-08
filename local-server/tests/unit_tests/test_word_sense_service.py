"""
Unit tests for WordSenseService.

Tests word sense extraction, filtering, validation, and error handling.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import json
from unittest.mock import Mock, MagicMock
from sqlalchemy.orm import Session

from services.word_sense_service import WordSenseService
from api.models.structure_nodes import WordSense
from database.models import StructureNode
from database.enums import NodeType
from nlp.models import NLPAnalysisResponse, TokenData, WordNetData


class TestWordSenseService:
    """Test suite for WordSenseService."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return Mock(spec=Session)

    @pytest.fixture
    def service(self, mock_db):
        """Create a WordSenseService instance with mock database."""
        return WordSenseService(mock_db)

    @pytest.fixture
    def sample_node(self):
        """Create a sample StructureNode for testing."""
        node = Mock(spec=StructureNode)
        node.id = "test-node-123"
        node.node_type = NodeType.TERM
        node.title = "bank"
        node.word_senses = None
        node.version = 1
        return node

    @pytest.fixture
    def sample_nlp_response(self):
        """Create a sample NLP analysis response with word senses."""
        token1 = TokenData(
            text="bank",
            wordnet=WordNetData(
                synsets=[
                    {
                        "name": "bank.n.01",
                        "definition": "financial institution",
                        "lemmas": ["bank"],
                        "pos": "n",
                        "offset": 12345,
                        "domain": "noun.group"
                    },
                    {
                        "name": "bank.n.02",
                        "definition": "sloping land beside water",
                        "lemmas": ["bank"],
                        "pos": "n",
                        "offset": 12346,
                        "domain": "noun.object"
                    }
                ]
            )
        )

        return NLPAnalysisResponse(
            text="bank",
            tokens=[token1],
            entities=[]
        )

    @pytest.fixture
    def sample_word_senses(self):
        """Create sample word senses."""
        return [
            WordSense(
                term="bank",
                sense_type="wordnet",
                sense_id="bank.n.01",
                definition="financial institution",
                domain="noun.group"
            ),
            WordSense(
                term="bank",
                sense_type="wordnet",
                sense_id="bank.n.02",
                definition="sloping land beside water",
                domain="noun.object"
            )
        ]

    def test_extract_word_senses_success(self, service, sample_nlp_response):
        """Test successfully extracting word senses from NLP response."""
        # Execute
        result = service.extract_word_senses(sample_nlp_response)

        # Assert
        assert len(result) == 2
        assert result[0].term == "bank"
        assert result[0].sense_id == "bank.n.01"
        assert result[0].definition == "financial institution"
        assert result[1].sense_id == "bank.n.02"

    def test_extract_word_senses_with_term_filter(self, service):
        """Test extracting word senses filtered by term."""
        # Create response with multiple terms
        token1 = TokenData(
            text="bank",
            wordnet=WordNetData(
                synsets=[
                    {
                        "name": "bank.n.01",
                        "definition": "financial institution",
                        "domain": "noun.group"
                    }
                ]
            )
        )
        token2 = TokenData(
            text="river",
            wordnet=WordNetData(
                synsets=[
                    {
                        "name": "river.n.01",
                        "definition": "large natural stream of water",
                        "domain": "noun.object"
                    }
                ]
            )
        )

        nlp_response = NLPAnalysisResponse(
            text="bank river",
            tokens=[token1, token2],
            entities=[]
        )

        # Execute - filter for "bank" only
        result = service.extract_word_senses(nlp_response, term="bank")

        # Assert
        assert len(result) == 1
        assert result[0].term == "bank"

    def test_extract_word_senses_no_synsets(self, service):
        """Test extracting from token with no synsets."""
        # Create token without wordnet data
        token = TokenData(text="the")

        nlp_response = NLPAnalysisResponse(
            text="the",
            tokens=[token],
            entities=[]
        )

        # Execute
        result = service.extract_word_senses(nlp_response)

        # Assert
        assert len(result) == 0

    def test_extract_word_senses_malformed_synset(self, service):
        """Test handling malformed synset data."""
        # Create token with malformed synset
        token = TokenData(
            text="test",
            wordnet=WordNetData(
                synsets=[
                    {"name": "test.n.01"},  # Missing definition
                    {"definition": "test definition"},  # Missing name
                    {"name": "test.n.02", "definition": "valid synset"}  # Valid
                ]
            )
        )

        nlp_response = NLPAnalysisResponse(
            text="test",
            tokens=[token],
            entities=[]
        )

        # Execute
        result = service.extract_word_senses(nlp_response)

        # Assert - should only extract valid synset
        assert len(result) == 1
        assert result[0].sense_id == "test.n.02"

    def test_update_word_senses_conservative_mode(self, service, mock_db, sample_node, sample_word_senses):
        """Test conservative update preserves matching senses."""
        # Setup - node has existing senses
        existing_senses = [
            WordSense(
                term="bank",
                sense_type="wordnet",
                sense_id="bank.n.01",
                definition="financial institution",
                domain="noun.group"
            ),
            WordSense(
                term="bank",
                sense_type="wordnet",
                sense_id="bank.n.03",
                definition="building housing a bank",
                domain="noun.artifact"
            )
        ]
        sample_node.word_senses = json.dumps([s.model_dump() for s in existing_senses])

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node

        # New senses include bank.n.01 (match) and bank.n.02 (new), but not bank.n.03
        new_senses = [
            WordSense(
                term="bank",
                sense_type="wordnet",
                sense_id="bank.n.01",
                definition="financial institution",
                domain="noun.group"
            ),
            WordSense(
                term="bank",
                sense_type="wordnet",
                sense_id="bank.n.02",
                definition="sloping land beside water",
                domain="noun.object"
            )
        ]

        # Execute
        result = service.update_word_senses("test-node-123", new_senses, conservative=True)

        # Assert
        # Should preserve bank.n.01, add bank.n.02, remove bank.n.03
        assert len(result) == 2
        sense_ids = {s.sense_id for s in result}
        assert "bank.n.01" in sense_ids  # Preserved
        assert "bank.n.02" in sense_ids  # Added
        assert "bank.n.03" not in sense_ids  # Removed
        assert sample_node.version == 2

    def test_update_word_senses_non_conservative_mode(self, service, mock_db, sample_node, sample_word_senses):
        """Test non-conservative update replaces all senses."""
        # Setup - node has existing senses
        existing_senses = [
            WordSense(
                term="bank",
                sense_type="wordnet",
                sense_id="bank.n.03",
                definition="building housing a bank",
                domain="noun.artifact"
            )
        ]
        sample_node.word_senses = json.dumps([s.model_dump() for s in existing_senses])

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node

        # Execute
        result = service.update_word_senses("test-node-123", sample_word_senses, conservative=False)

        # Assert - should completely replace with new senses
        assert len(result) == 2
        sense_ids = {s.sense_id for s in result}
        assert "bank.n.01" in sense_ids
        assert "bank.n.02" in sense_ids
        assert "bank.n.03" not in sense_ids

    def test_update_word_senses_node_not_found(self, service, mock_db, sample_word_senses):
        """Test updating senses when node doesn't exist."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Execute & Assert
        with pytest.raises(ValueError, match="StructureNode not found"):
            service.update_word_senses("nonexistent-node", sample_word_senses)

    def test_get_word_senses_success(self, service, mock_db, sample_node, sample_word_senses):
        """Test successfully retrieving word senses."""
        # Setup
        sample_node.word_senses = json.dumps([s.model_dump() for s in sample_word_senses])

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node

        # Execute
        result = service.get_word_senses("test-node-123")

        # Assert
        assert len(result) == 2
        assert result[0].sense_id == "bank.n.01"
        assert result[1].sense_id == "bank.n.02"

    def test_get_word_senses_empty(self, service, mock_db, sample_node):
        """Test retrieving senses when node has none."""
        # Test various empty states
        test_cases = [
            None,  # NULL
            "",    # Empty string
            "[]",  # Empty JSON array
        ]

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node

        for empty_value in test_cases:
            sample_node.word_senses = empty_value

            # Execute
            result = service.get_word_senses("test-node-123")

            # Assert
            assert result == []

    def test_get_word_senses_malformed_json(self, service, mock_db, sample_node):
        """Test handling of malformed JSON."""
        # Setup
        sample_node.word_senses = "{invalid json"

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node

        # Execute
        result = service.get_word_senses("test-node-123")

        # Assert - should return empty list, not raise exception
        assert result == []

    def test_get_word_senses_not_array(self, service, mock_db, sample_node):
        """Test handling when JSON is not an array."""
        # Setup
        sample_node.word_senses = json.dumps({"not": "an array"})

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node

        # Execute
        result = service.get_word_senses("test-node-123")

        # Assert
        assert result == []

    def test_get_word_senses_invalid_sense_data(self, service, mock_db, sample_node):
        """Test handling when sense data is invalid."""
        # Setup - one valid sense, one invalid
        sample_node.word_senses = json.dumps([
            {
                "term": "bank",
                "sense_type": "wordnet",
                "sense_id": "bank.n.01",
                "definition": "financial institution"
            },  # Valid
            {"invalid": "data"},  # Invalid - missing required fields
        ])

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node

        # Execute
        result = service.get_word_senses("test-node-123")

        # Assert - should return only valid sense
        assert len(result) == 1
        assert result[0].sense_id == "bank.n.01"

    def test_remove_word_senses_success(self, service, mock_db, sample_node, sample_word_senses):
        """Test successfully removing word senses."""
        # Setup
        sample_node.word_senses = json.dumps([s.model_dump() for s in sample_word_senses])

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node

        # Remove one sense
        sense_ids_to_remove = ["bank.n.01"]

        # Execute
        result = service.remove_word_senses("test-node-123", sense_ids_to_remove)

        # Assert
        assert len(result) == 1
        assert result[0].sense_id == "bank.n.02"
        assert sample_node.version == 2

    def test_remove_word_senses_empty_result(self, service, mock_db, sample_node):
        """Test removing all senses leaves empty array."""
        # Setup
        sense = WordSense(
            term="bank",
            sense_type="wordnet",
            sense_id="bank.n.01",
            definition="financial institution"
        )
        sample_node.word_senses = json.dumps([sense.model_dump()])

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node

        # Remove the sense
        sense_ids_to_remove = ["bank.n.01"]

        # Execute
        result = service.remove_word_senses("test-node-123", sense_ids_to_remove)

        # Assert
        assert len(result) == 0
        # Verify JSON is empty array not null
        saved_json = json.loads(sample_node.word_senses)
        assert saved_json == []

    def test_validate_sense_identifier_wordnet_valid(self, service):
        """Test validation of valid WordNet sense identifiers."""
        # Valid WordNet sense IDs
        valid_ids = [
            "bank.n.01",
            "run.v.03",
            "good.a.01",
            "quickly.r.01",
            "similar.s.01",
        ]

        for sense_id in valid_ids:
            # Execute
            result = service.validate_sense_identifier("wordnet", sense_id)

            # Assert
            assert result is True

    def test_validate_sense_identifier_wordnet_invalid_format(self, service):
        """Test validation rejects invalid WordNet format."""
        # Invalid formats
        invalid_ids = [
            "bank",  # Missing POS and number
            "bank.n",  # Missing number
            "bank.01",  # Missing POS
            "bank.x.01",  # Invalid POS
            "bank.n.abc",  # Non-numeric suffix
        ]

        for sense_id in invalid_ids:
            # Execute & Assert
            with pytest.raises(ValueError):
                service.validate_sense_identifier("wordnet", sense_id)

    def test_validate_sense_identifier_wordnet_empty(self, service):
        """Test validation rejects empty sense ID."""
        # Execute & Assert
        with pytest.raises(ValueError, match="cannot be empty"):
            service.validate_sense_identifier("wordnet", "")

    def test_validate_sense_identifier_other_type(self, service):
        """Test validation for non-WordNet sense types."""
        # Execute - should accept any non-empty string for other types
        result = service.validate_sense_identifier("custom", "some-id-123")

        # Assert
        assert result is True

    def test_validate_sense_identifier_other_type_empty(self, service):
        """Test validation rejects empty ID for other types too."""
        # Execute & Assert
        with pytest.raises(ValueError, match="cannot be empty"):
            service.validate_sense_identifier("custom", "")

    def test_get_nodes_with_word_sense(self, service, mock_db):
        """Test finding nodes by word sense."""
        # Setup
        node1 = Mock(spec=StructureNode)
        node1.id = "node-1"
        node1.word_senses = json.dumps([
            {
                "term": "bank",
                "sense_type": "wordnet",
                "sense_id": "bank.n.01",
                "definition": "financial institution"
            }
        ])

        node2 = Mock(spec=StructureNode)
        node2.id = "node-2"
        node2.word_senses = json.dumps([
            {
                "term": "bank",
                "sense_type": "wordnet",
                "sense_id": "bank.n.02",
                "definition": "sloping land"
            }
        ])

        node3 = Mock(spec=StructureNode)
        node3.id = "node-3"
        node3.word_senses = json.dumps([
            {
                "term": "bank",
                "sense_type": "wordnet",
                "sense_id": "bank.n.01",
                "definition": "financial institution"
            }
        ])

        # Setup query mock that returns itself for chaining
        query_mock = Mock()
        query_mock.filter.return_value = query_mock
        query_mock.params.return_value = query_mock
        query_mock.all.return_value = [node1, node3]  # Only nodes with bank.n.01
        mock_db.query.return_value = query_mock

        # Execute
        result = service.get_nodes_with_word_sense("bank.n.01")

        # Assert
        assert len(result) == 2  # node1 and node3
        assert result[0].id == "node-1"
        assert result[1].id == "node-3"

    def test_get_nodes_with_word_sense_with_limit(self, service, mock_db):
        """Test finding nodes with limit."""
        # Setup
        nodes = []
        for i in range(5):
            node = Mock(spec=StructureNode)
            node.id = f"node-{i}"
            node.word_senses = json.dumps([
                {
                    "term": "test",
                    "sense_type": "wordnet",
                    "sense_id": "test.n.01",
                    "definition": "test definition"
                }
            ])
            nodes.append(node)

        # Setup query mock that returns itself for chaining, including limit()
        query_mock = Mock()
        query_mock.filter.return_value = query_mock
        query_mock.params.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.all.return_value = nodes[:3]  # Simulate limit returning first 3
        mock_db.query.return_value = query_mock

        # Execute
        result = service.get_nodes_with_word_sense("test.n.01", limit=3)

        # Assert
        assert len(result) == 3

    def test_commit_failure_rollback(self, service, mock_db, sample_node, sample_word_senses):
        """Test that database rollback occurs on commit failure."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = sample_node
        mock_db.commit.side_effect = Exception("Database error")

        # Execute & Assert
        with pytest.raises(ValueError, match="Failed to update word senses"):
            service.update_word_senses("test-node-123", sample_word_senses)

        # Verify rollback was called
        mock_db.rollback.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
