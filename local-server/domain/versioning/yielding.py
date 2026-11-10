"""
Data that yields to the schema.

A dataset flagged `yields_to_schema` (e.g. Context Studio's own sample model in
the DR taxonomy) never blocks a schema operation. Its data follows the change
instead, only inside that dataset:

- a relationship type's delete moves its relationships to the replacement the
  delete names, when that links the same pair of classes or the reverse (the
  reverse swapping their ends), and drops those that don't fit it; with no such
  replacement it drops them. A retarget (another pair of classes) drops them.
- a class delete takes the class off its individuals, and drops an individual
  whose only class it was.
- an attribute delete drops the attribute's values.

A plan says what will happen; review shows its counts per dataset and apply
carries it out through OntologyService, so every step is recorded under the
proposal's run and undone by its revert.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from domain.versioning.in_use import BlockingEdge, InUseInspector, moved_ends

if TYPE_CHECKING:
    from domain.ontology.entities import AttributeDefinition, Individual, PropertyDefinition
    from domain.ontology.ports import OntologyRepository


@dataclass(frozen=True)
class DatasetImpact:
    """What a schema operation does to one yielding dataset's data (counts)."""

    dataset_id: str
    identifier: str
    title: str
    relationships_moved: int = 0
    relationships_dropped: int = 0
    individuals_untyped: int = 0
    individuals_dropped: int = 0
    values_dropped: int = 0


@dataclass
class YieldPlan:
    """
    The changes a schema operation makes to yielding datasets' data.

    Attributes:
        moves: (relationship, replacement type id, swap ends) to re-create
        drops: Relationships deleted
        untyped: (individual, class id) to take off the individual
        dropped_individuals: Individuals deleted (the class was their only one)
        values: (individual, attribute identifier) whose values are deleted
    """

    moves: list[tuple[BlockingEdge, str, bool]] = field(default_factory=list)
    drops: list[BlockingEdge] = field(default_factory=list)
    untyped: list[tuple[Individual, str]] = field(default_factory=list)
    dropped_individuals: list[Individual] = field(default_factory=list)
    values: list[tuple[Individual, str]] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(
            self.moves or self.drops or self.untyped or self.dropped_individuals or self.values
        )

    def impacts(self, repo: OntologyRepository) -> list[DatasetImpact]:
        """The plan's counts per dataset, by dataset identifier."""
        counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for edge, _, _ in self.moves:
            counts[edge.dataset_id or ""]["relationships_moved"] += 1
        for edge in self.drops:
            counts[edge.dataset_id or ""]["relationships_dropped"] += 1
        for individual, _ in self.untyped:
            counts[individual.dataset_id or ""]["individuals_untyped"] += 1
        for individual in self.dropped_individuals:
            counts[individual.dataset_id or ""]["individuals_dropped"] += 1
        for individual, _ in self.values:
            counts[individual.dataset_id or ""]["values_dropped"] += 1
        impacts = []
        for dataset_id, numbers in counts.items():
            dataset = repo.get_dataset(dataset_id)
            impacts.append(
                DatasetImpact(
                    dataset_id=dataset_id,
                    identifier=dataset.identifier if dataset else dataset_id,
                    title=dataset.title if dataset else dataset_id,
                    **numbers,
                )
            )
        return sorted(impacts, key=lambda i: i.identifier)


def plan_type_delete(
    inspector: InUseInspector,
    edges: list[BlockingEdge],
    replacement: PropertyDefinition | None,
    swap: bool,
) -> YieldPlan:
    """
    Yielding relationships of a deleted type: each moves to the replacement when
    it fits (see InUseInspector.misfits), else is dropped.
    """
    plan = YieldPlan()
    for edge in edges:
        if replacement is not None and not inspector.misfits(replacement, [edge], swap):
            plan.moves.append((edge, replacement.id, swap))
        else:
            plan.drops.append(edge)
    return plan


def plan_class_delete(
    repo: OntologyRepository,
    inspector: InUseInspector,
    yielding: frozenset[str],
    class_id: str,
) -> YieldPlan:
    """
    Yielding individuals of a deleted class lose it, or go when it was their
    only class, with their relationships (all in their own dataset).
    """
    plan = YieldPlan()
    dropped_edges: dict[str, BlockingEdge] = {}
    for dataset_id in sorted(yielding):
        for individual in repo.list_individuals(
            class_id=class_id, limit=None, dataset_id=dataset_id
        ):
            if individual.class_ids != [class_id]:
                plan.untyped.append((individual, class_id))
                continue
            plan.dropped_individuals.append(individual)
            for relationship in repo.list_relationships(
                source_id=individual.id, limit=None
            ) + repo.list_relationships(target_id=individual.id, limit=None):
                dropped_edges[relationship.id] = inspector.edge(relationship)
    plan.drops.extend(dropped_edges.values())
    return plan


def plan_attribute_delete(
    repo: OntologyRepository,
    inspector: InUseInspector,
    yielding: frozenset[str],
    attribute: AttributeDefinition,
) -> YieldPlan:
    """Yielding individuals of the attribute's class (or a subclass) lose its values."""
    plan = YieldPlan()
    for dataset_id in sorted(yielding):
        for individual in repo.list_individuals(limit=None, dataset_id=dataset_id):
            has_value = any(
                v.property_identifier == attribute.identifier for v in individual.data_properties
            )
            in_class = any(
                attribute.class_id in inspector.ancestors_of(c) for c in individual.class_ids
            )
            if has_value and in_class:
                plan.values.append((individual, attribute.identifier))
    return plan


def apply_yield(ontology: Any, plan: YieldPlan, run_id: str) -> None:
    """
    Carry out a plan through OntologyService, inside the caller's transaction
    and run: relationships first, then classes, individuals and values.
    """
    for edge in plan.drops:
        ontology.delete_relationship(edge.relationship_id)
    for edge, replacement_id, swap in plan.moves:
        ontology.delete_relationship(edge.relationship_id)
        source, target = moved_ends(edge, swap)
        ontology.create_relationship(
            source.id,
            target.id,
            replacement_id,
            source_run_id=run_id,
            attributes=edge.attributes,
        )
    for individual, class_id in plan.untyped:
        ontology.remove_class_from_individual(individual.id, class_id)
    for individual in plan.dropped_individuals:
        ontology.delete_individual(individual.id)
    gone: dict[str, set[str]] = defaultdict(set)
    for individual, identifier in plan.values:
        gone[individual.id].add(identifier)
    for individual_id, identifiers in gone.items():
        current = ontology.get_individual(individual_id)
        ontology.update_individual(
            individual_id,
            data_properties=[
                v for v in current.data_properties if v.property_identifier not in identifiers
            ],
        )
