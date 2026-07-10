"""
DR spec -> Context Studio ontology transform.

Translates the Documentation Robotics (DR) spec's node/relationship JSON
schemas (`documentation_robotics/spec/schemas/{nodes,relationships}/`) into
Context Studio's ontology domain model: one Taxonomy for the spec as a whole,
one ConceptScheme per DR layer, one Class per node schema, and one
PropertyDefinition per relationship schema.

This module is shared by the CLI import script (`import_dr_ontology.py`) and
by test fixtures that need the same DR-backed ontology built in-process, so
the DR-spec-transform logic is not duplicated between them.

Idempotent: entities are keyed on the preserved DR schema id (as the entity's
`identifier` and/or `ExternalReference`), so re-running against the same or an
updated spec version updates existing entities in place rather than
duplicating them.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

from domain.ontology.entities import Taxonomy
from domain.ontology.ports import OntologyRepository
from domain.ontology.services import OntologyService
from domain.ontology.value_objects import ExternalReference

DR_SOURCE = "documentation_robotics"
DR_TAXONOMY_IDENTIFIER = "dr_spec"
DR_TAXONOMY_TITLE = "Documentation Robotics"

_IDENTIFIER_MAX_LENGTH = 64
_TRUNCATED_LENGTH = 59


@dataclass(frozen=True)
class NodeSchemaRecord:
    """One `schemas/nodes/**/*.node.schema.json` file."""

    spec_node_id: str
    layer_id: str
    title: str
    description: str | None


@dataclass(frozen=True)
class RelationshipSchemaRecord:
    """One `schemas/relationships/**/*.relationship.schema.json` file."""

    source_spec_node_id: str
    source_layer: str
    destination_spec_node_id: str
    destination_layer: str
    predicate: str
    title: str
    description: str | None

    @property
    def full_identifier(self) -> str:
        """Long-form, always-fully-qualified id: {source}.{predicate}.{destination}."""
        return f"{self.source_spec_node_id}.{self.predicate}.{self.destination_spec_node_id}"


@dataclass
class ImportSummary:
    """Row counts produced by an `import_dr_ontology` run."""

    spec_version: str
    taxonomies_created: int = 0
    taxonomies_updated: int = 0
    concept_schemes_created: int = 0
    concept_schemes_updated: int = 0
    classes_created: int = 0
    classes_updated: int = 0
    property_definitions_created: int = 0
    property_definitions_updated: int = 0


def _load_json(path: Path) -> Any:
    """Read and parse a JSON file, raising ValueError with the file path on malformed JSON."""
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed JSON in {path}: {exc}") from exc


def read_manifest(spec_dir: Path) -> tuple[str, list[dict[str, Any]]]:
    """Read spec_version and per-layer metadata from spec/dist/manifest.json."""
    manifest_path = spec_dir / "dist" / "manifest.json"
    manifest = _load_json(manifest_path)
    try:
        return manifest["specVersion"], manifest["layers"]
    except KeyError as exc:
        raise ValueError(f"Manifest {manifest_path} is missing required key {exc}") from exc


def iter_node_schemas(spec_dir: Path) -> Iterator[NodeSchemaRecord]:
    """Yield one record per node schema in schemas/nodes/ (base schemas excluded)."""
    nodes_dir = spec_dir / "schemas" / "nodes"
    if not nodes_dir.is_dir():
        raise FileNotFoundError(
            f"DR node schema directory not found: {nodes_dir} — check --spec-dir points at a "
            "documentation_robotics spec checkout with a schemas/nodes/ directory"
        )
    for path in sorted(nodes_dir.glob("*/*.node.schema.json")):
        data = _load_json(path)
        try:
            props = data["properties"]
            yield NodeSchemaRecord(
                spec_node_id=props["spec_node_id"]["const"],
                layer_id=props["layer_id"]["const"],
                title=data["title"],
                description=data.get("description"),
            )
        except KeyError as exc:
            raise ValueError(f"Node schema {path} is missing required key {exc}") from exc


def iter_relationship_schemas(spec_dir: Path) -> Iterator[RelationshipSchemaRecord]:
    """Yield one record per relationship schema in schemas/relationships/ (base excluded)."""
    relationships_dir = spec_dir / "schemas" / "relationships"
    if not relationships_dir.is_dir():
        raise FileNotFoundError(
            f"DR relationship schema directory not found: {relationships_dir} — check "
            "--spec-dir points at a documentation_robotics spec checkout with a "
            "schemas/relationships/ directory"
        )
    for path in sorted(relationships_dir.glob("*/*.relationship.schema.json")):
        data = _load_json(path)
        try:
            props = data["properties"]
            yield RelationshipSchemaRecord(
                source_spec_node_id=props["source_spec_node_id"]["const"],
                source_layer=props["source_layer"]["const"],
                destination_spec_node_id=props["destination_spec_node_id"]["const"],
                destination_layer=props["destination_layer"]["const"],
                predicate=props["predicate"]["const"],
                title=data["title"],
                description=data.get("description"),
            )
        except KeyError as exc:
            raise ValueError(f"Relationship schema {path} is missing required key {exc}") from exc


def slugify_spec_node_id(spec_node_id: str) -> str:
    """'motivation.goal' -> 'motivation_goal' (Class identifier slug)."""
    return spec_node_id.replace(".", "_").replace("-", "_")


def _stripped_relationship_identifier(record: RelationshipSchemaRecord) -> str:
    """
    Layer-qualified type names already encode their layer for compound names
    (e.g. 'applicationcollaboration'), so the leading '{layer}.' segment of
    each side is redundant and can be dropped.
    """
    source_type = record.source_spec_node_id.split(".", 1)[1]
    destination_type = record.destination_spec_node_id.split(".", 1)[1]
    predicate = record.predicate.replace("-", "_")
    return f"{source_type}_{predicate}_{destination_type}"


def _hashed_relationship_identifier(record: RelationshipSchemaRecord) -> str:
    """Deterministic fallback: 59-char truncation + 4-hex-char SHA-256 suffix."""
    stripped = _stripped_relationship_identifier(record)
    digest = hashlib.sha256(record.full_identifier.encode("utf-8")).hexdigest()[:4]
    return f"{stripped[:_TRUNCATED_LENGTH]}_{digest}"


def compress_relationship_identifiers(
    records: Iterable[RelationshipSchemaRecord],
) -> dict[str, str]:
    """
    Map each relationship record's full long-form id to a compressed identifier
    that is <=64 chars and globally unique across all records.

    Two independent reasons a compressed id needs the hash-suffix fallback:
    - the layer-stripped form alone exceeds 64 chars, or
    - two distinct relationships (different source/destination layers) strip
      down to the identical short form (e.g. 'ux.view' and 'data-store.view'
      both stripping to 'view').

    Raises:
        ValueError: If compression cannot produce a fully unique, <=64-char
            identifier set (should not happen for the current DR spec; this
            is the "verify zero collisions" guard from the design).
    """
    records = list(records)
    compressed: dict[str, str] = {}
    for record in records:
        stripped = _stripped_relationship_identifier(record)
        compressed[record.full_identifier] = (
            stripped
            if len(stripped) <= _IDENTIFIER_MAX_LENGTH
            else _hashed_relationship_identifier(record)
        )

    # Resolve identifiers that collided even though each individually fit in 64 chars.
    by_compressed: dict[str, list[str]] = defaultdict(list)
    for full_id, compressed_id in compressed.items():
        by_compressed[compressed_id].append(full_id)

    by_full_id = {record.full_identifier: record for record in records}
    for compressed_id, full_ids in by_compressed.items():
        if len(full_ids) > 1:
            for full_id in full_ids:
                compressed[full_id] = _hashed_relationship_identifier(by_full_id[full_id])

    final_ids = list(compressed.values())
    if len(final_ids) != len(set(final_ids)):
        raise ValueError("Relationship identifier compression produced duplicate identifiers")
    too_long = [identifier for identifier in final_ids if len(identifier) > _IDENTIFIER_MAX_LENGTH]
    if too_long:
        raise ValueError(
            f"Relationship identifiers exceed {_IDENTIFIER_MAX_LENGTH} chars: {too_long}"
        )

    return compressed


def _upsert_taxonomy(
    service: OntologyService,
    repo: OntologyRepository,
    spec_version: str,
    summary: ImportSummary,
) -> Taxonomy:
    description = (
        f"Documentation Robotics 12-layer architecture ontology (spec version {spec_version})"
    )
    existing = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    if existing is None:
        taxonomy = service.create_taxonomy(
            title=DR_TAXONOMY_TITLE,
            description=description,
            identifier=DR_TAXONOMY_IDENTIFIER,
        )
        summary.taxonomies_created += 1
    else:
        taxonomy = service.update_taxonomy(
            existing.id, title=DR_TAXONOMY_TITLE, description=description
        )
        summary.taxonomies_updated += 1
    return taxonomy  # type: ignore[return-value]


def _upsert_concept_schemes(
    service: OntologyService,
    repo: OntologyRepository,
    taxonomy_id: str,
    layers: list[dict[str, Any]],
    summary: ImportSummary,
) -> dict[str, str]:
    scheme_id_by_layer: dict[str, str] = {}
    for layer in layers:
        layer_id = layer["id"]
        identifier = layer_id.replace("-", "_")
        title = layer["name"]
        description = (
            f"DR spec layer '{layer_id}': {layer['nodeTypeCount']} node types, "
            f"{layer['relationshipCount']} relationship types"
        )
        existing = repo.get_by_identifier(identifier)
        if existing is None:
            scheme = service.create_scheme(
                taxonomy_id=taxonomy_id, title=title, description=description, identifier=identifier
            )
            summary.concept_schemes_created += 1
        else:
            scheme = service.update_concept_scheme(
                existing.id, title=title, description=description
            )
            summary.concept_schemes_updated += 1
        scheme_id_by_layer[layer_id] = scheme.id  # type: ignore[union-attr]
    return scheme_id_by_layer


def _sync_external_reference(save_fn: Callable[[Any], Any], entity: Any, identifier: str) -> None:
    """Attach a DR-spec ExternalReference to `entity` if not already present (idempotent)."""
    already_present = any(
        ref.source == DR_SOURCE and ref.identifier == identifier
        for ref in entity.external_references
    )
    if already_present:
        return
    entity.external_references.append(ExternalReference(source=DR_SOURCE, identifier=identifier))
    save_fn(entity)


def _upsert_classes(
    service: OntologyService,
    repo: OntologyRepository,
    scheme_id_by_layer: dict[str, str],
    spec_dir: Path,
    summary: ImportSummary,
) -> dict[str, str]:
    nodes = list(iter_node_schemas(spec_dir))

    slug_by_spec_node_id = {
        node.spec_node_id: slugify_spec_node_id(node.spec_node_id) for node in nodes
    }
    collisions = {
        slug: count for slug, count in Counter(slug_by_spec_node_id.values()).items() if count > 1
    }
    if collisions:
        raise ValueError(f"DR node schema identifiers collide after slugification: {collisions}")

    class_id_by_spec_node_id: dict[str, str] = {}
    for node in nodes:
        identifier = slug_by_spec_node_id[node.spec_node_id]
        if node.layer_id not in scheme_id_by_layer:
            raise ValueError(
                f"Node schema '{node.spec_node_id}' references layer '{node.layer_id}', which "
                "has no matching entry in spec/dist/manifest.json"
            )
        scheme_id = scheme_id_by_layer[node.layer_id]
        existing = repo.get_by_identifier(identifier)
        if existing is None:
            cls = service.create_class(
                concept_scheme_id=scheme_id,
                title=node.title,
                description=node.description,
                identifier=identifier,
            )
            summary.classes_created += 1
        else:
            cls = service.update_class(existing.id, title=node.title, description=node.description)
            summary.classes_updated += 1
        _sync_external_reference(repo.save_class, cls, node.spec_node_id)
        class_id_by_spec_node_id[node.spec_node_id] = cls.id  # type: ignore[union-attr]
    return class_id_by_spec_node_id


def _upsert_property_definitions(
    service: OntologyService,
    repo: OntologyRepository,
    class_id_by_spec_node_id: dict[str, str],
    spec_dir: Path,
    summary: ImportSummary,
) -> None:
    records = list(iter_relationship_schemas(spec_dir))
    compressed_by_full_id = compress_relationship_identifiers(records)

    for record in records:
        identifier = compressed_by_full_id[record.full_identifier]
        title = f"{record.source_spec_node_id} {record.predicate} {record.destination_spec_node_id}"

        domain_class_id = class_id_by_spec_node_id.get(record.source_spec_node_id)
        if domain_class_id is None:
            raise ValueError(
                f"Relationship '{record.full_identifier}' references source node type "
                f"'{record.source_spec_node_id}', which has no matching node schema"
            )
        range_class_id = class_id_by_spec_node_id.get(record.destination_spec_node_id)
        if range_class_id is None:
            raise ValueError(
                f"Relationship '{record.full_identifier}' references destination node type "
                f"'{record.destination_spec_node_id}', which has no matching node schema"
            )

        existing = repo.get_property_definition_by_identifier(identifier)
        if existing is None:
            # New entity: safe to set the external reference directly at creation time,
            # there is nothing pre-existing that a wholesale write could discard.
            service.create_property_definition(
                identifier=identifier,
                title=title,
                description=record.description,
                domain_class_id=domain_class_id,
                range_class_id=range_class_id,
                external_references=[
                    ExternalReference(source=DR_SOURCE, identifier=record.full_identifier)
                ],
            )
            summary.property_definitions_created += 1
        else:
            # Existing entity: update everything except external_references here, then
            # append-if-missing below — a wholesale external_references= replace on update
            # would silently discard any non-DR reference some other source had attached.
            prop = service.update_property_definition(
                existing.id,
                title=title,
                description=record.description,
                domain_class_id=domain_class_id,
                range_class_id=range_class_id,
                update_domain_class_id=True,
                update_range_class_id=True,
            )
            summary.property_definitions_updated += 1
            _sync_external_reference(repo.save_property_definition, prop, record.full_identifier)


def import_dr_ontology(
    ontology_service: OntologyService,
    ontology_repo: OntologyRepository,
    spec_dir: Path,
) -> ImportSummary:
    """
    Idempotently import the DR spec at `spec_dir` into the ontology backing
    `ontology_service`/`ontology_repo`.

    `ontology_service` should be wired with `schema_index=None` by the caller
    to suppress per-entity embedding sync; the caller is responsible for
    calling `SchemaVectorIndex.reindex_all()` exactly once after this returns.
    """
    spec_version, layers = read_manifest(spec_dir)
    summary = ImportSummary(spec_version=spec_version)

    taxonomy = _upsert_taxonomy(ontology_service, ontology_repo, spec_version, summary)
    scheme_id_by_layer = _upsert_concept_schemes(
        ontology_service, ontology_repo, taxonomy.id, layers, summary
    )
    class_id_by_spec_node_id = _upsert_classes(
        ontology_service, ontology_repo, scheme_id_by_layer, spec_dir, summary
    )
    _upsert_property_definitions(
        ontology_service, ontology_repo, class_id_by_spec_node_id, spec_dir, summary
    )

    return summary
