"""
Unit tests for structure node attribute models with type validation.

Tests the StructureNodeAttribute and ResolvedAttribute Pydantic models,
including key format validation, value type validation, and inheritance markers.
"""
import sys
import os
from uuid import UUID, uuid4

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from pydantic import ValidationError  # noqa: E402
import pytest  # noqa: E402
from api.models.structure_nodes import (  # noqa: E402
    AttributeValueType,
    StructureNodeAttribute,
    ResolvedAttribute,
)


class TestAttributeValueType:
    """Test the AttributeValueType enum."""

    def test_enum_values(self):
        """Test that all five value types are defined."""
        assert AttributeValueType.STRING.value == "string"
        assert AttributeValueType.NUMBER.value == "number"
        assert AttributeValueType.BOOLEAN.value == "boolean"
        assert AttributeValueType.DATE.value == "date"
        assert AttributeValueType.URL.value == "url"

    def test_enum_members(self):
        """Test enum member count."""
        members = list(AttributeValueType)
        assert len(members) == 5


class TestStructureNodeAttribute:
    """Test StructureNodeAttribute Pydantic model."""

    def test_valid_string_attribute(self):
        """Test creating a valid string attribute."""
        attr = StructureNodeAttribute(
            key="display_name",
            title="Display Name",
            value_type=AttributeValueType.STRING,
            value="Example Value",
        )
        assert attr.key == "display_name"
        assert attr.title == "Display Name"
        assert attr.value_type == AttributeValueType.STRING
        assert attr.value == "Example Value"

    def test_valid_number_attribute_integer(self):
        """Test creating a valid number attribute with integer value."""
        attr = StructureNodeAttribute(
            key="confidence_score",
            title="Confidence Score",
            value_type=AttributeValueType.NUMBER,
            value=42,
        )
        assert attr.value == 42

    def test_valid_number_attribute_float(self):
        """Test creating a valid number attribute with float value."""
        attr = StructureNodeAttribute(
            key="accuracy_percentage",
            title="Accuracy Percentage",
            value_type=AttributeValueType.NUMBER,
            value=98.5,
        )
        assert attr.value == 98.5

    def test_valid_boolean_attribute_true(self):
        """Test creating a valid boolean attribute with True value."""
        attr = StructureNodeAttribute(
            key="is_active",
            title="Is Active",
            value_type=AttributeValueType.BOOLEAN,
            value=True,
        )
        assert attr.value is True

    def test_valid_boolean_attribute_false(self):
        """Test creating a valid boolean attribute with False value."""
        attr = StructureNodeAttribute(
            key="is_deprecated",
            title="Is Deprecated",
            value_type=AttributeValueType.BOOLEAN,
            value=False,
        )
        assert attr.value is False

    def test_valid_date_attribute_full_iso8601(self):
        """Test creating a valid date attribute with full ISO 8601 format."""
        attr = StructureNodeAttribute(
            key="publication_date",
            title="Publication Date",
            value_type=AttributeValueType.DATE,
            value="2024-01-15T10:30:00Z",
        )
        assert attr.value == "2024-01-15T10:30:00Z"

    def test_valid_date_attribute_basic_iso8601(self):
        """Test creating a valid date attribute with basic ISO 8601 format (YYYY-MM-DD)."""
        attr = StructureNodeAttribute(
            key="birth_date",
            title="Birth Date",
            value_type=AttributeValueType.DATE,
            value="1990-06-15",
        )
        assert attr.value == "1990-06-15"

    def test_valid_url_attribute_https(self):
        """Test creating a valid URL attribute with https."""
        attr = StructureNodeAttribute(
            key="homepage",
            title="Homepage",
            value_type=AttributeValueType.URL,
            value="https://example.com/path?query=value",
        )
        assert attr.value == "https://example.com/path?query=value"

    def test_valid_url_attribute_http(self):
        """Test creating a valid URL attribute with http."""
        attr = StructureNodeAttribute(
            key="legacy_url",
            title="Legacy URL",
            value_type=AttributeValueType.URL,
            value="http://example.com",
        )
        assert attr.value == "http://example.com"

    def test_key_pattern_valid_underscore_delimited(self):
        """Test that key accepts valid underscore_delimited format."""
        valid_keys = [
            "simple_key",
            "key_with_multiple_underscores",
            "a",
            "key0",
            "key0_with_numbers123",
        ]
        for key in valid_keys:
            attr = StructureNodeAttribute(
                key=key,
                title="Test",
                value_type=AttributeValueType.STRING,
                value="test",
            )
            assert attr.key == key

    def test_key_pattern_invalid_uppercase(self):
        """Test that key rejects uppercase letters."""
        with pytest.raises(ValidationError) as exc_info:
            StructureNodeAttribute(
                key="DisplayName",
                title="Test",
                value_type=AttributeValueType.STRING,
                value="test",
            )
        assert "pattern" in str(exc_info.value).lower()

    def test_key_pattern_invalid_starts_with_number(self):
        """Test that key rejects starting with a number."""
        with pytest.raises(ValidationError) as exc_info:
            StructureNodeAttribute(
                key="123key",
                title="Test",
                value_type=AttributeValueType.STRING,
                value="test",
            )
        assert "pattern" in str(exc_info.value).lower()

    def test_key_pattern_invalid_starts_with_underscore(self):
        """Test that key rejects starting with underscore."""
        with pytest.raises(ValidationError) as exc_info:
            StructureNodeAttribute(
                key="_private_key",
                title="Test",
                value_type=AttributeValueType.STRING,
                value="test",
            )
        assert "pattern" in str(exc_info.value).lower()

    def test_key_pattern_invalid_contains_hyphen(self):
        """Test that key rejects hyphens."""
        with pytest.raises(ValidationError) as exc_info:
            StructureNodeAttribute(
                key="key-with-hyphens",
                title="Test",
                value_type=AttributeValueType.STRING,
                value="test",
            )
        assert "pattern" in str(exc_info.value).lower()

    def test_key_pattern_invalid_contains_space(self):
        """Test that key rejects spaces."""
        with pytest.raises(ValidationError) as exc_info:
            StructureNodeAttribute(
                key="key with spaces",
                title="Test",
                value_type=AttributeValueType.STRING,
                value="test",
            )
        assert "pattern" in str(exc_info.value).lower()

    def test_title_required(self):
        """Test that title field is required."""
        with pytest.raises(ValidationError):
            StructureNodeAttribute(
                key="test_key",
                title="",  # Empty title should fail
                value_type=AttributeValueType.STRING,
                value="test",
            )

    def test_number_rejects_boolean(self):
        """Test that number type rejects boolean values."""
        with pytest.raises(ValidationError) as exc_info:
            StructureNodeAttribute(
                key="confidence_score",
                title="Confidence Score",
                value_type=AttributeValueType.NUMBER,
                value=True,
            )
        assert "numeric" in str(exc_info.value).lower()

    def test_number_rejects_string(self):
        """Test that number type rejects string values."""
        with pytest.raises(ValidationError) as exc_info:
            StructureNodeAttribute(
                key="confidence_score",
                title="Confidence Score",
                value_type=AttributeValueType.NUMBER,
                value="42",
            )
        assert "numeric" in str(exc_info.value).lower()

    def test_boolean_rejects_integer(self):
        """Test that boolean type rejects integer values."""
        with pytest.raises(ValidationError) as exc_info:
            StructureNodeAttribute(
                key="is_active",
                title="Is Active",
                value_type=AttributeValueType.BOOLEAN,
                value=1,
            )
        assert "boolean" in str(exc_info.value).lower()

    def test_boolean_rejects_string(self):
        """Test that boolean type rejects string values."""
        with pytest.raises(ValidationError) as exc_info:
            StructureNodeAttribute(
                key="is_active",
                title="Is Active",
                value_type=AttributeValueType.BOOLEAN,
                value="true",
            )
        assert "boolean" in str(exc_info.value).lower()

    def test_date_rejects_invalid_format(self):
        """Test that date type rejects invalid ISO 8601 format."""
        with pytest.raises(ValidationError) as exc_info:
            StructureNodeAttribute(
                key="publication_date",
                title="Publication Date",
                value_type=AttributeValueType.DATE,
                value="01/15/2024",  # US format, not ISO 8601
            )
        assert "ISO 8601" in str(exc_info.value)

    def test_date_accepts_semantically_invalid_but_formatted_month(self):
        """Test that date regex accepts any MM format even if semantically invalid (format-only validation)."""
        # The regex only validates format YYYY-MM-DD, not semantic validity
        attr = StructureNodeAttribute(
            key="publication_date",
            title="Publication Date",
            value_type=AttributeValueType.DATE,
            value="2024-13-01",  # Invalid month semantically, but valid format
        )
        assert attr.value == "2024-13-01"

    def test_date_accepts_semantically_invalid_but_formatted_day(self):
        """Test that date regex accepts any DD format even if semantically invalid (format-only validation)."""
        # The regex only validates format YYYY-MM-DD, not semantic validity
        attr = StructureNodeAttribute(
            key="publication_date",
            title="Publication Date",
            value_type=AttributeValueType.DATE,
            value="2024-02-30",  # Invalid day semantically, but valid format
        )
        assert attr.value == "2024-02-30"

    def test_url_rejects_missing_protocol(self):
        """Test that URL type rejects URLs without protocol."""
        with pytest.raises(ValidationError) as exc_info:
            StructureNodeAttribute(
                key="homepage",
                title="Homepage",
                value_type=AttributeValueType.URL,
                value="example.com",
            )
        assert "http" in str(exc_info.value).lower()

    def test_url_rejects_ftp_protocol(self):
        """Test that URL type only accepts http/https."""
        with pytest.raises(ValidationError) as exc_info:
            StructureNodeAttribute(
                key="ftp_url",
                title="FTP URL",
                value_type=AttributeValueType.URL,
                value="ftp://example.com/file.txt",
            )
        assert "http" in str(exc_info.value).lower()

    def test_value_optional_none(self):
        """Test that value field is optional and can be None."""
        attr = StructureNodeAttribute(
            key="optional_attribute",
            title="Optional Attribute",
            value_type=AttributeValueType.STRING,
            value=None,
        )
        assert attr.value is None

    def test_value_optional_default(self):
        """Test that value defaults to None when not provided."""
        attr = StructureNodeAttribute(
            key="optional_attribute",
            title="Optional Attribute",
            value_type=AttributeValueType.STRING,
        )
        assert attr.value is None

    def test_string_coercion(self):
        """Test that string type coerces values to string."""
        attr = StructureNodeAttribute(
            key="string_field",
            title="String Field",
            value_type=AttributeValueType.STRING,
            value=123,
        )
        assert attr.value == "123"
        assert isinstance(attr.value, str)

    def test_date_string_coercion(self):
        """Test that date values are stored as strings."""
        attr = StructureNodeAttribute(
            key="date_field",
            title="Date Field",
            value_type=AttributeValueType.DATE,
            value="2024-01-15",
        )
        assert isinstance(attr.value, str)

    def test_url_string_coercion(self):
        """Test that URL values are stored as strings."""
        attr = StructureNodeAttribute(
            key="url_field",
            title="URL Field",
            value_type=AttributeValueType.URL,
            value="https://example.com",
        )
        assert isinstance(attr.value, str)


