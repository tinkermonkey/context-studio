"""
Unit tests for the proposal tools (#1357) over a fake ProposalService: argument
mapping, result shapes, validation failures as fixable results, and size caps.
"""

import json
from datetime import datetime, timezone

import pytest

from adapters.chat.proposal_tools import (
    CLIPPED_TEXT_CHARS,
    MAX_BLOCKER_EDGES,
    MAX_OPERATIONS,
    MAX_PROPOSAL_CHARS,
    OPERATION_SCHEMA,
    build_proposal_tools,
)
from domain.chat.value_objects import EntityRef
from domain.versioning.exceptions import (
    ChangeProposalNotFoundError,
    OperationError,
    ProposalValidationError,
)
from domain.versioning.in_use import (
    BlockingEdge,
    ChainLink,
    ClassEnd,
    DeleteBlockers,
    EdgeEnd,
    PairMatch,
    ReplacementCheck,
    ReplacementType,
)
from domain.versioning.proposals import (
    ChangeProposal,
    ChangeScope,
    OperationKind,
    OperationStatus,
    OperationType,
    ProposalSource,
    ProposalStatus,
    ProposedOperation,
)

TAXONOMY = "tax-1"
CREATED = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)

TOOL_NAMES = ["propose_changes", "get_proposal", "list_proposals"]
FORBIDDEN = ("accept", "reject", "apply", "revert", "policy", "approve", "decide")


def make_operation(seq, status=OperationStatus.PENDING, **kwargs):
    defaults = dict(
        op=OperationType.UPDATE,
        kind=OperationKind.CLASS,
        target_id=f"cls-{seq}",
        fields={"description": f"Description {seq}"},
        scope=ChangeScope.EDITORIAL,
    )
    defaults.update(kwargs)
    return ProposedOperation(seq=seq, status=status, **defaults)


def make_proposal(operations, status=ProposalStatus.OPEN, proposal_id="prop-1"):
    return ChangeProposal(
        id=proposal_id,
        taxonomy_id=TAXONOMY,
        title="Clarify classes",
        source=ProposalSource.MCP,
        created_at=CREATED,
        rationale="Better definitions",
        status=status,
        operations=list(operations),
    )


class FakeProposalService:
    """Records calls; answers with canned proposals or raises a canned error."""

    def __init__(
        self,
        proposal=None,
        error=None,
        stale=frozenset(),
        listed=(),
        total=0,
        checks=None,
        blockers=None,
        auto=(),
    ):
        self.proposal = proposal
        self.checks = checks or {}
        self.blockers = blockers or {}
        self.auto = list(auto)
        self.dry_runs = []
        self.error = error
        self.stale = set(stale)
        self.listed = list(listed)
        self.total = total
        self.calls = []

    def propose(
        self,
        taxonomy_id,
        title,
        operations,
        source,
        rationale=None,
        source_detail=None,
        dry_run=False,
    ):
        self.calls.append(("propose", taxonomy_id, title, list(operations), source, rationale))
        self.dry_runs.append(dry_run)
        if self.error is not None:
            raise self.error
        return self.proposal

    def get(self, proposal_id):
        self.calls.append(("get", proposal_id))
        if self.proposal is None or self.proposal.id != proposal_id:
            raise ChangeProposalNotFoundError(proposal_id)
        return self.proposal

    def stale_operation_ids(self, proposal):
        return self.stale

    def replacement_checks(self, proposal):
        return self.checks

    def in_use_blockers(self, proposal):
        return self.blockers

    def type_usage(self, proposal):
        return {}

    def auto_apply_operation_ids(self, proposal):
        return self.auto

    def list_proposals(self, taxonomy_id=None, status=None, source=None, limit=50, offset=0):
        self.calls.append(("list", taxonomy_id, status, source, limit, offset))
        return self.listed

    def count_proposals(self, taxonomy_id=None, status=None, source=None):
        return self.total


def tools_for(service, source=ProposalSource.MCP):
    return {t.spec.name: t for t in build_proposal_tools(service, source)}


async def call(service, name, source=ProposalSource.MCP, **args):
    outcome = await tools_for(service, source)[name].execute(args)
    return outcome, json.loads(outcome.content)


def update_op(seq, **extra):
    return {
        "seq": seq,
        "op": "update",
        "kind": "class",
        "target_id": f"cls-{seq}",
        "fields": {"description": f"Description {seq}"},
        **extra,
    }


