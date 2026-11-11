"""
An individual-extraction run's merged triples on a source as proposal
operations (#1552).

Individuals come from typing triples (an individual ``is_a`` a class): one
create per mention (label, ignoring case), in every class it was typed with.
A mention recognized as an existing individual (its triple carries the id, or
an individual of one of its classes in the dataset has its title) gets no
create; operations point at the existing one. The same rules as applying a
run (`apply_service.py`) decide which classes an individual may be created in
and which existing individual a mention is.

A new individual's create carries a ref, its title and class_ids, the best
confidence of its typing triples as probability, every passage it was found in
as evidence ({source_id, page, start, end, quote}), and its recognition near
misses as alternatives ({kind: existing, entity_id, similarity}).

Relationships come from triples whose predicate is a relationship type: a
create whose ends are "$ref" of an individual create or an existing id, with
the triple's passages and confidence. A relationship that already exists, or
whose end or type can't be resolved, is skipped.

Literal (data property) triples are not proposed: extraction emits none, and
applying a run supports none.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from domain.extraction.services import class_reference_aliases
from domain.ontology.entities import Class
from domain.ontology.ports import OntologyRepository
from domain.pipelines.candidate_ids import mention_key
from domain.pipelines.individual_extraction.apply_service import (
    find_individual_by_label,
    typed_classes,
)
from domain.pipelines.source_operations import (
    OperationPlan,
    PlannedOperation,
    best_probability,
    merged_evidence,
    passage_evidence,
)
from domain.versioning.proposal_service import OperationDraft
from domain.versioning.proposals import AlternativeKind, OperationKind, OperationType


@dataclass
class _Individual:
    """One mention's create, gathered over its typing triples."""

    label: str
    class_ids: list[str] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    confidences: list[Any] = field(default_factory=list)
    alternatives: list[dict[str, Any]] = field(default_factory=list)
    existing_id: str | None = None


@dataclass
class _Relationship:
    source: str
    target: str
    property_id: str
    label: str
    evidence: list[dict[str, Any]] = field(default_factory=list)
    confidences: list[Any] = field(default_factory=list)


