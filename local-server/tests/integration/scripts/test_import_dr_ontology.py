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
import subprocess
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.events.change_recorder import ChangeEventRecorder
from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.connection import create_local_db_engine
from adapters.persistence.sqlite.models import Base, OntologyEntity
from adapters.persistence.sqlite.models import ChangeEvent as ChangeEventORM
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.proposal_repo import SQLiteChangeProposalRepository
from adapters.persistence.sqlite.schema_vector_index import SqliteSchemaVectorIndex
from domain.ontology.services import OntologyService
from domain.ontology.value_objects import ExternalReference
from domain.versioning.proposal_service import OperationDraft, ProposalService
from domain.versioning.proposals import (
    ChangeProposal,
    OperationKind,
    OperationType,
    ProposalSource,
    ProposalStatus,
    ProposedOperation,
)
from domain.versioning.revert_service import RevertService
from scripts import import_dr_ontology as import_script
from scripts.dr_ontology_loader import (
    DR_SOURCE,
    DR_TAXONOMY_IDENTIFIER,
    PruneFailed,
    find_prune_blockers,
    import_dr_ontology,
    prune_stale,
)
from scripts.import_dr_ontology import report_and_prune
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
    spec_dir,
    source_layer,
    source_type,
    predicate,
    dest_layer,
    dest_type,
    title,
    description,
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
                node_type: (
                    session.query(OntologyEntity)
                    .filter(OntologyEntity.node_type == node_type)
                    .count()
                )
                for node_type in (
                    "taxonomy",
                    "concept_scheme",
                    "class",
                    "property_definition",
                )
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


REALIZES_SCHEMA = (
    "schemas/relationships/motivation/goal.realizes.businessservice.relationship.schema.json"
)


def _realizes_reference(repo):
    prop = repo.get_property_definition_by_identifier("goal_realizes_businessservice")
    return next(ref for ref in prop.external_references if ref.source == DR_SOURCE)


def _set_spec_attributes(spec_dir, cardinality=None, strength=None, evidence=None):
    """Give the realizes schema attributes, as DR's relationship schemas carry them."""
    path = spec_dir / REALIZES_SCHEMA
    data = json.loads(path.read_text())
    if cardinality:
        data["properties"]["cardinality"] = {"const": cardinality}
    if strength:
        data["properties"]["strength"] = {"const": strength}
    if evidence is None:
        data.pop("x-dr-evidence", None)
    else:
        data["x-dr-evidence"] = evidence
    path.write_text(json.dumps(data))


class TestRelationshipAttributes:
    """Cardinality, strength and x-dr-evidence ride on the DR reference's metadata (#1397)."""

    def test_import_stores_the_attributes_on_the_dr_reference(
        self, ontology_service, repo, spec_dir
    ):
        _set_spec_attributes(spec_dir, "many-to-many", "high", ["A goal names the service."])

        import_dr_ontology(ontology_service, repo, spec_dir)

        assert dict(_realizes_reference(repo).metadata) == {
            "cardinality": "many-to-many",
            "strength": "high",
            "evidence": ["A goal names the service."],
        }

    def test_a_schema_without_attributes_gets_no_metadata(self, ontology_service, repo, spec_dir):
        import_dr_ontology(ontology_service, repo, spec_dir)

        assert _realizes_reference(repo).metadata is None

    def test_reimporting_an_unchanged_spec_saves_no_property_definition(
        self, ontology_service, repo, spec_dir, monkeypatch
    ):
        _set_spec_attributes(spec_dir, "many-to-many", "medium", ["Evidence."])
        import_dr_ontology(ontology_service, repo, spec_dir)
        saves = []
        save = repo.save_property_definition
        monkeypatch.setattr(
            repo, "save_property_definition", lambda prop: saves.append(prop) or save(prop)
        )

        import_dr_ontology(ontology_service, repo, spec_dir)

        assert saves == []

    def test_a_changed_spec_updates_the_attributes_and_keeps_other_references(
        self, ontology_service, repo, spec_dir
    ):
        _set_spec_attributes(spec_dir, "many-to-many", "medium", ["Old evidence."])
        import_dr_ontology(ontology_service, repo, spec_dir)
        prop = repo.get_property_definition_by_identifier("goal_realizes_businessservice")
        prop.external_references.append(ExternalReference(source="manual", identifier="m-1"))
        repo.save_property_definition(prop)

        _set_spec_attributes(spec_dir, "one-to-many", "high")
        import_dr_ontology(ontology_service, repo, spec_dir)

        prop = repo.get_property_definition_by_identifier("goal_realizes_businessservice")
        assert [(r.source, r.identifier) for r in prop.external_references] == [
            (DR_SOURCE, "motivation.goal.realizes.business.businessservice"),
            ("manual", "m-1"),
        ]
        assert dict(_realizes_reference(repo).metadata) == {
            "cardinality": "one-to-many",
            "strength": "high",
        }

    def test_malformed_evidence_raises(self, ontology_service, repo, spec_dir):
        _set_spec_attributes(spec_dir, evidence="not a list")

        with pytest.raises(ValueError, match="x-dr-evidence"):
            import_dr_ontology(ontology_service, repo, spec_dir)


