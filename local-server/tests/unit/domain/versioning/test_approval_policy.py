"""Unit tests for approval policies (#1355): parsing, matching, hard rules, auto-apply."""

import pytest

from domain.interchange.services import get_current_batch_run_id, set_batch_run_context
from domain.ontology.events import ClassCreated, IndividualCreated
from domain.ontology.exceptions import EntityNotFoundError
from domain.ontology.services import OntologyService
from domain.versioning.approval_policy import (
    ApprovalPolicy,
    ApprovalPolicyService,
    AutoApplyRule,
    auto_apply_ids,
)
from domain.versioning.proposal_service import OperationDraft, ProposalService
from domain.versioning.proposals import (
    ChangeScope,
    OperationKind,
    OperationStatus,
    OperationType,
    ProposalSource,
    ProposalStatus,
    ProposedOperation,
)
from domain.versioning.revert_service import RevertResult
from tests.fakes.fake_approval_policy_repository import FakeApprovalPolicyRepository
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_proposal_repository import FakeChangeProposalRepository

T, K, S = OperationType, OperationKind, ChangeScope

HOUSE_RULES = {
    "auto_apply": [
        {"op": "create", "kind": "individual", "class": "house_activity"},
        {"scope": "editorial"},
    ],
    "min_probability": 0,
}


def op(seq, op_type, kind, scope, target=None, ref=None, probability=None, **fields):
    return ProposedOperation(
        seq=seq,
        op=op_type,
        kind=kind,
        target_id=target,
        ref=ref,
        fields=fields,
        scope=scope,
        probability=probability,
    )


# ---------------------------------------------------------------- the value object


class TestParsing:
    def test_round_trips_the_rules_json(self):
        policy = ApprovalPolicy.from_rules("tax", HOUSE_RULES)
        assert policy.auto_apply == (
            AutoApplyRule(op=T.CREATE, kind=K.INDIVIDUAL, class_key="house_activity"),
            AutoApplyRule(scope=S.EDITORIAL),
        )
        assert policy.to_rules() == {**HOUSE_RULES, "min_probability": 0.0}

    def test_empty_rules_are_an_empty_policy(self):
        policy = ApprovalPolicy.from_rules("tax", {})
        assert (policy.auto_apply, policy.min_probability) == ((), 0.0)

    @pytest.mark.parametrize(
        "rules, message",
        [
            ({"auto_apply": [{"op": "create", "colour": "red"}]}, "Unknown auto-apply rule keys"),
            ({"auto_apply": [{"op": "replace"}]}, "replace"),
            ({"auto_apply": [{"kind": "widget"}]}, "widget"),
            ({"auto_apply": [{"scope": "huge"}]}, "huge"),
            ({"auto_apply": [{}]}, "at least one of"),
            ({"auto_apply": [{"class": ""}]}, "class id or identifier"),
            ({"auto_apply": ["create"]}, "must be an object"),
            ({"auto_apply": {"op": "create"}}, "must be a list"),
            ({"min_probability": 1.5}, "between 0 and 1"),
            ({"min_probability": "high"}, "must be a number"),
            ({"max_probability": 1}, "Unknown approval policy keys"),
        ],
    )
    def test_invalid_rules_are_refused(self, rules, message):
        with pytest.raises(ValueError, match=message):
            ApprovalPolicy.from_rules("tax", rules)


