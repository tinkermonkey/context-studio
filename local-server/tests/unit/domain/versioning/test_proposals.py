"""Unit tests for change proposal entities and scope classification (#1353)."""

from datetime import datetime, timezone

import pytest

from domain.versioning.proposals import (
    ChangeProposal,
    ChangeScope,
    OperationKind,
    OperationStatus,
    OperationType,
    ProposalSource,
    ProposalStatus,
    ProposedOperation,
    classify_scope,
)

NOW = datetime(2026, 10, 26, tzinfo=timezone.utc)


class TestClassifyScope:
    def test_wording_only_update_is_editorial(self):
        scope = classify_scope(
            OperationType.UPDATE, {"title": "Den", "description": "Off the hall."}
        )
        assert scope is ChangeScope.EDITORIAL

    def test_vision_and_color_are_editorial(self):
        assert classify_scope(OperationType.UPDATE, {"vision": "# V", "color": "#aabbcc"}) is (
            ChangeScope.EDITORIAL
        )

    def test_sort_order_is_editorial(self):
        assert classify_scope(OperationType.UPDATE, {"sort_order": 3}) is ChangeScope.EDITORIAL

    def test_adding_relationship_attributes_is_additive(self):
        scope = classify_scope(
            OperationType.UPDATE,
            {"attributes": {"quantity": 2, "unit": "each"}},
            base={"attributes": {"quantity": 2}},
        )
        assert scope is ChangeScope.ADDITIVE

    @pytest.mark.parametrize(
        "proposed", [{"quantity": 3}, {"unit": "each"}, {}], ids=["changed", "removed", "cleared"]
    )
    def test_changing_or_removing_a_relationship_attribute_is_breaking(self, proposed):
        scope = classify_scope(
            OperationType.UPDATE, {"attributes": proposed}, base={"attributes": {"quantity": 2}}
        )
        assert scope is ChangeScope.BREAKING

    def test_relationship_attributes_without_a_base_are_breaking(self):
        assert classify_scope(OperationType.UPDATE, {"attributes": {"quantity": 2}}) is (
            ChangeScope.BREAKING
        )

    def test_create_is_additive(self):
        assert classify_scope(OperationType.CREATE, {"title": "Furniture"}) is ChangeScope.ADDITIVE

    def test_creating_a_required_attribute_is_breaking(self):
        required = {"identifier": "size", "datatype": "integer", "is_required": True}
        assert classify_scope(OperationType.CREATE, required) is ChangeScope.BREAKING
        optional = {**required, "is_required": False}
        assert classify_scope(OperationType.CREATE, optional) is ChangeScope.ADDITIVE

    @pytest.mark.parametrize("op", [OperationType.DELETE, OperationType.MOVE])
    def test_delete_and_move_are_breaking(self, op):
        assert classify_scope(op, {}) is ChangeScope.BREAKING

    @pytest.mark.parametrize(
        "field", ["identifier", "domain_class_id", "range_class_id", "datatype", "is_required"]
    )
    def test_redefining_fields_are_breaking(self, field):
        assert classify_scope(OperationType.UPDATE, {field: "x"}) is ChangeScope.BREAKING

    def test_unknown_field_is_breaking(self):
        assert classify_scope(OperationType.UPDATE, {"constraints": {}}) is ChangeScope.BREAKING

    def test_growing_a_list_is_additive(self):
        scope = classify_scope(
            OperationType.UPDATE,
            {"allowed_values": ["each", "pair", "dozen"]},
            base={"allowed_values": ["each", "pair"]},
        )
        assert scope is ChangeScope.ADDITIVE

    def test_shrinking_a_list_is_breaking(self):
        scope = classify_scope(
            OperationType.UPDATE,
            {"class_ids": ["c1"]},
            base={"class_ids": ["c1", "c2"]},
        )
        assert scope is ChangeScope.BREAKING

    def test_list_with_unknown_base_is_breaking(self):
        assert classify_scope(OperationType.UPDATE, {"class_ids": ["c1"]}) is ChangeScope.BREAKING

    def test_list_with_empty_base_is_additive(self):
        scope = classify_scope(
            OperationType.UPDATE, {"class_ids": ["c1"]}, base={"class_ids": None}
        )
        assert scope is ChangeScope.ADDITIVE

    def test_mixed_update_takes_the_strictest_field(self):
        scope = classify_scope(OperationType.UPDATE, {"title": "Den", "datatype": "integer"})
        assert scope is ChangeScope.BREAKING

    def test_a_claim_can_only_make_it_stricter(self):
        editorial = {"title": "Den"}
        assert classify_scope(OperationType.UPDATE, editorial, claimed=ChangeScope.BREAKING) is (
            ChangeScope.BREAKING
        )
        assert classify_scope(OperationType.DELETE, {}, claimed=ChangeScope.EDITORIAL) is (
            ChangeScope.BREAKING
        )