def plan_individual_operations(
    triples: Sequence[dict[str, Any]],
    repo: OntologyRepository,
    taxonomy_id: str,
    dataset_id: str | None,
    source_id: str,
    page_starts: Sequence[int],
) -> OperationPlan:
    """
    Plan a run's merged triples as individual and relationship creates.

    Args:
        triples: The run's merged triples (with passages, near_matches)
        repo: The ontology, for classes, existing individuals and relationships
        taxonomy_id: The taxonomy the run extracted for
        dataset_id: The dataset the individuals go into
        source_id: The source the passages are in
        page_starts: Offset at which each of its pages starts

    Returns:
        The individual creates (seq 1..), then the relationship creates
    """
    plan = OperationPlan()
    aliases = _class_aliases(repo, taxonomy_id)
    individuals: dict[str, _Individual] = {}
    for triple in triples:
        subject = triple.get("subject") or {}
        if subject.get("kind") != "individual" or not _is_typing(triple):
            continue
        label = str(subject.get("label") or "").strip()
        if not label:
            plan.skip("(no label)", "invalid")
            continue
        class_ids = _typing_class_ids(repo, triple, aliases)
        if not class_ids:
            plan.skip(label, "missing_class")
            continue
        individual = individuals.setdefault(mention_key(label), _Individual(label))
        individual.class_ids += [c for c in class_ids if c not in individual.class_ids]
        individual.evidence = merged_evidence(
            individual.evidence, _evidence(triple, source_id, page_starts)
        )
        individual.confidences.append(triple.get("confidence"))
        individual.alternatives = _with_alternatives(
            individual.alternatives, triple.get("near_matches"), repo, dataset_id
        )
        if individual.existing_id is None:
            individual.existing_id = _existing_individual(repo, subject.get("id"), dataset_id)

    # Mention key -> "$ref" of its create, or the existing individual's id
    resolved: dict[str, str] = {}
    for key, individual in individuals.items():
        existing = individual.existing_id or find_individual_by_label(
            repo, individual.label, individual.class_ids, dataset_id
        )
        if existing is not None:
            resolved[key] = existing
            continue
        ref = f"i{len(plan.operations) + 1}"
        resolved[key] = f"${ref}"
        plan.operations.append(
            PlannedOperation(
                draft=OperationDraft(
                    seq=len(plan.operations) + 1,
                    op=OperationType.CREATE,
                    kind=OperationKind.INDIVIDUAL,
                    ref=ref,
                    fields={"title": individual.label, "class_ids": individual.class_ids},
                    evidence=individual.evidence,
                    probability=best_probability(*individual.confidences),
                    alternatives=individual.alternatives,
                ),
                label=individual.label,
            )
        )

    relationships: dict[tuple[str, str, str], _Relationship] = {}
    for triple in triples:
        relationship = _relationship(triple, repo, resolved, dataset_id, plan)
        if relationship is None:
            continue
        key = (relationship.source, relationship.property_id, relationship.target)
        found = relationships.setdefault(key, relationship)
        found.evidence = merged_evidence(found.evidence, _evidence(triple, source_id, page_starts))
        found.confidences.append(triple.get("confidence"))

    for relationship in relationships.values():
        ends = (relationship.source, relationship.target)
        plan.operations.append(
            PlannedOperation(
                draft=OperationDraft(
                    seq=len(plan.operations) + 1,
                    op=OperationType.CREATE,
                    kind=OperationKind.RELATIONSHIP,
                    fields={
                        "source_id": relationship.source,
                        "target_id": relationship.target,
                        "property_definition_id": relationship.property_id,
                    },
                    evidence=relationship.evidence,
                    probability=best_probability(*relationship.confidences),
                ),
                label=relationship.label,
                needs=frozenset(end[1:] for end in ends if end.startswith("$")),
            )
        )
    return plan


def _is_typing(triple: dict[str, Any]) -> bool:
    """An individual ``is_a`` a class: the object is a class and no relationship type is named."""
    obj = triple.get("object") or {}
    predicate = triple.get("predicate") or {}
    return obj.get("kind") == "class" and not predicate.get("property_definition_id")


def _class_aliases(repo: OntologyRepository, taxonomy_id: str) -> dict[str, Class]:
    """Every identifying form of the taxonomy's classes (lowercased) -> the class."""
    aliases: dict[str, Class] = {}
    for scheme in repo.list_concept_schemes(taxonomy_id=taxonomy_id, limit=None):
        for cls in repo.list_classes(concept_scheme_id=scheme.id, limit=None):
            for alias in class_reference_aliases(cls):
                aliases.setdefault(alias.strip().lower(), cls)
    return aliases


def _typing_class_ids(
    repo: OntologyRepository, triple: dict[str, Any], aliases: dict[str, Class]
) -> list[str]:
    """
    The classes a typing triple types its individual with: the class its object
    names (by id, else by reference, identifier or title), and any class ids
    the subject carries; only those an individual may be created in.
    """
    subject = triple.get("subject") or {}
    obj = triple.get("object") or {}
    candidates: list[str] = []
    named = aliases.get(str(obj.get("label") or "").strip().lower())
    for class_id in [obj.get("id"), named.id if named else None, *(subject.get("class_ids") or [])]:
        if isinstance(class_id, str) and class_id and class_id not in candidates:
            candidates.append(class_id)
    return [cls.id for cls in typed_classes(repo, candidates)]


def _existing_individual(
    repo: OntologyRepository, entity_id: Any, dataset_id: str | None
) -> str | None:
    """The id of an existing individual in the dataset (datasets never share data), else None."""
    if not isinstance(entity_id, str) or not entity_id:
        return None
    individual = repo.get_individual(entity_id)
    if individual is None or dataset_id not in (None, individual.dataset_id):
        return None
    return individual.id


