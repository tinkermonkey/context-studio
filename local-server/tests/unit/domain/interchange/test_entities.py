"""
Unit tests for interchange domain entities.

Tests domain invariants and state transitions for ImportRun.
"""

import sys
import os
from datetime import datetime, timezone

import pytest

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from domain.interchange.entities import (
    ImportRun,
    ImportRunStatus,
)
from domain.interchange.value_objects import (
    SerializationScope,
    SerializationScopeType,
    SerializationFormat,
    MatchKind,
    ResolutionKind,
)


class TestImportRunStatus:
    """Test ImportRunStatus transitions and invariants."""

    def test_pending_to_committed(self):
        """PENDING can transition to COMMITTED."""
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        run = ImportRun(
            id="test-run-1",
            created_at=datetime.now(timezone.utc),
            created_by="user-1",
            format=SerializationFormat.SKOS,
            source_uri="test.skos",
            source_hash="abc123",
            scope=scope,
            status=ImportRunStatus.PENDING,
        )

        run.mark_committed()
        assert run.status == ImportRunStatus.COMMITTED

    def test_pending_to_failed(self):
        """PENDING can transition to FAILED."""
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        run = ImportRun(
            id="test-run-1",
            created_at=datetime.now(timezone.utc),
            created_by="user-1",
            format=SerializationFormat.SKOS,
            source_uri="test.skos",
            source_hash="abc123",
            scope=scope,
            status=ImportRunStatus.PENDING,
        )

        run.mark_failed()
        assert run.status == ImportRunStatus.FAILED

    def test_pending_to_rolled_back(self):
        """PENDING can transition to ROLLED_BACK."""
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        run = ImportRun(
            id="test-run-1",
            created_at=datetime.now(timezone.utc),
            created_by="user-1",
            format=SerializationFormat.SKOS,
            source_uri="test.skos",
            source_hash="abc123",
            scope=scope,
            status=ImportRunStatus.PENDING,
        )

        run.mark_rolled_back()
        assert run.status == ImportRunStatus.ROLLED_BACK

    def test_committed_terminal_cannot_transition(self):
        """COMMITTED is terminal; cannot transition to other states."""
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        run = ImportRun(
            id="test-run-1",
            created_at=datetime.now(timezone.utc),
            created_by="user-1",
            format=SerializationFormat.SKOS,
            source_uri="test.skos",
            source_hash="abc123",
            scope=scope,
            status=ImportRunStatus.COMMITTED,
        )

        with pytest.raises(ValueError, match="terminal state"):
            run.mark_failed()

        with pytest.raises(ValueError, match="terminal state"):
            run.mark_committed()

    def test_failed_terminal_cannot_rollback(self):
        """FAILED is terminal; cannot transition to other states."""
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        run = ImportRun(
            id="test-run-1",
            created_at=datetime.now(timezone.utc),
            created_by="user-1",
            format=SerializationFormat.SKOS,
            source_uri="test.skos",
            source_hash="abc123",
            scope=scope,
            status=ImportRunStatus.FAILED,
        )

        with pytest.raises(ValueError, match="terminal state"):
            run.mark_rolled_back()

        with pytest.raises(ValueError, match="terminal state"):
            run.mark_committed()

    def test_committed_cannot_rollback(self):
        """COMMITTED is terminal; cannot transition to other states."""
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        run = ImportRun(
            id="test-run-1",
            created_at=datetime.now(timezone.utc),
            created_by="user-1",
            format=SerializationFormat.SKOS,
            source_uri="test.skos",
            source_hash="abc123",
            scope=scope,
            status=ImportRunStatus.COMMITTED,
        )

        with pytest.raises(ValueError, match="terminal state"):
            run.mark_rolled_back()


class TestImportRunResolutions:
    """Test resolution recording."""

    def test_add_resolution(self):
        """Can add resolutions to a run."""
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        run = ImportRun(
            id="test-run-1",
            created_at=datetime.now(timezone.utc),
            created_by="user-1",
            format=SerializationFormat.SKOS,
            source_uri="test.skos",
            source_hash="abc123",
            scope=scope,
        )

        assert len(run.resolutions) == 0

        run.add_resolution(
            match_kind=MatchKind.EXTERNAL_REFERENCE,
            entity_id="entity-1",
            resolution_chosen=ResolutionKind.MERGE,
        )

        assert len(run.resolutions) == 1
        assert run.resolutions[0].match_kind == MatchKind.EXTERNAL_REFERENCE
        assert run.resolutions[0].entity_id == "entity-1"
        assert run.resolutions[0].resolution_chosen == ResolutionKind.MERGE

    def test_add_multiple_resolutions(self):
        """Can add multiple resolutions."""
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        run = ImportRun(
            id="test-run-1",
            created_at=datetime.now(timezone.utc),
            created_by="user-1",
            format=SerializationFormat.SKOS,
            source_uri="test.skos",
            source_hash="abc123",
            scope=scope,
        )

        run.add_resolution(
            MatchKind.EXTERNAL_REFERENCE, "entity-1", ResolutionKind.MERGE
        )
        run.add_resolution(MatchKind.TITLE, "entity-2", ResolutionKind.SKIP)
        run.add_resolution(MatchKind.UUID, "entity-3", ResolutionKind.OVERWRITE)

        assert len(run.resolutions) == 3

    def test_add_resolution_terminal_committed(self):
        """Cannot add resolution to a committed run."""
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        run = ImportRun(
            id="test-run-1",
            created_at=datetime.now(timezone.utc),
            created_by="user-1",
            format=SerializationFormat.SKOS,
            source_uri="test.skos",
            source_hash="abc123",
            scope=scope,
            status=ImportRunStatus.COMMITTED,
        )

        with pytest.raises(ValueError, match="terminal state"):
            run.add_resolution(
                MatchKind.EXTERNAL_REFERENCE, "entity-1", ResolutionKind.MERGE
            )

    def test_add_resolution_terminal_failed(self):
        """Cannot add resolution to a failed run."""
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        run = ImportRun(
            id="test-run-1",
            created_at=datetime.now(timezone.utc),
            created_by="user-1",
            format=SerializationFormat.SKOS,
            source_uri="test.skos",
            source_hash="abc123",
            scope=scope,
            status=ImportRunStatus.FAILED,
        )

        with pytest.raises(ValueError, match="terminal state"):
            run.add_resolution(
                MatchKind.EXTERNAL_REFERENCE, "entity-1", ResolutionKind.MERGE
            )

    def test_add_resolution_terminal_rolled_back(self):
        """Cannot add resolution to a rolled back run."""
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        run = ImportRun(
            id="test-run-1",
            created_at=datetime.now(timezone.utc),
            created_by="user-1",
            format=SerializationFormat.SKOS,
            source_uri="test.skos",
            source_hash="abc123",
            scope=scope,
            status=ImportRunStatus.ROLLED_BACK,
        )

        with pytest.raises(ValueError, match="terminal state"):
            run.add_resolution(
                MatchKind.EXTERNAL_REFERENCE, "entity-1", ResolutionKind.MERGE
            )


