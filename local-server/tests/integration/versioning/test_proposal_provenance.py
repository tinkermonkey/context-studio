"""
Integration tests (#1553, part of #1552) over real SQLite, wired as in app.py:
an extraction-shaped proposal (individual creates with source passages and
near matches, relationships between them by "$ref") applied with and without
choosing "use existing", the provenance rows it records, and revert.
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
from adapters.persistence.sqlite.entity_source_repo import SQLiteEntitySourceRepository
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.proposal_repo import SQLiteChangeProposalRepository
from adapters.persistence.sqlite.transaction import SharedSessionFactory, SqliteTransactionScope
from domain.ontology.services import OntologyService
from domain.versioning.proposal_service import OperationDraft, ProposalService
from domain.versioning.proposals import OperationKind as K
from domain.versioning.proposals import OperationStatus, ProposalSource, ProposalStatus
from domain.versioning.proposals import OperationType as T
from domain.versioning.revert_service import RevertService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.utils.change_recording import wire_change_recorder

SOURCE = "src-whirlpool-manual"


@pytest.fixture()
def factory():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_local_db_engine(f"sqlite:///{Path(tmpdir) / 'local.db'}")
        Base.metadata.create_all(engine)
        yield SharedSessionFactory(sessionmaker(bind=engine))
        engine.dispose()


@pytest.fixture()
def parts(factory):
    repo = SQLiteOntologyRepository(session_factory=factory)
    change_repo = SQLiteChangeRepository(session_factory=factory)
    publisher = InProcessEventPublisher()
    wire_change_recorder(publisher, change_repo)
    ontology = OntologyService(repo, FakeEmbeddingService(), publisher)
    scope = SqliteTransactionScope(factory)
    service = ProposalService(
        SQLiteChangeProposalRepository(factory),
        ontology,
        repo,
        RevertService(change_repo=change_repo, ontology_repo=repo, transaction_scope=scope),
        transaction_scope=scope,
        entity_sources=SQLiteEntitySourceRepository(factory),
    )
    return ontology, repo, service


@pytest.fixture()
def house(parts):
    ontology, _, _ = parts
    taxonomy = ontology.create_taxonomy(title="House")
    scheme = ontology.create_scheme(taxonomy_id=taxonomy.id, title="Resources")
    appliance = ontology.create_class(scheme.id, "Appliance")
    business = ontology.create_class(scheme.id, "Business")
    made_by = ontology.create_property_definition(
        "made_by", "made by", domain_class_id=appliance.id, range_class_id=business.id
    )
    fridge = ontology.create_individual(appliance.id, "Kitchen refrigerator")
    whirlpool = ontology.create_individual(business.id, "Whirlpool Corporation")
    return {
        "taxonomy": taxonomy.id,
        "appliance": appliance.id,
        "business": business.id,
        "made_by": made_by.id,
        "fridge": fridge.id,
        "whirlpool": whirlpool.id,
    }


def passage(start, end, page, quote):
    return {"source_id": SOURCE, "page": page, "start": start, "end": end, "quote": quote}


def extraction(service, house):
    """Two candidates with near matches and a relationship between them, as #1552 drafts it."""
    return service.propose(
        house["taxonomy"],
        "Extracted from the use and care guide",
        [
            OperationDraft(
                1,
                T.CREATE,
                K.INDIVIDUAL,
                ref="c1",
                fields={"class_ids": [house["appliance"]], "title": "Whirlpool WRF555SDFZ"},
                evidence=[
                    passage(8412, 8447, 5, "WRF555SDFZ French door refrigerator"),
                    passage(104210, 104262, 54, "Accessories for your WRF555SDFZ"),
                ],
                probability=0.94,
                alternatives=[
                    {"kind": "existing", "entity_id": house["fridge"], "similarity": 0.93}
                ],
            ),
            OperationDraft(
                2,
                T.CREATE,
                K.INDIVIDUAL,
                ref="c2",
                fields={"class_ids": [house["business"]], "title": "Whirlpool"},
                evidence=[passage(12, 21, 1, "Whirlpool")],
                probability=0.97,
                alternatives=[
                    {"kind": "existing", "entity_id": house["whirlpool"], "similarity": 0.97}
                ],
            ),
            OperationDraft(
                3,
                T.CREATE,
                K.RELATIONSHIP,
                fields={
                    "source_id": "$c1",
                    "target_id": "$c2",
                    "property_definition_id": house["made_by"],
                },
                evidence=[passage(0, 20, 1, "Whirlpool WRF555SDFZ")],
                probability=0.95,
            ),
        ],
        ProposalSource.PIPELINE,
        source_detail=f"run r-1 on source {SOURCE}",
    )


def existing(entity_id):
    return {"kind": "existing", "entity_id": entity_id}


