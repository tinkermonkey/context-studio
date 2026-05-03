"""
Integration tests for SQLiteInterchangeRepository.

Tests round-trip persistence of ImportRun entities.
"""

import sys
import os
import uuid
from datetime import datetime, timezone

import pytest
import sqlalchemy
from sqlalchemy.orm import sessionmaker

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.interchange_repo import SQLiteInterchangeRepository
from domain.interchange.entities import (
    ImportRun,
    ImportRunStatus,
)
from domain.interchange.value_objects import (
    SerializationScope,
    SerializationScopeType,
    MatchKind,
    ResolutionKind,
)


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite database for testing."""
    engine = sqlalchemy.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session_factory(db_engine):
    """Create a session factory."""
    return sessionmaker(bind=db_engine)


@pytest.fixture
def repository(session_factory):
    """Create a repository."""
    return SQLiteInterchangeRepository(session_factory)


class TestImportRunPersistence:
    """Test round-trip persistence of ImportRun entities."""

    def test_create_and_get(self, repository):
        """Can create and retrieve an ImportRun."""
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        import_run = ImportRun(
            id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc),
            created_by="user-1",
            format="skos",
            source_uri="test.skos",
            source_hash="abc123def456",
            scope=scope,
        )

        repository.create(import_run)
        retrieved = repository.get(import_run.id)

        assert retrieved is not None
        assert retrieved.id == import_run.id
        assert retrieved.format == "skos"
        assert retrieved.source_uri == "test.skos"
        assert retrieved.status == ImportRunStatus.PENDING

    def test_persist_taxonomy_scope(self, repository):
        """Can persist ImportRun with TAXONOMY scope."""
        scope = SerializationScope(
            scope_type=SerializationScopeType.TAXONOMY,
            taxonomy_id="tax-1",
        )
        import_run = ImportRun(
            id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc),
            created_by="user-1",
            format="owl",
            source_uri="test.owl",
            source_hash="xyz789",
            scope=scope,
        )

        repository.create(import_run)
        retrieved = repository.get(import_run.id)

        assert retrieved.scope.scope_type == SerializationScopeType.TAXONOMY
        assert retrieved.scope.taxonomy_id == "tax-1"

    def test_persist_scheme_scope_with_descendants(self, repository):
        """Can persist ImportRun with SCHEME scope and descendants flag."""
        scope = SerializationScope(
            scope_type=SerializationScopeType.SCHEME,
            scheme_id="scheme-1",
            include_descendants=True,
        )
        import_run = ImportRun(
            id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc),
            created_by="user-1",
            format="graphml",
            source_uri="test.graphml",
            source_hash="uvw123",
            scope=scope,
        )

        repository.create(import_run)
        retrieved = repository.get(import_run.id)

        assert retrieved.scope.scope_type == SerializationScopeType.SCHEME
        assert retrieved.scope.scheme_id == "scheme-1"
        assert retrieved.scope.include_descendants is True

    def test_persist_entity_set_scope(self, repository):
        """Can persist ImportRun with ENTITY_SET scope."""
        entity_ids = ("entity-1", "entity-2", "entity-3")
        scope = SerializationScope(
            scope_type=SerializationScopeType.ENTITY_SET,
            entity_ids=entity_ids,
        )
        import_run = ImportRun(
            id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc),
            created_by="user-1",
            format="skos",
            source_uri="subset.skos",
            source_hash="pqr456",
            scope=scope,
        )

        repository.create(import_run)
        retrieved = repository.get(import_run.id)

        assert retrieved.scope.scope_type == SerializationScopeType.ENTITY_SET
        assert retrieved.scope.entity_ids == entity_ids

    def test_persist_resolutions(self, repository):
        """Can persist ImportRun with resolutions."""
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        import_run = ImportRun(
            id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc),
            created_by="user-1",
            format="skos",
            source_uri="test.skos",
            source_hash="abc123",
            scope=scope,
        )

        import_run.add_resolution(
            MatchKind.EXTERNAL_REFERENCE, "entity-1", ResolutionKind.MERGE
        )
        import_run.add_resolution(MatchKind.TITLE, "entity-2", ResolutionKind.SKIP)

        repository.create(import_run)
        retrieved = repository.get(import_run.id)

        assert len(retrieved.resolutions) == 2
        assert retrieved.resolutions[0].match_kind == MatchKind.EXTERNAL_REFERENCE
        assert retrieved.resolutions[0].entity_id == "entity-1"
        assert retrieved.resolutions[0].resolution_chosen == ResolutionKind.MERGE
        assert retrieved.resolutions[1].match_kind == MatchKind.TITLE
        assert retrieved.resolutions[1].entity_id == "entity-2"
        assert retrieved.resolutions[1].resolution_chosen == ResolutionKind.SKIP

    def test_persist_affected_entity_ids(self, repository):
        """Can persist ImportRun with affected entity IDs."""
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        import_run = ImportRun(
            id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc),
            created_by="user-1",
            format="skos",
            source_uri="test.skos",
            source_hash="abc123",
            scope=scope,
        )

        import_run.add_affected_entity("entity-1")
        import_run.add_affected_entity("entity-2")
        import_run.add_affected_entity("entity-3")

        repository.create(import_run)
        retrieved = repository.get(import_run.id)

        assert len(retrieved.affected_entity_ids) == 3
        assert "entity-1" in retrieved.affected_entity_ids
        assert "entity-2" in retrieved.affected_entity_ids
        assert "entity-3" in retrieved.affected_entity_ids

    def test_update_status(self, repository):
        """Can update ImportRun status."""
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        import_run = ImportRun(
            id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc),
            created_by="user-1",
            format="skos",
            source_uri="test.skos",
            source_hash="abc123",
            scope=scope,
        )

        repository.create(import_run)

        import_run.mark_committed()
        repository.update(import_run)

        retrieved = repository.get(import_run.id)
        assert retrieved.status == ImportRunStatus.COMMITTED

    def test_list_all(self, repository):
        """Can list all ImportRuns."""
        for i in range(3):
            scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
            import_run = ImportRun(
                id=str(uuid.uuid4()),
                created_at=datetime.now(timezone.utc),
                created_by=f"user-{i}",
                format="skos",
                source_uri=f"test-{i}.skos",
                source_hash=f"hash-{i}",
                scope=scope,
            )
            repository.create(import_run)

        runs = repository.list_all(limit=10)
        assert len(runs) == 3

    def test_list_by_status_pending(self, repository):
        """Can list ImportRuns filtered by PENDING status."""
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)

        pending_run = ImportRun(
            id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc),
            created_by="user-1",
            format="skos",
            source_uri="pending.skos",
            source_hash="hash-1",
            scope=scope,
            status=ImportRunStatus.PENDING,
        )

        committed_run = ImportRun(
            id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc),
            created_by="user-2",
            format="skos",
            source_uri="committed.skos",
            source_hash="hash-2",
            scope=scope,
            status=ImportRunStatus.COMMITTED,
        )

        repository.create(pending_run)
        repository.create(committed_run)

        pending_runs = repository.list_by_status(ImportRunStatus.PENDING)
        assert len(pending_runs) == 1
        assert pending_runs[0].id == pending_run.id

    def test_list_by_status_committed(self, repository):
        """Can list ImportRuns filtered by COMMITTED status."""
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)

        pending_run = ImportRun(
            id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc),
            created_by="user-1",
            format="skos",
            source_uri="pending.skos",
            source_hash="hash-1",
            scope=scope,
            status=ImportRunStatus.PENDING,
        )

        committed_run = ImportRun(
            id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc),
            created_by="user-2",
            format="skos",
            source_uri="committed.skos",
            source_hash="hash-2",
            scope=scope,
            status=ImportRunStatus.COMMITTED,
        )

        repository.create(pending_run)
        repository.create(committed_run)

        committed_runs = repository.list_by_status(ImportRunStatus.COMMITTED)
        assert len(committed_runs) == 1
        assert committed_runs[0].id == committed_run.id

    def test_get_nonexistent_returns_none(self, repository):
        """Getting a nonexistent ImportRun returns None."""
        result = repository.get("nonexistent-id")
        assert result is None

    def test_cannot_commit_failed_run(self):
        """Cannot transition a FAILED run to COMMITTED."""
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        import_run = ImportRun(
            id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc),
            created_by="user-1",
            format="skos",
            source_uri="test.skos",
            source_hash="abc123",
            scope=scope,
        )

        # Mark as failed
        import_run.mark_failed()
        assert import_run.status == ImportRunStatus.FAILED

        # Try to commit failed run — should raise
        with pytest.raises(ValueError, match="Cannot transition.*FAILED.*to COMMITTED"):
            import_run.mark_committed()
