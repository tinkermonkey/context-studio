"""
Integration tests for SQLiteExtractionRepository.

Tests verify persistence of extraction results with:
- Real SQLite database (in-memory)
- Complete entity and layer metadata serialization
- Retrieval and pagination functionality
- Data integrity through save/load cycles
"""

import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
)

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from domain.extraction.entities import ExtractionResult, ExtractedEntity
from domain.extraction.value_objects import ExtractionLayerResult
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.extraction_repo import SQLiteExtractionRepository


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for integration tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_url = f"sqlite:///{db_path}"

        engine = create_engine(db_url)
        Base.metadata.create_all(engine)

        yield db_url


@pytest.fixture
def session_factory(temp_db):
    """Create a session factory for the temporary database."""
    engine = create_engine(temp_db)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal


@pytest.fixture
def repository(session_factory):
    """Create a real SQLiteExtractionRepository."""
    return SQLiteExtractionRepository(session_factory)


@pytest.fixture
def sample_extraction_result():
    """Create a sample extraction result for testing."""
    entity1 = ExtractedEntity(
        id=str(uuid4()),
        label="Apple",
        entity_type="ORGANIZATION",
        source_layer=1,
        confidence=0.95,
        uri="http://example.com/apple",
        description="A tech company",
        properties={"sector": "technology"},
    )

    entity2 = ExtractedEntity(
        id=str(uuid4()),
        label="Microsoft",
        entity_type="ORGANIZATION",
        source_layer=1,
        confidence=0.92,
        uri="http://example.com/microsoft",
        description="Another tech company",
        properties={"sector": "technology"},
    )

    layer0 = ExtractionLayerResult(
        layer_number=0,
        layer_name="Knowledge Graph Context",
        entities_found=0,
        duration_ms=100,
        success=True,
    )

    layer1 = ExtractionLayerResult(
        layer_number=1,
        layer_name="LLM Extraction",
        entities_found=2,
        duration_ms=1500,
        success=True,
    )

    layer2 = ExtractionLayerResult(
        layer_number=2,
        layer_name="NLP Gap-Filling",
        entities_found=0,
        duration_ms=200,
        success=True,
    )

    layer3 = ExtractionLayerResult(
        layer_number=3,
        layer_name="Reference Source Enrichment",
        entities_found=2,
        duration_ms=800,
        success=True,
    )

    result = ExtractionResult(
        id=str(uuid4()),
        text="Apple and Microsoft are companies.",
        extracted_entities=[entity1, entity2],
        layers_executed=[layer0, layer1, layer2, layer3],
        total_duration_ms=2600,
        created_at=datetime.now(timezone.utc),
    )

    return result


class TestSaveExtractionResult:
    """Tests for save_extraction_result()."""

    def test_save_extracts_result_to_db(self, repository, sample_extraction_result):
        """Save extraction result persists to database."""
        result = repository.save_extraction_result(sample_extraction_result)

        assert result.id is not None
        assert result.text == sample_extraction_result.text
        assert len(result.extracted_entities) == 2
        assert len(result.layers_executed) == 4

    def test_save_returns_same_result(self, repository, sample_extraction_result):
        """Save returns the same result that was saved."""
        result = repository.save_extraction_result(sample_extraction_result)

        assert result.id == sample_extraction_result.id
        assert result.text == sample_extraction_result.text
        assert result.total_duration_ms == sample_extraction_result.total_duration_ms

    def test_save_preserves_entity_metadata(self, repository, sample_extraction_result):
        """Save preserves all entity properties."""
        result = repository.save_extraction_result(sample_extraction_result)

        entity = result.extracted_entities[0]
        original = sample_extraction_result.extracted_entities[0]

        assert entity.label == original.label
        assert entity.entity_type == original.entity_type
        assert entity.source_layer == original.source_layer
        assert entity.confidence == original.confidence
        assert entity.uri == original.uri
        assert entity.description == original.description
        assert entity.properties == original.properties

    def test_save_preserves_layer_metadata(self, repository, sample_extraction_result):
        """Save preserves all layer execution metadata."""
        result = repository.save_extraction_result(sample_extraction_result)

        layer = result.layers_executed[1]
        original = sample_extraction_result.layers_executed[1]

        assert layer.layer_number == original.layer_number
        assert layer.layer_name == original.layer_name
        assert layer.entities_found == original.entities_found
        assert layer.duration_ms == original.duration_ms
        assert layer.success == original.success


