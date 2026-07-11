"""
Integration tests for the DR ontology import orchestration
(scripts/dr_ontology_loader.import_dr_ontology).

Exercises the full create-or-update flow against a real (in-memory) SQLite
database and a tiny synthetic DR spec fixture — not the actual
documentation_robotics checkout, which is an external dependency not
available in CI. Covers: row counts, idempotent re-import (no duplicates,
in-place updates), external reference / domain-range population, and the
schema_index=None embedding-suppression contract.
"""

import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.models import Base, OntologyEntity
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.schema_vector_index import SqliteSchemaVectorIndex
from domain.ontology.services import OntologyService
from scripts.dr_ontology_loader import import_dr_ontology
from tests.fakes.fake_embedding_service import FakeEmbeddingService


class _NoOpEventPublisher:
    def publish(self, event):  # noqa: ANN001, ARG002
        return []


def _write_manifest(spec_dir):
    dist_dir = spec_dir / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "specVersion": "0.8.4",
        "layers": [
            {
                "id": "motivation",
                "number": 1,
                "name": "Motivation Layer",
                "nodeTypeCount": 2,
                "relationshipCount": 1,
            },
            {
                "id": "business",
                "number": 2,
                "name": "Business Layer",
                "nodeTypeCount": 1,
                "relationshipCount": 1,
            },
        ],
    }
    (dist_dir / "manifest.json").write_text(json.dumps(manifest))


def _write_node_schema(spec_dir, layer, type_name, title, description):
    layer_dir = spec_dir / "schemas" / "nodes" / layer
    layer_dir.mkdir(parents=True, exist_ok=True)
    (layer_dir / f"{type_name}.node.schema.json").write_text(
        json.dumps(
            {
                "title": title,
                "description": description,
                "properties": {
                    "spec_node_id": {"const": f"{layer}.{type_name}"},
                    "layer_id": {"const": layer},
                    "type": {"const": type_name},
                },
            }
        )
    )


def _write_relationship_schema(
    spec_dir, source_layer, source_type, predicate, dest_layer, dest_type, title, description
):
    rel_dir = spec_dir / "schemas" / "relationships" / source_layer
    rel_dir.mkdir(parents=True, exist_ok=True)
    (rel_dir / f"{source_type}.{predicate}.{dest_type}.relationship.schema.json").write_text(
        json.dumps(
            {
                "title": title,
                "description": description,
                "properties": {
                    "source_spec_node_id": {"const": f"{source_layer}.{source_type}"},
                    "source_layer": {"const": source_layer},
                    "destination_spec_node_id": {"const": f"{dest_layer}.{dest_type}"},
                    "destination_layer": {"const": dest_layer},
                    "predicate": {"const": predicate},
                },
            }
        )
    )


@pytest.fixture
def spec_dir(tmp_path):
    """A tiny synthetic DR spec: 2 layers, 3 node types, 2 relationships (one cross-layer)."""
    _write_manifest(tmp_path)
    _write_node_schema(tmp_path, "motivation", "goal", "Goal", "High-level statement of intent")
    _write_node_schema(tmp_path, "motivation", "stakeholder", "Stakeholder", "A person or role")
    _write_node_schema(tmp_path, "business", "businessservice", "Business Service", "A service")
    _write_relationship_schema(
        tmp_path,
        "motivation",
        "stakeholder",
        "associated-with",
        "motivation",
        "goal",
        "Stakeholder associated-with Goal",
        "Defines relationship: motivation.stakeholder associated-with motivation.goal",
    )
    _write_relationship_schema(
        tmp_path,
        "motivation",
        "goal",
        "realizes",
        "business",
        "businessservice",
        "Goal realizes Business Service",
        "Defines relationship: motivation.goal realizes business.businessservice",
    )
    return tmp_path


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def repo(session_factory):
    return SQLiteOntologyRepository(session_factory)


