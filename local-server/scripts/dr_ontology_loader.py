"""
DR spec -> Context Studio ontology transform.

Translates the Documentation Robotics (DR) spec's node/relationship JSON
schemas (`documentation_robotics/spec/schemas/{nodes,relationships}/`) into
Context Studio's ontology domain model: one Taxonomy for the spec as a whole,
one ConceptScheme per DR layer, one Class per node schema, one
AttributeDefinition per node attribute (keyed in its class by the attribute's
DR name; its remaining JSON Schema rides on its DR reference as metadata
`{"schema"}`), and one PropertyDefinition per relationship schema. A relationship schema's
cardinality is its property definition's structure fields (min_per_source,
max_per_source, max_per_target; see `DR_CARDINALITIES`; many-to-many when the
schema gives none), and its strength and x-dr-evidence ride on the property
definition's DR reference as metadata (`{"strength", "evidence"}`; see
`DR_ATTRIBUTE_KEYS`), so a change proposal can change them and
`scripts/export_dr_spec_changes.py` can hand them back to DR.

The spec's design charter (`spec/DESIGN_CHARTER.md`) becomes the taxonomy's
vision, and its "In one paragraph" section the taxonomy's summary
(description). Its predicate catalog (`spec/dist/base.json`) becomes the
taxonomy's predicates: each one's description, and its inverse, category,
archimate_alignment and semantics on its DR reference's metadata (see
`adapters.interchange.dr_relationships.dr_predicate_catalog`).
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
duplicating them. That direct path is for the first import and for test
fixtures: `import_dr_ontology.py` re-imports an existing taxonomy as a drift
proposal for review (`adapters/interchange/dr_drift.py`), which also follows
node types DR moved to another layer.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Iterator
from uuid import uuid4

from adapters.interchange.dr_predicates import dr_predicate_reference
from adapters.interchange.dr_relationships import (  # noqa: F401 - re-exported for the scripts
    DR_ATTRIBUTE_SCHEMA,
    DR_SOURCE,
    DR_TAXONOMY_IDENTIFIER,
    RelationshipSchemaRecord,
    assign_relationship_identifiers,
    compress_relationship_identifiers,
    dr_property_definitions,
)
from adapters.interchange.dr_spec import (  # noqa: F401 - re-exported for the scripts
    CHARTER_FILE,
    AttributeSchemaRecord,
    NodeSchemaRecord,
    _load_json,
    attribute_identifier,
    iter_node_schemas,
    iter_relationship_schemas,
    read_charter,
    read_layer_descriptions,
    read_manifest,
    read_predicate_catalog,
    read_source_revision,
    slugify_spec_node_id,
)
from domain.interchange.bundle import stale_entities
from domain.ontology.entities import AttributeDefinition, Class, PropertyDefinition, Taxonomy
from domain.ontology.exceptions import OntologyError
from domain.ontology.ports import OntologyRepository
from domain.ontology.services import OntologyService
from domain.ontology.value_objects import ExternalReference, SourceRevision
from domain.versioning.ports import ChangeProposalRepository
from domain.versioning.proposals import OperationStatus, ProposalStatus

DR_TAXONOMY_TITLE = "Documentation Robotics"

# An entity an import loads from a spec schema, so a later spec can leave it stale.
SpecEntity = Class | PropertyDefinition | AttributeDefinition


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
    attribute_definitions_created: int = 0
    attribute_definitions_updated: int = 0
    charter_found: bool = False
    source_revision: SourceRevision | None = None
    stale: list[str] = field(default_factory=list)
    # The stale classes, property definitions and attribute definitions, for pruning.
    stale_entities: list[SpecEntity] = field(default_factory=list)
    # x-dr-distinguish keys naming no node type of the spec, or the type itself
    # ("<node id> -> <key>"); DR refuses them on landing, so a valid spec has none.
    distinguish_unresolved: list[str] = field(default_factory=list)


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
        _upsert_predicates(service, repo, taxonomy, catalog)  # type: ignore[arg-type]
    return taxonomy  # type: ignore[return-value]


def _upsert_predicates(
    service: OntologyService,
    repo: OntologyRepository,
    taxonomy: Taxonomy,
    catalog: dict[str, dict[str, Any]],
) -> None:
    """
    Load the spec's predicate catalog into the taxonomy's predicates: each one's
    description, and its DR-only fields on its DR reference. A spec without a
    catalog leaves the predicates as they are.
    """
    for predicate_id, entry in catalog.items():
        reference = dr_predicate_reference(predicate_id, entry)
        existing = repo.get_predicate_by_identifier(taxonomy.id, predicate_id)
        if existing is None:
            service.create_predicate(
                taxonomy.id,
                predicate_id,
                description=entry.get("description"),
                external_references=[reference],
            )
        else:
            others = [ref for ref in existing.external_references if ref.source != DR_SOURCE]
            service.update_predicate(
                existing.id,
                description=entry.get("description") or "",
                external_references=[*others, reference],
            )


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
    matches a DR class whose node schema is gone. A direct import would
    duplicate it, as classes are keyed by an identifier that holds the layer,
    so it stops before writing any class or relationship type; the drift
    re-import follows the move instead.
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
            "These node types moved to another layer, which a direct import can't follow"
            f" (it would duplicate them): {', '.join(sorted(moved))}. Re-import with"
            " scripts/import_dr_ontology.py, which proposes the drift and follows moves."
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
    # Once every class exists, so x-dr-distinguish can name any node type
    for node in nodes:
        _sync_class_definition(service, node, class_id_by_spec_node_id, summary)
    return class_id_by_spec_node_id


def _sync_class_definition(
    service: OntologyService,
    node: NodeSchemaRecord,
    class_id_by_spec_node_id: dict[str, str],
    summary: ImportSummary,
) -> None:
    """
    Give a class its node schema's DR fields as its operational definition
    (#1513): x-dr-standard, x-dr-evidence and x-dr-distinguish, its keys
    resolved to the classes of those node types. A field the schema lacks is
    cleared; an unchanged definition saves nothing.
    """
    class_id = class_id_by_spec_node_id[node.spec_node_id]
    distinguish = []
    for key, when in node.distinguish:
        other_id = class_id_by_spec_node_id.get(key)
        if other_id is None or other_id == class_id:
            summary.distinguish_unresolved.append(f"{node.spec_node_id} -> {key}")
            continue
        distinguish.append({"class_id": other_id, "when": when})
    service.update_class(
        class_id,
        distinguish_from=distinguish,
        evidence_signals=list(node.evidence),
        standard_reference=node.standard or "",
    )


def _upsert_attributes(
    service: OntologyService,
    repo: OntologyRepository,
    nodes: list[NodeSchemaRecord],
    class_id_by_spec_node_id: dict[str, str],
    summary: ImportSummary,
) -> set[str]:
    """
    One attribute definition per node attribute, keyed within its class by the
    attribute's DR name (its DR reference's identifier; the definition's
    identifier is the name in snake case, its title the name): created, or
    updated in place (an unchanged one saves nothing). Its DR reference
    carries the attribute's remaining JSON Schema. Returns the ids of the
    attribute definitions loaded.
    """
    loaded: set[str] = set()
    for node in nodes:
        class_id = class_id_by_spec_node_id[node.spec_node_id]
        identifiers = {record.name: attribute_identifier(record.name) for record in node.attributes}
        clashes = sorted(
            name
            for name, identifier in identifiers.items()
            if list(identifiers.values()).count(identifier) > 1
        )
        if clashes:
            raise ValueError(
                f"Node schema {node.spec_node_id}: attributes {clashes} have the same identifier"
            )
        attributes = repo.list_attribute_definitions(class_id=class_id, limit=None)
        by_identifier = {attr.identifier: attr for attr in attributes}
        by_name = {
            ref.identifier: attr
            for attr in attributes
            for ref in attr.external_references
            if ref.source == DR_SOURCE
        }
        for order, record in enumerate(node.attributes):
            reference = ExternalReference(
                source=DR_SOURCE,
                identifier=record.name,
                metadata=MappingProxyType(record.metadata),
            )
            allowed = list(record.allowed_values) if record.allowed_values else None
            current = by_name.get(record.name) or by_identifier.get(identifiers[record.name])
            if current is None:
                attr = service.create_attribute_definition(
                    class_id=class_id,
                    identifier=identifiers[record.name],
                    title=record.name,
                    datatype=record.datatype,
                    description=record.description,
                    is_required=record.is_required,
                    allowed_values=allowed,
                    sort_order=order,
                    external_references=[reference],
                )
                summary.attribute_definitions_created += 1
            else:
                attr = service.update_attribute_definition(
                    current.id,
                    title=record.name,
                    description=record.description,
                    datatype=record.datatype,
                    is_required=record.is_required,
                    allowed_values=allowed or [],
                    sort_order=order,
                )
                summary.attribute_definitions_updated += 1
                _sync_attribute_reference(repo, attr, reference)
            loaded.add(attr.id)
    return loaded


def _sync_attribute_reference(
    repo: OntologyRepository, attr: AttributeDefinition, reference: ExternalReference
) -> None:
    """Give an attribute definition its DR reference (replacing a differing one); others stay."""
    others = [ref for ref in attr.external_references if ref.source != DR_SOURCE]
    current = [ref for ref in attr.external_references if ref.source == DR_SOURCE]
    if (
        len(current) == 1
        and current[0].identifier == reference.identifier
        and dict(current[0].metadata or {}) == dict(reference.metadata or {})
    ):
        return
    attr.external_references = [*others, reference]
    repo.save_attribute_definition(attr)


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
                create_missing_predicate=True,
                **record.structure,
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
                create_missing_predicate=True,
                structure=record.structure,
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
    attribute_ids = _upsert_attributes(
        ontology_service,
        ontology_repo,
        list(iter_node_schemas(spec_dir)),
        class_id_by_spec_node_id,
        summary,
    )

    # Spec entities from an earlier import that this spec version no longer defines.
    dr_classes = [
        cls
        for scheme in ontology_repo.list_concept_schemes(taxonomy_id=taxonomy.id, limit=None)
        for cls in ontology_repo.list_classes(concept_scheme_id=scheme.id, limit=None)
    ]
    dr_attributes = [
        attr
        for cls in dr_classes
        for attr in ontology_repo.list_attribute_definitions(class_id=cls.id, limit=None)
    ]
    candidates = [
        *dr_classes,
        *ontology_repo.list_property_definitions(limit=None),
        *dr_attributes,
    ]
    loaded_ids = {*class_id_by_spec_node_id.values(), *property_ids, *attribute_ids}
    summary.stale = stale_entities(candidates, DR_SOURCE, loaded_ids)
    summary.stale_entities = [
        entity
        for entity in candidates
        if entity.id not in loaded_ids
        and any(ref.source == DR_SOURCE for ref in entity.external_references)
    ]
    return summary


def describe_stale(entity: SpecEntity) -> str:
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
    stale: list[SpecEntity],
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
        deleted: list[SpecEntity],
        failed: SpecEntity,
        error: Exception,
    ):
        self.deleted = deleted
        self.failed = failed
        self.error = error
        super().__init__(f"Deleting {describe_stale(failed)} failed: {error}")


def prune_stale(service: OntologyService, stale: list[SpecEntity]) -> list[SpecEntity]:
    """
    Delete the stale entities through the service, so each delete is recorded
    like any other. Attribute definitions go first (but not those of a stale
    class, which go with it), then property definitions (they may have a
    stale class as domain or range), then classes, subclasses before their
    parents.
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

    order: list[SpecEntity] = [
        *(e for e in stale if isinstance(e, AttributeDefinition) and e.class_id not in classes),
        *(e for e in stale if isinstance(e, PropertyDefinition)),
        *sorted(classes.values(), key=depth, reverse=True),
    ]
    deleted: list[SpecEntity] = []
    for entity in order:
        try:
            if isinstance(entity, AttributeDefinition):
                service.delete_attribute_definition(entity.id)
            elif isinstance(entity, PropertyDefinition):
                service.delete_property_definition(entity.id)
            else:
                service.delete_class(entity.id)
        except OntologyError as exc:
            raise PruneFailed(deleted, entity, exc) from exc
        deleted.append(entity)
    return deleted