class TestGetExtractionResult:
    """Tests for get_extraction_result()."""

    def test_get_returns_saved_result(self, repository, sample_extraction_result):
        """Get retrieves a previously saved result."""
        saved = repository.save_extraction_result(sample_extraction_result)
        retrieved = repository.get_extraction_result(saved.id)

        assert retrieved is not None
        assert retrieved.id == saved.id
        assert retrieved.text == saved.text

    def test_get_returns_none_for_nonexistent(self, repository):
        """Get returns None for non-existent result ID."""
        result = repository.get_extraction_result("nonexistent-id")
        assert result is None

    def test_get_preserves_entity_integrity(self, repository, sample_extraction_result):
        """Get preserves all entity properties."""
        saved = repository.save_extraction_result(sample_extraction_result)
        retrieved = repository.get_extraction_result(saved.id)

        assert len(retrieved.extracted_entities) == len(saved.extracted_entities)

        for retrieved_entity, saved_entity in zip(
            retrieved.extracted_entities, saved.extracted_entities
        ):
            assert retrieved_entity.id == saved_entity.id
            assert retrieved_entity.label == saved_entity.label
            assert retrieved_entity.entity_type == saved_entity.entity_type
            assert retrieved_entity.source_layer == saved_entity.source_layer
            assert retrieved_entity.confidence == saved_entity.confidence
            assert retrieved_entity.uri == saved_entity.uri
            assert retrieved_entity.description == saved_entity.description
            assert retrieved_entity.properties == saved_entity.properties

    def test_get_preserves_layer_integrity(self, repository, sample_extraction_result):
        """Get preserves all layer execution metadata."""
        saved = repository.save_extraction_result(sample_extraction_result)
        retrieved = repository.get_extraction_result(saved.id)

        assert len(retrieved.layers_executed) == len(saved.layers_executed)

        for retrieved_layer, saved_layer in zip(
            retrieved.layers_executed, saved.layers_executed
        ):
            assert retrieved_layer.layer_number == saved_layer.layer_number
            assert retrieved_layer.layer_name == saved_layer.layer_name
            assert retrieved_layer.entities_found == saved_layer.entities_found
            assert retrieved_layer.duration_ms == saved_layer.duration_ms
            assert retrieved_layer.success == saved_layer.success


class TestListExtractionResults:
    """Tests for list_extraction_results()."""

    def test_list_returns_all_results(self, repository, sample_extraction_result):
        """List returns all saved results."""
        result1 = repository.save_extraction_result(sample_extraction_result)

        # Create a second result
        result2_data = ExtractionResult(
            id=str(uuid4()),
            text="Another test",
            extracted_entities=[],
            layers_executed=[],
            total_duration_ms=100,
            created_at=datetime.now(timezone.utc),
        )
        result2 = repository.save_extraction_result(result2_data)

        results = repository.list_extraction_results(limit=100, offset=0)

        assert len(results) == 2
        result_ids = [r.id for r in results]
        assert result1.id in result_ids
        assert result2.id in result_ids

    def test_list_respects_limit(self, repository, sample_extraction_result):
        """List respects limit parameter."""
        # Save 5 results
        for i in range(5):
            result_data = ExtractionResult(
                id=str(uuid4()),
                text=f"Test {i}",
                extracted_entities=[],
                layers_executed=[],
                total_duration_ms=100,
                created_at=datetime.now(timezone.utc),
            )
            repository.save_extraction_result(result_data)

        results = repository.list_extraction_results(limit=3, offset=0)

        assert len(results) == 3

    def test_list_respects_offset(self, repository, sample_extraction_result):
        """List respects offset parameter."""
        # Save 5 results
        saved_ids = []
        for i in range(5):
            result_data = ExtractionResult(
                id=str(uuid4()),
                text=f"Test {i}",
                extracted_entities=[],
                layers_executed=[],
                total_duration_ms=100,
                created_at=datetime.now(timezone.utc),
            )
            saved = repository.save_extraction_result(result_data)
            saved_ids.append(saved.id)

        # Get first 2
        results_page1 = repository.list_extraction_results(limit=2, offset=0)
        assert len(results_page1) == 2

        # Get next 2
        results_page2 = repository.list_extraction_results(limit=2, offset=2)
        assert len(results_page2) == 2

        # Verify different results
        page1_ids = [r.id for r in results_page1]
        page2_ids = [r.id for r in results_page2]
        assert set(page1_ids) != set(page2_ids)

    def test_list_returns_most_recent_first(self, repository):
        """List returns results ordered by created_at descending."""
        # Save results with explicit timestamps to ensure consistent ordering
        result1 = repository.save_extraction_result(
            ExtractionResult(
                id=str(uuid4()),
                text="First",
                extracted_entities=[],
                layers_executed=[],
                total_duration_ms=100,
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        )

        result2 = repository.save_extraction_result(
            ExtractionResult(
                id=str(uuid4()),
                text="Second",
                extracted_entities=[],
                layers_executed=[],
                total_duration_ms=100,
                created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            )
        )

        results = repository.list_extraction_results(limit=10, offset=0)

        # Most recent (result2) should be first
        assert results[0].id == result2.id
        assert results[1].id == result1.id

    def test_list_returns_empty_for_out_of_range_offset(self, repository):
        """List returns empty sequence when offset exceeds result count."""
        repository.save_extraction_result(
            ExtractionResult(
                id=str(uuid4()),
                text="Test",
                extracted_entities=[],
                layers_executed=[],
                total_duration_ms=100,
                created_at=datetime.now(timezone.utc),
            )
        )

        results = repository.list_extraction_results(limit=10, offset=100)

        assert len(results) == 0
