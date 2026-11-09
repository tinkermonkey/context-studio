"""
Orchestrator for the schema relationship reflection pipeline.

For every relationship type in scope (a scheme, a list of relationship types,
or the whole taxonomy) the decision model answers three sorting questions
(see `questions.py`) about the type's evidence pack. The answers are
classified, grouped into a change plan (`plan.py`) and proposed as one change
proposal (`drafts.py`, source pipeline) for a person to review. The run never
changes the ontology itself.

Input: taxonomy_id (required) and scope:
- None: every relationship type of the taxonomy
- a scheme id or identifier (str, or {"concept_scheme_id": ...}): the types
  whose domain is a class of that scheme
- relationship type ids or identifiers (list, or {"relationship_type_ids": [...]})

The decision model is the configured default instance unless the
configuration names one (`decision_model`). Cost and latency are summed from
the answers and recorded on the run.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, cast

from domain.decision.ports import DecisionModel, DecisionModels
from domain.decision.value_objects import ChoiceAnswer
from domain.ontology.entities import PropertyDefinition
from domain.ontology.evidence import ContextPolicy, EvidencePackBuilder
from domain.ontology.ports import OntologyRepository
from domain.pipelines.entities import PipelineRunStatus
from domain.pipelines.exceptions import PipelineExecutionError, PipelineInputError
from domain.pipelines.orchestration.base import PipelineOrchestrator, PipelineState
from domain.pipelines.ports import PipelineRunStatusWriter
from domain.versioning.exceptions import ProposalValidationError
from domain.versioning.proposal_service import ProposalService
from domain.versioning.proposals import ProposalSource

from .configurations.default import get_default_config
from .drafts import TripleFieldCompleter, plan_drafts
from .plan import (
    PlannedChange,
    RankedAnswer,
    Reflection,
    build_plan,
    outcome_counts,
    plan_counts,
    reflection_outcome,
)
from .questions import QUESTION_NAMES, RelationshipCatalog, sorting_questions

PredicateCatalogLookup = Callable[[str], Mapping[str, Mapping[str, Any]] | None]
GeneralPredicatesLookup = Callable[[str], Sequence[str]]
MAX_REPORTED_ERRORS = 20
MAX_LISTED = 5


@dataclass
class RelationshipReflectionState(PipelineState):
    """State for a reflection run (the input names the taxonomy and scope)."""


@dataclass(frozen=True)
class _Scope:
    label: str
    types: list[PropertyDefinition]
    description: Any


class RelationshipReflectionOrchestrator(PipelineOrchestrator):
    """Asks the sorting questions, builds the change plan and proposes it."""

    def __init__(
        self,
        ontology_repo: OntologyRepository,
        decision_models: DecisionModels,
        proposal_service: ProposalService,
        predicate_catalog: PredicateCatalogLookup | None = None,
        general_predicates: GeneralPredicatesLookup | None = None,
        complete_fields: TripleFieldCompleter | None = None,
        config: dict[str, Any] | None = None,
        run_id: str | None = None,
        status_writer: PipelineRunStatusWriter | None = None,
    ) -> None:
        """
        Args:
            ontology_repo: The ontology to reflect on
            decision_models: The configured decision-model instances
            proposal_service: Where the change proposal goes
            predicate_catalog: Taxonomy id -> predicate catalog (predicate ->
                {"description": ...}), or None where a taxonomy has none
            general_predicates: Taxonomy id -> predicates to offer after a
                type's own (only those the taxonomy knows are offered); none
                when omitted
            complete_fields: Completes an update that changes a type's triple
                (e.g. a DR identifier and reference); None leaves it as is
            config: The run's configuration (see configurations/default.py)
        """
        super().__init__(None, run_id, status_writer)
        self._repo = ontology_repo
        self._decision_models = decision_models
        self._proposals = proposal_service
        self._predicate_catalog = predicate_catalog
        self._general_predicates = general_predicates
        self._complete_fields = complete_fields
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
        if taxonomy.mirrored:
            # Its source drives proposals; Context Studio only adjudicates them.
            raise PipelineInputError(
                f"{taxonomy.title} mirrors an external source: its client proposes"
                " changes, so Context Studio runs no reflection on it"
            )

        predicates = self._predicate_catalog(taxonomy_id) if self._predicate_catalog else None
        catalog = RelationshipCatalog.for_taxonomy(self._repo, taxonomy_id, predicates)
        scope = self._scope(state.input_data.get("scope"), catalog, taxonomy.title)
        model = self._decision_models.get(self._config.get("decision_model"))
        builder = EvidencePackBuilder(self._repo, predicates)
        policy = ContextPolicy(self._config.get("context_policy") or ContextPolicy.SUMMARY)
        general = tuple(self._general_predicates(taxonomy_id)) if self._general_predicates else ()

        total = len(scope.types)
        done = 0
        self._report_progress(0, total)

        async def reflect(prop: PropertyDefinition) -> Reflection:
            nonlocal done
            try:
                return await self._reflect(prop, catalog, model, builder, policy, general)
            finally:
                done += 1
                self._report_progress(done, total)

        outcomes = await asyncio.gather(
            *(reflect(prop) for prop in scope.types), return_exceptions=True
        )
        reflections: list[Reflection] = []
        failed: list[tuple[str, str]] = []  # (relationship type, error)
        for prop, outcome in zip(scope.types, outcomes):
            if isinstance(outcome, asyncio.CancelledError):
                raise outcome
            if isinstance(outcome, BaseException):
                failed.append((str(catalog.triple(prop)), str(outcome) or type(outcome).__name__))
            else:
                reflections.append(outcome)
        llm_metadata = _llm_metadata(model.name, reflections, len(failed), started)
        if total and not reflections:
            raise PipelineExecutionError(
                f"The decision model answered none of {total} relationship types:"
                f" {failed[0][0]}: {failed[0][1]}",
                llm_metadata=llm_metadata,
            )

        try:
            plan = build_plan(reflections, catalog.by_triple)
            proposal_id, proposed, refused = self._propose(
                taxonomy_id, scope, model.name, plan, catalog, failed, total, state.run_id
            )
        except Exception as exc:
            raise PipelineExecutionError(
                f"Proposing the change plan failed: {exc}", llm_metadata=llm_metadata
            ) from exc
        llm_metadata["wall_ms"] = _since(started)

        warnings: list[dict[str, Any]] = [
            {"stage": "reflect", "relationship_type": triple, "error": error}
            for triple, error in failed
        ]
        warnings += [{"stage": "propose", **item} for item in refused]
        planned_rows = sum(1 for row in plan if row.replacement != row.current)
        if planned_rows and proposal_id is None:
            warnings.append(
                {
                    "stage": "propose",
                    "error": (
                        f"All {planned_rows} planned operations were refused;"
                        " no proposal was made"
                    ),
                }
            )
        result = {
            "status": "completed_with_warnings" if warnings else "completed",
            "taxonomy_id": taxonomy_id,
            "scope": scope.description,
            "scope_label": scope.label,
            "relationship_types": total,
            "outcomes": outcome_counts(reflections),
            "plan_kinds": plan_counts(plan),
            "plan": [
                {
                    "property_id": row.property_id,
                    "current": str(row.current),
                    "kind": row.kind,
                    "replacement": str(row.replacement),
                    "replacement_exists": row.replacement_exists,
                    "p": round(row.p, 3),
                    "alternatives": list(row.alternatives),
                }
                for row in plan
            ],
            "operations": proposed,
            "refused_operations": refused,
            "proposal_id": proposal_id,
            "errors": [f"{t}: {e}" for t, e in failed][:MAX_REPORTED_ERRORS],
            "error_count": len(failed),
            "cost_usd": llm_metadata["cost_usd"],
            "latency_ms_total": llm_metadata["latency_ms_total"],
            "wall_ms": llm_metadata["wall_ms"],
            "reflections": [r.to_json() for r in reflections],
        }
        return replace(
            cast(RelationshipReflectionState, state),
            current_status=PipelineRunStatus.COMPLETED,
            result=result,
            llm_metadata=llm_metadata,
            parse_warnings=[*state.parse_warnings, *warnings],
        )

    async def _reflect(
        self,
        prop: PropertyDefinition,
        catalog: RelationshipCatalog,
        model: DecisionModel,
        builder: EvidencePackBuilder,
        policy: ContextPolicy,
        general: Sequence[str],
    ) -> Reflection:
        sq = sorting_questions(
            prop, catalog, top=int(self._config.get("top") or 8), general_predicates=general
        )
        pack = builder.build_for_relationship_type(prop.id, policy)
        answers = await model.decide_async(pack.text, sq.questions)
        ranked: dict[str, RankedAnswer] = {}
        costs: list[float | None] = []
        latencies: list[float] = []
        for question in QUESTION_NAMES:
            answer = answers.get(question)
            if not isinstance(answer, ChoiceAnswer):
                raise PipelineExecutionError(f"no choice answer to {question}")
            ranked[question] = RankedAnswer.of(answer.choice, answer.probabilities)
            costs.append(answer.cost_usd)
            latencies.append(answer.latency_ms)
        outcome, alternatives = reflection_outcome(sq.triple, ranked)
        return Reflection(
            property_id=prop.id,
            triple=sq.triple,
            answers=ranked,
            candidates=sq.candidates,
            outcome=outcome,
            alternatives=alternatives,
            evidence=pack.text,
            # One request answers all three: its latency, and the answers' cost shares summed
            latency_ms=max(latencies) if latencies else None,
            cost_usd=None if any(c is None for c in costs) else sum(c for c in costs if c),
        )

    def _scope(self, scope: Any, catalog: RelationshipCatalog, taxonomy_title: str) -> _Scope:
        if isinstance(scope, dict):
            if "concept_scheme_id" in scope:
                scope = scope["concept_scheme_id"]
            elif "relationship_type_ids" in scope:
                scope = scope["relationship_type_ids"]
            else:
                raise PipelineInputError(
                    "scope must name concept_scheme_id or relationship_type_ids"
                )
        if scope is None or scope == "":
            return _Scope(taxonomy_title, list(catalog.relationship_types), None)
        if isinstance(scope, str):
            scheme = next(
                (
                    s
                    for s in {c.concept_scheme_id for c in catalog.classes.values()}
                    if self._scheme_matches(s, scope)
                ),
                None,
            )
            if scheme is None:
                raise PipelineInputError(f"No scheme {scope} in the taxonomy")
            types = [
                p
                for p in catalog.relationship_types
                if catalog.classes[p.domain_class_id or ""].concept_scheme_id == scheme
            ]
            found = self._repo.get_concept_scheme(scheme)
            return _Scope(found.title if found else scope, types, {"concept_scheme_id": scheme})
        if isinstance(scope, list) and all(isinstance(x, str) for x in scope):
            wanted = set(scope)
            types = [p for p in catalog.relationship_types if {p.id, p.identifier} & wanted]
            missing = wanted - {p.id for p in types} - {p.identifier for p in types}
            if missing:
                raise PipelineInputError(
                    "Not relationship types between classes of the taxonomy: "
                    + ", ".join(sorted(missing))
                )
            return _Scope(
                f"{len(types)} relationship types",
                types,
                {"relationship_type_ids": [p.id for p in types]},
            )
        raise PipelineInputError(
            "scope must be a scheme id or identifier, a list of relationship type ids, or empty"
        )

    def _scheme_matches(self, scheme_id: str, name: str) -> bool:
        if scheme_id == name:
            return True
        scheme = self._repo.get_concept_scheme(scheme_id)
        return scheme is not None and scheme.identifier == name

    def _propose(
        self,
        taxonomy_id: str,
        scope: _Scope,
        model_name: str,
        plan: list[PlannedChange],
        catalog: RelationshipCatalog,
        failed: list[tuple[str, str]],
        total: int,
        run_id: str,
    ) -> tuple[str | None, int, list[dict[str, Any]]]:
        """
        Propose the plan as one proposal. When the proposal service refuses
        operations, their rows are dropped and the operations rebuilt from the
        rows left, so one that leaned on a dropped one (a delete naming the type
        a dropped update would have produced) is planned afresh.

        Returns:
            The proposal id (None when nothing was proposed), the number of
            operations proposed, and the refused rows with the reasons
        """
        refused: list[dict[str, Any]] = []
        rows = list(plan)
        while True:
            planned = plan_drafts(rows, catalog, self._complete_fields)
            if not planned:
                return None, 0, refused
            drafts = [p.draft for p in planned]
            try:
                proposal = self._proposals.propose(
                    taxonomy_id=taxonomy_id,
                    title=f"Reflection: {scope.label} ({len(drafts)} relationship changes)",
                    operations=drafts,
                    source=ProposalSource.PIPELINE,
                    rationale=_rationale(failed, total, refused),
                    source_detail=(
                        f"schema_relationship_reflection run {run_id}; decision model {model_name}"
                    ),
                )
                return proposal.id, len(drafts), refused
            except ProposalValidationError as exc:
                by_seq = {p.draft.seq: p.row for p in planned}
                reasons: dict[int, list[str]] = {}
                for error in exc.errors:
                    if error.seq in by_seq:
                        reasons.setdefault(error.seq, []).append(f"{error.code}: {error.message}")
                if not reasons:
                    raise
                for seq, messages in reasons.items():
                    row = by_seq[seq]
                    refused.append(
                        {
                            "relationship_type": str(row.current),
                            "property_id": row.property_id,
                            "kind": row.kind,
                            "error": "; ".join(messages),
                        }
                    )
                dropped = {by_seq[seq].property_id for seq in reasons}
                rows = [row for row in rows if row.property_id not in dropped]


def _since(started: float) -> float:
    return round((time.monotonic() - started) * 1000, 1)


def _llm_metadata(
    model_name: str, reflections: list[Reflection], failures: int, started: float
) -> dict[str, Any]:
    """Cost and latency of the run's decision-model calls."""
    costs = [r.cost_usd for r in reflections if r.cost_usd is not None]
    latencies = [r.latency_ms for r in reflections if r.latency_ms is not None]
    return {
        "decision_model": model_name,
        "requests": len(reflections) + failures,
        "failed_requests": failures,
        "cost_usd": round(sum(costs), 6) if costs else None,
        "latency_ms_total": round(sum(latencies), 1),
        "latency_ms_mean": round(sum(latencies) / len(latencies), 1) if latencies else None,
        "latency_ms_max": round(max(latencies), 1) if latencies else None,
        "wall_ms": _since(started),
    }


def _listed(items: list[str]) -> str:
    shown = "; ".join(items[:MAX_LISTED])
    return shown + (f"; and {len(items) - MAX_LISTED} more" if len(items) > MAX_LISTED else "")


def _rationale(failed: list[tuple[str, str]], total: int, refused: list[dict[str, Any]]) -> str:
    """The proposal's rationale, saying what the run could not ask or propose."""
    text = (
        "Relationship types whose sorting questions (best source, best target, best"
        " predicate) a concrete alternative won. Each operation carries its plan kind, p,"
        " the ranked answers and the evidence pack the decision model read."
    )
    notes = []
    if failed:
        notes.append(
            f"{len(failed)} of {total} types not asked: "
            + _listed([f"{t} ({e})" for t, e in failed])
        )
    if refused:
        notes.append(
            f"{len(refused)} operations refused: "
            + _listed([f"{r['relationship_type']} ({r['error']})" for r in refused])
        )
    return text + (f" {'. '.join(notes)}." if notes else "")
