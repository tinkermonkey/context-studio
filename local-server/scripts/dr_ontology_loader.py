"""
DR spec -> Context Studio ontology transform.

Translates the Documentation Robotics (DR) spec's node/relationship JSON
schemas (`documentation_robotics/spec/schemas/{nodes,relationships}/`) into
Context Studio's ontology domain model: one Taxonomy for the spec as a whole,
one ConceptScheme per DR layer, one Class per node schema, and one
PropertyDefinition per relationship schema.

The spec's design charter (`spec/DESIGN_CHARTER.md`) becomes the taxonomy's
vision, and its "In one paragraph" section the taxonomy's summary
(description). Its predicate catalog (`spec/dist/base.json`) is kept on the
taxonomy's DR external reference, for reviewers' edits to check predicates
against (see `adapters.interchange.dr_relationships.dr_predicate_catalog`). Each layer file's description (`spec/layers/*.layer.json`)
becomes its scheme's scope note. Entities from an earlier import that the spec
no longer defines are reported as stale, never deleted.

This module is shared by the CLI import script (`import_dr_ontology.py`) and
by test fixtures that need the same DR-backed ontology built in-process, so
the DR-spec-transform logic is not duplicated between them.

Idempotent: entities are keyed on the preserved DR schema id (as the entity's
`identifier` and/or `ExternalReference`), so re-running against the same or an
updated spec version updates existing entities in place rather than
duplicating them.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Iterator
from uuid import uuid4

from adapters.interchange.dr_relationships import (  # noqa: F401 - re-exported for the scripts
    DR_SOURCE,
    DR_SPEC_REFERENCE,
    DR_TAXONOMY_IDENTIFIER,
    RelationshipSchemaRecord,
    assign_relationship_identifiers,
    compress_relationship_identifiers,
    dr_property_definitions,
)
from domain.interchange.bundle import stale_entities
from domain.ontology.entities import PropertyDefinition, Taxonomy
from domain.ontology.ports import OntologyRepository
from domain.ontology.services import OntologyService
from domain.ontology.value_objects import ExternalReference

DR_TAXONOMY_TITLE = "Documentation Robotics"

CHARTER_FILE = "DESIGN_CHARTER.md"
_SUMMARY_HEADING = "## In one paragraph"


@dataclass(frozen=True)
class NodeSchemaRecord:
    """One `schemas/nodes/**/*.node.schema.json` file."""

    spec_node_id: str
    layer_id: str
    title: str
    description: str | None


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
    charter_found: bool = False
    stale: list[str] = field(default_factory=list)


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


def read_predicate_catalog(spec_dir: Path) -> dict[str, dict[str, Any]] | None:
    """
    The spec's predicate catalog from spec/dist/base.json, by predicate id: each
    predicate's inverse, category and description. None when the spec has no
    dist/base.json (older specs).
    """
    path = spec_dir / "dist" / "base.json"
    if not path.is_file():
        return None
    predicates = _load_json(path).get("predicates")
    if not isinstance(predicates, dict) or not predicates:
        raise ValueError(f"{path} has no predicates object")
    try:
        return {
            predicate_id: {
                "inverse": entry.get("inverse"),
                "category": entry.get("category"),
                "description": entry.get("description"),
            }
            for predicate_id, entry in sorted(predicates.items())
        }
    except AttributeError as exc:
        raise ValueError(f"{path}: a predicate entry is not an object") from exc


def read_charter(spec_dir: Path) -> tuple[str | None, str | None]:
    """
    The spec's design charter as (vision, summary).

    The vision is the whole file; the summary is the text under "## In one
    paragraph", unwrapped into one line. Both are None when the spec has no
    charter (older spec versions); the summary is None if the file has no such
    section.
    """
    path = spec_dir / CHARTER_FILE
    if not path.is_file():
        return None, None
    vision = path.read_text()
    lines = vision.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == _SUMMARY_HEADING)
    except StopIteration:
        return vision, None
    body: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        if line.strip():
            body.append(line.strip())
    return vision, " ".join(body) or None


def read_layer_descriptions(spec_dir: Path) -> dict[str, str]:
    """Each layer's description from spec/layers/*.layer.json, by layer id."""
    descriptions: dict[str, str] = {}
    for path in sorted((spec_dir / "layers").glob("*.layer.json")):
        data = _load_json(path)
        if data.get("id") and data.get("description"):
            descriptions[data["id"]] = data["description"]
    return descriptions


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


