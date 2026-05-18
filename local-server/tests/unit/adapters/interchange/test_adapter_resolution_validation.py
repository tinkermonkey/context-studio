"""
Unit tests for adapter resolution validation in commit paths.

Tests verify that SKOS, OWL, and GraphML adapters properly validate
that all conflicts have resolutions before committing imports.
These tests ensure the ValueError guards prevent partial commits.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from adapters.interchange.graphml import GraphMLDeserializer
from adapters.interchange.owl import OWLDeserializer
from adapters.interchange.skos import SKOSDeserializer
from domain.interchange.entities import ResolutionRecord
from domain.interchange.value_objects import (
    ImportConflict,
    MatchKind,
    ResolutionKind,
    SerializationFormat,
)
from tests.fakes.fake_interchange_repository import FakeInterchangeRepository
from tests.fakes.fake_ontology_repository import FakeOntologyRepository


class TestSKOSAdapterResolutionValidation:
    """Test SKOS adapter resolution validation in commit path."""

    def test_commit_with_unresolved_conflict_raises_error(self):
        """Real SKOS adapter raises ValueError when conflicts lack resolutions."""
        ontology_repo = FakeOntologyRepository()
        interchange_repo = FakeInterchangeRepository()
        deserializer = SKOSDeserializer(ontology_repo, interchange_repo)

        # Manually set up incoming entities and conflicts
        deserializer.incoming_entities = {
            "entity-1": {"id": "entity-1", "title": "Test Entity"},
        }

        # Create a conflict
        conflict = ImportConflict(
            incoming={"id": "entity-1", "title": "Test Entity"},
            existing=None,
            match_kind=MatchKind.EXTERNAL_REFERENCE,
            default_resolution=ResolutionKind.MERGE,
            available_resolutions=(ResolutionKind.MERGE, ResolutionKind.SKIP),
        )

        # Try to commit without resolutions - should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            deserializer._commit_with_resolutions(
                conflicts=[conflict],
                source_hash="hash123",
                resolutions=None,
            )

        error_msg = str(exc_info.value)
        assert "entity-1" in error_msg
        assert "requires resolution before commit" in error_msg

    def test_commit_with_partial_resolutions_raises_error(self):
        """Real SKOS adapter raises ValueError with only partial resolutions."""
        ontology_repo = FakeOntologyRepository()
        interchange_repo = FakeInterchangeRepository()
        deserializer = SKOSDeserializer(ontology_repo, interchange_repo)

        # Set up multiple incoming entities
        deserializer.incoming_entities = {
            "entity-1": {"id": "entity-1", "title": "Entity 1"},
            "entity-2": {"id": "entity-2", "title": "Entity 2"},
        }

        # Create two conflicts
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
        ]

        # Only resolve first conflict
        resolutions = [
            ResolutionRecord(
                match_kind=MatchKind.EXTERNAL_REFERENCE,
                entity_id="entity-1",
                resolution_chosen=ResolutionKind.MERGE,
            ),
        ]

        # Should raise ValueError because entity-2 is unresolved
        with pytest.raises(ValueError) as exc_info:
            deserializer._commit_with_resolutions(
                conflicts=conflicts,
                source_hash="hash123",
                resolutions=resolutions,
            )

        error_msg = str(exc_info.value)
        assert "entity-2" in error_msg
        assert "requires resolution before commit" in error_msg

    def test_commit_with_all_resolutions_succeeds(self):
        """Real SKOS adapter commits successfully with all conflicts resolved."""
        ontology_repo = FakeOntologyRepository()
        interchange_repo = FakeInterchangeRepository()
        deserializer = SKOSDeserializer(ontology_repo, interchange_repo)

        # Set up incoming entities
        deserializer.incoming_entities = {
            "entity-1": {"id": "entity-1", "title": "Entity 1"},
            "entity-2": {"id": "entity-2", "title": "Entity 2"},
        }

        # Create conflicts
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
        ]

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

        # Should succeed
        import_run_id = deserializer._commit_with_resolutions(
            conflicts=conflicts,
            source_hash="hash123",
            resolutions=resolutions,
        )

        assert import_run_id is not None
        # Verify persistence
        persisted_run = interchange_repo.get(import_run_id)
        assert persisted_run is not None
        assert persisted_run.format == SerializationFormat.SKOS

    def test_commit_with_empty_conflicts_succeeds(self):
        """Real SKOS adapter commits successfully with no conflicts."""
        ontology_repo = FakeOntologyRepository()
        interchange_repo = FakeInterchangeRepository()
        deserializer = SKOSDeserializer(ontology_repo, interchange_repo)

        deserializer.incoming_entities = {}

        # Commit with no conflicts and no resolutions needed
        import_run_id = deserializer._commit_with_resolutions(
            conflicts=[],
            source_hash="hash123",
            resolutions=None,
        )

        assert import_run_id is not None
        persisted_run = interchange_repo.get(import_run_id)
        assert persisted_run is not None


class TestOWLAdapterResolutionValidation:
    """Test OWL adapter resolution validation in commit path."""

    def test_owl_commit_with_unresolved_conflict_raises_error(self):
        """Real OWL adapter raises ValueError with unresolved conflicts."""
        ontology_repo = FakeOntologyRepository()
        interchange_repo = FakeInterchangeRepository()
        deserializer = OWLDeserializer(ontology_repo, interchange_repo)

        deserializer.incoming_entities = {
            "owl-class-1": {"id": "owl-class-1", "title": "OWL Class"},
        }

        conflict = ImportConflict(
            incoming={"id": "owl-class-1", "title": "OWL Class"},
            existing=None,
            match_kind=MatchKind.UUID,
            default_resolution=None,
            available_resolutions=(ResolutionKind.MERGE, ResolutionKind.SKIP),
        )

        with pytest.raises(ValueError) as exc_info:
            deserializer._commit_with_resolutions(
                conflicts=[conflict],
                source_hash="owl_hash",
                resolutions=None,
            )

        error_msg = str(exc_info.value)
        assert "owl-class-1" in error_msg
        assert "requires resolution before commit" in error_msg

    def test_owl_commit_validates_all_conflicts(self):
        """Real OWL adapter validates all conflicts, not just the first."""
        ontology_repo = FakeOntologyRepository()
        interchange_repo = FakeInterchangeRepository()
        deserializer = OWLDeserializer(ontology_repo, interchange_repo)

        # Create entities for multiple conflicts
        deserializer.incoming_entities = {
            "entity-1": {"id": "entity-1", "title": "Entity 1"},
            "entity-2": {"id": "entity-2", "title": "Entity 2"},
            "entity-3": {"id": "entity-3", "title": "Entity 3"},
        }

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

        # Only resolve first and third
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

        # Should fail because entity-2 is unresolved
        with pytest.raises(ValueError) as exc_info:
            deserializer._commit_with_resolutions(
                conflicts=conflicts,
                source_hash="owl_hash",
                resolutions=resolutions,
            )

        error_msg = str(exc_info.value)
        assert "entity-2" in error_msg
        assert "requires resolution before commit" in error_msg


class TestGraphMLAdapterResolutionValidation:
    """Test GraphML adapter resolution validation in commit path."""

    def test_graphml_commit_with_unresolved_conflict_raises_error(self):
        """Real GraphML adapter raises ValueError with unresolved conflicts."""
        ontology_repo = FakeOntologyRepository()
        interchange_repo = FakeInterchangeRepository()
        deserializer = GraphMLDeserializer(ontology_repo, interchange_repo)

        deserializer.incoming_entities = {
            "graphml-node-1": {"id": "graphml-node-1", "title": "GraphML Node"},
        }

        conflict = ImportConflict(
            incoming={"id": "graphml-node-1", "title": "GraphML Node"},
            existing=None,
            match_kind=MatchKind.EXTERNAL_REFERENCE,
            default_resolution=ResolutionKind.MERGE,
            available_resolutions=(ResolutionKind.MERGE, ResolutionKind.SKIP),
        )

        with pytest.raises(ValueError) as exc_info:
            deserializer._commit_with_resolutions(
                conflicts=[conflict],
                source_hash="graphml_hash",
                resolutions=None,
            )

        error_msg = str(exc_info.value)
        assert "graphml-node-1" in error_msg
        assert "requires resolution before commit" in error_msg

    def test_graphml_commit_prevents_partial_commits(self):
        """Real GraphML adapter prevents partial commits with unresolved conflicts."""
        ontology_repo = FakeOntologyRepository()
        interchange_repo = FakeInterchangeRepository()
        deserializer = GraphMLDeserializer(ontology_repo, interchange_repo)

        deserializer.incoming_entities = {
            "node-1": {"id": "node-1", "title": "Node 1"},
            "node-2": {"id": "node-2", "title": "Node 2"},
        }

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
            deserializer._commit_with_resolutions(
                conflicts=conflicts,
                source_hash="graphml_hash",
                resolutions=resolutions,
            )

        error_msg = str(exc_info.value)
        assert "node-2" in error_msg
        assert "requires resolution before commit" in error_msg

    def test_graphml_commit_with_all_resolutions_succeeds(self):
        """Real GraphML adapter commits successfully with all resolutions."""
        ontology_repo = FakeOntologyRepository()
        interchange_repo = FakeInterchangeRepository()
        deserializer = GraphMLDeserializer(ontology_repo, interchange_repo)

        deserializer.incoming_entities = {
            "node-1": {"id": "node-1", "title": "Node 1"},
            "node-2": {"id": "node-2", "title": "Node 2"},
        }

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

        import_run_id = deserializer._commit_with_resolutions(
            conflicts=conflicts,
            source_hash="graphml_hash",
            resolutions=resolutions,
        )

        assert import_run_id is not None
        persisted_run = interchange_repo.get(import_run_id)
        assert persisted_run is not None
        assert persisted_run.format == SerializationFormat.GRAPHML