CHARTER = """# Documentation Robotics Design Charter

**Status:** Adopted.

## In one paragraph

Documentation Robotics models a software system
as a federated set of elements.

## What the specification is

The long form.
"""


class TestDesignCharterAndLayerIntent:
    """#1340: the charter becomes vision and summary; layer files give scope notes."""

    def test_charter_sets_vision_and_unwrapped_summary(self, ontology_service, repo, spec_dir):
        (spec_dir / "DESIGN_CHARTER.md").write_text(CHARTER)

        summary = import_dr_ontology(ontology_service, repo, spec_dir)

        taxonomy = repo.get_by_identifier("dr_spec")
        assert summary.charter_found is True
        assert taxonomy.vision == CHARTER
        assert taxonomy.description == (
            "Documentation Robotics models a software system as a federated set of elements."
        )

    def test_spec_without_charter_leaves_vision_and_summary_alone(
        self, ontology_service, repo, spec_dir
    ):
        (spec_dir / "DESIGN_CHARTER.md").write_text(CHARTER)
        import_dr_ontology(ontology_service, repo, spec_dir)
        (spec_dir / "DESIGN_CHARTER.md").unlink()

        summary = import_dr_ontology(ontology_service, repo, spec_dir)

        taxonomy = repo.get_by_identifier("dr_spec")
        assert summary.charter_found is False
        assert taxonomy.vision == CHARTER
        assert taxonomy.description.startswith("Documentation Robotics models")

    def test_layer_description_becomes_the_scheme_scope_note(
        self, ontology_service, repo, spec_dir
    ):
        layers = spec_dir / "layers"
        layers.mkdir()
        (layers / "01-motivation.layer.json").write_text(
            json.dumps({"id": "motivation", "description": "Captures why the system exists."})
        )

        import_dr_ontology(ontology_service, repo, spec_dir)

        assert repo.get_by_identifier("motivation").description == (
            "Captures why the system exists."
        )
        assert repo.get_by_identifier("business").description.startswith("DR spec layer")

    def test_entities_the_spec_dropped_are_reported_stale(self, ontology_service, repo, spec_dir):
        import_dr_ontology(ontology_service, repo, spec_dir)
        for path in (spec_dir / "schemas" / "relationships").rglob("*realizes*.json"):
            path.unlink()

        summary = import_dr_ontology(ontology_service, repo, spec_dir)

        assert len(summary.stale) == 1
        assert summary.stale[0].startswith("PropertyDefinition")
        assert "motivation.goal.realizes.business.businessservice" in summary.stale[0]


def _drop_spec_files(spec_dir, pattern):
    for path in (spec_dir / "schemas").rglob(pattern):
        path.unlink()


def _delete_event_count(session_factory):
    with session_factory() as session:
        return session.query(ChangeEventORM).filter(ChangeEventORM.operation == "delete").count()


def _realizes(repo):
    return next(p for p in repo.list_property_definitions(limit=None) if "realizes" in p.identifier)


@pytest.fixture
def recorded_service(repo, session_factory):
    """An OntologyService whose deletes are recorded as change events, as the script wires it."""
    publisher = InProcessEventPublisher()
    ChangeEventRecorder(SQLiteChangeRepository(session_factory)).subscribe_ontology_events(
        publisher
    )
    return OntologyService(
        repository=repo,
        embedding_service=FakeEmbeddingService(),
        event_publisher=publisher,
        schema_index=None,
    )


@pytest.fixture
def proposals(session_factory):
    return SQLiteChangeProposalRepository(session_factory)


