"""
An individual-extraction run's merged triples on a source as proposal
operations (#1552).

Individuals come from typing triples (an individual ``is_a`` a class, as the
extraction service decides: `is_typing_triple`): one
create per mention, in every class it was typed with. Mentions are the same
when their labels share a key among the run's individual labels (`LabelKeys`,
#1575: "screws (D)" and "Screw", "Moen Inc." and "Moen", but not "Screw (B)"
and "Screw (D)", nor a name and the same name with a corporate suffix typed
with different classes: "Wikimedia Enterprise" a product and "Wikimedia
Enterprise LLC" a business); the create is titled with their preferred label. A
one-word mention that is the head word of exactly one other mention's label,
typed with all of its classes, is that mention ("bracket" is "Mounting
Bracket"), unless it names an existing individual. A mention recognized as an
existing individual (its triple carries the id, or an individual of one of its
classes in the dataset is titled with one of its labels) gets no create; operations point at the
existing one. The same rules as applying a run (`apply_service.py`) decide
which classes an individual may be created in and which existing individual a
mention is.

A new individual's create carries a ref, its title and class_ids, the best
confidence of its typing triples as probability, every passage it was found in
as evidence ({source_id, page, start, end, quote}), and its near matches as
alternatives ({kind: existing, entity_id, similarity}): recognition's near
misses, then the individuals of its classes in the dataset whose label has its
key, or (for a key of three or more words) its key without the first word
("Moen handheld shower" offers "handheld shower"; "Hand Shower" does not offer
"Shower"), with no similarity.

Relationships come from triples whose predicate is a relationship type: a
create whose ends are "$ref" of an individual create or an existing id, with
the triple's passages and confidence. A relationship that already exists,
whose end or type can't be resolved, or whose ends don't fit the type's domain
and range (`domain_range_mismatch`, inheritance-aware: #1574), is skipped.

Literal (data property) triples are not proposed: extraction emits none, and
applying a run supports none.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from domain.extraction.services import class_reference_aliases, is_typing_triple
from domain.ontology.entities import Class
from domain.ontology.ports import OntologyRepository
from domain.ontology.relationship_fit import RelationshipFit
from domain.pipelines.individual_extraction.apply_service import (
    find_individual_by_label,
    typed_classes,
)
from domain.pipelines.individual_extraction.labels import (
    LabelKeys,
    head_word,
    without_corporate_mark,
    without_leading_word,
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

    labels: list[str] = field(default_factory=list)
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
    # Each typing triple of a labelled individual, with its label and classes
    typings: list[tuple[dict[str, Any], str, list[str]]] = []
    for triple in triples:
        subject = triple.get("subject") or {}
        if subject.get("kind") != "individual" or not is_typing_triple(triple):
            continue
        label = str(subject.get("label") or "").strip()
        if not label:
            plan.skip("(no label)", "invalid")
            continue
        class_ids = _typing_class_ids(repo, triple, aliases)
        if not class_ids:
            plan.skip(label, "missing_class")
            continue
        typings.append((triple, label, class_ids))

    keys = LabelKeys(
        (
            node.get("label")
            for triple in triples
            for node in (triple.get("subject"), triple.get("object"))
            if isinstance(node, dict) and node.get("kind") == "individual"
        ),
        typed=((label, class_id) for _, label, class_ids in typings for class_id in class_ids),
    )
    individuals: dict[str, _Individual] = {}
    for triple, label, class_ids in typings:
        subject = triple.get("subject") or {}
        individual = individuals.setdefault(keys.key(label), _Individual())
        individual.labels.append(label)
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

    existing_ids = {
        key: individual.existing_id or _titled(repo, individual, dataset_id)
        for key, individual in individuals.items()
    }
    folded = _fold_head_words(individuals, existing_ids)
    existing_keys = _ExistingKeys(repo, dataset_id)
    # Individual key -> "$ref" of its create, or the existing individual's id
    resolved: dict[str, str] = {}
    # "$ref" of an individual create -> its classes
    planned: dict[str, list[str]] = {}
    for key, individual in individuals.items():
        if key in folded:
            continue
        existing = existing_ids[key]
        if existing is not None:
            resolved[key] = existing
            continue
        individual.alternatives = _merged_alternatives(
            individual.alternatives,
            [
                _existing_alternative(entity_id)
                for entity_id in existing_keys.matches(key, individual.class_ids)
            ],
        )
        title = keys.preferred_label(individual.labels)
        ref = f"i{len(plan.operations) + 1}"
        resolved[key] = f"${ref}"
        planned[f"${ref}"] = individual.class_ids
        plan.operations.append(
            PlannedOperation(
                draft=OperationDraft(
                    seq=len(plan.operations) + 1,
                    op=OperationType.CREATE,
                    kind=OperationKind.INDIVIDUAL,
                    ref=ref,
                    fields={"title": title, "class_ids": individual.class_ids},
                    evidence=individual.evidence,
                    probability=best_probability(*individual.confidences),
                    alternatives=individual.alternatives,
                ),
                label=title,
            )
        )
    for short, long in folded.items():
        resolved[short] = resolved[long]

    relationships: dict[tuple[str, str, str], _Relationship] = {}
    fit = RelationshipFit(repo)
    for triple in triples:
        relationship = _relationship(triple, repo, resolved, keys, planned, fit, dataset_id, plan)
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


def _class_aliases(repo: OntologyRepository, taxonomy_id: str) -> dict[str, Class]:
    """
    Every identifying form of the taxonomy's classes (lowercased) -> the class.
    Derived classes are left out, so one sharing a title never shadows the
    class an individual can be created in.
    """
    aliases: dict[str, Class] = {}
    for scheme in repo.list_concept_schemes(taxonomy_id=taxonomy_id, limit=None):
        for cls in repo.list_classes(concept_scheme_id=scheme.id, limit=None):
            if cls.derived:
                continue  # computed by its client, never an extraction target
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
    added = []
    for match in near_matches if isinstance(near_matches, list) else []:
        entity_id = match.get("entity_id") if isinstance(match, dict) else None
        if _existing_individual(repo, entity_id, dataset_id) is None:
            continue
        similarity = best_probability(match.get("similarity"))
        added.append(
            _existing_alternative(
                entity_id, round(similarity, 4) if similarity is not None else None
            )
        )
    return _merged_alternatives(current, added)


def _existing_alternative(entity_id: str, similarity: float | None = None) -> dict[str, Any]:
    """An "existing" alternative; one matched by label has no similarity."""
    return {
        "kind": AlternativeKind.EXISTING.value,
        "entity_id": entity_id,
        "similarity": similarity,
    }


def _titled(
    repo: OntologyRepository, individual: _Individual, dataset_id: str | None
) -> str | None:
    """The existing individual of the mention's classes in the dataset titled with one of its
    labels (ignoring case), else None."""
    for label in dict.fromkeys(individual.labels):
        found = find_individual_by_label(repo, label, individual.class_ids, dataset_id)
        if found is not None:
            return found
    return None


def _merged_alternatives(*groups: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Alternatives of several groups: each individual once, with its best
    similarity, best first (those without a similarity last, in the order found).
    """
    best: dict[str, dict[str, Any]] = {}
    for group in groups:
        for alternative in group:
            known = best.get(alternative["entity_id"])
            if known is None or (alternative["similarity"] or 0.0) > (known["similarity"] or 0.0):
                best[alternative["entity_id"]] = alternative
    return sorted(best.values(), key=lambda a: a["similarity"] or 0.0, reverse=True)