class TestProposedOperation:
    def test_create_takes_a_ref_not_a_target(self):
        op = ProposedOperation(
            seq=0, op=OperationType.CREATE, kind=OperationKind.CLASS, ref="furniture"
        )
        assert op.status is OperationStatus.PENDING and not op.decided
        with pytest.raises(ValueError, match="no target_id"):
            ProposedOperation(
                seq=0, op=OperationType.CREATE, kind=OperationKind.CLASS, target_id="c1"
            )

    @pytest.mark.parametrize("op", [OperationType.UPDATE, OperationType.MOVE, OperationType.DELETE])
    def test_other_operations_need_a_target(self, op):
        with pytest.raises(ValueError, match="needs a target_id"):
            ProposedOperation(seq=0, op=op, kind=OperationKind.CLASS)

    def test_only_creates_carry_a_ref(self):
        with pytest.raises(ValueError, match="Only a create"):
            ProposedOperation(
                seq=0,
                op=OperationType.UPDATE,
                kind=OperationKind.CLASS,
                target_id="c1",
                ref="x",
                fields={"title": "Den"},
            )

    def test_an_update_needs_fields(self):
        with pytest.raises(ValueError, match="at least one field"):
            ProposedOperation(
                seq=0, op=OperationType.UPDATE, kind=OperationKind.CLASS, target_id="c1"
            )

    @pytest.mark.parametrize(
        "kind, fields",
        [
            (OperationKind.SCHEME, {"taxonomy_id": "t2"}),
            (OperationKind.CLASS, {"parent_class_id": None}),
            (OperationKind.CLASS, {"concept_scheme_id": "s2"}),
            (OperationKind.CLASS, {"concept_scheme_id": "s2", "parent_class_id": None}),
        ],
    )
    def test_a_scheme_or_class_can_move(self, kind, fields):
        op = ProposedOperation(
            seq=0, op=OperationType.MOVE, kind=kind, target_id="x", fields=fields
        )
        assert op.fields == fields

    @pytest.mark.parametrize(
        "kind",
        [
            OperationKind.TAXONOMY,
            OperationKind.PROPERTY,
            OperationKind.ATTRIBUTE,
            OperationKind.INDIVIDUAL,
            OperationKind.RELATIONSHIP,
        ],
    )
    def test_nothing_else_can_move(self, kind):
        with pytest.raises(ValueError, match="can't be moved"):
            ProposedOperation(
                seq=0, op=OperationType.MOVE, kind=kind, target_id="x", fields={"class_id": "c2"}
            )

    @pytest.mark.parametrize("fields", [{}, {"parent_class_id": "c2", "title": "Den"}])
    def test_a_move_sets_only_its_move_fields(self, fields):
        with pytest.raises(ValueError, match="sets only concept_scheme_id, parent_class_id"):
            ProposedOperation(
                seq=0,
                op=OperationType.MOVE,
                kind=OperationKind.CLASS,
                target_id="c1",
                fields=fields,
            )

    def test_an_update_cannot_move(self):
        with pytest.raises(ValueError, match="Use a move to change taxonomy_id"):
            ProposedOperation(
                seq=0,
                op=OperationType.UPDATE,
                kind=OperationKind.SCHEME,
                target_id="s1",
                fields={"taxonomy_id": "t2"},
            )

    def test_an_update_cannot_move_a_class_to_another_scheme(self):
        with pytest.raises(ValueError, match="Use a move to change concept_scheme_id"):
            ProposedOperation(
                seq=0,
                op=OperationType.UPDATE,
                kind=OperationKind.CLASS,
                target_id="c1",
                fields={"title": "Den", "concept_scheme_id": "s2"},
            )

    @pytest.mark.parametrize(
        "fields", [{"target_id": "c2"}, {"attributes": {"quantity": 1}, "source_id": "c1"}]
    )
    def test_a_relationship_update_sets_only_attributes(self, fields):
        with pytest.raises(ValueError, match="relationship update sets only attributes"):
            ProposedOperation(
                seq=0,
                op=OperationType.UPDATE,
                kind=OperationKind.RELATIONSHIP,
                target_id="r1",
                fields=fields,
            )

    def test_a_relationship_attributes_update_is_allowed(self):
        operation = ProposedOperation(
            seq=0,
            op=OperationType.UPDATE,
            kind=OperationKind.RELATIONSHIP,
            target_id="r1",
            fields={"attributes": {"quantity": 2}},
        )
        assert operation.fields == {"attributes": {"quantity": 2}}

    @pytest.mark.parametrize("probability", [-0.1, 1.5])
    def test_probability_is_bounded(self, probability):
        with pytest.raises(ValueError, match="probability"):
            ProposedOperation(
                seq=0,
                op=OperationType.UPDATE,
                kind=OperationKind.CLASS,
                target_id="c1",
                fields={"title": "Den"},
                probability=probability,
            )


