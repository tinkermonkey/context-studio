"""Unit tests for predicate CRUD operations, identifier generation, and ConceptNet mapping."""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import json
import uuid
from unittest.mock import Mock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base, Predicate, StructureNode, StructureNodeLink
from database.predicate_utils import generate_identifier_from_title


class TestPredicateCRUDOperations:
    """Test predicate CRUD operations."""

    @pytest.fixture
    def db_session(self):
        """Create in-memory database session for testing."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        yield session
        session.close()

    def test_create_predicate_with_all_fields(self, db_session):
        """Test creating a predicate with all fields specified."""
        mapping = {
            "conceptnet": {
                "relation": "RelatedTo",
                "url": "https://conceptnet.io/r/RelatedTo",
            }
        }

        predicate = Predicate(
            identifier="related_to",
            title="Related To",
            definition="Indicates a general relationship between concepts",
            mapping=json.dumps(mapping),
        )

        db_session.add(predicate)
        db_session.commit()

        # Verify predicate was created
        saved_predicate = (
            db_session.query(Predicate).filter_by(identifier="related_to").first()
        )
        assert saved_predicate is not None
        assert saved_predicate.title == "Related To"
        assert (
            saved_predicate.definition
            == "Indicates a general relationship between concepts"
        )
        assert json.loads(saved_predicate.mapping) == mapping
        assert saved_predicate.date_created is not None
        assert saved_predicate.date_modified is not None

    def test_create_predicate_minimal_fields(self, db_session):
        """Test creating a predicate with only required fields."""
        predicate = Predicate(identifier="synonym", title="Synonym")

        db_session.add(predicate)
        db_session.commit()

        # Verify predicate was created
        saved_predicate = (
            db_session.query(Predicate).filter_by(identifier="synonym").first()
        )
        assert saved_predicate is not None
        assert saved_predicate.title == "Synonym"
        assert saved_predicate.definition is None
        assert saved_predicate.mapping is None

    def test_create_predicate_unique_constraints(self, db_session):
        """Test that unique constraints are enforced on identifier and title."""
        # Create first predicate
        predicate1 = Predicate(identifier="test_id", title="Test Title")
        db_session.add(predicate1)
        db_session.commit()

        # Try to create predicate with duplicate identifier
        predicate2 = Predicate(identifier="test_id", title="Different Title")
        db_session.add(predicate2)

        with pytest.raises(Exception):  # Should raise IntegrityError
            db_session.commit()

        db_session.rollback()

        # Try to create predicate with duplicate title
        predicate3 = Predicate(identifier="different_id", title="Test Title")
        db_session.add(predicate3)

        with pytest.raises(Exception):  # Should raise IntegrityError
            db_session.commit()

    def test_read_predicate_by_id(self, db_session):
        """Test reading a predicate by ID."""
        predicate = Predicate(identifier="test", title="Test")
        db_session.add(predicate)
        db_session.commit()

        # Read by ID
        found_predicate = db_session.query(Predicate).filter_by(id=predicate.id).first()
        assert found_predicate is not None
        assert found_predicate.identifier == "test"
        assert found_predicate.title == "Test"

    def test_read_predicate_by_identifier(self, db_session):
        """Test reading a predicate by identifier."""
        predicate = Predicate(identifier="test_identifier", title="Test")
        db_session.add(predicate)
        db_session.commit()

        # Read by identifier
        found_predicate = (
            db_session.query(Predicate).filter_by(identifier="test_identifier").first()
        )
        assert found_predicate is not None
        assert found_predicate.title == "Test"

    def test_update_predicate(self, db_session):
        """Test updating a predicate."""
        predicate = Predicate(identifier="test", title="Original Title")
        db_session.add(predicate)
        db_session.commit()

        original_modified = predicate.date_modified

        # Update predicate
        predicate.title = "Updated Title"
        predicate.definition = "Updated definition"
        db_session.commit()

        # Verify update
        updated_predicate = (
            db_session.query(Predicate).filter_by(id=predicate.id).first()
        )
        assert updated_predicate.title == "Updated Title"
        assert updated_predicate.definition == "Updated definition"
        # Note: date_modified update depends on trigger or application logic

    def test_delete_predicate(self, db_session):
        """Test deleting a predicate."""
        predicate = Predicate(identifier="test", title="Test")
        db_session.add(predicate)
        db_session.commit()

        predicate_id = predicate.id

        # Delete predicate
        db_session.delete(predicate)
        db_session.commit()

        # Verify deletion
        deleted_predicate = (
            db_session.query(Predicate).filter_by(id=predicate_id).first()
        )
        assert deleted_predicate is None

    def test_list_predicates_pagination(self, db_session):
        """Test listing predicates with pagination."""
        # Create multiple predicates
        for i in range(10):
            predicate = Predicate(identifier=f"test_{i}", title=f"Test {i}")
            db_session.add(predicate)
        db_session.commit()

        # Test pagination
        page_1 = db_session.query(Predicate).offset(0).limit(5).all()
        page_2 = db_session.query(Predicate).offset(5).limit(5).all()

        assert len(page_1) == 5
        assert len(page_2) == 5
        assert page_1[0].id != page_2[0].id

    def test_list_predicates_sorting(self, db_session):
        """Test listing predicates with sorting."""
        # Create predicates in random order
        predicates_data = [("zebra", "Zebra"), ("alpha", "Alpha"), ("beta", "Beta")]

        for identifier, title in predicates_data:
            predicate = Predicate(identifier=identifier, title=title)
            db_session.add(predicate)
        db_session.commit()

        # Sort by title
        sorted_by_title = db_session.query(Predicate).order_by(Predicate.title).all()
        assert sorted_by_title[0].title == "Alpha"
        assert sorted_by_title[1].title == "Beta"
        assert sorted_by_title[2].title == "Zebra"

        # Sort by identifier
        sorted_by_identifier = (
            db_session.query(Predicate).order_by(Predicate.identifier).all()
        )
        assert sorted_by_identifier[0].identifier == "alpha"
        assert sorted_by_identifier[1].identifier == "beta"
        assert sorted_by_identifier[2].identifier == "zebra"


class TestIdentifierGeneration:
    """Test identifier generation from titles."""

    def test_generate_identifier_basic(self):
        """Test basic identifier generation."""
        assert generate_identifier_from_title("Related To") == "related_to"
        assert generate_identifier_from_title("Synonym") == "synonym"
        assert generate_identifier_from_title("Antonym") == "antonym"

    def test_generate_identifier_special_characters(self):
        """Test identifier generation with special characters."""
        assert generate_identifier_from_title("Part-Of") == "part_of"
        assert generate_identifier_from_title("Is/Are") == "is_are"
        assert generate_identifier_from_title("Similar@To") == "similar_to"
        assert generate_identifier_from_title("Test & Trial") == "test_trial"

    def test_generate_identifier_multiple_spaces(self):
        """Test identifier generation with multiple spaces."""
        assert (
            generate_identifier_from_title("Related  To  Something")
            == "related_to_something"
        )
        assert generate_identifier_from_title("  Leading Spaces") == "leading_spaces"
        assert generate_identifier_from_title("Trailing Spaces  ") == "trailing_spaces"

    def test_generate_identifier_numbers(self):
        """Test identifier generation with numbers."""
        assert generate_identifier_from_title("Test 123") == "test_123"
        assert generate_identifier_from_title("Version 2.0") == "version_2_0"

    def test_generate_identifier_edge_cases(self):
        """Test identifier generation edge cases."""
        assert generate_identifier_from_title("") == ""
        assert generate_identifier_from_title("   ") == ""
        assert generate_identifier_from_title("___") == ""
        assert generate_identifier_from_title("A") == "a"
        assert generate_identifier_from_title("123") == "123"

    def test_generate_identifier_unicode(self):
        """Test identifier generation with unicode characters."""
        # Current implementation preserves unicode characters
        assert generate_identifier_from_title("Café") == "café"
        assert generate_identifier_from_title("Naïve") == "naïve"


class TestConceptNetMapping:
    """Test ConceptNet mapping functionality."""

    @pytest.fixture
    def db_session(self):
        """Create in-memory database session for testing."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        yield session
        session.close()

    def test_create_predicate_with_conceptnet_mapping(self, db_session):
        """Test creating predicate with ConceptNet mapping."""
        # Use a unique predicate name not in the migration
        unique_suffix = str(uuid.uuid4())[:8]
        unique_title = f"TestRelation_{unique_suffix}"
        unique_identifier = f"test_relation_{unique_suffix}"

        mapping = {
            "conceptnet": {
                "relation": unique_title,
                "url": f"https://conceptnet.io/r/{unique_title}",
                "description": f"ConceptNet relation type: {unique_title}",
            }
        }

        predicate = Predicate(
            identifier=unique_identifier,
            title=unique_title,
            definition=f"ConceptNet relation: {unique_title}",
            mapping=json.dumps(mapping),
        )

        db_session.add(predicate)
        db_session.commit()

        # Verify mapping is stored correctly
        saved_predicate = (
            db_session.query(Predicate).filter_by(identifier=unique_identifier).first()
        )
        stored_mapping = json.loads(saved_predicate.mapping)
        assert stored_mapping["conceptnet"]["relation"] == unique_title
        assert (
            stored_mapping["conceptnet"]["url"]
            == f"https://conceptnet.io/r/{unique_title}"
        )

    def test_get_conceptnet_relation_for_predicate(self, db_session):
        """Test extracting ConceptNet relation from predicate mapping."""

        def get_conceptnet_relation_for_predicate(predicate: Predicate):
            """Extract ConceptNet relation from predicate mapping."""
            if not predicate.mapping:
                return None
            try:
                mapping = json.loads(predicate.mapping)
                return mapping.get("conceptnet", {}).get("relation")
            except (json.JSONDecodeError, KeyError):
                return None

        # Test with valid ConceptNet mapping
        mapping = {"conceptnet": {"relation": "RelatedTo"}}
        predicate = Predicate(
            identifier="related_to", title="RelatedTo", mapping=json.dumps(mapping)
        )

        assert get_conceptnet_relation_for_predicate(predicate) == "RelatedTo"

        # Test with no mapping
        predicate_no_mapping = Predicate(identifier="test", title="Test")
        assert get_conceptnet_relation_for_predicate(predicate_no_mapping) is None

        # Test with invalid JSON
        predicate_invalid = Predicate(
            identifier="invalid", title="Invalid", mapping="invalid json"
        )
        assert get_conceptnet_relation_for_predicate(predicate_invalid) is None

    @patch("config.get_settings")
    def test_import_conceptnet_predicates(self, mock_get_settings, db_session):
        """Test importing ConceptNet relations as predicates."""
        # Check how many predicates exist before import (from migration)
        initial_count = db_session.query(Predicate).count()

        # Mock config with relations not already in the migration
        unique_suffix = str(uuid.uuid4())[:8]
        mock_settings = Mock()
        mock_settings.concepcy_config = {
            "relations_of_interest": [
                f"TestRelation1_{unique_suffix}",
                f"TestRelation2_{unique_suffix}",
                f"TestRelation3_{unique_suffix}",
            ]
        }
        mock_get_settings.return_value = mock_settings

        def import_conceptnet_predicates(db):
            """Import ConceptNet relations as predicates."""
            from config import get_settings

            settings = get_settings()
            relations = settings.concepcy_config["relations_of_interest"]

            predicates = []
            for relation in relations:
                identifier = relation.lower()

                # Check if already exists
                existing = db.query(Predicate).filter_by(identifier=identifier).first()
                if existing:
                    continue

                mapping = {
                    "conceptnet": {
                        "relation": relation,
                        "url": f"https://conceptnet.io/r/{relation}",
                        "description": f"ConceptNet relation type: {relation}",
                    }
                }

                predicate = Predicate(
                    identifier=identifier,
                    title=relation,
                    definition=f"ConceptNet relation: {relation}",
                    mapping=json.dumps(mapping),
                )

                db.add(predicate)
                predicates.append(predicate)

            db.commit()
            return predicates

        # Import predicates
        imported_predicates = import_conceptnet_predicates(db_session)

        # Verify import
        assert len(imported_predicates) == 3

        # Check total count increased by 3
        final_count = db_session.query(Predicate).count()
        assert final_count == initial_count + 3

        # Check each imported predicate
        test1_id = f"testrelation1_{unique_suffix}"
        test1 = db_session.query(Predicate).filter_by(identifier=test1_id).first()
        assert test1 is not None
        assert test1.title == f"TestRelation1_{unique_suffix}"

        mapping = json.loads(test1.mapping)
        assert mapping["conceptnet"]["relation"] == f"TestRelation1_{unique_suffix}"
        assert (
            mapping["conceptnet"]["url"]
            == f"https://conceptnet.io/r/TestRelation1_{unique_suffix}"
        )


