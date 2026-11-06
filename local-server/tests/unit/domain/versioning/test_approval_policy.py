"""Unit tests for approval policies (#1355): parsing, matching, hard rules, auto-apply."""

import logging

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
from domain.versioning.proposal_service import ID_FIELDS, OperationDraft, ProposalService
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
MCP = ProposalSource.MCP

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

    @pytest.mark.parametrize(
        "rule, reason",
        [
            ({"op": "delete"}, "a delete is breaking"),
            ({"op": "move", "kind": "class"}, "a move is breaking"),
            ({"scope": "breaking"}, "breaking operations never auto-apply"),
            ({"kind": "property", "scope": "editorial"}, "property definitions are global"),
            ({"op": "create", "kind": "taxonomy"}, "taxonomy creates never auto-apply"),
        ],
    )
    def test_rules_that_can_never_match_are_refused_by_name(self, rule, reason):
        with pytest.raises(ValueError) as refused:
            ApprovalPolicy.from_rules("tax", {"auto_apply": [{"scope": "editorial"}, rule]})
        assert f"Auto-apply rule {rule} can never match: {reason}" in str(refused.value)

    def test_rules_the_hard_rules_still_allow_are_accepted(self):
        rules = [{"kind": "taxonomy", "scope": "editorial"}, {"op": "update", "kind": "class"}]
        policy = ApprovalPolicy.from_rules("tax", {"auto_apply": rules})
        assert len(policy.auto_apply) == 2


ACTIVITY = {"c-act", "house_activity"}
PLACE = {"c-place", "place"}


ID_NAMES = frozenset(ID_FIELDS)


def everywhere(operation):
    return True


