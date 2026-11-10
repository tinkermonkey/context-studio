"""
Claim triage: decision-model questions on each claim, saved on the claim.

For each claim in scope, the orchestrator renders its state (the claim, the
definition pending for its subject, and an evidence pack from the ontology),
asks the triage questions (validity, category, severity, fix scope, and
whether the pending definition already addresses it), and saves the answers as
the claim's triage. It changes nothing in the taxonomy and makes no proposal.
"""

from __future__ import annotations

import asyncio
import time
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any, Optional, cast

from domain.decision.ports import DecisionModel, DecisionModels
from domain.decision.value_objects import Answer, ChoiceAnswer, ScoreAnswer, YesNoAnswer
from domain.ontology.evidence import ContextPolicy, EvidencePackBuilder
from domain.ontology.ports import OntologyRepository
from domain.pipelines.entities import PipelineRunStatus
from domain.pipelines.exceptions import PipelineExecutionError, PipelineInputError
from domain.pipelines.orchestration.base import PipelineOrchestrator, PipelineState
from domain.pipelines.ports import PipelineRunStatusWriter
from domain.versioning.claims import Claim, ClaimFilter, ClaimService, ClaimTriage, Validity
from domain.versioning.proposal_service import ProposalService
from domain.versioning.proposals import (
    OperationKind,
    OperationStatus,
    OperationType,
    ProposalStatus,
)

from .configurations.default import get_default_config
from .questions import ADDRESSED_BY_PROPOSAL, triage_questions
from .state import ClaimStateRenderer

MAX_REPORTED_ERRORS = 20
SCOPE_KEYS = ("keys", "note_ref", "subject_ids", "concept_scheme_id", "untriaged")


@dataclass
class ClaimTriageState(PipelineState):
    """State for a triage run (the input names the taxonomy and scope)."""


class ClaimTriageOrchestrator(PipelineOrchestrator):
    """Asks the triage questions about each claim in scope and saves the answers."""

    def __init__(
        self,
        ontology_repo: OntologyRepository,
        decision_models: DecisionModels,
        claim_service: ClaimService,
        proposal_service: Optional[ProposalService] = None,
        config: Optional[dict[str, Any]] = None,
        run_id: Optional[str] = None,
        status_writer: Optional[PipelineRunStatusWriter] = None,
    ) -> None:
        """
        Args:
            ontology_repo: The ontology the claims are about
            decision_models: The configured decision-model instances
            claim_service: Where the claims are read and their triage saved
            proposal_service: Open proposals, for the definitions pending per
                subject; without it no pending definition is shown
            config: decision_model, context_policy and categories (see the
                default configuration)
            run_id, status_writer: Where the run's status and progress go
        """
        super().__init__(None, run_id, status_writer)
        self._repo = ontology_repo
        self._decision_models = decision_models
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
        claims = self._scope(taxonomy_id, state.input_data.get("scope"))
        model = self._decision_models.get(self._config.get("decision_model"))
        policy = ContextPolicy(self._config.get("context_policy") or ContextPolicy.SUMMARY)
        categories = self._config.get("categories") or {}
        if not categories:
            raise PipelineInputError("The configuration lists no categories")
        renderer = ClaimStateRenderer(self._repo, EvidencePackBuilder(self._repo))
        pending = self._pending_definitions(taxonomy_id)
        total = len(claims)
        done = 0
        self._report_progress(0, total)

        async def triage(claim: Claim) -> ClaimTriage:
            nonlocal done
            try:
                return await self._triage(
                    claim, model, renderer, taxonomy.title, policy, categories, pending, state
                )
            finally:
                done += 1
                self._report_progress(done, total)

        outcomes = await asyncio.gather(*(triage(c) for c in claims), return_exceptions=True)
        triaged: list[ClaimTriage] = []
        failed: list[tuple[str, str]] = []  # (claim key, error)
        for claim, outcome in zip(claims, outcomes):
            if isinstance(outcome, asyncio.CancelledError):
                raise outcome
            if isinstance(outcome, BaseException):
                failed.append((claim.key, str(outcome) or type(outcome).__name__))
            else:
                triaged.append(outcome)
        llm_metadata = _llm_metadata(model.name, triaged, len(failed), started)
        if total and not triaged:
            raise PipelineExecutionError(
                f"The decision model answered none of {total} claims: {failed[0][0]}:"
                f" {failed[0][1]}",
                llm_metadata=llm_metadata,
            )
        warnings = [{"stage": "triage", "claim": key, "error": error} for key, error in failed]
        result = {
            "status": "completed_with_warnings" if failed else "completed",
            "taxonomy_id": taxonomy_id,
            "scope": state.input_data.get("scope"),
            "claims": len(triaged),
            "validity": dict(Counter(t.validity.value for t in triaged)),
            "errors": [f"{key}: {error}" for key, error in failed][:MAX_REPORTED_ERRORS],
            "error_count": len(failed),
            "cost_usd": llm_metadata["cost_usd"],
            "latency_ms_total": llm_metadata["latency_ms_total"],
            "wall_ms": llm_metadata["wall_ms"],
        }
        return replace(
            cast(ClaimTriageState, state),
            current_status=PipelineRunStatus.COMPLETED,
            result=result,
            llm_metadata=llm_metadata,
            parse_warnings=[*state.parse_warnings, *warnings],
        )

    async def _triage(
        self,
        claim: Claim,
        model: DecisionModel,
        renderer: ClaimStateRenderer,
        taxonomy_title: str,
        policy: ContextPolicy,
        categories: Mapping[str, str],
        pending: Mapping[str, Mapping[str, object]],
        state: PipelineState,
    ) -> ClaimTriage:
        definition = pending.get(claim.subject_id or "")
        text = renderer.render(claim, taxonomy_title, policy, definition)
        answers = await model.decide_async(
            text, triage_questions(categories, with_pending_definition=bool(definition))
        )
        triage = _triage_of(answers, model.name, state.run_id)
        self._claims.save_triage(claim.id, triage)
        return triage

    def _scope(self, taxonomy_id: str, scope: Any) -> list[Claim]:
        """
        The claims to triage: claim keys (a list, or {keys}), {note_ref},
        {subject_ids}, {concept_scheme_id} (its classes' claims), optionally
        with {untriaged: true}; no scope means every untriaged claim.
        """
        if scope is None or scope == {}:
            scope = {"untriaged": True}
        if isinstance(scope, list):
            scope = {"keys": scope}
        if not isinstance(scope, dict) or set(scope) - set(SCOPE_KEYS):
            raise PipelineInputError(
                f"scope must be a list of claim keys or an object with {', '.join(SCOPE_KEYS)}"
            )
        triaged = False if scope.get("untriaged") else None
        base = ClaimFilter(taxonomy_id=taxonomy_id, triaged=triaged)
        if scope.get("keys") is not None:
            base = replace(base, keys=tuple(_strings(scope["keys"], "keys")))
        if scope.get("note_ref") is not None:
            base = replace(base, note_ref=str(scope["note_ref"]))
        subjects: Optional[list[str]] = None
        if scope.get("subject_ids") is not None:
            subjects = _strings(scope["subject_ids"], "subject_ids")
        if scope.get("concept_scheme_id") is not None:
            scheme_id = str(scope["concept_scheme_id"])
            scheme = self._repo.get_concept_scheme(scheme_id)
            if scheme is None or scheme.taxonomy_id != taxonomy_id:
                raise PipelineInputError(f"No scheme {scheme_id} in this taxonomy")
            in_scheme = [
                c.id for c in self._repo.list_classes(concept_scheme_id=scheme_id, limit=None)
            ]
            subjects = [s for s in subjects if s in in_scheme] if subjects else in_scheme
        if subjects is None:
            return self._claims.list_claims(base)
        claims: dict[str, Claim] = {}
        for subject_id in subjects:
            for claim in self._claims.list_claims(replace(base, subject_id=subject_id)):
                claims[claim.id] = claim
        return sorted(claims.values(), key=lambda c: (c.created_at, c.key))

    def _pending_definitions(self, taxonomy_id: str) -> dict[str, dict[str, object]]:
        """
        Per class, the fields of the newest pending update to it in an open
        proposal (newest proposal first, then its last such operation).
        """
        if self._proposals is None:
            return {}
        pending: dict[str, dict[str, object]] = {}
        for proposal in self._proposals.list_proposals(
            taxonomy_id=taxonomy_id, status=ProposalStatus.OPEN, limit=1000
        ):
            for operation in reversed(proposal.operations):
                if (
                    operation.kind is OperationKind.CLASS
                    and operation.op is OperationType.UPDATE
                    and operation.status is OperationStatus.PENDING
                    and operation.target_id
                    and operation.target_id not in pending
                ):
                    pending[operation.target_id] = dict(operation.fields)
        return pending


