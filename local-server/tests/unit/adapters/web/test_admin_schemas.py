"""
Unit tests for admin schemas, specifically API key masking.

Tests the AppConfigurationResponse.from_domain() method to verify
that API keys are properly masked in responses.
"""

import sys
import os

# Add local-server root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from adapters.web.schemas.admin import AppConfigurationResponse
from domain.admin.entities import AppConfiguration


class TestAppConfigurationResponseMasking:
    """Test API key masking in AppConfigurationResponse."""

    def test_openai_api_key_is_masked(self) -> None:
        """Test that OpenAI API key is masked with last 4 characters."""
        config = AppConfiguration(
            server={},
            database={},
            logging={},
            llm={
                "openai_api_key": "sk-abcdefghijklmnop1234"
            },
            nlp={},
            embedding={},
            reference_sources={},
        )

        response = AppConfigurationResponse.from_domain(config)

        assert response.llm["openai_api_key"] == "***1234"

    def test_anthropic_api_key_is_masked(self) -> None:
        """Test that Anthropic API key is masked with last 4 characters."""
        config = AppConfiguration(
            server={},
            database={},
            logging={},
            llm={
                "anthropic_api_key": "sk-ant-v0-abcdefghijklmnop1234"
            },
            nlp={},
            embedding={},
            reference_sources={},
        )

        response = AppConfigurationResponse.from_domain(config)

        assert response.llm["anthropic_api_key"] == "***1234"

    def test_s3_secret_key_is_masked(self) -> None:
        """Test that S3 secret key is masked with last 4 characters."""
        config = AppConfiguration(
            server={},
            database={},
            logging={},
            llm={},
            nlp={},
            embedding={},
            reference_sources={},
            sync={
                "s3_secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
            }
        )

        response = AppConfigurationResponse.from_domain(config)

        assert response.sync is not None
        assert response.sync["s3_secret_key"] == "***EKEY"

    def test_s3_access_key_is_masked(self) -> None:
        """Test that S3 access key is masked with last 4 characters."""
        config = AppConfiguration(
            server={},
            database={},
            logging={},
            llm={},
            nlp={},
            embedding={},
            reference_sources={},
            sync={
                "s3_access_key": "AKIAIOSFODNN7EXAMPLE"
            }
        )

        response = AppConfigurationResponse.from_domain(config)

        assert response.sync is not None
        assert response.sync["s3_access_key"] == "***MPLE"

    def test_short_api_key_is_masked_as_three_asterisks(self) -> None:
        """Test that API keys shorter than 4 characters are masked as ***."""
        config = AppConfiguration(
            server={},
            database={},
            logging={},
            llm={
                "openai_api_key": "abc"
            },
            nlp={},
            embedding={},
            reference_sources={},
        )

        response = AppConfigurationResponse.from_domain(config)

        assert response.llm["openai_api_key"] == "***"

    def test_empty_api_key_is_not_masked(self) -> None:
        """Test that empty API keys remain unchanged."""
        config = AppConfiguration(
            server={},
            database={},
            logging={},
            llm={
                "openai_api_key": ""
            },
            nlp={},
            embedding={},
            reference_sources={},
        )

        response = AppConfigurationResponse.from_domain(config)

        assert response.llm["openai_api_key"] == ""

    def test_none_api_key_is_not_masked(self) -> None:
        """Test that None API keys remain unchanged."""
        config = AppConfiguration(
            server={},
            database={},
            logging={},
            llm={
                "openai_api_key": None
            },
            nlp={},
            embedding={},
            reference_sources={},
        )

        response = AppConfigurationResponse.from_domain(config)

        assert response.llm["openai_api_key"] is None

    def test_multiple_api_keys_are_masked(self) -> None:
        """Test masking multiple API keys in same section."""
        config = AppConfiguration(
            server={},
            database={},
            logging={},
            llm={
                "openai_api_key": "sk-openai1234567890",
                "anthropic_api_key": "sk-ant-anthropic1234567890"
            },
            nlp={},
            embedding={},
            reference_sources={},
        )

        response = AppConfigurationResponse.from_domain(config)

        assert response.llm["openai_api_key"] == "***7890"
        assert response.llm["anthropic_api_key"] == "***7890"

    def test_s3_keys_in_sync_section_are_masked(self) -> None:
        """Test masking S3 keys in sync section."""
        config = AppConfiguration(
            server={},
            database={},
            logging={},
            llm={},
            nlp={},
            embedding={},
            reference_sources={},
            sync={
                "s3_access_key": "AKIAIOSFODNN7EXAMPLE",
                "s3_secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
            }
        )

        response = AppConfigurationResponse.from_domain(config)

        assert response.sync is not None
        assert response.sync["s3_access_key"] == "***MPLE"
        assert response.sync["s3_secret_key"] == "***EKEY"

    def test_non_key_fields_are_not_masked(self) -> None:
        """Test that non-sensitive fields are not masked."""
        config = AppConfiguration(
            server={},
            database={},
            logging={},
            llm={
                "provider": "openai",
                "model": "gpt-4",
                "openai_api_key": "sk-test1234567890"
            },
            nlp={},
            embedding={},
            reference_sources={},
        )

        response = AppConfigurationResponse.from_domain(config)

        assert response.llm["provider"] == "openai"
        assert response.llm["model"] == "gpt-4"
        assert response.llm["openai_api_key"] == "***7890"

    def test_original_config_is_not_modified(self) -> None:
        """Test that the original config object is not modified by masking."""
        original_key = "sk-test1234567890"
        config = AppConfiguration(
            server={},
            database={},
            logging={},
            llm={
                "openai_api_key": original_key
            },
            nlp={},
            embedding={},
            reference_sources={},
        )

        AppConfigurationResponse.from_domain(config)

        assert config.llm["openai_api_key"] == original_key

    def test_nested_sections_are_masked(self) -> None:
        """Test masking in multiple nested sections."""
        config = AppConfiguration(
            server={},
            database={},
            logging={},
            llm={
                "openai_api_key": "sk-openai1234567890"
            },
            nlp={},
            embedding={},
            reference_sources={},
            sync={
                "s3_access_key": "AKIAIOSFODNN7EXAMPLE",
                "s3_secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
            }
        )

        response = AppConfigurationResponse.from_domain(config)

        assert response.llm["openai_api_key"] == "***7890"
        assert response.sync is not None
        assert response.sync["s3_access_key"] == "***MPLE"
        assert response.sync["s3_secret_key"] == "***EKEY"

    def test_exactly_4_character_key_shows_last_4(self) -> None:
        """Test that a 4-character key shows all 4 characters."""
        config = AppConfiguration(
            server={},
            database={},
            logging={},
            llm={
                "openai_api_key": "abcd"
            },
            nlp={},
            embedding={},
            reference_sources={},
        )

        response = AppConfigurationResponse.from_domain(config)

        assert response.llm["openai_api_key"] == "***abcd"

    def test_non_string_api_key_is_converted_and_masked(self) -> None:
        """Test that non-string API keys are converted to string before masking."""
        config = AppConfiguration(
            server={},
            database={},
            logging={},
            llm={
                "openai_api_key": 12345678901234
            },
            nlp={},
            embedding={},
            reference_sources={},
        )

        response = AppConfigurationResponse.from_domain(config)

        # 12345678901234 converted to string "12345678901234", last 4 is "1234"
        assert response.llm["openai_api_key"] == "***1234"

    def test_none_sync_section_remains_none(self) -> None:
        """Test that None section values remain as None."""
        config = AppConfiguration(
            server={},
            database={},
            logging={},
            llm={
                "openai_api_key": "sk-test1234567890"
            },
            nlp={},
            embedding={},
            reference_sources={},
            sync=None
        )

        response = AppConfigurationResponse.from_domain(config)

        assert response.llm["openai_api_key"] == "***7890"
        assert response.sync is None