def _upsert_taxonomy(
    service: OntologyService,
    repo: OntologyRepository,
    spec_dir: Path,
    spec_version: str,
    summary: ImportSummary,
) -> Taxonomy:
    """
    Create or update the DR taxonomy. With a charter, its summary and vision are
    written; without one (older specs), an existing summary and vision are left
    as they are.
    """
    vision, charter_summary = read_charter(spec_dir)
    summary.charter_found = vision is not None
    existing = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    if existing is None:
        taxonomy = service.create_taxonomy(
            title=DR_TAXONOMY_TITLE,
            description=charter_summary
            or f"Documentation Robotics architecture ontology (spec version {spec_version})",
            identifier=DR_TAXONOMY_IDENTIFIER,
            vision=vision,
        )
        summary.taxonomies_created += 1
    else:
        taxonomy = service.update_taxonomy(
            existing.id,
            title=DR_TAXONOMY_TITLE,
            description=charter_summary,
            vision=vision,
        )
        summary.taxonomies_updated += 1
    catalog = read_predicate_catalog(spec_dir)
    if catalog is not None:
        taxonomy = _store_predicate_catalog(repo, taxonomy, spec_version, catalog)
    return taxonomy  # type: ignore[return-value]


def _store_predicate_catalog(
    repo: OntologyRepository,
    taxonomy: Taxonomy,
    spec_version: str,
    catalog: dict[str, dict[str, Any]],
) -> Taxonomy:
    """
    Keep the predicate catalog on the taxonomy's DR reference (see
    `dr_predicate_catalog`), replacing the one an earlier import stored. A spec
    without a catalog leaves the stored one as it is.
    """
    reference = ExternalReference(
        source=DR_SOURCE,
        identifier=DR_SPEC_REFERENCE,
        metadata=MappingProxyType({"spec_version": spec_version, "predicates": catalog}),
    )
    others = [
        ref
        for ref in taxonomy.external_references
        if not (ref.source == DR_SOURCE and ref.identifier == DR_SPEC_REFERENCE)
    ]
    if [*others, reference] == taxonomy.external_references:
        return taxonomy
    taxonomy.external_references = [*others, reference]
    return repo.save_taxonomy(taxonomy)


