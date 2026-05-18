"""
Unit tests for ImportRunService.

Tests service methods for managing import run lifecycle, including:
- Creating and starting import runs
- Committing, failing, and rolling back runs
- Context variable management for correlation tracking
"""

import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from domain.interchange.entities import ImportRunStatus, ResolutionRecord
from domain.interchange.services import (
    ImportRunService,
    get_current_import_run_id,
    set_import_run_context,
)
from domain.interchange.value_objects import (
    MatchKind,
    ResolutionKind,
    SerializationFormat,
    SerializationScope,
    SerializationScopeType,
)
from tests.fakes.fake_interchange_repository import FakeInterchangeRepository


class TestImportRunServiceStartRun:
    """Test ImportRunService.start_run method."""

    def test_start_run_creates_pending_run(self):
        """start_run creates a new ImportRun in PENDING status."""
        service = ImportRunService()
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)

        run = service.start_run(
            format=SerializationFormat.SKOS,
            source_hash="abc123def456",
            scope=scope,
            source_uri="test.skos",
            created_by="user-1",
        )

        assert run.id is not None
        assert run.status == ImportRunStatus.PENDING
        assert run.format == SerializationFormat.SKOS
        assert run.source_hash == "abc123def456"
        assert run.source_uri == "test.skos"
        assert run.created_by == "user-1"

    def test_start_run_generates_unique_id(self):
        """start_run generates unique IDs for each run."""
        service = ImportRunService()
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)

        run1 = service.start_run(
            format=SerializationFormat.SKOS,
            source_hash="hash1",
            scope=scope,
        )
        run2 = service.start_run(
            format=SerializationFormat.SKOS,
            source_hash="hash2",
            scope=scope,
        )

        assert run1.id != run2.id

    def test_start_run_sets_created_at_timestamp(self):
        """start_run sets created_at timestamp."""
        service = ImportRunService()
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        before = datetime.now(timezone.utc)

        run = service.start_run(
            format=SerializationFormat.SKOS,
            source_hash="abc123",
            scope=scope,
        )

        after = datetime.now(timezone.utc)
        assert before <= run.created_at <= after

    def test_start_run_with_optional_fields(self):
        """start_run works with optional source_uri and created_by."""
        service = ImportRunService()
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)

        # Without optional fields
        run1 = service.start_run(
            format=SerializationFormat.SKOS,
            source_hash="abc123",
            scope=scope,
        )
        assert run1.source_uri is None
        assert run1.created_by is None

        # With optional fields
        run2 = service.start_run(
            format=SerializationFormat.SKOS,
            source_hash="abc123",
            scope=scope,
            source_uri="http://example.com/ontology.skos",
            created_by="alice",
        )
        assert run2.source_uri == "http://example.com/ontology.skos"
        assert run2.created_by == "alice"

    def test_start_run_with_different_scopes(self):
        """start_run works with different serialization scopes."""
        service = ImportRunService()

        # Whole graph scope
        scope_whole = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        run_whole = service.start_run(
            format=SerializationFormat.SKOS,
            source_hash="hash",
            scope=scope_whole,
        )
        assert run_whole.scope.scope_type == SerializationScopeType.WHOLE_GRAPH

        # Taxonomy scope
        scope_tax = SerializationScope(
            scope_type=SerializationScopeType.TAXONOMY,
            taxonomy_id="tax-1",
        )
        run_tax = service.start_run(
            format=SerializationFormat.SKOS,
            source_hash="hash",
            scope=scope_tax,
        )
        assert run_tax.scope.scope_type == SerializationScopeType.TAXONOMY
        assert run_tax.scope.taxonomy_id == "tax-1"


class TestImportRunServiceCommitRun:
    """Test ImportRunService.commit_run method."""

    def test_commit_run_transitions_to_committed(self):
        """commit_run transitions run from PENDING to COMMITTED."""
        service = ImportRunService()
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        run = service.start_run(
            format=SerializationFormat.SKOS,
            source_hash="abc123",
            scope=scope,
        )

        result = service.commit_run(run)

        assert result.status == ImportRunStatus.COMMITTED

    def test_commit_run_returns_same_run(self):
        """commit_run returns the updated ImportRun."""
        service = ImportRunService()
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        run = service.start_run(
            format=SerializationFormat.SKOS,
            source_hash="abc123",
            scope=scope,
        )

        result = service.commit_run(run)

        assert result.id == run.id
        assert result.source_hash == run.source_hash


class TestImportRunServiceFailRun:
    """Test ImportRunService.fail_run method."""

    def test_fail_run_transitions_to_failed(self):
        """fail_run transitions run from PENDING to FAILED."""
        service = ImportRunService()
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        run = service.start_run(
            format=SerializationFormat.SKOS,
            source_hash="abc123",
            scope=scope,
        )

        result = service.fail_run(run)

        assert result.status == ImportRunStatus.FAILED

    def test_fail_run_returns_same_run(self):
        """fail_run returns the updated ImportRun."""
        service = ImportRunService()
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        run = service.start_run(
            format=SerializationFormat.SKOS,
            source_hash="abc123",
            scope=scope,
        )

        result = service.fail_run(run)

        assert result.id == run.id
        assert result.source_hash == run.source_hash