class TestMatching:
    def test_a_rule_matches_when_every_key_it_sets_matches(self):
        policy = ApprovalPolicy(
            "tax", (AutoApplyRule(op=T.CREATE, kind=K.INDIVIDUAL, class_key="house_activity"),)
        )
        create = op(1, T.CREATE, K.INDIVIDUAL, S.ADDITIVE, class_ids=["c-act"])
        assert policy.allows(create, [ACTIVITY], MCP)
        assert not policy.allows(create, [PLACE], MCP)
        update = op(2, T.UPDATE, K.INDIVIDUAL, S.EDITORIAL, target="i1", title="x")
        assert not policy.allows(update, [ACTIVITY], MCP)
        assert ApprovalPolicy("tax", (AutoApplyRule(scope=S.EDITORIAL),)).allows(update, [], MCP)

    def test_a_taxonomy_vision_update_is_never_allowed(self):
        policy = ApprovalPolicy(
            "tax", (AutoApplyRule(scope=S.EDITORIAL), AutoApplyRule(kind=K.TAXONOMY))
        )
        vision = op(1, T.UPDATE, K.TAXONOMY, S.EDITORIAL, target="tax", vision="New charter")
        both = op(2, T.UPDATE, K.TAXONOMY, S.EDITORIAL, target="tax", title="H", vision=None)
        title = op(3, T.UPDATE, K.TAXONOMY, S.EDITORIAL, target="tax", title="Home")
        assert not policy.allows(vision, [], MCP)
        assert not policy.allows(both, [], MCP)
        assert policy.allows(title, [], MCP)

    def test_every_class_must_be_covered(self):
        activity_only = ApprovalPolicy(
            "tax", (AutoApplyRule(op=T.CREATE, kind=K.INDIVIDUAL, class_key="house_activity"),)
        )
        create = op(1, T.CREATE, K.INDIVIDUAL, S.ADDITIVE, class_ids=["c-act", "c-place"])
        assert not activity_only.allows(create, [ACTIVITY, PLACE], MCP)
        assert not activity_only.allows(create, [ACTIVITY, set()], MCP)  # a "$ref" class
        assert not activity_only.allows(create, [], MCP)

        both = ApprovalPolicy(
            "tax",
            (
                AutoApplyRule(op=T.CREATE, class_key="house_activity"),
                AutoApplyRule(kind=K.INDIVIDUAL, class_key="c-place"),
            ),
        )
        assert both.allows(create, [ACTIVITY, PLACE], MCP)

    def test_a_rule_without_a_class_covers_every_class(self):
        policy = ApprovalPolicy(
            "tax",
            (
                AutoApplyRule(class_key="house_activity"),
                AutoApplyRule(op=T.CREATE, kind=K.INDIVIDUAL),
            ),
        )
        create = op(1, T.CREATE, K.INDIVIDUAL, S.ADDITIVE, class_ids=["c-act", "c-place"])
        assert policy.allows(create, [ACTIVITY, PLACE, set()], MCP)

    def test_a_class_rule_covers_only_operations_its_other_keys_match(self):
        policy = ApprovalPolicy(
            "tax",
            (
                AutoApplyRule(op=T.CREATE, class_key="house_activity"),
                AutoApplyRule(op=T.UPDATE, class_key="place"),
            ),
        )
        create = op(1, T.CREATE, K.INDIVIDUAL, S.ADDITIVE, class_ids=["c-act", "c-place"])
        assert not policy.allows(create, [ACTIVITY, PLACE], MCP)

    def test_hard_rules_beat_any_rule(self):
        policy = ApprovalPolicy(
            "tax",
            (
                AutoApplyRule(op=T.DELETE),
                AutoApplyRule(scope=S.BREAKING),
                AutoApplyRule(op=T.MOVE),
                AutoApplyRule(kind=K.TAXONOMY),
            ),
        )
        delete = op(1, T.DELETE, K.INDIVIDUAL, S.BREAKING, target="i1")
        move = op(2, T.MOVE, K.CLASS, S.BREAKING, target="c1", parent_class_id=None)
        breaking_update = op(3, T.UPDATE, K.CLASS, S.BREAKING, target="c1", identifier="x")
        new_taxonomy = op(4, T.CREATE, K.TAXONOMY, S.ADDITIVE, title="Other")
        assert not any(
            policy.allows(o, [], MCP) for o in (delete, move, breaking_update, new_taxonomy)
        )

    def test_min_probability(self):
        policy = ApprovalPolicy("tax", (AutoApplyRule(scope=S.EDITORIAL),), min_probability=0.8)
        assert policy.allows(
            op(1, T.UPDATE, K.CLASS, S.EDITORIAL, "c", probability=0.8, title="x"), [], MCP
        )
        assert not policy.allows(
            op(1, T.UPDATE, K.CLASS, S.EDITORIAL, "c", probability=0.5, title="x"), [], MCP
        )
        assert not policy.allows(op(1, T.UPDATE, K.CLASS, S.EDITORIAL, "c", title="x"), [], MCP)
        lenient = ApprovalPolicy("tax", (AutoApplyRule(scope=S.EDITORIAL),))
        assert lenient.allows(op(1, T.UPDATE, K.CLASS, S.EDITORIAL, "c", title="x"), [], MCP)

    def test_a_bundle_import_is_exempt_from_min_probability_alone(self):
        policy = ApprovalPolicy("tax", (AutoApplyRule(scope=S.EDITORIAL),), min_probability=0.8)
        edit = op(1, T.UPDATE, K.CLASS, S.EDITORIAL, "c", title="x")
        assert policy.allows(edit, [], ProposalSource.BUNDLE)
        assert not policy.allows(edit, [], ProposalSource.MCP)
        assert not policy.allows(edit, [], ProposalSource.CHAT)
        # Every other rule still applies to it.
        additive = op(2, T.CREATE, K.CLASS, S.ADDITIVE, ref="c2", title="New")
        delete = op(3, T.DELETE, K.CLASS, S.BREAKING, "c")
        vision = op(4, T.UPDATE, K.TAXONOMY, S.EDITORIAL, "tax", vision="v")
        for other in (additive, delete, vision):
            assert not policy.allows(other, [], ProposalSource.BUNDLE)

    def test_no_policy_or_no_rules_applies_nothing(self):
        edit = op(1, T.UPDATE, K.CLASS, S.EDITORIAL, "c", title="x")
        assert (
            auto_apply_ids(None, [edit], lambda o: [], everywhere, id_fields=ID_NAMES, source=MCP)
            == []
        )
        policy = ApprovalPolicy("tax")
        assert (
            auto_apply_ids(policy, [edit], lambda o: [], everywhere, id_fields=ID_NAMES, source=MCP)
            == []
        )

    def test_only_operations_inside_the_taxonomy_qualify(self):
        policy = ApprovalPolicy("tax", (AutoApplyRule(scope=S.EDITORIAL),))
        inside = op(1, T.UPDATE, K.CLASS, S.EDITORIAL, "c-in", title="x")
        outside = op(2, T.UPDATE, K.CLASS, S.EDITORIAL, "c-out", title="y")
        chosen = auto_apply_ids(
            policy,
            [inside, outside],
            lambda o: [],
            lambda o: o.target_id == "c-in",
            id_fields=ID_NAMES,
            source=MCP,
        )
        assert chosen == [inside.id]

    def test_a_ref_qualifies_only_if_its_create_does(self):
        policy = ApprovalPolicy("tax", (AutoApplyRule(op=T.CREATE, kind=K.INDIVIDUAL),))
        kept_class = op(1, T.CREATE, K.CLASS, S.ADDITIVE, ref="kit", title="Kit")
        on_new_class = op(2, T.CREATE, K.INDIVIDUAL, S.ADDITIVE, ref="a", class_ids=["$kit"])
        plain = op(3, T.CREATE, K.INDIVIDUAL, S.ADDITIVE, ref="b", class_ids=["c1"])
        relationship = op(4, T.CREATE, K.RELATIONSHIP, S.ADDITIVE, source_id="$b")
        chosen = auto_apply_ids(
            policy,
            [relationship, plain, on_new_class, kept_class],
            lambda o: [],
            everywhere,
            id_fields=ID_NAMES,
            source=MCP,
        )
        assert chosen == [plain.id]

    def test_text_that_starts_with_a_dollar_is_not_a_ref(self):
        policy = ApprovalPolicy("tax", (AutoApplyRule(scope=S.EDITORIAL),))
        priced = op(1, T.UPDATE, K.INDIVIDUAL, S.EDITORIAL, "i1", title="$5 attic")
        noted = op(2, T.UPDATE, K.INDIVIDUAL, S.EDITORIAL, "i2", description="$x marks it")
        chosen = auto_apply_ids(
            policy, [priced, noted], lambda o: [], everywhere, id_fields=ID_NAMES, source=MCP
        )
        assert chosen == [priced.id, noted.id]


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

    def test_a_vision_change_never_auto_applies(self, service, policies, house, ontology):
        """The vision is the charter proposals are judged against; a person decides."""
        policies.save(
            ApprovalPolicy(
                house["taxonomy"],
                (AutoApplyRule(scope=S.EDITORIAL), AutoApplyRule(kind=K.TAXONOMY)),
            )
        )
        before = ontology.get_taxonomy(house["taxonomy"])
        drafts = [
            OperationDraft(
                1, T.UPDATE, K.TAXONOMY, house["taxonomy"], fields={"vision": "Anything"}
            ),
            OperationDraft(
                2, T.UPDATE, K.TAXONOMY, house["taxonomy"], fields={"description": "Our home"}
            ),
        ]

        proposal = service.propose(house["taxonomy"], "Recharter", drafts, ProposalSource.MCP)

        vision, description = proposal.operations
        assert vision.scope is S.EDITORIAL
        assert vision.status is OperationStatus.PENDING
        assert description.status is OperationStatus.APPLIED
        after = ontology.get_taxonomy(house["taxonomy"])
        assert after.vision == before.vision
        assert after.description == "Our home"

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


