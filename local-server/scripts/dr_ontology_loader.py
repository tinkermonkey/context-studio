"""
DR spec -> Context Studio ontology transform.

Translates the Documentation Robotics (DR) spec's node/relationship JSON
schemas (`documentation_robotics/spec/schemas/{nodes,relationships}/`) into
Context Studio's ontology domain model: one Taxonomy for the spec as a whole,
one ConceptScheme per DR layer, one Class per node schema, and one
PropertyDefinition per relationship schema. A relationship schema's
cardinality, strength and x-dr-evidence ride on its property definition's DR
reference as metadata (`{"cardinality", "strength", "evidence"}`; see
`DR_ATTRIBUTE_KEYS`), so a change proposal can change them and
`scripts/export_dr_spec_changes.py` can hand them back to DR.

The spec's design charter (`spec/DESIGN_CHARTER.md`) becomes the taxonomy's
vision, and its "In one paragraph" section the taxonomy's summary
(description). Its predicate catalog (`spec/dist/base.json`) is kept on the
taxonomy's DR external reference, for reviewers' edits to check predicates
against (see `adapters.interchange.dr_relationships.dr_predicate_catalog`).
Each layer file's description (`spec/layers/*.layer.json`) becomes its
scheme's scope note. Entities from an earlier import that the spec
no longer defines are reported as stale; they are deleted only on request
(`find_prune_blockers` / `prune_stale`), and only when nothing uses them.

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
import subprocess
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
from domain.ontology.entities import Class, PropertyDefinition, Taxonomy
from domain.ontology.exceptions import OntologyError
from domain.ontology.ports import OntologyRepository
from domain.ontology.services import OntologyService
from domain.ontology.value_objects import ExternalReference, SourceRevision
from domain.versioning.ports import ChangeProposalRepository
from domain.versioning.proposals import OperationStatus, ProposalStatus

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
    source_revision: SourceRevision | None = None
    stale: list[str] = field(default_factory=list)
    # The stale classes and property definitions themselves, for pruning.
    stale_entities: list[Class | PropertyDefinition] = field(default_factory=list)


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


def read_source_revision(spec_dir: Path, spec_version: str) -> SourceRevision:
    """
    The spec's revision: its repository's origin URL and HEAD commit (each None
    when git can't tell, e.g. a spec outside a git checkout) and its version.
    """
    return SourceRevision(
        repo=_git(spec_dir, "remote", "get-url", "origin"),
        commit=_git(spec_dir, "rev-parse", "HEAD"),
        spec_version=spec_version,
    )


def _git(directory: Path, *args: str) -> str | None:
    """A git command's output in `directory`, or None if it fails."""
    try:
        result = subprocess.run(
            ["git", "-C", str(directory), *args], capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


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
            evidence = data.get("x-dr-evidence") or []
            if not isinstance(evidence, list) or not all(isinstance(e, str) for e in evidence):
                raise ValueError(f"Relationship schema {path}: x-dr-evidence is not a string list")
            yield RelationshipSchemaRecord(
                source_spec_node_id=props["source_spec_node_id"]["const"],
                source_layer=props["source_layer"]["const"],
                destination_spec_node_id=props["destination_spec_node_id"]["const"],
                destination_layer=props["destination_layer"]["const"],
                predicate=props["predicate"]["const"],
                title=data["title"],
                description=data.get("description"),
                cardinality=(props.get("cardinality") or {}).get("const"),
                strength=(props.get("strength") or {}).get("const"),
                evidence=tuple(evidence),
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


def _attributes_reference(identifier: str, attributes: dict[str, Any]) -> ExternalReference:
    """A relationship type's DR reference, its spec attributes as metadata (None if none)."""
    return ExternalReference(
        source=DR_SOURCE,
        identifier=identifier,
        metadata=MappingProxyType(attributes) if attributes else None,
    )


def _sync_relationship_reference(
    repo: OntologyRepository, prop: PropertyDefinition, record: RelationshipSchemaRecord
) -> None:
    """
    Give a property definition its DR reference, with the schema's attributes
    as metadata: added if missing, its metadata replaced if it differs (a
    re-import of an unchanged spec saves nothing). Other references stay.
    """
    identifier = record.full_identifier
    attributes = record.attributes
    refs = list(prop.external_references)
    index = next(
        (
            i
            for i, ref in enumerate(refs)
            if ref.source == DR_SOURCE and ref.identifier == identifier
        ),
        None,
    )
    if index is None:
        refs.append(_attributes_reference(identifier, attributes))
    elif dict(refs[index].metadata or {}) == attributes:
        return
    else:
        current = refs[index]
        refs[index] = ExternalReference(
            source=DR_SOURCE,
            identifier=identifier,
            uri=current.uri,
            metadata=MappingProxyType(attributes) if attributes else None,
        )
    prop.external_references = refs
    repo.save_property_definition(prop)


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


def _refuse_moved_node_types(
    repo: OntologyRepository, nodes: list[NodeSchemaRecord], slug_by_spec_node_id: dict[str, str]
) -> None:
    """
    Refuse a spec in which a node type moved to another layer (a class move
    exported to DR and landed there): its new id is a new node schema whose type
    matches a DR class whose node schema is gone. The import would duplicate it,
    as classes are keyed by an identifier that holds the layer, so it stops
    before writing any class or relationship type until re-import can follow
    a move.
    """
    taxonomy = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    if taxonomy is None:
        return
    spec_ids = {node.spec_node_id for node in nodes}
    gone_by_type: dict[str, list[str]] = {}
    for scheme in repo.list_concept_schemes(taxonomy_id=taxonomy.id, limit=None):
        for cls in repo.list_classes(concept_scheme_id=scheme.id, limit=None):
            for ref in cls.external_references:
                if ref.source == DR_SOURCE and ref.identifier not in spec_ids:
                    type_name = ref.identifier.partition(".")[2]
                    gone_by_type.setdefault(type_name, []).append(ref.identifier)
    moved = [
        f"{old} -> {node.spec_node_id}"
        for node in nodes
        if repo.get_by_identifier(slug_by_spec_node_id[node.spec_node_id]) is None
        for old in gone_by_type.get(node.spec_node_id.partition(".")[2], [])
    ]
    if moved:
        raise ValueError(
            "These node types moved to another layer, which a re-import can't follow yet "
            f"(it would duplicate them): {', '.join(sorted(moved))}"
        )


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

    _refuse_moved_node_types(repo, nodes, slug_by_spec_node_id)

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
                    _attributes_reference(record.full_identifier, record.attributes)
                ],
            )
            summary.property_definitions_created += 1
        else:
            # Existing entity: update everything except external_references here, then
            # sync its DR reference below — a wholesale external_references= replace on
            # update would silently discard any non-DR reference some other source had
            # attached.
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
            _sync_relationship_reference(repo, prop, record)  # type: ignore[arg-type]
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
    # The DR spec is the source of truth: the taxonomy mirrors it, at this revision.
    summary.source_revision = read_source_revision(spec_dir, spec_version)
    ontology_service.set_taxonomy_mirrored(taxonomy.id, True)
    ontology_service.set_taxonomy_source_revision(taxonomy.id, summary.source_revision)
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
    candidates = [*dr_classes, *ontology_repo.list_property_definitions(limit=None)]
    loaded_ids = {*class_id_by_spec_node_id.values(), *property_ids}
    summary.stale = stale_entities(candidates, DR_SOURCE, loaded_ids)
    summary.stale_entities = [
        entity
        for entity in candidates
        if entity.id not in loaded_ids
        and any(ref.source == DR_SOURCE for ref in entity.external_references)
    ]
    return summary


def describe_stale(entity: Class | PropertyDefinition) -> str:
    """'PropertyDefinition 'Title' (<DR id>)', as `ImportSummary.stale` lists it."""
    kind = type(entity).__name__
    ref = next(r.identifier for r in entity.external_references if r.source == DR_SOURCE)
    return f"{kind} {entity.title!r} ({ref})"


def _strings_in(value: Any) -> Iterator[str]:
    """Every string in a field value, however deeply nested in dicts and lists."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings_in(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings_in(item)


def find_prune_blockers(
    repo: OntologyRepository,
    proposals: ChangeProposalRepository,
    stale: list[Class | PropertyDefinition],
) -> list[tuple[str, str]]:
    """
    What still uses the stale entities, as (stale entity, user) descriptions.

    A use is:
      - any row that references a stale entity through a foreign key
        (`find_references`: relationships typed by or attached to it, classes
        and individuals pointing at it, property definitions with it as
        domain/range, attribute definitions on it) other than another stale
        entity;
      - a pending or failed operation of an open change proposal that targets
        a stale entity or names its id anywhere in its fields;
      - an applied operation of a proposal that wasn't reverted which created
        or changed a stale entity: a reflection plan applied here before DR's
        spec has the same change makes its new triples look stale, and deleting
        them would break the proposal's revert and decisions export.

    Empty means all of them can go.
    """
    by_id = {entity.id: entity for entity in stale}
    blockers = [
        (describe_stale(by_id[ref.referenced_id]), f"{ref.dependent_kind} {ref.dependent_id}")
        for ref in repo.find_references(sorted(by_id))
        if ref.dependent_id not in by_id
    ]
    for proposal in proposals.list_proposals(limit=proposals.count_proposals()):
        if proposal.status is ProposalStatus.REVERTED:
            continue  # its applied operations are undone
        for operation in proposal.operations:
            where = (
                f"proposal {proposal.id} ({proposal.title!r}) operation {operation.id} "
                f"(seq {operation.seq}, {operation.op.value} {operation.kind.value}, "
                f"{operation.status.value})"
            )
            if operation.status is OperationStatus.APPLIED:
                changed = {operation.result_entity_id, operation.target_id}
                where += ", which created/changed it; DR's spec may not have this triple yet"
            elif proposal.status is ProposalStatus.OPEN and not operation.decided:
                changed = {operation.target_id, *_strings_in(operation.fields)}
            else:
                continue
            blockers.extend(
                (describe_stale(entity), where)
                for entity_id, entity in by_id.items()
                if entity_id in changed
            )
    return sorted(blockers)


class PruneFailed(Exception):
    """A delete was refused partway through a prune; the earlier deletes stand."""

    def __init__(
        self,
        deleted: list[Class | PropertyDefinition],
        failed: Class | PropertyDefinition,
        error: Exception,
    ):
        self.deleted = deleted
        self.failed = failed
        self.error = error
        super().__init__(f"Deleting {describe_stale(failed)} failed: {error}")


def prune_stale(
    service: OntologyService, stale: list[Class | PropertyDefinition]
) -> list[Class | PropertyDefinition]:
    """
    Delete the stale entities through the service, so each delete is recorded
    like any other. Property definitions go first (they may have a stale class
    as domain or range), then classes, subclasses before their parents.
    Callers check `find_prune_blockers` first.

    Returns:
        The deleted entities, in the order deleted

    Raises:
        PruneFailed: If a delete is refused; the ones before it stay deleted
    """
    classes = {e.id: e for e in stale if isinstance(e, Class)}

    def depth(cls: Class) -> int:
        parent = classes.get(cls.parent_class_id or "")
        return 0 if parent is None else 1 + depth(parent)

    order: list[Class | PropertyDefinition] = [
        *(e for e in stale if isinstance(e, PropertyDefinition)),
        *sorted(classes.values(), key=depth, reverse=True),
    ]
    deleted: list[Class | PropertyDefinition] = []
    for entity in order:
        try:
            if isinstance(entity, PropertyDefinition):
                service.delete_property_definition(entity.id)
            else:
                service.delete_class(entity.id)
        except OntologyError as exc:
            raise PruneFailed(deleted, entity, exc) from exc
        deleted.append(entity)
    return deleted