# ============================================================================
# The tool set
# ============================================================================


def test_tools_propose_and_follow_only():
    tools = build_proposal_tools(FakeProposalService(), ProposalSource.CHAT)

    names = [t.spec.name for t in tools]
    assert names == TOOL_NAMES
    for name in names:
        assert not any(word in name for word in FORBIDDEN)
    for tool in tools:
        assert tool.spec.description
        assert tool.spec.input_schema["type"] == "object"


def test_propose_schema_defines_every_operation_field():
    tool = tools_for(FakeProposalService())["propose_changes"]
    schema = tool.spec.input_schema

    assert schema["required"] == ["taxonomy_id", "title", "operations"]
    operations = schema["properties"]["operations"]
    assert operations["minItems"] == 1 and operations["maxItems"] == MAX_OPERATIONS == 200
    assert operations["items"] is OPERATION_SCHEMA
    assert set(OPERATION_SCHEMA["properties"]) == {
        "seq",
        "op",
        "kind",
        "target_id",
        "ref",
        "fields",
        "rationale",
        "evidence",
        "probability",
        "replacement",
    }
    assert OPERATION_SCHEMA["required"] == ["seq", "op", "kind"]
    assert OPERATION_SCHEMA["properties"]["op"]["enum"] == [t.value for t in OperationType]
    assert OPERATION_SCHEMA["properties"]["kind"]["enum"] == [k.value for k in OperationKind]
    probability = OPERATION_SCHEMA["properties"]["probability"]
    assert (probability["minimum"], probability["maximum"]) == (0, 1)


def test_propose_description_has_a_field_guide_for_every_kind():
    description = tools_for(FakeProposalService())["propose_changes"].spec.description

    for kind in OperationKind:
        assert f"- {kind.value}: create " in description
    assert "concept_scheme_id*, title*" in description
    assert '"$<ref>"' in description
    assert "vision" in description


# ============================================================================
# propose_changes
# ============================================================================


