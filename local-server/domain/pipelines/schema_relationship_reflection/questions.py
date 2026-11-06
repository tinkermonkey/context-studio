"""
Sorting questions for one relationship type: "if not this, then what?"

A port of DR's `sortingQuestions()` (`cli/scripts/spec-enrich/triage-reflect.ts`)
to any taxonomy. For a relationship type `source predicate target` the decision
model is asked:

- source_for:    which class is the best source of `predicate target`?
- target_for:    what does `source predicate` best point to?
- predicate_for: which predicate best relates source to target?

Each offers the current answer, then the catalog's other answers, then the
current answer's siblings (the other classes of its scheme), capped at `top`,
plus 'none'. Predicates offered are the current one, the others the catalog
declares from source to target, then general predicates the taxonomy knows
(at least 12 in all), then those declared from target to source as
`reverse:<p>`.

Options are named by class label (identifier, else title) and predicate, as
the decision model reads them; `RelationshipCatalog` maps them back to ids.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from domain.decision.value_objects import NONE_OPTION, ChoiceQuestion
from domain.ontology.entities import Class, PropertyDefinition
from domain.ontology.ports import OntologyRepository

SOURCE_FOR = "source_for"
TARGET_FOR = "target_for"
PREDICATE_FOR = "predicate_for"
QUESTION_NAMES = (SOURCE_FOR, TARGET_FOR, PREDICATE_FOR)
REVERSE_PREFIX = "reverse:"
MIN_PREDICATE_OPTIONS = 12
EXTRA_REVERSE_OPTIONS = 3
DESCRIPTION_CLIP = 170


@dataclass(frozen=True)
class Triple:
    """A relationship type as the decision model reads it: class labels and predicate."""

    source: str
    predicate: str
    target: str

    def __str__(self) -> str:
        return f"{self.source} {self.predicate} {self.target}"


def class_label(cls: Class) -> str:
    """How a class is named in questions and plans."""
    return cls.identifier or cls.title


def predicate_of(prop: PropertyDefinition) -> str:
    """A relationship type's predicate: its canonical predicate, else its identifier."""
    return prop.canonical_predicate or prop.identifier


def first_sentence(text: str, limit: int = DESCRIPTION_CLIP) -> str:
    """The first sentence of `text` on one line, cut at a word to `limit` characters."""
    flat = " ".join(text.split())
    match = re.match(r"^(.+?[.!?])(\s|$)", flat)
    sentence = match.group(1) if match else flat
    if len(sentence) <= limit:
        return sentence
    return re.sub(r"\s\S*$", "", sentence[:limit]) + "..."


class RelationshipCatalog:
    """
    A taxonomy's classes and the relationship types between them.

    Relationship types count when both their domain and range are classes of
    the taxonomy. Predicate meanings come from a predicate catalog when one is
    given (it alone then says which predicates exist, as in DR); otherwise the
    predicates are those the taxonomy's relationship types use, each meaning
    the description of the first type using it.
    """

    def __init__(
        self,
        classes: Sequence[Class],
        relationship_types: Sequence[PropertyDefinition],
        predicate_catalog: Mapping[str, Mapping[str, object]] | None = None,
    ) -> None:
        self.classes: dict[str, Class] = {c.id: c for c in classes}
        self._by_label: dict[str, Class] = {}
        for cls in sorted(classes, key=lambda c: (class_label(c), c.id)):
            self._by_label.setdefault(class_label(cls), cls)
        self.relationship_types: list[PropertyDefinition] = sorted(
            (
                p
                for p in relationship_types
                if p.domain_class_id in self.classes and p.range_class_id in self.classes
            ),
            key=lambda p: (str(self.triple(p)), p.id),
        )
        self.by_triple: dict[Triple, PropertyDefinition] = {}
        for prop in self.relationship_types:
            self.by_triple.setdefault(self.triple(prop), prop)
        self.predicates: dict[str, str | None] = {}
        if predicate_catalog is not None:
            for name, entry in predicate_catalog.items():
                description = entry.get("description") if isinstance(entry, Mapping) else None
                self.predicates[name] = description if isinstance(description, str) else None
        else:
            for prop in self.relationship_types:
                self.predicates.setdefault(predicate_of(prop), prop.description)

    @classmethod
    def for_taxonomy(
        cls,
        repo: OntologyRepository,
        taxonomy_id: str,
        predicate_catalog: Mapping[str, Mapping[str, object]] | None = None,
    ) -> "RelationshipCatalog":
        """The catalog of one taxonomy, read from the repository."""
        classes = [
            c
            for scheme in repo.list_concept_schemes(taxonomy_id=taxonomy_id, limit=None)
            for c in repo.list_classes(concept_scheme_id=scheme.id, limit=None)
        ]
        return cls(classes, repo.list_property_definitions(limit=None), predicate_catalog)

    def label(self, class_id: str) -> str:
        return class_label(self.classes[class_id])

    def class_id(self, label: str) -> str | None:
        """The class a label names (None for 'none' or an unknown label)."""
        found = self._by_label.get(label)
        return found.id if found else None

    def triple(self, prop: PropertyDefinition) -> Triple:
        return Triple(
            self.label(prop.domain_class_id or ""),
            predicate_of(prop),
            self.label(prop.range_class_id or ""),
        )

    def siblings(self, label: str) -> list[str]:
        """The other classes of the class's scheme, by label."""
        cls = self._by_label[label]
        return sorted(
            class_label(c)
            for c in self.classes.values()
            if c.concept_scheme_id == cls.concept_scheme_id and c.id != cls.id
        )

    def describe(self, label: str) -> str:
        cls = self._by_label.get(label)
        return first_sentence(cls.description or label) if cls else label


