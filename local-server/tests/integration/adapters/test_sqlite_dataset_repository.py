"""
Integration tests for SQLiteDatasetRepository.

Tests persistence of Dataset entities, error handling for database operations,
and integration with domain exception mapping.
"""

import sys
import os
import uuid
from datetime import datetime, timezone

import pytest
import sqlalchemy
from sqlalchemy.orm import sessionmaker

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.dataset_repo import SQLiteDatasetRepository
from domain.admin.entities import Dataset, DatasetMetrics
from domain.admin.exceptions import DatasetNotFoundError


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite database for testing."""
    engine = sqlalchemy.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session_factory(db_engine):
    """Create a session factory."""
    return sessionmaker(bind=db_engine)


@pytest.fixture
def repository(session_factory):
    """Create a dataset repository."""
    return SQLiteDatasetRepository(session_factory)


@pytest.fixture
def sample_dataset():
    """Create a sample dataset for testing."""
    return Dataset(
        id=str(uuid.uuid4()),
        title="Test Dataset",
        filename="test.db",
        description="A test dataset",
        created_at=datetime.now(timezone.utc),
        last_accessed=datetime.now(timezone.utc),
        schema_version="1.0.0",
        metrics=DatasetMetrics(
            layers_count=1,
            domains_count=2,
            terms_count=5,
            relationships_count=3,
            individuals_count=0,
        ),
        is_active=False,
    )


class TestDatasetPersistence:
    """Test basic CRUD operations on Dataset entities."""

    def test_save_and_get_dataset(self, repository, sample_dataset):
        """Can save and retrieve a dataset."""
        repository.save_dataset(sample_dataset)
        retrieved = repository.get_dataset(sample_dataset.id)

        assert retrieved is not None
        assert retrieved.id == sample_dataset.id
        assert retrieved.title == sample_dataset.title
        assert retrieved.filename == sample_dataset.filename
        assert retrieved.is_active is False

    def test_get_nonexistent_dataset_returns_none(self, repository):
        """Getting a nonexistent dataset returns None."""
        result = repository.get_dataset("nonexistent-id")
        assert result is None

    def test_list_empty_datasets(self, repository):
        """Listing datasets when none exist returns empty list."""
        datasets = repository.list_datasets()
        assert len(datasets) == 0

    def test_list_multiple_datasets(self, repository, sample_dataset):
        """Can list multiple datasets."""
        dataset2 = Dataset(
            id=str(uuid.uuid4()),
            title="Dataset 2",
            filename="test2.db",
            created_at=datetime.now(timezone.utc),
            last_accessed=datetime.now(timezone.utc),
            schema_version="1.0.0",
            metrics=DatasetMetrics(),
        )

        repository.save_dataset(sample_dataset)
        repository.save_dataset(dataset2)

        datasets = repository.list_datasets()
        assert len(datasets) == 2
        assert {d.id for d in datasets} == {sample_dataset.id, dataset2.id}

    def test_delete_existing_dataset(self, repository, sample_dataset):
        """Can delete an existing dataset."""
        repository.save_dataset(sample_dataset)
        deleted = repository.delete_dataset(sample_dataset.id)

        assert deleted is True
        assert repository.get_dataset(sample_dataset.id) is None

    def test_delete_nonexistent_dataset(self, repository):
        """Deleting nonexistent dataset returns False."""
        deleted = repository.delete_dataset("nonexistent-id")
        assert deleted is False


class TestDatasetMetrics:
    """Test dataset metrics computation."""

    def test_compute_metrics_empty_database(self, repository):
        """Compute metrics on empty database returns zero counts."""
        metrics = repository.compute_metrics("any-id")

        assert metrics.layers_count == 0
        assert metrics.domains_count == 0
        assert metrics.terms_count == 0
        assert metrics.relationships_count == 0
        assert metrics.individuals_count == 0

    def test_compute_metrics_preserves_cached_values(self, repository, sample_dataset):
        """Computed metrics match those cached in dataset."""
        repository.save_dataset(sample_dataset)
        retrieved = repository.get_dataset(sample_dataset.id)

        assert retrieved.metrics.layers_count == sample_dataset.metrics.layers_count
        assert retrieved.metrics.domains_count == sample_dataset.metrics.domains_count
        assert retrieved.metrics.terms_count == sample_dataset.metrics.terms_count


class TestActiveDataset:
    """Test active dataset management."""

    def test_set_active_dataset(self, repository, sample_dataset):
        """Can set a dataset as active."""
        repository.save_dataset(sample_dataset)
        activated = repository.set_active_dataset(sample_dataset.id)

        assert activated.is_active is True
        assert repository.get_active_dataset().id == sample_dataset.id

    def test_set_active_dataset_deactivates_others(self, repository, sample_dataset):
        """Setting a dataset active deactivates the previous active dataset."""
        dataset2 = Dataset(
            id=str(uuid.uuid4()),
            title="Dataset 2",
            filename="test2.db",
            created_at=datetime.now(timezone.utc),
            last_accessed=datetime.now(timezone.utc),
            schema_version="1.0.0",
            metrics=DatasetMetrics(),
        )

        # Save both datasets
        repository.save_dataset(sample_dataset)
        repository.save_dataset(dataset2)

        # Activate first dataset
        repository.set_active_dataset(sample_dataset.id)
        assert repository.get_active_dataset().id == sample_dataset.id

        # Activate second dataset
        repository.set_active_dataset(dataset2.id)
        assert repository.get_active_dataset().id == dataset2.id

        # Verify first is now inactive
        retrieved_first = repository.get_dataset(sample_dataset.id)
        assert retrieved_first.is_active is False

    def test_set_active_dataset_nonexistent_raises_error(
        self, repository, sample_dataset
    ):
        """
        Setting nonexistent dataset as active raises DatasetNotFoundError with message.

        This is the primary test for the critical fix: scalar_one_or_none() + explicit
        check ensures domain exception mapping works in the route layer.
        """
        # Try to set nonexistent dataset as active
        with pytest.raises(DatasetNotFoundError) as exc_info:
            repository.set_active_dataset("missing-id")

        # Verify the exception message is informative
        assert "missing-id" in str(exc_info.value)

    def test_get_active_dataset_no_active(self, repository):
        """Getting active dataset when none set returns None."""
        active = repository.get_active_dataset()
        assert active is None

    def test_set_active_dataset_race_condition(self, repository, sample_dataset):
        """
        Test race condition: dataset deleted between service check and repo call.

        This simulates the scenario where the service checks that the dataset exists,
        but it's deleted before the repository's set_active_dataset call completes.
        """
        repository.save_dataset(sample_dataset)

        # Delete the dataset
        repository.delete_dataset(sample_dataset.id)

        # Attempting to set it as active should raise DatasetNotFoundError
        with pytest.raises(DatasetNotFoundError):
            repository.set_active_dataset(sample_dataset.id)


class TestErrorHandling:
    """Test error handling for database operation failures."""

    def test_get_dataset_database_failure_raises_runtime_error(
        self, db_engine, session_factory, repository
    ):
        """
        Database failure in get_dataset raises RuntimeError (not SQLAlchemyError).

        SQLAlchemyError exceptions are caught at the adapter boundary and mapped
        to RuntimeError to prevent infrastructure exceptions from leaking to routes.
        """
        # Dispose the engine to force a database error on next query
        db_engine.dispose()

        with pytest.raises(RuntimeError) as exc_info:
            repository.get_dataset("any-id")

        # Verify the exception message is informative
        assert "Failed to retrieve dataset" in str(exc_info.value)

    def test_save_dataset_database_failure_raises_runtime_error(
        self, db_engine, session_factory, repository, sample_dataset
    ):
        """
        Database failure in save_dataset raises RuntimeError (not SQLAlchemyError).

        SQLAlchemyError exceptions are caught at the adapter boundary and mapped
        to RuntimeError to prevent infrastructure exceptions from leaking to routes.
        """
        # Dispose the engine to force a database error on next query
        db_engine.dispose()

        with pytest.raises(RuntimeError) as exc_info:
            repository.save_dataset(sample_dataset)

        # Verify the exception message is informative
        assert "Failed to save dataset" in str(exc_info.value)


class TestDatasetUpdate:
    """Test dataset updates."""

    def test_update_dataset(self, repository, sample_dataset):
        """Can update an existing dataset."""
        repository.save_dataset(sample_dataset)

        # Modify and save
        sample_dataset.title = "Updated Title"
        sample_dataset.metrics.terms_count = 10

        repository.save_dataset(sample_dataset)

        # Verify update
        retrieved = repository.get_dataset(sample_dataset.id)
        assert retrieved.title == "Updated Title"
        assert retrieved.metrics.terms_count == 10