class TestProposeChanges:
    async def test_maps_arguments_to_drafts_with_the_tool_source(self):
        service = FakeProposalService(proposal=make_proposal([make_operation(1)]))

        await call(
            service,
            "propose_changes",
            source=ProposalSource.CHAT,
            taxonomy_id=TAXONOMY,
            title="Clarify classes",
            rationale="Better definitions",
            operations=[
                update_op(
                    1,
                    rationale="Vaguer than the vision allows",
                    evidence=[{"quote": "An element is a named fact"}],
                    probability=0.8,
                ),
                {
                    "seq": 2,
                    "op": "create",
                    "kind": "class",
                    "ref": "kit",
                    "fields": {"concept_scheme_id": "s-1", "title": "Kit"},
                },
            ],
        )

        _, taxonomy_id, title, drafts, source, rationale = service.calls[0]
        assert (taxonomy_id, title, source, rationale) == (
            TAXONOMY,
            "Clarify classes",
            ProposalSource.CHAT,
            "Better definitions",
        )
        first, second = drafts
        assert (first.seq, first.op, first.kind, first.target_id) == (1, "update", "class", "cls-1")
        assert first.fields == {"description": "Description 1"}
        assert first.rationale == "Vaguer than the vision allows"
        assert first.evidence == [{"quote": "An element is a named fact"}]
        assert first.probability == 0.8
        assert (second.ref, second.target_id) == ("kit", None)

    async def test_pending_result_has_status_scope_and_review_link_ref(self):
        proposal = make_proposal(
            [
                make_operation(1),
                make_operation(2, op=OperationType.DELETE, fields={}, scope=ChangeScope.BREAKING),
            ]
        )
        service = FakeProposalService(proposal=proposal)

        outcome, result = await call(
            service,
            "propose_changes",
            taxonomy_id=TAXONOMY,
            title="Clarify classes",
            operations=[
                update_op(1),
                {"seq": 2, "op": "delete", "kind": "class", "target_id": "c"},
            ],
        )

        assert outcome.is_error is False
        assert outcome.entities == (EntityRef("prop-1", "proposal", "Clarify classes"),)
        assert result["stored"] is True
        assert result["id"] == "prop-1"
        assert result["kind"] == "proposal"
        assert result["status"] == "open"
        assert result["counts"] == {"pending": 2, "applied": 0, "rejected": 0, "failed": 0}
        assert result["operations"] == [
            {"seq": 1, "status": "pending", "scope": "editorial"},
            {"seq": 2, "status": "pending", "scope": "breaking"},
        ]
        assert "2 pending" in result["next"] and "person reviews" in result["next"]
        assert "pending" in outcome.summary

    async def test_operations_applied_by_policy_carry_their_entity(self):
        proposal = make_proposal(
            [
                make_operation(1, OperationStatus.APPLIED, result_entity_id="cls-1"),
                make_operation(
                    2,
                    OperationStatus.FAILED,
                    reason="target_changed: description changed since proposed",
                ),
            ]
        )
        service = FakeProposalService(proposal=proposal)

        _, result = await call(
            service,
            "propose_changes",
            taxonomy_id=TAXONOMY,
            title="t",
            operations=[update_op(1), update_op(2)],
        )

        assert result["operations"] == [
            {"seq": 1, "status": "applied", "scope": "editorial", "result_entity_id": "cls-1"},
            {
                "seq": 2,
                "status": "failed",
                "scope": "editorial",
                "reason": "target_changed: description changed since proposed",
            },
        ]
        assert "approval policy" in result["next"]
        assert "pending" not in result["next"]

    async def test_all_applied_says_nothing_is_pending(self):
        proposal = make_proposal(
            [make_operation(1, OperationStatus.APPLIED, result_entity_id="cls-1")],
            status=ProposalStatus.DONE,
        )

        _, result = await call(
            FakeProposalService(proposal=proposal),
            "propose_changes",
            taxonomy_id=TAXONOMY,
            title="t",
            operations=[update_op(1)],
        )

        assert result["status"] == "done"
        assert result["next"] == "1 applied under the taxonomy's approval policy."

    async def test_validation_errors_are_fixable_entries_not_tool_errors(self):
        error = ProposalValidationError(
            [
                OperationError(None, "taxonomy_not_found", "No taxonomy tax-9"),
                OperationError(2, "target_not_found", "No class cls-2"),
                OperationError(3, "unknown_field", "A class update can't set colour"),
            ]
        )
        service = FakeProposalService(error=error)

        outcome, result = await call(
            service,
            "propose_changes",
            taxonomy_id="tax-9",
            title="t",
            operations=[update_op(1), update_op(2), update_op(3)],
        )

        assert outcome.is_error is False
        assert outcome.entities == ()
        assert result["stored"] is False
        assert result["id"] is None
        assert result["errors"] == [{"code": "taxonomy_not_found", "message": "No taxonomy tax-9"}]
        assert result["operations"] == [
            {
                "seq": 2,
                "status": "invalid",
                "code": "target_not_found",
                "message": "No class cls-2",
            },
            {
                "seq": 3,
                "status": "invalid",
                "code": "unknown_field",
                "message": "A class update can't set colour",
            },
        ]
        assert result["valid_seqs"] == [1]
        assert "Nothing was stored" in result["next"]
        assert outcome.summary == "Proposal not stored: 3 problems"

    async def test_malformed_operations_are_reported_without_proposing(self):
        service = FakeProposalService(proposal=make_proposal([make_operation(1)]))

        outcome, result = await call(
            service,
            "propose_changes",
            taxonomy_id=TAXONOMY,
            title="t",
            operations=[
                update_op(1),
                "not an object",
                {"seq": True, "op": "update", "kind": "class"},
                update_op(4, ref={"name": "x"}),
            ],
        )

        assert service.calls == []
        assert outcome.is_error is False
        assert result["stored"] is False
        assert [e["message"] for e in result["errors"]] == [
            "operations[1] is not an object",
            "operations[2] needs an integer seq",
        ]
        assert result["operations"] == [
            {"seq": 4, "status": "invalid", "code": "invalid", "message": "ref must be text"}
        ]
        assert result["unchecked_seqs"] == [1]
        assert "valid_seqs" not in result

    @pytest.mark.parametrize(
        "args",
        [
            {"title": "t", "operations": [update_op(1)]},
            {"taxonomy_id": TAXONOMY, "title": " ", "operations": [update_op(1)]},
            {"taxonomy_id": TAXONOMY, "title": "t", "operations": []},
            {"taxonomy_id": TAXONOMY, "title": "t", "operations": {"seq": 1}},
            {
                "taxonomy_id": TAXONOMY,
                "title": "t",
                "operations": [update_op(i) for i in range(MAX_OPERATIONS + 1)],
            },
        ],
    )
    async def test_malformed_arguments_are_tool_errors(self, args):
        service = FakeProposalService(proposal=make_proposal([make_operation(1)]))

        outcome = await tools_for(service)["propose_changes"].execute(args)

        assert outcome.is_error is True
        assert "Invalid arguments" in json.loads(outcome.content)["error"]
        assert service.calls == []

    async def test_unexpected_errors_are_tool_errors(self):
        service = FakeProposalService(error=RuntimeError("database is locked"))

        outcome, result = await call(
            service, "propose_changes", taxonomy_id=TAXONOMY, title="t", operations=[update_op(1)]
        )

        assert outcome.is_error is True
        assert "could not be stored" in result["error"]
        assert "database is locked" not in outcome.content

    async def test_a_full_result_fits_the_cap(self):
        operations = [
            make_operation(
                seq,
                OperationStatus.APPLIED,
                op=OperationType.CREATE,
                target_id=None,
                fields={"concept_scheme_id": "s", "title": f"C{seq}"},
                scope=ChangeScope.ADDITIVE,
                result_entity_id=f"a0000000-0000-4000-8000-{seq:012d}",
            )
            for seq in range(1, MAX_OPERATIONS + 1)
        ]
        service = FakeProposalService(proposal=make_proposal(operations))

        outcome, result = await call(
            service,
            "propose_changes",
            taxonomy_id=TAXONOMY,
            title="t",
            operations=[update_op(seq) for seq in range(1, MAX_OPERATIONS + 1)],
        )

        assert len(outcome.content) <= MAX_PROPOSAL_CHARS
        assert result["counts"]["applied"] == MAX_OPERATIONS
        shown = len(result["operations"])
        if shown < MAX_OPERATIONS:
            assert result["truncated"].startswith(f"showing {shown} of {MAX_OPERATIONS}")

    async def test_many_invalid_operations_are_cut_whole(self):
        errors = [OperationError(seq, "invalid", "x" * 200) for seq in range(1, 201)]
        service = FakeProposalService(error=ProposalValidationError(errors))

        outcome, result = await call(
            service,
            "propose_changes",
            taxonomy_id=TAXONOMY,
            title="t",
            operations=[update_op(seq) for seq in range(1, 201)],
        )

        assert len(outcome.content) <= MAX_PROPOSAL_CHARS
        assert 0 < len(result["operations"]) < 200
        assert result["truncated"].startswith(f"showing {len(result['operations'])} of 200")


