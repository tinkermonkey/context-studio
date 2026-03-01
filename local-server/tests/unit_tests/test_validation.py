"""Unit tests for validation logic in predicate utilities."""

import sys
import os
import datetime
from uuid import uuid4

# Add the project root to the path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base, StructureNode, Predicate
from database.predicate_utils import (
    validate_term_relationship_predicate,
    validate_predicate_identifier,
)


# Create in-memory SQLite database for testing
@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def sample_domain(db_session):
    """Create a sample domain structure node with predicate set."""

    domain = StructureNode(
        id=str(uuid4()),
        node_type="domain",
        title="Sample Domain",
        definition="Test domain",
        created_at=datetime.datetime.now(datetime.UTC),
        last_modified=datetime.datetime.now(datetime.UTC),
    )
    db_session.add(domain)
    db_session.commit()
    return domain


@pytest.fixture
def sample_domain_no_predicate_set(db_session):
    """Create a sample domain structure node without predicate set."""
    domain = StructureNode(
        id=str(uuid4()),
        node_type="domain",
        title="Domain No Predicates",
        definition="Test domain without predicate set",
        created_at=datetime.datetime.now(datetime.UTC),
        last_modified=datetime.datetime.now(datetime.UTC),
    )
    db_session.add(domain)
    db_session.commit()
    return domain


@pytest.fixture
def sample_predicates(db_session):
    """Create sample predicates."""
    predicates = []

    # Create allowed predicates
    for identifier in ["synonym", "hypernym", "hyponym"]:
        predicate = Predicate(
            id=str(uuid4()),
            identifier=identifier,
            title=identifier.title(),
            definition=f"Test {identifier} predicate",
            date_created=datetime.datetime.now(datetime.UTC),
            date_modified=datetime.datetime.now(datetime.UTC),
        )
        db_session.add(predicate)
        predicates.append(predicate)

    # Create a disallowed predicate
    disallowed_predicate = Predicate(
        id=str(uuid4()),
        identifier="antonym",
        title="Antonym",
        definition="Test antonym predicate",
        date_created=datetime.datetime.now(datetime.UTC),
        date_modified=datetime.datetime.now(datetime.UTC),
    )
    db_session.add(disallowed_predicate)
    predicates.append(disallowed_predicate)

    db_session.commit()
    return predicates


@pytest.fixture
def sample_terms(db_session, sample_domain, sample_domain_no_predicate_set):
    """Create sample terms in different domains."""
    terms = []

    # Terms as children of the domain structure node
    for i in range(2):
        term = StructureNode(
            id=str(uuid4()),
            node_type="term",
            title=f"Term {i}",
            definition=f"Test term {i}",
            parent_node_id=sample_domain.id,
            created_at=datetime.datetime.now(datetime.UTC),
            last_modified=datetime.datetime.now(datetime.UTC),
        )
        db_session.add(term)
        terms.append(term)

    # Term as child of different domain (no predicate set)
    term = StructureNode(
        id=str(uuid4()),
        node_type="term",
        title="Term Different Domain",
        definition="Test term in different domain",
        parent_node_id=sample_domain_no_predicate_set.id,
        created_at=datetime.datetime.now(datetime.UTC),
        last_modified=datetime.datetime.now(datetime.UTC),
    )
    db_session.add(term)
    terms.append(term)

    db_session.commit()
    return terms