@pytest.fixture
def ontology_service(repo):
    return OntologyService(
        repository=repo,
        embedding_service=FakeEmbeddingService(),
        event_publisher=_NoOpEventPublisher(),
        schema_index=None,
    )


class TestImportDrOntologyRowCounts:
    def test_produces_expected_row_counts(self, ontology_service, repo, spec_dir):
        summary = import_dr_ontology(ontology_service, repo, spec_dir)

        assert summary.spec_version == "0.8.4"
        assert summary.taxonomies_created == 1
        assert summary.concept_schemes_created == 2
        assert summary.classes_created == 3
        assert summary.property_definitions_created == 2
        assert summary.taxonomies_updated == 0
        assert summary.concept_schemes_updated == 0
        assert summary.classes_updated == 0
        assert summary.property_definitions_updated == 0

    def test_row_counts_match_database(self, ontology_service, repo, spec_dir, session_factory):
        import_dr_ontology(ontology_service, repo, spec_dir)

        with session_factory() as session:
            counts = {
                node_type: session.query(OntologyEntity)
                .filter(OntologyEntity.node_type == node_type)
                .count()
                for node_type in ("taxonomy", "concept_scheme", "class", "property_definition")
            }

        assert counts == {
            "taxonomy": 1,
            "concept_scheme": 2,
            "class": 3,
            "property_definition": 2,
        }


class TestImportDrOntologyExternalReferencesAndDomainRange:
    def test_class_external_reference_matches_spec_node_id(self, ontology_service, repo, spec_dir):
        import_dr_ontology(ontology_service, repo, spec_dir)

        goal_class = repo.get_by_identifier("motivation_goal")
        assert goal_class is not None
        assert len(goal_class.external_references) == 1
        assert goal_class.external_references[0].source == "documentation_robotics"
        assert goal_class.external_references[0].identifier == "motivation.goal"

    def test_property_definition_domain_range_and_full_identifier(
        self, ontology_service, repo, spec_dir
    ):
        import_dr_ontology(ontology_service, repo, spec_dir)

        goal_class = repo.get_by_identifier("motivation_goal")
        stakeholder_class = repo.get_by_identifier("motivation_stakeholder")
        assert goal_class is not None
        assert stakeholder_class is not None

        prop = repo.get_property_definition_by_identifier("stakeholder_associated_with_goal")
        assert prop is not None
        assert prop.domain_class_id == stakeholder_class.id
        assert prop.range_class_id == goal_class.id
        assert len(prop.external_references) == 1
        assert (
            prop.external_references[0].identifier
            == "motivation.stakeholder.associated-with.motivation.goal"
        )

    def test_cross_layer_relationship_resolves_domain_range_across_schemes(
        self, ontology_service, repo, spec_dir
    ):
        import_dr_ontology(ontology_service, repo, spec_dir)

        goal_class = repo.get_by_identifier("motivation_goal")
        service_class = repo.get_by_identifier("business_businessservice")

        prop = repo.get_property_definition_by_identifier("goal_realizes_businessservice")
        assert prop is not None
        assert prop.domain_class_id == goal_class.id
        assert prop.range_class_id == service_class.id


class TestImportDrOntologyIdempotency:
    def test_reimport_produces_no_duplicates(
        self, ontology_service, repo, spec_dir, session_factory
    ):
        import_dr_ontology(ontology_service, repo, spec_dir)
        second_summary = import_dr_ontology(ontology_service, repo, spec_dir)

        assert second_summary.taxonomies_created == 0
        assert second_summary.concept_schemes_created == 0
        assert second_summary.classes_created == 0
        assert second_summary.property_definitions_created == 0
        assert second_summary.taxonomies_updated == 1
        assert second_summary.concept_schemes_updated == 2
        assert second_summary.classes_updated == 3
        assert second_summary.property_definitions_updated == 2

        with session_factory() as session:
            total = session.query(OntologyEntity).count()
        # 1 taxonomy + 2 schemes + 3 classes + 2 property definitions
        assert total == 8

    def test_reimport_after_spec_change_updates_in_place(
        self, ontology_service, repo, spec_dir, session_factory
    ):
        import_dr_ontology(ontology_service, repo, spec_dir)

        # Simulate a spec version bump that only changes a node's description.
        goal_schema_path = spec_dir / "schemas" / "nodes" / "motivation" / "goal.node.schema.json"
        data = json.loads(goal_schema_path.read_text())
        data["description"] = "Updated description after spec bump"
        goal_schema_path.write_text(json.dumps(data))

        import_dr_ontology(ontology_service, repo, spec_dir)

        goal_class = repo.get_by_identifier("motivation_goal")
        assert goal_class.description == "Updated description after spec bump"

        with session_factory() as session:
            total = session.query(OntologyEntity).count()
        assert total == 8


