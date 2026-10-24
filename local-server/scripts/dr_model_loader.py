"""
DR model -> Context Studio individuals transform.

Translates a Documentation Robotics (DR) *model* (instance data: the
`documentation-robotics/model/` directory of per-layer element YAML files and
`relationships.yaml`) into Individuals and Relationships under the `dr_spec`
taxonomy that `dr_ontology_loader.py` builds from the DR *spec*:

- one Individual per model element, typed to the `dr_spec` Class whose DR
  ExternalReference matches the element's `spec_node_id` (e.g.
  `motivation.stakeholder`);
- one Relationship per `relationships.yaml` entry, typed to the
  PropertyDefinition whose DR ExternalReference is
  `{source spec_node_id}.{predicate}.{target spec_node_id}`.

Element and relationship YAML parsing is reused from `dr_bootstrap_loader.py`.
Elements or relationships whose class, endpoints, or predicate do not resolve
against the imported ontology are skipped and reported, never fabricated.

Idempotent: each individual carries an ExternalReference
(source=`documentation_robotics`, identifier=<element path>), so a re-run
updates individuals in place. A relationship is identified by its
(source, target, property definition) triple, so a re-run leaves existing ones
untouched. All writes go through `OntologyService`.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from domain.ontology.entities import Class, Individual
from domain.ontology.exceptions import DuplicateEntityError
from domain.ontology.ports import OntologyRepository
from domain.ontology.services import OntologyService
from domain.ontology.value_objects import ExternalReference
from scripts.dr_bootstrap_loader import MODEL_SUBDIR, iter_elements, load_relationships
from scripts.dr_ontology_loader import (
    DR_SOURCE,
    DR_TAXONOMY_IDENTIFIER,
    slugify_spec_node_id,
)

_REQUIRED_ELEMENT_FIELDS = ("path", "spec_node_id", "layer_id", "name")
_REQUIRED_RELATIONSHIP_FIELDS = ("source", "target", "predicate")


@dataclass
class LayerCounts:
    """Per-layer outcome counts. Relationships are bucketed by their source layer."""

    individuals_created: int = 0
    individuals_updated: int = 0
    individuals_unchanged: int = 0
    individuals_skipped: int = 0
    relationships_created: int = 0
    relationships_unchanged: int = 0
    relationships_skipped: int = 0


@dataclass(frozen=True)
class SkippedRecord:
    """One model element or relationship that was not imported, and why."""

    layer: str
    kind: str  # "element" or "relationship"
    key: str
    reason: str


@dataclass
class ModelImportSummary:
    """Outcome of an `import_dr_model` run."""

    model_spec_version: str | None
    layers: dict[str, LayerCounts] = field(default_factory=lambda: defaultdict(LayerCounts))
    skipped: list[SkippedRecord] = field(default_factory=list)

    def skip(self, layer: str, kind: str, key: str, reason: str) -> None:
        """Record a skipped element/relationship and bump its layer's skip count."""
        self.skipped.append(SkippedRecord(layer=layer, kind=kind, key=key, reason=reason))
        counts = self.layers[layer]
        if kind == "element":
            counts.individuals_skipped += 1
        else:
            counts.relationships_skipped += 1


def read_model_spec_version(viewer_dir: Path) -> str | None:
    """The `spec_version` the model's manifest.yaml was written against, if present."""
    manifest_path = viewer_dir / MODEL_SUBDIR / "manifest.yaml"
    if not manifest_path.is_file():
        return None
    manifest = yaml.safe_load(manifest_path.read_text()) or {}
    return manifest.get("spec_version")


def _dr_identifiers(entity: Any) -> set[str]:
    return {ref.identifier for ref in entity.external_references if ref.source == DR_SOURCE}


def _resolve_class(
    repo: OntologyRepository, taxonomy_id: str, spec_node_id: str, cache: dict[str, Class | None]
) -> Class | None:
    """The dr_spec Class for `spec_node_id`, or None if the ontology has no such class."""
    if spec_node_id not in cache:
        candidate = repo.get_by_identifier(slugify_spec_node_id(spec_node_id))
        cache[spec_node_id] = (
            candidate
            if isinstance(candidate, Class)
            and candidate.taxonomy_id == taxonomy_id
            and spec_node_id in _dr_identifiers(candidate)
            else None
        )
    return cache[spec_node_id]


def _attach_path_reference(repo: OntologyRepository, individual: Individual, path: str) -> None:
    individual.external_references.append(ExternalReference(source=DR_SOURCE, identifier=path))
    repo.save_individual(individual)