class TestValidateTermRelationshipPredicate:
    """Tests for validate_term_relationship_predicate function."""

    def test_different_domains_allows_any_predicate(
        self, db_session, sample_terms, sample_predicates
    ):
        """Test that different domains allow any predicate."""
        same_domain_term = sample_terms[0]
        different_domain_term = sample_terms[2]
        disallowed_predicate = sample_predicates[3]  # antonym

        # Get the parent domain ID for each term
        same_domain_id = same_domain_term.parent_node_id
        different_domain_id = different_domain_term.parent_node_id

        result = validate_term_relationship_predicate(
            same_domain_id, different_domain_id, disallowed_predicate.id, db_session
        )

        assert result is True

    def test_same_domain_with_allowed_predicate(
        self, db_session, sample_terms, sample_predicates
    ):
        """Test that same domain allows predicates in predicate set."""
        term1 = sample_terms[0]
        sample_terms[1]
        allowed_predicate = sample_predicates[0]  # synonym

        # Both terms are in the same domain (same parent_node_id)
        domain_id = term1.parent_node_id

        result = validate_term_relationship_predicate(
            domain_id, domain_id, allowed_predicate.id, db_session
        )

        assert result is True

    def test_same_domain_with_disallowed_predicate(
        self, db_session, sample_terms, sample_predicates
    ):
        """Test that same domain allows all predicates (predicate sets removed)."""
        term1 = sample_terms[0]
        sample_terms[1]
        disallowed_predicate = sample_predicates[3]  # antonym

        # Both terms are in the same domain (same parent_node_id)
        domain_id = term1.parent_node_id

        result = validate_term_relationship_predicate(
            domain_id, domain_id, disallowed_predicate.id, db_session
        )

        assert result is True

    def test_same_domain_no_predicate_set_allows_any(
        self, db_session, sample_domain_no_predicate_set, sample_predicates
    ):
        """Test that domain with no predicate set allows any predicate."""
        disallowed_predicate = sample_predicates[3]  # antonym

        result = validate_term_relationship_predicate(
            sample_domain_no_predicate_set.id,
            sample_domain_no_predicate_set.id,
            disallowed_predicate.id,
            db_session,
        )

        assert result is True

    def test_nonexistent_domain(self, db_session, sample_predicates):
        """Test validation with nonexistent domain (all predicates now allowed)."""
        fake_domain_id = str(uuid4())
        predicate = sample_predicates[0]

        result = validate_term_relationship_predicate(
            fake_domain_id, fake_domain_id, predicate.id, db_session
        )

        assert result is True

    def test_nonexistent_predicate(self, db_session, sample_domain):
        """Test validation with nonexistent predicate (all predicates now allowed)."""
        fake_predicate_id = str(uuid4())

        result = validate_term_relationship_predicate(
            sample_domain.id, sample_domain.id, fake_predicate_id, db_session
        )

        assert result is True

    def test_invalid_predicate_set_json(self, db_session, sample_predicates):
        """Test validation with domain (predicate sets no longer used)."""
        # Create domain structure node - Note: predicate_set is not a field in StructureNode
        # This test verifies that domains without predicate sets allow all predicates
        domain = StructureNode(
            id=str(uuid4()),
            node_type="domain",
            title="Domain Without Predicate Set",
            definition="Test domain without predicate set",
            created_at=datetime.datetime.now(datetime.UTC),
            last_modified=datetime.datetime.now(datetime.UTC),
        )
        db_session.add(domain)
        db_session.commit()

        predicate = sample_predicates[0]

        result = validate_term_relationship_predicate(
            domain.id, domain.id, predicate.id, db_session
        )

        assert result is True


class TestValidatePredicateIdentifier:
    """Tests for validate_predicate_identifier function."""

    def test_new_predicate_unique_identifier(self, db_session):
        """Test that new predicate with unique identifier passes validation."""
        result = validate_predicate_identifier("unique_identifier", None, db_session)
        assert result is True

    def test_new_predicate_duplicate_identifier(self, db_session, sample_predicates):
        """Test that new predicate with duplicate identifier fails validation."""
        existing_predicate = sample_predicates[0]

        result = validate_predicate_identifier(
            existing_predicate.identifier, None, db_session
        )
        assert result is False

    def test_update_predicate_same_identifier(self, db_session, sample_predicates):
        """Test that updating predicate with same identifier passes validation."""
        existing_predicate = sample_predicates[0]

        result = validate_predicate_identifier(
            existing_predicate.identifier, existing_predicate.id, db_session
        )
        assert result is True

    def test_update_predicate_different_unique_identifier(
        self, db_session, sample_predicates
    ):
        """Test that updating predicate with unique identifier passes validation."""
        existing_predicate = sample_predicates[0]

        result = validate_predicate_identifier(
            "new_unique_identifier", existing_predicate.id, db_session
        )
        assert result is True

    def test_update_predicate_different_duplicate_identifier(
        self, db_session, sample_predicates
    ):
        """Test that updating predicate with another's identifier fails validation."""
        predicate1 = sample_predicates[0]
        predicate2 = sample_predicates[1]

        result = validate_predicate_identifier(
            predicate2.identifier, predicate1.id, db_session
        )
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__])
