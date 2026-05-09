"""
Test environment context manager for complete test isolation.

This module provides a context manager that handles both configuration
and database setup with automatic cleanup, ensuring complete isolation
between tests and from the development environment.
"""

import tempfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, cast
from contextlib import contextmanager

from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

from tests.test_config import TestConfigurationManager
from tests.test_db_utils import TestDatabaseManager
from config import Settings


class TestEnvironment:
    """
    Complete test environment with configuration and database isolation.

    This class provides a comprehensive test environment that isolates
    both configuration and database resources, ensuring no test artifacts
    pollute the development environment.
    """

    def __init__(
        self,
        temp_dir: Optional[str] = None,
        config_overrides: Optional[Dict[str, Any]] = None,
    ):  # noqa: E501
        """
        Initialize test environment.

        Args:
            temp_dir: Optional temporary directory path. If not provided,
                     a new temporary directory will be created.
            config_overrides: Optional configuration overrides to apply
        """
        # Create or use provided temporary directory
        if temp_dir:
            self.temp_dir = Path(temp_dir)
            self.temp_dir.mkdir(exist_ok=True)
            self._cleanup_temp_dir = False
        else:
            self.temp_dir = Path(tempfile.mkdtemp(prefix="test_env_"))
            self._cleanup_temp_dir = True

        # Initialize configuration manager
        self.config_manager = TestConfigurationManager(str(self.temp_dir))
        self.config_overrides = config_overrides or {}

        # Initialize database manager
        self.db_manager = TestDatabaseManager(str(self.temp_dir))

        # Track created resources
        self.settings: Optional[Settings] = None
        self.primary_engine: Optional[Engine] = None
        self.primary_session_local: Optional[sessionmaker] = None
        self.primary_db_path: Optional[Path] = None

    def setup(self) -> Tuple[Settings, Engine, sessionmaker]:
        """
        Set up the test environment.

        Returns:
            Tuple of (settings, engine, session_local_factory)
        """
        # Create isolated configuration
        self.settings = self.config_manager.get_test_settings(
            self.config_overrides
        )  # noqa: E501

        # Create primary database with migrations
        (
            self.primary_engine,
            self.primary_session_local,
            self.primary_db_path,
        ) = self.db_manager.create_migrated_database(  # noqa: E501
            "primary_test.db"
        )

        return self.settings, self.primary_engine, self.primary_session_local

    def create_session(self) -> Session:
        """
        Create a new database session.

        Returns:
            SQLAlchemy Session: New database session
        """
        if not self.primary_session_local:
            raise RuntimeError(
                "Test environment not set up. Call setup() first."
            )  # noqa: E501

        return cast(Session, self.primary_session_local())

    def create_additional_database(
        self, db_name: str
    ) -> Tuple[Engine, sessionmaker, Path]:  # noqa: E501
        """
        Create an additional isolated database for testing.

        Args:
            db_name: Name for the additional database

        Returns:
            Tuple of (engine, session_local_factory, db_path)
        """
        return self.db_manager.create_migrated_database(db_name)

    def create_in_memory_database(self) -> Tuple[Engine, sessionmaker]:
        """
        Create an in-memory database for fast testing.

        Returns:
            Tuple of (engine, session_local_factory)
        """
        return self.db_manager.create_in_memory_database()

    def get_temp_file_path(self, filename: str) -> Path:
        """
        Get path for a temporary file within the test environment.

        Args:
            filename: Name of the temporary file

        Returns:
            Path: Full path to the temporary file
        """
        return self.temp_dir / filename

    def cleanup(self) -> None:
        """Clean up all test environment resources."""
        # Clean up configuration
        if self.config_manager:
            self.config_manager.cleanup()

        # Clean up databases
        if self.db_manager:
            self.db_manager.cleanup_all()

        # Clean up temporary directory if we created it
        if self._cleanup_temp_dir and self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir)
            except (OSError, PermissionError):
                # Handle cases where files might be locked
                pass

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.cleanup()


@contextmanager
def isolated_test_environment(
    config_overrides: Optional[Dict[str, Any]] = None, temp_dir: Optional[str] = None
):  # noqa: E501
    """
    Context manager for creating a completely isolated test environment.

    This context manager provides complete isolation for tests by creating
    temporary configuration and database resources that are automatically
    cleaned up when the test completes.

    Args:
        config_overrides: Optional configuration overrides to apply
        temp_dir: Optional temporary directory path

    Yields:
        TestEnvironment: Configured test environment

    Example:
        with isolated_test_environment({"database.check_same_thread": False}) as env:  # noqa: E501
            settings, engine, session_local = env.setup()
            session = env.create_session()
            # Run tests with isolated environment
    """
    env = TestEnvironment(temp_dir, config_overrides)
    try:
        yield env
    finally:
        env.cleanup()