class TestImportDrOntologySchemaIndexSuppression:
    def test_embeddings_not_synced_during_import_until_reindex_all(
        self, ontology_service, repo, spec_dir, session_factory
    ):
        import_dr_ontology(ontology_service, repo, spec_dir)

        with session_factory() as session:
            rows = (
                session.query(OntologyEntity)
                .filter(OntologyEntity.node_type.in_(("class", "property_definition")))
                .all()
            )
            assert all(row.title_embedding is None for row in rows)
            assert all(row.definition_embedding is None for row in rows)

        vector_index = SqliteSchemaVectorIndex(session_factory, FakeEmbeddingService())
        reindexed_count = vector_index.reindex_all()

        # 3 classes + 2 property definitions
        assert reindexed_count == 5

        with session_factory() as session:
            rows = (
                session.query(OntologyEntity)
                .filter(OntologyEntity.node_type.in_(("class", "property_definition")))
                .all()
            )
            assert all(row.title_embedding is not None for row in rows)


class TestImportDrOntologyMalformedSpec:
    def test_colliding_node_identifiers_raise(self, ontology_service, repo, spec_dir):
        # 'motivation.go_al' and 'motivation.go-al' both slugify to 'motivation_go_al'
        # ('.', '-' both map to '_').
        _write_node_schema(spec_dir, "motivation", "go_al", "Go Al", "A node type")
        _write_node_schema(spec_dir, "motivation", "go-al", "Go-Al", "A colliding node type")

        with pytest.raises(ValueError, match="collide"):
            import_dr_ontology(ontology_service, repo, spec_dir)

    def test_node_schema_with_unknown_layer_raises(self, ontology_service, repo, spec_dir):
        _write_node_schema(spec_dir, "unknown-layer", "widget", "Widget", "An orphan node type")

        with pytest.raises(ValueError, match="unknown-layer"):
            import_dr_ontology(ontology_service, repo, spec_dir)

    def test_relationship_referencing_missing_node_type_raises(
        self, ontology_service, repo, spec_dir
    ):
        _write_relationship_schema(
            spec_dir,
            "motivation",
            "nonexistent",
            "associated-with",
            "motivation",
            "goal",
            "Nonexistent associated-with Goal",
            "Defines relationship: motivation.nonexistent associated-with motivation.goal",
        )

        with pytest.raises(ValueError, match="nonexistent"):
            import_dr_ontology(ontology_service, repo, spec_dir)


class TestImportDrOntologyExternalReferencePreservation:
    def test_reimport_preserves_non_dr_external_reference_on_property_definition(
        self, ontology_service, repo, spec_dir
    ):
        from domain.ontology.value_objects import ExternalReference

        import_dr_ontology(ontology_service, repo, spec_dir)

        prop = repo.get_property_definition_by_identifier("stakeholder_associated_with_goal")
        prop.external_references.append(
            ExternalReference(source="manual", identifier="curated-ref-1")
        )
        repo.save_property_definition(prop)

        import_dr_ontology(ontology_service, repo, spec_dir)

        prop = repo.get_property_definition_by_identifier("stakeholder_associated_with_goal")
        sources = {ref.source for ref in prop.external_references}
        assert sources == {"documentation_robotics", "manual"}