def _with_alternatives(
    current: list[dict[str, Any]],
    near_matches: Any,
    repo: OntologyRepository,
    dataset_id: str | None,
) -> list[dict[str, Any]]:
    """
    A create's alternatives with a typing triple's near matches added: each an
    existing individual of the dataset, once, keeping its best similarity, best first.
    """
    best = {a["entity_id"]: a for a in current}
    for match in near_matches if isinstance(near_matches, list) else []:
        entity_id = match.get("entity_id") if isinstance(match, dict) else None
        if _existing_individual(repo, entity_id, dataset_id) is None:
            continue
        similarity = best_probability(match.get("similarity"))
        known = best.get(entity_id)
        if known is None or (similarity or 0.0) > (known["similarity"] or 0.0):
            best[entity_id] = {
                "kind": AlternativeKind.EXISTING.value,
                "entity_id": entity_id,
                "similarity": round(similarity, 4) if similarity is not None else None,
            }
    return sorted(best.values(), key=lambda a: a["similarity"] or 0.0, reverse=True)


def _relationship(
    triple: dict[str, Any],
    repo: OntologyRepository,
    resolved: dict[str, str],
    dataset_id: str | None,
    plan: OperationPlan,
) -> _Relationship | None:
    """A relationship triple's create with its ends resolved, or None (skipped, or not one)."""
    predicate = triple.get("predicate") or {}
    property_id = predicate.get("property_definition_id")
    subject, obj = triple.get("subject") or {}, triple.get("object") or {}
    label = " ".join(
        str(part or "").strip()
        for part in (subject.get("label"), predicate.get("label"), obj.get("label"))
    )
    if _is_typing(triple):
        return None
    if obj.get("kind") == "literal":
        plan.skip(label, "literal")
        return None
    if not property_id:
        plan.skip(label, "unresolved_predicate")
        return None
    prop = repo.get_property_definition(str(property_id))
    if prop is None:
        plan.skip(label, "unresolved_predicate")
        return None
    if prop.derived:
        plan.skip(label, "derived_type")
        return None
    source = _end(subject, repo, resolved, dataset_id)
    target = _end(obj, repo, resolved, dataset_id)
    if source is None or target is None:
        plan.skip(label, "unresolved_endpoint")
        return None
    if source == target:
        plan.skip(label, "self_loop")
        return None
    if not source.startswith("$") and not target.startswith("$"):
        if repo.list_relationships(
            source_id=source, target_id=target, property_id=prop.id, limit=1
        ):
            plan.skip(label, "exists")
            return None
    return _Relationship(source, target, prop.id, label)


def _end(
    node: dict[str, Any], repo: OntologyRepository, resolved: dict[str, str], dataset_id: str | None
) -> str | None:
    """
    A relationship end: an existing individual (by id, else the mention's
    resolution), a planned create's "$ref", or a class; else None.
    """
    if node.get("kind") == "class":
        cls = repo.get_class(str(node.get("id") or ""))
        return cls.id if cls is not None else None
    if node.get("kind") != "individual":
        return None
    existing = _existing_individual(repo, node.get("id"), dataset_id)
    if existing is not None:
        return existing
    return resolved.get(mention_key(str(node.get("label") or "")))


def _evidence(
    triple: dict[str, Any], source_id: str, page_starts: Sequence[int]
) -> list[dict[str, Any]]:
    """A triple's passages as evidence; a triple without passages offers its provenance."""
    passages = triple.get("passages")
    if not passages:
        provenance = triple.get("provenance")
        if isinstance(provenance, str):
            provenance = {"quote": provenance}
        passages = provenance if isinstance(provenance, list) else [provenance or {}]
    return passage_evidence([p for p in passages if isinstance(p, dict)], source_id, page_starts)
