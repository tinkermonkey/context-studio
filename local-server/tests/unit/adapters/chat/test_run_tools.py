"""
Unit tests for what get_run reports of a run on a source whose chunks failed:
the payload lists failed_chunks, and the summary never reads as a clean run.
"""

import json

from adapters.chat.run_tools import GetRunTool, run_payload
from domain.pipelines.entities import PipelineRun, PipelineRunStatus

REASON = "The LLM response for identify_individuals was still incomplete after 3 attempts"
FAILED_CHUNK = {"index": 1, "start": 8000, "end": 16000, "triples": 0, "failure_reason": REASON}
UNREAD = f"Extraction failed for 1 of 3 chunks (chunk 2), so what they hold is missing. {REASON}."


class _Runs:
    def __init__(self, run):
        self._run = run

    def get(self, run_id):
        return self._run if run_id == self._run.id else None


def _run(**fields):
    return PipelineRun(
        id="run-1",
        batch_run_id="batch-1",
        status=PipelineRunStatus.COMPLETED,
        items_done=3,
        items_total=3,
        **fields,
    )


def test_payload_lists_the_failed_chunks():
    run = _run(output_summary={"failed_chunks": [FAILED_CHUNK]}, proposal_id="prop-1")
    assert run_payload(run)["failed_chunks"] == [FAILED_CHUNK]


def test_payload_of_a_run_with_no_failed_chunk_lists_none():
    assert run_payload(_run(output_summary={}))["failed_chunks"] == []


def test_summary_of_a_partial_run_says_chunks_failed():
    run = _run(output_summary={"failed_chunks": [FAILED_CHUNK]}, proposal_id="prop-1")
    outcome = GetRunTool(_Runs(run)).run({"run_id": "run-1"})
    assert outcome.summary == "Run completed (3/3), 1 chunk failed"
    assert json.loads(outcome.content)["failed_chunks"] == [FAILED_CHUNK]


def test_summary_of_a_partial_run_that_proposed_nothing_gives_the_failure():
    reason = f"{UNREAD} The run found no candidates in what it could read."
    run = _run(
        output_summary={
            "failed_chunks": [FAILED_CHUNK, FAILED_CHUNK],
            "no_proposal_reason": reason,
        }
    )
    outcome = GetRunTool(_Runs(run)).run({"run_id": "run-1"})
    assert outcome.summary == f"Run completed (3/3), 2 chunks failed, nothing proposed: {reason}"


def test_summary_of_a_whole_run_is_unchanged():
    outcome = GetRunTool(_Runs(_run(output_summary={}, proposal_id="prop-1"))).run(
        {"run_id": "run-1"}
    )
    assert outcome.summary == "Run completed (3/3)"
    assert "failed_chunks" in GetRunTool.description
