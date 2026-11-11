"""Unit tests for the drift re-import service (#1464), with a fake planner."""

from types import MappingProxyType

import pytest

from domain.ontology.services import OntologyService
from domain.ontology.value_objects import ExternalReference, SourceRevision
from domain.versioning.drift import DriftEntry, DriftError, DriftImportService, DriftPlan
from domain.versioning.proposal_service import OperationDraft, ProposalService
from domain.versioning.proposals import (
    OperationKind,
    OperationStatus,
    OperationType,
    ProposalSource,
    ProposalStatus,
)
from domain.versioning.revert_service import RevertResult
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_proposal_repository import FakeChangeProposalRepository

REVISION = SourceRevision(repo="dr", commit="abcdef1234", spec_version="0.11.0")
LABELLED = [ExternalReference("dr", "spec", metadata=MappingProxyType({"spec_version": "0.11.0"}))]


class StubRevertService:
    def revert_with_summary(self, run_id, on_reverted=None):
        return RevertResult(run_id=run_id, events_reverted=0)


class FakePlanner:
    """Plans whatever drift the test sets: a retitle of the class, or nothing."""

    def __init__(self, taxonomy_id, class_id):
        self.taxonomy_id, self.class_id = taxonomy_id, class_id
        self.title: str | None = None
        self.error: Exception | None = None
        self.references: list[ExternalReference] | None = None

    def plan(self, location):
        if self.error is not None:
            raise self.error
        plan = DriftPlan(
            taxonomy_id=self.taxonomy_id,
            source="spec",
            source_revision=REVISION,
            taxonomy_references=self.references,
        )
        if self.title is not None:
            plan.entries.append(
                DriftEntry(kind="class", source_id="x.op", change="update", entity_id=self.class_id)
            )
            plan.operations.append(
                OperationDraft(
                    1,
                    OperationType.UPDATE,
                    OperationKind.CLASS,
                    self.class_id,
                    fields={"title": self.title},
                )
            )
        return plan


@pytest.fixture()
def world():
    ontology = OntologyService(
        FakeOntologyRepository(), FakeEmbeddingService(), FakeEventPublisher()
    )
    taxonomy = ontology.create_taxonomy(title="Spec")
    scheme = ontology.create_scheme(taxonomy_id=taxonomy.id, title="Layer")
    cls = ontology.create_class(scheme.id, "Operation", identifier="operation")
    proposals = ProposalService(
        FakeChangeProposalRepository(), ontology, ontology._repository, StubRevertService()
    )
    planner = FakePlanner(taxonomy.id, cls.id)
    service = DriftImportService(proposals, ontology, planner)
    return ontology, proposals, planner, service, taxonomy.id


def test_a_dry_run_reports_and_validates_without_storing(world):
    _, proposals, planner, service, _ = world
    planner.title = "API operation"

    result = service.reimport("spec/", dry_run=True)

    assert result.dry_run and len(result.plan.entries) == 1
    assert result.proposal.operations[0].fields == {"title": "API operation"}
    assert proposals.count_proposals() == 0


def test_a_real_run_proposes_with_the_source_revision(world):
    ontology, proposals, planner, service, _ = world
    planner.title = "API operation"

    proposal = service.reimport("spec/", dry_run=False).proposal

    stored = proposals.get(proposal.id)
    assert stored.source is ProposalSource.BUNDLE
    assert stored.source_detail == "bundle:spec"
    assert stored.source_revision == REVISION
    assert stored.title == "Re-import spec at 0.11.0 (abcdef12)"
    assert [o.status for o in stored.operations] == [OperationStatus.PENDING]


def test_a_new_run_supersedes_the_earlier_open_one(world):
    _, proposals, planner, service, _ = world
    planner.title = "First"
    first = service.reimport("spec/", dry_run=False).proposal
    planner.title = "Second"

    service.reimport("spec/", dry_run=False)

    assert proposals.get(first.id).status is ProposalStatus.DONE
    assert proposals.get(first.id).operations[0].status is OperationStatus.REJECTED


def test_no_drift_proposes_nothing_and_records_the_revision(world):
    ontology, proposals, _, service, taxonomy_id = world

    result = service.reimport("spec/", dry_run=False)

    assert result.proposal is None and result.plan.entries == []
    assert proposals.count_proposals() == 0
    assert ontology.get_taxonomy(taxonomy_id).source_revision == REVISION


def test_a_dry_run_with_no_drift_records_nothing(world):
    ontology, _, _, service, taxonomy_id = world
    service.reimport("spec/", dry_run=True)
    assert ontology.get_taxonomy(taxonomy_id).source_revision is None


def test_no_drift_records_the_revision_label_on_the_taxonomy_references(world):
    ontology, _, planner, service, taxonomy_id = world
    planner.references = LABELLED

    service.reimport("spec/", dry_run=False)

    assert ontology.get_taxonomy(taxonomy_id).external_references == LABELLED


def test_a_dry_run_leaves_the_taxonomy_references(world):
    ontology, _, planner, service, taxonomy_id = world
    planner.references = LABELLED

    service.reimport("spec/", dry_run=True)

    assert ontology.get_taxonomy(taxonomy_id).external_references == []


def test_drift_leaves_the_taxonomy_references(world):
    ontology, _, planner, service, taxonomy_id = world
    planner.title, planner.references = "API operation", LABELLED

    service.reimport("spec/", dry_run=False)

    taxonomy = ontology.get_taxonomy(taxonomy_id)
    assert taxonomy.external_references == [] and taxonomy.source_revision is None


def test_a_planner_error_propagates(world):
    _, _, planner, service, _ = world
    planner.error = DriftError("not a spec")
    with pytest.raises(DriftError, match="not a spec"):
        service.reimport("nowhere/")
