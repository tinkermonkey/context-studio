"""
Unit tests for AttributeDefinition entity in the Ontology Management context.

These tests verify AttributeDefinition behavior in isolation — entity construction,
identifier validation, and the rename method.
"""

import pytest

from domain.ontology.entities import AttributeDefinition
from domain.ontology.value_objects import ExternalReference, Status


class TestAttributeDefinitionCreation:
    """Tests for AttributeDefinition entity construction."""

    def test_attribute_definition_creation_minimal(self):
        """Create an attribute definition with required fields only."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="name",
            title="Name",
            datatype="string",
        )
        assert attr_def.id == "attr-1"
        assert attr_def.class_id == "cls-1"
        assert attr_def.identifier == "name"
        assert attr_def.title == "Name"
        assert attr_def.datatype == "string"
        assert attr_def.description is None
        assert attr_def.is_required is False
        assert attr_def.allowed_values is None
        assert attr_def.default_value is None
        assert attr_def.sort_order == 0
        assert attr_def.status == Status.DRAFT
        assert len(attr_def.external_references) == 0

    def test_attribute_definition_creation_with_all_fields(self):
        """Create an attribute definition with all optional fields."""
        ext_ref = ExternalReference(
            source="DR", identifier="node_schema.attribute_name"
        )
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="name",
            title="Name",
            datatype="string",
            description="The entity's name",
            is_required=True,
            allowed_values=["alice", "bob", "charlie"],
            default_value="alice",
            sort_order=1,
            external_references=[ext_ref],
            status=Status.PUBLISHED,
        )
        assert attr_def.description == "The entity's name"
        assert attr_def.is_required is True
        assert attr_def.allowed_values == ["alice", "bob", "charlie"]
        assert attr_def.default_value == "alice"
        assert attr_def.sort_order == 1
        assert len(attr_def.external_references) == 1
        assert attr_def.external_references[0].source == "DR"
        assert attr_def.status == Status.PUBLISHED

    def test_attribute_definition_with_different_datatypes(self):
        """Create attribute definitions with various datatypes."""
        for datatype in ["string", "integer", "boolean", "array", "object"]:
            attr_def = AttributeDefinition(
                id="attr-1",
                class_id="cls-1",
                identifier=f"attr_{datatype}",
                title=f"Attribute {datatype}",
                datatype=datatype,
            )
            assert attr_def.datatype == datatype

    def test_attribute_definition_class_id_is_required(self):
        """AttributeDefinition requires class_id (no global registry)."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="name",
            title="Name",
            datatype="string",
        )
        assert attr_def.class_id == "cls-1"
        assert attr_def.class_id is not None

    def test_attribute_definition_two_with_same_identifier_different_class_ids(self):
        """Two AttributeDefinitions with same identifier but different class_ids construct
        independently."""
        attr_def_1 = AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="name",
            title="Name",
            datatype="string",
        )
        attr_def_2 = AttributeDefinition(
            id="attr-2",
            class_id="cls-2",
            identifier="name",
            title="Name",
            datatype="string",
        )
        assert attr_def_1.id == "attr-1"
        assert attr_def_2.id == "attr-2"
        assert attr_def_1.class_id == "cls-1"
        assert attr_def_2.class_id == "cls-2"
        # No collision at domain level — both are valid
        assert attr_def_1 is not attr_def_2

    def test_attribute_definition_allowed_values_enum(self):
        """AttributeDefinition supports explicit allowed_values for enum constraints."""
        allowed_values = ["red", "green", "blue"]
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="color",
            title="Color",
            datatype="string",
            allowed_values=allowed_values,
        )
        assert attr_def.allowed_values == allowed_values
        assert len(attr_def.allowed_values) == 3

    def test_attribute_definition_allowed_values_none_means_unconstrained(self):
        """When allowed_values is None, the attribute is unconstrained."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="color",
            title="Color",
            datatype="string",
            allowed_values=None,
        )
        assert attr_def.allowed_values is None


class TestAttributeDefinitionIdentifierValidation:
    """Tests for identifier validation via __post_init__."""

    def test_identifier_valid_slug(self):
        """Valid slug identifier passes validation."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="my_attribute",
            title="My Attribute",
            datatype="string",
        )
        assert attr_def.identifier == "my_attribute"

    def test_identifier_lowercase_and_underscore(self):
        """Identifier is normalized to lowercase with underscores."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="MyAttribute",
            title="My Attribute",
            datatype="string",
        )
        assert attr_def.identifier == "myattribute"

    def test_identifier_with_numbers(self):
        """Valid identifier containing numbers."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="attribute_1",
            title="Attribute 1",
            datatype="string",
        )
        assert attr_def.identifier == "attribute_1"

    def test_identifier_empty_raises_error(self):
        """Creating an AttributeDefinition with empty identifier raises ValueError."""
        with pytest.raises(ValueError, match="Identifier cannot be empty"):
            AttributeDefinition(
                id="attr-1",
                class_id="cls-1",
                identifier="",
                title="My Attribute",
                datatype="string",
            )

    def test_identifier_whitespace_only_raises_error(self):
        """Creating an AttributeDefinition with whitespace-only identifier raises ValueError."""
        with pytest.raises(ValueError, match="Identifier cannot be empty"):
            AttributeDefinition(
                id="attr-1",
                class_id="cls-1",
                identifier="   ",
                title="My Attribute",
                datatype="string",
            )

    def test_identifier_starts_with_number_raises_error(self):
        """Identifier starting with number raises ValueError."""
        with pytest.raises(
            ValueError,
            match="Identifier must start with a lowercase letter",
        ):
            AttributeDefinition(
                id="attr-1",
                class_id="cls-1",
                identifier="1attribute",
                title="My Attribute",
                datatype="string",
            )

    def test_identifier_with_invalid_chars_raises_error(self):
        """Identifier with special characters (except underscore) raises ValueError."""
        with pytest.raises(
            ValueError,
            match="Identifier must start with a lowercase letter",
        ):
            AttributeDefinition(
                id="attr-1",
                class_id="cls-1",
                identifier="my-attribute",
                title="My Attribute",
                datatype="string",
            )

    def test_identifier_too_short_raises_error(self):
        """Identifier shorter than 2 characters raises ValueError."""
        with pytest.raises(
            ValueError,
            match="Identifier must start with a lowercase letter",
        ):
            AttributeDefinition(
                id="attr-1",
                class_id="cls-1",
                identifier="a",
                title="A",
                datatype="string",
            )

    def test_identifier_too_long_raises_error(self):
        """Identifier longer than 64 characters raises ValueError."""
        long_identifier = "a" + "b" * 64
        with pytest.raises(
            ValueError,
            match="Identifier must start with a lowercase letter",
        ):
            AttributeDefinition(
                id="attr-1",
                class_id="cls-1",
                identifier=long_identifier,
                title="Long Identifier",
                datatype="string",
            )


