"""Unit tests for mirrored taxonomies and the landed state of proposals (#1463)."""

from datetime import datetime, timezone

import pytest

from domain.ontology.services import OntologyService
from domain.ontology.value_objects import SourceRevision
from domain.versioning.approval_policy import ApprovalPolicy
from domain.versioning.exceptions import ChangeProposalStateError
from domain.versioning.proposal_service import OperationDraft, ProposalService
from domain.versioning.proposals import (
    Landing,
    OperationKind,
    OperationStatus,
    OperationType,
    ProposalSource,
    ProposalStatus,
)
from domain.versioning.revert_service import RevertResult
from tests.fakes.fake_approval_policy_repository import FakeApprovalPolicyRepository
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_proposal_repository import FakeChangeProposalRepository

T, K = OperationType, OperationKind
MCP = ProposalSource.MCP
EDITORIAL = {"auto_apply": [{"scope": "editorial"}]}
IMPORTED = SourceRevision(repo="dr", commit="aaa111", spec_version="0.10.0")
DRAFTED = SourceRevision(repo="dr", commit="bbb222", spec_version="0.10.1")
LANDED = SourceRevision(repo="dr", commit="ccc333", spec_version="0.10.1")


class StubRevertService:
    def __init__(self):
        self.reverted: list[str] = []

    def revert_with_summary(self, run_id, on_reverted=None):
        self.reverted.append(run_id)
        result = RevertResult(run_id=run_id, events_reverted=0)
        if on_reverted is not None:
            on_reverted(result)
        return result


@pytest.fixture()
def ontology():
    return OntologyService(FakeOntologyRepository(), FakeEmbeddingService(), FakeEventPublisher())


@pytest.fixture()
def policies():
    return FakeApprovalPolicyRepository()


@pytest.fixture()
def reverts():
    return StubRevertService()


@pytest.fixture()
def service(ontology, policies, reverts):
    return ProposalService(
        FakeChangeProposalRepository(),
        ontology,
        ontology._repository,
        reverts,
        approval_policies=policies,
    )


@pytest.fixture()
def spec(ontology, policies):
    """A taxonomy with a class, an editorial auto-apply policy, imported at IMPORTED."""
    taxonomy = ontology.create_taxonomy(title="Spec")
    scheme = ontology.create_scheme(taxonomy_id=taxonomy.id, title="Layer")
    cls = ontology.create_class(scheme.id, "Operation", identifier="operation")
    ontology.set_taxonomy_source_revision(taxonomy.id, IMPORTED)
    policies.save(ApprovalPolicy.from_rules(taxonomy.id, EDITORIAL))
    return {"taxonomy": taxonomy.id, "class": cls.id}


def retitle(spec, title="API operation"):
    return [OperationDraft(1, T.UPDATE, K.CLASS, spec["class"], fields={"title": title})]


def decided(service, spec, **kwargs):
    """A proposal whose only operation a person applied: done."""
    proposal = service.propose(spec["taxonomy"], "Rename", retitle(spec), MCP, **kwargs)
    pending = [o.id for o in proposal.operations if o.status is OperationStatus.PENDING]
    if pending:
        proposal = service.apply(proposal.id, pending)
    assert proposal.status is ProposalStatus.DONE
    return proposal


class TestMirroredFlag:
    def test_taxonomies_start_unmirrored_and_a_person_can_set_it(self, ontology, spec):
        assert ontology.get_taxonomy(spec["taxonomy"]).mirrored is False
        ontology.set_taxonomy_mirrored(spec["taxonomy"], True)
        assert ontology.get_taxonomy(spec["taxonomy"]).mirrored is True

    def test_the_source_revision_is_kept_on_the_taxonomy(self, ontology, spec):
        assert ontology.get_taxonomy(spec["taxonomy"]).source_revision == IMPORTED


class TestNoAutoApply:
    def test_an_unmirrored_taxonomy_auto_applies_what_its_policy_allows(self, service, spec):
        proposal = service.propose(spec["taxonomy"], "Rename", retitle(spec), MCP)
        assert proposal.operations[0].status is OperationStatus.APPLIED

    def test_nothing_auto_applies_on_a_mirrored_taxonomy(self, service, ontology, spec):
        ontology.set_taxonomy_mirrored(spec["taxonomy"], True)

        proposal = service.propose(spec["taxonomy"], "Rename", retitle(spec), MCP)

        assert proposal.operations[0].status is OperationStatus.PENDING
        assert proposal.status is ProposalStatus.OPEN
        assert ontology.get_class(spec["class"]).title == "Operation"
        assert service.auto_apply_operation_ids(proposal) == []

    def test_a_person_still_applies_on_decision(self, service, ontology, spec):
        ontology.set_taxonomy_mirrored(spec["taxonomy"], True)
        proposal = decided(service, spec)
        assert ontology.get_class(spec["class"]).title == "API operation"
        assert proposal.landed is None