@pytest.fixture()
def other(ontology):
    taxonomy = ontology.create_taxonomy(title="Other")
    scheme = ontology.create_scheme(taxonomy_id=taxonomy.id, title="Misc")
    thing = ontology.create_class(scheme.id, "Thing", identifier="thing")
    widget = ontology.create_individual(thing.id, "Widget")
    return {"taxonomy": taxonomy.id, "scheme": scheme.id, "thing": thing.id, "widget": widget.id}


def statuses(proposal):
    return {o.seq: o.status for o in proposal.operations}


PENDING, APPLIED, FAILED = OperationStatus.PENDING, OperationStatus.APPLIED, OperationStatus.FAILED


class TestAutoApplyStaysInsideTheTaxonomy:
    def test_a_policy_never_changes_another_taxonomy(
        self, service, policies, house, other, ontology
    ):
        policies.save(
            ApprovalPolicy(
                house["taxonomy"], (AutoApplyRule(scope=S.EDITORIAL), AutoApplyRule(op=T.CREATE))
            )
        )
        drafts = [
            OperationDraft(1, T.UPDATE, K.INDIVIDUAL, other["widget"], fields={"title": "Gadget"}),
            OperationDraft(
                2,
                T.CREATE,
                K.CLASS,
                fields={"concept_scheme_id": other["scheme"], "title": "Gizmo"},
            ),
            OperationDraft(3, T.CREATE, K.TAXONOMY, fields={"title": "Third"}),
            OperationDraft(
                4, T.UPDATE, K.TAXONOMY, other["taxonomy"], fields={"title": "Elsewhere"}
            ),
            OperationDraft(
                5,
                T.CREATE,
                K.INDIVIDUAL,
                fields={"class_ids": [house["place"], other["thing"]], "title": "Shed"},
            ),
            OperationDraft(6, T.UPDATE, K.INDIVIDUAL, house["attic"], fields={"title": "Loft"}),
            OperationDraft(7, T.UPDATE, K.TAXONOMY, house["taxonomy"], fields={"title": "Home"}),
        ]

        proposal = service.propose(house["taxonomy"], "Mixed", drafts, ProposalSource.MCP)

        assert statuses(proposal) == {
            1: PENDING,
            2: PENDING,
            3: PENDING,
            4: PENDING,
            5: PENDING,
            6: APPLIED,
            7: APPLIED,
        }
        assert ontology.get_individual(other["widget"]).title == "Widget"
        assert "Third" not in [t.title for t in ontology.list_taxonomies()]

    def test_property_definitions_are_global(self, service, policies, house, ontology):
        near = ontology.create_property_definition("near", "near")
        hall = ontology.create_individual(house["place"], "Hall")
        policies.save(
            ApprovalPolicy(
                house["taxonomy"], (AutoApplyRule(scope=S.EDITORIAL), AutoApplyRule(op=T.CREATE))
            )
        )
        drafts = [
            OperationDraft(1, T.UPDATE, K.PROPERTY, near.id, fields={"title": "next to"}),
            OperationDraft(
                2, T.CREATE, K.PROPERTY, fields={"identifier": "under", "title": "under"}
            ),
            OperationDraft(
                3,
                T.CREATE,
                K.RELATIONSHIP,
                fields={
                    "source_id": house["attic"],
                    "target_id": hall.id,
                    "property_definition_id": near.id,
                },
            ),
        ]
        proposal = service.propose(house["taxonomy"], "Links", drafts, ProposalSource.MCP)
        assert statuses(proposal) == {1: PENDING, 2: PENDING, 3: APPLIED}