def _strings(value: Any, name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise PipelineInputError(f"scope {name} must be a list of strings")
    return value


def _triage_of(answers: Mapping[str, Answer], model: str, run_id: Optional[str]) -> ClaimTriage:
    """The triage from the decision model's answers."""
    validity = answers.get("validity")
    category = answers.get("category")
    if not isinstance(validity, ChoiceAnswer) or validity.choice is None:
        raise PipelineExecutionError("no answer to validity")
    addressed = answers.get(ADDRESSED_BY_PROPOSAL)
    costs = [a.cost_usd for a in answers.values() if a.cost_usd is not None]
    return ClaimTriage(
        validity=Validity(validity.choice),
        model=model,
        validity_probabilities=dict(validity.probabilities),
        category=category.choice if isinstance(category, ChoiceAnswer) else None,
        category_probabilities=(
            dict(category.probabilities) if isinstance(category, ChoiceAnswer) else {}
        ),
        severity=_level(answers.get("severity")),
        fix_scope=_level(answers.get("fix_scope")),
        addressed_by_proposal=addressed.p_yes if isinstance(addressed, YesNoAnswer) else None,
        calibrated=all(a.calibrated for a in answers.values()),
        cost_usd=round(sum(costs), 6) if costs else None,
        latency_ms=max((a.latency_ms for a in answers.values()), default=None),
        run_id=run_id,
    )


def _level(answer: Optional[Answer]) -> Optional[int]:
    """A score answer's expected level, rounded to the 0-3 scale."""
    if not isinstance(answer, ScoreAnswer) or answer.score is None:
        return None
    return min(3, max(0, round(answer.score)))


def _since(started: float) -> float:
    return round((time.monotonic() - started) * 1000, 1)


def _llm_metadata(
    model_name: str, triaged: list[ClaimTriage], failures: int, started: float
) -> dict[str, Any]:
    """Cost and latency of the run's decision-model calls."""
    costs = [t.cost_usd for t in triaged if t.cost_usd is not None]
    latencies = [t.latency_ms for t in triaged if t.latency_ms is not None]
    return {
        "decision_model": model_name,
        "requests": len(triaged) + failures,
        "failed_requests": failures,
        "cost_usd": round(sum(costs), 6) if costs else None,
        "latency_ms_total": round(sum(latencies), 1),
        "latency_ms_mean": round(sum(latencies) / len(latencies), 1) if latencies else None,
        "wall_ms": _since(started),
    }
