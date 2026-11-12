"""
Unit tests (#1575): an operation of an extraction from a source that cites no
passage in it is flagged, and never auto-applies (nor what names it by "$ref").
"""

from datetime import datetime, timezone

import pytest

from domain.versioning.approval_policy import ApprovalPolicy, AutoApplyRule
from domain.versioning.proposal_service import OperationDraft
from domain.versioning.proposals import (
    ChangeProposal,
    OperationStatus,
    ProposalSource,
    ProposedOperation,
)
from tests.unit.domain.versioning.test_approval_policy import (  # noqa: F401 - fixtures
    K,
    T,
    house,
    ontology,
    policies,
    publisher,
    service,
)

SOURCE = "src-moen"
FROM_SOURCE = {"source_id": SOURCE, "pipeline": "individual_extraction"}


def passage(start=10, end=24, quote="adhesive disk"):
    return {"source_id": SOURCE, "page": 1, "start": start, "end": end, "quote": quote}


def operation(seq, evidence=()):
    return ProposedOperation(
        seq=seq,
        op=T.CREATE,
        kind=K.INDIVIDUAL,
        ref=f"i{seq}",
        fields={"title": f"Item {seq}", "class_ids": ["c"]},
        evidence=list(evidence),
    )


def proposal(operations, source=ProposalSource.PIPELINE, client_metadata=FROM_SOURCE):
    return ChangeProposal(
        id="p",
        taxonomy_id="t",
        title="Extraction: Moen",
        source=source,
        created_at=datetime.now(timezone.utc),
        operations=list(operations),
        client_metadata=dict(client_metadata),
    )


class TestLacksPassage:
    def test_an_extraction_operation_without_a_source_passage_lacks_one(self):
        placed = operation(1, [passage()])
        quote_only = operation(2, [{"quote": "Moen recommends painter's tape"}])
        bare = operation(3)
        extraction = proposal([placed, quote_only, bare])

        assert extraction.extracted_from_source
        assert not extraction.lacks_passage(placed)
        assert extraction.lacks_passage(quote_only)
        assert extraction.lacks_passage(bare)

    @pytest.mark.parametrize(
        ("source", "metadata"),
        [
            (ProposalSource.MCP, {}),
            (ProposalSource.CHAT, FROM_SOURCE),  # only a pipeline extracts from a source
            (ProposalSource.PIPELINE, {"run_id": "r"}),  # e.g. a reflection: no source
        ],
    )
    def test_other_proposals_never_lack_one(self, source, metadata):
        bare = operation(1)
        other = proposal([bare], source=source, client_metadata=metadata)

        assert not other.extracted_from_source
        assert not other.lacks_passage(bare)


class TestAutoApply:
    def test_an_operation_without_a_passage_and_what_names_it_wait(
        self, service, policies, house, ontology
    ):
        near = ontology.create_property_definition(
            "near", "Near", taxonomy_id=house["taxonomy"], create_missing_predicate=True
        )
        policies.save(
            ApprovalPolicy(
                house["taxonomy"],
                (AutoApplyRule(op=T.CREATE, kind=K.INDIVIDUAL), AutoApplyRule(op=T.CREATE)),
            )
        )

        def place(seq, title, evidence):
            return OperationDraft(
                seq,
                T.CREATE,
                K.INDIVIDUAL,
                ref=f"i{seq}",
                fields={"class_ids": [house["place"]], "title": title},
                evidence=evidence,
            )

        def link(seq, source, target):
            return OperationDraft(
                seq,
                T.CREATE,
                K.RELATIONSHIP,
                fields={
                    "source_id": source,
                    "target_id": target,
                    "property_definition_id": near.id,
                },
                evidence=[passage(30, 40, "the wall")],
            )

        drafts = [
            place(1, "Wall", [passage()]),
            place(2, "Pacemaker", [{"quote": "pacemaker"}]),
            link(3, "$i2", "$i1"),
            link(4, "$i1", house["attic"]),
        ]

        stored = service.propose(
            house["taxonomy"],
            "Extraction: Moen",
            drafts,
            ProposalSource.PIPELINE,
            client_metadata=FROM_SOURCE,
        )

        statuses = [o.status for o in stored.operations]
        assert statuses == [
            OperationStatus.APPLIED,
            OperationStatus.PENDING,  # no passage
            OperationStatus.PENDING,  # names it
            OperationStatus.APPLIED,
        ]
        # A dry run's verdict is the same selection
        first, _, _, last = stored.operations
        assert service.auto_apply_operation_ids(stored) == [first.id, last.id]

    def test_without_a_source_the_same_operations_apply(self, service, policies, house):
        policies.save(ApprovalPolicy(house["taxonomy"], (AutoApplyRule(op=T.CREATE),)))
        draft = OperationDraft(
            1, T.CREATE, K.INDIVIDUAL, fields={"class_ids": [house["place"]], "title": "Shed"}
        )

        stored = service.propose(house["taxonomy"], "By hand", [draft], ProposalSource.MCP)

        assert stored.operations[0].status is OperationStatus.APPLIED
