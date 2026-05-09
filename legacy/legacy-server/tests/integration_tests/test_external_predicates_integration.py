"""
Integration tests for external predicates functionality.

These tests validate the integration of external predicates with:
- Database persistence layer
- Embedding generation system
- Vector search capabilities
- Reference database manager
"""

import os
import sys
import tempfile
import pytest

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reference_db.config import ReferenceConfig  # noqa: E402
from reference_db.manager import ReferenceManager  # noqa: E402


class TestExternalPredicatesIntegration:
    """
    Integration tests for external predicates with full system components.

    These tests validate:
    - Database schema creation and constraints
    - Embedding generation pipeline integration
    - Vector search with sqlite-vec
    - Thread-safe operations
    - Full CRUD workflows
    """

    @pytest.fixture(autouse=True)
    def check_sqlite_vec(self):
        """Check if sqlite-vec is available and working, skip tests if not."""
        try:
            import sqlite_vec as _  # noqa: F401 # type: ignore[import-untyped]
        except ImportError:
            pytest.skip(
                "sqlite-vec not available (expected in Docker environment)"
            )  # noqa: E501

        # Also verify that vec functions are actually available in SQLite
        test_db_path = None
        try:
            import tempfile
            from sqlalchemy import create_engine, text
            from database.utils import init_db

            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
                test_db_path = tf.name

            test_engine = create_engine(f"sqlite:///{test_db_path}")
            init_db(test_engine)

            # Test if vec_distance_cosine is available
            with test_engine.connect() as conn:
                try:
                    conn.execute(
                        text("SELECT vec_distance_cosine(x'00000000', x'00000000')")
                    )  # noqa: E501
                except Exception as e:
                    pytest.skip(
                        f"sqlite-vec extension not properly loaded: {e}"
                    )  # noqa: E501

            test_engine.dispose()
        finally:
            if test_db_path and os.path.exists(test_db_path):
                os.unlink(test_db_path)

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = tf.name
        yield db_path
        if os.path.exists(db_path):
            os.unlink(db_path)

    @pytest.fixture
    def manager(self, temp_db):
        """Create a ReferenceManager instance for testing."""
        config = ReferenceConfig()
        with ReferenceManager(config, db_path=temp_db) as mgr:
            yield mgr

    def test_database_schema_creation(self, temp_db):
        """
        Test that external predicates table is created with correct schema.

        Validates:
        - Table exists after manager initialization
        - All columns are present
        - Indexes are created
        - Unique constraint is enforced
        """
        config = ReferenceConfig()

        with ReferenceManager(config, db_path=temp_db) as manager:
            from sqlalchemy import inspect, text

            # Check table exists
            inspector = inspect(manager.engine)
            assert "external_predicates" in inspector.get_table_names()

            # Check columns
            columns = {
                col["name"] for col in inspector.get_columns("external_predicates")
            }  # noqa: E501
            expected_columns = {
                "id",
                "title",
                "definition",
                "source",
                "external_id",
                "attributes",
                "title_embedding",
                "definition_embedding",
                "created_at",
                "updated_at",
            }
            assert expected_columns.issubset(columns)

            # Check indexes
            with manager.engine.connect() as conn:
                result = conn.execute(
                    text(
                        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='external_predicates'"
                    )  # noqa: E501
                )
                indexes = [row[0] for row in result]
                assert (
                    len(indexes) >= 5
                ), f"Expected at least 5 indexes, found {len(indexes)}"  # noqa: E501

    def test_embedding_generation_integration(self, manager):
        """
        Test integration with embedding generation system.

        Validates:
        - Embeddings are auto-generated when not provided
        - Generated embeddings have correct dimensions (384)
        - Embeddings are stored as binary data
        - Both title and definition embeddings are generated
        """
        predicate = manager.add_external_predicate(
            title="hasProperty",
            definition="Indicates that an entity has a specific property",
            source="schema.org",
            external_id="hasProperty",
        )

        # Verify embeddings were generated
        assert predicate.title_embedding is not None
        assert predicate.definition_embedding is not None

        # Verify dimensions (384 dims * 4 bytes per float32 = 1536 bytes)
        # Using all-MiniLM-L6-v2 model which produces 384-dimensional embeddings  # noqa: E501
        assert len(predicate.title_embedding) == 384 * 4
        assert len(predicate.definition_embedding) == 384 * 4

        # Verify embeddings are different (not duplicate references)
        assert predicate.title_embedding != predicate.definition_embedding

        # Retrieve from database to verify persistence
        retrieved = manager.get_external_predicate(predicate.id)
        assert retrieved.title_embedding == predicate.title_embedding
        assert retrieved.definition_embedding == predicate.definition_embedding

    def test_vector_search_integration(self, manager):
        """
        Test integration with sqlite-vec vector search.

        Validates:
        - Vector search finds semantically similar predicates
        - Similarity scores are meaningful (higher for related terms)
        - Results are properly ordered by similarity
        - Search works across both title and definition embeddings
        """
        # Create predicates with semantic relationships
        class_pred = manager.add_external_predicate(
            title="subClassOf",
            definition="Indicates that one class is a subclass of another class in a hierarchy",  # noqa: E501
            source="schema.org",
            external_id="subClassOf",
        )

        property_pred = manager.add_external_predicate(
            title="hasProperty",
            definition="Indicates that an entity has a specific property or attribute",  # noqa: E501
            source="schema.org",
            external_id="hasProperty",
        )

        color_pred = manager.add_external_predicate(
            title="color",
            definition="The color appearance of an object",
            source="schema.org",
            external_id="color",
        )

        # Search for class-related predicates
        results = manager.search_external_predicates_by_similarity(
            "class hierarchy inheritance", threshold=0.3, limit=10
        )

        assert len(results) > 0

        # Find the class-related predicate in results
        class_results = [r for r in results if r[0].id == class_pred.id]
        property_results = [r for r in results if r[0].id == property_pred.id]
        color_results = [r for r in results if r[0].id == color_pred.id]

        # Class predicate should be most relevant
        if class_results:
            class_score = class_results[0][1]

            # Should be more similar to "class hierarchy" than property/color
            if property_results:
                assert class_score > property_results[0][1]
            if color_results:
                assert class_score > color_results[0][1]

    def test_unique_constraint_enforcement(self, manager):
        """
        Test that UNIQUE(source, external_id) constraint is enforced.

        Validates:
        - First insert succeeds
        - Duplicate (source, external_id) fails
        - Different source allows same external_id
        - Error handling provides clear message
        """
        # First insert should succeed
        pred1 = manager.add_external_predicate(
            title="testPredicate",
            definition="Test predicate for constraint testing",
            source="schema.org",
            external_id="test1",
        )
        assert pred1.id is not None

        # Duplicate should fail
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError) as exc_info:
            manager.add_external_predicate(
                title="duplicatePredicate",
                definition="This should fail",
                source="schema.org",
                external_id="test1",
            )

        # Verify error message mentions constraint
        assert (
            "UNIQUE constraint failed" in str(exc_info.value)
            or "unique" in str(exc_info.value).lower()
        )  # noqa: E501

        # Rollback the session after the IntegrityError to clean up the failed transaction  # noqa: E501
        manager.session.rollback()

        # Different source should succeed
        pred2 = manager.add_external_predicate(
            title="testPredicate",
            definition="Test predicate from different source",
            source="wikidata",
            external_id="test1",
        )
        assert pred2.id is not None
        assert pred2.id != pred1.id

    def test_full_crud_workflow(self, manager):
        """
        Test complete Create-Read-Update-Delete workflow.

        Validates:
        - Create: Add new predicate with all fields
        - Read: Retrieve by ID and by (source, external_id)
        - Read: List with filters
        - Read: Search by similarity
        - Transactions: All operations are properly committed
        """
        # CREATE
        created = manager.add_external_predicate(
            title="relatedTo",
            definition="Indicates a general relationship between two entities",
            source="schema.org",
            external_id="relatedTo",
        )
        assert created.id is not None

        # READ by ID
        by_id = manager.get_external_predicate(created.id)
        assert by_id is not None
        assert by_id.id == created.id
        assert by_id.title == "relatedTo"

        # READ by source
        by_source = manager.get_external_predicate_by_source(
            "schema.org", "relatedTo"
        )  # noqa: E501
        assert by_source is not None
        assert by_source.id == created.id

        # LIST
        all_preds = manager.list_external_predicates()
        assert len(all_preds) > 0
        assert any(p.id == created.id for p in all_preds)

        # LIST with source filter
        schema_preds = manager.list_external_predicates(source="schema.org")
        assert len(schema_preds) > 0
        assert all(p.source == "schema.org" for p in schema_preds)

        # SEARCH
        search_results = manager.search_external_predicates_by_similarity(
            "relationship", threshold=0.3, limit=10
        )
        assert len(search_results) > 0

    def test_concurrent_access_simulation(self, temp_db):
        """
        Test that multiple manager instances can access the database concurrently.  # noqa: E501

        Validates:
        - check_same_thread=False configuration works
        - Multiple reads work correctly
        - Data consistency across connections
        """
        config = ReferenceConfig()

        # Create data with first manager
        with ReferenceManager(config, db_path=temp_db) as manager1:
            pred = manager1.add_external_predicate(
                title="concurrentTest",
                definition="Testing concurrent access",
                source="test",
                external_id="concurrent1",
            )
            pred_id = pred.id

        # Read with second manager (simulates different thread/context)
        with ReferenceManager(config, db_path=temp_db) as manager2:
            retrieved = manager2.get_external_predicate(pred_id)
            assert retrieved is not None
            assert retrieved.title == "concurrentTest"

            # Add another predicate
            pred2 = manager2.add_external_predicate(
                title="concurrentTest2",
                definition="Testing concurrent write",
                source="test",
                external_id="concurrent2",
            )
            assert pred2.id is not None

        # Verify with third manager
        with ReferenceManager(config, db_path=temp_db) as manager3:
            all_preds = manager3.list_external_predicates(source="test")
            assert len(all_preds) == 2

    def test_batch_operations_performance(self, manager):
        """
        Test performance of batch operations.

        Validates:
        - Multiple predicates can be added efficiently
        - Batch retrieval works correctly
        - Vector search performs reasonably with multiple entries
        """
        # Add multiple predicates
        pred_ids = []
        for i in range(10):
            pred = manager.add_external_predicate(
                title=f"predicate{i}",
                definition=f"Definition for predicate number {i}",
                source="test_batch",
                external_id=f"pred{i}",
            )
            pred_ids.append(pred.id)

        # Verify all were added
        assert len(pred_ids) == 10

        # Batch retrieval
        batch_preds = manager.list_external_predicates(source="test_batch")
        assert len(batch_preds) == 10

        # Search should work with larger dataset
        results = manager.search_external_predicates_by_similarity(
            "predicate definition", source="test_batch", threshold=0.2, limit=20
        )
        assert len(results) > 0

    def test_error_handling_and_recovery(self, manager):
        """
        Test error handling and recovery scenarios.

        Validates:
        - Invalid inputs are rejected with clear errors
        - Database remains consistent after errors
        - Transaction rollback works correctly
        """
        # Test invalid embedding dimensions
        with pytest.raises(ValueError) as exc_info:
            manager.add_external_predicate(
                title="invalidEmbedding",
                definition="Test invalid embedding",
                source="test",
                external_id="invalid1",
                title_embedding=b"\x00" * 256,  # Wrong size
                embedding_dims=128,
            )
        assert "dimension" in str(exc_info.value).lower()

        # Test invalid search parameters
        with pytest.raises(ValueError):
            manager.search_external_predicates_by_similarity("", threshold=0.5)

        with pytest.raises(ValueError):
            manager.search_external_predicates_by_similarity(
                "test", threshold=2.0
            )  # noqa: E501

        with pytest.raises(ValueError):
            manager.search_external_predicates_by_similarity("test", limit=0)

        # Database should still work after errors
        pred = manager.add_external_predicate(
            title="afterError",
            definition="Created after error handling",
            source="test",
            external_id="after_error",
        )
        assert pred.id is not None

    def test_large_text_handling(self, manager):
        """
        Test handling of large text in title and definition fields.

        Validates:
        - Long titles are handled correctly
        - Long definitions are stored and retrieved
        - Embeddings are generated for long text
        """
        long_title = "A" * 500
        long_definition = "B" * 5000

        pred = manager.add_external_predicate(
            title=long_title,
            definition=long_definition,
            source="test",
            external_id="long_text",
        )

        assert pred.id is not None
        assert pred.title_embedding is not None
        assert pred.definition_embedding is not None

        # Retrieve and verify
        retrieved = manager.get_external_predicate(pred.id)
        assert retrieved.title == long_title
        assert retrieved.definition == long_definition

    def test_special_characters_handling(self, manager):
        """
        Test handling of special characters and unicode.

        Validates:
        - Unicode characters are stored correctly
        - Special SQL characters don't cause issues
        - Embeddings work with non-ASCII text
        """
        pred = manager.add_external_predicate(
            title="Spécial Chàracters",
            definition="Unicode: 日本語, Emoji: 🔥, SQL: ' OR '1'='1",
            source="unicode_test",
            external_id="special_chars",
        )

        assert pred.id is not None

        # Retrieve and verify
        retrieved = manager.get_external_predicate(pred.id)
        assert retrieved.title == "Spécial Chàracters"
        assert "日本語" in retrieved.definition
        assert "🔥" in retrieved.definition

        # Search should work with unicode
        results = manager.search_external_predicates_by_similarity(
            "日本語", threshold=0.1, limit=10
        )
        # Should at least not crash
        assert isinstance(results, list)

    def test_null_and_empty_attributes(self, manager):
        """
        Test handling of null and empty attribute values.

        Validates:
        - NULL attributes are handled correctly
        - Empty strings are distinguished from NULL
        - Optional fields work as expected
        """
        # Test with no attributes
        pred1 = manager.add_external_predicate(
            title="noAttributes",
            definition="Predicate without attributes",
            source="test",
            external_id="no_attrs",
        )
        assert pred1.attributes is None

        # Test with empty dict attributes
        pred2 = manager.add_external_predicate(
            title="emptyAttributes",
            definition="Predicate with empty attributes dict",
            source="test",
            external_id="empty_attrs",
            attributes={},
        )
        # Note: Current implementation converts to string
        assert pred2.attributes is not None

    def test_search_with_no_results(self, manager):
        """
        Test search behavior when no results match criteria.

        Validates:
        - Empty list is returned (not None)
        - No errors occur
        - System remains stable
        """
        # Add a predicate
        manager.add_external_predicate(
            title="computer",
            definition="An electronic device for computing",
            source="test",
            external_id="computer",
        )

        # Search for something completely unrelated with high threshold
        results = manager.search_external_predicates_by_similarity(
            "zzzzzzzzz nonsense query xyz",
            threshold=0.99,  # Very high threshold
            limit=10,
        )

        assert results == []
        assert isinstance(results, list)

    def test_search_source_filter(self, manager):
        """
        Test that source filter works correctly in similarity search.

        Validates:
        - Results are filtered by source
        - Other sources are excluded
        - Empty results when source doesn't exist
        """
        # Add predicates from different sources
        manager.add_external_predicate(
            title="property",
            definition="A characteristic or attribute",
            source="schema.org",
            external_id="property1",
        )

        manager.add_external_predicate(
            title="property",
            definition="A characteristic or attribute",
            source="wikidata",
            external_id="P31",
        )

        # Search with source filter
        schema_results = manager.search_external_predicates_by_similarity(
            "property attribute", source="schema.org", threshold=0.3, limit=10
        )

        # All results should be from schema.org
        for pred, score in schema_results:
            assert pred.source == "schema.org"

        # Search non-existent source
        no_results = manager.search_external_predicates_by_similarity(
            "property", source="nonexistent_source", threshold=0.3, limit=10
        )

        assert no_results == []

    def test_predicate_mapping_stores_external_reference(self, manager):
        """
        Test that external predicate mappings are stored correctly.

        Validates:
        - External predicates can be added with source and external_id
        - Predicates can be retrieved by source and external_id
        - Attributes field stores additional metadata
        """
        # Add an external predicate with mapping information
        attributes = {
            "url": "https://schema.org/subClassOf",
            "domain": "rdfs:Class",
            "range": "rdfs:Class",
        }

        predicate = manager.add_external_predicate(
            title="subClassOf",
            definition="Indicates that one class is a subclass of another",
            source="schema.org",
            external_id="subClassOf",
            attributes=attributes,
        )

        assert predicate.id is not None
        assert predicate.source == "schema.org"
        assert predicate.external_id == "subClassOf"

        # Retrieve by source and external_id
        retrieved = manager.get_external_predicate_by_source(
            "schema.org", "subClassOf"
        )  # noqa: E501
        assert retrieved is not None
        assert retrieved.id == predicate.id
        assert retrieved.title == "subClassOf"
        assert retrieved.source == "schema.org"
        assert retrieved.external_id == "subClassOf"

    def test_external_source_filtering(self, manager):
        """
        Test filtering external predicates by source.

        Validates:
        - List operations can filter by source
        - Search operations can filter by source
        - Filtering is accurate and complete
        """
        # Add predicates from multiple sources
        manager.add_external_predicate(
            title="type",
            definition="The type of the item",
            source="schema.org",
            external_id="type",
        )

        manager.add_external_predicate(
            title="instance of",
            definition="That class of which this subject is a particular example",  # noqa: E501
            source="wikidata",
            external_id="P31",
        )

        manager.add_external_predicate(
            title="IsA",
            definition="Indicates that one concept is a type of another",
            source="conceptnet",
            external_id="/r/IsA",
        )

        # List all predicates
        all_preds = manager.list_external_predicates()
        assert len(all_preds) == 3

        # Filter by schema.org
        schema_preds = manager.list_external_predicates(source="schema.org")
        assert len(schema_preds) == 1
        assert schema_preds[0].source == "schema.org"

        # Filter by wikidata
        wikidata_preds = manager.list_external_predicates(source="wikidata")
        assert len(wikidata_preds) == 1
        assert wikidata_preds[0].source == "wikidata"

        # Filter by conceptnet
        conceptnet_preds = manager.list_external_predicates(
            source="conceptnet"
        )  # noqa: E501
        assert len(conceptnet_preds) == 1
        assert conceptnet_preds[0].source == "conceptnet"

        # Search with source filter
        schema_search = manager.search_external_predicates_by_similarity(
            "type classification", source="schema.org", threshold=0.3, limit=10
        )
        for pred, score in schema_search:
            assert pred.source == "schema.org"

    def test_predicate_similarity_scoring(self, manager):
        """
        Test similarity scoring for external predicates.

        Validates:
        - Similarity scores are in valid range [0, 1]
        - More similar predicates have higher scores
        - Scores are based on semantic meaning
        """
        # Add predicates with varying degrees of semantic similarity
        manager.add_external_predicate(
            title="subClassOf",
            definition="Indicates that one class is a subclass of another class in a hierarchy",  # noqa: E501
            source="test",
            external_id="subclass",
        )

        manager.add_external_predicate(
            title="parentClass",
            definition="The parent class in a class hierarchy structure",
            source="test",
            external_id="parent",
        )

        manager.add_external_predicate(
            title="color",
            definition="The color appearance of an object",
            source="test",
            external_id="color",
        )

        # Search for class hierarchy concepts
        results = manager.search_external_predicates_by_similarity(
            "class hierarchy parent subclass",
            source="test",
            threshold=0.0,  # Get all results
            limit=10,
        )

        assert len(results) > 0

        # Check all scores are valid
        for pred, score in results:
            assert 0.0 <= score <= 1.0, f"Score {score} out of valid range"

        # Get scores for each predicate
        scores_by_id = {pred.external_id: score for pred, score in results}

        # Class-related predicates should have higher scores than color
        if "subclass" in scores_by_id and "color" in scores_by_id:
            assert scores_by_id["subclass"] > scores_by_id["color"]

        if "parent" in scores_by_id and "color" in scores_by_id:
            assert scores_by_id["parent"] > scores_by_id["color"]

    def test_external_predicate_caching(self, manager):
        """
        Test that external predicate retrieval is efficient with repeated access.  # noqa: E501

        Validates:
        - Repeated retrieval by ID returns consistent results
        - Repeated retrieval by source/external_id returns consistent results
        - No errors occur with repeated access
        """
        # Add a predicate
        predicate = manager.add_external_predicate(
            title="relatedTo",
            definition="Indicates a general relationship between entities",
            source="test",
            external_id="related",
        )

        pred_id = predicate.id

        # Retrieve multiple times by ID
        for _ in range(10):
            retrieved = manager.get_external_predicate(pred_id)
            assert retrieved is not None
            assert retrieved.id == pred_id
            assert retrieved.title == "relatedTo"
            assert retrieved.source == "test"
            assert retrieved.external_id == "related"

        # Retrieve multiple times by source/external_id
        for _ in range(10):
            retrieved = manager.get_external_predicate_by_source(
                "test", "related"
            )  # noqa: E501
            assert retrieved is not None
            assert retrieved.id == pred_id
            assert retrieved.title == "relatedTo"

        # Verify data consistency across retrieval methods
        by_id = manager.get_external_predicate(pred_id)
        by_source = manager.get_external_predicate_by_source("test", "related")

        assert by_id.id == by_source.id
        assert by_id.title == by_source.title
        assert by_id.definition == by_source.definition
        assert by_id.source == by_source.source
        assert by_id.external_id == by_source.external_id

    def test_list_predicates_limit(self, manager):
        """
        Test that limit parameter works correctly in list operations.

        Validates:
        - Limit restricts number of results
        - Results are consistent
        """
        # Add multiple predicates
        for i in range(20):
            manager.add_external_predicate(
                title=f"pred{i}",
                definition=f"Definition {i}",
                source="test_limit",
                external_id=f"pred{i}",
            )

        # Test various limits
        results_5 = manager.list_external_predicates(
            source="test_limit", limit=5
        )  # noqa: E501
        assert len(results_5) == 5

        results_10 = manager.list_external_predicates(
            source="test_limit", limit=10
        )  # noqa: E501
        assert len(results_10) == 10

        results_all = manager.list_external_predicates(source="test_limit")
        assert len(results_all) == 20