# ============================================================================
# get_proposal
# ============================================================================


class TestReplacements:
    async def test_propose_passes_a_deletes_replacement_and_checks_it_is_text(self):
        service = FakeProposalService(proposal=make_proposal([make_operation(1)]))
        delete = {"seq": 1, "op": "delete", "kind": "property", "target_id": "p-1"}

        await call(
            service,
            "propose_changes",
            taxonomy_id=TAXONOMY,
            title="Drop a twin",
            operations=[{**delete, "replacement": "businessrole_assigned_to_businessprocess"}],
        )
        (draft,) = service.calls[0][3]
        assert draft.replacement == "businessrole_assigned_to_businessprocess"

        _, result = await call(
            service,
            "propose_changes",
            taxonomy_id=TAXONOMY,
            title="Drop a twin",
            operations=[{**delete, "replacement": 7}],
        )
        assert result["stored"] is False
        assert result["operations"] == [
            {
                "seq": 1,
                "status": "invalid",
                "code": "invalid",
                "message": "replacement must be text",
            }
        ]
        assert len(service.calls) == 1

    async def test_get_proposal_flags_a_different_pair(self):
        """Gate B row 17: performs businessfunction -> assigned-to businessprocess."""
        row_17 = make_operation(
            17,
            op=OperationType.DELETE,
            kind=OperationKind.PROPERTY,
            target_id="p-perf",
            fields={},
            scope=ChangeScope.BREAKING,
            proposed_replacement_id="p-assigned",
        )
        check = ReplacementCheck(
            replacement_id="p-assigned",
            property_id="p-assigned",
            identifier="businessrole_assigned_to_businessprocess",
            title="assigned-to process",
            pair=PairMatch.DIFFERENT,
            deleted_domain=ClassEnd("c-role", "BusinessRole"),
            deleted_range=ClassEnd("c-fn", "BusinessFunction"),
            domain=ClassEnd("c-role", "BusinessRole"),
            range=ClassEnd("c-proc", "BusinessProcess"),
        )
        service = FakeProposalService(
            proposal=make_proposal([make_operation(1), row_17]), checks={row_17.id: check}
        )

        _, result = await call(service, "get_proposal", id="prop-1")

        plain, flagged = result["operations"]
        assert "replacement_check" not in plain
        assert flagged["proposed_replacement_id"] == "p-assigned"
        assert flagged["replacement_check"] == {
            "replacement_id": "p-assigned",
            "property_id": "p-assigned",
            "identifier": "businessrole_assigned_to_businessprocess",
            "title": "assigned-to process",
            "pair": "different",
            "deleted_domain": {"id": "c-role", "title": "BusinessRole"},
            "deleted_range": {"id": "c-fn", "title": "BusinessFunction"},
            "domain": {"id": "c-role", "title": "BusinessRole"},
            "range": {"id": "c-proc", "title": "BusinessProcess"},
            "replacement_deleted": False,
            "cycle": False,
        }

    async def test_get_proposal_flags_a_cycle_of_deletes(self):
        """DR apm 8 <-> 9: each delete names the type the other deletes."""
        eight = make_operation(
            8,
            op=OperationType.DELETE,
            kind=OperationKind.PROPERTY,
            target_id="p-a",
            fields={},
            scope=ChangeScope.BREAKING,
            proposed_replacement_id="p-b",
        )
        end = ClassEnd("c-1", "Metric")
        check = ReplacementCheck(
            replacement_id="p-b",
            property_id="p-b",
            identifier="b",
            title="b",
            pair=PairMatch.REVERSED,
            deleted_domain=end,
            deleted_range=end,
            domain=end,
            range=end,
            chain=(ChainLink("p-b", "b", 9),),
            cycle=True,
        )
        service = FakeProposalService(proposal=make_proposal([eight]), checks={eight.id: check})

        _, result = await call(service, "get_proposal", id="prop-1")

        flagged = result["operations"][0]["replacement_check"]
        assert flagged["replacement_deleted"] is True
        assert flagged["cycle"] is True
        assert flagged["chain"] == [
            {"replacement_id": "p-b", "identifier": "b", "deleted_by_seq": 9}
        ]


