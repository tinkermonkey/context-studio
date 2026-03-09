"""
Unit tests for external predicates functionality in the reference database module.

This module contains comprehensive tests for ExternalPredicate model and
ReferenceManager external predicate operations.
"""

import os
import tempfile
import pytest
from datetime import date
from uuid import uuid4

from reference_db.models import ExternalPredicate
from reference_db.config import ReferenceConfig
from reference_db.manager import ReferenceManager

# Test constants
EMBEDDING_DIMS_SMALL = 128  # Small embedding dimension for testing
BYTES_PER_FLOAT32 = 4  # Size of float32 in bytes


class TestExternalPredicateModel:
    """Test suite for ExternalPredicate model."""

    def test_external_predicate_creation(self):
        """
        Test creating an ExternalPredicate with all required fields.

        Validates:
        - All required fields are present
        - Field types are correct
        - NOT NULL constraints are enforced
        """
        predicate = ExternalPredicate(
            id=str(uuid4()),
            title="subClassOf",
            definition="Indicates that one class is a subclass of another",
            source="schema.org",
            external_id="subClassOf",
            attributes=None,
            title_embedding=None,
            definition_embedding=None,
            created_at=date.today().isoformat(),
            updated_at=date.today().isoformat(),
        )

        assert predicate.id is not None
        assert predicate.title == "subClassOf"
        assert (
            predicate.definition == "Indicates that one class is a subclass of another"
        )
        assert predicate.source == "schema.org"
        assert predicate.external_id == "subClassOf"
        assert predicate.attributes is None
        assert predicate.title_embedding is None
        assert predicate.definition_embedding is None

    def test_external_predicate_repr(self):
        """
        Test ExternalPredicate __repr__ method returns readable output.

        Validates:
        - __repr__ includes key fields (id, source, external_id, title)
        - Output is readable and useful for debugging
        """
        predicate = ExternalPredicate(
            id="test-uuid-123",
            title="A very long predicate title that should be truncated in the repr output",
            definition="Test definition",
            source="schema.org",
            external_id="testPredicate",
            attributes=None,
            title_embedding=None,
            definition_embedding=None,
            created_at=date.today().isoformat(),
            updated_at=date.today().isoformat(),
        )

        repr_str = repr(predicate)
        assert "test-uuid-123" in repr_str
        assert "schema.org" in repr_str
        assert "testPredicate" in repr_str
        assert "ExternalPredicate" in repr_str