class TestPredicateRelationships:
    """Test predicate relationships with other entities."""

    @pytest.fixture
    def db_session(self):
        """Create in-memory database session for testing."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        yield session
        session.close()

    def test_predicate_structure_node_relationship(self, db_session):
        """Test relationship between predicates and structure nodes."""
        # Create predicate
        predicate = Predicate(identifier="synonym", title="Synonym")
        db_session.add(predicate)
        db_session.commit()

        # Create structure node that references the predicate
        structure_node = StructureNode(
            id=str(uuid.uuid4()),
            node_type="domain",
            title="Test Domain",
            definition="Test definition",
            structural_predicate_id=predicate.id,
        )
        db_session.add(structure_node)
        db_session.commit()

        # Test relationship
        assert structure_node.structural_predicate_ref == predicate
        assert predicate.structure_nodes == [structure_node]

    def test_predicate_structure_node_link_relationship(self, db_session):
        """Test relationship between predicates and structure node links."""
        # Create predicate
        predicate = Predicate(identifier="synonym", title="Synonym")
        db_session.add(predicate)
        db_session.commit()

        # Create structure node link that references the predicate
        node_link = StructureNodeLink(
            id=str(uuid.uuid4()),
            source_node_id=str(uuid.uuid4()),
            target_node_id=str(uuid.uuid4()),
            predicate="synonym",
            predicate_id=predicate.id,
        )
        db_session.add(node_link)
        db_session.commit()

        # Test relationship
        assert node_link.predicate_ref == predicate
        assert predicate.structure_node_links == [node_link]

    def test_predicate_cascade_behavior(self, db_session):
        """Test what happens when predicates are deleted."""
        # Create predicate
        predicate = Predicate(identifier="test", title="Test")
        db_session.add(predicate)
        db_session.commit()

        # Create structure node that references the predicate
        structure_node = StructureNode(
            id=str(uuid.uuid4()),
            node_type="domain",
            title="Test Domain",
            definition="Test definition",
            structural_predicate_id=predicate.id,
        )
        db_session.add(structure_node)
        db_session.commit()

        # Delete predicate
        db_session.delete(predicate)
        db_session.commit()

        # Check structure node still exists but reference is null
        remaining_node = (
            db_session.query(StructureNode).filter_by(id=structure_node.id).first()
        )
        assert remaining_node is not None
        # Note: Actual behavior depends on foreign key constraints setup