class TestImportRunAffectedEntities:
    """Test affected entity tracking."""

    def test_add_affected_entity(self):
        """Can add affected entity IDs."""
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        run = ImportRun(
            id="test-run-1",
            created_at=datetime.now(timezone.utc),
            created_by="user-1",
            format=SerializationFormat.SKOS,
            source_uri="test.skos",
            source_hash="abc123",
            scope=scope,
        )

        assert len(run.affected_entity_ids) == 0

        run.add_affected_entity("entity-1")
        assert len(run.affected_entity_ids) == 1
        assert "entity-1" in run.affected_entity_ids

    def test_add_affected_entity_idempotent(self):
        """Adding the same affected entity twice doesn't duplicate."""
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        run = ImportRun(
            id="test-run-1",
            created_at=datetime.now(timezone.utc),
            created_by="user-1",
            format=SerializationFormat.SKOS,
            source_uri="test.skos",
            source_hash="abc123",
            scope=scope,
        )

        run.add_affected_entity("entity-1")
        run.add_affected_entity("entity-1")

        assert len(run.affected_entity_ids) == 1
        assert run.affected_entity_ids.count("entity-1") == 1

    def test_add_affected_entity_terminal_committed(self):
        """Cannot add affected entity to a committed run."""
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        run = ImportRun(
            id="test-run-1",
            created_at=datetime.now(timezone.utc),
            created_by="user-1",
            format=SerializationFormat.SKOS,
            source_uri="test.skos",
            source_hash="abc123",
            scope=scope,
            status=ImportRunStatus.COMMITTED,
        )

        with pytest.raises(ValueError, match="terminal state"):
            run.add_affected_entity("entity-1")

    def test_add_affected_entity_terminal_failed(self):
        """Cannot add affected entity to a failed run."""
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        run = ImportRun(
            id="test-run-1",
            created_at=datetime.now(timezone.utc),
            created_by="user-1",
            format=SerializationFormat.SKOS,
            source_uri="test.skos",
            source_hash="abc123",
            scope=scope,
            status=ImportRunStatus.FAILED,
        )

        with pytest.raises(ValueError, match="terminal state"):
            run.add_affected_entity("entity-1")

    def test_add_affected_entity_terminal_rolled_back(self):
        """Cannot add affected entity to a rolled back run."""
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        run = ImportRun(
            id="test-run-1",
            created_at=datetime.now(timezone.utc),
            created_by="user-1",
            format=SerializationFormat.SKOS,
            source_uri="test.skos",
            source_hash="abc123",
            scope=scope,
            status=ImportRunStatus.ROLLED_BACK,
        )

        with pytest.raises(ValueError, match="terminal state"):
            run.add_affected_entity("entity-1")

    def test_resolutions_immutable(self):
        """Resolutions field returns immutable tuple, preventing direct modification."""
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        run = ImportRun(
            id="test-run-1",
            created_at=datetime.now(timezone.utc),
            created_by="user-1",
            format=SerializationFormat.SKOS,
            source_uri="test.skos",
            source_hash="abc123",
            scope=scope,
        )

        run.add_resolution(
            MatchKind.EXTERNAL_REFERENCE, "entity-1", ResolutionKind.MERGE
        )

        # Returned resolutions is a tuple (immutable)
        assert isinstance(run.resolutions, tuple)
        assert len(run.resolutions) == 1

        # Cannot modify the returned tuple
        with pytest.raises(AttributeError):
            run.resolutions.append(  # type: ignore
                type("obj", (), {})()
            )

    def test_affected_entity_ids_immutable(self):
        """Affected entity IDs field returns immutable tuple, preventing direct modification."""
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        run = ImportRun(
            id="test-run-1",
            created_at=datetime.now(timezone.utc),
            created_by="user-1",
            format=SerializationFormat.SKOS,
            source_uri="test.skos",
            source_hash="abc123",
            scope=scope,
        )

        run.add_affected_entity("entity-1")

        # Returned affected_entity_ids is a tuple (immutable)
        assert isinstance(run.affected_entity_ids, tuple)
        assert len(run.affected_entity_ids) == 1

        # Cannot modify the returned tuple
        with pytest.raises(AttributeError):
            run.affected_entity_ids.append("entity-2")  # type: ignore