class TestGetProposal:
    async def test_each_operation_has_status_and_stale_flag(self):
        stale_op = make_operation(1)
        applied = make_operation(2, OperationStatus.APPLIED, result_entity_id="cls-2")
        rejected = make_operation(3, OperationStatus.REJECTED, reason="Not in the vision")
        proposal = make_proposal([stale_op, applied, rejected])
        service = FakeProposalService(proposal=proposal, stale={stale_op.id})

        outcome, result = await call(service, "get_proposal", id="prop-1")

        assert outcome.is_error is False
        assert outcome.entities == (EntityRef("prop-1", "proposal", "Clarify classes"),)
        assert result["id"] == "prop-1"
        assert result["kind"] == "proposal"
        assert result["source"] == "mcp"
        assert result["rationale"] == "Better definitions"
        assert result["created_at"] == "2026-10-28T12:00:00Z"
        assert result["counts"] == {"pending": 1, "applied": 1, "rejected": 1, "failed": 0}
        first, second, third = result["operations"]
        assert first == {
            "id": stale_op.id,
            "seq": 1,
            "op": "update",
            "kind": "class",
            "target_id": "cls-1",
            "fields": {"description": "Description 1"},
            "scope": "editorial",
            "status": "pending",
            "stale": True,
        }
        assert (second["status"], second["stale"], second["result_entity_id"]) == (
            "applied",
            False,
            "cls-2",
        )
        assert (third["status"], third["reason"]) == ("rejected", "Not in the vision")

    async def test_unknown_id_is_a_tool_error(self):
        outcome, result = await call(FakeProposalService(), "get_proposal", id="missing")

        assert outcome.is_error is True
        assert "missing" in result["error"]

    async def test_a_large_proposal_drops_fields_then_pages_operations(self):
        operations = [
            make_operation(seq, fields={"description": "d" * 400})
            for seq in range(1, MAX_OPERATIONS + 1)
        ]
        service = FakeProposalService(proposal=make_proposal(operations))

        outcome, first = await call(service, "get_proposal", id="prop-1")

        assert len(outcome.content) <= MAX_PROPOSAL_CHARS
        assert "fields_omitted" in first
        assert all("fields" not in o for o in first["operations"])
        kept = len(first["operations"])
        assert 0 < kept < MAX_OPERATIONS
        assert first["truncated"].endswith(f"pass offset {kept} for the rest")

        _, rest = await call(service, "get_proposal", id="prop-1", offset=kept)

        assert rest["offset"] == kept
        assert rest["operations"][0]["seq"] == kept + 1
        seen = [o["seq"] for o in first["operations"] + rest["operations"]]
        assert seen == list(range(1, len(seen) + 1))

    async def test_a_small_proposal_keeps_fields(self):
        service = FakeProposalService(proposal=make_proposal([make_operation(1)]))

        _, result = await call(service, "get_proposal", id="prop-1")

        assert "fields_omitted" not in result and "truncated" not in result
        assert result["offset"] == 0