def _fold_head_words(
    individuals: dict[str, _Individual], existing_ids: dict[str, str | None]
) -> dict[str, str]:
    """
    Fold each one-word mention into the multi-word mention it is the head word
    of ("bracket" into "Mounting Bracket"), when there is exactly one such
    mention, it was typed with every class of the one-word mention, and the
    one-word mention isn't an existing individual. The head word is the
    name's: a corporate suffix kept in the other mention's key is not a word
    ("enterprise" is the head word of "Wikimedia Enterprise LLC"). The folded
    mention's evidence, confidences and alternatives join the other's.

    Returns:
        Each folded mention's key -> the key it was folded into
    """
    folded: dict[str, str] = {}
    for short, individual in individuals.items():
        if len(short.split()) != 1 or existing_ids[short] is not None:
            continue
        heads = [
            key
            for key, other in individuals.items()
            if head_word(without_corporate_mark(key)) == short
            and set(individual.class_ids) <= set(other.class_ids)
        ]
        if len(heads) != 1:
            continue
        target = individuals[heads[0]]
        target.evidence = merged_evidence(target.evidence, individual.evidence)
        target.confidences += individual.confidences
        target.alternatives = _merged_alternatives(target.alternatives, individual.alternatives)
        folded[short] = heads[0]
    return folded


