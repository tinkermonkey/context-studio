"""
Unit tests for bundle import as a proposal (#1364): the planner's operations
and the BundleImportService's propose / apply / dry-run / supersede rules, with
in-memory fakes.
"""

import copy

import pytest

from domain.interchange.bundle import NEW_TAXONOMY, BundleError, plan_bundle
from domain.ontology.services import OntologyService
from domain.versioning.approval_policy import ApprovalPolicy
from domain.versioning.bundle_import import BundleImportService
from domain.versioning.exceptions import ProposalValidationError
from domain.versioning.proposal_service import ProposalService
from domain.versioning.proposals import (
    ChangeScope,
    OperationKind,
    OperationStatus,
    OperationType,
    ProposalSource,
    ProposalStatus,
)
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_proposal_repository import FakeChangeProposalRepository
from tests.unit.domain.versioning.test_proposal_service import StubRevertService

T, K = OperationType, OperationKind

BUNDLE = {
    "format": "context-studio-bundle",
    "version": 0,
    "source": "house",
    "taxonomy": {"identifier": "house", "title": "House", "description": "Chores."},
    "schemes": [{"identifier": "house_kinds", "title": "Kinds"}],
    "classes": [
        {"identifier": "house_place", "scheme": "house_kinds", "title": "Place"},
        {
            "identifier": "house_room",
            "scheme": "house_kinds",
            "parent": "house_place",
            "title": "Room",
        },
        {
            "identifier": "house_activity",
            "scheme": "house_kinds",
            "title": "Activity",
            "attributes": [
                {"identifier": "house_minutes", "title": "Minutes", "datatype": "integer"}
            ],
        },
        {"identifier": "house_resource", "scheme": "house_kinds", "title": "Resource"},
    ],
    "properties": [
        {
            "identifier": "house_requires",
            "title": "requires",
            "domain": "house_activity",
            "range": "house_resource",
            "constraints": {"edge_properties": ["quantity", "unit"]},
        }
    ],
    "individuals": [
        {"id": "hang", "classes": ["house_activity"], "title": "Hang a picture"},
        {"id": "hooks", "classes": ["house_resource"], "title": "Hooks"},
        {"id": "hammer", "classes": ["house_resource"], "title": "Hammer"},
    ],
    "relationships": [
        {
            "source": "hang",
            "property": "house_requires",
            "target": "hooks",
            "attributes": {"quantity": 2, "unit": "each"},
        },
        {"source": "hang", "property": "house_requires", "target": "hammer"},
    ],
}


def bundle(**changes):
    result = copy.deepcopy(BUNDLE)
    result.update(changes)
    return result


@pytest.fixture()
def ontology():
    return OntologyService(FakeOntologyRepository(), FakeEmbeddingService(), FakeEventPublisher())


@pytest.fixture()
def repo(ontology):
    return ontology._repository


@pytest.fixture()
def proposals(ontology, repo):
    return ProposalService(FakeChangeProposalRepository(), ontology, repo, StubRevertService())


@pytest.fixture()
def importer(proposals, ontology, repo):
    return BundleImportService(proposals, ontology, repo)


def loaded(importer):
    """Import BUNDLE and apply everything (a first import is all creates)."""
    result = importer.import_bundle(bundle(), apply=True)
    assert result.proposal.status is ProposalStatus.DONE
    return result


# ------------------------------------------------------------------ planner