class TestResolvedAttribute:
    """Test ResolvedAttribute model for inheritance information."""

    def test_basic_resolved_attribute(self):
        """Test creating a resolved attribute."""
        node_id = uuid4()
        attr = ResolvedAttribute(
            key="inherited_attribute",
            title="Inherited Attribute",
            value_type=AttributeValueType.STRING,
            value="inherited_value",
            inherited=True,
            source_node_id=node_id,
        )
        assert attr.inherited is True
        assert attr.source_node_id == node_id

    def test_resolved_attribute_inherited_default_false(self):
        """Test that inherited defaults to False."""
        attr = ResolvedAttribute(
            key="local_attribute",
            title="Local Attribute",
            value_type=AttributeValueType.STRING,
            value="local_value",
        )
        assert attr.inherited is False

    def test_resolved_attribute_source_node_id_optional(self):
        """Test that source_node_id is optional."""
        attr = ResolvedAttribute(
            key="attribute",
            title="Attribute",
            value_type=AttributeValueType.STRING,
            value="value",
            inherited=False,
        )
        assert attr.source_node_id is None

    def test_resolved_attribute_with_uuid_string(self):
        """Test that UUID can be provided as string."""
        node_id_str = str(uuid4())
        attr = ResolvedAttribute(
            key="attribute",
            title="Attribute",
            value_type=AttributeValueType.STRING,
            value="value",
            source_node_id=node_id_str,
        )
        # Pydantic should parse the string as UUID
        assert isinstance(attr.source_node_id, UUID)

    def test_resolved_attribute_inherits_validation(self):
        """Test that ResolvedAttribute inherits validation from StructureNodeAttribute."""
        # Invalid key should fail
        with pytest.raises(ValidationError):
            ResolvedAttribute(
                key="InvalidKey",  # uppercase
                title="Title",
                value_type=AttributeValueType.STRING,
                value="value",
            )

    def test_inherited_true_requires_source_node_id(self):
        """Test that inherited=True requires source_node_id to be set."""
        with pytest.raises(ValidationError) as exc_info:
            ResolvedAttribute(
                key="inherited_attr",
                title="Inherited Attribute",
                value_type=AttributeValueType.STRING,
                value="value",
                inherited=True,
                source_node_id=None,  # Invalid: inherited=True but source_node_id=None
            )
        assert "source_node_id" in str(exc_info.value).lower()

    def test_inherited_false_source_node_id_optional(self):
        """Test that when inherited=False, source_node_id is optional."""
        # Should not raise validation error
        attr = ResolvedAttribute(
            key="local_attr",
            title="Local Attribute",
            value_type=AttributeValueType.STRING,
            value="value",
            inherited=False,
            source_node_id=None,
        )
        assert attr.inherited is False
        assert attr.source_node_id is None

    def test_inherited_false_with_source_node_id(self):
        """Test that inherited=False can have source_node_id (allowed but semantically unusual)."""
        node_id = uuid4()
        attr = ResolvedAttribute(
            key="local_attr",
            title="Local Attribute",
            value_type=AttributeValueType.STRING,
            value="value",
            inherited=False,
            source_node_id=node_id,
        )
        assert attr.inherited is False
        assert attr.source_node_id == node_id

    def test_inherited_true_with_valid_source_node_id(self):
        """Test that inherited=True with valid source_node_id passes validation."""
        node_id = uuid4()
        attr = ResolvedAttribute(
            key="inherited_attr",
            title="Inherited Attribute",
            value_type=AttributeValueType.STRING,
            value="value",
            inherited=True,
            source_node_id=node_id,
        )
        assert attr.inherited is True
        assert attr.source_node_id == node_id

    def test_resolved_attribute_all_number_types(self):
        """Test resolved attributes with all value types."""
        test_cases = [
            (
                AttributeValueType.STRING,
                "string_value",
                "string_value",
            ),
            (
                AttributeValueType.NUMBER,
                42.5,
                42.5,
            ),
            (
                AttributeValueType.BOOLEAN,
                True,
                True,
            ),
            (
                AttributeValueType.DATE,
                "2024-01-15",
                "2024-01-15",
            ),
            (
                AttributeValueType.URL,
                "https://example.com",
                "https://example.com",
            ),
        ]

        for value_type, input_val, expected_val in test_cases:
            attr = ResolvedAttribute(
                key="test_attribute",
                title="Test Attribute",
                value_type=value_type,
                value=input_val,
                inherited=True,
                source_node_id=uuid4(),
            )
            assert attr.value == expected_val
            assert attr.value_type == value_type
            assert attr.inherited is True


