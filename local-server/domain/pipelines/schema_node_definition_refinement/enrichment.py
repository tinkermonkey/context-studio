"""
Definition enrichment (#1517): the definition refinement pipeline's scoped mode.

Given a taxonomy and a scope of classes, asks the LLM, one class at a time, for
an operational definition in DR's shape (cli/scripts/spec-enrich/propose-nodes.ts):
a genus-and-differentia definition, the siblings to use instead and when
(distinguish_from), the standard it follows, and observable evidence signals,
plus notes for a maintainer and a confidence. The changed fields of each class
become one class update, and all of them one change proposal for a person to
review. It never writes the taxonomy itself.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from domain.ontology.entities import Class, PropertyDefinition, Taxonomy
from domain.ontology.ports import OntologyRepository
from domain.ontology.value_objects import (
    normalize_distinguish_from,
    normalize_evidence_signals,
)
from domain.pipelines.exceptions import PipelineExecutionError, PipelineInputError
from domain.pipelines.llm_json import extract_json
from domain.pipelines.ports import LLMResponse
from domain.versioning.exceptions import ProposalValidationError
from domain.versioning.proposal_service import ProposalService
from domain.versioning.proposals import (
    OperationDraft,
    OperationKind,
    OperationType,
    ProposalSource,
)

CallLLM = Callable[[str, str], Awaitable[LLMResponse]]
MAX_DISTINGUISH = 4
MAX_REPORTED_ERRORS = 20

SYSTEM_TASK = "\n".join(
    [
        "# Your task for the one class named in the message",
        (
            "1. definition: one or two sentences in genus-and-differentia form ('A <kind of "
            "thing> that <what sets it apart>'), decidable by a reader who knows the domain. "
            "State what it IS, not why it is useful. Do not start with the class name. No "
            "marketing adjectives."
        ),
        (
            "2. distinguish_from: up to four sibling classes in this scheme that a modeller could"
            ' confuse with this one; for each, the class identifier exactly as listed ("type") '
            "and a clause completing 'Use <that class> instead when ...' (\"when\"). Only real "
            "confusions, not every sibling."
        ),
        (
            "3. standard_reference: the concept or clause in the domain's standard this class "
            "corresponds to (e.g. 'ArchiMate 3.2 §9.3 Application Service', 'OpenAPI 3.0 "
            "Operation Object'), or null if none applies."
        ),
        (
            "4. evidence_signals: exactly three concrete, observable signals that indicate an "
            "instance of this class. Signals, not restatements of the definition."
        ),
        (
            "5. notes: at most 60 words of concerns a maintainer should hear: overlap with "
            "another class, a missing or misnamed attribute, an enum that does not fit. Empty "
            "string if none."
        ),
        "6. confidence: 0 to 1, how sure you are the definition is right.",
        (
            "Be consistent with the sibling definitions above; where a sibling definition is "
            "thin, define this class so the boundary is clear from this side."
        ),
        (
            'Answer with one JSON object: {"definition", "distinguish_from": [{"type", "when"}], '
            '"standard_reference", "evidence_signals", "notes", "confidence"}.'
        ),
    ]
)


@dataclass
class _Enrichment:
    """One class's answer, turned into the fields an update would change."""

    cls: Class
    fields: dict[str, Any]
    notes: str | None
    confidence: float | None
    dropped: list[str] = field(default_factory=list)


@dataclass
class EnrichmentOutcome:
    """What a scoped enrichment run did."""

    proposal_id: str | None
    classes: int
    proposed: int
    unchanged: int
    failed: list[tuple[str, str]]
    refused: list[dict[str, Any]]
    dropped_distinguish: list[str]
    llm_metadata: dict[str, Any]


