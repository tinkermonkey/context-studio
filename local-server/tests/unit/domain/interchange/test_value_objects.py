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
    ImportPlan,
    MatchKind,
    ResolutionKind,
)


class TestSerializationScopeValidation:
    """Test SerializationScope discriminator validity."""

    def test_whole_graph_valid(self):
        """WHOLE_GRAPH scope with no other fields is valid."""
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        # Validation happens at construction time via __post_init__

    def test_whole_graph_rejects_taxonomy_id(self):
        """WHOLE_GRAPH scope cannot have taxonomy_id."""
        with pytest.raises(ValueError, match="must not have"):
            SerializationScope(
                scope_type=SerializationScopeType.WHOLE_GRAPH,
                taxonomy_id="tax-1",
            )

    def test_whole_graph_rejects_scheme_id(self):
        """WHOLE_GRAPH scope cannot have scheme_id."""
        with pytest.raises(ValueError, match="must not have"):
            SerializationScope(
                scope_type=SerializationScopeType.WHOLE_GRAPH,
                scheme_id="scheme-1",
            )

    def test_whole_graph_rejects_entity_ids(self):
        """WHOLE_GRAPH scope cannot have entity_ids."""
        with pytest.raises(ValueError, match="must not have"):
            SerializationScope(
                scope_type=SerializationScopeType.WHOLE_GRAPH,
                entity_ids=("entity-1",),
            )

    def test_taxonomy_valid(self):
        """TAXONOMY scope with taxonomy_id is valid."""
        scope = SerializationScope(
            scope_type=SerializationScopeType.TAXONOMY,
            taxonomy_id="tax-1",
        )
        # Validation happens at construction time via __post_init__

    def test_taxonomy_requires_id(self):
        """TAXONOMY scope requires taxonomy_id."""
        with pytest.raises(ValueError, match="requires taxonomy_id"):
            SerializationScope(scope_type=SerializationScopeType.TAXONOMY)

    def test_taxonomy_rejects_scheme_id(self):
        """TAXONOMY scope cannot have scheme_id."""
        with pytest.raises(ValueError, match="must not have"):
            SerializationScope(
                scope_type=SerializationScopeType.TAXONOMY,
                taxonomy_id="tax-1",
                scheme_id="scheme-1",
            )

    def test_taxonomy_rejects_entity_ids(self):
        """TAXONOMY scope cannot have entity_ids."""
        with pytest.raises(ValueError, match="must not have"):
            SerializationScope(
                scope_type=SerializationScopeType.TAXONOMY,
                taxonomy_id="tax-1",
                entity_ids=("entity-1",),
            )

    def test_scheme_valid(self):
        """SCHEME scope with scheme_id is valid."""
        scope = SerializationScope(
            scope_type=SerializationScopeType.SCHEME,
            scheme_id="scheme-1",
        )
        # Validation happens at construction time via __post_init__

    def test_scheme_requires_id_at_construction(self):
        """SCHEME scope requires scheme_id at construction."""
        with pytest.raises(ValueError, match="requires scheme_id"):
            SerializationScope(scope_type=SerializationScopeType.SCHEME)

    def test_scheme_rejects_taxonomy_id(self):
        """SCHEME scope cannot have taxonomy_id."""
        with pytest.raises(ValueError, match="must not have"):
            SerializationScope(
                scope_type=SerializationScopeType.SCHEME,
                scheme_id="scheme-1",
                taxonomy_id="tax-1",
            )

    def test_scheme_rejects_entity_ids(self):
        """SCHEME scope cannot have entity_ids."""
        with pytest.raises(ValueError, match="must not have"):
            SerializationScope(
                scope_type=SerializationScopeType.SCHEME,
                scheme_id="scheme-1",
                entity_ids=("entity-1",),
            )

    def test_scheme_include_descendants_flag(self):
        """SCHEME scope can have include_descendants flag."""
        scope = SerializationScope(
            scope_type=SerializationScopeType.SCHEME,
            scheme_id="scheme-1",
            include_descendants=True,
        )
        # Validation happens at construction time via __post_init__

    def test_entity_set_valid(self):
        """ENTITY_SET scope with entity_ids is valid."""
        scope = SerializationScope(
            scope_type=SerializationScopeType.ENTITY_SET,
            entity_ids=("entity-1", "entity-2"),
        )
        # Validation happens at construction time via __post_init__

    def test_entity_set_requires_ids(self):
        """ENTITY_SET scope requires entity_ids."""
        with pytest.raises(ValueError, match="requires entity_ids"):
            SerializationScope(scope_type=SerializationScopeType.ENTITY_SET)

    def test_entity_set_rejects_empty_ids(self):
        """ENTITY_SET scope cannot have empty entity_ids."""
        with pytest.raises(ValueError, match="requires entity_ids"):
            SerializationScope(
                scope_type=SerializationScopeType.ENTITY_SET,
                entity_ids=(),
            )

    def test_entity_set_rejects_taxonomy_id(self):
        """ENTITY_SET scope cannot have taxonomy_id."""
        with pytest.raises(ValueError, match="must not have"):
            SerializationScope(
                scope_type=SerializationScopeType.ENTITY_SET,
                entity_ids=("entity-1",),
                taxonomy_id="tax-1",
            )

    def test_entity_set_rejects_scheme_id(self):
        """ENTITY_SET scope cannot have scheme_id."""
        with pytest.raises(ValueError, match="must not have"):
            SerializationScope(
                scope_type=SerializationScopeType.ENTITY_SET,
                entity_ids=("entity-1",),
                scheme_id="scheme-1",
            )


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


class TestImportPlanValidation:
    """Test ImportPlan validation invariants."""

    def test_import_plan_valid_with_non_negative_count(self):
        """ImportPlan can be created with non-negative new_entity_count."""
        plan = ImportPlan(
            conflicts=(),
            new_entity_count=5,
            import_run_id="run-1",
        )
        assert plan.new_entity_count == 5

    def test_import_plan_valid_with_zero_count(self):
        """ImportPlan can be created with zero new_entity_count."""
        plan = ImportPlan(
            conflicts=(),
            new_entity_count=0,
            import_run_id="run-1",
        )
        assert plan.new_entity_count == 0

    def test_import_plan_rejects_negative_count(self):
        """ImportPlan cannot be created with negative new_entity_count."""
        with pytest.raises(ValueError, match="non-negative"):
            ImportPlan(
                conflicts=(),
                new_entity_count=-1,
                import_run_id="run-1",
            )

    def test_import_plan_frozen(self):
        """ImportPlan is frozen and immutable."""
        plan = ImportPlan(
            conflicts=(),
            new_entity_count=5,
            import_run_id="run-1",
        )
        with pytest.raises(AttributeError):
            plan.new_entity_count = 10
