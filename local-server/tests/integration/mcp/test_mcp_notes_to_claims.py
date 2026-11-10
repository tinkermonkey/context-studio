"""
Splitting a proposal's notes over MCP (#1519): on a mirrored taxonomy (DR's),
the client starts notes_to_claims with run_refinement, and the operations'
maintainer notes and the reviewers' decision reasons become resolved claims. A
run asked for from the chat is refused.
"""

import json
from types import SimpleNamespace

import pytest

from adapters.chat.run_tools import build_run_tools
from adapters.persistence.sqlite.batch_repo import BatchRepository
from adapters.persistence.sqlite.claim_repo import SQLiteClaimRepository
from adapters.persistence.sqlite.pipeline_run_repo import PipelineRepository
from adapters.pipelines.run_executor import BackgroundRunExecutor
from domain.pipelines.notes_to_claims import register_notes_to_claims
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from domain.pipelines.requested_via import RequestedVia
from domain.versioning.claims import ClaimFilter, ClaimService, NoteSource
from domain.versioning.proposals import OperationDraft, ProposalSource
from tests.fakes.fake_note_splitter import FakeNoteSplitter
from tests.integration.chat.conftest import OPERATION_ID, SERVICE_CLASS_ID, TAXONOMY_ID
from tests.integration.mcp.test_mcp_run_tools import call, wait_for_run
from tests.integration.mcp.test_mcp_server import mcp_client
from tests.integration.pipelines.test_notes_to_claims import wait_for_end

OPERATION_NOTE = "The operation has no attribute for its HTTP method. It realizes services."
REVIEW_NOTE = "Business services are not renamed this way."


def claim_split(text, *affected):
    return {
        "text": text,
        "category": "missing_attribute",
        "affected_ids": list(affected),
        "proposed_change": "none stated",
    }


def splitter():
    return FakeNoteSplitter(
        {
            "HTTP method": [
                claim_split("operation has no attribute for its HTTP method.", "operation"),
                claim_split(
                    "operation realizes business_service.",
                    "operation_realizes_service",
                    "business_service",
                ),
            ],
            "renamed": [claim_split("business_service should not be renamed.", "business_service")],
        }
    )


@pytest.fixture
def notes_setup(dr_workspace, proposals):
    dr_workspace.ontology.set_taxonomy_mirrored(TAXONOMY_ID, True)
    proposal = proposals.service.propose(
        TAXONOMY_ID,
        "Enrich the API layer",
        [
            OperationDraft(
                seq=1,
                op="update",
                kind="class",
                target_id=OPERATION_ID,
                fields={"description": "One callable operation of an API"},
                notes=OPERATION_NOTE,
            ),
            OperationDraft(
                seq=2,
                op="update",
                kind="class",
                target_id=SERVICE_CLASS_ID,
                fields={"title": "Service"},
            ),
        ],
        source=ProposalSource.MCP,
    )
    rejected = proposals.service.reject(proposal.id, [proposal.operations[1].id], REVIEW_NOTE)
    claims = ClaimService(
        SQLiteClaimRepository(dr_workspace.session_factory), dr_workspace.repository
    )
    implementations = PipelineImplementationRegistry()
    configurations = PipelineConfigurationRegistry()
    register_notes_to_claims(implementations, configurations)
    runs = PipelineRepository(dr_workspace.session_factory)
    executor = BackgroundRunExecutor(
        runs=runs,
        batches=BatchRepository(dr_workspace.session_factory),
        implementations=implementations,
        configurations=configurations,
        llm_provider=splitter(),
        app_state=SimpleNamespace(
            ontology_repo=dr_workspace.repository,
            claim_service=claims,
            proposal_service=proposals.service,
        ),
        poll_seconds=0.05,
    )
    executor.start()
    yield SimpleNamespace(proposal=rejected, claims=claims, runs=runs, executor=executor)
    executor.stop()


async def test_splitting_a_proposals_notes_over_mcp_stores_resolved_claims(
    dr_workspace, notes_setup
):
    tools = build_run_tools(
        notes_setup.executor, notes_setup.runs, dr_workspace.ontology, RequestedVia.MCP
    )
    async with mcp_client(dr_workspace, write_tools=tools) as client:
        result, text = await call(
            client,
            "run_refinement",
            {
                "taxonomy_id": TAXONOMY_ID,
                "pipeline": "notes_to_claims",
                "scope": {"proposal_id": notes_setup.proposal.id},
            },
        )
        assert result["isError"] is False
        run_id = json.loads(text)["run_id"]
        finished = await wait_for_run(
            client, run_id, lambda r: r["status"] not in ("pending", "running")
        )

    assert finished["status"] == "completed", finished
    assert finished["proposal_id"] is None
    operation = notes_setup.proposal.operations[0]
    stored = {
        c.key: c for c in notes_setup.claims.list_claims(ClaimFilter(taxonomy_id=TAXONOMY_ID))
    }
    decision_keys = [k for k in stored if k.startswith("decision:")]
    assert sorted(k for k in stored if k.startswith("op:")) == [
        f"op:{operation.id}#1",
        f"op:{operation.id}#2",
    ]
    assert len(decision_keys) == 1 and decision_keys[0].endswith("#1")
    first, second = stored[f"op:{operation.id}#1"], stored[f"op:{operation.id}#2"]
    assert (first.subject_id, first.note_source) == (OPERATION_ID, NoteSource.MAINTAINER)
    assert first.affected_ids == [OPERATION_ID]
    realizes = dr_workspace.repository.get_property_definition_by_identifier(
        "operation_realizes_service"
    )
    assert second.affected_ids == [realizes.id, SERVICE_CLASS_ID]
    assert second.unresolved_refs == []
    review = stored[decision_keys[0]]
    assert (review.subject_id, review.note_source) == (SERVICE_CLASS_ID, NoteSource.REVIEWER)
    assert review.note_text == REVIEW_NOTE
    assert review.affected_ids == [SERVICE_CLASS_ID]


def test_a_run_asked_for_from_the_chat_is_refused(dr_workspace, notes_setup):
    tools = build_run_tools(
        notes_setup.executor, notes_setup.runs, dr_workspace.ontology, RequestedVia.CHAT
    )
    run_refinement = next(t for t in tools if t.spec.name == "run_refinement")
    outcome = run_refinement.run(
        {
            "taxonomy_id": TAXONOMY_ID,
            "pipeline": "notes_to_claims",
            "scope": {"proposal_id": notes_setup.proposal.id},
        }
    )

    done = wait_for_end(notes_setup.runs, json.loads(outcome.content)["run_id"])
    assert "mirrors an external source" in done.failure_reason
    assert notes_setup.claims.count_claims(ClaimFilter(taxonomy_id=TAXONOMY_ID)) == 0