class TestAttributeDefinitionRename:
    """Tests for the rename() method."""

    def test_rename_success(self):
        """Rename an attribute definition."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="name",
            title="Name",
            datatype="string",
        )
        old_title = attr_def.title
        attr_def.rename("Entity Name")
        assert attr_def.title == "Entity Name"
        assert attr_def.title != old_title

    def test_rename_updates_last_modified(self):
        """Rename updates the last_modified timestamp."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="name",
            title="Name",
            datatype="string",
            last_modified=None,
        )
        assert attr_def.last_modified is None
        attr_def.rename("Entity Name")
        assert attr_def.last_modified is not None

    def test_rename_empty_string_raises_error(self):
        """Rename with empty string raises ValueError."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="name",
            title="Name",
            datatype="string",
        )
        with pytest.raises(ValueError, match="Title cannot be empty"):
            attr_def.rename("")

    def test_rename_whitespace_only_raises_error(self):
        """Rename with whitespace-only string raises ValueError."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="name",
            title="Name",
            datatype="string",
        )
        with pytest.raises(ValueError, match="Title cannot be empty"):
            attr_def.rename("   ")

    def test_rename_matches_property_definition_pattern(self):
        """Rename behavior matches PropertyDefinition.rename() pattern."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="name",
            title="Name",
            datatype="string",
        )
        attr_def.rename("New Name")
        assert attr_def.title == "New Name"

    def test_rename_with_various_titles(self):
        """Rename with different title formats."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="name",
            title="Name",
            datatype="string",
        )
        # Test various title formats
        titles = [
            "Single",
            "Multiple Words",
            "With-Hyphens",
            "With_Underscores",
            "With Numbers 123",
            "123 Numbers First",
        ]
        for title in titles:
            attr_def.rename(title)
            assert attr_def.title == title


class TestAttributeDefinitionVersioning:
    """Tests for version and status fields."""

    def test_attribute_definition_default_version(self):
        """AttributeDefinition has default version of 1."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="name",
            title="Name",
            datatype="string",
        )
        assert attr_def.version == 1

    def test_attribute_definition_default_status_draft(self):
        """AttributeDefinition has default status of DRAFT."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="name",
            title="Name",
            datatype="string",
        )
        assert attr_def.status == Status.DRAFT

    def test_attribute_definition_published_status(self):
        """AttributeDefinition can be created with PUBLISHED status."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="name",
            title="Name",
            datatype="string",
            status=Status.PUBLISHED,
        )
        assert attr_def.status == Status.PUBLISHED


class TestAttributeDefinitionSortOrder:
    """Tests for sort_order field."""

    def test_sort_order_default_zero(self):
        """AttributeDefinition has default sort_order of 0."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="name",
            title="Name",
            datatype="string",
        )
        assert attr_def.sort_order == 0

    def test_sort_order_custom_value(self):
        """AttributeDefinition can have custom sort_order."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="name",
            title="Name",
            datatype="string",
            sort_order=5,
        )
        assert attr_def.sort_order == 5

    def test_sort_order_negative_value(self):
        """AttributeDefinition can have negative sort_order."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="name",
            title="Name",
            datatype="string",
            sort_order=-1,
        )
        assert attr_def.sort_order == -1