def test_an_editorial_title_starting_with_a_dollar_auto_applies(service, policies, house, ontology):
    policies.save(ApprovalPolicy(house["taxonomy"], (AutoApplyRule(scope=S.EDITORIAL),)))
    drafts = [
        OperationDraft(1, T.UPDATE, K.INDIVIDUAL, house["attic"], fields={"title": "$5 attic"})
    ]
    proposal = service.propose(house["taxonomy"], "Price", drafts, ProposalSource.MCP)
    assert statuses(proposal) == {1: APPLIED}
    assert ontology.get_individual(house["attic"]).title == "$5 attic"


class TestEveryClassIsCovered:
    RULE = {"auto_apply": [{"op": "create", "kind": "individual", "class": "house_activity"}]}

    def test_a_create_typed_by_an_uncovered_class_waits(self, service, policies, house):
        policies.save(ApprovalPolicy.from_rules(house["taxonomy"], self.RULE))
        drafts = [
            OperationDraft(
                1,
                T.CREATE,
                K.INDIVIDUAL,
                fields={"class_ids": [house["activity"], house["place"]], "title": "Garage"},
            ),
            OperationDraft(
                2,
                T.CREATE,
                K.INDIVIDUAL,
                fields={"class_ids": [house["activity"]], "title": "Dust"},
            ),
        ]
        proposal = service.propose(house["taxonomy"], "Chores", drafts, ProposalSource.MCP)
        assert statuses(proposal) == {1: PENDING, 2: APPLIED}

    def test_an_update_counts_current_and_added_classes(self, service, policies, house, ontology):
        dusting = ontology.create_individual(house["activity"], "Dusting")
        sweeping = ontology.create_individual(house["activity"], "Sweeping")
        policies.save(
            ApprovalPolicy.from_rules(
                house["taxonomy"],
                {"auto_apply": [{"op": "update", "kind": "individual", "class": "house_activity"}]},
            )
        )
        drafts = [
            OperationDraft(
                1,
                T.UPDATE,
                K.INDIVIDUAL,
                dusting.id,
                fields={"class_ids": [house["activity"], house["place"]]},
            ),
            OperationDraft(2, T.UPDATE, K.INDIVIDUAL, house["attic"], fields={"title": "Loft"}),
            OperationDraft(3, T.UPDATE, K.INDIVIDUAL, sweeping.id, fields={"title": "Sweep"}),
        ]
        proposal = service.propose(house["taxonomy"], "Retype", drafts, ProposalSource.MCP)
        # Seq 1 would make Dusting a place too, and the attic is a place already.
        assert statuses(proposal) == {1: PENDING, 2: PENDING, 3: APPLIED}