class DefinitionEnrichment:
    """Asks for each class's operational definition and proposes the changes."""

    def __init__(
        self,
        repo: OntologyRepository,
        proposals: ProposalService,
        call_llm: CallLLM,
        report_progress: Callable[[int, int], None],
        concurrency: int = 4,
    ) -> None:
        self._repo = repo
        self._proposals = proposals
        self._call_llm = call_llm
        self._report_progress = report_progress
        self._concurrency = max(1, concurrency)

    def scope(self, taxonomy: Taxonomy, scope: Any) -> list[Class]:
        """
        The classes to enrich: every class of the taxonomy (no scope), a scheme's
        classes (its id or identifier, or {"concept_scheme_id"}), or classes by
        id or identifier (a list, or {"class_ids"}).

        Raises:
            PipelineInputError: If the scope is malformed or names nothing in the taxonomy
        """
        if isinstance(scope, dict):
            if set(scope) - {"concept_scheme_id", "class_ids"} or len(scope) != 1:
                raise PipelineInputError("scope is {concept_scheme_id} or {class_ids}")
            scope = scope.get("concept_scheme_id") or scope.get("class_ids")
        schemes = {
            s.id: s for s in self._repo.list_concept_schemes(taxonomy_id=taxonomy.id, limit=None)
        }
        if scope is None:
            return [
                c for s in schemes for c in self._repo.list_classes(concept_scheme_id=s, limit=None)
            ]
        if isinstance(scope, str):
            scheme = schemes.get(scope) or next(
                (s for s in schemes.values() if s.identifier == scope), None
            )
            if scheme is None:
                raise PipelineInputError(f"No scheme {scope} in this taxonomy")
            return self._repo.list_classes(concept_scheme_id=scheme.id, limit=None)
        if not isinstance(scope, list) or not all(isinstance(i, str) for i in scope):
            raise PipelineInputError("scope is a scheme, a list of classes, or empty")
        classes = []
        for ref in scope:
            cls = self._repo.get_class(ref) or self._class_by_identifier(ref)
            if cls is None or cls.taxonomy_id != taxonomy.id:
                raise PipelineInputError(f"No class {ref} in this taxonomy")
            classes.append(cls)
        return classes

    async def run(
        self, taxonomy: Taxonomy, classes: list[Class], model: str, run_id: str
    ) -> EnrichmentOutcome:
        """Enrich each class, then propose the changes as one proposal."""
        started = time.monotonic()
        properties = self._repo.list_property_definitions(taxonomy_id=taxonomy.id, limit=None)
        siblings_by_scheme: dict[str, list[Class]] = {}
        for cls in classes:
            if cls.concept_scheme_id not in siblings_by_scheme:
                siblings_by_scheme[cls.concept_scheme_id] = self._repo.list_classes(
                    concept_scheme_id=cls.concept_scheme_id, limit=None
                )
        responses: list[LLMResponse] = []
        unanswered = 0
        limit = asyncio.Semaphore(self._concurrency)
        done = 0
        total = len(classes)
        self._report_progress(0, total)

        async def enrich(cls: Class) -> _Enrichment:
            nonlocal done, unanswered
            async with limit:
                try:
                    system = self._system_prompt(
                        taxonomy, cls, siblings_by_scheme[cls.concept_scheme_id]
                    )
                    try:
                        response = await self._call_llm(
                            system, _user_prompt(cls, properties, self._repo)
                        )
                    except Exception:
                        unanswered += 1
                        raise
                    responses.append(response)
                    return _enrichment(
                        cls, response.content, siblings_by_scheme[cls.concept_scheme_id]
                    )
                finally:
                    done += 1
                    self._report_progress(done, total)

        outcomes = await asyncio.gather(*(enrich(c) for c in classes), return_exceptions=True)
        enriched: list[_Enrichment] = []
        failed: list[tuple[str, str]] = []
        for cls, outcome in zip(classes, outcomes):
            if isinstance(outcome, asyncio.CancelledError):
                raise outcome
            if isinstance(outcome, BaseException):
                failed.append((_label(cls), str(outcome) or type(outcome).__name__))
            else:
                enriched.append(outcome)
        llm_metadata = _llm_metadata(model, responses, unanswered, started)
        if total and not enriched:
            raise PipelineExecutionError(
                f"The LLM answered none of {total} classes: {failed[0][0]}: {failed[0][1]}",
                llm_metadata=llm_metadata,
            )
        changing = [e for e in enriched if e.fields]
        try:
            proposal_id, refused = self._propose(taxonomy, changing, model, run_id, failed)
        except Exception as exc:
            # Keep what the LLM calls cost even though nothing was proposed
            raise PipelineExecutionError(
                f"Proposing the enrichment failed: {exc}", llm_metadata=llm_metadata
            ) from exc
        return EnrichmentOutcome(
            proposal_id=proposal_id,
            classes=total,
            proposed=len(changing) - len(refused),
            unchanged=len(enriched) - len(changing),
            failed=failed,
            refused=refused,
            dropped_distinguish=[d for e in enriched for d in e.dropped],
            llm_metadata=llm_metadata,
        )

    def _propose(
        self,
        taxonomy: Taxonomy,
        changing: list[_Enrichment],
        model: str,
        run_id: str,
        failed: list[tuple[str, str]],
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """
        Propose one update per changed class. When the proposal service refuses
        operations, they are dropped and the rest proposed again.
        """
        refused: list[dict[str, Any]] = []
        rows = list(changing)
        while rows:
            drafts = [
                OperationDraft(
                    seq=seq,
                    op=OperationType.UPDATE,
                    kind=OperationKind.CLASS,
                    target_id=row.cls.id,
                    fields=row.fields,
                    rationale="Operational definition from definition enrichment",
                    notes=row.notes,
                    probability=row.confidence,
                )
                for seq, row in enumerate(rows, start=1)
            ]
            try:
                proposal = self._proposals.propose(
                    taxonomy_id=taxonomy.id,
                    title=f"Definition enrichment ({len(drafts)} classes)",
                    operations=drafts,
                    source=ProposalSource.PIPELINE,
                    rationale=_rationale(failed, refused),
                    source_detail=f"schema_node_definition_refinement run {run_id}; model {model}",
                )
                return proposal.id, refused
            except ProposalValidationError as exc:
                reasons: dict[int, list[str]] = {}
                for error in exc.errors:
                    if error.seq is not None and 1 <= error.seq <= len(rows):
                        reasons.setdefault(error.seq, []).append(f"{error.code}: {error.message}")
                if not reasons:
                    raise
                for seq, messages in reasons.items():
                    refused.append(
                        {"class": _label(rows[seq - 1].cls), "error": "; ".join(messages)}
                    )
                rows = [row for seq, row in enumerate(rows, start=1) if seq not in reasons]
        return None, refused

    def _system_prompt(self, taxonomy: Taxonomy, cls: Class, siblings: list[Class]) -> str:
        scheme = self._repo.get_concept_scheme(cls.concept_scheme_id)
        scheme_label = (scheme.identifier or scheme.title) if scheme else cls.concept_scheme_id
        return "\n".join(
            [
                f"You are the editor of the {taxonomy.title} taxonomy, whose classes must be"
                " definable precisely enough that a reader can decide whether a thing is an"
                " instance. You write operational definitions.",
                "",
                f"# Taxonomy: {taxonomy.title}",
                taxonomy.description or "",
                "",
                f"# Scheme: {scheme_label}",
                (scheme.description or "") if scheme else "",
                "",
                "# All classes in this scheme (current definitions)",
                *(f"- {_label(s)}: {s.description or '(no definition)'}" for s in siblings),
                "",
                SYSTEM_TASK,
            ]
        )

    def _class_by_identifier(self, identifier: str) -> Class | None:
        found = self._repo.get_by_identifier(identifier)
        return found if isinstance(found, Class) else None


def _user_prompt(
    cls: Class, properties: Sequence[PropertyDefinition], repo: OntologyRepository
) -> str:
    attributes = repo.list_attribute_definitions(class_id=cls.id, limit=None)
    outgoing = [p for p in properties if p.domain_class_id == cls.id]
    incoming = [p for p in properties if p.range_class_id == cls.id and p.domain_class_id != cls.id]
    labels = {cls.id: _label(cls)}

    def name(class_id: str | None) -> str:
        if not class_id:
            return "?"
        if class_id not in labels:
            other = repo.get_class(class_id)
            labels[class_id] = _label(other) if other else class_id
        return labels[class_id]

    def edge(p: PropertyDefinition) -> str:
        predicate = p.canonical_predicate or p.identifier
        return f"  {name(p.domain_class_id)} --[{predicate}]--> {name(p.range_class_id)}"

    distinguish = "; ".join(f"{name(e['class_id'])}: {e['when']}" for e in cls.distinguish_from)
    current = [
        f"Current distinguish_from: {distinguish or '(none)'}",
        f"Current evidence_signals: {'; '.join(cls.evidence_signals) or '(none)'}",
        f"Current standard_reference: {cls.standard_reference or '(none)'}",
        "External references: "
        + ("; ".join(f"{r.source}: {r.identifier}" for r in cls.external_references) or "(none)"),
    ]
    edges = [edge(p) for p in outgoing[:40]] + [edge(p) for p in incoming[:40]]
    if len(outgoing) > 40 or len(incoming) > 40:
        edges.append("  ... (truncated)")
    return "\n".join(
        [
            f"Define this class: {_label(cls)}",
            "",
            f"Title: {cls.title}",
            f"Current definition: {cls.description or '(none)'}",
            *current,
            "Attributes: "
            + (
                "; ".join(
                    f"{a.identifier} ({a.datatype}): {a.description or '-'}" for a in attributes
                )
                or "(none)"
            ),
            f"Relationships in which it participates ({len(outgoing)} outgoing,"
            f" {len(incoming)} incoming):",
            *edges,
        ]
    )


def _enrichment(cls: Class, content: str, siblings: list[Class]) -> _Enrichment:
    """
    The fields an update of the class would change from the LLM's answer:
    distinguish_from types resolve to sibling classes (others are dropped).

    Raises:
        PipelineExecutionError: If the answer is not the expected JSON object
    """
    try:
        answer = extract_json(content)
    except json.JSONDecodeError as exc:
        raise PipelineExecutionError("the answer is not JSON") from exc
    if not isinstance(answer, dict):
        raise PipelineExecutionError("the answer is not a JSON object")
    by_label = {_label(s): s.id for s in siblings} | {s.id: s.id for s in siblings}
    distinguish, dropped = [], []
    for entry in answer.get("distinguish_from") or []:
        if not isinstance(entry, dict):
            continue
        other = by_label.get(str(entry.get("type", "")).strip())
        when = str(entry.get("when") or "").strip()
        if other is None or other == cls.id or not when:
            dropped.append(f"{_label(cls)} -> {entry.get('type')}")
            continue
        if all(d["class_id"] != other for d in distinguish):
            distinguish.append({"class_id": other, "when": when})
    distinguish = normalize_distinguish_from(distinguish[:MAX_DISTINGUISH])
    evidence = answer.get("evidence_signals") or []
    evidence = normalize_evidence_signals(
        [str(e) for e in evidence] if isinstance(evidence, list) else []
    )
    standard = answer.get("standard_reference")
    standard = str(standard).strip() or None if standard else None
    definition = str(answer.get("definition") or "").strip()

    # The answer adds or rewords; it never clears what the class already has
    fields: dict[str, Any] = {}
    if definition and definition != (cls.description or ""):
        fields["description"] = definition
    if distinguish:
        merged = _merge_distinguish(cls.distinguish_from, distinguish)
        if merged != cls.distinguish_from:
            fields["distinguish_from"] = merged
    if evidence and evidence != cls.evidence_signals:
        fields["evidence_signals"] = evidence
    if standard and standard != cls.standard_reference:
        fields["standard_reference"] = standard
    notes = str(answer.get("notes") or "").strip() or None
    confidence = answer.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        confidence = None
    else:
        confidence = min(1.0, max(0.0, float(confidence)))
    return _Enrichment(cls, fields, notes, confidence, dropped)


def _merge_distinguish(
    current: list[dict[str, str]], answered: list[dict[str, str]]
) -> list[dict[str, str]]:
    """
    The class's distinguish_from with the answer's entries: an entry for a class
    it already names rewords it in place, a new one is added, and the entries
    the answer doesn't name (another scheme's classes among them) stay.
    """
    new_when = {e["class_id"]: e["when"] for e in answered}
    kept = [{**e, "when": new_when.pop(e["class_id"], e["when"])} for e in current]
    return [*kept, *({"class_id": c, "when": w} for c, w in new_when.items())]


def _label(cls: Class) -> str:
    return cls.identifier or cls.title


def _rationale(failed: list[tuple[str, str]], refused: list[dict[str, Any]]) -> str:
    parts = ["Operational definitions proposed by definition enrichment, one update per class."]
    if failed:
        parts.append(f"{len(failed)} classes got no answer and are not included.")
    if refused:
        parts.append(f"{len(refused)} updates were refused and left out.")
    return " ".join(parts)


def _llm_metadata(
    model: str, responses: list[LLMResponse], failures: int, started: float
) -> dict[str, Any]:
    """Tokens and latency of the run's LLM calls."""
    return {
        "model": model,
        "requests": len(responses) + failures,
        "failed_requests": failures,
        "tokens_in": sum(r.tokens_in for r in responses),
        "tokens_out": sum(r.tokens_out for r in responses),
        "latency_ms_total": round(sum(r.duration_ms for r in responses), 1),
        "wall_ms": round((time.monotonic() - started) * 1000, 1),
    }