class _ExistingKeys:
    """
    The dataset's existing individuals of each class by their `LabelKeys` key
    among the class's titles, read once a class.
    """

    def __init__(self, repo: OntologyRepository, dataset_id: str | None) -> None:
        self._repo = repo
        self._dataset_id = dataset_id
        self._by_class: dict[str, list[tuple[str, str]]] = {}

    def matches(self, key: str, class_ids: list[str]) -> list[str]:
        """
        Ids of the existing individuals of the classes whose key is ``key``, then
        of those whose key is ``key`` without its first word when it has three
        or more (a leading brand or maker: "moen handheld shower" ->
        "handheld shower", but "hand shower" is not "shower"). A corporate
        suffix kept in ``key`` is left out: within a class it is only a variant.
        """
        key = without_corporate_mark(key)
        found: list[str] = []
        for wanted in (key, without_leading_word(key)):
            for class_id in class_ids:
                for existing_key, entity_id in self._of_class(class_id):
                    if wanted and existing_key == wanted and entity_id not in found:
                        found.append(entity_id)
        return found

    def _of_class(self, class_id: str) -> list[tuple[str, str]]:
        if class_id not in self._by_class:
            individuals = self._repo.list_individuals(
                class_id=class_id, limit=None, dataset_id=self._dataset_id
            )
            keys = LabelKeys(individual.title for individual in individuals)
            self._by_class[class_id] = [
                (keys.key(individual.title), individual.id) for individual in individuals
            ]
        return self._by_class[class_id]


def _relationship(
    triple: dict[str, Any],
    repo: OntologyRepository,
    resolved: dict[str, str],
    keys: LabelKeys,
    planned: dict[str, list[str]],
    fit: RelationshipFit,
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
    if is_typing_triple(triple):
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
    source = _end(subject, repo, resolved, keys, dataset_id)
    target = _end(obj, repo, resolved, keys, dataset_id)
    if source is None or target is None:
        plan.skip(label, "unresolved_endpoint")
        return None
    if source == target:
        plan.skip(label, "self_loop")
        return None
    source_classes, target_classes = (
        planned[end] if end in planned else fit.end_class_ids(end) or () for end in (source, target)
    )
    if fit.misfit(prop, source_classes, target_classes) is not None:
        plan.skip(label, "domain_range_mismatch")
        return None
    if not source.startswith("$") and not target.startswith("$"):
        if repo.list_relationships(
            source_id=source, target_id=target, property_id=prop.id, limit=1
        ):
            plan.skip(label, "exists")
            return None
    return _Relationship(source, target, prop.id, label)


def _end(
    node: dict[str, Any],
    repo: OntologyRepository,
    resolved: dict[str, str],
    keys: LabelKeys,
    dataset_id: str | None,
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
    return resolved.get(keys.key(str(node.get("label") or "")))


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