def _upsert_concept_schemes(
    service: OntologyService,
    repo: OntologyRepository,
    taxonomy_id: str,
    layers: list[dict[str, Any]],
    layer_descriptions: dict[str, str],
    summary: ImportSummary,
) -> dict[str, str]:
    scheme_id_by_layer: dict[str, str] = {}
    for layer in layers:
        layer_id = layer["id"]
        identifier = layer_id.replace("-", "_")
        title = layer["name"]
        # The layer's own description is the scheme's scope note; older specs
        # without one get a generated line.
        description = layer_descriptions.get(layer_id) or (
            f"DR spec layer '{layer_id}': {layer['nodeTypeCount']} node types, "
            f"{layer['relationshipCount']} relationship types"
        )
        existing = repo.get_by_identifier(identifier)
        if existing is None:
            scheme = service.create_scheme(
                taxonomy_id=taxonomy_id,
                title=title,
                description=description,
                identifier=identifier,
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


def _existing_property_definitions(
    repo: OntologyRepository, records: list[RelationshipSchemaRecord]
) -> dict[str, PropertyDefinition]:
    """
    The property definition each relationship schema already has: the one whose
    DR reference names it (it follows renames applied in Context Studio), else
    one without any DR reference that holds its plain compressed identifier.
    """
    by_reference = dr_property_definitions(repo)
    plain = compress_relationship_identifiers(records)
    found: dict[str, PropertyDefinition] = {}
    for record in records:
        prop = by_reference.get(record.full_identifier)
        if prop is None:
            holder = repo.get_property_definition_by_identifier(plain[record.full_identifier])
            if holder is not None and not any(
                ref.source == DR_SOURCE for ref in holder.external_references
            ):
                prop = holder
        if prop is not None:
            found[record.full_identifier] = prop
    return found


def _endpoint_classes(
    record: RelationshipSchemaRecord, class_id_by_spec_node_id: dict[str, str]
) -> tuple[str, str]:
    """The (domain, range) class ids of a relationship schema."""
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
    return domain_class_id, range_class_id


def _upsert_property_definitions(
    service: OntologyService,
    repo: OntologyRepository,
    class_id_by_spec_node_id: dict[str, str],
    spec_dir: Path,
    summary: ImportSummary,
) -> set[str]:
    property_ids: set[str] = set()
    records = list(iter_relationship_schemas(spec_dir))
    # Every record must resolve before any write, so a bad spec changes nothing here.
    endpoints = {
        record.full_identifier: _endpoint_classes(record, class_id_by_spec_node_id)
        for record in records
    }
    existing_by_full_id = _existing_property_definitions(repo, records)
    identifier_by_full_id = assign_relationship_identifiers(
        records,
        repo,
        {full_id: prop.id for full_id, prop in existing_by_full_id.items()},
    )
    # Identifiers move in two steps, so properties trading identifiers in one
    # load (a rename into or out of a hash-collision group) never collide.
    moving = [
        (prop, identifier_by_full_id[full_id])
        for full_id, prop in existing_by_full_id.items()
        if prop.identifier != identifier_by_full_id[full_id]
    ]
    for prop, _ in moving:
        service.update_property_definition(prop.id, identifier=f"tmp_{uuid4().hex}")

    for record in records:
        identifier = identifier_by_full_id[record.full_identifier]
        title = f"{record.source_spec_node_id} {record.predicate} {record.destination_spec_node_id}"
        domain_class_id, range_class_id = endpoints[record.full_identifier]

        existing = existing_by_full_id.get(record.full_identifier)
        if existing is None:
            # New entity: safe to set the external reference directly at creation time,
            # there is nothing pre-existing that a wholesale write could discard.
            prop = service.create_property_definition(
                identifier=identifier,
                title=title,
                description=record.description,
                canonical_predicate=record.predicate,
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
                identifier=identifier,
                title=title,
                description=record.description,
                canonical_predicate=record.predicate,
                update_canonical_predicate=True,
                domain_class_id=domain_class_id,
                range_class_id=range_class_id,
                update_domain_class_id=True,
                update_range_class_id=True,
            )
            summary.property_definitions_updated += 1
            _sync_external_reference(repo.save_property_definition, prop, record.full_identifier)
        property_ids.add(prop.id)
    return property_ids


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

    taxonomy = _upsert_taxonomy(ontology_service, ontology_repo, spec_dir, spec_version, summary)
    scheme_id_by_layer = _upsert_concept_schemes(
        ontology_service,
        ontology_repo,
        taxonomy.id,
        layers,
        read_layer_descriptions(spec_dir),
        summary,
    )
    class_id_by_spec_node_id = _upsert_classes(
        ontology_service, ontology_repo, scheme_id_by_layer, spec_dir, summary
    )
    property_ids = _upsert_property_definitions(
        ontology_service, ontology_repo, class_id_by_spec_node_id, spec_dir, summary
    )

    # Spec entities from an earlier import that this spec version no longer defines.
    dr_classes = [
        cls
        for scheme in ontology_repo.list_concept_schemes(taxonomy_id=taxonomy.id, limit=None)
        for cls in ontology_repo.list_classes(concept_scheme_id=scheme.id, limit=None)
    ]
    summary.stale = stale_entities(
        [*dr_classes, *ontology_repo.list_property_definitions(limit=None)],
        DR_SOURCE,
        {*class_id_by_spec_node_id.values(), *property_ids},
    )
    return summary
