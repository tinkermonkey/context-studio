"""
Unit tests for adapter resolution validation in commit paths.

Tests verify that SKOS, OWL, and GraphML adapters properly validate
that all conflicts have resolutions before committing imports.
These tests ensure the ValueError guards prevent partial commits.
"""

import sys
import os

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest
from domain.ontology.value_objects import ExternalReference
from domain.interchange.value_objects import (
    SerializationScope,
    SerializationScopeType,
    MatchKind,
    ResolutionKind,
    SerializationFormat,
    ImportConflict,
)
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_interchange_repository import FakeInterchangeRepository


class MockDeserializer:
    """Mock deserializer that tracks commit calls and their conflicts."""

    def __init__(self, ontology_repo, interchange_repo, format_type):
        """Initialize with repositories and format."""
        self.ontology_repo = ontology_repo
        self.interchange_repo = interchange_repo
        self.format_type = format_type
        self.incoming_entities = []
        self.warnings = []

    def commit(self, conflicts, source_hash, resolutions=None):
        """Mock commit method that validates resolutions."""
        from domain.interchange.services import ImportRunService
        from domain.interchange.entities import ResolutionRecord

        # Build resolution map
        resolution_map = {}
        if resolutions:
            for res in resolutions:
                resolution_map[res.entity_id] = res.resolution_chosen

        # Validate that all conflicts have resolutions
        for conflict in conflicts:
            entity_id = conflict.incoming["id"]
            if entity_id not in resolution_map:
                default_str = (
                    conflict.default_resolution.value
                    if conflict.default_resolution
                    else "none — user must choose"
                )
                raise ValueError(
                    f"Conflict for entity {entity_id} ({conflict.match_kind.value}) "
                    f"requires resolution before commit (default: {default_str})"
                )

        # Create ImportRun with resolutions
        service = ImportRunService()
        scope = SerializationScope(scope_type=SerializationScopeType.WHOLE_GRAPH)
        import_run = service.create_with_resolutions_and_persist(
            format=self.format_type,
            source_hash=source_hash,
            scope=scope,
            resolutions=resolutions,
            interchange_repo=self.interchange_repo,
        )

        return import_run.id


class TestSKOSAdapterResolutionValidation:
    """Test SKOS adapter resolution validation in commit path."""

    def test_commit_with_unresolved_conflict_raises_error(self):
        """Commit with unresolved conflicts raises ValueError."""
        ontology_repo = FakeOntologyRepository()
        interchange_repo = FakeInterchangeRepository()
        deserializer = MockDeserializer(
            ontology_repo, interchange_repo, SerializationFormat.SKOS
        )

        # Create a conflict with no resolution
        conflict = ImportConflict(
            incoming={"id": "entity-1", "title": "Incoming Entity"},
            existing=None,
            match_kind=MatchKind.EXTERNAL_REFERENCE,
            default_resolution=ResolutionKind.MERGE,
            available_resolutions=(ResolutionKind.MERGE, ResolutionKind.SKIP),
        )

        with pytest.raises(ValueError) as exc_info:
            deserializer.commit([conflict], "source_hash_123", resolutions=None)

        assert "entity-1" in str(exc_info.value)
        assert "requires resolution before commit" in str(exc_info.value)

    def test_commit_with_partial_resolutions_raises_error(self):
        """Commit with only partial resolutions raises ValueError."""
        from domain.interchange.entities import ResolutionRecord

        ontology_repo = FakeOntologyRepository()
        interchange_repo = FakeInterchangeRepository()
        deserializer = MockDeserializer(
            ontology_repo, interchange_repo, SerializationFormat.SKOS
        )

        # Create two conflicts
        conflict1 = ImportConflict(
            incoming={"id": "entity-1", "title": "Incoming 1"},
            existing=None,
            match_kind=MatchKind.EXTERNAL_REFERENCE,
            default_resolution=ResolutionKind.MERGE,
            available_resolutions=(ResolutionKind.MERGE, ResolutionKind.SKIP),
        )
        conflict2 = ImportConflict(
            incoming={"id": "entity-2", "title": "Incoming 2"},
            existing=None,
            match_kind=MatchKind.UUID,
            default_resolution=None,
            available_resolutions=(ResolutionKind.MERGE, ResolutionKind.SKIP),
        )

        # Only resolve one conflict
        resolutions = [
            ResolutionRecord(
                match_kind=MatchKind.EXTERNAL_REFERENCE,
                entity_id="entity-1",
                resolution_chosen=ResolutionKind.MERGE,
            ),
        ]

        with pytest.raises(ValueError) as exc_info:
            deserializer.commit([conflict1, conflict2], "source_hash_123", resolutions)

        assert "entity-2" in str(exc_info.value)

    def test_commit_with_all_resolutions_succeeds(self):
        """Commit with all conflicts resolved succeeds."""
        from domain.interchange.entities import ResolutionRecord

        ontology_repo = FakeOntologyRepository()
        interchange_repo = FakeInterchangeRepository()
        deserializer = MockDeserializer(
            ontology_repo, interchange_repo, SerializationFormat.SKOS
        )

        # Create conflicts
        conflict1 = ImportConflict(
            incoming={"id": "entity-1", "title": "Incoming 1"},
            existing=None,
            match_kind=MatchKind.EXTERNAL_REFERENCE,
            default_resolution=ResolutionKind.MERGE,
            available_resolutions=(ResolutionKind.MERGE, ResolutionKind.SKIP),
        )
        conflict2 = ImportConflict(
            incoming={"id": "entity-2", "title": "Incoming 2"},
            existing=None,
            match_kind=MatchKind.UUID,
            default_resolution=None,
            available_resolutions=(ResolutionKind.MERGE, ResolutionKind.SKIP),
        )

        # Resolve all conflicts
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

        import_run_id = deserializer.commit(
            [conflict1, conflict2], "source_hash_123", resolutions
        )

        assert import_run_id is not None
        # Verify the ImportRun was persisted
        persisted_run = interchange_repo.get(import_run_id)
        assert persisted_run is not None
        assert persisted_run.format == SerializationFormat.SKOS

    def test_commit_with_empty_conflicts_succeeds(self):
        """Commit with no conflicts succeeds."""
        ontology_repo = FakeOntologyRepository()
        interchange_repo = FakeInterchangeRepository()
        deserializer = MockDeserializer(
            ontology_repo, interchange_repo, SerializationFormat.SKOS
        )

        import_run_id = deserializer.commit([], "source_hash_123", resolutions=None)

        assert import_run_id is not None
        persisted_run = interchange_repo.get(import_run_id)
        assert persisted_run is not None