class TestSourceRevision:
    def test_a_proposal_records_the_revision_it_was_drafted_against(self, service, spec):
        proposal = service.propose(
            spec["taxonomy"], "Rename", retitle(spec), MCP, source_revision=DRAFTED
        )
        assert service.get(proposal.id).source_revision == DRAFTED

    def test_without_one_it_records_the_taxonomys_imported_revision(self, service, spec):
        proposal = service.propose(spec["taxonomy"], "Rename", retitle(spec), MCP)
        assert service.get(proposal.id).source_revision == IMPORTED

    def test_a_taxonomy_with_no_revision_records_none(self, service, ontology, spec):
        ontology.set_taxonomy_source_revision(spec["taxonomy"], None)
        proposal = service.propose(spec["taxonomy"], "Rename", retitle(spec), MCP)
        assert service.get(proposal.id).source_revision is None

    def test_a_revision_needs_a_value(self):
        with pytest.raises(ValueError, match="at least one"):
            SourceRevision()
        with pytest.raises(ValueError, match="non-empty"):
            SourceRevision(commit=" ")
        with pytest.raises(ValueError, match="Unknown source revision keys"):
            SourceRevision.from_dict({"sha": "abc"})


class TestLanding:
    def test_a_done_proposal_can_be_marked_landed(self, service, spec):
        proposal = decided(service, spec)

        landed = service.mark_landed(proposal.id, LANDED)

        assert landed.landed.revision == LANDED
        assert landed.landed.landed_at.tzinfo is not None
        assert service.get(proposal.id).landed == landed.landed

    def test_the_same_revision_again_changes_nothing(self, service, spec):
        proposal = decided(service, spec)
        first = service.mark_landed(proposal.id, LANDED).landed
        assert service.mark_landed(proposal.id, LANDED).landed == first

    def test_another_revision_replaces_the_landing(self, service, spec):
        proposal = decided(service, spec)
        service.mark_landed(proposal.id, LANDED)
        later = SourceRevision(repo="dr", commit="ddd444")
        assert service.mark_landed(proposal.id, later).landed.revision == later

    def test_an_open_proposal_cant_land(self, service, ontology, spec):
        ontology.set_taxonomy_mirrored(spec["taxonomy"], True)
        proposal = service.propose(spec["taxonomy"], "Rename", retitle(spec), MCP)
        with pytest.raises(ChangeProposalStateError, match="only a done proposal"):
            service.mark_landed(proposal.id, LANDED)
        assert service.get(proposal.id).landed is None

    def test_a_reverted_proposal_cant_land(self, service, spec):
        proposal = decided(service, spec)
        service.revert(proposal.id)
        with pytest.raises(ChangeProposalStateError, match="reverted"):
            service.mark_landed(proposal.id, LANDED)

    def test_a_landing_needs_a_commit(self, service, spec):
        proposal = decided(service, spec)
        with pytest.raises(ValueError, match="commit"):
            service.mark_landed(proposal.id, SourceRevision(spec_version="0.10.1"))

    def test_a_landing_can_be_cleared(self, service, spec):
        proposal = decided(service, spec)
        service.mark_landed(proposal.id, LANDED)
        assert service.clear_landing(proposal.id).landed is None
        assert service.clear_landing(proposal.id).landed is None

    def test_the_landing_round_trips_as_json(self):
        landing = Landing(revision=LANDED, landed_at=datetime(2026, 11, 9, tzinfo=timezone.utc))
        assert Landing.from_dict(landing.to_dict()) == landing


class TestUnlandedFilter:
    def test_done_and_unlanded_lists_the_decided_proposals_not_yet_landed(
        self, service, ontology, spec
    ):
        ontology.set_taxonomy_mirrored(spec["taxonomy"], True)
        landed = decided(service, spec)
        service.mark_landed(landed.id, LANDED)
        unlanded = decided(service, spec)
        still_open = service.propose(spec["taxonomy"], "Open", retitle(spec, "Op"), MCP)

        listed = service.list_proposals(spec["taxonomy"], status=ProposalStatus.DONE, landed=False)

        assert [p.id for p in listed] == [unlanded.id]
        assert (
            service.count_proposals(spec["taxonomy"], status=ProposalStatus.DONE, landed=False) == 1
        )
        assert [p.id for p in service.list_proposals(spec["taxonomy"], landed=True)] == [landed.id]
        assert still_open.id in {p.id for p in service.list_proposals(spec["taxonomy"])}


class TestRevert:
    def test_a_landed_proposal_on_a_mirrored_taxonomy_cant_be_reverted(
        self, service, ontology, spec, reverts
    ):
        ontology.set_taxonomy_mirrored(spec["taxonomy"], True)
        proposal = decided(service, spec)
        service.mark_landed(proposal.id, LANDED)

        with pytest.raises(ChangeProposalStateError, match="propose the reversal"):
            service.revert(proposal.id)

        assert reverts.reverted == []
        assert service.get(proposal.id).status is ProposalStatus.DONE

    def test_an_unlanded_one_can_be_reverted_to_abandon_it(self, service, ontology, spec, reverts):
        ontology.set_taxonomy_mirrored(spec["taxonomy"], True)
        proposal = decided(service, spec)
        service.revert(proposal.id)
        assert reverts.reverted == [proposal.id]
        assert service.get(proposal.id).status is ProposalStatus.REVERTED

    def test_a_landed_proposal_on_an_unmirrored_taxonomy_can_be_reverted(
        self, service, spec, reverts
    ):
        proposal = decided(service, spec)
        service.mark_landed(proposal.id, LANDED)
        service.revert(proposal.id)
        assert reverts.reverted == [proposal.id]