class TestPlan:
    def test_new_taxonomy_plans_creates_with_refs_in_dependency_order(self, repo):
        plan = plan_bundle(repo, bundle())

        assert plan.taxonomy_id is None
        assert [o.seq for o in plan.operations] == list(range(1, len(plan.operations) + 1))
        assert {o.op for o in plan.operations} == {T.CREATE}
        kinds = [o.kind for o in plan.operations]
        assert (
            kinds
            == [K.SCHEME]
            + [K.CLASS] * 3
            + [K.ATTRIBUTE, K.CLASS, K.PROPERTY]
            + [K.INDIVIDUAL] * 3
            + [K.RELATIONSHIP] * 2
        )
        by_ref = {o.ref: o for o in plan.operations}
        assert by_ref["scheme:house_kinds"].fields["taxonomy_id"] == NEW_TAXONOMY
        room = by_ref["class:house_room"]
        assert room.fields["parent_class_id"] == "$class:house_place"
        assert room.fields["external_references"] == [
            {"source": "house", "identifier": "house_room", "uri": None, "metadata": None}
        ]
        assert by_ref["attribute:house_activity/house_minutes"].fields["class_id"] == (
            "$class:house_activity"
        )
        kit = by_ref["relationship:hang/house_requires/hooks"].fields
        assert kit == {
            "source_id": "$individual:hang",
            "target_id": "$individual:hooks",
            "property_definition_id": "$property:house_requires",
            "attributes": {"quantity": 2, "unit": "each"},
        }
        assert "attributes" not in by_ref["relationship:hang/house_requires/hammer"].fields
        assert plan.kind("relationship").created == 2

    def test_a_matching_workspace_plans_nothing(self, importer, repo):
        loaded(importer)

        plan = plan_bundle(repo, bundle())

        assert plan.operations == [] and plan.changed == 0 and plan.deletes == []

    def test_changes_become_updates_moves_and_attribute_updates(self, importer, repo):
        loaded(importer)
        changed = bundle()
        changed["taxonomy"]["description"] = None
        changed["classes"][1]["parent"] = None
        changed["relationships"][0]["attributes"] = {"quantity": 3, "unit": "each"}

        plan = plan_bundle(repo, changed)

        ops = {(o.op, o.kind): o for o in plan.operations}
        assert ops[(T.UPDATE, K.TAXONOMY)].fields == {"description": None}
        assert ops[(T.MOVE, K.CLASS)].fields == {"parent_class_id": None}
        assert ops[(T.UPDATE, K.RELATIONSHIP)].fields == {
            "attributes": {"quantity": 3, "unit": "each"}
        }
        assert len(plan.operations) == 3

    def test_dropped_entities_become_deletes_after_everything_else(self, importer, repo):
        loaded(importer)
        smaller = bundle(relationships=[], properties=[])
        smaller["individuals"] = smaller["individuals"][:2]
        smaller["classes"] = smaller["classes"][:2]
        smaller["individuals"] = [smaller["individuals"][0] | {"classes": ["house_place"]}]
        smaller["classes"][0]["attributes"] = []

        plan = plan_bundle(repo, smaller)

        deletes = [o for o in plan.operations if o.op is T.DELETE]
        assert [o.kind for o in deletes] == [
            K.RELATIONSHIP,
            K.RELATIONSHIP,
            K.INDIVIDUAL,
            K.INDIVIDUAL,
            K.PROPERTY,
            K.CLASS,
            K.CLASS,
        ]
        assert plan.operations[-len(deletes) :] == deletes
        assert "Individual 'Hammer' (hammer)" in plan.deletes
        assert "PropertyDefinition 'requires' (house_requires)" in plan.deletes
        update = next(o for o in plan.operations if o.kind is K.INDIVIDUAL and o.op is T.UPDATE)
        assert update.fields["class_ids"] == [repo.get_by_identifier("house_place").id]

    def test_unknown_edge_attributes_are_refused(self, repo):
        bad = bundle()
        bad["relationships"][1]["attributes"] = {"brand": "Acme"}
        with pytest.raises(BundleError, match=r"\['brand'\]"):
            plan_bundle(repo, bad)


# ------------------------------------------------------------------ service


