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
proposal, and its output_summary says why (`no_proposal_reason`, with
`skipped_by_reason` counting the candidates skipped for each reason).

A new proposal supersedes the open proposal of an older extraction of the
same source by the same pipeline into the same dataset from the same pages:
what it still awaits is rejected (no decision is recorded), since the new run
repeats what still applies. Extractions are ordered by when they started, not
when they finished: a run that finishes after a newer extraction of the same
pages has proposed is superseded by it instead. Superseding is best effort; a
failure is a warning on the run. The proposal's client_metadata records
`{source_id, run_id, pipeline, pages, extraction_id, extraction_started_at}`,
which is how other extractions are found and ordered.

Proposing to a taxonomy that mirrors an external source is refused for
schema extraction unless its client asked over MCP (`check_may_propose`), as
for every other run that proposes schema changes.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from domain.ontology.ports import OntologyRepository
from domain.pipelines.entities import PipelineType
from domain.pipelines.exceptions import PipelineInputError
from domain.pipelines.individual_extraction.source_operations import plan_individual_operations
from domain.pipelines.requested_via import ensure_may_propose_to
from domain.pipelines.schema_extraction.source_operations import plan_schema_operations
from domain.pipelines.source_operations import OperationPlan, PlannedOperation
from domain.versioning.exceptions import ProposalValidationError
from domain.versioning.proposal_service import ProposalService
from domain.versioning.proposals import ChangeProposal, ProposalSource, ProposalStatus

_logger = logging.getLogger(__name__)

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
        no_proposal_reason: Why nothing was proposed (a sentence); None when
            a proposal was made
    """

    proposal_id: str | None
    operations: int
    refused: list[dict[str, str]]
    skipped: list[dict[str, str]]
    warnings: list[str]
    no_proposal_reason: str | None = None

    def to_json(self) -> dict[str, Any]:
        """The keys the run's output_summary gains."""
        return {
            "proposal_id": self.proposal_id,
            "no_proposal_reason": self.no_proposal_reason,
            "proposed_operations": self.operations,
            "refused_operations": self.refused,
            "skipped_candidates": self.skipped,
            "skipped_by_reason": skipped_by_reason(self.skipped),
        }