class TestMatching:
    def test_a_rule_matches_when_every_key_it_sets_matches(self):
        rule = AutoApplyRule(op=T.CREATE, kind=K.INDIVIDUAL, class_key="house_activity")
        create = op(1, T.CREATE, K.INDIVIDUAL, S.ADDITIVE, class_ids=["c1"])
        assert rule.matches(create, {"c1", "house_activity"})
        assert not rule.matches(create, {"c1", "place"})
        update = op(2, T.UPDATE, K.INDIVIDUAL, S.EDITORIAL, target="i1", title="x")
        assert not rule.matches(update, {"house_activity"})
        assert AutoApplyRule(scope=S.EDITORIAL).matches(update, set())

    def test_hard_rules_beat_any_rule(self):
        policy = ApprovalPolicy(
            "tax",
            (AutoApplyRule(op=T.DELETE), AutoApplyRule(scope=S.BREAKING), AutoApplyRule(op=T.MOVE)),
        )
        delete = op(1, T.DELETE, K.INDIVIDUAL, S.BREAKING, target="i1")
        move = op(2, T.MOVE, K.CLASS, S.BREAKING, target="c1", parent_class_id=None)
        breaking_update = op(3, T.UPDATE, K.CLASS, S.BREAKING, target="c1", identifier="x")
        assert not any(policy.allows(o, set()) for o in (delete, move, breaking_update))

    def test_min_probability(self):
        policy = ApprovalPolicy("tax", (AutoApplyRule(scope=S.EDITORIAL),), min_probability=0.8)
        assert policy.allows(
            op(1, T.UPDATE, K.CLASS, S.EDITORIAL, "c", probability=0.8, title="x"), set()
        )
        assert not policy.allows(
            op(1, T.UPDATE, K.CLASS, S.EDITORIAL, "c", probability=0.5, title="x"), set()
        )
        assert not policy.allows(op(1, T.UPDATE, K.CLASS, S.EDITORIAL, "c", title="x"), set())
        lenient = ApprovalPolicy("tax", (AutoApplyRule(scope=S.EDITORIAL),))
        assert lenient.allows(op(1, T.UPDATE, K.CLASS, S.EDITORIAL, "c", title="x"), set())

    def test_no_policy_or_no_rules_applies_nothing(self):
        edit = op(1, T.UPDATE, K.CLASS, S.EDITORIAL, "c", title="x")
        assert auto_apply_ids(None, [edit], lambda o: set()) == []
        assert auto_apply_ids(ApprovalPolicy("tax"), [edit], lambda o: set()) == []

    def test_a_ref_qualifies_only_if_its_create_does(self):
        policy = ApprovalPolicy("tax", (AutoApplyRule(op=T.CREATE, kind=K.INDIVIDUAL),))
        kept_class = op(1, T.CREATE, K.CLASS, S.ADDITIVE, ref="kit", title="Kit")
        on_new_class = op(2, T.CREATE, K.INDIVIDUAL, S.ADDITIVE, ref="a", class_ids=["$kit"])
        plain = op(3, T.CREATE, K.INDIVIDUAL, S.ADDITIVE, ref="b", class_ids=["c1"])
        relationship = op(4, T.CREATE, K.RELATIONSHIP, S.ADDITIVE, source_id="$b")
        chosen = auto_apply_ids(
            policy, [relationship, plain, on_new_class, kept_class], lambda o: set()
        )
        assert chosen == [plain.id]


# ---------------------------------------------------------------- the services


class StubRevertService:
    def revert_with_summary(self, run_id):
        return RevertResult(run_id=run_id, events_reverted=0)


class RunTags:
    def __init__(self):
        self.tags = []

    def __call__(self, event):
        self.tags.append((type(event).__name__, get_current_batch_run_id()))


@pytest.fixture()
def publisher():
    return FakeEventPublisher()


@pytest.fixture()
def ontology(publisher):
    return OntologyService(FakeOntologyRepository(), FakeEmbeddingService(), publisher)


@pytest.fixture()
def policies():
    return FakeApprovalPolicyRepository()


@pytest.fixture()
def service(ontology, policies):
    return ProposalService(
        FakeChangeProposalRepository(),
        ontology,
        ontology._repository,
        StubRevertService(),
        approval_policies=policies,
    )


@pytest.fixture()
def house(ontology):
    taxonomy = ontology.create_taxonomy(title="House")
    scheme = ontology.create_scheme(taxonomy_id=taxonomy.id, title="Life")
    activity = ontology.create_class(scheme.id, "House activity", identifier="house_activity")
    place = ontology.create_class(scheme.id, "Place", identifier="place")
    attic = ontology.create_individual(place.id, "Attic")
    return {
        "taxonomy": taxonomy.id,
        "scheme": scheme.id,
        "activity": activity.id,
        "place": place.id,
        "attic": attic.id,
    }


def house_drafts(house):
    return [
        OperationDraft(
            1, T.CREATE, K.INDIVIDUAL, fields={"class_ids": [house["activity"]], "title": "Dust"}
        ),
        OperationDraft(
            2, T.CREATE, K.INDIVIDUAL, fields={"class_ids": [house["place"]], "title": "Cellar"}
        ),
        OperationDraft(3, T.UPDATE, K.INDIVIDUAL, house["attic"], fields={"description": "Dusty"}),
        OperationDraft(4, T.DELETE, K.INDIVIDUAL, house["attic"]),
    ]