def _upsert_individuals(
    service: OntologyService,
    repo: OntologyRepository,
    taxonomy_id: str,
    elements: list[dict[str, Any]],
    summary: ModelImportSummary,
) -> tuple[dict[str, str], dict[str, str]]:
    """
    Create or update one Individual per element.

    Returns (individual id by element path, spec_node_id by element path) for
    every element that was imported.
    """
    all_individuals = repo.list_individuals(class_id=None, limit=None)
    individual_by_path: dict[str, Individual] = {}
    for individual in all_individuals:
        for identifier in _dr_identifiers(individual):
            individual_by_path[identifier] = individual

    class_cache: dict[str, Class | None] = {}
    individual_id_by_path: dict[str, str] = {}
    spec_node_id_by_path: dict[str, str] = {}

    for element in elements:
        layer = element.get("layer_id") or "<unknown>"
        key = element.get("path") or element.get("id") or "<unknown>"
        missing = [name for name in _REQUIRED_ELEMENT_FIELDS if not element.get(name)]
        if missing:
            summary.skip(layer, "element", key, f"missing_field:{','.join(missing)}")
            continue

        path = element["path"]
        spec_node_id = element["spec_node_id"]
        title = element["name"]
        description = element.get("description")
        counts = summary.layers[layer]

        cls = _resolve_class(repo, taxonomy_id, spec_node_id, class_cache)
        if cls is None:
            summary.skip(layer, "element", path, f"unresolved_class:{spec_node_id}")
            continue

        existing = individual_by_path.get(path)
        adopted = False
        if existing is None:
            # Adopt an individual of this class with the same title that carries no
            # DR path yet (a hand-created one, or a run interrupted between create
            # and reference attach) instead of failing on the title-uniqueness rule.
            existing = next(
                (
                    individual
                    for individual in all_individuals
                    if cls.id in individual.class_ids
                    and individual.title == title
                    and not _dr_identifiers(individual)
                ),
                None,
            )
            adopted = existing is not None

        try:
            if existing is None:
                individual = service.create_individual(cls.id, title=title, description=description)
                _attach_path_reference(repo, individual, path)
                counts.individuals_created += 1
            else:
                changed = existing.title != title or (
                    description is not None and existing.description != description
                )
                individual = (
                    service.update_individual(existing.id, title=title, description=description)
                    if changed
                    else existing
                )
                if adopted:
                    _attach_path_reference(repo, individual, path)
                if changed or adopted:
                    counts.individuals_updated += 1
                else:
                    counts.individuals_unchanged += 1
        except DuplicateEntityError:
            summary.skip(layer, "element", path, f"duplicate_title_in_class:{title}")
            continue

        individual_by_path[path] = individual
        individual_id_by_path[path] = individual.id
        spec_node_id_by_path[path] = spec_node_id

    return individual_id_by_path, spec_node_id_by_path


def _upsert_relationships(
    service: OntologyService,
    repo: OntologyRepository,
    relationships: list[dict[str, Any]],
    individual_id_by_path: dict[str, str],
    spec_node_id_by_path: dict[str, str],
    layer_by_path: dict[str, str],
    summary: ModelImportSummary,
) -> None:
    property_id_by_dr_identifier: dict[str, str] = {}
    for prop in repo.list_property_definitions(limit=None):
        for identifier in _dr_identifiers(prop):
            property_id_by_dr_identifier[identifier] = prop.id

    for relationship in relationships:
        source = relationship.get("source")
        target = relationship.get("target")
        predicate = relationship.get("predicate")
        layer = layer_by_path.get(source or "") or relationship.get("layer") or "<unknown>"
        key = f"{source} {predicate} {target}"

        missing = [name for name in _REQUIRED_RELATIONSHIP_FIELDS if not relationship.get(name)]
        if missing:
            summary.skip(layer, "relationship", key, f"missing_field:{','.join(missing)}")
            continue
        if source == target:
            summary.skip(layer, "relationship", key, "self_loop")
            continue
        if source not in individual_id_by_path:
            summary.skip(layer, "relationship", key, f"unresolved_source:{source}")
            continue
        if target not in individual_id_by_path:
            summary.skip(layer, "relationship", key, f"unresolved_target:{target}")
            continue

        full_identifier = (
            f"{spec_node_id_by_path[source]}.{predicate}.{spec_node_id_by_path[target]}"
        )
        property_id = property_id_by_dr_identifier.get(full_identifier)
        if property_id is None:
            summary.skip(layer, "relationship", key, f"unresolved_predicate:{full_identifier}")
            continue

        source_id = individual_id_by_path[source]
        target_id = individual_id_by_path[target]
        counts = summary.layers[layer]
        if repo.list_relationships(
            source_id=source_id, target_id=target_id, property_id=property_id, limit=None
        ):
            counts.relationships_unchanged += 1
            continue
        service.create_relationship(source_id, target_id, property_id)
        counts.relationships_created += 1


def import_dr_model(
    ontology_service: OntologyService,
    ontology_repo: OntologyRepository,
    viewer_dir: Path,
) -> ModelImportSummary:
    """
    Idempotently import the DR model under `{viewer_dir}/documentation-robotics/model/`
    as individuals and relationships in the `dr_spec` taxonomy.

    Raises:
        ValueError: If the `dr_spec` taxonomy has not been imported yet.
    """
    taxonomy = ontology_repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    if taxonomy is None:
        raise ValueError(
            f"Taxonomy '{DR_TAXONOMY_IDENTIFIER}' not found — import the DR spec first "
            "(scripts/import_dr_ontology.py)"
        )

    summary = ModelImportSummary(model_spec_version=read_model_spec_version(viewer_dir))
    elements = iter_elements(viewer_dir)
    relationships = load_relationships(viewer_dir)
    layer_by_path = {
        element["path"]: element["layer_id"]
        for element in elements
        if element.get("path") and element.get("layer_id")
    }

    individual_id_by_path, spec_node_id_by_path = _upsert_individuals(
        ontology_service, ontology_repo, taxonomy.id, elements, summary
    )
    _upsert_relationships(
        ontology_service,
        ontology_repo,
        relationships,
        individual_id_by_path,
        spec_node_id_by_path,
        layer_by_path,
        summary,
    )
    return summary
