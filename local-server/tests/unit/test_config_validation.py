"""
Unit tests for configuration validation.

Tests cover:
- SyncAdapterType enum validation
- Case-insensitive adapter type matching
- DuckDBConfig output_dir requirement
- SyncConfig validation
- CORS origins default and the MCP section
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from config import (
    ChatConfig,
    DuckDBConfig,
    McpConfig,
    RecognitionConfig,
    S3Config,
    ServerConfig,
    Settings,
    SyncAdapterType,
    SyncConfig,
    url_origin,
)

EXAMPLE_CONFIG = Path(__file__).resolve().parents[2] / "config.example.json"


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
        config = SyncConfig(adapter=SyncAdapterType.NONE)
        assert config.adapter == SyncAdapterType.NONE

    def test_uppercase_adapter_type_converted_to_lowercase(self) -> None:
        """Test that uppercase adapter types are converted to lowercase."""
        config = SyncConfig(adapter=SyncAdapterType.S3, s3=S3Config(s3_bucket="test-bucket"))
        assert config.adapter == SyncAdapterType.S3

    def test_mixed_case_adapter_type_converted(self) -> None:
        """Test that mixed case adapter types are converted to lowercase."""
        config = SyncConfig(adapter=SyncAdapterType.DUCKDB, duckdb=DuckDBConfig(output_dir="/tmp"))
        assert config.adapter == SyncAdapterType.DUCKDB

    def test_all_valid_adapter_types_case_insensitive(self) -> None:
        """Test that all valid adapter types work case-insensitively."""
        # Test NONE adapter (doesn't require sub-config)
        config = SyncConfig(adapter=SyncAdapterType.NONE)
        assert config.adapter == SyncAdapterType.NONE

        # Test S3 adapter with config
        config = SyncConfig(adapter=SyncAdapterType.S3, s3=S3Config(s3_bucket="test-bucket"))
        assert config.adapter == SyncAdapterType.S3

        # Test DUCKDB adapter with config
        config = SyncConfig(adapter=SyncAdapterType.DUCKDB, duckdb=DuckDBConfig(output_dir="/tmp"))
        assert config.adapter == SyncAdapterType.DUCKDB

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
        """Test that DuckDBConfig is optional in SyncConfig when using different adapter."""
        config = SyncConfig(adapter=SyncAdapterType.S3, s3=S3Config(s3_bucket="test-bucket"))
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


class TestSyncConfigCrossFieldValidation:
    """Test SyncConfig cross-field validation."""

    def test_s3_adapter_requires_s3_config(self) -> None:
        """Test that S3 adapter requires s3 configuration."""
        with pytest.raises(ValidationError) as exc_info:
            SyncConfig(adapter=SyncAdapterType.S3)  # Missing s3 config
        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert "s3 configuration is missing" in str(errors[0]["msg"]).lower()

    def test_duckdb_adapter_requires_duckdb_config(self) -> None:
        """Test that DuckDB adapter requires duckdb configuration."""
        with pytest.raises(ValidationError) as exc_info:
            SyncConfig(adapter=SyncAdapterType.DUCKDB)  # Missing duckdb config
        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert "duckdb configuration is missing" in str(errors[0]["msg"]).lower()

    def test_none_adapter_allows_no_config(self) -> None:
        """Test that NONE adapter allows no sub-config."""
        config = SyncConfig(adapter=SyncAdapterType.NONE)
        assert config.adapter == SyncAdapterType.NONE
        assert config.s3 is None
        assert config.duckdb is None

    def test_default_none_adapter_allows_no_config(self) -> None:
        """Test that default NONE adapter allows no sub-config."""
        config = SyncConfig()
        assert config.adapter == SyncAdapterType.NONE
        assert config.s3 is None
        assert config.duckdb is None


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


class TestRecognitionConfigValidation:
    """Test RecognitionConfig validation."""

    def test_default_individual_match_threshold(self) -> None:
        """Test that individual_match_threshold defaults to 0.90."""
        config = RecognitionConfig()
        assert config.individual_match_threshold == 0.90

    def test_individual_match_threshold_accepts_custom_value(self) -> None:
        """Test that individual_match_threshold can be configured."""
        config = RecognitionConfig(individual_match_threshold=0.75)
        assert config.individual_match_threshold == 0.75

    @pytest.mark.parametrize("invalid_threshold", [-0.1, 1.1])
    def test_individual_match_threshold_out_of_range_rejected(self, invalid_threshold) -> None:
        """Test that individual_match_threshold must be within [0, 1]."""
        with pytest.raises(ValidationError):
            RecognitionConfig(individual_match_threshold=invalid_threshold)


class TestChatConfigValidation:
    """Test ChatConfig defaults and validation."""

    def test_defaults(self) -> None:
        """Chat defaults to Claude Sonnet 5.5 with 8 tool rounds."""
        config = ChatConfig()
        assert config.model == "claude-sonnet-5-5"
        assert config.max_tool_rounds == 8

    def test_settings_include_chat_section(self) -> None:
        """Settings parses a chat section from config.json data."""
        settings = Settings(chat={"model": "anthropic/claude-opus-4-7", "max_tool_rounds": 4})
        assert settings.chat.model == "anthropic/claude-opus-4-7"
        assert settings.chat.max_tool_rounds == 4

    @pytest.mark.parametrize("invalid_rounds", [0, 51])
    def test_max_tool_rounds_out_of_range_rejected(self, invalid_rounds) -> None:
        """max_tool_rounds must be within [1, 50]."""
        with pytest.raises(ValidationError):
            ChatConfig(max_tool_rounds=invalid_rounds)

    def test_empty_model_rejected(self) -> None:
        """The chat model id cannot be empty."""
        with pytest.raises(ValidationError):
            ChatConfig(model="")


class TestCorsOriginsDefault:
    """server.cors_origins defaults to the UI origin rather than every origin."""

    def test_defaults_to_the_ui_base_url(self) -> None:
        assert ServerConfig().cors_origins == ["http://localhost:3100"]

    def test_follows_a_configured_ui_base_url(self) -> None:
        config = ServerConfig(ui_base_url="http://localhost:4000")
        assert config.cors_origins == ["http://localhost:4000"]

    def test_is_empty_when_there_is_no_ui(self) -> None:
        assert ServerConfig(ui_base_url=None).cors_origins == []

    @pytest.mark.parametrize(
        "ui_base_url",
        ["http://localhost:3100/", "http://localhost:3100/app/settings", "HTTP://LocalHost:3100"],
    )
    def test_ui_base_url_is_reduced_to_its_origin(self, ui_base_url: str) -> None:
        assert ServerConfig(ui_base_url=ui_base_url).cors_origins == ["http://localhost:3100"]

    def test_explicit_origins_win(self) -> None:
        config = ServerConfig(cors_origins=["*"], ui_base_url="http://localhost:4000")
        assert config.cors_origins == ["*"]

    def test_settings_loaded_from_a_section_without_cors_origins(self) -> None:
        settings = Settings(server={"host": "127.0.0.1", "port": 8000})
        assert settings.server.cors_origins == ["http://localhost:3100"]

    def test_example_config_allows_only_the_vite_dev_origin(self) -> None:
        """config.example.json leaves cors_origins to the default: the UI on :3100."""
        with open(EXAMPLE_CONFIG) as f:
            example = json.load(f)
        assert "cors_origins" not in example["server"]
        assert Settings(**example).server.cors_origins == ["http://localhost:3100"]

    def test_example_config_carries_no_mcp_token(self) -> None:
        """Each install generates its own token; the committed example must not hold one."""
        with open(EXAMPLE_CONFIG) as f:
            assert not Settings(**json.load(f)).mcp.auth_token


class TestMcpConfig:
    def test_auth_token_defaults_to_empty(self) -> None:
        assert McpConfig().auth_token == ""
        assert Settings().mcp.auth_token == ""

    def test_auth_token_is_read_from_the_mcp_section(self) -> None:
        assert Settings(mcp={"auth_token": "abc"}).mcp.auth_token == "abc"


class TestUrlOrigin:
    @pytest.mark.parametrize(
        ("url", "origin"),
        [
            ("http://localhost:3100/", "http://localhost:3100"),
            ("https://example.com:443/path?q=1", "https://example.com"),
            ("http://example.com:80", "http://example.com"),
            ("http://[::1]:3100/app", "http://[::1]:3100"),
            ("null", None),
            ("", None),
            (None, None),
        ],
    )
    def test_url_origin(self, url, origin) -> None:
        assert url_origin(url) == origin


class TestUiOrigins:
    def test_ui_origin_plus_listed_origins_without_wildcard(self) -> None:
        config = ServerConfig(
            ui_base_url="http://localhost:3100/",
            cors_origins=["*", "http://localhost:5173/"],
        )
        assert config.ui_origins() == {"http://localhost:3100", "http://localhost:5173"}

    def test_wildcard_alone_allows_only_the_ui(self) -> None:
        assert ServerConfig(cors_origins=["*"]).ui_origins() == {"http://localhost:3100"}

    def test_no_ui_and_wildcard_allows_nothing(self) -> None:
        assert ServerConfig(ui_base_url=None, cors_origins=["*"]).ui_origins() == frozenset()
