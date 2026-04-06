"""
Unit tests for the _mask_credentials function.

Tests the credential masking logic directly, including:
- Credential field masking with last 4 characters
- Short key edge cases (< 4 characters)
- None and empty string handling
- Deep copy behavior (original not modified)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from adapters.web.schemas.admin import _mask_credentials


class TestMaskCredentialsFunction:
    """Test the _mask_credentials function directly."""

    def test_masks_openai_api_key(self):
        """Test that openai_api_key is masked with last 4 characters."""
        section = {
            "openai_api_key": "sk-1234567890abcdef1234"
        }

        result = _mask_credentials(section)

        assert result["openai_api_key"] == "***1234"

    def test_masks_anthropic_api_key(self):
        """Test that anthropic_api_key is masked with last 4 characters."""
        section = {
            "anthropic_api_key": "sk-ant-v0-abc1234567890"
        }

        result = _mask_credentials(section)

        assert result["anthropic_api_key"] == "***7890"

    def test_masks_s3_access_key(self):
        """Test that s3_access_key is masked with last 4 characters."""
        section = {
            "s3_access_key": "AKIAIOSFODNN7EXAMPLE"
        }

        result = _mask_credentials(section)

        assert result["s3_access_key"] == "***MPLE"

    def test_masks_s3_secret_key(self):
        """Test that s3_secret_key is masked with last 4 characters."""
        section = {
            "s3_secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        }

        result = _mask_credentials(section)

        assert result["s3_secret_key"] == "***EKEY"

    def test_short_key_masked_as_three_asterisks(self):
        """Test that keys shorter than 4 characters are masked as ***."""
        section = {
            "openai_api_key": "abc"
        }

        result = _mask_credentials(section)

        assert result["openai_api_key"] == "***"

    def test_single_character_key_masked_as_three_asterisks(self):
        """Test that single character key is masked as ***."""
        section = {
            "openai_api_key": "x"
        }

        result = _mask_credentials(section)

        assert result["openai_api_key"] == "***"

    def test_exactly_four_character_key_shows_all_four(self):
        """Test that 4-character key shows all 4 characters."""
        section = {
            "openai_api_key": "abcd"
        }

        result = _mask_credentials(section)

        assert result["openai_api_key"] == "***abcd"

    def test_empty_string_key_not_masked(self):
        """Test that empty string API keys are not masked."""
        section = {
            "openai_api_key": ""
        }

        result = _mask_credentials(section)

        assert result["openai_api_key"] == ""

    def test_none_credential_field_not_masked(self):
        """Test that None credential field values are not masked."""
        section = {
            "openai_api_key": None
        }

        result = _mask_credentials(section)

        assert result["openai_api_key"] is None

    def test_deep_copy_preserves_original(self):
        """Test that original section dict is not modified (deep copy)."""
        original_key = "sk-test1234567890"
        section = {
            "openai_api_key": original_key
        }

        _mask_credentials(section)

        # Original should be unchanged
        assert section["openai_api_key"] == original_key

    def test_deep_copy_nested_structures(self):
        """Test that deep copy works with nested structures."""
        original_key = "sk-test1234567890"
        section = {
            "openai_api_key": original_key,
            "model": "gpt-4",
            "settings": {
                "temperature": 0.7
            }
        }

        result = _mask_credentials(section)

        # Original should be unchanged
        assert section["openai_api_key"] == original_key
        # Result should have masked key
        assert result["openai_api_key"] == "***7890"
        # Nested structure should be independent
        result["settings"]["temperature"] = 0.5
        assert section["settings"]["temperature"] == 0.7

    def test_non_credential_fields_not_masked(self):
        """Test that non-credential fields are not masked."""
        section = {
            "provider": "openai",
            "model": "gpt-4",
            "openai_api_key": "sk-test1234567890"
        }

        result = _mask_credentials(section)

        assert result["provider"] == "openai"
        assert result["model"] == "gpt-4"
        assert result["openai_api_key"] == "***7890"

    def test_multiple_credentials_masked(self):
        """Test masking multiple credential fields."""
        section = {
            "openai_api_key": "sk-openai1234567890",
            "anthropic_api_key": "sk-ant-anthropic1234567890"
        }

        result = _mask_credentials(section)

        assert result["openai_api_key"] == "***7890"
        assert result["anthropic_api_key"] == "***7890"

    def test_non_string_credential_converted_to_string(self):
        """Test that non-string credential values are converted before masking."""
        section = {
            "openai_api_key": 12345678901234
        }

        result = _mask_credentials(section)

        # 12345678901234 → "12345678901234", last 4 is "1234"
        assert result["openai_api_key"] == "***1234"

    def test_empty_section_dict(self):
        """Test handling of empty section dict."""
        section = {}

        result = _mask_credentials(section)

        assert result == {}

    def test_section_with_only_non_credential_fields(self):
        """Test section with only non-credential fields."""
        section = {
            "provider": "openai",
            "model": "gpt-4"
        }

        result = _mask_credentials(section)

        assert result["provider"] == "openai"
        assert result["model"] == "gpt-4"