class TestAutoApplyOnPropose:
    def test_matching_operations_apply_under_the_proposal_run(
        self, service, policies, house, ontology, publisher
    ):
        policies.save(ApprovalPolicy.from_rules(house["taxonomy"], HOUSE_RULES))
        tags = RunTags()
        publisher.subscribe(IndividualCreated, tags)
        drafts = house_drafts(house)[:3]  # a delete conflicts with the update

        previous_run = get_current_batch_run_id()
        set_batch_run_context("outer-run")
        try:
            proposal = service.propose(house["taxonomy"], "Chores", drafts, ProposalSource.MCP)
            assert get_current_batch_run_id() == "outer-run"
        finally:
            set_batch_run_context(previous_run)

        statuses = [o.status for o in proposal.operations]
        assert statuses == [
            OperationStatus.APPLIED,
            OperationStatus.PENDING,
            OperationStatus.APPLIED,
        ]
        assert proposal.status is ProposalStatus.OPEN
        dust = ontology.get_individual(proposal.operations[0].result_entity_id)
        assert dust.title == "Dust"
        assert ontology.get_individual(house["attic"]).description == "Dusty"
        assert tags.tags == [("IndividualCreated", proposal.id)]

    def test_deletes_never_auto_apply(self, service, policies, house, ontology):
        policies.save(
            ApprovalPolicy(
                house["taxonomy"], (AutoApplyRule(op=T.DELETE), AutoApplyRule(kind=K.INDIVIDUAL))
            )
        )
        proposal = service.propose(
            house["taxonomy"], "Tidy", [house_drafts(house)[3]], ProposalSource.MCP
        )
        assert proposal.operations[0].status is OperationStatus.PENDING
        assert ontology.get_individual(house["attic"]) is not None

    def test_no_policy_applies_nothing(self, service, house):
        proposal = service.propose(
            house["taxonomy"], "Chores", house_drafts(house)[:3], ProposalSource.MCP
        )
        assert {o.status for o in proposal.operations} == {OperationStatus.PENDING}

    def test_another_taxonomys_policy_does_not_apply(self, service, policies, house, ontology):
        other = ontology.create_taxonomy(title="Garden")
        policies.save(ApprovalPolicy.from_rules(other.id, HOUSE_RULES))
        proposal = service.propose(
            house["taxonomy"], "Chores", house_drafts(house)[:1], ProposalSource.MCP
        )
        assert proposal.operations[0].status is OperationStatus.PENDING

    def test_class_rule_matches_by_id_too(self, service, policies, house):
        policies.save(ApprovalPolicy(house["taxonomy"], (AutoApplyRule(class_key=house["place"]),)))
        proposal = service.propose(
            house["taxonomy"], "Places", house_drafts(house)[1:3], ProposalSource.MCP
        )
        # Seq 2 creates a place; seq 3 edits the attic, which is a place.
        assert {o.status for o in proposal.operations} == {OperationStatus.APPLIED}
        assert proposal.status is ProposalStatus.DONE

    def test_a_create_that_auto_applies_can_be_referenced(
        self, service, policies, house, publisher
    ):
        policies.save(ApprovalPolicy(house["taxonomy"], (AutoApplyRule(op=T.CREATE),)))
        tags = RunTags()
        publisher.subscribe(ClassCreated, tags)
        drafts = [
            OperationDraft(
                1,
                T.CREATE,
                K.CLASS,
                ref="chore",
                fields={"concept_scheme_id": house["scheme"], "title": "Chore"},
            ),
            OperationDraft(
                2, T.CREATE, K.INDIVIDUAL, fields={"class_ids": ["$chore"], "title": "Mop"}
            ),
        ]
        proposal = service.propose(house["taxonomy"], "Chores", drafts, ProposalSource.MCP)
        assert [o.status for o in proposal.operations] == [OperationStatus.APPLIED] * 2
        assert tags.tags == [("ClassCreated", proposal.id)]


class TestApprovalPolicyService:
    def test_get_defaults_to_an_empty_policy_and_set_replaces_it(self, ontology, policies, house):
        svc = ApprovalPolicyService(policies, ontology._repository)
        assert svc.get(house["taxonomy"]) == ApprovalPolicy(house["taxonomy"])

        saved = svc.set(house["taxonomy"], HOUSE_RULES)
        assert svc.get(house["taxonomy"]) == saved
        assert saved.to_rules()["auto_apply"] == HOUSE_RULES["auto_apply"]

        svc.set(house["taxonomy"], {"auto_apply": []})
        assert svc.get(house["taxonomy"]).auto_apply == ()

    def test_unknown_taxonomy(self, ontology, policies):
        svc = ApprovalPolicyService(policies, ontology._repository)
        with pytest.raises(EntityNotFoundError):
            svc.get("nope")
        with pytest.raises(EntityNotFoundError):
            svc.set("nope", HOUSE_RULES)
        assert policies.policies == {}

    def test_invalid_rules_store_nothing(self, ontology, policies, house):
        svc = ApprovalPolicyService(policies, ontology._repository)
        with pytest.raises(ValueError):
            svc.set(house["taxonomy"], {"auto_apply": [{"op": "replace"}]})
        assert policies.policies == {}