class TestPruneStale:
    def test_prune_deletes_unused_stale_entities_and_records_the_deletes(
        self, ontology_service, recorded_service, repo, proposals, spec_dir, session_factory
    ):
        import_dr_ontology(ontology_service, repo, spec_dir)
        _drop_spec_files(spec_dir, "*realizes*.json")
        _drop_spec_files(spec_dir, "businessservice.node.schema.json")
        summary = import_dr_ontology(ontology_service, repo, spec_dir)
        stale_ids = {entity.id for entity in summary.stale_entities}
        assert len(stale_ids) == 2  # the realizes property and its range class

        assert report_and_prune(summary, recorded_service, repo, proposals, prune=True)

        assert repo.get_by_identifier("business_businessservice") is None
        assert not [p for p in repo.list_property_definitions(limit=None) if p.id in stale_ids]
        with session_factory() as session:
            deleted = {
                row.entity_id
                for row in session.query(ChangeEventORM).filter(
                    ChangeEventORM.entity_id.in_(stale_ids), ChangeEventORM.operation == "delete"
                )
            }
        assert deleted == stale_ids
        assert import_dr_ontology(ontology_service, repo, spec_dir).stale == []

    def test_prune_refuses_and_deletes_nothing_when_a_relationship_uses_a_stale_property(
        self, ontology_service, recorded_service, repo, proposals, spec_dir, session_factory, capsys
    ):
        import_dr_ontology(ontology_service, repo, spec_dir)
        goal = repo.get_by_identifier("motivation_goal")
        service_class = repo.get_by_identifier("business_businessservice")
        realizes = _realizes(repo)
        source = ontology_service.create_individual(goal.id, "Grow revenue")
        target = ontology_service.create_individual(service_class.id, "Billing")
        relationship = ontology_service.create_relationship(source.id, target.id, realizes.id)
        _drop_spec_files(spec_dir, "*realizes*.json")
        summary = import_dr_ontology(ontology_service, repo, spec_dir)

        blockers = find_prune_blockers(repo, proposals, summary.stale_entities)
        assert blockers == [(summary.stale[0], f"relationship {relationship.id}")]
        assert not report_and_prune(summary, recorded_service, repo, proposals, prune=True)

        assert repo.get_property_definition(realizes.id) is not None
        assert repo.get_relationship(relationship.id) is not None
        assert f"relationship {relationship.id}" in capsys.readouterr().err
        assert _delete_event_count(session_factory) == 0

    @pytest.mark.parametrize("use", ["subclass", "individual", "property_range"])
    def test_prune_refuses_when_something_outside_the_stale_set_uses_a_stale_class(
        self, ontology_service, recorded_service, repo, proposals, spec_dir, session_factory, use
    ):
        import_dr_ontology(ontology_service, repo, spec_dir)
        service_class = repo.get_by_identifier("business_businessservice")
        if use == "subclass":
            user = ontology_service.create_class(
                service_class.concept_scheme_id,
                "Internal Service",
                parent_class_id=service_class.id,
            )
        elif use == "individual":
            user = ontology_service.create_individual(service_class.id, "Billing")
        else:
            user = ontology_service.create_property_definition(
                identifier="hosts", title="Hosts", range_class_id=service_class.id
            )
        _drop_spec_files(spec_dir, "*realizes*.json")
        _drop_spec_files(spec_dir, "businessservice.node.schema.json")
        summary = import_dr_ontology(ontology_service, repo, spec_dir)
        assert len(summary.stale_entities) == 2  # the class and the stale property ranging over it

        blockers = find_prune_blockers(repo, proposals, summary.stale_entities)
        assert [user_desc.split()[-1] for _, user_desc in blockers] == [user.id]
        assert blockers[0][0].startswith("Class 'Business Service'")
        assert not report_and_prune(summary, recorded_service, repo, proposals, prune=True)

        assert all(
            repo.get_class(e.id) or repo.get_property_definition(e.id)
            for e in summary.stale_entities
        )
        assert _delete_event_count(session_factory) == 0

    def test_prune_refuses_when_an_open_proposal_operation_names_a_stale_entity(
        self, ontology_service, recorded_service, repo, proposals, spec_dir
    ):
        import_dr_ontology(ontology_service, repo, spec_dir)
        realizes = _realizes(repo)
        proposal = proposals.create(
            ChangeProposal(
                id=str(uuid4()),
                taxonomy_id=repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER).id,
                title="Retitle realizes",
                source=ProposalSource.USER,
                created_at=datetime.now(timezone.utc),
                operations=[
                    ProposedOperation(
                        seq=1,
                        op=OperationType.UPDATE,
                        kind=OperationKind.PROPERTY,
                        target_id=realizes.id,
                        fields={"title": "Delivers"},
                    )
                ],
            )
        )
        _drop_spec_files(spec_dir, "*realizes*.json")
        summary = import_dr_ontology(ontology_service, repo, spec_dir)

        blockers = find_prune_blockers(repo, proposals, summary.stale_entities)
        assert len(blockers) == 1
        assert f"proposal {proposal.id}" in blockers[0][1]
        assert not report_and_prune(summary, recorded_service, repo, proposals, prune=True)
        assert repo.get_property_definition(realizes.id) is not None

    def test_prune_refuses_when_an_open_proposal_names_a_stale_id_nested_in_its_fields(
        self, ontology_service, repo, proposals, spec_dir
    ):
        import_dr_ontology(ontology_service, repo, spec_dir)
        realizes = _realizes(repo)
        other = next(p for p in repo.list_property_definitions(limit=None) if p.id != realizes.id)
        proposals.create(
            ChangeProposal(
                id=str(uuid4()),
                taxonomy_id=repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER).id,
                title="Point at realizes",
                source=ProposalSource.USER,
                created_at=datetime.now(timezone.utc),
                operations=[
                    ProposedOperation(
                        seq=1,
                        op=OperationType.UPDATE,
                        kind=OperationKind.PROPERTY,
                        target_id=other.id,
                        fields={"external_references": [{"metadata": {"see": [realizes.id]}}]},
                    )
                ],
            )
        )
        _drop_spec_files(spec_dir, "*realizes*.json")
        summary = import_dr_ontology(ontology_service, repo, spec_dir)

        blockers = find_prune_blockers(repo, proposals, summary.stale_entities)
        assert len(blockers) == 1
        assert "Point at realizes" in blockers[0][1]

    def test_prune_refuses_for_a_type_an_applied_proposal_created_that_the_spec_lacks(
        self, ontology_service, recorded_service, repo, proposals, spec_dir, session_factory
    ):
        import_dr_ontology(ontology_service, repo, spec_dir)
        goal = repo.get_by_identifier("motivation_goal")
        stakeholder = repo.get_by_identifier("motivation_stakeholder")
        change_repo = SQLiteChangeRepository(session_factory)
        publisher = InProcessEventPublisher()
        ChangeEventRecorder(change_repo).subscribe_ontology_events(publisher)
        proposal_service = ProposalService(
            proposals,
            OntologyService(repo, FakeEmbeddingService(), publisher, schema_index=None),
            repo,
            RevertService(change_repo=change_repo, ontology_repo=repo),
        )
        # As a reflection plan's create does: a new triple carrying its DR reference.
        new_triple = "motivation.goal.serves.motivation.stakeholder"
        proposal = proposal_service.propose(
            repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER).id,
            "Reflection plan",
            [
                OperationDraft(
                    seq=1,
                    op=OperationType.CREATE,
                    kind=OperationKind.PROPERTY,
                    fields={
                        "identifier": "goal_serves_stakeholder",
                        "title": "Goal serves Stakeholder",
                        "canonical_predicate": "serves",
                        "domain_class_id": goal.id,
                        "range_class_id": stakeholder.id,
                        "external_references": [
                            ExternalReference(source=DR_SOURCE, identifier=new_triple).to_dict()
                        ],
                    },
                )
            ],
            ProposalSource.USER,
        )
        proposal = proposal_service.apply(proposal.id, [proposal.operations[0].id])
        assert proposal.status is ProposalStatus.DONE
        created_id = proposal.operations[0].result_entity_id

        summary = import_dr_ontology(ontology_service, repo, spec_dir)  # spec lacks the triple
        assert [e.id for e in summary.stale_entities] == [created_id]

        blockers = find_prune_blockers(repo, proposals, summary.stale_entities)
        assert len(blockers) == 1
        assert f"proposal {proposal.id}" in blockers[0][1]
        assert "created/changed" in blockers[0][1]
        assert not report_and_prune(summary, recorded_service, repo, proposals, prune=True)
        assert repo.get_property_definition(created_id) is not None
        assert _delete_event_count(session_factory) == 0

    def test_a_refused_delete_stops_the_prune_and_reports_what_was_deleted(
        self, ontology_service, recorded_service, repo, spec_dir
    ):
        import_dr_ontology(ontology_service, repo, spec_dir)
        service_class = repo.get_by_identifier("business_businessservice")
        ontology_service.create_individual(service_class.id, "Billing")
        _drop_spec_files(spec_dir, "*realizes*.json")
        _drop_spec_files(spec_dir, "businessservice.node.schema.json")
        summary = import_dr_ontology(ontology_service, repo, spec_dir)

        # Skipping find_prune_blockers: the class's individual makes its delete fail.
        with pytest.raises(PruneFailed) as caught:
            prune_stale(recorded_service, summary.stale_entities)

        assert [type(e).__name__ for e in caught.value.deleted] == ["PropertyDefinition"]
        assert caught.value.failed.id == service_class.id
        assert repo.get_class(service_class.id) is not None

    def test_without_prune_nothing_is_deleted(
        self, ontology_service, recorded_service, repo, proposals, spec_dir, capsys
    ):
        import_dr_ontology(ontology_service, repo, spec_dir)
        _drop_spec_files(spec_dir, "*realizes*.json")
        summary = import_dr_ontology(ontology_service, repo, spec_dir)

        assert report_and_prune(summary, recorded_service, repo, proposals, prune=False)

        assert repo.get_property_definition(summary.stale_entities[0].id) is not None
        assert "not deleted" in capsys.readouterr().out


