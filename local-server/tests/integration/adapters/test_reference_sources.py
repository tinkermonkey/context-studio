"""Integration tests for reference source adapters."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest


@pytest.mark.reference
def test_conceptnet_source_search():
    """Test ConceptNet source search with network access."""
    from adapters.reference.conceptnet import ConceptNetSource

    source = ConceptNetSource(timeout=10)

    if not source.is_available():
        pytest.skip("ConceptNet API is not available")

    results = source.search("dog", limit=5)

    assert isinstance(results, list)
    assert len(results) > 0
    assert all(r.uri for r in results)
    assert all(r.label for r in results)
    assert all(r.source == "ConceptNet" for r in results)


@pytest.mark.reference
def test_conceptnet_source_is_available():
    """Test ConceptNet is_available() method."""
    from adapters.reference.conceptnet import ConceptNetSource

    source = ConceptNetSource(timeout=10)
    available = source.is_available()

    assert isinstance(available, bool)
    # Note: don't assert True/False as it depends on network


@pytest.mark.reference
def test_conceptnet_source_gracefully_handles_unavailable():
    """Test ConceptNet search returns empty list when unavailable."""
    from adapters.reference.conceptnet import ConceptNetSource

    source = ConceptNetSource(timeout=0.001)  # Very short timeout
    results = source.search("test", limit=5)

    # Should return empty list, not raise
    assert results == []


@pytest.mark.reference
def test_dbpedia_source_search():
    """Test DBpedia source search with network access."""
    from adapters.reference.dbpedia import DBpediaSource

    source = DBpediaSource(timeout=10)

    if not source.is_available():
        pytest.skip("DBpedia API is not available")

    results = source.search("apple", limit=5)

    assert isinstance(results, list)
    # DBpedia may return 0 results for some queries, which is valid
    if results:
        assert all(r.uri for r in results)
        assert all(r.label for r in results)
        assert all(r.source == "DBpedia" for r in results)


@pytest.mark.reference
def test_dbpedia_source_is_available():
    """Test DBpedia is_available() method."""
    from adapters.reference.dbpedia import DBpediaSource

    source = DBpediaSource(timeout=10)
    available = source.is_available()

    assert isinstance(available, bool)


@pytest.mark.reference
def test_wikidata_source_search():
    """Test Wikidata source search with network access."""
    from adapters.reference.wikidata import WikidataSource

    source = WikidataSource(timeout=10)

    if not source.is_available():
        pytest.skip("Wikidata API is not available")

    results = source.search("python", limit=5)

    assert isinstance(results, list)
    # Wikidata should return results for common terms
    assert len(results) > 0
    assert all(r.uri for r in results)
    assert all(r.label for r in results)
    assert all(r.source == "Wikidata" for r in results)
    # Verify URI format
    assert all(r.uri.startswith("http://www.wikidata.org/entity/Q") for r in results)


@pytest.mark.reference
def test_wikidata_source_get_relations():
    """Test Wikidata get_relations() with real entity."""
    from adapters.reference.wikidata import WikidataSource

    source = WikidataSource(timeout=10)

    if not source.is_available():
        pytest.skip("Wikidata API is not available")

    # Q42 is Douglas Adams
    uri = "http://www.wikidata.org/entity/Q42"
    relations = source.get_relations(uri, limit=5)

    assert isinstance(relations, list)
    # May or may not have relations depending on query
    if relations:
        assert all(r.subject_uri for r in relations)
        assert all(r.predicate for r in relations)
        assert all(r.object_uri for r in relations)
        assert all(r.source == "Wikidata" for r in relations)


@pytest.mark.reference
def test_schema_org_source_search():
    """Test schema.org source search (always available)."""
    from adapters.reference.schema_org import SchemaOrgSource

    source = SchemaOrgSource()

    assert source.is_available() is True

    results = source.search("person", limit=10)

    assert isinstance(results, list)
    assert len(results) > 0
    assert any(r.label.lower() == "person" for r in results)
    assert all(r.source == "schema.org" for r in results)


@pytest.mark.reference
def test_schema_org_source_get_relations():
    """Test schema.org get_relations()."""
    from adapters.reference.schema_org import SchemaOrgSource

    source = SchemaOrgSource()

    uri = "http://schema.org/Person"
    relations = source.get_relations(uri, limit=10)

    assert isinstance(relations, list)
    assert all(r.subject_uri for r in relations)
    assert all(r.predicate for r in relations)
    assert all(r.object_uri for r in relations)


class TestLocalReferenceRepository:
    """Tests for LocalReferenceRepository."""

    def test_search_returns_empty_for_nonexistent(self):
        """Test search returns empty list for nonexistent terms."""
        import tempfile
        from pathlib import Path

        from adapters.persistence.sqlite.reference_repo import LocalReferenceRepository

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = LocalReferenceRepository(str(db_path))

            results = repo.search("nonexistent_term_xyz", limit=10)

            assert results == []

    def test_import_and_search(self):
        """Test importing and searching references."""
        import tempfile
        from pathlib import Path

        from adapters.persistence.sqlite.reference_repo import LocalReferenceRepository

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = LocalReferenceRepository(str(db_path))

            # Import a reference
            repo.import_reference(
                uri="http://example.org/person/alice",
                label="Alice",
                description="A person",
                source="test",
            )

            # Search for it
            results = repo.search("Alice", limit=10)

            assert len(results) == 1
            assert results[0].uri == "http://example.org/person/alice"
            assert results[0].label == "Alice"

    def test_import_relation_and_get(self):
        """Test importing and retrieving relations."""
        import tempfile
        from pathlib import Path

        from adapters.persistence.sqlite.reference_repo import LocalReferenceRepository

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = LocalReferenceRepository(str(db_path))

            uri = "http://example.org/person/alice"

            repo.import_relation(
                subject_uri=uri,
                predicate="knows",
                object_uri="http://example.org/person/bob",
                source="test",
            )

            relations = repo.get_relations(uri, limit=10)

            assert len(relations) == 1
            assert relations[0].subject_uri == uri
            assert relations[0].predicate == "knows"

    def test_import_is_idempotent(self):
        """Test that import is idempotent (safe to re-run)."""
        import tempfile
        from pathlib import Path

        from adapters.persistence.sqlite.reference_repo import LocalReferenceRepository

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            repo = LocalReferenceRepository(str(db_path))

            uri = "http://example.org/test"

            # Import twice
            repo.import_reference(
                uri=uri,
                label="Test",
                description="Test reference",
                source="test",
            )

            repo.import_reference(
                uri=uri,
                label="Test Updated",
                description="Updated description",
                source="test",
            )

            # Should only have one entry
            results = repo.search("Test", limit=10)
            assert len(results) == 1
            assert results[0].label == "Test Updated"


class TestCachedReferenceSourceIntegration:
    """Integration tests for CachedReferenceSource with real sources."""

    @pytest.mark.reference
    def test_cached_conceptnet_source(self):
        """Test CachedReferenceSource wrapping ConceptNet."""
        import tempfile
        from pathlib import Path

        from adapters.reference.conceptnet import ConceptNetSource
        from adapters.reference.cache import CachedReferenceSource

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_db = Path(tmpdir) / "cache.db"
            inner = ConceptNetSource()

            if not inner.is_available():
                pytest.skip("ConceptNet API is not available")

            cached = CachedReferenceSource(inner, str(cache_db))

            # First search
            results1 = cached.search("water", limit=5)

            # Second search (should be cached)
            results2 = cached.search("water", limit=5)

            assert results1 == results2
            assert len(results1) > 0

    def test_cached_schema_org_source(self):
        """Test CachedReferenceSource wrapping schema.org."""
        import tempfile
        from pathlib import Path

        from adapters.reference.schema_org import SchemaOrgSource
        from adapters.reference.cache import CachedReferenceSource

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_db = Path(tmpdir) / "cache.db"
            inner = SchemaOrgSource()
            cached = CachedReferenceSource(inner, str(cache_db))

            # Search multiple times
            results1 = cached.search("type", limit=10)
            results2 = cached.search("type", limit=10)

            assert results1 == results2
            assert len(results1) > 0
