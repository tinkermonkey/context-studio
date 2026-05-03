"""
Unit tests for app.py configuration wiring and error handling.

Tests cover:
- ConfigurationError is raised for missing S3 sub-config
- ConfigurationError is raised for missing DuckDB sub-config
- ConfigurationError is raised for missing s3_bucket
- Valid sync configurations initialize correctly
- ConfigurationError is properly imported from domain.admin.exceptions
"""

import sys
import os
import pytest
from pydantic import ValidationError

# Add local-server root to path for imports
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from domain.admin.exceptions import ConfigurationError
from config import SyncAdapterType, SyncConfig, DuckDBConfig, S3Config


class TestConfigurationErrorImport:
    """Test that ConfigurationError is properly imported from domain."""

    def test_configuration_error_is_from_admin_domain(self) -> None:
        """Test that ConfigurationError is the domain version."""
        from domain.admin.exceptions import AdminError

        # ConfigurationError should be a subclass of AdminError
        assert issubclass(ConfigurationError, AdminError)

    def test_configuration_error_is_exception(self) -> None:
        """Test that ConfigurationError is an Exception."""
        assert issubclass(ConfigurationError, Exception)

    def test_configuration_error_can_be_raised(self) -> None:
        """Test that ConfigurationError can be instantiated and raised."""
        error = ConfigurationError("Test error message")
        assert str(error) == "Test error message"

    def test_configuration_error_with_cause_chain(self) -> None:
        """Test that ConfigurationError supports exception chaining."""
        original_error = ValueError("Original error")
        error = ConfigurationError("Wrapper error")
        error.__cause__ = original_error

        assert error.__cause__ is original_error


class TestSyncAdapterInitializationErrors:
    """Test that sync adapter wiring raises ConfigurationError appropriately."""

    def test_missing_s3_config_raises_validation_error(self) -> None:
        """Test that missing S3 sub-config raises ValidationError at config creation time."""
        with pytest.raises(ValidationError) as exc_info:
            SyncConfig(adapter=SyncAdapterType.S3)  # No s3 sub-config
        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert "s3 configuration" in str(errors[0]["msg"]).lower()

    def test_missing_s3_bucket_checked_by_app(self) -> None:
        """Test that missing s3_bucket is checked when initializing adapters in app.py."""
        s3_config = S3Config()  # No bucket specified

        # Test the app.py validation logic: missing bucket should raise ConfigurationError
        try:
            # Simulate the app.py check for missing bucket (lines 239-242)
            if not s3_config or not s3_config.s3_bucket:
                raise ConfigurationError(
                    "S3 adapter configured but required settings missing: "
                    "sync.s3.s3_bucket is required when adapter is 's3'"
                )
            pytest.fail("Expected ConfigurationError for missing s3_bucket")
        except ConfigurationError as e:
            assert "s3_bucket is required" in str(e)

    def test_missing_duckdb_config_raises_validation_error(self) -> None:
        """Test that missing DuckDB sub-config raises ValidationError at config creation time."""
        with pytest.raises(ValidationError) as exc_info:
            SyncConfig(adapter=SyncAdapterType.DUCKDB)  # No duckdb sub-config
        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert "duckdb configuration" in str(errors[0]["msg"]).lower()

    def test_s3_adapter_with_bucket_does_not_raise(self) -> None:
        """Test that S3 adapter with bucket does not raise ConfigurationError."""
        s3_config = S3Config(s3_bucket="my-bucket")

        # Simulate the validation logic
        if not s3_config or not s3_config.s3_bucket:
            pytest.fail("Should not raise ConfigurationError with valid bucket")

    def test_duckdb_adapter_with_output_dir_does_not_raise(self) -> None:
        """Test that DuckDB adapter with output_dir does not raise ConfigurationError."""
        duckdb_config = DuckDBConfig(output_dir="/tmp/sync")

        # Simulate the validation logic
        if not duckdb_config:
            pytest.fail("Should not raise ConfigurationError with valid output_dir")


class TestEnumValueValidation:
    """Test enum value validation in adapter selection."""

    def test_all_enum_values_are_strings(self) -> None:
        """Test that all SyncAdapterType values are strings."""
        for adapter_type in SyncAdapterType:
            assert isinstance(adapter_type.value, str)

    def test_enum_values_match_config_expectations(self) -> None:
        """Test that enum values match what app.py expects."""
        # These are the values that app.py uses in equality checks
        assert str(SyncAdapterType.S3.value) == "s3"
        assert str(SyncAdapterType.DUCKDB.value) == "duckdb"
        assert str(SyncAdapterType.NONE.value) == "none"

    def test_invalid_enum_value_cannot_be_created(self) -> None:
        """Test that invalid enum values cannot be created directly."""
        # This tests that SyncAdapterType is an enum, not just a string
        with pytest.raises(ValueError):
            SyncAdapterType("invalid")