class TestImportRunServiceRollbackRun:
    """Test ImportRunService.rollback_run method."""

    def test_rollback_run_transitions_to_rolled_back(self):
        """rollback_run transitions run from PENDING to ROLLED_BACK."""
        service = ImportRunService()
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        run = service.start_run(
            format=SerializationFormat.SKOS,
            source_hash="abc123",
            scope=scope,
        )

        result = service.rollback_run(run)

        assert result.status == ImportRunStatus.ROLLED_BACK

    def test_rollback_run_returns_same_run(self):
        """rollback_run returns the updated ImportRun."""
        service = ImportRunService()
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        run = service.start_run(
            format=SerializationFormat.SKOS,
            source_hash="abc123",
            scope=scope,
        )

        result = service.rollback_run(run)

        assert result.id == run.id
        assert result.source_hash == run.source_hash

    def test_rollback_run_fails_for_committed(self):
        """rollback_run raises ValueError for COMMITTED runs."""
        service = ImportRunService()
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        run = service.start_run(
            format=SerializationFormat.SKOS,
            source_hash="abc123",
            scope=scope,
        )
        service.commit_run(run)

        with pytest.raises(ValueError, match="terminal state"):
            service.rollback_run(run)


class TestImportRunServiceContextVariables:
    """Test context variable management for import correlation."""

    def test_get_context_import_run_id_when_not_set(self):
        """get_context_import_run_id returns None when not set."""
        # Clear context first
        set_import_run_context(None)

        service = ImportRunService()
        result = service.get_context_import_run_id()

        assert result is None

    def test_get_context_import_run_id_when_set(self):
        """get_context_import_run_id returns the set run ID."""
        service = ImportRunService()
        test_id = "test-run-12345"

        service.set_context_import_run_id(test_id)
        result = service.get_context_import_run_id()

        assert result == test_id

    def test_set_context_import_run_id_clears_with_none(self):
        """set_context_import_run_id clears context when passed None."""
        service = ImportRunService()
        test_id = "test-run-12345"

        # Set a value
        service.set_context_import_run_id(test_id)
        assert service.get_context_import_run_id() == test_id

        # Clear it
        service.set_context_import_run_id(None)
        assert service.get_context_import_run_id() is None

    def test_set_context_import_run_id_overwrites_previous(self):
        """set_context_import_run_id overwrites previous values."""
        service = ImportRunService()
        id1 = "run-1"
        id2 = "run-2"

        service.set_context_import_run_id(id1)
        assert service.get_context_import_run_id() == id1

        service.set_context_import_run_id(id2)
        assert service.get_context_import_run_id() == id2

    def test_global_context_functions_integration(self):
        """Test integration between service methods and global context functions."""
        service = ImportRunService()
        test_id = "test-run-integration"

        # Use service method
        service.set_context_import_run_id(test_id)

        # Check with global function
        assert get_current_import_run_id() == test_id

        # Clear with global function
        set_import_run_context(None)

        # Check with service method
        assert service.get_context_import_run_id() is None


class TestImportRunServiceLifecycle:
    """Test full lifecycle workflows."""

    def test_complete_successful_import_lifecycle(self):
        """Test complete lifecycle: start → set context → commit."""
        service = ImportRunService()
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)

        # Start import
        run = service.start_run(
            format=SerializationFormat.SKOS,
            source_hash="abc123",
            scope=scope,
            created_by="user-1",
        )
        assert run.status == ImportRunStatus.PENDING

        # Set context for correlation
        service.set_context_import_run_id(run.id)
        assert service.get_context_import_run_id() == run.id

        # Commit
        run = service.commit_run(run)
        assert run.status == ImportRunStatus.COMMITTED

    def test_failed_import_lifecycle(self):
        """Test lifecycle: start → fail."""
        service = ImportRunService()
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)

        run = service.start_run(
            format=SerializationFormat.SKOS,
            source_hash="abc123",
            scope=scope,
        )

        run = service.fail_run(run)
        assert run.status == ImportRunStatus.FAILED

    def test_cancelled_import_lifecycle(self):
        """Test lifecycle: start → rollback."""
        service = ImportRunService()
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)

        run = service.start_run(
            format=SerializationFormat.SKOS,
            source_hash="abc123",
            scope=scope,
        )

        run = service.rollback_run(run)
        assert run.status == ImportRunStatus.ROLLED_BACK


