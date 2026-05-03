"""
Unit tests for interchange value objects.

Tests invariants and discriminator validity for SerializationScope and ImportConflict.
"""

import sys
import os

import pytest

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from domain.interchange.value_objects import (
    SerializationScope,
    SerializationScopeType,
    ImportConflict,
    MatchKind,
    ResolutionKind,
)


class TestSerializationScopeValidation:
    """Test SerializationScope discriminator validity."""

    def test_whole_graph_valid(self):
        """WHOLE_GRAPH scope with no other fields is valid."""
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        scope.validate()  # Should not raise

    def test_whole_graph_rejects_taxonomy_id(self):
        """WHOLE_GRAPH scope cannot have taxonomy_id."""
        scope = SerializationScope(
            scope_type=SerializationScopeType.WHOLE_GRAPH,
            taxonomy_id="tax-1",
        )
        with pytest.raises(ValueError, match="must not have"):
            scope.validate()

    def test_whole_graph_rejects_scheme_id(self):
        """WHOLE_GRAPH scope cannot have scheme_id."""
        scope = SerializationScope(
            scope_type=SerializationScopeType.WHOLE_GRAPH,
            scheme_id="scheme-1",
        )
        with pytest.raises(ValueError, match="must not have"):
            scope.validate()

    def test_whole_graph_rejects_entity_ids(self):
        """WHOLE_GRAPH scope cannot have entity_ids."""
        scope = SerializationScope(
            scope_type=SerializationScopeType.WHOLE_GRAPH,
            entity_ids=("entity-1",),
        )
        with pytest.raises(ValueError, match="must not have"):
            scope.validate()

    def test_taxonomy_valid(self):
        """TAXONOMY scope with taxonomy_id is valid."""
        scope = SerializationScope(
            scope_type=SerializationScopeType.TAXONOMY,
            taxonomy_id="tax-1",
        )
        scope.validate()  # Should not raise

    def test_taxonomy_requires_id(self):
        """TAXONOMY scope requires taxonomy_id."""
        scope = SerializationScope(scope_type=SerializationScopeType.TAXONOMY)
        with pytest.raises(ValueError, match="requires taxonomy_id"):
            scope.validate()

    def test_taxonomy_rejects_scheme_id(self):
        """TAXONOMY scope cannot have scheme_id."""
        scope = SerializationScope(
            scope_type=SerializationScopeType.TAXONOMY,
            taxonomy_id="tax-1",
            scheme_id="scheme-1",
        )
        with pytest.raises(ValueError, match="must not have"):
            scope.validate()

    def test_taxonomy_rejects_entity_ids(self):
        """TAXONOMY scope cannot have entity_ids."""
        scope = SerializationScope(
            scope_type=SerializationScopeType.TAXONOMY,
            taxonomy_id="tax-1",
            entity_ids=("entity-1",),
        )
        with pytest.raises(ValueError, match="must not have"):
            scope.validate()

    def test_scheme_valid(self):
        """SCHEME scope with scheme_id is valid."""
        scope = SerializationScope(
            scope_type=SerializationScopeType.SCHEME,
            scheme_id="scheme-1",
        )
        scope.validate()  # Should not raise

    def test_scheme_requires_id(self):
        """SCHEME scope requires scheme_id."""
        scope = SerializationScope(scope_type=SerializationScopeType.SCHEME)
        with pytest.raises(ValueError, match="requires scheme_id"):
            scope.validate()

    def test_scheme_rejects_taxonomy_id(self):
        """SCHEME scope cannot have taxonomy_id."""
        scope = SerializationScope(
            scope_type=SerializationScopeType.SCHEME,
            scheme_id="scheme-1",
            taxonomy_id="tax-1",
        )
        with pytest.raises(ValueError, match="must not have"):
            scope.validate()

    def test_scheme_rejects_entity_ids(self):
        """SCHEME scope cannot have entity_ids."""
        scope = SerializationScope(
            scope_type=SerializationScopeType.SCHEME,
            scheme_id="scheme-1",
            entity_ids=("entity-1",),
        )
        with pytest.raises(ValueError, match="must not have"):
            scope.validate()

    def test_scheme_include_descendants_flag(self):
        """SCHEME scope can have include_descendants flag."""
        scope = SerializationScope(
            scope_type=SerializationScopeType.SCHEME,
            scheme_id="scheme-1",
            include_descendants=True,
        )
        scope.validate()  # Should not raise

    def test_entity_set_valid(self):
        """ENTITY_SET scope with entity_ids is valid."""
        scope = SerializationScope(
            scope_type=SerializationScopeType.ENTITY_SET,
            entity_ids=("entity-1", "entity-2"),
        )
        scope.validate()  # Should not raise

    def test_entity_set_requires_ids(self):
        """ENTITY_SET scope requires entity_ids."""
        scope = SerializationScope(scope_type=SerializationScopeType.ENTITY_SET)
        with pytest.raises(ValueError, match="requires entity_ids"):
            scope.validate()

    def test_entity_set_rejects_empty_ids(self):
        """ENTITY_SET scope cannot have empty entity_ids."""
        scope = SerializationScope(
            scope_type=SerializationScopeType.ENTITY_SET,
            entity_ids=(),
        )
        with pytest.raises(ValueError, match="requires entity_ids"):
            scope.validate()

    def test_entity_set_rejects_taxonomy_id(self):
        """ENTITY_SET scope cannot have taxonomy_id."""
        scope = SerializationScope(
            scope_type=SerializationScopeType.ENTITY_SET,
            entity_ids=("entity-1",),
            taxonomy_id="tax-1",
        )
        with pytest.raises(ValueError, match="must not have"):
            scope.validate()

    def test_entity_set_rejects_scheme_id(self):
        """ENTITY_SET scope cannot have scheme_id."""
        scope = SerializationScope(
            scope_type=SerializationScopeType.ENTITY_SET,
            entity_ids=("entity-1",),
            scheme_id="scheme-1",
        )
        with pytest.raises(ValueError, match="must not have"):
            scope.validate()


class TestImportConflictDefaultResolution:
    """Test ImportConflict.default_resolution derivation from match_kind."""

    def test_external_reference_defaults_to_merge(self):
        """EXTERNAL_REFERENCE matches default to MERGE."""
        resolution = ImportConflict.derive_default_resolution(
            MatchKind.EXTERNAL_REFERENCE
        )
        assert resolution == ResolutionKind.MERGE

    def test_uuid_defaults_to_skip(self):
        """UUID matches default to SKIP."""
        resolution = ImportConflict.derive_default_resolution(MatchKind.UUID)
        assert resolution == ResolutionKind.SKIP

    def test_title_defaults_to_skip(self):
        """TITLE matches default to SKIP."""
        resolution = ImportConflict.derive_default_resolution(MatchKind.TITLE)
        assert resolution == ResolutionKind.SKIP

    def test_conflict_with_derived_default(self):
        """ImportConflict can be created with derived default_resolution."""
        conflict = ImportConflict(
            match_kind=MatchKind.EXTERNAL_REFERENCE,
            incoming={"id": "incoming-1"},
            existing="existing-1",
            default_resolution=ImportConflict.derive_default_resolution(
                MatchKind.EXTERNAL_REFERENCE
            ),
            available_resolutions=(
                ResolutionKind.SKIP,
                ResolutionKind.OVERWRITE,
                ResolutionKind.MERGE,
                ResolutionKind.RENAME,
                ResolutionKind.ABORT,
            ),
        )

        assert conflict.default_resolution == ResolutionKind.MERGE