def _operation(seq, status=OperationStatus.PENDING):
    return ProposedOperation(
        seq=seq,
        op=OperationType.UPDATE,
        kind=OperationKind.CLASS,
        target_id=f"c{seq}",
        fields={"title": f"Class {seq}"},
        status=status,
    )


class TestChangeProposal:
    def test_operations_are_kept_in_seq_order(self):
        proposal = ChangeProposal(
            id="p1",
            taxonomy_id="t1",
            title="Tidy places",
            source=ProposalSource.MCP,
            created_at=NOW,
            operations=[_operation(2), _operation(0), _operation(1)],
        )
        assert [o.seq for o in proposal.operations] == [0, 1, 2]

    def test_needs_a_title_and_unique_seqs(self):
        with pytest.raises(ValueError, match="title"):
            ChangeProposal(
                id="p", taxonomy_id="t", title=" ", source=ProposalSource.USER, created_at=NOW
            )
        with pytest.raises(ValueError, match="unique"):
            ChangeProposal(
                id="p",
                taxonomy_id="t",
                title="T",
                source=ProposalSource.USER,
                created_at=NOW,
                operations=[_operation(0), _operation(0)],
            )

    def test_created_at_must_be_timezone_aware(self):
        with pytest.raises(ValueError, match="timezone-aware"):
            ChangeProposal(
                id="p",
                taxonomy_id="t",
                title="T",
                source=ProposalSource.USER,
                created_at=datetime(2026, 10, 26, 12),
            )

    def test_settles_to_done_once_nothing_is_pending(self):
        proposal = ChangeProposal(
            id="p",
            taxonomy_id="t",
            title="T",
            source=ProposalSource.CHAT,
            created_at=NOW,
            operations=[_operation(0, OperationStatus.APPLIED), _operation(1)],
        )
        assert proposal.settle_status() is ProposalStatus.OPEN
        proposal.operations[1].status = OperationStatus.REJECTED
        assert proposal.pending == []
        assert proposal.settle_status() is ProposalStatus.DONE

    def test_a_reverted_proposal_stays_reverted(self):
        proposal = ChangeProposal(
            id="p",
            taxonomy_id="t",
            title="T",
            source=ProposalSource.CHAT,
            created_at=NOW,
            status=ProposalStatus.REVERTED,
            operations=[_operation(0, OperationStatus.APPLIED)],
        )
        assert proposal.settle_status() is ProposalStatus.REVERTED