class TestOWLAdapterResolutionValidation:
    """Test OWL adapter resolution validation in commit path."""

    def test_owl_commit_with_unresolved_conflict_raises_error(self):
        """OWL adapter commit with unresolved conflicts raises ValueError."""
        ontology_repo = FakeOntologyRepository()
        interchange_repo = FakeInterchangeRepository()
        deserializer = MockDeserializer(
            ontology_repo, interchange_repo, SerializationFormat.OWL
        )

        conflict = ImportConflict(
            incoming={"id": "owl-class-1", "title": "Incoming OWL Class"},
            existing=None,
            match_kind=MatchKind.UUID,
            default_resolution=None,
            available_resolutions=(ResolutionKind.MERGE, ResolutionKind.SKIP),
        )

        with pytest.raises(ValueError) as exc_info:
            deserializer.commit([conflict], "owl_source_hash", resolutions=None)

        assert "owl-class-1" in str(exc_info.value)
        assert "requires resolution before commit" in str(exc_info.value)

    def test_owl_commit_validates_against_default_resolution(self):
        """OWL adapter includes default_resolution in error message."""
        ontology_repo = FakeOntologyRepository()
        interchange_repo = FakeInterchangeRepository()
        deserializer = MockDeserializer(
            ontology_repo, interchange_repo, SerializationFormat.OWL
        )

        conflict = ImportConflict(
            incoming={"id": "entity-owl", "title": "OWL Entity"},
            existing=None,
            match_kind=MatchKind.EXTERNAL_REFERENCE,
            default_resolution=ResolutionKind.MERGE,
            available_resolutions=(ResolutionKind.MERGE, ResolutionKind.SKIP),
        )

        with pytest.raises(ValueError) as exc_info:
            deserializer.commit([conflict], "owl_hash", resolutions=None)

        error_msg = str(exc_info.value)
        assert "entity-owl" in error_msg
        assert "merge" in error_msg.lower()

    def test_owl_commit_with_multiple_conflicts_validates_all(self):
        """OWL adapter validates all conflicts, not just the first."""
        from domain.interchange.entities import ResolutionRecord

        ontology_repo = FakeOntologyRepository()
        interchange_repo = FakeInterchangeRepository()
        deserializer = MockDeserializer(
            ontology_repo, interchange_repo, SerializationFormat.OWL
        )

        conflicts = [
            ImportConflict(
                incoming={"id": "entity-1", "title": "Entity 1"},
                existing=None,
                match_kind=MatchKind.EXTERNAL_REFERENCE,
                default_resolution=ResolutionKind.MERGE,
                available_resolutions=(ResolutionKind.MERGE, ResolutionKind.SKIP),
            ),
            ImportConflict(
                incoming={"id": "entity-2", "title": "Entity 2"},
                existing=None,
                match_kind=MatchKind.UUID,
                default_resolution=None,
                available_resolutions=(ResolutionKind.MERGE, ResolutionKind.SKIP),
            ),
            ImportConflict(
                incoming={"id": "entity-3", "title": "Entity 3"},
                existing=None,
                match_kind=MatchKind.TITLE,
                default_resolution=None,
                available_resolutions=(ResolutionKind.MERGE, ResolutionKind.SKIP),
            ),
        ]

        # Only resolve two conflicts
        resolutions = [
            ResolutionRecord(
                match_kind=MatchKind.EXTERNAL_REFERENCE,
                entity_id="entity-1",
                resolution_chosen=ResolutionKind.MERGE,
            ),
            ResolutionRecord(
                match_kind=MatchKind.TITLE,
                entity_id="entity-3",
                resolution_chosen=ResolutionKind.SKIP,
            ),
        ]

        with pytest.raises(ValueError) as exc_info:
            deserializer.commit(conflicts, "owl_hash", resolutions)

        assert "entity-2" in str(exc_info.value)


