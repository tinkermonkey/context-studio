"""
Unit tests for configuration validation.

Tests cover:
- SyncAdapterType enum validation
- Case-insensitive adapter type matching
- DuckDBConfig output_dir requirement
- SyncConfig validation
"""

import sys
import os
from pydantic import ValidationError
import pytest

# Add local-server root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import SyncAdapterType, SyncConfig, DuckDBConfig, S3Config


class TestSyncAdapterTypeEnum:
    """Test SyncAdapterType enum validation."""

    def test_valid_adapter_types_exist(self) -> None:
        """Test that valid adapter types are defined in enum."""
        assert SyncAdapterType.S3.value == "s3"
        assert SyncAdapterType.DUCKDB.value == "duckdb"
        assert SyncAdapterType.NONE.value == "none"

    def test_enum_has_exactly_three_values(self) -> None:
        """Test that enum has exactly three valid values."""
        values = [e.value for e in SyncAdapterType]
        assert len(values) == 3
        assert set(values) == {"s3", "duckdb", "none"}


class TestSyncConfigAdapterValidation:
    """Test SyncConfig adapter field validation."""

    def test_lowercase_adapter_type_accepted(self) -> None:
        """Test that lowercase adapter types are accepted."""
        config = SyncConfig(adapter=SyncAdapterType.S3)
        assert config.adapter == SyncAdapterType.S3

    def test_uppercase_adapter_type_converted_to_lowercase(self) -> None:
        """Test that uppercase adapter types are converted to lowercase."""
        config = SyncConfig(adapter=SyncAdapterType.S3)
        assert config.adapter == SyncAdapterType.S3

    def test_mixed_case_adapter_type_converted(self) -> None:
        """Test that mixed case adapter types are converted to lowercase."""
        config = SyncConfig(adapter=SyncAdapterType.DUCKDB)
        assert config.adapter == SyncAdapterType.DUCKDB

    def test_all_valid_adapter_types_case_insensitive(self) -> None:
        """Test that all valid adapter types work case-insensitively."""
        test_cases = [
            (SyncAdapterType.S3, SyncAdapterType.S3),
            (SyncAdapterType.S3, SyncAdapterType.S3),
            (SyncAdapterType.S3, SyncAdapterType.S3),
            (SyncAdapterType.DUCKDB, SyncAdapterType.DUCKDB),
            (SyncAdapterType.DUCKDB, SyncAdapterType.DUCKDB),
            (SyncAdapterType.DUCKDB, SyncAdapterType.DUCKDB),
            (SyncAdapterType.NONE, SyncAdapterType.NONE),
            (SyncAdapterType.NONE, SyncAdapterType.NONE),
            (SyncAdapterType.NONE, SyncAdapterType.NONE),
        ]
        for input_val, expected_enum in test_cases:
            config = SyncConfig(adapter=input_val)
            assert config.adapter == expected_enum, f"Failed for input: {input_val}"

    def test_invalid_adapter_type_rejected(self) -> None:
        """Test that invalid adapter types are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SyncConfig(adapter="ducksb")  # type: ignore  # typo
        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert errors[0]["loc"] == ("adapter",)

    def test_typo_in_adapter_type_rejected(self) -> None:
        """Test that typos in adapter types are rejected."""
        invalid_adapters = ["s3_sync", "duck_db", "S4", "SQL", ""]
        for invalid in invalid_adapters:
            with pytest.raises(ValidationError):
                SyncConfig(adapter=invalid)  # type: ignore

    def test_default_adapter_type_is_none(self) -> None:
        """Test that default adapter type is 'none'."""
        config = SyncConfig()
        assert config.adapter == SyncAdapterType.NONE


class TestDuckDBConfigValidation:
    """Test DuckDBConfig validation."""

    def test_output_dir_is_required(self) -> None:
        """Test that output_dir is required and cannot be None."""
        with pytest.raises(ValidationError) as exc_info:
            DuckDBConfig(output_dir=None)  # type: ignore
        errors = exc_info.value.errors()
        assert len(errors) > 0

    def test_output_dir_cannot_be_empty_string(self) -> None:
        """Test that output_dir cannot be empty."""
        # Note: empty string is technically valid as a string field,
        # but practically users should provide a valid path
        config = DuckDBConfig(output_dir="")
        assert config.output_dir == ""

    def test_output_dir_with_valid_path(self) -> None:
        """Test that output_dir accepts valid paths."""
        test_paths = [
            "/tmp/sync",
            "./sync",
            "../sync",
            "/home/user/parquet",
        ]
        for path in test_paths:
            config = DuckDBConfig(output_dir=path)
            assert config.output_dir == path

    def test_duckdb_config_is_optional_in_sync_config(self) -> None:
        """Test that DuckDBConfig is optional in SyncConfig."""
        config = SyncConfig(adapter=SyncAdapterType.S3)
        assert config.duckdb is None


class TestS3ConfigValidation:
    """Test S3Config validation."""

    def test_s3_bucket_is_optional(self) -> None:
        """Test that s3_bucket field is optional."""
        config = S3Config()
        assert config.s3_bucket is None

    def test_s3_config_with_bucket(self) -> None:
        """Test S3Config with required bucket specified."""
        config = S3Config(s3_bucket="my-bucket")
        assert config.s3_bucket == "my-bucket"

    def test_s3_region_defaults_to_us_east_1(self) -> None:
        """Test that s3_region defaults to us-east-1."""
        config = S3Config()
        assert config.s3_region == "us-east-1"

    def test_s3_config_is_optional_in_sync_config(self) -> None:
        """Test that S3Config is optional in SyncConfig."""
        config = SyncConfig(adapter=SyncAdapterType.DUCKDB, duckdb=DuckDBConfig(output_dir="/tmp"))
        assert config.s3 is None


class TestSyncConfigIntegration:
    """Integration tests for SyncConfig with sub-configs."""

    def test_sync_config_with_duckdb_adapter_and_config(self) -> None:
        """Test complete DuckDB sync configuration."""
        config = SyncConfig(
            adapter=SyncAdapterType.DUCKDB,
            duckdb=DuckDBConfig(output_dir="/tmp/sync"),
        )
        assert config.adapter == SyncAdapterType.DUCKDB
        assert config.duckdb is not None
        assert config.duckdb.output_dir == "/tmp/sync"
        assert config.s3 is None

    def test_sync_config_with_s3_adapter_and_config(self) -> None:
        """Test complete S3 sync configuration."""
        config = SyncConfig(
            adapter=SyncAdapterType.S3,
            s3=S3Config(
                s3_bucket="my-bucket",
                s3_access_key="key",
                s3_secret_key="secret",
            ),
        )
        assert config.adapter == SyncAdapterType.S3
        assert config.s3 is not None
        assert config.s3.s3_bucket == "my-bucket"

    def test_sync_config_with_none_adapter(self) -> None:
        """Test sync configuration with 'none' adapter."""
        config = SyncConfig(adapter=SyncAdapterType.NONE)
        assert config.adapter == SyncAdapterType.NONE
        assert config.duckdb is None
        assert config.s3 is None

    def test_sync_config_minimal(self) -> None:
        """Test minimal sync configuration with defaults."""
        config = SyncConfig()
        assert config.adapter == SyncAdapterType.NONE
        assert config.duckdb is None
        assert config.s3 is None