class BrokenPolicies:
    """A policy store whose stored rules no longer parse."""

    def get(self, taxonomy_id):
        return ApprovalPolicy.from_rules(taxonomy_id, {"auto_apply": [{"op": "replace"}]})

    def save(self, policy):
        return policy


def _raise_disk_error(*args, **kwargs):
    raise RuntimeError("disk")


class TestAutoApplyNeverFailsThePropose:
    def test_a_policy_that_does_not_parse_leaves_everything_pending(self, ontology, house, caplog):
        service = ProposalService(
            FakeChangeProposalRepository(),
            ontology,
            ontology._repository,
            StubRevertService(),
            approval_policies=BrokenPolicies(),
        )
        with caplog.at_level(logging.ERROR):
            proposal = service.propose(
                house["taxonomy"], "Chores", house_drafts(house)[:1], ProposalSource.MCP
            )
        assert statuses(proposal) == {1: PENDING}
        assert service.get(proposal.id).status is ProposalStatus.OPEN
        assert "Auto-apply of proposal" in caplog.text

    def test_an_error_inside_an_operation_fails_only_that_operation(
        self, service, policies, house, ontology, monkeypatch
    ):
        policies.save(ApprovalPolicy(house["taxonomy"], (AutoApplyRule(op=T.CREATE),)))
        monkeypatch.setattr(ontology, "create_individual", _raise_disk_error)
        proposal = service.propose(
            house["taxonomy"], "Chores", house_drafts(house)[:1], ProposalSource.MCP
        )
        assert statuses(proposal) == {1: FAILED}
        assert proposal.operations[0].reason == "error: disk"
        assert proposal.status is ProposalStatus.OPEN

    def test_a_storage_error_while_applying_returns_the_stored_proposal(
        self, ontology, policies, house, caplog
    ):
        proposals = FakeChangeProposalRepository()
        service = ProposalService(
            proposals,
            ontology,
            ontology._repository,
            StubRevertService(),
            approval_policies=policies,
        )
        policies.save(ApprovalPolicy(house["taxonomy"], (AutoApplyRule(scope=S.EDITORIAL),)))
        proposals.save_operations = _raise_disk_error
        with caplog.at_level(logging.ERROR):
            proposal = service.propose(
                house["taxonomy"], "Edit", house_drafts(house)[2:3], ProposalSource.MCP
            )
        assert proposal.id == service.get(proposal.id).id
        assert proposal.status is ProposalStatus.OPEN
        assert "disk" in caplog.text


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


# ------------------------------------------- class rules follow inheritance (#1414)


@pytest.fixture()
def chores(ontology, house):
    """Under House activity: Cleaning, and under that Dusting; a Resource class beside them."""
    cleaning = ontology.create_class(
        house["scheme"], "Cleaning", identifier="cleaning", parent_class_id=house["activity"]
    )
    dusting = ontology.create_class(
        house["scheme"], "Dusting", identifier="dusting", parent_class_id=cleaning.id
    )
    resource = ontology.create_class(house["scheme"], "Resource", identifier="resource")
    mop = ontology.create_individual(dusting.id, "Mop the floor")
    cook = ontology.create_individual(house["activity"], "Cook")
    broom = ontology.create_individual(resource.id, "Broom")
    requires = ontology.create_property_definition(
        "requires", "requires", domain_class_id=house["activity"], range_class_id=resource.id
    )
    follows = ontology.create_property_definition("follows", "follows")
    return {
        "cleaning": cleaning.id,
        "dusting": dusting.id,
        "resource": resource.id,
        "mop": mop.id,
        "cook": cook.id,
        "broom": broom.id,
        "requires": requires.id,
        "follows": follows.id,
    }


def rules(house, *rule_dicts):
    return ApprovalPolicy.from_rules(house["taxonomy"], {"auto_apply": list(rule_dicts)})


