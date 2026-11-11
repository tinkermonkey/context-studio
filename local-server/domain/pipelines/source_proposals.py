"""
One proposal per extraction run on a source (#1552).

An individual- or schema-extraction run over a source ends in one change
proposal (source pipeline) for review, instead of writing to the graph. The
run's candidates are planned as operations (see
`individual_extraction/source_operations.py` and
`schema_extraction/source_operations.py`), each with the source passages it
was found in as evidence, and proposed through `ProposalService.propose`.

Operations the proposal service refuses are dropped, with every operation that
points at one of them by "$ref", and the rest proposed again, as the
relationship reflection does. A run with nothing left to propose makes no
proposal.

A new proposal supersedes the open proposal of an earlier extraction of the
same source by the same pipeline into the same dataset: what it still awaits
is rejected (no decision is recorded), since the new run repeats what still
applies. The proposal's client_metadata records `{source_id, run_id,
pipeline}`, which is how earlier extractions are found.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from domain.ontology.ports import OntologyRepository
from domain.pipelines.entities import PipelineType
from domain.pipelines.individual_extraction.source_operations import plan_individual_operations
from domain.pipelines.schema_extraction.source_operations import plan_schema_operations
from domain.pipelines.source_operations import OperationPlan, PlannedOperation
from domain.versioning.exceptions import ProposalValidationError
from domain.versioning.proposal_service import ProposalService
from domain.versioning.proposals import ChangeProposal, ProposalSource, ProposalStatus

# Why a newer extraction of the same source rejects an older proposal's pending operations
SUPERSEDED_REASON = "superseded by extraction proposal {}"
MAX_TITLE_SOURCE_CHARS = 400
MAX_LISTED = 5
_PAGE = 200


@dataclass
class ProposalOutcome:
    """
    What proposing a run's candidates did.

    Attributes:
        proposal_id: The stored proposal; None when nothing was proposed
        operations: How many operations it holds
        refused: Operations the proposal service refused, each {"label", "error"}
        skipped: Candidates that became no operation, each {"label", "reason"}
        warnings: Sentences for the run's warnings
    """

    proposal_id: str | None
    operations: int
    refused: list[dict[str, str]]
    skipped: list[dict[str, str]]
    warnings: list[str]

    def to_json(self) -> dict[str, Any]:
        """The keys the run's output_summary gains."""
        return {
            "proposal_id": self.proposal_id,
            "proposed_operations": self.operations,
            "refused_operations": self.refused,
            "skipped_candidates": self.skipped,
        }


class SourceProposer:
    """Proposes an extraction run's candidates on a source as one proposal."""

    def __init__(self, proposals: ProposalService, ontology_repo: OntologyRepository) -> None:
        self._proposals = proposals
        self._repo = ontology_repo

    def propose_individuals(
        self, run_id: str, input_data: Mapping[str, Any], triples: Sequence[dict[str, Any]]
    ) -> ProposalOutcome:
        """
        Propose an individual-extraction run's merged triples (individual and
        relationship creates) in the run's dataset.

        Args:
            run_id: The run
            input_data: The run's input: ontology_id, dataset_id, source_id,
                source_title, page_starts
            triples: The run's merged triples
        """
        source_id = str(input_data["source_id"])
        plan = plan_individual_operations(
            triples,
            self._repo,
            taxonomy_id=str(input_data["ontology_id"]),
            dataset_id=_text(input_data.get("dataset_id")),
            source_id=source_id,
            page_starts=_page_starts(input_data.get("page_starts")),
        )
        return self._propose(
            PipelineType.INDIVIDUAL_EXTRACTION,
            run_id,
            input_data,
            str(input_data["ontology_id"]),
            _text(input_data.get("dataset_id")),
            plan,
        )

    def propose_schema(
        self, run_id: str, input_data: Mapping[str, Any], candidates: Sequence[dict[str, Any]]
    ) -> ProposalOutcome:
        """
        Propose a schema-extraction run's class and property candidates (class,
        predicate and relationship-type creates) to the source's taxonomy.

        Args:
            run_id: The run
            input_data: The run's input: scope (the taxonomy), source_id,
                source_title, page_starts
            candidates: The run's class and property_definition candidates
        """
        taxonomy_id = str(input_data["scope"])
        plan = plan_schema_operations(
            candidates,
            self._repo,
            taxonomy_id=taxonomy_id,
            source_id=str(input_data["source_id"]),
            page_starts=_page_starts(input_data.get("page_starts")),
        )
        return self._propose(
            PipelineType.SCHEMA_EXTRACTION, run_id, input_data, taxonomy_id, None, plan
        )

    def _propose(
        self,
        pipeline: PipelineType,
        run_id: str,
        input_data: Mapping[str, Any],
        taxonomy_id: str,
        dataset_id: str | None,
        plan: OperationPlan,
    ) -> ProposalOutcome:
        source_id = str(input_data["source_id"])
        source_title = _text(input_data.get("source_title")) or source_id
        refused: list[dict[str, str]] = []
        rows = list(plan.operations)
        proposal: ChangeProposal | None = None
        while rows:
            try:
                proposal = self._proposals.propose(
                    taxonomy_id=taxonomy_id,
                    title=f"Extraction: {source_title[:MAX_TITLE_SOURCE_CHARS]}",
                    operations=[row.draft for row in rows],
                    source=ProposalSource.PIPELINE,
                    rationale=_rationale(pipeline, source_title, plan, refused),
                    source_detail=f"{pipeline.value} run {run_id} on source {source_id}",
                    client_metadata={
                        "source_id": source_id,
                        "run_id": run_id,
                        "pipeline": pipeline.value,
                    },
                    dataset_id=dataset_id,
                )
                break
            except ProposalValidationError as exc:
                rows = _without_refused(rows, exc, refused)

        warnings = [f"Refused {r['label']}: {r['error']}" for r in refused]
        if proposal is None:
            warnings.append(
                f"Nothing to propose: {len(refused)} operations refused"
                if refused
                else "Nothing to propose: the run found no candidates that make an operation"
            )
            return ProposalOutcome(None, 0, refused, plan.skipped, warnings)
        self._supersede_earlier(proposal, source_id, pipeline)
        return ProposalOutcome(
            proposal.id, len(proposal.operations), refused, plan.skipped, warnings
        )

    def _supersede_earlier(
        self, proposal: ChangeProposal, source_id: str, pipeline: PipelineType
    ) -> None:
        """Reject what earlier extractions' open proposals of this source still await."""
        older: list[ChangeProposal] = []
        offset = 0
        while True:
            page = self._proposals.list_proposals(
                taxonomy_id=proposal.taxonomy_id,
                status=ProposalStatus.OPEN,
                source=ProposalSource.PIPELINE,
                limit=_PAGE,
                offset=offset,
            )
            older += page
            if len(page) < _PAGE:
                break
            offset += _PAGE
        for other in older:
            meta = other.client_metadata or {}
            if (
                other.id == proposal.id
                or not other.pending
                or meta.get("source_id") != source_id
                or meta.get("pipeline") != pipeline.value
                or other.dataset_id != proposal.dataset_id
            ):
                continue
            # Nobody judged these: no decision is recorded.
            self._proposals.reject(
                other.id,
                [o.id for o in other.pending],
                note=SUPERSEDED_REASON.format(proposal.id),
                decided_by=None,
            )