def test_the_proposal_stores_passages_and_near_matches(parts, house):
    _, _, service = parts

    stored = service.get(extraction(service, house).id)

    first = stored.operations[0]
    assert first.evidence[0] == passage(8412, 8447, 5, "WRF555SDFZ French door refrigerator")
    assert first.alternatives == [
        {"kind": "existing", "entity_id": house["fridge"], "similarity": 0.93}
    ]
    assert stored.operations[2].alternatives == []


def test_use_existing_repoints_the_relationship_records_provenance_and_reverts(parts, house):
    ontology, repo, service = parts
    proposal = extraction(service, house)
    ids = [o.id for o in proposal.operations]
    individuals_before = ontology.count_individuals()

    applied = service.apply(
        proposal.id,
        ids,
        chosen_alternatives={
            ids[0]: existing(house["fridge"]),
            ids[1]: existing(house["whirlpool"]),
        },
    )

    first, second, edge = applied.operations
    assert all(o.status is OperationStatus.APPLIED for o in applied.operations)
    assert (first.matched, first.result_entity_id) == (True, house["fridge"])
    assert (second.matched, second.result_entity_id) == (True, house["whirlpool"])
    assert ontology.count_individuals() == individuals_before
    relationship = repo.get_relationship(edge.result_entity_id)
    assert (relationship.source_id, relationship.target_id) == (house["fridge"], house["whirlpool"])
    assert applied.status is ProposalStatus.DONE

    fridge_sources = service.sources_of(house["fridge"])
    assert [(s.page, s.start, s.end, s.op_seq) for s in fridge_sources] == [
        (5, 8412, 8447, 1),
        (54, 104210, 104262, 1),
    ]
    assert {(s.entity_kind, s.source_id, s.proposal_id) for s in fridge_sources} == {
        ("individual", SOURCE, proposal.id)
    }
    [edge_source] = service.sources_of(relationship.id)
    assert (edge_source.entity_kind, edge_source.quote) == ("relationship", "Whirlpool WRF555SDFZ")
    decisions = service.decisions_of(proposal.id)
    assert decisions[ids[0]].chosen_alternative == {
        "kind": "existing",
        "entity_id": house["fridge"],
        "similarity": 0.93,
    }
    assert decisions[ids[0]].applied_fields == {}

    service.revert(proposal.id)

    assert repo.get_relationship(relationship.id) is None
    assert repo.get_individual(house["fridge"]).title == "Kitchen refrigerator"
    assert repo.get_individual(house["whirlpool"]) is not None
    assert service.sources_of(house["fridge"]) == []
    assert service.sources_of(relationship.id) == []
    assert service.get(proposal.id).status is ProposalStatus.REVERTED


def test_accepting_without_a_choice_creates_new_individuals_and_revert_removes_them(parts, house):
    ontology, repo, service = parts
    proposal = extraction(service, house)
    individuals_before = ontology.count_individuals()

    applied = service.apply(proposal.id, [o.id for o in proposal.operations])

    first, second, edge = applied.operations
    assert not first.matched and first.result_entity_id != house["fridge"]
    assert ontology.count_individuals() == individuals_before + 2
    relationship = repo.get_relationship(edge.result_entity_id)
    assert (relationship.source_id, relationship.target_id) == (
        first.result_entity_id,
        second.result_entity_id,
    )
    assert len(service.sources_of(first.result_entity_id)) == 2
    assert service.sources_of(house["fridge"]) == []

    service.revert(proposal.id)

    assert repo.get_individual(first.result_entity_id) is None
    assert ontology.count_individuals() == individuals_before
    assert service.sources_of(first.result_entity_id) == []


def test_a_mixed_choice_points_each_end_at_its_own_entity(parts, house):
    _, repo, service = parts
    proposal = extraction(service, house)
    ids = [o.id for o in proposal.operations]

    applied = service.apply(
        proposal.id, ids, chosen_alternatives={ids[1]: existing(house["whirlpool"])}
    )

    first, second, edge = applied.operations
    relationship = repo.get_relationship(edge.result_entity_id)
    assert (relationship.source_id, relationship.target_id) == (
        first.result_entity_id,
        house["whirlpool"],
    )
    assert repo.get_individual(first.result_entity_id).title == "Whirlpool WRF555SDFZ"
    assert [s.quote for s in service.sources_of(house["whirlpool"])] == ["Whirlpool"]


def test_provenance_of_other_proposals_survives_a_revert(parts, house):
    _, _, service = parts
    kept = extraction(service, house)
    kept_ids = [o.id for o in kept.operations]
    service.apply(
        kept.id, [kept_ids[0]], chosen_alternatives={kept_ids[0]: existing(house["fridge"])}
    )
    reverted = extraction(service, house)
    reverted_ids = [o.id for o in reverted.operations]
    service.apply(
        reverted.id,
        [reverted_ids[0]],
        chosen_alternatives={reverted_ids[0]: existing(house["fridge"])},
    )

    service.revert(reverted.id)

    assert {s.proposal_id for s in service.sources_of(house["fridge"])} == {kept.id}