@contextmanager
def isolated_test_session(
    config_overrides: Optional[Dict[str, Any]] = None, temp_dir: Optional[str] = None
):  # noqa: E501
    """
    Context manager for creating an isolated test session with complete environment.  # noqa: E501

    This is a convenience context manager that sets up a complete test environment  # noqa: E501
    and provides a ready-to-use database session.

    Args:
        config_overrides: Optional configuration overrides to apply
        temp_dir: Optional temporary directory path

    Yields:
        Tuple of (session, settings, test_environment)

    Example:
        with isolated_test_session() as (session, settings, env):
            # Use session for database operations
            # Use settings for configuration access
            # Use env for additional test resources
    """
    with isolated_test_environment(config_overrides, temp_dir) as env:
        settings, engine, session_local = env.setup()
        session = env.create_session()
        try:
            yield session, settings, env
        finally:
            session.close()


class TestEnvironmentBuilder:
    """
    Builder pattern for creating customized test environments.

    Provides a fluent interface for configuring test environments
    with specific requirements.
    """

    def __init__(self):
        self.temp_dir: Optional[str] = None
        self.config_overrides: Dict[str, Any] = {}
        self.db_type: str = "migrated"  # "memory", "file", or "migrated"

    def with_temp_dir(self, temp_dir: str) -> "TestEnvironmentBuilder":
        """Set temporary directory for the test environment."""
        self.temp_dir = temp_dir
        return self

    def with_config(self, **overrides) -> "TestEnvironmentBuilder":
        """Add configuration overrides."""
        self.config_overrides.update(overrides)
        return self

    def with_config_dict(
        self, overrides: Dict[str, Any]
    ) -> "TestEnvironmentBuilder":  # noqa: E501
        """Add configuration overrides from a dictionary."""
        self.config_overrides.update(overrides)
        return self

    def with_memory_database(self) -> "TestEnvironmentBuilder":
        """Use in-memory database for faster tests."""
        self.db_type = "memory"
        return self

    def with_file_database(self) -> "TestEnvironmentBuilder":
        """Use file-based database for debugging."""
        self.db_type = "file"
        return self

    def with_migrated_database(self) -> "TestEnvironmentBuilder":
        """Use file-based database with migrations applied (default)."""
        self.db_type = "migrated"
        return self

    def build(self) -> TestEnvironment:
        """Build the configured test environment."""
        return TestEnvironment(self.temp_dir, self.config_overrides)

    @contextmanager
    def context(self):
        """Create a context manager for the configured test environment."""
        with isolated_test_environment(
            self.config_overrides, self.temp_dir
        ) as env:  # noqa: E501
            yield env


# Convenience functions for common test patterns
def fast_test_environment(config_overrides: Optional[Dict[str, Any]] = None):
    """
    Create a fast test environment with in-memory database.

    Args:
        config_overrides: Optional configuration overrides

    Returns:
        TestEnvironmentBuilder: Configured for fast testing
    """
    builder = TestEnvironmentBuilder().with_memory_database()
    if config_overrides:
        builder = builder.with_config_dict(config_overrides)
    return builder


def debug_test_environment(config_overrides: Optional[Dict[str, Any]] = None):
    """
    Create a test environment with file-based database for debugging.

    Args:
        config_overrides: Optional configuration overrides

    Returns:
        TestEnvironmentBuilder: Configured for debugging
    """
    builder = TestEnvironmentBuilder().with_migrated_database()
    if config_overrides:
        builder = builder.with_config_dict(config_overrides)
    return builder


def verify_no_test_artifacts():
    """
    Verify that no test artifacts remain in the current directory.

    This function can be called after tests to ensure complete cleanup.
    Raises AssertionError if test artifacts are found.
    """
    current_dir = Path.cwd()

    # Check for database files
    db_files = list(current_dir.glob("test_*.db*"))
    if db_files:
        raise AssertionError(
            f"Test database files found in root directory: {db_files}"
        )  # noqa: E501

    # Check for test configuration files
    config_files = list(current_dir.glob("*test*.json"))
    config_files.extend(current_dir.glob("test_config.*"))
    if config_files:
        raise AssertionError(
            f"Test configuration files found in root directory: {config_files}"
        )  # noqa: E501

    # Check for temporary directories
    temp_dirs = [
        d for d in current_dir.iterdir() if d.is_dir() and "test_env_" in d.name
    ]  # noqa: E501
    if temp_dirs:
        raise AssertionError(
            f"Test temporary directories found in root directory: {temp_dirs}"
        )  # noqa: E501


def cleanup_test_artifacts():
    """
    Clean up any remaining test artifacts in the current directory.

    This function provides a safety net for cleaning up test artifacts
    that might have been left behind by interrupted tests.
    """
    current_dir = Path.cwd()

    # Clean up database files
    for db_file in current_dir.glob("test_*.db*"):
        try:
            db_file.unlink()
        except (OSError, PermissionError):
            pass

    # Clean up configuration files
    for config_file in current_dir.glob("*test*.json"):
        try:
            config_file.unlink()
        except (OSError, PermissionError):
            pass

    for config_file in current_dir.glob("test_config.*"):
        try:
            config_file.unlink()
        except (OSError, PermissionError):
            pass

    # Clean up temporary directories
    for temp_dir in current_dir.iterdir():
        if temp_dir.is_dir() and "test_env_" in temp_dir.name:
            try:
                shutil.rmtree(temp_dir)
            except (OSError, PermissionError):
                pass