class SourceProposer:
    """Proposes an extraction run's candidates on a source as one proposal."""

    def __init__(self, proposals: ProposalService, ontology_repo: OntologyRepository) -> None:
        self._proposals = proposals
        self._repo = ontology_repo

    def check_may_propose(self, taxonomy_id: str, input_data: Mapping[str, Any]) -> None:
        """
        Refuse, before any model call, a run whose proposal would change the
        schema of a taxonomy that mirrors an external source for someone other
        than its client over MCP.

        Raises:
            PipelineInputError: If the taxonomy doesn't exist, or it is mirrored
                and the run's requested_via isn't mcp
        """
        taxonomy = self._repo.get_taxonomy(taxonomy_id)
        if taxonomy is None:
            raise PipelineInputError(f"No taxonomy {taxonomy_id}")
        ensure_may_propose_to(taxonomy, input_data)

    def propose_individuals(
        self,
        run_id: str,
        input_data: Mapping[str, Any],
        triples: Sequence[dict[str, Any]],
        notes: Sequence[str] = (),
    ) -> ProposalOutcome:
        """
        Propose an individual-extraction run's merged triples (individual and
        relationship creates) in the run's dataset.

        Args:
            run_id: The run
            input_data: The run's input: ontology_id, dataset_id, source_id,
                source_title, page_starts
            triples: The run's merged triples
            notes: Sentences the proposal's rationale adds, saying what the run
                could not read (chunks whose extraction failed)
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
            notes,
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
        notes: Sequence[str] = (),
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
                    rationale=_rationale(pipeline, source_title, plan, refused, notes),
                    source_detail=f"{pipeline.value} run {run_id} on source {source_id}",
                    client_metadata={
                        "source_id": source_id,
                        "run_id": run_id,
                        "pipeline": pipeline.value,
                        "pages": _text(input_data.get("pages")),
                        "extraction_id": _text(input_data.get("extraction_id")),
                        "extraction_started_at": _text(input_data.get("extraction_started_at")),
                    },
                    dataset_id=dataset_id,
                )
                break
            except ProposalValidationError as exc:
                rows = _without_refused(rows, exc, refused)

        warnings = [f"Refused {r['label']}: {r['error']}" for r in refused]
        if proposal is None:
            reason = _no_proposal_reason(plan.skipped, refused)
            warnings.append(f"Nothing to propose. {reason}")
            return ProposalOutcome(None, 0, refused, plan.skipped, warnings, reason)
        warnings += self._supersede(proposal)
        return ProposalOutcome(
            proposal.id, len(proposal.operations), refused, plan.skipped, warnings
        )

    def _supersede(self, proposal: ChangeProposal) -> list[str]:
        """
        Settle the new proposal against the other extractions of the same
        source, pipeline, dataset and page selection: what an older
        extraction's open proposal still awaits is rejected; and when a newer
        extraction already proposed (this run finished late), what this one
        awaits is rejected instead. Best effort: a failure is logged and
        returned as a warning, and never undoes the new proposal.

        Returns:
            Warnings for the run, one per proposal that could not be settled
        """
        warnings: list[str] = []
        try:
            others = [
                other
                for other in self._pipeline_proposals(proposal.taxonomy_id)
                if other.id != proposal.id and _same_extraction_scope(other, proposal)
            ]
        except Exception as exc:  # noqa: BLE001 - the new proposal stands regardless
            _logger.exception("Could not list earlier extractions of proposal %s", proposal.id)
            return [f"Could not supersede earlier extractions: {exc}"]
        started = _started_at(proposal)
        newer = [o for o in others if _started_at(o) > started]
        older = [o for o in others if _started_at(o) < started]
        if newer:
            newest = max(newer, key=_started_at)
            older = [proposal]
            superseding = newest
        else:
            superseding = proposal
        for other in older:
            try:
                current = self._proposals.get(other.id)
                if current.status is not ProposalStatus.OPEN or not current.pending:
                    continue
                # Nobody judged these: no decision is recorded.
                self._proposals.reject(
                    current.id,
                    [o.id for o in current.pending],
                    note=SUPERSEDED_REASON.format(superseding.id),
                    decided_by=None,
                )
            except Exception as exc:  # noqa: BLE001 - one failure never fails the run
                _logger.exception("Could not supersede proposal %s", other.id)
                warnings.append(f"Could not supersede proposal {other.id}: {exc}")
        return warnings

    def _pipeline_proposals(self, taxonomy_id: str) -> list[ChangeProposal]:
        """Every pipeline proposal of the taxonomy, whatever its status."""
        found: list[ChangeProposal] = []
        offset = 0
        while True:
            page = self._proposals.list_proposals(
                taxonomy_id=taxonomy_id,
                source=ProposalSource.PIPELINE,
                limit=_PAGE,
                offset=offset,
            )
            found += page
            if len(page) < _PAGE:
                return found
            offset += _PAGE


def _same_extraction_scope(one: ChangeProposal, other: ChangeProposal) -> bool:
    """Whether two proposals extract the same source, by the same pipeline, into the same
    dataset, from the same pages."""
    a, b = one.client_metadata or {}, other.client_metadata or {}
    return (
        a.get("source_id") is not None
        and all(a.get(key) == b.get(key) for key in ("source_id", "pipeline", "pages"))
        and one.dataset_id == other.dataset_id
    )


def _started_at(proposal: ChangeProposal) -> datetime:
    """When the extraction behind a proposal started; its creation when it records none."""
    value = (proposal.client_metadata or {}).get("extraction_started_at")
    try:
        started = datetime.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        started = None
    started = started or proposal.created_at
    return started if started.tzinfo else started.replace(tzinfo=timezone.utc)


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


def skipped_by_reason(skipped: Sequence[Mapping[str, str]]) -> dict[str, int]:
    """How many candidates were skipped for each reason, most first."""
    counts: dict[str, int] = {}
    for item in skipped:
        counts[item["reason"]] = counts.get(item["reason"], 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True))


def _no_proposal_reason(skipped: list[dict[str, str]], refused: list[dict[str, str]]) -> str:
    """Why a run proposed nothing, as a sentence."""
    if refused:
        return f"All {len(refused)} operations were refused."
    if skipped:
        counts = ", ".join(f"{reason} {n}" for reason, n in skipped_by_reason(skipped).items())
        return f"None of the {len(skipped)} candidates made an operation ({counts})."
    return "The run found no candidates in the text."


_RATIONALES = {
    PipelineType.INDIVIDUAL_EXTRACTION: (
        "Individuals and relationships found in the source {title!r}. Each operation"
        " carries the passages it was found in as evidence and the extraction's confidence"
        " as p; an individual that may already exist offers it as an alternative."
    ),
    PipelineType.SCHEMA_EXTRACTION: (
        "Classes and relationship types the source {title!r} names that the taxonomy lacks."
        " Each operation carries passages where its term occurs as evidence and the"
        " extraction's confidence as p."
    ),
}


def _rationale(
    pipeline: PipelineType,
    source_title: str,
    plan: OperationPlan,
    refused: list[dict[str, str]],
    run_notes: Sequence[str] = (),
) -> str:
    """The proposal's rationale, saying what the run found, could not read and could not propose."""
    text = _RATIONALES[pipeline].format(title=source_title)
    notes = [note.rstrip(".") for note in run_notes]
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