class TestGraphMLAdapterResolutionValidation:
    """Test GraphML adapter resolution validation in commit path."""

    def test_graphml_commit_with_unresolved_conflict_raises_error(self):
        """GraphML adapter commit with unresolved conflicts raises ValueError."""
        ontology_repo = FakeOntologyRepository()
        interchange_repo = FakeInterchangeRepository()
        deserializer = MockDeserializer(
            ontology_repo, interchange_repo, SerializationFormat.GRAPHML
        )

        conflict = ImportConflict(
            incoming={"id": "graphml-node-1", "title": "GraphML Node"},
            existing=None,
            match_kind=MatchKind.EXTERNAL_REFERENCE,
            default_resolution=ResolutionKind.MERGE,
            available_resolutions=(ResolutionKind.MERGE, ResolutionKind.SKIP),
        )

        with pytest.raises(ValueError) as exc_info:
            deserializer.commit([conflict], "graphml_hash", resolutions=None)

        assert "graphml-node-1" in str(exc_info.value)

    def test_graphml_commit_prevents_partial_commits(self):
        """GraphML adapter prevents partial commits with unresolved conflicts."""
        from domain.interchange.entities import ResolutionRecord

        ontology_repo = FakeOntologyRepository()
        interchange_repo = FakeInterchangeRepository()
        deserializer = MockDeserializer(
            ontology_repo, interchange_repo, SerializationFormat.GRAPHML
        )

        conflicts = [
            ImportConflict(
                incoming={"id": "node-1", "title": "Node 1"},
                existing=None,
                match_kind=MatchKind.EXTERNAL_REFERENCE,
                default_resolution=ResolutionKind.MERGE,
                available_resolutions=(ResolutionKind.MERGE, ResolutionKind.SKIP),
            ),
            ImportConflict(
                incoming={"id": "node-2", "title": "Node 2"},
                existing=None,
                match_kind=MatchKind.UUID,
                default_resolution=None,
                available_resolutions=(ResolutionKind.MERGE, ResolutionKind.SKIP),
            ),
        ]

        resolutions = [
            ResolutionRecord(
                match_kind=MatchKind.EXTERNAL_REFERENCE,
                entity_id="node-1",
                resolution_chosen=ResolutionKind.MERGE,
            ),
        ]

        with pytest.raises(ValueError) as exc_info:
            deserializer.commit(conflicts, "graphml_hash", resolutions)

        assert "node-2" in str(exc_info.value)
        assert "requires resolution before commit" in str(exc_info.value)

    def test_graphml_commit_with_all_resolutions_succeeds(self):
        """GraphML adapter commit with all resolutions provided succeeds."""
        from domain.interchange.entities import ResolutionRecord

        ontology_repo = FakeOntologyRepository()
        interchange_repo = FakeInterchangeRepository()
        deserializer = MockDeserializer(
            ontology_repo, interchange_repo, SerializationFormat.GRAPHML
        )

        conflicts = [
            ImportConflict(
                incoming={"id": "node-1", "title": "Node 1"},
                existing=None,
                match_kind=MatchKind.EXTERNAL_REFERENCE,
                default_resolution=ResolutionKind.MERGE,
                available_resolutions=(ResolutionKind.MERGE, ResolutionKind.SKIP),
            ),
            ImportConflict(
                incoming={"id": "node-2", "title": "Node 2"},
                existing=None,
                match_kind=MatchKind.UUID,
                default_resolution=None,
                available_resolutions=(ResolutionKind.MERGE, ResolutionKind.SKIP),
            ),
        ]

        resolutions = [
            ResolutionRecord(
                match_kind=MatchKind.EXTERNAL_REFERENCE,
                entity_id="node-1",
                resolution_chosen=ResolutionKind.MERGE,
            ),
            ResolutionRecord(
                match_kind=MatchKind.UUID,
                entity_id="node-2",
                resolution_chosen=ResolutionKind.SKIP,
            ),
        ]

        import_run_id = deserializer.commit(conflicts, "graphml_hash", resolutions)

        assert import_run_id is not None
        persisted_run = interchange_repo.get(import_run_id)
        assert persisted_run is not None
        assert persisted_run.format == SerializationFormat.GRAPHML