class TestImportScriptExitCode:
    def test_main_exits_1_when_the_prune_is_refused(self, spec_dir, tmp_path, monkeypatch):
        db_path = tmp_path / "local.db"
        engine = create_local_db_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)
        repo = SQLiteOntologyRepository(sessionmaker(bind=engine))
        service = OntologyService(repo, FakeEmbeddingService(), _NoOpEventPublisher())
        import_dr_ontology(service, repo, spec_dir)
        goal = repo.get_by_identifier("motivation_goal")
        service_class = repo.get_by_identifier("business_businessservice")
        source = service.create_individual(goal.id, "Grow revenue")
        target = service.create_individual(service_class.id, "Billing")
        service.create_relationship(source.id, target.id, _realizes(repo).id)
        engine.dispose()
        _drop_spec_files(spec_dir, "*realizes*.json")

        database = SimpleNamespace(
            local_db_path=str(db_path), operations_db_path=str(tmp_path / "operations.db")
        )
        settings = SimpleNamespace(database=database)
        monkeypatch.setattr(
            import_script,
            "get_config_manager",
            lambda: SimpleNamespace(get_settings=lambda: settings),
        )
        monkeypatch.setattr(
            import_script, "SentenceTransformerEmbedding", lambda **_: FakeEmbeddingService()
        )
        monkeypatch.setattr(import_script, "record_baseline_reset_if_new", lambda *_: False)
        monkeypatch.setattr(
            sys, "argv", ["import_dr_ontology.py", "--spec-dir", str(spec_dir), "--prune"]
        )

        assert import_script.main() == 1

        monkeypatch.setattr(sys, "argv", ["import_dr_ontology.py", "--spec-dir", str(spec_dir)])
        assert import_script.main() == 0


class TestImportDrOntologyMirrorsTheSpec:
    def test_the_taxonomy_is_mirrored_at_the_spec_revision(self, ontology_service, repo, spec_dir):
        git = ["git", "-C", str(spec_dir)]
        subprocess.run([*git, "init", "-q"], check=True)
        subprocess.run([*git, "remote", "add", "origin", "https://example.com/dr.git"], check=True)
        subprocess.run([*git, "add", "-A"], check=True)
        subprocess.run(
            [*git, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "spec"],
            check=True,
        )
        head = subprocess.run(
            [*git, "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()

        summary = import_dr_ontology(ontology_service, repo, spec_dir)

        taxonomy = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
        assert taxonomy.mirrored is True
        assert taxonomy.source_revision.to_dict() == {
            "repo": "https://example.com/dr.git",
            "commit": head,
            "spec_version": "0.8.4",
        }
        assert summary.source_revision == taxonomy.source_revision

    def test_a_spec_outside_git_still_records_its_version(self, ontology_service, repo, spec_dir):
        import_dr_ontology(ontology_service, repo, spec_dir)

        revision = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER).source_revision
        assert revision.spec_version == "0.8.4"