class TestRestParityFields:
    """#1413: what REST returns of a proposal, get_proposal returns too."""

    async def test_get_proposal_has_every_rest_field(self):
        decided = make_operation(
            1,
            OperationStatus.APPLIED,
            base={"description": "Old"},
            rationale="Vaguer than the vision allows",
            evidence=[{"quote": "An element is a named fact"}],
            probability=0.8,
            applied_fields={"description": "Edited"},
            result_entity_id="cls-1",
        )
        proposal = make_proposal([decided])
        proposal.source_detail = "claude-code"
        service = FakeProposalService(proposal=proposal)

        _, result = await call(service, "get_proposal", id="prop-1")

        assert result["source_detail"] == "claude-code"
        (operation,) = result["operations"]
        assert operation["base"] == {"description": "Old"}
        assert operation["rationale"] == "Vaguer than the vision allows"
        assert operation["evidence"] == [{"quote": "An element is a named fact"}]
        assert operation["probability"] == 0.8
        assert operation["applied_fields"] == {"description": "Edited"}

    async def test_get_proposal_shows_in_use_blockers(self):
        delete = blocked_delete()
        service = FakeProposalService(
            proposal=make_proposal([delete]), blockers={delete.id: blockers(1)}
        )

        _, result = await call(service, "get_proposal", id="prop-1")

        assert result["operations"][0]["blockers"] == {
            "edges": [edge_dict(0)],
            "move_unavailable_reason": "No type fits every edge",
        }

    async def test_propose_shows_blockers_and_replacement_check(self):
        delete = blocked_delete()
        check = ReplacementCheck(
            replacement_id="p-2",
            property_id="p-2",
            identifier="b",
            title="b",
            pair=PairMatch.SAME,
            deleted_domain=ClassEnd("c-1", "A"),
            deleted_range=ClassEnd("c-2", "B"),
            domain=ClassEnd("c-1", "A"),
            range=ClassEnd("c-2", "B"),
        )
        service = FakeProposalService(
            proposal=make_proposal([delete]),
            blockers={delete.id: blockers(1, replacements=True)},
            checks={delete.id: check},
        )

        _, result = await call(
            service,
            "propose_changes",
            taxonomy_id=TAXONOMY,
            title="t",
            operations=[{"seq": 1, "op": "delete", "kind": "property", "target_id": "p-1"}],
        )

        (operation,) = result["operations"]
        assert operation["blockers"] == {
            "edges": [edge_dict(0)],
            "replacements": [
                {"property_id": "p-2", "identifier": "b", "title": "b", "reversed": False}
            ],
        }
        assert operation["replacement_check"]["pair"] == "same"
        assert service.dry_runs == [False]

    async def test_a_blockers_edges_are_capped(self):
        delete = blocked_delete()
        service = FakeProposalService(
            proposal=make_proposal([delete]), blockers={delete.id: blockers(25)}
        )

        _, result = await call(service, "get_proposal", id="prop-1")

        found = result["operations"][0]["blockers"]
        assert len(found["edges"]) == MAX_BLOCKER_EDGES
        assert found["edges_total"] == 25

    async def test_a_blockers_move_targets_are_capped(self):
        delete = blocked_delete()
        many = DeleteBlockers(
            edges=blockers(1).edges,
            replacements=tuple(ReplacementType(f"p-{i}", f"t{i}", f"t{i}") for i in range(15)),
        )
        service = FakeProposalService(proposal=make_proposal([delete]), blockers={delete.id: many})

        _, result = await call(service, "get_proposal", id="prop-1")

        found = result["operations"][0]["blockers"]
        assert len(found["replacements"]) == MAX_BLOCKER_EDGES
        assert found["replacements_total"] == 15

    async def test_get_proposal_shows_dry_run_only_when_true(self):
        service = FakeProposalService(proposal=make_proposal([make_operation(1)]))

        _, result = await call(service, "get_proposal", id="prop-1")

        assert "dry_run" not in result
        assert "auto_apply" not in result["operations"][0]

    async def test_a_stored_proposal_that_cannot_be_described_is_still_stored(self):
        proposal = make_proposal([make_operation(1, OperationStatus.APPLIED)])
        service = FakeProposalService(proposal=proposal)

        def broken(proposal):
            raise RuntimeError("database is locked")

        service.in_use_blockers = broken

        outcome, result = await call(
            service, "propose_changes", taxonomy_id=TAXONOMY, title="t", operations=[update_op(1)]
        )

        assert outcome.is_error is False
        assert (result["stored"], result["id"]) == (True, "prop-1")
        assert result["operations"] == [{"seq": 1, "status": "applied", "scope": "editorial"}]
        assert "Do not propose it again" in result["details_unavailable"]
        assert outcome.entities == (EntityRef("prop-1", "proposal", "Clarify classes"),)