class TestImport:
    def test_first_import_creates_the_taxonomy_and_proposes_the_rest(self, importer, repo):
        result = importer.import_bundle(bundle(), source_detail="house.bundle.json")

        assert result.taxonomy_created and not result.dry_run
        proposal = result.proposal
        assert proposal.taxonomy_id == repo.get_by_identifier("house").id
        assert proposal.source is ProposalSource.BUNDLE
        assert proposal.source_detail == "house.bundle.json"
        assert {o.status for o in proposal.operations} == {OperationStatus.PENDING}
        assert repo.get_by_identifier("house_kinds") is None  # nothing applied without a policy

    def test_apply_applies_every_non_breaking_operation(self, importer, repo):
        result = loaded(importer)

        assert {o.scope for o in result.proposal.operations} == {ChangeScope.ADDITIVE}
        hang = repo.get_by_identifier("house_activity")
        assert [i.title for i in repo.list_individuals(class_id=hang.id, limit=None)] == [
            "Hang a picture"
        ]

    def test_reimporting_an_unchanged_bundle_proposes_nothing(self, importer, proposals):
        loaded(importer)

        result = importer.import_bundle(bundle(), apply=True)

        assert result.proposal is None and result.plan.operations == []
        assert proposals.count_proposals() == 1

    def test_deletes_wait_for_review_even_with_apply(self, importer, repo):
        loaded(importer)
        smaller = bundle()
        smaller["individuals"] = smaller["individuals"][:2]
        smaller["relationships"] = smaller["relationships"][:1]
        smaller["taxonomy"]["title"] = "Home"

        result = importer.import_bundle(smaller, apply=True)

        ops = {(o.op, o.kind): o for o in result.proposal.operations}
        assert ops[(T.UPDATE, K.TAXONOMY)].status is OperationStatus.APPLIED
        delete = ops[(T.DELETE, K.INDIVIDUAL)]
        assert (delete.status, delete.scope) == (OperationStatus.PENDING, ChangeScope.BREAKING)
        assert result.proposal.status is ProposalStatus.OPEN
        assert repo.get_individual(delete.target_id) is not None

    def test_dry_run_stores_nothing(self, importer, proposals, repo):
        first = importer.import_bundle(bundle(), dry_run=True)
        assert first.dry_run and first.taxonomy_created and first.proposal is None
        assert repo.get_by_identifier("house") is None
        assert len(first.plan.operations) == 12

        loaded(importer)
        changed = bundle()
        changed["individuals"][0]["title"] = "Hang a frame"
        result = importer.import_bundle(changed, dry_run=True)

        [op] = result.proposal.operations
        assert (op.op, op.scope, op.status) == (
            T.UPDATE,
            ChangeScope.EDITORIAL,
            OperationStatus.PENDING,
        )
        assert proposals.count_proposals() == 1
        assert proposals.list_proposals()[0].id != result.proposal.id

    def test_a_new_import_supersedes_open_bundle_proposals(self, importer, proposals):
        loaded(importer)
        smaller = bundle()
        smaller["individuals"] = smaller["individuals"][:2]
        smaller["relationships"] = smaller["relationships"][:1]
        first = importer.import_bundle(smaller).proposal

        second = importer.import_bundle(smaller).proposal

        old = proposals.get(first.id)
        assert old.status is ProposalStatus.DONE
        assert {o.status for o in old.operations} == {OperationStatus.REJECTED}
        assert old.operations[0].reason == f"superseded by bundle proposal {second.id}"
        assert proposals.get(second.id).status is ProposalStatus.OPEN

    def test_an_invalid_plan_on_a_new_taxonomy_removes_the_taxonomy(
        self, importer, proposals, repo, monkeypatch
    ):
        def refuse(*args, **kwargs):
            raise ProposalValidationError([])

        monkeypatch.setattr(proposals, "propose", refuse)
        with pytest.raises(ProposalValidationError):
            importer.import_bundle(bundle())
        assert repo.get_by_identifier("house") is None

    def test_the_policy_auto_applies_what_it_allows(self, ontology, repo, importer, proposals):
        loaded(importer)
        grown = bundle()
        grown["individuals"].append(
            {"id": "level", "classes": ["house_resource"], "title": "Level"}
        )
        grown["individuals"][0]["title"] = "Hang a frame"

        class Policies:
            def get(self, taxonomy_id):
                return ApprovalPolicy.from_rules(
                    taxonomy_id, {"auto_apply": [{"op": "create", "kind": "individual"}]}
                )

        proposals._policies = Policies()
        result = importer.import_bundle(grown)

        ops = {o.op: o for o in result.proposal.operations}
        assert ops[T.CREATE].status is OperationStatus.APPLIED
        assert ops[T.UPDATE].status is OperationStatus.PENDING
