"""
Unit tests for Phase 2: Verify datafiles directory creation across all database managers.

This test suite ensures that all database initialization code properly creates
the /datafiles/ directory before attempting to create or access database files.
"""

import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock


class TestPipelineDatabaseManager:
    """Test datafiles directory creation in operations database manager."""

    def test_operations_db_creates_datafiles_directory(self):
        """Test that PipelineDatabaseManager creates /datafiles/ directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set up operations database path in a non-existent datafiles directory
            db_dir = os.path.join(temp_dir, "datafiles")
            db_path = os.path.join(db_dir, "operations.db")

            # Ensure directory does not exist initially
            assert not os.path.exists(db_dir)

            # Import and initialize pipeline manager
            from pipeline.manager import PipelineDatabaseManager

            manager = PipelineDatabaseManager(operations_db_path=db_path)

            # Verify directory was created
            assert os.path.exists(db_dir)
            assert os.path.isdir(db_dir)

            # Verify database file was created
            assert os.path.exists(db_path)

            # Clean up
            manager.engine.dispose()

    def test_operations_db_handles_existing_directory(self):
        """Test that PipelineDatabaseManager works when directory already exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set up operations database path with existing datafiles directory
            db_dir = os.path.join(temp_dir, "datafiles")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "operations.db")

            # Import and initialize pipeline manager
            from pipeline.manager import PipelineDatabaseManager

            manager = PipelineDatabaseManager(operations_db_path=db_path)

            # Verify no errors occurred
            assert os.path.exists(db_dir)
            assert os.path.exists(db_path)

            # Clean up
            manager.engine.dispose()

    def test_operations_db_uses_config_default_path(self):
        """Test that PipelineDatabaseManager uses config default path correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock settings to use temp directory
            mock_settings = MagicMock()
            mock_settings.database.operations_path = os.path.join(
                temp_dir, "datafiles", "operations.db"
            )

            with patch("config.get_settings", return_value=mock_settings):
                from pipeline.manager import PipelineDatabaseManager

                manager = PipelineDatabaseManager()

                # Verify directory was created from config
                expected_dir = os.path.join(temp_dir, "datafiles")
                assert os.path.exists(expected_dir)

                # Clean up
                manager.engine.dispose()


class TestReferenceDatabaseManager:
    """Test datafiles directory creation in reference database manager."""

    def test_reference_db_creates_datafiles_directory(self):
        """Test that ReferenceManager creates /datafiles/ directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set up reference database path in a non-existent datafiles directory
            db_dir = os.path.join(temp_dir, "datafiles")
            db_path = os.path.join(db_dir, "reference.db")

            # Ensure directory does not exist initially
            assert not os.path.exists(db_dir)

            # Import and initialize reference manager
            from reference_db.manager import ReferenceManager
            from reference_db.config import ReferenceConfig

            config = ReferenceConfig()
            manager = ReferenceManager(config, db_path=db_path)

            # Verify directory was created
            assert os.path.exists(db_dir)
            assert os.path.isdir(db_dir)

            # Verify database file was created
            assert os.path.exists(db_path)

            # Clean up
            manager.close()

    def test_reference_db_handles_existing_directory(self):
        """Test that ReferenceManager works when directory already exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set up reference database path with existing datafiles directory
            db_dir = os.path.join(temp_dir, "datafiles")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "reference.db")

            # Import and initialize reference manager
            from reference_db.manager import ReferenceManager
            from reference_db.config import ReferenceConfig

            config = ReferenceConfig()
            manager = ReferenceManager(config, db_path=db_path)

            # Verify no errors occurred
            assert os.path.exists(db_dir)
            assert os.path.exists(db_path)

            # Clean up
            manager.close()


class TestDatasetManager:
    """Test directory creation in dataset manager."""

    def test_dataset_manager_creates_datasets_directory(self):
        """Test that DatasetManager creates datasets directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            datasets_dir = os.path.join(temp_dir, "datasets")

            # Ensure directory does not exist initially
            assert not os.path.exists(datasets_dir)

            # Import and initialize dataset manager
            from dataset.manager import DatasetManager

            config_path = os.path.join(temp_dir, "datasets.json")
            DatasetManager(
                datasets_config_path=config_path, datasets_directory=datasets_dir
            )

            # Verify directory was created
            assert os.path.exists(datasets_dir)
            assert os.path.isdir(datasets_dir)

    def test_dataset_manager_handles_existing_directory(self):
        """Test that DatasetManager works when directory already exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            datasets_dir = os.path.join(temp_dir, "datasets")
            os.makedirs(datasets_dir, exist_ok=True)

            # Import and initialize dataset manager
            from dataset.manager import DatasetManager

            config_path = os.path.join(temp_dir, "datasets.json")
            DatasetManager(
                datasets_config_path=config_path, datasets_directory=datasets_dir
            )

            # Verify no errors occurred
            assert os.path.exists(datasets_dir)


class TestDirectoryCreationPatterns:
    """Test that directory creation patterns are consistent across all managers."""

    def test_all_managers_use_makedirs_with_exist_ok(self):
        """Verify all database managers use os.makedirs(dir, exist_ok=True) pattern."""
        import inspect

        # List of manager modules to check
        manager_modules = [
            "pipeline.manager",
            "reference_db.manager",
            "dataset.manager",
            "nlp.proxy_manager",
        ]

        for module_name in manager_modules:
            module = __import__(module_name, fromlist=[""])

            # Get source code of the module
            source = inspect.getsource(module)

            # Check for directory creation pattern
            assert (
                "os.makedirs" in source
            ), f"{module_name} should use os.makedirs for directory creation"
            assert (
                "exist_ok=True" in source
            ), f"{module_name} should use exist_ok=True to handle existing directories"

    def test_directory_creation_before_database_access(self):
        """Verify directory creation happens before first database access in each manager."""
        # This test checks the order of operations in each manager's __init__
        import inspect

        # For PipelineDatabaseManager
        from pipeline.manager import PipelineDatabaseManager

        init_source = inspect.getsource(PipelineDatabaseManager.__init__)

        # Find position of makedirs and database initialization
        makedirs_pos = init_source.find("os.makedirs")
        db_init_pos = init_source.find("self._initialize_database")

        assert (
            makedirs_pos < db_init_pos
        ), "Pipeline manager should create directory before initializing database"

        # For ReferenceManager
        from reference_db.manager import ReferenceManager

        init_method_source = inspect.getsource(ReferenceManager._initialize_database)

        makedirs_pos = init_method_source.find("os.makedirs")
        engine_pos = init_method_source.find("create_engine")

        assert (
            makedirs_pos < engine_pos
        ), "Reference manager should create directory before creating engine"


class TestFreshInstallation:
    """Test application startup on fresh installation (no datafiles directory)."""

    def test_fresh_install_creates_all_directories(self):
        """Test that all required directories are created on fresh installation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Simulate fresh installation - no datafiles directory
            datafiles_dir = os.path.join(temp_dir, "datafiles")
            assert not os.path.exists(datafiles_dir)

            # Initialize all managers that use datafiles
            from pipeline.manager import PipelineDatabaseManager
            from reference_db.manager import ReferenceManager
            from reference_db.config import ReferenceConfig

            # Create pipeline manager
            operations_db_path = os.path.join(datafiles_dir, "operations.db")
            pipeline_manager = PipelineDatabaseManager(
                operations_db_path=operations_db_path
            )

            # Verify datafiles directory was created
            assert os.path.exists(datafiles_dir)

            # Create reference manager
            reference_db_path = os.path.join(datafiles_dir, "reference.db")
            reference_config = ReferenceConfig()
            reference_manager = ReferenceManager(
                reference_config, db_path=reference_db_path
            )

            # Verify all databases exist
            assert os.path.exists(operations_db_path)
            assert os.path.exists(reference_db_path)

            # Clean up
            pipeline_manager.engine.dispose()
            reference_manager.close()

    def test_appropriate_file_permissions(self):
        """Test that created directories have appropriate file permissions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            datafiles_dir = os.path.join(temp_dir, "datafiles")
            db_path = os.path.join(datafiles_dir, "operations.db")

            from pipeline.manager import PipelineDatabaseManager

            manager = PipelineDatabaseManager(operations_db_path=db_path)

            # Check directory permissions
            os.stat(datafiles_dir)

            # Directory should be readable, writable, and executable by owner
            # On Unix-like systems, this is typically 0o755 or 0o700
            # We just verify it's a directory and accessible
            assert os.path.isdir(datafiles_dir)
            assert os.access(datafiles_dir, os.R_OK | os.W_OK | os.X_OK)

            # Clean up
            manager.engine.dispose()


class TestErrorHandling:
    """Test error handling for directory creation failures."""

    def test_handles_permission_errors_gracefully(self):
        """Test that managers handle permission errors appropriately."""
        # Note: This test may require elevated permissions or may be skipped on some systems
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a read-only parent directory
            readonly_dir = os.path.join(temp_dir, "readonly")
            os.makedirs(readonly_dir)
            os.chmod(readonly_dir, 0o444)  # Read-only

            db_path = os.path.join(readonly_dir, "datafiles", "test.db")

            try:
                from pipeline.manager import PipelineDatabaseManager

                # This should raise an error due to permissions
                with pytest.raises((OSError, PermissionError)):
                    PipelineDatabaseManager(operations_db_path=db_path)
            finally:
                # Restore permissions for cleanup
                os.chmod(readonly_dir, 0o755)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