class TestDryRun:
    async def test_dry_run_stores_nothing_and_previews_each_operation(self):
        auto, held = make_operation(1), blocked_delete(seq=2)
        service = FakeProposalService(
            proposal=make_proposal([auto, held]),
            stale={held.id},
            blockers={held.id: blockers(1)},
            auto=[auto.id],
        )

        outcome, result = await call(
            service,
            "propose_changes",
            taxonomy_id=TAXONOMY,
            title="Clarify classes",
            dry_run=True,
            operations=[
                update_op(1),
                {"seq": 2, "op": "delete", "kind": "property", "target_id": "p-1"},
            ],
        )

        assert service.dry_runs == [True]
        assert outcome.is_error is False
        assert outcome.entities == ()
        assert (result["stored"], result["dry_run"], result["id"]) == (False, True, None)
        first, second = result["operations"]
        assert first == {
            "seq": 1,
            "op": "update",
            "kind": "class",
            "scope": "editorial",
            "auto_apply": True,
            "stale": False,
        }
        assert second["auto_apply"] is False and second["stale"] is True
        assert second["blockers"]["edges"] == [edge_dict(0)]
        assert "Nothing was stored" in result["next"]
        assert "1 would apply at once" in result["next"]
        assert "1 blocked" in result["next"]

    async def test_dry_run_must_be_a_boolean(self):
        service = FakeProposalService(proposal=make_proposal([make_operation(1)]))

        outcome, result = await call(
            service,
            "propose_changes",
            taxonomy_id=TAXONOMY,
            title="t",
            dry_run="yes",
            operations=[update_op(1)],
        )

        assert outcome.is_error is True
        assert "dry_run" in result["error"]
        assert service.calls == []

    def test_schema_offers_dry_run(self):
        schema = tools_for(FakeProposalService())["propose_changes"].spec.input_schema

        assert schema["properties"]["dry_run"]["type"] == "boolean"


def blocked_delete(seq=1):
    return make_operation(
        seq,
        op=OperationType.DELETE,
        kind=OperationKind.PROPERTY,
        target_id="p-1",
        fields={},
        scope=ChangeScope.BREAKING,
    )


def blockers(edges, replacements=False):
    return DeleteBlockers(
        edges=tuple(
            BlockingEdge(
                relationship_id=f"r-{i}",
                source=EdgeEnd(f"s-{i}", f"Source {i}", ("c-1",), ("A",)),
                target=EdgeEnd(f"t-{i}", f"Target {i}", ("c-2",), ("B",)),
                attributes={},
            )
            for i in range(edges)
        ),
        replacements=(ReplacementType("p-2", "b", "b"),) if replacements else (),
        move_unavailable_reason=None if replacements else "No type fits every edge",
    )