@dataclass(frozen=True)
class SortingQuestions:
    """The three questions for one relationship type and the options each offers."""

    triple: Triple
    questions: dict[str, ChoiceQuestion]
    candidates: dict[str, list[str]]


def sorting_questions(
    prop: PropertyDefinition,
    catalog: RelationshipCatalog,
    top: int = 8,
    general_predicates: Sequence[str] = (),
) -> SortingQuestions:
    """
    Build the three sorting questions for one relationship type.

    Args:
        prop: The relationship type (its domain and range must be catalog classes)
        catalog: The taxonomy's classes and relationship types
        top: At most this many classes per question (before 'none')
        general_predicates: Predicates to offer after the catalog's own, when
            the taxonomy knows them
    """
    t = catalog.triple(prop)
    triples = list(catalog.by_triple)

    def pick(first: str, others: list[str], pool: list[str]) -> list[str]:
        out: list[str] = []
        for label in [first, *others, *pool]:
            if catalog.class_id(label) and label not in out and len(out) < top:
                out.append(label)
        return out

    sources = pick(
        t.source,
        sorted(x.source for x in triples if x.predicate == t.predicate and x.target == t.target),
        catalog.siblings(t.source),
    )
    targets = pick(
        t.target,
        sorted(x.target for x in triples if x.predicate == t.predicate and x.source == t.source),
        catalog.siblings(t.target),
    )
    forward = list(
        dict.fromkeys(x.predicate for x in triples if x.source == t.source and x.target == t.target)
    )
    reverse = list(
        dict.fromkeys(x.predicate for x in triples if x.source == t.target and x.target == t.source)
    )
    meanings = catalog.predicates
    predicate_top = max(top, MIN_PREDICATE_OPTIONS)
    predicate_criteria: dict[str, str] = {}
    for p in [t.predicate, *forward, *general_predicates]:
        if len(predicate_criteria) >= predicate_top:
            break
        if p in meanings and p not in predicate_criteria:
            predicate_criteria[p] = f"{t.source} {p} {t.target}: {meanings[p] or p}"
    for p in reverse:
        if len(predicate_criteria) >= predicate_top + EXTRA_REVERSE_OPTIONS:
            break
        key = f"{REVERSE_PREFIX}{p}"
        if p in meanings and key not in predicate_criteria:
            predicate_criteria[key] = (
                f"the other way round, {t.target} {p} {t.source}: {meanings[p] or p}"
            )
    predicate_criteria[NONE_OPTION] = (
        f"no predicate fits; {t.source} and {t.target} should not be directly related"
    )

    def class_criteria(labels: list[str], none_text: str) -> dict[str, str]:
        return {**{label: catalog.describe(label) for label in labels}, NONE_OPTION: none_text}

    predicate_text = meanings.get(t.predicate) or t.predicate
    return SortingQuestions(
        triple=t,
        candidates={
            SOURCE_FOR: sources,
            TARGET_FOR: targets,
            PREDICATE_FOR: list(predicate_criteria),
        },
        questions={
            SOURCE_FOR: ChoiceQuestion(
                instructions=(
                    f"Sorting question. The catalog says '{t}' ({t.predicate}: {predicate_text})."
                    f" If {t.source} is not the right source, what is? Which listed element type"
                    f" is the best SOURCE of '{t.predicate} {t.target}', judged by the"
                    " predicate's meaning and the design intent? Choose 'none' if no listed type"
                    f" should {t.predicate} {t.target}."
                ),
                criteria=class_criteria(sources, f"no listed type should {t.predicate} {t.target}"),
            ),
            TARGET_FOR: ChoiceQuestion(
                instructions=(
                    f"Sorting question. If {t.target} is not the right destination, what is?"
                    " Which listed element type is the best DESTINATION of"
                    f" '{t.source} {t.predicate}'? Choose 'none' if {t.source} should not"
                    f" {t.predicate} any listed type."
                ),
                criteria=class_criteria(
                    targets, f"{t.source} should not {t.predicate} any listed type"
                ),
            ),
            PREDICATE_FOR: ChoiceQuestion(
                instructions=(
                    f"Sorting question. Which predicate best describes how {t.source} relates"
                    f" to {t.target}? Options prefixed 'reverse:' mean the relationship should"
                    f" run from {t.target} to {t.source} instead."
                ),
                criteria=predicate_criteria,
            ),
        },
    )