class TestAttributeIntegration:
    """Integration tests for attribute model usage patterns."""

    def test_create_local_attribute_set(self):
        """Test creating a list of local attributes for a node."""
        attributes = [
            StructureNodeAttribute(
                key="creator",
                title="Creator",
                value_type=AttributeValueType.STRING,
                value="John Doe",
            ),
            StructureNodeAttribute(
                key="version_number",
                title="Version Number",
                value_type=AttributeValueType.NUMBER,
                value=2.1,
            ),
            StructureNodeAttribute(
                key="is_published",
                title="Is Published",
                value_type=AttributeValueType.BOOLEAN,
                value=True,
            ),
        ]
        assert len(attributes) == 3
        assert all(not attr.inherited for attr in attributes if hasattr(attr, "inherited"))

    def test_resolve_attribute_hierarchy(self):
        """Test resolving attributes with inheritance from parent."""
        parent_id = uuid4()
        child_id = uuid4()

        # Child overrides one, inherits another
        child_attrs = [
            ResolvedAttribute(
                key="category",
                title="Category",
                value_type=AttributeValueType.STRING,
                value="child_category",
                inherited=False,
                source_node_id=child_id,
            ),
            ResolvedAttribute(
                key="priority",
                title="Priority",
                value_type=AttributeValueType.NUMBER,
                value=1,
                inherited=True,
                source_node_id=parent_id,
            ),
        ]

        # Verify child has correct values
        category_attr = next(a for a in child_attrs if a.key == "category")
        assert category_attr.value == "child_category"
        assert category_attr.inherited is False

        priority_attr = next(a for a in child_attrs if a.key == "priority")
        assert priority_attr.value == 1
        assert priority_attr.inherited is True
        assert priority_attr.source_node_id == parent_id

    def test_attribute_json_serialization(self):
        """Test that attributes can be serialized to JSON."""
        attr = StructureNodeAttribute(
            key="test_key",
            title="Test Key",
            value_type=AttributeValueType.STRING,
            value="test_value",
        )
        json_data = attr.model_dump_json()
        assert isinstance(json_data, str)
        assert "test_key" in json_data
        assert "string" in json_data

    def test_resolved_attribute_json_serialization(self):
        """Test that resolved attributes can be serialized to JSON."""
        node_id = uuid4()
        attr = ResolvedAttribute(
            key="test_key",
            title="Test Key",
            value_type=AttributeValueType.STRING,
            value="test_value",
            inherited=True,
            source_node_id=node_id,
        )
        json_data = attr.model_dump_json()
        assert isinstance(json_data, str)
        assert "inherited" in json_data
        assert "true" in json_data.lower()