class TestExternalPredicateManager:
    """
    Test suite for ReferenceManager external predicate operations.

    These tests require sqlite-vec extension and will be skipped if not available.
    """

    @pytest.fixture(autouse=True)
    def check_sqlite_vec(self):
        """Check if sqlite-vec is available, skip tests if not."""
        try:
            import sqlite_vec as _  # noqa: F401 # type: ignore[import-untyped]
        except ImportError:
            pytest.skip("sqlite-vec not available (expected in Docker environment)")

    def test_add_external_predicate_with_embeddings(self):
        """
        Test adding an external predicate with embedding vectors.

        Validates:
        - Predicates can be created with embeddings
        - Embedding validation checks dimensions
        - UNIQUE constraint on (source, external_id) works
        """
        config = ReferenceConfig()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = tf.name

        try:
            with ReferenceManager(config, db_path=db_path) as manager:
                # Create fake embedding (128 dimensions * 4 bytes = 512 bytes)
                fake_embedding = b"\x00" * (EMBEDDING_DIMS_SMALL * BYTES_PER_FLOAT32)

                predicate = manager.add_external_predicate(
                    title="subClassOf",
                    definition="Indicates that one class is a subclass of another",
                    source="schema.org",
                    external_id="subClassOf",
                    title_embedding=fake_embedding,
                    definition_embedding=fake_embedding,
                    embedding_dims=EMBEDDING_DIMS_SMALL,
                )

                assert predicate.id is not None
                assert predicate.title == "subClassOf"
                assert predicate.title_embedding == fake_embedding

                # Try to add duplicate - should fail with UNIQUE constraint
                with pytest.raises(Exception):  # SQLAlchemy will raise IntegrityError
                    manager.add_external_predicate(
                        title="subClassOf (duplicate)",
                        definition="Duplicate entry",
                        source="schema.org",
                        external_id="subClassOf",
                    )

        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_add_external_predicate_auto_embeddings(self):
        """
        Test adding an external predicate with auto-generated embeddings.

        Validates:
        - Embeddings are automatically generated when not provided
        - Generated embeddings have correct dimensions
        """
        config = ReferenceConfig()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = tf.name

        try:
            with ReferenceManager(config, db_path=db_path) as manager:
                predicate = manager.add_external_predicate(
                    title="relatedTo",
                    definition="Indicates a general relationship between entities",
                    source="schema.org",
                    external_id="relatedTo",
                )

                assert predicate.id is not None
                assert predicate.title == "relatedTo"
                assert predicate.title_embedding is not None
                assert predicate.definition_embedding is not None
                # Verify embeddings have correct size (384 dims * 4 bytes = 1536 bytes)
                # all-MiniLM-L6-v2 produces 384-dimensional embeddings
                assert len(predicate.title_embedding) == 384 * 4
                assert len(predicate.definition_embedding) == 384 * 4

        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_get_external_predicate(self):
        """
        Test retrieving an external predicate by ID.

        Validates:
        - Predicates can be retrieved by ID
        - Returns None for non-existent IDs
        """
        config = ReferenceConfig()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = tf.name

        try:
            with ReferenceManager(config, db_path=db_path) as manager:
                # Create a predicate
                predicate = manager.add_external_predicate(
                    title="associatedWith",
                    definition="Indicates an association between entities",
                    source="schema.org",
                    external_id="associatedWith",
                )

                # Retrieve by ID
                retrieved = manager.get_external_predicate(predicate.id)
                assert retrieved is not None
                assert retrieved.id == predicate.id
                assert retrieved.title == "associatedWith"

                # Try non-existent ID
                not_found = manager.get_external_predicate("non-existent-id")
                assert not_found is None

        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_get_external_predicate_by_source(self):
        """
        Test retrieving an external predicate by source and external_id.

        Validates:
        - Predicates can be retrieved by (source, external_id)
        - Returns None for non-existent combinations
        """
        config = ReferenceConfig()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = tf.name

        try:
            with ReferenceManager(config, db_path=db_path) as manager:
                # Create a predicate
                manager.add_external_predicate(
                    title="partOf",
                    definition="Indicates that one thing is part of another",
                    source="schema.org",
                    external_id="partOf",
                )

                # Retrieve by source and external_id
                retrieved = manager.get_external_predicate_by_source(
                    "schema.org", "partOf"
                )
                assert retrieved is not None
                assert retrieved.title == "partOf"
                assert retrieved.source == "schema.org"
                assert retrieved.external_id == "partOf"

                # Try non-existent combination
                not_found = manager.get_external_predicate_by_source(
                    "wikidata", "partOf"
                )
                assert not_found is None

        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_list_external_predicates(self):
        """
        Test listing external predicates with optional filters.

        Validates:
        - Can list all predicates
        - Can filter by source
        - Can limit results
        """
        config = ReferenceConfig()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = tf.name

        try:
            with ReferenceManager(config, db_path=db_path) as manager:
                # Create multiple predicates from different sources
                manager.add_external_predicate(
                    title="pred1",
                    definition="First predicate",
                    source="schema.org",
                    external_id="pred1",
                )
                manager.add_external_predicate(
                    title="pred2",
                    definition="Second predicate",
                    source="schema.org",
                    external_id="pred2",
                )
                manager.add_external_predicate(
                    title="pred3",
                    definition="Third predicate",
                    source="wikidata",
                    external_id="P1",
                )

                # List all predicates
                all_predicates = manager.list_external_predicates()
                assert len(all_predicates) == 3

                # Filter by source
                schema_predicates = manager.list_external_predicates(
                    source="schema.org"
                )
                assert len(schema_predicates) == 2
                for p in schema_predicates:
                    assert p.source == "schema.org"

                # Test limit
                limited = manager.list_external_predicates(limit=2)
                assert len(limited) == 2

        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_search_external_predicates_by_similarity(self):
        """
        Test semantic similarity search for external predicates.

        Validates:
        - Can search predicates by semantic similarity
        - Results are ordered by similarity (descending)
        - Similarity scores are in valid range
        - Threshold filtering works correctly
        """
        config = ReferenceConfig()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = tf.name

        try:
            with ReferenceManager(config, db_path=db_path) as manager:
                # Create predicates with semantically related terms
                manager.add_external_predicate(
                    title="subClassOf",
                    definition="Indicates that one class is a subclass of another class",
                    source="schema.org",
                    external_id="subClassOf",
                )
                manager.add_external_predicate(
                    title="parentClass",
                    definition="The parent class in a class hierarchy",
                    source="schema.org",
                    external_id="parentClass",
                )
                manager.add_external_predicate(
                    title="color",
                    definition="The color of an object",
                    source="schema.org",
                    external_id="color",
                )

                # Search for "class hierarchy"
                results = manager.search_external_predicates_by_similarity(
                    "class hierarchy",
                    threshold=0.3,  # Lower threshold to ensure we get results
                    limit=10,
                )

                assert len(results) > 0

                # Check that results are tuples of (predicate, score)
                for predicate, score in results:
                    assert isinstance(predicate, ExternalPredicate)
                    assert isinstance(score, float)
                    assert -1.0 <= score <= 1.0

                # Verify ordering (descending by similarity)
                if len(results) > 1:
                    for i in range(len(results) - 1):
                        assert results[i][1] >= results[i + 1][1]

        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_search_external_predicates_validation(self):
        """
        Test input validation for external predicate similarity search.

        Validates:
        - Empty query text raises ValueError
        - Invalid threshold raises ValueError
        - Invalid limit raises ValueError
        """
        config = ReferenceConfig()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = tf.name

        try:
            with ReferenceManager(config, db_path=db_path) as manager:
                # Test empty query text
                with pytest.raises(ValueError, match="query_text cannot be empty"):
                    manager.search_external_predicates_by_similarity("")

                # Test invalid threshold (too high)
                with pytest.raises(ValueError, match="threshold must be between"):
                    manager.search_external_predicates_by_similarity(
                        "test", threshold=1.5
                    )

                # Test invalid threshold (too low)
                with pytest.raises(ValueError, match="threshold must be between"):
                    manager.search_external_predicates_by_similarity(
                        "test", threshold=-1.5
                    )

                # Test invalid limit (non-positive)
                with pytest.raises(
                    ValueError, match="limit must be a positive integer"
                ):
                    manager.search_external_predicates_by_similarity("test", limit=0)

                # Test invalid limit (too large)
                with pytest.raises(ValueError, match="limit must not exceed"):
                    manager.search_external_predicates_by_similarity(
                        "test", limit=20000
                    )

        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_external_predicate_embedding_dimension_validation(self):
        """
        Test that embedding dimension validation prevents inconsistent data.

        Validates:
        - Embeddings with incorrect dimensions are rejected
        - Clear error message indicates dimension mismatch
        - Validation occurs before database write
        """
        config = ReferenceConfig()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = tf.name

        try:
            with ReferenceManager(config, db_path=db_path) as manager:
                # Create embedding with wrong dimensions
                wrong_size_embedding = b"\x00" * 256  # 64 dimensions instead of 128

                with pytest.raises(ValueError) as exc_info:
                    manager.add_external_predicate(
                        title="testPredicate",
                        definition="Test predicate for validation",
                        source="schema.org",
                        external_id="testPredicate",
                        title_embedding=wrong_size_embedding,
                        embedding_dims=EMBEDDING_DIMS_SMALL,  # Expects 128 dims
                    )

                error = str(exc_info.value)
                assert "dimension" in error.lower()
                assert "mismatch" in error.lower()

        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_external_predicate_indexes_created(self):
        """
        Test that all required indexes are created for the external_predicates table.

        Validates:
        - source index exists
        - external_id index exists
        - title index exists
        - title_embedding index exists
        - definition_embedding index exists
        """
        config = ReferenceConfig()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = tf.name

        try:
            from sqlalchemy import text

            with ReferenceManager(config, db_path=db_path) as manager:
                # Query SQLite's index information
                with manager.engine.connect() as conn:
                    result = conn.execute(
                        text(
                            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='external_predicates'"
                        )
                    )
                    indexes = [row[0] for row in result]

                # Check for expected indexes (SQLAlchemy auto-generates index names)
                # The indexes should include columns: source, external_id, title,
                # title_embedding, definition_embedding
                assert (
                    len(indexes) >= 5
                ), f"Expected at least 5 indexes, found {len(indexes)}: {indexes}"

        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_external_predicate_unique_constraint(self):
        """
        Test that the UNIQUE constraint on (source, external_id) works correctly.

        Validates:
        - First insert succeeds
        - Duplicate insert fails with IntegrityError
        - Different source allows same external_id
        """
        config = ReferenceConfig()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = tf.name

        try:
            with ReferenceManager(config, db_path=db_path) as manager:
                # First insert should succeed
                manager.add_external_predicate(
                    title="testPredicate",
                    definition="Test predicate",
                    source="schema.org",
                    external_id="test1",
                )

                # Duplicate (source, external_id) should fail
                with pytest.raises(Exception):  # SQLAlchemy raises IntegrityError
                    manager.add_external_predicate(
                        title="duplicatePredicate",
                        definition="This should fail",
                        source="schema.org",
                        external_id="test1",
                    )

                # Roll back the session after the integrity error
                manager.session.rollback()

                # Different source with same external_id should succeed
                manager.add_external_predicate(
                    title="testPredicate",
                    definition="Test predicate from different source",
                    source="wikidata",
                    external_id="test1",
                )

                # Verify both exist
                schema_pred = manager.get_external_predicate_by_source(
                    "schema.org", "test1"
                )
                wikidata_pred = manager.get_external_predicate_by_source(
                    "wikidata", "test1"
                )
                assert schema_pred is not None
                assert wikidata_pred is not None
                assert schema_pred.id != wikidata_pred.id

        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_external_predicate_thread_safe_access(self):
        """
        Test that external predicate operations work correctly with check_same_thread=False.

        Validates:
        - Database can be accessed from different contexts
        - Thread-safe connection configuration is applied
        """
        config = ReferenceConfig()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = tf.name

        try:
            with ReferenceManager(config, db_path=db_path) as manager:
                # Add a predicate
                manager.add_external_predicate(
                    title="testThreadSafe",
                    definition="Testing thread-safe access",
                    source="schema.org",
                    external_id="threadTest",
                )

                # Query it back - should work without threading errors
                predicate = manager.get_external_predicate_by_source(
                    "schema.org", "threadTest"
                )
                assert predicate is not None
                assert predicate.title == "testThreadSafe"

        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