class TestImportRunServiceCreateWithResolutionsAndPersist:
    """Test ImportRunService.create_with_resolutions_and_persist method."""

    def test_create_with_resolutions_without_repo(self):
        """create_with_resolutions_and_persist creates ImportRun without persisting when repo is None."""
        service = ImportRunService()
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        resolutions = [
            ResolutionRecord(
                match_kind=MatchKind.EXTERNAL_REFERENCE,
                entity_id="entity-1",
                resolution_chosen=ResolutionKind.MERGE,
            ),
            ResolutionRecord(
                match_kind=MatchKind.UUID,
                entity_id="entity-2",
                resolution_chosen=ResolutionKind.SKIP,
            ),
        ]

        run = service.create_with_resolutions_and_persist(
            format=SerializationFormat.SKOS,
            source_hash="abc123def456",
            scope=scope,
            resolutions=resolutions,
            source_uri="test.skos",
            created_by="user-1",
            interchange_repo=None,
        )

        assert run.id is not None
        assert run.status == ImportRunStatus.PENDING
        assert run.format == SerializationFormat.SKOS
        assert run.source_hash == "abc123def456"
        assert run.source_uri == "test.skos"
        assert run.created_by == "user-1"
        assert len(run.resolutions) == 2
        assert run.resolutions[0].entity_id == "entity-1"
        assert run.resolutions[0].resolution_chosen == ResolutionKind.MERGE
        assert run.resolutions[1].entity_id == "entity-2"
        assert run.resolutions[1].resolution_chosen == ResolutionKind.SKIP

    def test_create_with_resolutions_with_repo(self):
        """create_with_resolutions_and_persist persists ImportRun when repo is provided."""
        service = ImportRunService()
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        resolutions = [
            ResolutionRecord(
                match_kind=MatchKind.EXTERNAL_REFERENCE,
                entity_id="entity-1",
                resolution_chosen=ResolutionKind.MERGE,
            ),
        ]
        repo = FakeInterchangeRepository()

        run = service.create_with_resolutions_and_persist(
            format=SerializationFormat.OWL,
            source_hash="xyz789",
            scope=scope,
            resolutions=resolutions,
            source_uri="test.owl",
            created_by="alice",
            interchange_repo=repo,
        )

        assert run.id is not None
        assert len(run.resolutions) == 1
        # Verify it was persisted by checking the repository
        persisted_run = repo.get(run.id)
        assert persisted_run is not None
        assert persisted_run.id == run.id
        assert persisted_run.format == SerializationFormat.OWL
        assert persisted_run.created_by == "alice"

    def test_create_without_resolutions(self):
        """create_with_resolutions_and_persist works with no resolutions provided."""
        service = ImportRunService()
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)

        run = service.create_with_resolutions_and_persist(
            format=SerializationFormat.GRAPHML,
            source_hash="graphml123",
            scope=scope,
            resolutions=None,
            interchange_repo=None,
        )

        assert run.id is not None
        assert run.status == ImportRunStatus.PENDING
        assert len(run.resolutions) == 0
        assert run.format == SerializationFormat.GRAPHML

    def test_create_records_all_resolutions(self):
        """create_with_resolutions_and_persist records all provided ResolutionRecords."""
        service = ImportRunService()
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        resolutions = [
            ResolutionRecord(
                match_kind=MatchKind.EXTERNAL_REFERENCE,
                entity_id="entity-1",
                resolution_chosen=ResolutionKind.MERGE,
            ),
            ResolutionRecord(
                match_kind=MatchKind.UUID,
                entity_id="entity-2",
                resolution_chosen=ResolutionKind.SKIP,
            ),
            ResolutionRecord(
                match_kind=MatchKind.TITLE,
                entity_id="entity-3",
                resolution_chosen=ResolutionKind.ABORT,
            ),
        ]

        run = service.create_with_resolutions_and_persist(
            format=SerializationFormat.SKOS,
            source_hash="abc123",
            scope=scope,
            resolutions=resolutions,
            interchange_repo=None,
        )

        assert len(run.resolutions) == 3
        for i, expected_res in enumerate(resolutions):
            assert run.resolutions[i].entity_id == expected_res.entity_id
            assert run.resolutions[i].match_kind == expected_res.match_kind
            assert run.resolutions[i].resolution_chosen == expected_res.resolution_chosen

    def test_create_with_different_formats(self):
        """create_with_resolutions_and_persist works with all SerializationFormats."""
        service = ImportRunService()
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)

        for format_type in [
            SerializationFormat.SKOS,
            SerializationFormat.OWL,
            SerializationFormat.GRAPHML,
        ]:
            run = service.create_with_resolutions_and_persist(
                format=format_type,
                source_hash=f"hash_{format_type.value}",
                scope=scope,
                interchange_repo=None,
            )

            assert run.format == format_type

    def test_create_with_different_scopes(self):
        """create_with_resolutions_and_persist works with different SerializationScopes."""
        service = ImportRunService()
        repo = FakeInterchangeRepository()

        # Whole graph scope
        scope_whole = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        run_whole = service.create_with_resolutions_and_persist(
            format=SerializationFormat.SKOS,
            source_hash="hash1",
            scope=scope_whole,
            interchange_repo=repo,
        )
        assert run_whole.scope.scope_type == SerializationScopeType.WHOLE_GRAPH

        # Taxonomy scope
        scope_tax = SerializationScope(
            scope_type=SerializationScopeType.TAXONOMY,
            taxonomy_id="tax-1",
        )
        run_tax = service.create_with_resolutions_and_persist(
            format=SerializationFormat.SKOS,
            source_hash="hash2",
            scope=scope_tax,
            interchange_repo=repo,
        )
        assert run_tax.scope.scope_type == SerializationScopeType.TAXONOMY
        assert run_tax.scope.taxonomy_id == "tax-1"
