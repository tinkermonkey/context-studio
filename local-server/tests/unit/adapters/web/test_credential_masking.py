"""
Unit tests for the _mask_credential_sections function.

Tests the credential masking logic directly, including:
- Credential field masking with last 4 characters
- Short key edge cases (< 4 characters)
- None and empty string handling
- Non-dict section handling (replaced with None)
- Deep copy behavior (original not modified)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from adapters.web.schemas.admin import _mask_credential_sections


class TestMaskCredentialSectionsFunction:
    """Test the _mask_credential_sections function directly."""

    def test_masks_openai_api_key(self):
        """Test that openai_api_key is masked with last 4 characters."""
        sections = {
            "llm": {
                "openai_api_key": "sk-1234567890abcdef1234"
            }
        }

        result = _mask_credential_sections(sections)

        assert result["llm"]["openai_api_key"] == "***1234"

    def test_masks_anthropic_api_key(self):
        """Test that anthropic_api_key is masked with last 4 characters."""
        sections = {
            "llm": {
                "anthropic_api_key": "sk-ant-v0-abc1234567890"
            }
        }

        result = _mask_credential_sections(sections)

        assert result["llm"]["anthropic_api_key"] == "***7890"

    def test_masks_s3_access_key(self):
        """Test that s3_access_key is masked with last 4 characters."""
        sections = {
            "storage": {
                "s3_access_key": "AKIAIOSFODNN7EXAMPLE"
            }
        }

        result = _mask_credential_sections(sections)

        assert result["storage"]["s3_access_key"] == "***MPLE"

    def test_masks_s3_secret_key(self):
        """Test that s3_secret_key is masked with last 4 characters."""
        sections = {
            "storage": {
                "s3_secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
            }
        }

        result = _mask_credential_sections(sections)

        assert result["storage"]["s3_secret_key"] == "***EKEY"

    def test_short_key_masked_as_three_asterisks(self):
        """Test that keys shorter than 4 characters are masked as ***."""
        sections = {
            "llm": {
                "openai_api_key": "abc"
            }
        }

        result = _mask_credential_sections(sections)

        assert result["llm"]["openai_api_key"] == "***"

    def test_single_character_key_masked_as_three_asterisks(self):
        """Test that single character key is masked as ***."""
        sections = {
            "llm": {
                "openai_api_key": "x"
            }
        }

        result = _mask_credential_sections(sections)

        assert result["llm"]["openai_api_key"] == "***"

    def test_exactly_four_character_key_shows_all_four(self):
        """Test that 4-character key shows all 4 characters."""
        sections = {
            "llm": {
                "openai_api_key": "abcd"
            }
        }

        result = _mask_credential_sections(sections)

        assert result["llm"]["openai_api_key"] == "***abcd"

    def test_empty_string_key_not_masked(self):
        """Test that empty string API keys are not masked."""
        sections = {
            "llm": {
                "openai_api_key": ""
            }
        }

        result = _mask_credential_sections(sections)

        assert result["llm"]["openai_api_key"] == ""

    def test_none_credential_field_not_masked(self):
        """Test that None credential field values are not masked."""
        sections = {
            "llm": {
                "openai_api_key": None
            }
        }

        result = _mask_credential_sections(sections)

        assert result["llm"]["openai_api_key"] is None

    def test_none_section_remains_none(self):
        """Test that None section values remain as None."""
        sections = {
            "llm": {
                "openai_api_key": "sk-test1234567890"
            },
            "sync": None
        }

        result = _mask_credential_sections(sections)

        assert result["sync"] is None

    def test_non_dict_section_replaced_with_none(self):
        """Test that non-dict sections are replaced with None."""
        sections = {
            "llm": {
                "openai_api_key": "sk-test1234567890"
            },
            "list_section": ["item1", "item2"]
        }

        result = _mask_credential_sections(sections)

        assert result["llm"]["openai_api_key"] == "***7890"
        assert result["list_section"] is None

    def test_string_section_replaced_with_none(self):
        """Test that string sections are replaced with None."""
        sections = {
            "llm": {
                "openai_api_key": "sk-test1234567890"
            },
            "corrupted": "some-string-value"
        }

        result = _mask_credential_sections(sections)

        assert result["corrupted"] is None

    def test_integer_section_replaced_with_none(self):
        """Test that integer sections are replaced with None."""
        sections = {
            "llm": {
                "openai_api_key": "sk-test1234567890"
            },
            "bad_section": 12345
        }

        result = _mask_credential_sections(sections)

        assert result["bad_section"] is None

    def test_deep_copy_preserves_original(self):
        """Test that original sections dict is not modified (deep copy)."""
        original_key = "sk-test1234567890"
        sections = {
            "llm": {
                "openai_api_key": original_key
            }
        }

        _mask_credential_sections(sections)

        # Original should be unchanged
        assert sections["llm"]["openai_api_key"] == original_key

    def test_deep_copy_nested_structures(self):
        """Test that deep copy works with nested structures."""
        original_key = "sk-test1234567890"
        sections = {
            "llm": {
                "openai_api_key": original_key,
                "model": "gpt-4",
                "settings": {
                    "temperature": 0.7
                }
            }
        }

        result = _mask_credential_sections(sections)

        # Original should be unchanged
        assert sections["llm"]["openai_api_key"] == original_key
        # Result should have masked key
        assert result["llm"]["openai_api_key"] == "***7890"
        # Nested structure should be independent
        result["llm"]["settings"]["temperature"] = 0.5
        assert sections["llm"]["settings"]["temperature"] == 0.7

    def test_non_credential_fields_not_masked(self):
        """Test that non-credential fields are not masked."""
        sections = {
            "llm": {
                "provider": "openai",
                "model": "gpt-4",
                "openai_api_key": "sk-test1234567890"
            }
        }

        result = _mask_credential_sections(sections)

        assert result["llm"]["provider"] == "openai"
        assert result["llm"]["model"] == "gpt-4"
        assert result["llm"]["openai_api_key"] == "***7890"

    def test_multiple_credentials_masked(self):
        """Test masking multiple credential fields."""
        sections = {
            "llm": {
                "openai_api_key": "sk-openai1234567890",
                "anthropic_api_key": "sk-ant-anthropic1234567890"
            }
        }

        result = _mask_credential_sections(sections)

        assert result["llm"]["openai_api_key"] == "***7890"
        assert result["llm"]["anthropic_api_key"] == "***7890"

    def test_credentials_across_multiple_sections(self):
        """Test masking credentials in multiple sections."""
        sections = {
            "llm": {
                "openai_api_key": "sk-openai1234567890"
            },
            "storage": {
                "s3_access_key": "AKIAIOSFODNN7EXAMPLE",
                "s3_secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
            }
        }

        result = _mask_credential_sections(sections)

        assert result["llm"]["openai_api_key"] == "***7890"
        assert result["storage"]["s3_access_key"] == "***MPLE"
        assert result["storage"]["s3_secret_key"] == "***EKEY"

    def test_non_string_credential_converted_to_string(self):
        """Test that non-string credential values are converted before masking."""
        sections = {
            "llm": {
                "openai_api_key": 12345678901234
            }
        }

        result = _mask_credential_sections(sections)

        # 12345678901234 → "12345678901234", last 4 is "1234"
        assert result["llm"]["openai_api_key"] == "***1234"

    def test_empty_sections_dict(self):
        """Test handling of empty sections dict."""
        sections = {}

        result = _mask_credential_sections(sections)

        assert result == {}

    def test_section_with_only_non_credential_fields(self):
        """Test section with only non-credential fields."""
        sections = {
            "llm": {
                "provider": "openai",
                "model": "gpt-4"
            }
        }

        result = _mask_credential_sections(sections)

        assert result["llm"]["provider"] == "openai"
        assert result["llm"]["model"] == "gpt-4"

    def test_mixed_valid_and_invalid_sections(self):
        """Test handling of mix of valid dict sections and invalid sections."""
        sections = {
            "llm": {
                "openai_api_key": "sk-test1234567890",
                "model": "gpt-4"
            },
            "invalid_list": [1, 2, 3],
            "sync": None,
            "database": {
                "url": "sqlite:///local.db"
            }
        }

        result = _mask_credential_sections(sections)

        assert result["llm"]["openai_api_key"] == "***7890"
        assert result["llm"]["model"] == "gpt-4"
        assert result["invalid_list"] is None
        assert result["sync"] is None
        assert result["database"]["url"] == "sqlite:///local.db"
