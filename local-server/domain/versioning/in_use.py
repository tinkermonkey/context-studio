"""
Relationship types still in use: what deleting one would break, and which
other types the relationships using it could move to.

A relationship fits a type when the type's domain accepts its source and its
range accepts its target, inheritance-aware: an end fits a class when one of
its classes (an individual's classes, or a class end itself) is that class or
a subclass of it. A type without a domain (or range) accepts any source (or
target). It must also allow the relationship's attributes, and not already
have a relationship between the same two ends.

A type whose domain and range are the deleted type's reversed (see
`compare_pair`) takes the relationships over with their ends swapped: each
moved relationship runs from the old target to the old source, and fitting is
checked that way round.

A relationship belongs to its source individual's dataset. Relationships of
a dataset that yields to the schema (`Dataset.yields_to_schema`, e.g. Context
Studio's own sample model in the DR taxonomy) never block: they follow the
schema change instead (see ProposalService.yield_plan). `blockers` counts the
others only; a relationship whose source is a class belongs to no dataset and
always blocks.

Only types that share a taxonomy with the deleted type (the taxonomies of
their domain and range classes) are offered as replacements, so a generic
untyped type from elsewhere isn't offered just because it accepts anything. A
deleted type with neither domain nor range has no taxonomy, and any type may
replace it.

A property delete may also name its replacement (`proposed_replacement_id`).
Its pair of classes is compared with the deleted type's: the same domain and
range, the two reversed, or a different pair. Only a same or reversed pair can
take over the deleted type's relationships as they are (a reversed one with
their ends swapped, as above; DR's `dr upgrade`
rewrites only those; see `pairOf` in DR's apply-reflect-plan.ts), so a
different pair is flagged for review. The comparison is exact, as DR's: a
subclass or superclass is a different class, and an untyped end (None) differs
from a typed one, so an untyped deleted type against a typed replacement is a
different pair. Whether the relationships still fit is the in-use check's job.

A replacement the same proposal also deletes is flagged too, following each
delete's own replacement to the end of the chain, or round a cycle (two deletes
naming each other: neither type survives).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Iterable

from domain.ontology.datasets import yielding_dataset_ids
from domain.ontology.entities import edge_attribute_values

if TYPE_CHECKING:
    from domain.ontology.entities import PropertyDefinition, Relationship
    from domain.ontology.ports import OntologyRepository


@dataclass(frozen=True)
class EdgeEnd:
    """
    One end of a relationship: the entity and the classes it is typed by, and
    its dataset (an individual's; None for a class end).
    """

    id: str
    title: str
    class_ids: tuple[str, ...]
    class_titles: tuple[str, ...]
    dataset_id: str | None = None


@dataclass(frozen=True)
class BlockingEdge:
    """A relationship that uses the type being deleted."""

    relationship_id: str
    source: EdgeEnd
    target: EdgeEnd
    attributes: dict[str, Any]

    @property
    def dataset_id(self) -> str | None:
        """The relationship's dataset: its source individual's (None for a class source)."""
        return self.source.dataset_id


@dataclass(frozen=True)
class ReplacementType:
    """A relationship type every blocking relationship fits."""

    property_id: str
    identifier: str
    title: str
    # Its domain and range are the deleted type's reversed: moving swaps each
    # relationship's source and target
    reversed: bool = False


@dataclass(frozen=True)
class DeleteBlockers:
    """
    What blocks deleting a relationship type.

    Attributes:
        edges: The relationships using it
        replacements: Types every one of them fits (empty when none does)
        move_unavailable_reason: Why no type fits, when replacements is empty
    """

    edges: tuple[BlockingEdge, ...]
    replacements: tuple[ReplacementType, ...]
    move_unavailable_reason: str | None = None


class PairMatch(str, Enum):
    """How a replacement's domain and range compare with the deleted type's."""

    SAME = "same"
    REVERSED = "reversed"
    DIFFERENT = "different"
    # The replacement no longer exists, or its create was rejected
    MISSING = "missing"


def compare_pair(
    deleted: tuple[str | None, str | None], replacement: tuple[str | None, str | None]
) -> PairMatch:
    """
    Compare two (domain class id, range class id) pairs exactly; None (untyped)
    is a value like any other. A pair whose two ends are the same class is the
    same pair, never reversed.
    """
    if replacement == deleted:
        return PairMatch.SAME
    if replacement == (deleted[1], deleted[0]):
        return PairMatch.REVERSED
    return PairMatch.DIFFERENT


@dataclass(frozen=True)
class ClassEnd:
    """A domain or range class, by id and title (None: untyped)."""

    id: str | None
    title: str | None


@dataclass(frozen=True)
class ChainLink:
    """
    One replacement in a chain of deletes: the type, and the delete of the
    same proposal that removes it (None for the type the chain ends at).
    """

    replacement_id: str
    identifier: str | None
    deleted_by_seq: int | None


@dataclass(frozen=True)
class ReplacementCheck:
    """
    A property delete's named replacement, compared with the deleted type.

    Attributes:
        replacement_id: The replacement as proposed: an id or "$<ref>"
        property_id: The replacement type, once it exists (None for a "$ref"
            whose create isn't applied yet, or a replacement since deleted)
        identifier, title: The replacement's (from its create while unapplied)
        pair: Same, reversed or different pair; missing if it is gone
        deleted_domain, deleted_range: The deleted type's classes when proposed
        domain, range: The replacement's classes (None when missing)
        chain: Empty unless the proposal also deletes the replacement; then
            each replacement in turn, following each delete's own replacement,
            to the type it ends at (the last link, not deleted) or until it
            comes back round
        cycle: Whether the chain comes back round to a type already in it
            (this delete's own included): every type in it is deleted
    """

    replacement_id: str
    property_id: str | None
    identifier: str | None
    title: str | None
    pair: PairMatch
    deleted_domain: ClassEnd
    deleted_range: ClassEnd
    domain: ClassEnd | None = None
    range: ClassEnd | None = None
    chain: tuple[ChainLink, ...] = ()
    cycle: bool = False

    @property
    def replacement_deleted(self) -> bool:
        """Whether the proposal also deletes the replacement."""
        return bool(self.chain)


class InUseInspector:
    """Reads the relationships using a type and checks other types against them."""

    def __init__(self, repo: OntologyRepository) -> None:
        self._repo = repo
        self._ancestors: dict[str, frozenset[str]] = {}
        self._ends: dict[str, EdgeEnd] = {}
        self._class_titles: dict[str, str] = {}
        self._types: list[PropertyDefinition] | None = None
        self._class_taxonomies: dict[str, str | None] = {}
        self._yielding: frozenset[str] | None = None

    def yielding(self) -> frozenset[str]:
        """The datasets that yield to the schema."""
        if self._yielding is None:
            self._yielding = yielding_dataset_ids(self._repo)
        return self._yielding

    def partition(
        self, edges: Iterable[BlockingEdge]
    ) -> tuple[list[BlockingEdge], list[BlockingEdge]]:
        """Split relationships into (blocking, yielding): the latter in yielding datasets."""
        yielding = self.yielding()
        blocking: list[BlockingEdge] = []
        follows: list[BlockingEdge] = []
        for edge in edges:
            (follows if edge.dataset_id in yielding else blocking).append(edge)
        return blocking, follows

    def edges(self, property_id: str) -> list[BlockingEdge]:
        """The relationships that use the type, oldest first."""
        relationships = self._repo.list_relationships(property_id=property_id, limit=None)
        return [self._edge(r) for r in relationships]

    def blockers(
        self,
        property_id: str,
        excluded: Iterable[str] = (),
        covered: Iterable[str] = (),
    ) -> DeleteBlockers | None:
        """
        What blocks deleting the type, or None when nothing (left) uses it.
        Relationships of datasets that yield to the schema never block.

        Args:
            property_id: The type being deleted
            excluded: Other types not to offer as replacements (ones the same
                proposal deletes, say)
            covered: Relationships something else already deletes (the same
                proposal's relationship deletes, say); they don't block
        """
        gone = set(covered)
        blocking, _ = self.partition(self.edges(property_id))
        edges = [e for e in blocking if e.relationship_id not in gone]
        if not edges:
            return None
        skip = {property_id, *excluded}
        if self._types is None:
            self._types = list(self._repo.list_property_definitions(limit=None))
        deleted = self._repo.get_property_definition(property_id)
        home = self._taxonomies_of(deleted) if deleted is not None else set()
        candidates = [
            p
            for p in self._types
            if p.id not in skip and (not home or self._taxonomies_of(p) & home)
        ]
        swaps = {p.id: reverses(deleted, p) for p in candidates}
        fitting = [p for p in candidates if not self.misfits(p, edges, swaps[p.id])]
        replacements = tuple(
            ReplacementType(
                property_id=p.id, identifier=p.identifier, title=p.title, reversed=swaps[p.id]
            )
            for p in sorted(fitting, key=lambda p: p.identifier)
        )
        reason = None if replacements else self._no_fit_reason(candidates, edges, swaps)
        return DeleteBlockers(tuple(edges), replacements, reason)

    def misfits(
        self, prop: PropertyDefinition, edges: Iterable[BlockingEdge], swap: bool = False
    ) -> list[str]:
        """
        Why each relationship that doesn't fit the type doesn't; empty when all fit.

        Args:
            swap: Check each relationship with its ends swapped, as a move to a
                reversed replacement re-creates it (see `reverses`)
        """
        problems: list[str] = []
        definitions = self._repo.list_attribute_definitions(
            property_definition_id=prop.id, limit=None
        )
        for edge in edges:
            source, target = moved_ends(edge, swap)
            label = f"{source.title} → {target.title}"
            if not self._accepts(prop.domain_class_id, source):
                problems.append(
                    f"{label}: source is {_classes(source)}, not "
                    f"{self._class_title(prop.domain_class_id)}"  # type: ignore[arg-type]
                )
                continue
            if not self._accepts(prop.range_class_id, target):
                problems.append(
                    f"{label}: target is {_classes(target)}, not "
                    f"{self._class_title(prop.range_class_id)}"  # type: ignore[arg-type]
                )
                continue
            try:
                edge_attribute_values(prop.identifier, definitions, dict(edge.attributes))
            except ValueError as exc:
                problems.append(f"{label}: {exc}")
                continue
            if self._repo.list_relationships(
                source_id=source.id, target_id=target.id, property_id=prop.id, limit=1
            ):
                problems.append(f"{label}: already related by {prop.identifier}")
        return problems

    # ------------------------------------------------------------------ helpers

    def _no_fit_reason(
        self,
        candidates: list[PropertyDefinition],
        edges: list[BlockingEdge],
        swaps: dict[str, bool],
    ) -> str:
        """Why no type fits: the sources, the targets, or something about the edges."""
        source_classes = _end_classes(e.source for e in edges)
        target_classes = _end_classes(e.target for e in edges)

        def accepts(p: PropertyDefinition, end: int) -> bool:
            class_id = p.domain_class_id if end == 0 else p.range_class_id
            return all(self._accepts(class_id, moved_ends(e, swaps[p.id])[end]) for e in edges)

        sources = [p for p in candidates if accepts(p, 0)]
        if not sources:
            return f"No other relationship type accepts {source_classes} sources"
        both = [p for p in sources if accepts(p, 1)]
        if not both:
            return (
                f"{_count(len(sources), 'type')} accept{'s' if len(sources) == 1 else ''} "
                f"{source_classes} sources ({_names(sources)}), but none accepts "
                f"{target_classes} targets"
            )
        first = sorted(both, key=lambda p: p.identifier)[0]
        return f"{_names(both)} fit both ends, but not every relationship: " + "; ".join(
            self.misfits(first, edges, swaps[first.id])
        )

    def _taxonomies_of(self, prop: PropertyDefinition) -> set[str]:
        """The taxonomies of a type's domain and range classes (empty when untyped)."""
        found: set[str] = set()
        for class_id in (prop.domain_class_id, prop.range_class_id):
            if class_id is None:
                continue
            if class_id not in self._class_taxonomies:
                cls = self._repo.get_class(class_id)
                self._class_taxonomies[class_id] = cls.taxonomy_id if cls is not None else None
            taxonomy_id = self._class_taxonomies[class_id]
            if taxonomy_id is not None:
                found.add(taxonomy_id)
        return found

    def _accepts(self, class_id: str | None, end: EdgeEnd) -> bool:
        if class_id is None:
            return True
        return any(class_id in self.ancestors_of(c) for c in end.class_ids)

    def ancestors_of(self, class_id: str) -> frozenset[str]:
        """The class and every class above it."""
        if class_id not in self._ancestors:
            seen: list[str] = []
            current: str | None = class_id
            while current is not None and current not in seen:
                seen.append(current)
                cls = self._repo.get_class(current)
                current = cls.parent_class_id if cls is not None else None
            self._ancestors[class_id] = frozenset(seen)
        return self._ancestors[class_id]

    def _class_title(self, class_id: str) -> str:
        if class_id not in self._class_titles:
            cls = self._repo.get_class(class_id)
            self._class_titles[class_id] = cls.title if cls is not None else class_id
        return self._class_titles[class_id]

    def edge(self, relationship: Relationship) -> BlockingEdge:
        """A relationship with its ends' classes and datasets."""
        return self._edge(relationship)

    def _edge(self, relationship: Relationship) -> BlockingEdge:
        return BlockingEdge(
            relationship_id=relationship.id,
            source=self._end(relationship.source_id),
            target=self._end(relationship.target_id),
            attributes=dict(relationship.attributes),
        )

    def _end(self, entity_id: str) -> EdgeEnd:
        if entity_id not in self._ends:
            individual = self._repo.get_individual(entity_id)
            dataset_id = None
            if individual is not None:
                title, class_ids = individual.title, tuple(individual.class_ids)
                dataset_id = individual.dataset_id
            else:
                cls = self._repo.get_class(entity_id)
                title = cls.title if cls is not None else entity_id
                class_ids = (entity_id,) if cls is not None else ()
            self._ends[entity_id] = EdgeEnd(
                id=entity_id,
                title=title,
                class_ids=class_ids,
                class_titles=tuple(self._class_title(c) for c in class_ids),
                dataset_id=dataset_id,
            )
        return self._ends[entity_id]


def reverses(deleted: PropertyDefinition | None, replacement: PropertyDefinition) -> bool:
    """
    Whether a move from the deleted type to the replacement swaps each
    relationship's ends: the replacement's domain and range are the deleted
    type's reversed (`compare_pair`, exact).
    """
    if deleted is None:
        return False
    pair = compare_pair(
        (deleted.domain_class_id, deleted.range_class_id),
        (replacement.domain_class_id, replacement.range_class_id),
    )
    return pair is PairMatch.REVERSED


def moved_ends(edge: BlockingEdge, swap: bool) -> tuple[EdgeEnd, EdgeEnd]:
    """The (source, target) a relationship moved to another type gets."""
    return (edge.target, edge.source) if swap else (edge.source, edge.target)


def _classes(end: EdgeEnd) -> str:
    return " / ".join(end.class_titles) or "untyped"


def _end_classes(ends: Iterable[EdgeEnd]) -> str:
    return ", ".join(sorted({_classes(end) for end in ends}))


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def _names(props: list[PropertyDefinition], shown: int = 3) -> str:
    names = sorted(p.identifier for p in props)
    more = f" and {len(names) - shown} more" if len(names) > shown else ""
    return ", ".join(names[:shown]) + more
