"""
End-to-end tests for external predicates workflows.

These tests validate complete user workflows from start to finish:
- Initial setup and database creation
- Adding external predicates from multiple sources
- Searching and retrieving predicates
- Building predicate mappings
- Real-world usage scenarios
"""

import os
import sys
import tempfile
import pytest

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reference_db.config import ReferenceConfig
from reference_db.manager import ReferenceManager


class TestExternalPredicatesE2E:
    """
    End-to-end tests for complete external predicates workflows.

    These tests simulate real-world usage patterns:
    - Multi-source predicate management
    - Semantic search and mapping workflows
    - Production-like data scenarios
    """

    @pytest.fixture(autouse=True)
    def check_sqlite_vec(self):
        """Check if sqlite-vec is available, skip tests if not."""
        try:
            import sqlite_vec  # noqa: F401
        except ImportError:
            pytest.skip("sqlite-vec not available (expected in Docker environment)")

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tf:
            db_path = tf.name
        yield db_path
        if os.path.exists(db_path):
            os.unlink(db_path)

    def test_e2e_schema_org_import_workflow(self, temp_db):
        """
        Test end-to-end workflow for importing Schema.org predicates.

        Workflow:
        1. Initialize empty database
        2. Import multiple Schema.org predicates
        3. Verify all predicates are stored correctly
        4. Search for semantically similar predicates
        5. Retrieve specific predicates by source ID
        """
        config = ReferenceConfig()

        with ReferenceManager(config, db_path=temp_db) as manager:
            # Step 1: Database is initialized (happens automatically)
            initial_count = len(manager.list_external_predicates(source="schema.org"))
            assert initial_count == 0

            # Step 2: Import Schema.org predicates
            schema_predicates = [
                {
                    "title": "subClassOf",
                    "definition": "Indicates that one class is a subclass of another class",
                    "external_id": "subClassOf"
                },
                {
                    "title": "domainIncludes",
                    "definition": "Relates a property to a class that is (one of) the type(s) the property is expected to be used on",
                    "external_id": "domainIncludes"
                },
                {
                    "title": "rangeIncludes",
                    "definition": "Relates a property to a class that constitutes (one of) the expected type(s) for values of the property",
                    "external_id": "rangeIncludes"
                },
                {
                    "title": "inverseOf",
                    "definition": "Relates a property to a property that is its inverse",
                    "external_id": "inverseOf"
                },
                {
                    "title": "supersededBy",
                    "definition": "Relates a term to a term that supersedes it",
                    "external_id": "supersededBy"
                }
            ]

            created_predicates = []
            for pred_data in schema_predicates:
                pred = manager.add_external_predicate(
                    title=pred_data["title"],
                    definition=pred_data["definition"],
                    source="schema.org",
                    external_id=pred_data["external_id"]
                )
                created_predicates.append(pred)

            # Step 3: Verify all predicates stored correctly
            all_schema = manager.list_external_predicates(source="schema.org")
            assert len(all_schema) == 5
            assert all(p.source == "schema.org" for p in all_schema)

            # Step 4: Search for semantically similar predicates
            # Search for class hierarchy related predicates
            class_results = manager.search_external_predicates_by_similarity(
                "class hierarchy type inheritance",
                source="schema.org",
                threshold=0.4,
                limit=5
            )

            assert len(class_results) > 0

            # subClassOf should be highly relevant
            titles_found = [pred.title for pred, score in class_results]
            assert "subClassOf" in titles_found

            # Search for property-related predicates
            property_results = manager.search_external_predicates_by_similarity(
                "property domain range type",
                source="schema.org",
                threshold=0.4,
                limit=5
            )

            assert len(property_results) > 0
            property_titles = [pred.title for pred, score in property_results]
            # Should find domain/range predicates
            assert any(t in property_titles for t in ["domainIncludes", "rangeIncludes"])

            # Step 5: Retrieve specific predicates by source ID
            subclass = manager.get_external_predicate_by_source("schema.org", "subClassOf")
            assert subclass is not None
            assert subclass.title == "subClassOf"
            assert "class" in subclass.definition.lower()

    def test_e2e_multi_source_comparison_workflow(self, temp_db):
        """
        Test end-to-end workflow for comparing predicates across sources.

        Workflow:
        1. Import predicates from Schema.org
        2. Import similar predicates from Wikidata
        3. Search across all sources to find similarities
        4. Filter by specific source
        5. Compare semantic similarity between sources
        """
        config = ReferenceConfig()

        with ReferenceManager(config, db_path=temp_db) as manager:
            # Step 1: Import Schema.org predicates
            manager.add_external_predicate(
                title="subClassOf",
                definition="Indicates that one class is a subclass of another",
                source="schema.org",
                external_id="subClassOf"
            )

            manager.add_external_predicate(
                title="name",
                definition="The name of the item",
                source="schema.org",
                external_id="name"
            )

            # Step 2: Import similar Wikidata predicates
            manager.add_external_predicate(
                title="subclass of",
                definition="Class of which this subject is a particular example or subclass",
                source="wikidata",
                external_id="P279"
            )

            manager.add_external_predicate(
                title="instance of",
                definition="That class of which this subject is a particular example",
                source="wikidata",
                external_id="P31"
            )

            manager.add_external_predicate(
                title="label",
                definition="Label or title to describe the entity",
                source="wikidata",
                external_id="P1476"
            )

            # Step 3: Search across all sources
            hierarchy_results = manager.search_external_predicates_by_similarity(
                "class hierarchy subclass",
                threshold=0.3,
                limit=10
            )

            assert len(hierarchy_results) > 0

            # Should find predicates from both sources
            sources_found = set(pred.source for pred, score in hierarchy_results)
            assert "schema.org" in sources_found
            assert "wikidata" in sources_found

            # Step 4: Filter by specific source
            schema_only = manager.search_external_predicates_by_similarity(
                "class hierarchy",
                source="schema.org",
                threshold=0.3,
                limit=10
            )

            assert all(pred.source == "schema.org" for pred, score in schema_only)

            wikidata_only = manager.search_external_predicates_by_similarity(
                "class hierarchy",
                source="wikidata",
                threshold=0.3,
                limit=10
            )

            assert all(pred.source == "wikidata" for pred, score in wikidata_only)

            # Step 5: Compare semantic similarity
            # Both "subClassOf" and "subclass of" should have high similarity to query
            schema_subclass = next(
                (score for pred, score in schema_only if pred.external_id == "subClassOf"),
                None
            )
            wikidata_subclass = next(
                (score for pred, score in wikidata_only if pred.external_id == "P279"),
                None
            )

            # Both should be found with reasonable similarity
            assert schema_subclass is not None
            assert wikidata_subclass is not None
            assert schema_subclass > 0.3
            assert wikidata_subclass > 0.3

    def test_e2e_predicate_mapping_discovery_workflow(self, temp_db):
        """
        Test end-to-end workflow for discovering predicate mappings.

        Workflow:
        1. Setup internal predicates (simulated)
        2. Import external predicates from Schema.org
        3. For each internal predicate, find matching external predicates
        4. Review and validate mappings
        5. Store mapping decisions (conceptual - not implemented in Phase 1)
        """
        config = ReferenceConfig()

        with ReferenceManager(config, db_path=temp_db) as manager:
            # Step 1: Define internal predicates (simulated as dict)
            internal_predicates = [
                {"id": "int_001", "label": "is_parent_of", "description": "Child-parent relationship in a hierarchy"},
                {"id": "int_002", "label": "has_attribute", "description": "Entity has a specific attribute or property"},
                {"id": "int_003", "label": "refers_to", "description": "One entity refers to or mentions another"},
            ]

            # Step 2: Import Schema.org predicates
            schema_predicates_data = [
                ("subClassOf", "Indicates that one class is a subclass of another", "subClassOf"),
                ("superclassOf", "Indicates that one class is a superclass of another", "superclassOf"),
                ("property", "A property of the entity", "property"),
                ("relatedTo", "Related entity or concept", "relatedTo"),
                ("mentions", "Indicates that this CreativeWork mentions a person, organization, or other entity", "mentions"),
            ]

            for title, definition, external_id in schema_predicates_data:
                manager.add_external_predicate(
                    title=title,
                    definition=definition,
                    source="schema.org",
                    external_id=external_id
                )

            # Step 3: For each internal predicate, find matches
            mapping_results = {}

            for internal_pred in internal_predicates:
                # Combine label and description for search
                search_query = f"{internal_pred['label']} {internal_pred['description']}"

                # Search for similar external predicates
                matches = manager.search_external_predicates_by_similarity(
                    search_query,
                    source="schema.org",
                    threshold=0.3,
                    limit=3
                )

                mapping_results[internal_pred['id']] = {
                    'internal': internal_pred,
                    'matches': [(pred.external_id, pred.title, score) for pred, score in matches]
                }

            # Step 4: Validate mappings
            # is_parent_of should match subclass/superclass predicates
            parent_matches = mapping_results['int_001']['matches']
            assert len(parent_matches) > 0
            parent_titles = [title for ext_id, title, score in parent_matches]
            assert any("class" in title.lower() for title in parent_titles)

            # has_attribute should match property predicates
            attr_matches = mapping_results['int_002']['matches']
            assert len(attr_matches) > 0
            attr_titles = [title for ext_id, title, score in attr_matches]
            assert any("property" in title.lower() for title in attr_titles)

            # refers_to should match relatedTo or mentions
            refers_matches = mapping_results['int_003']['matches']
            assert len(refers_matches) > 0
            refers_titles = [title for ext_id, title, score in refers_matches]
            assert any(title.lower() in ["relatedto", "mentions"] for title in refers_titles)

    def test_e2e_incremental_update_workflow(self, temp_db):
        """
        Test end-to-end workflow for incrementally updating predicates.

        Workflow:
        1. Initial import of predicates
        2. Check for existing predicates before adding
        3. Add only new predicates
        4. Verify no duplicates
        5. Handle update scenarios (read-only in Phase 1)
        """
        config = ReferenceConfig()

        with ReferenceManager(config, db_path=temp_db) as manager:
            # Step 1: Initial import
            initial_predicates = [
                ("subClassOf", "Indicates that one class is a subclass of another", "subClassOf"),
                ("property", "A property of the entity", "property"),
            ]

            for title, definition, external_id in initial_predicates:
                manager.add_external_predicate(
                    title=title,
                    definition=definition,
                    source="schema.org",
                    external_id=external_id
                )

            initial_count = len(manager.list_external_predicates(source="schema.org"))
            assert initial_count == 2

            # Step 2 & 3: Check for existing and add only new
            predicates_to_import = [
                ("subClassOf", "Updated definition", "subClassOf"),  # Duplicate
                ("rangeIncludes", "Relates a property to a class", "rangeIncludes"),  # New
                ("property", "Same definition", "property"),  # Duplicate
                ("domainIncludes", "Relates a property to a class", "domainIncludes"),  # New
            ]

            added_count = 0
            skipped_count = 0

            for title, definition, external_id in predicates_to_import:
                # Check if exists
                existing = manager.get_external_predicate_by_source("schema.org", external_id)

                if existing is None:
                    # Add new predicate
                    manager.add_external_predicate(
                        title=title,
                        definition=definition,
                        source="schema.org",
                        external_id=external_id
                    )
                    added_count += 1
                else:
                    skipped_count += 1

            # Step 4: Verify no duplicates
            final_count = len(manager.list_external_predicates(source="schema.org"))
            assert final_count == 4  # 2 initial + 2 new
            assert added_count == 2
            assert skipped_count == 2

            # Verify all expected predicates exist
            expected_ids = ["subClassOf", "property", "rangeIncludes", "domainIncludes"]
            for ext_id in expected_ids:
                pred = manager.get_external_predicate_by_source("schema.org", ext_id)
                assert pred is not None

    def test_e2e_large_dataset_workflow(self, temp_db):
        """
        Test end-to-end workflow with larger dataset.

        Workflow:
        1. Import 50+ predicates from multiple sources
        2. Perform bulk searches
        3. Verify performance and correctness
        4. Test pagination/limits
        """
        config = ReferenceConfig()

        with ReferenceManager(config, db_path=temp_db) as manager:
            # Step 1: Import large dataset
            # Schema.org predicates
            for i in range(30):
                manager.add_external_predicate(
                    title=f"schema_predicate_{i}",
                    definition=f"A Schema.org predicate for testing, number {i}",
                    source="schema.org",
                    external_id=f"pred_{i}"
                )

            # Wikidata predicates
            for i in range(30):
                manager.add_external_predicate(
                    title=f"wikidata_property_{i}",
                    definition=f"A Wikidata property for testing, number {i}",
                    source="wikidata",
                    external_id=f"P{i}"
                )

            # Step 2: Verify import
            all_predicates = manager.list_external_predicates()
            assert len(all_predicates) == 60

            schema_predicates = manager.list_external_predicates(source="schema.org")
            assert len(schema_predicates) == 30

            wikidata_predicates = manager.list_external_predicates(source="wikidata")
            assert len(wikidata_predicates) == 30

            # Step 3: Bulk search
            search_results = manager.search_external_predicates_by_similarity(
                "predicate property testing",
                threshold=0.2,
                limit=20
            )

            assert len(search_results) > 0
            assert len(search_results) <= 20  # Respects limit

            # Step 4: Test pagination
            page1 = manager.list_external_predicates(limit=10)
            assert len(page1) == 10

            page2 = manager.list_external_predicates(limit=20)
            assert len(page2) == 20

    def test_e2e_error_recovery_workflow(self, temp_db):
        """
        Test end-to-end workflow with error scenarios and recovery.

        Workflow:
        1. Start adding predicates
        2. Encounter error (duplicate)
        3. Handle error gracefully
        4. Continue with remaining predicates
        5. Verify partial success
        """
        config = ReferenceConfig()

        with ReferenceManager(config, db_path=temp_db) as manager:
            predicates_to_add = [
                ("pred1", "First predicate", "pred1"),
                ("pred2", "Second predicate", "pred2"),
                ("pred1", "Duplicate predicate", "pred1"),  # Will fail
                ("pred3", "Third predicate", "pred3"),
            ]

            successful = []
            failed = []

            for title, definition, external_id in predicates_to_add:
                try:
                    pred = manager.add_external_predicate(
                        title=title,
                        definition=definition,
                        source="test",
                        external_id=external_id
                    )
                    successful.append(pred.external_id)
                except Exception as e:
                    failed.append((external_id, str(e)))
                    # Rollback the session after error to allow subsequent operations
                    manager.session.rollback()

            # Verify results
            # Note: After rollback from duplicate, subsequent operations should work
            # We expect: pred1 (success), pred2 (success), pred1 duplicate (fail), pred3 (success after rollback)
            assert len(successful) == 3  # pred1, pred2, pred3
            assert len(failed) == 1  # Duplicate pred1

            # Verify database state
            all_test = manager.list_external_predicates(source="test")
            assert len(all_test) == 3

            # Verify specific predicates
            assert manager.get_external_predicate_by_source("test", "pred1") is not None
            assert manager.get_external_predicate_by_source("test", "pred2") is not None
            assert manager.get_external_predicate_by_source("test", "pred3") is not None

    def test_e2e_semantic_grouping_workflow(self, temp_db):
        """
        Test end-to-end workflow for finding semantically related predicates.

        Workflow:
        1. Import predicates with different semantic categories
        2. Search for predicates in each category
        3. Verify clustering of related predicates
        4. Build semantic groups
        """
        config = ReferenceConfig()

        with ReferenceManager(config, db_path=temp_db) as manager:
            # Step 1: Import predicates in semantic categories

            # Hierarchy predicates
            hierarchy_preds = [
                ("subClassOf", "One class is a subclass of another", "subClassOf"),
                ("parentClass", "The parent class in a hierarchy", "parentClass"),
                ("childClass", "The child class in a hierarchy", "childClass"),
            ]

            # Property predicates
            property_preds = [
                ("hasProperty", "Entity has a property", "hasProperty"),
                ("propertyValue", "The value of a property", "propertyValue"),
                ("attribute", "An attribute of an entity", "attribute"),
            ]

            # Temporal predicates
            temporal_preds = [
                ("startDate", "The start date of something", "startDate"),
                ("endDate", "The end date of something", "endDate"),
                ("dateCreated", "The date something was created", "dateCreated"),
            ]

            all_preds = hierarchy_preds + property_preds + temporal_preds

            for title, definition, external_id in all_preds:
                manager.add_external_predicate(
                    title=title,
                    definition=definition,
                    source="test",
                    external_id=external_id
                )

            # Step 2 & 3: Search and verify clustering

            # Search for hierarchy predicates
            hierarchy_search = manager.search_external_predicates_by_similarity(
                "class hierarchy parent child subclass",
                source="test",
                threshold=0.3,
                limit=5
            )

            hierarchy_titles = [pred.title for pred, score in hierarchy_search]
            # Should find hierarchy predicates at top
            assert any(t in hierarchy_titles for t in ["subClassOf", "parentClass", "childClass"])

            # Search for property predicates
            property_search = manager.search_external_predicates_by_similarity(
                "property attribute characteristic",
                source="test",
                threshold=0.3,
                limit=5
            )

            property_titles = [pred.title for pred, score in property_search]
            # Should find property predicates at top
            assert any(t in property_titles for t in ["hasProperty", "propertyValue", "attribute"])

            # Search for temporal predicates
            temporal_search = manager.search_external_predicates_by_similarity(
                "date time when created",
                source="test",
                threshold=0.3,
                limit=5
            )

            temporal_titles = [pred.title for pred, score in temporal_search]
            # Should find temporal predicates at top
            assert any(t in temporal_titles for t in ["startDate", "endDate", "dateCreated"])

    def test_e2e_cross_lingual_search(self, temp_db):
        """
        Test end-to-end workflow with multilingual predicates.

        Workflow:
        1. Import predicates with English definitions
        2. Search using related English terms
        3. Verify semantic matching works
        """
        config = ReferenceConfig()

        with ReferenceManager(config, db_path=temp_db) as manager:
            # Import predicates
            manager.add_external_predicate(
                title="subClassOf",
                definition="Indicates that one class is a subclass of another class",
                source="schema.org",
                external_id="subClassOf"
            )

            manager.add_external_predicate(
                title="color",
                definition="The color of an object or item",
                source="schema.org",
                external_id="color"
            )

            # Search with synonyms
            results = manager.search_external_predicates_by_similarity(
                "hierarchy inheritance type",
                source="schema.org",
                threshold=0.3,
                limit=5
            )

            # Should find subClassOf with high relevance
            assert len(results) > 0
            top_titles = [pred.title for pred, score in results[:2]]
            assert "subClassOf" in top_titles

            # Search for color with synonym
            color_results = manager.search_external_predicates_by_similarity(
                "hue shade tint",
                source="schema.org",
                threshold=0.3,
                limit=5
            )

            # Should find color predicate
            color_titles = [pred.title for pred, score in color_results]
            assert "color" in color_titles

    def test_e2e_database_persistence_workflow(self, temp_db):
        """
        Test end-to-end workflow verifying database persistence.

        Workflow:
        1. Create manager and add predicates
        2. Close manager
        3. Open new manager with same database
        4. Verify all data persisted
        5. Add more data
        6. Verify cumulative persistence
        """
        config = ReferenceConfig()

        # Step 1 & 2: Add data and close
        with ReferenceManager(config, db_path=temp_db) as manager:
            manager.add_external_predicate(
                title="persistent1",
                definition="First persisted predicate",
                source="test",
                external_id="persist1"
            )

            manager.add_external_predicate(
                title="persistent2",
                definition="Second persisted predicate",
                source="test",
                external_id="persist2"
            )

        # Manager closed, database file should persist

        # Step 3 & 4: Reopen and verify
        with ReferenceManager(config, db_path=temp_db) as manager:
            all_preds = manager.list_external_predicates(source="test")
            assert len(all_preds) == 2

            persist1 = manager.get_external_predicate_by_source("test", "persist1")
            assert persist1 is not None
            assert persist1.title == "persistent1"

            persist2 = manager.get_external_predicate_by_source("test", "persist2")
            assert persist2 is not None
            assert persist2.title == "persistent2"

            # Step 5: Add more data
            manager.add_external_predicate(
                title="persistent3",
                definition="Third persisted predicate",
                source="test",
                external_id="persist3"
            )

        # Step 6: Verify cumulative persistence
        with ReferenceManager(config, db_path=temp_db) as manager:
            all_preds = manager.list_external_predicates(source="test")
            assert len(all_preds) == 3

            for ext_id in ["persist1", "persist2", "persist3"]:
                pred = manager.get_external_predicate_by_source("test", ext_id)
                assert pred is not None

    def test_map_local_predicate_to_dbpedia(self, temp_db):
        """
        Test mapping a local predicate to DBpedia predicates.

        Workflow:
        1. Create DBpedia predicates in reference database
        2. Search for similar predicates
        3. Verify DBpedia predicates are found
        4. Verify similarity scoring works
        """
        config = ReferenceConfig()

        with ReferenceManager(config, db_path=temp_db) as manager:
            # Add DBpedia predicates
            manager.add_external_predicate(
                title="location",
                definition="The geographic location of an entity",
                source="dbpedia",
                external_id="dbo:location"
            )

            manager.add_external_predicate(
                title="isPartOf",
                definition="Indicates that one entity is part of another",
                source="dbpedia",
                external_id="dbo:isPartOf"
            )

            manager.add_external_predicate(
                title="nearestCity",
                definition="The nearest city to a location",
                source="dbpedia",
                external_id="dbo:nearestCity"
            )

            # Search for location-related predicates
            location_results = manager.search_external_predicates_by_similarity(
                "geographic location place position",
                source="dbpedia",
                threshold=0.3,
                limit=10
            )

            # Verify we found relevant predicates
            assert len(location_results) > 0, "Should find location-related DBpedia predicates"

            # Check that location predicate is in results
            titles = [pred.title for pred, score in location_results]
            assert "location" in titles or "nearestCity" in titles

            # Verify scores are reasonable
            for pred, score in location_results:
                assert 0.0 <= score <= 1.0, f"Score {score} out of range"
                assert score >= 0.3, f"Score {score} below threshold"

    def test_discover_similar_predicates_from_conceptnet(self, temp_db):
        """
        Test discovering similar predicates from ConceptNet.

        Workflow:
        1. Create ConceptNet predicates in reference database
        2. Search for predicates related to relationships
        3. Verify ConceptNet predicates are found
        4. Verify semantic similarity matching works
        """
        config = ReferenceConfig()

        with ReferenceManager(config, db_path=temp_db) as manager:
            # Add ConceptNet relation predicates
            manager.add_external_predicate(
                title="RelatedTo",
                definition="General semantic relationship between concepts",
                source="conceptnet",
                external_id="/r/RelatedTo"
            )

            manager.add_external_predicate(
                title="IsA",
                definition="Indicates that one concept is a type or instance of another",
                source="conceptnet",
                external_id="/r/IsA"
            )

            manager.add_external_predicate(
                title="PartOf",
                definition="Indicates a part-whole relationship",
                source="conceptnet",
                external_id="/r/PartOf"
            )

            manager.add_external_predicate(
                title="HasProperty",
                definition="Indicates that an entity has a specific property or attribute",
                source="conceptnet",
                external_id="/r/HasProperty"
            )

            manager.add_external_predicate(
                title="Causes",
                definition="Indicates a causal relationship where one event causes another",
                source="conceptnet",
                external_id="/r/Causes"
            )

            # Search for hierarchy-related predicates
            hierarchy_results = manager.search_external_predicates_by_similarity(
                "type classification taxonomy hierarchy",
                source="conceptnet",
                threshold=0.3,
                limit=10
            )

            # Verify we found relevant predicates
            assert len(hierarchy_results) > 0, "Should find hierarchy-related ConceptNet predicates"

            # IsA should be among the results for hierarchy queries
            titles = [pred.title for pred, score in hierarchy_results]
            assert "IsA" in titles or "PartOf" in titles

            # Search for property-related predicates
            property_results = manager.search_external_predicates_by_similarity(
                "attribute characteristic property feature",
                source="conceptnet",
                threshold=0.3,
                limit=10
            )

            # Verify we found property-related predicates
            assert len(property_results) > 0, "Should find property-related ConceptNet predicates"

            property_titles = [pred.title for pred, score in property_results]
            assert "HasProperty" in property_titles or "RelatedTo" in property_titles

            # Verify all scores are valid
            for pred, score in hierarchy_results + property_results:
                assert 0.0 <= score <= 1.0, f"Score {score} out of range"
                assert pred.source == "conceptnet", f"Expected conceptnet, got {pred.source}"
