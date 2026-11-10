"""
Integration tests (#1485): a dataset that yields to the schema never blocks a
schema operation; its data follows the change inside that dataset only, review
shows the impact, and reverting the proposal restores it.

One schema with two datasets: `context-studio` (yields, like CS's own DR model)
and `platform` (doesn't). Real SQLite, foreign keys enforced, change events
recorded, everything wired as in app.py.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import tempfile
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.connection import create_local_db_engine
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.proposal_repo import SQLiteChangeProposalRepository
from adapters.persistence.sqlite.transaction import SharedSessionFactory, SqliteTransactionScope
from domain.ontology.services import OntologyService
from domain.ontology.value_objects import DataPropertyValue
from domain.versioning.proposal_service import OperationDraft, ProposalService
from domain.versioning.proposals import (
    InUseResolution,
    OperationStatus,
    ProposalSource,
    ResolutionStrategy,
)
from domain.versioning.proposals import OperationKind as K
from domain.versioning.proposals import OperationType as T
from domain.versioning.revert_service import RevertService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.utils.change_recording import wire_change_recorder


@pytest.fixture()
def session_factory():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_local_db_engine(f"sqlite:///{Path(tmpdir) / 'local.db'}")
        Base.metadata.create_all(engine)
        yield sessionmaker(bind=engine)
        engine.dispose()


@pytest.fixture()
def parts(session_factory):
    shared = SharedSessionFactory(session_factory)
    scope = SqliteTransactionScope(shared)
    repo = SQLiteOntologyRepository(session_factory=shared)
    change_repo = SQLiteChangeRepository(session_factory=shared)
    publisher = InProcessEventPublisher()
    wire_change_recorder(publisher, change_repo)
    ontology = OntologyService(repo, FakeEmbeddingService(), publisher, transaction_scope=scope)
    service = ProposalService(
        SQLiteChangeProposalRepository(shared),
        ontology,
        repo,
        RevertService(change_repo=change_repo, ontology_repo=repo, transaction_scope=scope),
        transaction_scope=scope,
    )
    return ontology, repo, service


@pytest.fixture()
def model(parts):
    ontology, repo, _ = parts
    taxonomy = ontology.create_taxonomy(title="Documentation Robotics")
    scheme = ontology.create_scheme(taxonomy.id, title="Application")
    component = ontology.create_class(scheme.id, "Component")
    service_cls = ontology.create_class(scheme.id, "Service")
    legacy_cls = ontology.create_class(scheme.id, "Legacy")
    ontology.create_attribute_definition(
        class_id=component.id, identifier="tier", title="Tier", datatype="string"
    )
    types = {
        name: ontology.create_property_definition(
            name, name, domain_class_id=component.id, range_class_id=service_cls.id
        )
        for name in ("uses", "uses_v2", "depends", "calls")
    }
    sample = ontology.create_dataset(taxonomy.id, "context-studio", "Context Studio")
    sample.yields_to_schema = True
    repo.save_dataset(sample)
    platform = ontology.create_dataset(taxonomy.id, "platform", "Platform")

    def data(dataset):
        tier = [DataPropertyValue(property_identifier="tier", value="edge", datatype="string")]
        gateway = ontology.create_individual(
            component.id, "Gateway", dataset_id=dataset.id, data_properties=tier
        )
        api = ontology.create_individual(service_cls.id, "API", dataset_id=dataset.id)
        edges = {
            name: ontology.create_relationship(gateway.id, api.id, types[name].id)
            for name in ("uses", "depends", "calls")
        }
        return gateway, api, edges

    sample_data = data(sample)
    platform_gateway, platform_api, _ = data(platform)
    # The platform uses only `uses`; drop its other edges so they don't block.
    for rel in repo.list_relationships(source_id=platform_gateway.id, limit=None):
        if rel.property_definition_id != types["uses"].id:
            ontology.delete_relationship(rel.id)
    legacy = ontology.create_individual(legacy_cls.id, "Old Batch Job", dataset_id=sample.id)
    mixed = ontology.create_individual(
        [component.id, legacy_cls.id], "Mixed Job", dataset_id=sample.id
    )
    return {
        "taxonomy": taxonomy,
        "component": component,
        "service": service_cls,
        "legacy": legacy_cls,
        "types": types,
        "sample": sample,
        "platform": platform,
        "sample_data": sample_data,
        "platform_gateway": platform_gateway,
        "legacy_individual": legacy,
        "mixed_individual": mixed,
    }


def _propose(service, model, *drafts):
    return service.propose(model["taxonomy"].id, "Spec change", list(drafts), ProposalSource.USER)


def _edge_types(repo, dataset):
    return sorted(
        repo.get_property_definition(r.property_definition_id).identifier
        for r in repo.list_relationships(limit=None, dataset_id=dataset.id)
    )


def test_a_type_only_sample_data_uses_deletes_without_blockers_and_drops_its_edges(parts, model):
    _, repo, service = parts
    proposal = _propose(
        service, model, OperationDraft(1, T.DELETE, K.PROPERTY, model["types"]["depends"].id)
    )
    [operation] = proposal.operations

    assert service.in_use_blockers(proposal) == {}
    [impact] = service.dataset_impacts(proposal)[operation.id]
    assert (impact.identifier, impact.relationships_dropped) == ("context-studio", 1)

    applied = service.apply(proposal.id, [operation.id])

    assert applied.operations[0].status is OperationStatus.APPLIED
    assert applied.operations[0].resolution is None
    assert repo.get_property_definition(model["types"]["depends"].id) is None
    assert _edge_types(repo, model["sample"]) == ["calls", "uses"]
    assert _edge_types(repo, model["platform"]) == ["uses"]

    service.revert(proposal.id)

    assert _edge_types(repo, model["sample"]) == ["calls", "depends", "uses"]


def test_sample_edges_move_to_the_replacement_and_only_other_data_blocks(parts, model):
    _, repo, service = parts
    uses, uses_v2 = model["types"]["uses"], model["types"]["uses_v2"]
    proposal = _propose(
        service,
        model,
        OperationDraft(1, T.DELETE, K.PROPERTY, uses.id, replacement=uses_v2.id),
    )
    [operation] = proposal.operations

    blockers = service.in_use_blockers(proposal)[operation.id]
    assert [e.dataset_id for e in blockers.edges] == [model["platform"].id]
    [impact] = service.dataset_impacts(proposal)[operation.id]
    assert (impact.relationships_moved, impact.relationships_dropped) == (1, 0)

    applied = service.apply(
        proposal.id,
        [operation.id],
        resolutions={
            operation.id: InUseResolution(
                ResolutionStrategy.MOVE, replacement_property_id=uses_v2.id
            )
        },
    )

    done = applied.operations[0]
    assert done.status is OperationStatus.APPLIED
    # The resolution records the reviewed (platform) relationships only.
    assert len(done.resolution.edges) == 1
    assert _edge_types(repo, model["sample"]) == ["calls", "depends", "uses_v2"]
    assert _edge_types(repo, model["platform"]) == ["uses_v2"]

    service.revert(proposal.id)

    assert _edge_types(repo, model["sample"]) == ["calls", "depends", "uses"]
    assert _edge_types(repo, model["platform"]) == ["uses"]


def test_a_retarget_drops_sample_edges_without_a_resolution(parts, model):
    _, repo, service = parts
    calls = model["types"]["calls"]
    proposal = _propose(
        service,
        model,
        OperationDraft(
            1, T.UPDATE, K.PROPERTY, calls.id, fields={"range_class_id": model["component"].id}
        ),
    )
    [operation] = proposal.operations

    assert service.in_use_blockers(proposal) == {}
    [impact] = service.dataset_impacts(proposal)[operation.id]
    assert impact.relationships_dropped == 1

    applied = service.apply(proposal.id, [operation.id])

    assert applied.operations[0].status is OperationStatus.APPLIED
    assert repo.get_property_definition(calls.id).range_class_id == model["component"].id
    assert _edge_types(repo, model["sample"]) == ["depends", "uses"]

    service.revert(proposal.id)

    assert _edge_types(repo, model["sample"]) == ["calls", "depends", "uses"]


def test_a_class_delete_drops_or_untypes_sample_individuals(parts, model):
    _, repo, service = parts
    legacy, mixed = model["legacy_individual"], model["mixed_individual"]
    proposal = _propose(service, model, OperationDraft(1, T.DELETE, K.CLASS, model["legacy"].id))
    [operation] = proposal.operations

    [impact] = service.dataset_impacts(proposal)[operation.id]
    assert (impact.individuals_dropped, impact.individuals_untyped) == (1, 1)
    assert impact.relationships_dropped == 0  # the dropped one has no relationships

    applied = service.apply(proposal.id, [operation.id])

    assert applied.operations[0].status is OperationStatus.APPLIED
    assert repo.get_class(model["legacy"].id) is None
    assert repo.get_individual(legacy.id) is None
    assert repo.get_individual(mixed.id).class_ids == [model["component"].id]

    service.revert(proposal.id)

    assert repo.get_individual(legacy.id).class_ids == [model["legacy"].id]
    assert repo.get_individual(mixed.id).class_ids == [model["component"].id, model["legacy"].id]


def test_a_class_with_other_datasets_individuals_still_blocks(parts, model):
    ontology, repo, service = parts
    ontology.create_individual(
        model["legacy"].id, "Platform Batch Job", dataset_id=model["platform"].id
    )
    proposal = _propose(service, model, OperationDraft(1, T.DELETE, K.CLASS, model["legacy"].id))

    applied = service.apply(proposal.id, [proposal.operations[0].id])

    assert applied.operations[0].status is OperationStatus.FAILED
    assert "platform 1" in applied.operations[0].reason
    # Nothing of the sample changed: the failed operation rolled back.
    assert repo.get_individual(model["legacy_individual"].id) is not None


def test_an_attribute_delete_drops_only_sample_values(parts, model):
    _, repo, service = parts
    [attribute] = repo.list_attribute_definitions(class_id=model["component"].id)
    sample_gateway = model["sample_data"][0]
    proposal = _propose(service, model, OperationDraft(1, T.DELETE, K.ATTRIBUTE, attribute.id))
    [operation] = proposal.operations

    [impact] = service.dataset_impacts(proposal)[operation.id]
    assert impact.values_dropped == 1

    service.apply(proposal.id, [operation.id])

    assert repo.get_individual(sample_gateway.id).data_properties == []
    assert [v.value for v in repo.get_individual(model["platform_gateway"].id).data_properties] == [
        "edge"
    ]

    service.revert(proposal.id)

    assert [v.value for v in repo.get_individual(sample_gateway.id).data_properties] == ["edge"]


def test_no_yielding_dataset_means_no_impacts(parts, model):
    _, repo, service = parts
    sample = model["sample"]
    sample.yields_to_schema = False
    repo.save_dataset(sample)
    proposal = _propose(
        service, model, OperationDraft(1, T.DELETE, K.PROPERTY, model["types"]["depends"].id)
    )

    assert service.dataset_impacts(proposal) == {}
    assert proposal.operations[0].id in service.in_use_blockers(proposal)


def test_review_counts_moves_to_a_replacement_the_proposal_creates(parts, model):
    _, repo, service = parts
    proposal = _propose(
        service,
        model,
        OperationDraft(
            1,
            T.CREATE,
            K.PROPERTY,
            ref="depends_v2",
            fields={
                "identifier": "depends_v2",
                "title": "depends v2",
                "domain_class_id": model["component"].id,
                "range_class_id": model["service"].id,
            },
        ),
        OperationDraft(
            2, T.DELETE, K.PROPERTY, model["types"]["depends"].id, replacement="$depends_v2"
        ),
    )
    create, delete = proposal.operations

    [impact] = service.dataset_impacts(proposal)[delete.id]
    assert (impact.relationships_moved, impact.relationships_dropped) == (1, 0)

    service.apply(proposal.id, [create.id, delete.id])

    assert _edge_types(repo, model["sample"]) == ["calls", "depends_v2", "uses"]


def test_a_delete_resolution_still_moves_sample_edges_to_the_named_replacement(parts, model):
    _, repo, service = parts
    uses, uses_v2 = model["types"]["uses"], model["types"]["uses_v2"]
    proposal = _propose(
        service,
        model,
        OperationDraft(1, T.DELETE, K.PROPERTY, uses.id, replacement=uses_v2.id),
    )
    [operation] = proposal.operations

    service.apply(
        proposal.id,
        [operation.id],
        resolutions={operation.id: InUseResolution(ResolutionStrategy.DELETE)},
    )

    # The platform's edge went with the resolution; the sample's followed the record.
    assert _edge_types(repo, model["platform"]) == []
    assert _edge_types(repo, model["sample"]) == ["calls", "depends", "uses_v2"]


def test_dropping_a_sample_individual_counts_its_relationships(parts, model):
    ontology, repo, service = parts
    legacy = model["legacy_individual"]
    _, api, _ = model["sample_data"]
    link = ontology.create_property_definition(
        "replaced_by", "replaced by", domain_class_id=model["legacy"].id
    )
    ontology.create_relationship(legacy.id, api.id, link.id)
    proposal = _propose(service, model, OperationDraft(1, T.DELETE, K.CLASS, model["legacy"].id))
    [operation] = proposal.operations

    [impact] = service.dataset_impacts(proposal)[operation.id]
    assert (impact.individuals_dropped, impact.relationships_dropped) == (1, 1)