def edge_dict(i):
    return {
        "relationship_id": f"r-{i}",
        "source": {
            "id": f"s-{i}",
            "title": f"Source {i}",
            "class_ids": ["c-1"],
            "class_titles": ["A"],
        },
        "target": {
            "id": f"t-{i}",
            "title": f"Target {i}",
            "class_ids": ["c-2"],
            "class_titles": ["B"],
        },
    }


# ============================================================================
# list_proposals
# ============================================================================


class TestListProposals:
    async def test_lists_summaries_with_filters(self):
        listed = [
            make_proposal([make_operation(1)], proposal_id="p-2"),
            make_proposal(
                [make_operation(1, OperationStatus.APPLIED)],
                status=ProposalStatus.DONE,
                proposal_id="p-1",
            ),
        ]
        service = FakeProposalService(listed=listed, total=7)

        outcome, result = await call(
            service, "list_proposals", taxonomy_id=TAXONOMY, status="open", limit=2, offset=4
        )

        assert service.calls == [("list", TAXONOMY, ProposalStatus.OPEN, None, 2, 4)]
        assert result["total"] == 7 and result["offset"] == 4
        assert [i["id"] for i in result["items"]] == ["p-2", "p-1"]
        assert result["items"][1] == {
            "id": "p-1",
            "kind": "proposal",
            "title": "Clarify classes",
            "taxonomy_id": TAXONOMY,
            "source": "mcp",
            "created_at": "2026-10-28T12:00:00Z",
            "status": "done",
            "counts": {"pending": 0, "applied": 1, "rejected": 0, "failed": 0},
        }
        assert [e.id for e in outcome.entities] == ["p-2", "p-1"]
        assert outcome.summary == "2 of 7 proposals"

    async def test_defaults_and_limit_cap(self):
        service = FakeProposalService()

        await call(service, "list_proposals")
        await call(service, "list_proposals", limit=500)

        assert service.calls == [
            ("list", None, None, None, 20, 0),
            ("list", None, None, None, 50, 0),
        ]

    async def test_unknown_status_is_a_tool_error(self):
        outcome, result = await call(FakeProposalService(), "list_proposals", status="accepted")

        assert outcome.is_error is True
        assert "open, done, reverted" in result["error"]


# ============================================================================
# The size cap is hard, and paging always advances
# ============================================================================


class TestHardCap:
    async def test_huge_titles_are_clipped_and_paging_advances(self):
        listed = [make_proposal([make_operation(1)], proposal_id=f"p-{i}") for i in range(3)]
        for proposal in listed:
            proposal.title = "t" * 40000
        service = FakeProposalService(listed=listed, total=3)

        outcome, result = await call(service, "list_proposals", offset=5)

        assert len(outcome.content) <= MAX_PROPOSAL_CHARS
        assert "clipped" in result
        assert len(result["items"]) >= 1
        assert result["items"][0]["title"] == "t" * CLIPPED_TEXT_CHARS + "…"
        if "truncated" in result:
            kept = len(result["items"])
            assert result["truncated"].endswith(f"pass offset {5 + kept} for the rest")
        assert [e.id for e in outcome.entities] == [i["id"] for i in result["items"]]

    async def test_paging_never_stalls_on_one_large_entry(self):
        listed = [make_proposal([make_operation(1)], proposal_id=f"p-{i}") for i in range(30)]
        for proposal in listed:
            proposal.title = "t" * 499
        service = FakeProposalService(listed=listed, total=30)

        outcome, result = await call(service, "list_proposals", limit=30)

        assert len(outcome.content) <= MAX_PROPOSAL_CHARS
        kept = len(result["items"])
        assert 1 <= kept < 30
        assert result["truncated"].endswith(f"pass offset {kept} for the rest")

    async def test_a_huge_single_operation_still_fits(self):
        operation = make_operation(
            1, OperationStatus.REJECTED, reason="r" * 40000, fields={"description": "d" * 40000}
        )
        service = FakeProposalService(proposal=make_proposal([operation]))

        get_outcome, detail = await call(service, "get_proposal", id="prop-1")
        propose_outcome, proposed = await call(
            service, "propose_changes", taxonomy_id=TAXONOMY, title="t", operations=[update_op(1)]
        )

        for outcome in (get_outcome, propose_outcome):
            assert len(outcome.content) <= MAX_PROPOSAL_CHARS
        assert len(detail["operations"]) == 1 and "clipped" in detail
        assert len(proposed["operations"]) == 1 and "clipped" in proposed