def _without_refused(
    rows: list[PlannedOperation], exc: ProposalValidationError, refused: list[dict[str, str]]
) -> list[PlannedOperation]:
    """
    The rows left once those the proposal service refused are dropped, with
    every row pointing at a dropped create.

    Raises:
        ProposalValidationError: If the refusal names no operation (the
            proposal as a whole was refused)
    """
    by_seq = {row.draft.seq: row for row in rows}
    reasons: dict[int, list[str]] = {}
    for error in exc.errors:
        if error.seq in by_seq:
            reasons.setdefault(error.seq, []).append(f"{error.code}: {error.message}")
    if not reasons:
        raise exc
    dropped_refs: set[str] = set()
    for seq, messages in reasons.items():
        row = by_seq[seq]
        refused.append({"label": row.label, "error": "; ".join(messages)})
        if row.draft.ref:
            dropped_refs.add(row.draft.ref)
    kept = [row for row in rows if row.draft.seq not in reasons]
    while True:
        dependents = [row for row in kept if row.needs & dropped_refs]
        if not dependents:
            return kept
        for row in dependents:
            refused.append({"label": row.label, "error": "points at a refused operation"})
            if row.draft.ref:
                dropped_refs.add(row.draft.ref)
        kept = [row for row in kept if row not in dependents]


def _rationale(
    pipeline: PipelineType, source_title: str, plan: OperationPlan, refused: list[dict[str, str]]
) -> str:
    """The proposal's rationale, saying what the run found and could not propose."""
    text = (
        f"Candidates {pipeline.value} found in the source {source_title!r}. Each operation"
        " carries the passages it was found in as evidence and the extraction's confidence"
        " as p; an individual that may already exist offers it as an alternative."
    )
    notes = []
    if plan.skipped:
        listed = [f"{s['label']} ({s['reason']})" for s in plan.skipped[:MAX_LISTED]]
        more = len(plan.skipped) - MAX_LISTED
        notes.append(
            f"{len(plan.skipped)} candidates not proposed: {'; '.join(listed)}"
            + (f"; and {more} more" if more > 0 else "")
        )
    if refused:
        listed = [f"{r['label']} ({r['error']})" for r in refused[:MAX_LISTED]]
        more = len(refused) - MAX_LISTED
        notes.append(
            f"{len(refused)} operations refused: {'; '.join(listed)}"
            + (f"; and {more} more" if more > 0 else "")
        )
    return (text + (f" {'. '.join(notes)}." if notes else ""))[:8000]


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _page_starts(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    return [v for v in value if isinstance(v, int) and not isinstance(v, bool) and v >= 0]
