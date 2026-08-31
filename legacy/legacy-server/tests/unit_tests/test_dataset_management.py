"""Unit tests for dataset management functionality."""

import os
import shutil
import sys
import tempfile

import pytest

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.migrations.migration_manager import MigrationManager
from dataset.manager import DatasetManager
from dataset.models import DatasetMetrics


class TestDatasetManager:
    """Test cases for DatasetManager."""

    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.datasets_dir = os.path.join(self.temp_dir, "datasets")
        self.config_path = os.path.join(self.temp_dir, "datasets.json")

        self.manager = DatasetManager(
            datasets_config_path=self.config_path, datasets_directory=self.datasets_dir
        )

    def teardown_method(self):
        """Cleanup test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_dataset(self):
        """Test creating a new dataset."""
        dataset = self.manager.create_dataset("Test Dataset", "test.db")

        assert dataset.title == "Test Dataset"
        assert dataset.filename == "test.db"

        # Verify schema version matches the target version from migration manager
        dataset_path = self.manager.get_dataset_file_path("test.db")
        migration_manager = MigrationManager(dataset_path)
        assert (
            dataset.schema_version == migration_manager.target_version
        ), f"Expected schema version {migration_manager.target_version}, got {dataset.schema_version}"

        assert isinstance(dataset.metrics, DatasetMetrics)

        # Verify file was created
        assert os.path.exists(dataset_path)

    def test_list_datasets(self):
        """Test listing datasets."""
        # Initially empty
        datasets = self.manager.list_datasets()
        assert len(datasets) == 0

        # Create datasets
        self.manager.create_dataset("Dataset 1", "test1.db")
        self.manager.create_dataset("Dataset 2", "test2.db")

        datasets = self.manager.list_datasets()
        assert len(datasets) == 2
        assert datasets[0].title == "Dataset 1"
        assert datasets[1].title == "Dataset 2"

    def test_switch_dataset(self):
        """Test switching between datasets."""
        dataset1 = self.manager.create_dataset("Dataset 1", "test1.db")
        dataset2 = self.manager.create_dataset("Dataset 2", "test2.db")

        # Initially, dataset1 should be active (first created)
        assert self.manager.active_dataset_id == dataset1.id

        # Switch to dataset2
        success = self.manager.switch_dataset(dataset2.id)
        assert success
        assert self.manager.active_dataset_id == dataset2.id

        # Verify active dataset
        active = self.manager.get_active_dataset()
        assert active.id == dataset2.id
        assert active.title == "Dataset 2"

    def test_delete_dataset(self):
        """Test deleting a dataset."""
        dataset = self.manager.create_dataset("Test Dataset", "test.db")
        dataset_path = self.manager.get_dataset_file_path("test.db")

        # Verify file exists
        assert os.path.exists(dataset_path)

        # Delete dataset
        success = self.manager.delete_dataset(dataset.id)
        assert success

        # Verify file is deleted
        assert not os.path.exists(dataset_path)

        # Verify dataset is removed from list
        datasets = self.manager.list_datasets()
        assert len(datasets) == 0

    def test_duplicate_title_error(self):
        """Test that duplicate titles raise an error."""
        self.manager.create_dataset("Test Dataset", "test1.db")

        with pytest.raises(
            ValueError, match="Dataset with title 'Test Dataset' already exists"
        ):
            self.manager.create_dataset("Test Dataset", "test2.db")

    def test_duplicate_filename_error(self):
        """Test that duplicate filenames raise an error."""
        self.manager.create_dataset("Dataset 1", "test.db")

        with pytest.raises(
            ValueError, match="Dataset with filename 'test.db' already exists"
        ):
            self.manager.create_dataset("Dataset 2", "test.db")

    def test_get_dataset_metrics(self):
        """Test getting dataset metrics."""
        dataset = self.manager.create_dataset("Test Dataset", "test.db")

        metrics = self.manager.get_dataset_metrics(dataset.id)
        assert isinstance(metrics, DatasetMetrics)
        assert metrics.layers_count == 0
        assert metrics.domains_count == 0
        assert metrics.terms_count == 0
        assert metrics.relationships_count == 0

    def test_update_datasets_directory(self):
        """Test updating the datasets directory."""
        new_dir = os.path.join(self.temp_dir, "new_datasets")

        success = self.manager.update_datasets_directory(new_dir)
        assert success
        assert self.manager.datasets_directory == new_dir
        assert os.path.exists(new_dir)

    def test_add_existing_dataset(self):
        """Test adding an existing dataset file."""
        # Create a temporary dataset file outside the datasets directory
        external_file = os.path.join(self.temp_dir, "external.db")

        # Create a real dataset first to get a valid file
        self.manager.create_dataset("Original", "original.db")
        original_path = self.manager.get_dataset_file_path("original.db")

        # Copy it to external location
        shutil.copy2(original_path, external_file)

        # Add the external file
        added_dataset = self.manager.add_existing_dataset(
            "External Dataset", external_file
        )

        assert added_dataset.title == "External Dataset"
        assert added_dataset.filename == "external.db"
        assert added_dataset.schema_version >= 1

        # Verify file was copied to datasets directory
        expected_path = self.manager.get_dataset_file_path("external.db")
        assert os.path.exists(expected_path)

        # Verify it appears in list
        datasets = self.manager.list_datasets()
        assert len(datasets) == 2  # original + added
        assert any(d.title == "External Dataset" for d in datasets)

    def test_add_existing_dataset_duplicate_title(self):
        """Test adding existing dataset with duplicate title fails."""
        # Create original dataset
        self.manager.create_dataset("Test Dataset", "test1.db")

        # Try to add another with same title
        external_file = os.path.join(self.temp_dir, "external.db")
        original_path = self.manager.get_dataset_file_path("test1.db")
        shutil.copy2(original_path, external_file)

        with pytest.raises(
            ValueError, match="Dataset with title 'Test Dataset' already exists"
        ):
            self.manager.add_existing_dataset("Test Dataset", external_file)

    def test_add_existing_dataset_nonexistent_file(self):
        """Test adding non-existent file fails."""
        with pytest.raises(ValueError, match="Dataset file does not exist"):
            self.manager.add_existing_dataset("Test", "/nonexistent/file.db")

    def test_add_existing_dataset_invalid_file(self):
        """Test adding invalid SQLite file fails."""
        # Create a non-SQLite file
        invalid_file = os.path.join(self.temp_dir, "invalid.db")
        with open(invalid_file, "w") as f:
            f.write("This is not a SQLite database")

        with pytest.raises(ValueError, match="Failed to validate dataset file"):
            self.manager.add_existing_dataset("Invalid", invalid_file)

    def test_forget_dataset(self):
        """Test forgetting a dataset (removing from inventory but keeping file)."""
        # Create dataset
        dataset = self.manager.create_dataset("Test Dataset", "test.db")
        dataset_path = self.manager.get_dataset_file_path("test.db")

        # Verify it exists
        assert os.path.exists(dataset_path)
        datasets = self.manager.list_datasets()
        assert len(datasets) == 1

        # Forget it
        success = self.manager.forget_dataset(dataset.id)
        assert success

        # Verify it's no longer in inventory
        datasets = self.manager.list_datasets()
        assert len(datasets) == 0

        # But file still exists
        assert os.path.exists(dataset_path)

    def test_forget_dataset_not_found(self):
        """Test forgetting non-existent dataset returns False."""
        success = self.manager.forget_dataset("nonexistent-id")
        assert not success

    def test_forget_active_dataset(self):
        """Test forgetting the active dataset clears active state."""
        dataset = self.manager.create_dataset("Test Dataset", "test.db")

        # Make sure it's active
        assert self.manager.active_dataset_id == dataset.id

        # Forget it
        success = self.manager.forget_dataset(dataset.id)
        assert success

        # Active state should be cleared
        assert self.manager.active_dataset_id is None


class TestMigrationManager:
    """Test cases for MigrationManager."""

    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.manager = MigrationManager(self.db_path)

    def teardown_method(self):
        """Cleanup test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_migration_status(self):
        """Test getting migration status."""
        status = self.manager.get_migration_status()

        assert status.current_version == 0
        assert status.target_version >= 3  # Should have at least 3 migrations
        assert status.needs_migration
        assert len(status.pending_migrations) > 0

    def test_migrate_to_latest(self):
        """Test applying migrations."""
        # Check initial status
        initial_status = self.manager.get_migration_status()
        assert initial_status.needs_migration

        # Apply migrations
        success = self.manager.migrate_to_latest()
        assert success

        # Check status after migration
        final_status = self.manager.get_migration_status()
        assert not final_status.needs_migration
        assert final_status.current_version > 0

    def test_generate_migration(self):
        """Test generating a new migration file."""
        description = "Test migration"
        filepath = self.manager.generate_migration(description)

        assert os.path.exists(filepath)
        assert description.lower().replace(" ", "_") in filepath

        # Cleanup generated file
        os.remove(filepath)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