class TestAttributeDefinitionExternalReferences:
    """Tests for external_references field."""

    def test_external_references_default_empty(self):
        """AttributeDefinition has default empty external_references."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="name",
            title="Name",
            datatype="string",
        )
        assert attr_def.external_references == []

    def test_external_references_with_single_reference(self):
        """AttributeDefinition can have a single external reference."""
        ref = ExternalReference(
            source="DR", identifier="node_schema.attribute_name"
        )
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="name",
            title="Name",
            datatype="string",
            external_references=[ref],
        )
        assert len(attr_def.external_references) == 1
        assert attr_def.external_references[0].source == "DR"

    def test_external_references_with_multiple_references(self):
        """AttributeDefinition can have multiple external references."""
        ref1 = ExternalReference(
            source="DR", identifier="node_schema.attribute_name"
        )
        ref2 = ExternalReference(
            source="schema.org", identifier="https://schema.org/name"
        )
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="name",
            title="Name",
            datatype="string",
            external_references=[ref1, ref2],
        )
        assert len(attr_def.external_references) == 2
        assert attr_def.external_references[0].source == "DR"
        assert attr_def.external_references[1].source == "schema.org"


class TestAttributeDefinitionDefaultValueValidation:
    """Tests for cross-field validation of default_value against allowed_values."""

    def test_default_value_in_allowed_values_valid(self):
        """Creating an AttributeDefinition with default_value in allowed_values succeeds."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="color",
            title="Color",
            datatype="string",
            allowed_values=["red", "green", "blue"],
            default_value="red",
        )
        assert attr_def.default_value == "red"
        assert attr_def.allowed_values == ["red", "green", "blue"]

    def test_default_value_not_in_allowed_values_raises_error(self):
        """Creating an AttributeDefinition with default_value not in allowed_values raises ValueError."""
        with pytest.raises(
            ValueError,
            match="Default value 'yellow' is not in allowed values",
        ):
            AttributeDefinition(
                id="attr-1",
                class_id="cls-1",
                identifier="color",
                title="Color",
                datatype="string",
                allowed_values=["red", "green", "blue"],
                default_value="yellow",
            )

    def test_no_default_value_with_allowed_values(self):
        """Creating an AttributeDefinition with allowed_values but no default_value is valid."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="color",
            title="Color",
            datatype="string",
            allowed_values=["red", "green", "blue"],
            default_value=None,
        )
        assert attr_def.default_value is None
        assert attr_def.allowed_values == ["red", "green", "blue"]

    def test_default_value_without_allowed_values(self):
        """Creating an AttributeDefinition with default_value but no allowed_values is valid."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="name",
            title="Name",
            datatype="string",
            allowed_values=None,
            default_value="John",
        )
        assert attr_def.default_value == "John"
        assert attr_def.allowed_values is None

    def test_neither_default_value_nor_allowed_values(self):
        """Creating an AttributeDefinition with neither default_value nor allowed_values is valid."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="name",
            title="Name",
            datatype="string",
            allowed_values=None,
            default_value=None,
        )
        assert attr_def.default_value is None
        assert attr_def.allowed_values is None

    def test_empty_allowed_values_list_with_default_value(self):
        """Creating an AttributeDefinition with empty allowed_values list and default_value is valid."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="color",
            title="Color",
            datatype="string",
            allowed_values=[],
            default_value="red",
        )
        assert attr_def.default_value == "red"
        assert attr_def.allowed_values == []

    def test_default_value_last_item_in_allowed_values(self):
        """Default value can be the last item in allowed_values."""
        attr_def = AttributeDefinition(
            id="attr-1",
            class_id="cls-1",
            identifier="color",
            title="Color",
            datatype="string",
            allowed_values=["red", "green", "blue"],
            default_value="blue",
        )
        assert attr_def.default_value == "blue"

    def test_default_value_exact_match_case_sensitive(self):
        """Default value matching is case-sensitive."""
        with pytest.raises(
            ValueError,
            match="Default value 'Red' is not in allowed values",
        ):
            AttributeDefinition(
                id="attr-1",
                class_id="cls-1",
                identifier="color",
                title="Color",
                datatype="string",
                allowed_values=["red", "green", "blue"],
                default_value="Red",
            )