class TestClassRulesFollowInheritance:
    def test_an_individual_of_a_subclass_is_covered_by_its_ancestors_rule(
        self, service, policies, house, chores
    ):
        policies.save(ApprovalPolicy.from_rules(house["taxonomy"], HOUSE_RULES))
        drafts = [
            OperationDraft(
                1,
                T.CREATE,
                K.INDIVIDUAL,
                fields={"class_ids": [chores["dusting"]], "title": "Dust"},
            ),
            OperationDraft(
                2,
                T.CREATE,
                K.INDIVIDUAL,
                fields={"class_ids": [chores["resource"]], "title": "Bucket"},
            ),
        ]
        proposal = service.propose(house["taxonomy"], "Chores", drafts, ProposalSource.MCP)
        # Dusting is a Cleaning, which is a House activity; a Resource is not.
        assert statuses(proposal) == {1: APPLIED, 2: PENDING}

    def test_an_update_of_a_subclass_individual_is_covered_by_identifier_or_id(
        self, service, policies, house, chores
    ):
        drafts = [OperationDraft(1, T.UPDATE, K.INDIVIDUAL, chores["mop"], fields={"title": "Mop"})]
        for key in ("house_activity", house["activity"]):
            policies.save(rules(house, {"op": "update", "kind": "individual", "class": key}))
            proposal = service.propose(house["taxonomy"], "Rename", drafts, ProposalSource.MCP)
            assert statuses(proposal) == {1: APPLIED}

    def test_a_rule_on_a_subclass_doesnt_cover_its_parent(self, service, policies, house, chores):
        policies.save(rules(house, {"op": "update", "kind": "individual", "class": "cleaning"}))
        drafts = [
            OperationDraft(1, T.UPDATE, K.INDIVIDUAL, chores["cook"], fields={"title": "Bake"}),
            OperationDraft(2, T.UPDATE, K.INDIVIDUAL, chores["mop"], fields={"title": "Mop"}),
        ]
        proposal = service.propose(house["taxonomy"], "Rename", drafts, ProposalSource.MCP)
        assert statuses(proposal) == {1: PENDING, 2: APPLIED}

    def test_a_class_create_matches_by_its_proposed_parent(
        self, service, policies, house, chores, ontology
    ):
        policies.save(rules(house, {"op": "create", "kind": "class", "class": "house_activity"}))
        scheme = house["scheme"]
        drafts = [
            OperationDraft(
                1,
                T.CREATE,
                K.CLASS,
                ref="laundry",
                fields={
                    "concept_scheme_id": scheme,
                    "title": "Laundry",
                    "parent_class_id": house["activity"],
                },
            ),
            OperationDraft(
                2,
                T.CREATE,
                K.CLASS,
                fields={
                    "concept_scheme_id": scheme,
                    "title": "Polishing",
                    "parent_class_id": chores["dusting"],
                },
            ),
            # Under a class the proposal creates, itself under House activity.
            OperationDraft(
                3,
                T.CREATE,
                K.CLASS,
                fields={
                    "concept_scheme_id": scheme,
                    "title": "Ironing",
                    "parent_class_id": "$laundry",
                },
            ),
            OperationDraft(
                4,
                T.CREATE,
                K.CLASS,
                fields={
                    "concept_scheme_id": scheme,
                    "title": "Tool",
                    "parent_class_id": chores["resource"],
                },
            ),
            # At the top of the scheme: no parent, so no class rule names it.
            OperationDraft(
                5, T.CREATE, K.CLASS, fields={"concept_scheme_id": scheme, "title": "Mood"}
            ),
        ]
        proposal = service.propose(house["taxonomy"], "Classes", drafts, ProposalSource.MCP)

        assert statuses(proposal) == {1: APPLIED, 2: APPLIED, 3: APPLIED, 4: PENDING, 5: PENDING}
        ironing = ontology.get_class(proposal.operations[2].result_entity_id)
        assert ironing.parent_class_id == proposal.operations[0].result_entity_id

    def test_a_relationship_between_instances_of_a_named_class(
        self, service, policies, house, chores
    ):
        policies.save(
            rules(house, {"op": "create", "kind": "relationship", "class": "house_activity"})
        )
        follows = chores["follows"]
        drafts = [
            OperationDraft(
                1,
                T.CREATE,
                K.RELATIONSHIP,
                fields={
                    "source_id": chores["mop"],
                    "target_id": chores["cook"],
                    "property_definition_id": follows,
                },
            ),
            # The target is a Resource: not covered.
            OperationDraft(
                2,
                T.CREATE,
                K.RELATIONSHIP,
                fields={
                    "source_id": chores["cook"],
                    "target_id": chores["broom"],
                    "property_definition_id": chores["requires"],
                },
            ),
            # A class end is its own class.
            OperationDraft(
                3,
                T.CREATE,
                K.RELATIONSHIP,
                fields={
                    "source_id": chores["cleaning"],
                    "target_id": house["activity"],
                    "property_definition_id": follows,
                },
            ),
        ]
        proposal = service.propose(house["taxonomy"], "Links", drafts, ProposalSource.MCP)
        assert statuses(proposal) == {1: APPLIED, 2: PENDING, 3: APPLIED}

    def test_both_ends_covered_by_two_rules_and_a_new_individual_end(
        self, service, policies, house, chores
    ):
        policies.save(
            rules(
                house,
                {"op": "create", "class": "house_activity"},
                {"op": "create", "kind": "relationship", "class": "resource"},
            )
        )
        drafts = [
            OperationDraft(
                1,
                T.CREATE,
                K.INDIVIDUAL,
                ref="sweep",
                fields={"class_ids": [chores["cleaning"]], "title": "Sweep"},
            ),
            OperationDraft(
                2,
                T.CREATE,
                K.RELATIONSHIP,
                fields={
                    "source_id": "$sweep",
                    "target_id": chores["broom"],
                    "property_definition_id": chores["requires"],
                },
            ),
        ]
        proposal = service.propose(house["taxonomy"], "Kit", drafts, ProposalSource.MCP)
        assert statuses(proposal) == {1: APPLIED, 2: APPLIED}

    def test_the_house_policy_after_the_change(self, service, policies, house, chores):
        """
        House's policy (activity creates and editorial changes auto-apply): a kit's
        resources and `requires` edges still wait, activities of a subclass now apply.
        """
        policies.save(ApprovalPolicy.from_rules(house["taxonomy"], HOUSE_RULES))
        drafts = [
            OperationDraft(
                1,
                T.CREATE,
                K.INDIVIDUAL,
                ref="vacuum",
                fields={"class_ids": [chores["resource"]], "title": "Vacuum"},
            ),
            OperationDraft(
                2,
                T.CREATE,
                K.RELATIONSHIP,
                fields={
                    "source_id": chores["cook"],
                    "target_id": chores["broom"],
                    "property_definition_id": chores["requires"],
                },
            ),
            OperationDraft(
                3,
                T.CREATE,
                K.INDIVIDUAL,
                fields={"class_ids": [chores["cleaning"]], "title": "Scrub"},
            ),
            OperationDraft(4, T.UPDATE, K.INDIVIDUAL, chores["broom"], fields={"title": "Brush"}),
            OperationDraft(
                5,
                T.CREATE,
                K.CLASS,
                fields={
                    "concept_scheme_id": house["scheme"],
                    "title": "Gardening",
                    "parent_class_id": house["activity"],
                },
            ),
        ]
        proposal = service.propose(house["taxonomy"], "Kits", drafts, ProposalSource.MCP)
        assert statuses(proposal) == {1: PENDING, 2: PENDING, 3: APPLIED, 4: APPLIED, 5: PENDING}


def test_a_subclass_rule_is_honoured_by_the_dry_run_verdict_and_a_real_propose(
    service, policies, house, chores
):
    """The dry run's verdict and propose share _policy_auto_apply_ids (#1414 with #1425)."""
    policies.save(ApprovalPolicy.from_rules(house["taxonomy"], HOUSE_RULES))
    drafts = [
        OperationDraft(
            1, T.CREATE, K.INDIVIDUAL, fields={"class_ids": [chores["dusting"]], "title": "Dust"}
        ),
        OperationDraft(
            2, T.CREATE, K.INDIVIDUAL, fields={"class_ids": [chores["resource"]], "title": "Pail"}
        ),
    ]

    dry = service.propose(house["taxonomy"], "Chores", drafts, ProposalSource.MCP, dry_run=True)
    verdict = service.auto_apply_operation_ids(dry)
    assert [o.seq for o in dry.operations if o.id in verdict] == [1]

    proposal = service.propose(house["taxonomy"], "Chores", drafts, ProposalSource.MCP)
    assert statuses(proposal) == {1: APPLIED, 2: PENDING}
