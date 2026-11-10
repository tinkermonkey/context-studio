"""
Notes to claims: split maintainer and reviewer notes into atomic claims.

For each note in scope, the orchestrator renders its subject's context with
Context Studio identifiers, asks the LLM to split the note (DR's split-notes.ts
prompt), resolves the entities each claim names, and stores the claims with
keys "<note ref>#<n>" (DR's claim ids). It changes nothing in the taxonomy and
makes no proposal.

A re-run is idempotent: it submits the new split first, so a claim whose key
and text are unchanged keeps its triage and verdict (verdicts are benchmark
gold), and only then deletes that note's claims whose keys the new split no
longer produced. A note whose split fails keeps its claims.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Optional, cast

from domain.ontology.entities import Taxonomy
from domain.ontology.ports import OntologyRepository
from domain.pipelines.entities import PipelineRunStatus
from domain.pipelines.exceptions import PipelineExecutionError, PipelineInputError
from domain.pipelines.orchestration.base import PipelineOrchestrator, PipelineState
from domain.pipelines.ports import LLMProvider, LLMResponse, PipelineRunStatusWriter
from domain.pipelines.refinement.neighborhood import SchemaNeighborhoodTraversal
from domain.pipelines.requested_via import ensure_may_propose_to
from domain.versioning.claims import Claim, ClaimService
from domain.versioning.exceptions import ChangeProposalNotFoundError
from domain.versioning.gold import DecisionFilter
from domain.versioning.proposal_service import ProposalService

from .configurations.default import get_default_config
from .context import EntityRefResolver, NoteContextRenderer
from .notes import Note, client_notes, decision_notes, proposal_notes
from .prompt import parse_split, system_prompt, user_prompt

MAX_REPORTED_ERRORS = 20
SCOPE_FORMS = ("notes", "proposal_id", "since")


@dataclass
class NotesToClaimsState(PipelineState):
    """State for a notes-to-claims run (the input names the taxonomy and scope)."""


@dataclass
class _Split:
    """What splitting one note stored."""

    claims: list[Claim]
    removed: int
    response: LLMResponse


class NotesToClaimsOrchestrator(PipelineOrchestrator):
    """Splits each note in scope into claims and stores them."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        ontology_repo: OntologyRepository,
        claim_service: ClaimService,
        proposal_service: Optional[ProposalService] = None,
        config: Optional[dict[str, Any]] = None,
        run_id: Optional[str] = None,
        status_writer: Optional[PipelineRunStatusWriter] = None,
    ) -> None:
        """
        Args:
            llm_provider: The LLM that splits the notes
            ontology_repo: The ontology the notes are about
            claim_service: Where the claims are stored
            proposal_service: Proposals and their decisions, for the
                {proposal_id} and {since} scopes
            config: model, temperature, max_tokens, concurrency and categories
                (see the default configuration)
            run_id, status_writer: Where the run's status and progress go
        """
        super().__init__(llm_provider, run_id, status_writer)
        self._repo = ontology_repo
        self._claims = claim_service
        self._proposals = proposal_service
        self._config = {**get_default_config(), **(config or {})}

    async def execute(self, state: PipelineState) -> PipelineState:
        self._write_running_status()
        started = time.monotonic()
        taxonomy_id = state.input_data.get("taxonomy_id")
        if not isinstance(taxonomy_id, str) or not taxonomy_id:
            raise PipelineInputError("taxonomy_id is required")
        taxonomy = self._repo.get_taxonomy(taxonomy_id)
        if taxonomy is None:
            raise PipelineInputError(f"No taxonomy {taxonomy_id}")
        # A mirrored taxonomy's notes are its client's to split, over MCP
        ensure_may_propose_to(taxonomy, state.input_data)
        categories = self._config.get("categories") or {}
        if not categories:
            raise PipelineInputError("The configuration lists no categories")
        in_scope = self._notes(taxonomy_id, state.input_data.get("scope"))
        notes = [note for note in in_scope if note.text.strip()]
        renderer = NoteContextRenderer(self._repo, SchemaNeighborhoodTraversal(self._repo))
        resolver = EntityRefResolver(
            self._repo, lambda ids: self._claims.in_taxonomy(taxonomy_id, ids)
        )
        system = system_prompt(taxonomy.title, categories)
        gate = asyncio.Semaphore(max(1, int(self._config.get("concurrency") or 1)))
        total = len(notes)
        done = 0
        self._report_progress(0, total)

        async def split(note: Note) -> _Split:
            nonlocal done
            try:
                async with gate:
                    return await self._split(
                        note, taxonomy, system, categories, renderer, resolver, state.run_id
                    )
            finally:
                done += 1
                self._report_progress(done, total)

        outcomes = await asyncio.gather(*(split(n) for n in notes), return_exceptions=True)
        splits: list[_Split] = []
        failed: list[tuple[str, str]] = []  # (note ref, error)
        for note, outcome in zip(notes, outcomes):
            if isinstance(outcome, asyncio.CancelledError):
                raise outcome
            if isinstance(outcome, BaseException):
                failed.append((note.ref, str(outcome) or type(outcome).__name__))
            else:
                splits.append(outcome)
        llm_metadata = self._llm_metadata(splits, len(failed), started)
        if total and not splits:
            raise PipelineExecutionError(
                f"No note could be split, {failed[0][0]}: {failed[0][1]}",
                llm_metadata=llm_metadata,
            )
        claims = [c for s in splits for c in s.claims]
        warnings = [{"stage": "split", "note": ref, "error": error} for ref, error in failed]
        result = {
            "status": "completed_with_warnings" if failed else "completed",
            "taxonomy_id": taxonomy_id,
            "scope": state.input_data.get("scope"),
            "notes": len(splits),
            "notes_skipped": len(in_scope) - total,
            "claims": len(claims),
            "claims_removed": sum(s.removed for s in splits),
            "unresolved_refs": sum(len(c.unresolved_refs) for c in claims),
            "errors": [f"{ref}: {error}" for ref, error in failed][:MAX_REPORTED_ERRORS],
            "error_count": len(failed),
            "tokens_in": llm_metadata["tokens_in"],
            "tokens_out": llm_metadata["tokens_out"],
            "wall_ms": llm_metadata["wall_ms"],
        }
        return replace(
            cast(NotesToClaimsState, state),
            current_status=PipelineRunStatus.COMPLETED,
            result=result,
            llm_metadata=llm_metadata,
            parse_warnings=[*state.parse_warnings, *warnings],
        )

    async def _split(
        self,
        note: Note,
        taxonomy: Taxonomy,
        system: str,
        categories: dict[str, str],
        renderer: NoteContextRenderer,
        resolver: EntityRefResolver,
        run_id: Optional[str],
    ) -> _Split:
        subject_id = resolver.resolve(note.subject) if note.subject else None
        subject = renderer.subject(subject_id)
        context = renderer.render(subject, taxonomy)
        if note.proposed_definition:
            context += f"\nProposed definition: {note.proposed_definition}"
        response = await self._call_llm(
            system_prompt=system,
            user_prompt=user_prompt(renderer.heading(subject, taxonomy), note.text, context),
            model=self._config["model"],
            temperature=self._config.get("temperature", 0.0),
            max_tokens=self._config.get("max_tokens", 4000),
            response_format="json",
        )
        try:
            split = parse_split(response.content, categories)
        except ValueError as exc:
            cut = " (cut off at max_tokens)" if response.finish_reason == "length" else ""
            raise PipelineExecutionError(f"{exc}{cut}") from exc
        # An unresolved subject is kept first among each claim's unresolved refs
        unresolved_subject = [note.subject] if note.subject and subject_id is None else []
        claims = []
        for n, item in enumerate(split, start=1):
            resolved = [(ref, resolver.resolve(ref)) for ref in item.affected_ids]
            claims.append(
                Claim(
                    taxonomy_id=taxonomy.id,
                    key=f"{note.ref}#{n}",
                    text=item.text,
                    note_ref=note.ref,
                    note_source=note.source,
                    note_text=note.text,
                    subject_id=subject_id,
                    category_hint=item.category,
                    affected_ids=[entity_id for _, entity_id in resolved if entity_id],
                    unresolved_refs=[
                        *unresolved_subject,
                        *(ref for ref, entity_id in resolved if entity_id is None),
                    ],
                    proposed_change=item.proposed_change,
                    source_run_id=run_id,
                )
            )
        # Upsert first, so unchanged claims keep their triage and verdict; then
        # drop only the keys this split no longer produced
        stored = self._claims.submit(taxonomy.id, claims) if claims else []
        removed = self._claims.delete_note_claims(
            taxonomy.id, note.ref, keep_keys=[c.key for c in claims]
        )
        return _Split(claims=stored, removed=removed, response=response)

    def _notes(self, taxonomy_id: str, scope: Any) -> list[Note]:
        """
        The notes in scope: {notes: [{ref, subject, text, source?}]} from the
        client, {proposal_id} (its operations' notes and its decisions'
        reasons), or {since} (decision reasons in the taxonomy's gold since
        then).
        """
        if not isinstance(scope, dict) or len(set(scope) & set(SCOPE_FORMS)) != 1:
            raise PipelineInputError(
                "scope must be one of {notes: [{ref, subject, text}]}, {proposal_id} or {since}"
            )
        if set(scope) - set(SCOPE_FORMS):
            raise PipelineInputError(
                f"scope takes only one of {', '.join(SCOPE_FORMS)}, not"
                f" {', '.join(sorted(set(scope) - set(SCOPE_FORMS)))}"
            )
        if "notes" in scope:
            return client_notes(scope["notes"])
        if self._proposals is None:
            raise PipelineInputError("Proposals are not available to read notes from")
        if "proposal_id" in scope:
            proposal_id = str(scope["proposal_id"])
            try:
                proposal = self._proposals.get(proposal_id)
            except ChangeProposalNotFoundError as exc:
                raise PipelineInputError(f"No proposal {proposal_id}") from exc
            if proposal.taxonomy_id != taxonomy_id:
                raise PipelineInputError(f"Proposal {proposal_id} is about another taxonomy")
            decisions = self._proposals.list_decisions(
                DecisionFilter(taxonomy_id=taxonomy_id, proposal_id=proposal_id)
            )
            return proposal_notes(proposal, decisions)
        since = _datetime(scope["since"])
        return decision_notes(
            self._proposals.list_decisions(
                DecisionFilter(taxonomy_id=taxonomy_id, decided_from=since)
            )
        )

    def _llm_metadata(self, splits: list[_Split], failures: int, started: float) -> dict[str, Any]:
        """Tokens and latency of the run's LLM calls (the provider reports no cost)."""
        responses = [s.response for s in splits]
        return {
            "model": self._config["model"],
            "requests": len(responses) + failures,
            "failed_requests": failures,
            "tokens_in": sum(r.tokens_in for r in responses),
            "tokens_out": sum(r.tokens_out for r in responses),
            "latency_ms_total": round(sum(r.duration_ms for r in responses), 1),
            "wall_ms": round((time.monotonic() - started) * 1000, 1),
        }


def _datetime(value: Any) -> datetime:
    """An ISO 8601 time; one without a zone is UTC."""
    try:
        when = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise PipelineInputError(f"since must be an ISO 8601 time, not {value!r}") from exc
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)
