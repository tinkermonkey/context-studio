"""
Unit tests for WordSenseService.

Tests word sense extraction, filtering, validation, and error handling.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
import json  # noqa: E402
from unittest.mock import Mock  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from services.word_sense_service import WordSenseService  # noqa: E402
from services.exceptions import ValidationError  # noqa: E402
from api.models.structure_nodes import WordSense  # noqa: E402
from database.models import StructureNode  # noqa: E402
from database.enums import NodeType  # noqa: E402
from nlp.models import NLPAnalysisResponse, TokenData, WordNetData  # noqa: E402, E501


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
                    {"name": "test.n.02", "definition": "valid synset"}  # Valid  # noqa: E501
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

    def test_update_word_senses_conservative_mode(self, service, mock_db, sample_node, sample_word_senses):  # noqa: E501
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
        sample_node.word_senses = json.dumps([s.model_dump() for s in existing_senses])  # noqa: E501

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node  # noqa: E501

        # New senses include bank.n.01 (match) and bank.n.02 (new), but not bank.n.03  # noqa: E501
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
        result = service.update_word_senses("test-node-123", new_senses, conservative=True)  # noqa: E501

        # Assert
        # Should preserve bank.n.01, add bank.n.02, remove bank.n.03
        assert len(result) == 2
        sense_ids = {s.sense_id for s in result}
        assert "bank.n.01" in sense_ids  # Preserved
        assert "bank.n.02" in sense_ids  # Added
        assert "bank.n.03" not in sense_ids  # Removed
        assert sample_node.version == 2

    def test_update_word_senses_non_conservative_mode(self, service, mock_db, sample_node, sample_word_senses):  # noqa: E501
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
        sample_node.word_senses = json.dumps([s.model_dump() for s in existing_senses])  # noqa: E501

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node  # noqa: E501

        # Execute
        result = service.update_word_senses("test-node-123", sample_word_senses, conservative=False)  # noqa: E501

        # Assert - should completely replace with new senses
        assert len(result) == 2
        sense_ids = {s.sense_id for s in result}
        assert "bank.n.01" in sense_ids
        assert "bank.n.02" in sense_ids
        assert "bank.n.03" not in sense_ids

    def test_update_word_senses_node_not_found(self, service, mock_db, sample_word_senses):  # noqa: E501
        """Test updating senses when node doesn't exist."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = None  # noqa: E501

        # Execute & Assert
        with pytest.raises(ValueError, match="StructureNode not found"):
            service.update_word_senses("nonexistent-node", sample_word_senses)

    def test_get_word_senses_success(self, service, mock_db, sample_node, sample_word_senses):  # noqa: E501
        """Test successfully retrieving word senses."""
        # Setup
        sample_node.word_senses = json.dumps([s.model_dump() for s in sample_word_senses])  # noqa: E501

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node  # noqa: E501

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

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node  # noqa: E501

        for empty_value in test_cases:
            sample_node.word_senses = empty_value

            # Execute
            result = service.get_word_senses("test-node-123")

            # Assert
            assert result == []

    def test_get_word_senses_malformed_json(self, service, mock_db, sample_node):  # noqa: E501
        """Test handling of malformed JSON - should raise ValidationError."""
        # Setup
        sample_node.word_senses = "{invalid json"

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node  # noqa: E501

        # Execute & Assert - should raise ValidationError for corrupted data
        with pytest.raises(ValidationError, match="Word sense data.*corrupted"):  # noqa: E501
            service.get_word_senses("test-node-123")

    def test_get_word_senses_not_array(self, service, mock_db, sample_node):
        """Test handling when JSON is not an array."""
        # Setup
        sample_node.word_senses = json.dumps({"not": "an array"})

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node  # noqa: E501

        # Execute
        result = service.get_word_senses("test-node-123")

        # Assert
        assert result == []

    def test_get_word_senses_invalid_sense_data(self, service, mock_db, sample_node):  # noqa: E501
        """Test handling when sense data is invalid - should raise ValidationError."""  # noqa: E501
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

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node  # noqa: E501

        # Execute & Assert - should raise ValidationError for partially corrupted data  # noqa: E501
        with pytest.raises(ValidationError, match="Word sense data is partially corrupted"):  # noqa: E501
            service.get_word_senses("test-node-123")

    def test_remove_word_senses_success(self, service, mock_db, sample_node, sample_word_senses):  # noqa: E501
        """Test successfully removing word senses."""
        # Setup
        sample_node.word_senses = json.dumps([s.model_dump() for s in sample_word_senses])  # noqa: E501

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node  # noqa: E501

        # Remove one sense
        sense_ids_to_remove = ["bank.n.01"]

        # Execute
        result = service.remove_word_senses("test-node-123", sense_ids_to_remove)  # noqa: E501

        # Assert
        assert len(result) == 1
        assert result[0].sense_id == "bank.n.02"
        assert sample_node.version == 2

    def test_remove_word_senses_empty_result(self, service, mock_db, sample_node):  # noqa: E501
        """Test removing all senses leaves empty array."""
        # Setup
        sense = WordSense(
            term="bank",
            sense_type="wordnet",
            sense_id="bank.n.01",
            definition="financial institution"
        )
        sample_node.word_senses = json.dumps([sense.model_dump()])

        mock_db.query.return_value.filter.return_value.first.return_value = sample_node  # noqa: E501

        # Remove the sense
        sense_ids_to_remove = ["bank.n.01"]

        # Execute
        result = service.remove_word_senses("test-node-123", sense_ids_to_remove)  # noqa: E501

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
        query_mock.all.return_value = [node1, node3]  # Only nodes with bank.n.01  # noqa: E501
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
        query_mock.all.return_value = nodes[:3]  # Simulate limit returning first 3  # noqa: E501
        mock_db.query.return_value = query_mock

        # Execute
        result = service.get_nodes_with_word_sense("test.n.01", limit=3)

        # Assert
        assert len(result) == 3

    def test_commit_failure_rollback(self, service, mock_db, sample_node, sample_word_senses):  # noqa: E501
        """Test that database rollback occurs on commit failure."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = sample_node  # noqa: E501
        mock_db.commit.side_effect = Exception("Database error")

        # Execute & Assert
        with pytest.raises(ValueError, match="Failed to update word senses"):
            service.update_word_senses("test-node-123", sample_word_senses)

        # Verify rollback was called
        mock_db.rollback.assert_called_once()

    def test_update_selected_senses_success(self, service, mock_db, sample_node):  # noqa: E501
        """Test successfully updating selected word senses."""
        # Setup - node has no existing senses
        sample_node.word_senses = None
        mock_db.query.return_value.filter.return_value.first.return_value = sample_node  # noqa: E501

        # Create selected senses for a single word
        selected_senses = [
            WordSense(
                term="bank",
                sense_type="wordnet",
                sense_id="bank.n.01",
                definition="financial institution",
                domain="noun.group"
            )
        ]

        # Execute
        result = service.update_selected_senses("test-node-123", selected_senses)  # noqa: E501

        # Assert
        assert len(result) == 1
        assert result[0].sense_id == "bank.n.01"
        assert result[0].term == "bank"
        assert sample_node.version == 2
        mock_db.commit.assert_called_once()

    def test_update_selected_senses_conservative_merge(self, service, mock_db, sample_node):  # noqa: E501
        """Test conservative merge preserves senses for other words."""
        # Setup - node has existing senses for two different words
        existing_senses = [
            WordSense(
                term="bank",
                sense_type="wordnet",
                sense_id="bank.n.02",
                definition="sloping land beside water",
                domain="noun.object"
            ),
            WordSense(
                term="account",
                sense_type="wordnet",
                sense_id="account.n.01",
                definition="a record or narrative description",
                domain="noun.communication"
            )
        ]
        sample_node.word_senses = json.dumps([s.model_dump() for s in existing_senses])  # noqa: E501
        mock_db.query.return_value.filter.return_value.first.return_value = sample_node  # noqa: E501

        # Update only "bank", not "account"
        selected_senses = [
            WordSense(
                term="bank",
                sense_type="wordnet",
                sense_id="bank.n.01",
                definition="financial institution",
                domain="noun.group"
            )
        ]

        # Execute
        result = service.update_selected_senses("test-node-123", selected_senses)  # noqa: E501

        # Assert
        assert len(result) == 2  # Both words should still be present
        sense_by_term = {s.term: s for s in result}

        # "bank" should be updated
        assert "bank" in sense_by_term
        assert sense_by_term["bank"].sense_id == "bank.n.01"

        # "account" should be preserved
        assert "account" in sense_by_term
        assert sense_by_term["account"].sense_id == "account.n.01"

        assert sample_node.version == 2

    def test_update_selected_senses_replaces_word(self, service, mock_db, sample_node):  # noqa: E501
        """Test that updating a word replaces all its previous senses."""
        # Setup - node has multiple senses for "bank"
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
                sense_id="bank.n.02",
                definition="sloping land beside water",
                domain="noun.object"
            )
        ]
        sample_node.word_senses = json.dumps([s.model_dump() for s in existing_senses])  # noqa: E501
        mock_db.query.return_value.filter.return_value.first.return_value = sample_node  # noqa: E501

        # Update "bank" with a single new sense
        selected_senses = [
            WordSense(
                term="bank",
                sense_type="wordnet",
                sense_id="bank.n.03",
                definition="building housing a bank",
                domain="noun.artifact"
            )
        ]

        # Execute
        result = service.update_selected_senses("test-node-123", selected_senses)  # noqa: E501

        # Assert - only the new sense should remain
        assert len(result) == 1
        assert result[0].sense_id == "bank.n.03"

    def test_update_selected_senses_multiple_words(self, service, mock_db, sample_node):  # noqa: E501
        """Test updating senses for multiple words at once."""
        # Setup - node has no existing senses
        sample_node.word_senses = None
        mock_db.query.return_value.filter.return_value.first.return_value = sample_node  # noqa: E501

        # Update with senses for two different words
        selected_senses = [
            WordSense(
                term="bank",
                sense_type="wordnet",
                sense_id="bank.n.01",
                definition="financial institution",
                domain="noun.group"
            ),
            WordSense(
                term="account",
                sense_type="wordnet",
                sense_id="account.n.02",
                definition="a formal contractual relationship",
                domain="noun.state"
            )
        ]

        # Execute
        result = service.update_selected_senses("test-node-123", selected_senses)  # noqa: E501

        # Assert
        assert len(result) == 2
        sense_ids = {s.sense_id for s in result}
        assert "bank.n.01" in sense_ids
        assert "account.n.02" in sense_ids

    def test_update_selected_senses_invalid_sense_id(self, service, mock_db, sample_node):  # noqa: E501
        """Test validation rejects invalid sense IDs."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = sample_node  # noqa: E501

        # Create senses with invalid sense_id
        selected_senses = [
            WordSense(
                term="bank",
                sense_type="wordnet",
                sense_id="invalid-format",  # Invalid WordNet format
                definition="test definition"
            )
        ]

        # Execute & Assert
        with pytest.raises(ValueError, match="Invalid sense"):
            service.update_selected_senses("test-node-123", selected_senses)

        # Verify no commit occurred
        mock_db.commit.assert_not_called()

    def test_update_selected_senses_node_not_found(self, service, mock_db):
        """Test error when updating senses for non-existent node."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = None  # noqa: E501

        selected_senses = [
            WordSense(
                term="bank",
                sense_type="wordnet",
                sense_id="bank.n.01",
                definition="financial institution"
            )
        ]

        # Execute & Assert
        with pytest.raises(ValueError, match="StructureNode not found"):
            service.update_selected_senses("nonexistent-node", selected_senses)

    def test_update_selected_senses_case_insensitive_term_matching(self, service, mock_db, sample_node):  # noqa: E501
        """Test that term matching is case-insensitive."""
        # Setup - existing sense with lowercase term
        existing_senses = [
            WordSense(
                term="bank",
                sense_type="wordnet",
                sense_id="bank.n.01",
                definition="financial institution",
                domain="noun.group"
            )
        ]
        sample_node.word_senses = json.dumps([s.model_dump() for s in existing_senses])  # noqa: E501
        mock_db.query.return_value.filter.return_value.first.return_value = sample_node  # noqa: E501

        # Update with uppercase term
        selected_senses = [
            WordSense(
                term="BANK",  # Uppercase
                sense_type="wordnet",
                sense_id="bank.n.02",
                definition="sloping land beside water",
                domain="noun.object"
            )
        ]

        # Execute
        result = service.update_selected_senses("test-node-123", selected_senses)  # noqa: E501

        # Assert - should replace the existing "bank" sense despite case difference  # noqa: E501
        assert len(result) == 1
        assert result[0].sense_id == "bank.n.02"

    def test_update_selected_senses_commit_failure(self, service, mock_db, sample_node):  # noqa: E501
        """Test rollback on commit failure."""
        # Setup
        sample_node.word_senses = None
        mock_db.query.return_value.filter.return_value.first.return_value = sample_node  # noqa: E501
        mock_db.commit.side_effect = Exception("Database error")

        selected_senses = [
            WordSense(
                term="bank",
                sense_type="wordnet",
                sense_id="bank.n.01",
                definition="financial institution"
            )
        ]

        # Execute & Assert
        with pytest.raises(ValueError, match="Failed to update selected word senses"):  # noqa: E501
            service.update_selected_senses("test-node-123", selected_senses)

        # Verify rollback was called
        mock_db.rollback.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
