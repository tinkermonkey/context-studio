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
from collections.abc import Callable, Mapping
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
from .drafts import PlannedDraft, TripleFieldCompleter, plan_drafts
from .plan import (
    RankedAnswer,
    Reflection,
    build_plan,
    outcome_counts,
    plan_counts,
    reflection_outcome,
)
from .questions import QUESTION_NAMES, RelationshipCatalog, sorting_questions

PredicateCatalogLookup = Callable[[str], Mapping[str, Mapping[str, Any]] | None]
MAX_REPORTED_ERRORS = 20


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
            complete_fields: Completes an update that changes a type's triple
                (e.g. a DR identifier and reference); None leaves it as is
            config: The run's configuration (see configurations/default.py)
        """
        super().__init__(None, run_id, status_writer)
        self._repo = ontology_repo
        self._decision_models = decision_models
        self._proposals = proposal_service
        self._predicate_catalog = predicate_catalog
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

        predicates = self._predicate_catalog(taxonomy_id) if self._predicate_catalog else None
        catalog = RelationshipCatalog.for_taxonomy(self._repo, taxonomy_id, predicates)
        scope = self._scope(state.input_data.get("scope"), catalog, taxonomy.title)
        model = self._decision_models.get(self._config.get("decision_model"))
        builder = EvidencePackBuilder(self._repo, predicates)
        policy = ContextPolicy(self._config.get("context_policy") or ContextPolicy.SUMMARY)

        total = len(scope.types)
        done = 0
        self._report_progress(0, total)

        async def reflect(prop: PropertyDefinition) -> Reflection:
            nonlocal done
            try:
                return await self._reflect(prop, catalog, model, builder, policy)
            finally:
                done += 1
                self._report_progress(done, total)

        outcomes = await asyncio.gather(
            *(reflect(prop) for prop in scope.types), return_exceptions=True
        )
        reflections: list[Reflection] = []
        errors: list[str] = []
        for prop, outcome in zip(scope.types, outcomes):
            if isinstance(outcome, asyncio.CancelledError):
                raise outcome
            if isinstance(outcome, BaseException):
                errors.append(f"{catalog.triple(prop)}: {outcome}")
            else:
                reflections.append(outcome)
        if total and not reflections:
            raise PipelineExecutionError(
                f"The decision model answered none of {total} relationship types: {errors[0]}"
            )

        plan = build_plan(reflections, catalog.by_triple)
        planned = plan_drafts(plan, catalog, self._complete_fields)
        proposal_id, proposed, dropped = self._propose(
            taxonomy_id, scope, model.name, planned, state.run_id
        )

        costs = [r.cost_usd for r in reflections if r.cost_usd is not None]
        latencies = [r.latency_ms for r in reflections if r.latency_ms is not None]
        cost = sum(costs) if costs else None
        wall_ms = round((time.monotonic() - started) * 1000, 1)
        llm_metadata = {
            "decision_model": model.name,
            "requests": len(reflections) + len(errors),
            "failed_requests": len(errors),
            "cost_usd": round(cost, 6) if cost is not None else None,
            "latency_ms_total": round(sum(latencies), 1),
            "latency_ms_mean": round(sum(latencies) / len(latencies), 1) if latencies else None,
            "latency_ms_max": round(max(latencies), 1) if latencies else None,
            "wall_ms": wall_ms,
        }
        result = {
            "status": "completed",
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
                    "replacement": [str(r) for r in row.replacement],
                    "replacement_exists": row.replacement_exists,
                    "p": round(row.p, 3),
                    "alternatives": list(row.alternatives),
                }
                for row in plan
            ],
            "operations": proposed,
            "dropped_operations": dropped,
            "proposal_id": proposal_id,
            "errors": errors[:MAX_REPORTED_ERRORS],
            "error_count": len(errors),
            "cost_usd": llm_metadata["cost_usd"],
            "latency_ms_total": llm_metadata["latency_ms_total"],
            "wall_ms": wall_ms,
            "reflections": [r.to_json() for r in reflections],
        }
        return replace(
            cast(RelationshipReflectionState, state),
            current_status=PipelineRunStatus.COMPLETED,
            result=result,
            llm_metadata=llm_metadata,
        )

    async def _reflect(
        self,
        prop: PropertyDefinition,
        catalog: RelationshipCatalog,
        model: DecisionModel,
        builder: EvidencePackBuilder,
        policy: ContextPolicy,
    ) -> Reflection:
        sq = sorting_questions(
            prop,
            catalog,
            top=int(self._config.get("top") or 8),
            general_predicates=self._config.get("general_predicates") or (),
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
        planned: list[PlannedDraft],
        run_id: str,
    ) -> tuple[str | None, int, list[dict[str, Any]]]:
        """
        Propose the operations as one proposal. Operations the proposal
        service refuses are dropped (and reported) and the rest proposed again,
        so one bad row does not waste the run.

        Returns:
            The proposal id (None when nothing was proposed), the number of
            operations proposed, and the problems of those dropped
        """
        dropped: list[dict[str, Any]] = []
        drafts = [p.draft for p in planned]
        while drafts:
            try:
                proposal = self._proposals.propose(
                    taxonomy_id=taxonomy_id,
                    title=f"Reflection: {scope.label} ({len(drafts)} relationship changes)",
                    operations=drafts,
                    source=ProposalSource.PIPELINE,
                    rationale=(
                        "Relationship types whose sorting questions (best source, best target,"
                        " best predicate) a concrete alternative won. Each operation carries its"
                        " plan kind, p, the ranked answers and the evidence pack the decision"
                        " model read."
                    ),
                    source_detail=(
                        f"schema_relationship_reflection run {run_id}; decision model {model_name}"
                    ),
                )
                return proposal.id, len(drafts), dropped
            except ProposalValidationError as exc:
                bad = {e.seq for e in exc.errors if e.seq is not None}
                if not bad:
                    raise
                dropped += [
                    {"seq": e.seq, "code": e.code, "message": e.message}
                    for e in exc.errors
                    if e.seq is not None
                ]
                drafts = [d for d in drafts if d.seq not in bad]
        return None, 0, dropped
