"""
Drift between the DR spec on disk and the dr_spec taxonomy, as a plan of
proposal operations (`domain.versioning.drift`).

Everything the DR importer loads is compared, matched by DR id (the
`documentation_robotics` external reference), never by identifier:

- the taxonomy: its vision and summary (when the spec has a design charter);
- predicates, by id: description, and inverse, category, archimate_alignment
  and semantics on their DR reference; a new predicate is a create, one the
  spec dropped a delete (after the relationship-type deletes);
- schemes, by layer: title, and description when the layer file has one; a new
  layer is a create;
- classes, by spec node id: title, description, scheme, DR reference, and
  their operational definition (#1513) from x-dr-standard, x-dr-evidence and
  x-dr-distinguish (whose keys name types new in the spec only once those
  types' creates have applied);
- attributes, by DR attribute name within their class: title, description,
  datatype, required, allowed values, and the rest of their JSON Schema on
  their DR reference;
- relationship types, by DR relationship id: title, description, predicate,
  domain and range, and cardinality, strength and evidence on their DR
  reference. Their identifiers aren't compared: the DR id is their identity.

Moves. A node type DR moved to another layer has a new spec node id, so it
matches no class by id. When exactly one class whose DR id the spec no longer
has shares its type name (the part after the layer), the class has moved: its
DR reference is swapped for the new id, and it is moved to the new layer's
scheme unless it is there already (a move made in Context Studio and landed
by DR). Relationship types with no match by id are then matched on (domain
class, predicate, range class) among those whose DR id is gone, so a moved
node's relationship types get their new ids too. Anything else unmatched is a
create, and a class, attribute or relationship type whose DR id the spec no
longer has is a delete; deletes are breaking, so they always wait for review
(a relationship type still in use shows its blockers there).

Operations come in apply order: the taxonomy, schemes, classes (creates,
updates and moves), attributes, relationship types, then deletes
(relationship types, attributes, classes). A relationship type's DR id is
checked against its classes' DR references when it applies, so classes come
first.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from adapters.interchange.dr_predicates import dr_predicate_reference
from adapters.interchange.dr_relationships import (
    DR_SOURCE,
    DR_TAXONOMY_IDENTIFIER,
    RelationshipSchemaRecord,
    assign_relationship_identifiers,
    dr_predicate_catalog,
    dr_property_definitions,
)
from adapters.interchange.dr_spec import (
    NodeSchemaRecord,
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
from domain.ontology.entities import AttributeDefinition, Class, PropertyDefinition, Taxonomy
from domain.ontology.ports import OntologyRepository
from domain.ontology.value_objects import ExternalReference
from domain.versioning.drift import DriftEntry, DriftError, DriftPlan
from domain.versioning.proposals import OperationDraft, OperationKind, OperationType

DR_DRIFT_SOURCE = "dr_spec"

K, T = OperationKind, OperationType


def _text(value: Any) -> str:
    """Text as compared: None and "" are the same."""
    return value or ""


def _json(value: Any) -> Any:
    """A JSON value as plain dicts and lists ({} and None are the same)."""
    plain = json.loads(json.dumps(value, default=dict)) if value else None
    return plain or None


def _reference(identifier: str, metadata: Any = None) -> dict[str, Any]:
    """A DR external reference as an operation field value."""
    return {"source": DR_SOURCE, "identifier": identifier, "metadata": _json(metadata)}


def _dr_ref(entity: Any) -> ExternalReference | None:
    return next((r for r in entity.external_references if r.source == DR_SOURCE), None)


def _with_dr_ref(entity: Any, reference: dict[str, Any]) -> list[dict[str, Any]]:
    """The entity's references with its DR reference replaced (others kept, in order)."""
    others = [r.to_dict() for r in entity.external_references if r.source != DR_SOURCE]
    return [*others, reference]


def _property_title(record: RelationshipSchemaRecord) -> str:
    """A relationship type's title, as the importer gives it: its DR id with spaces."""
    return f"{record.source_spec_node_id} {record.predicate} {record.destination_spec_node_id}"


def _type_name(spec_node_id: str) -> str:
    """'application.capability' -> 'capability'."""
    return spec_node_id.partition(".")[2]


def _match(
    node: NodeSchemaRecord,
    by_id: dict[str, Class],
    gone: dict[str, list[tuple[str, Class]]],
    moved: set[str],
) -> tuple[Class | None, str | None]:
    """
    The class a node type is now, and its old DR id when it moved: the class
    with its DR id, else the one class of the same type name that left the
    spec (and no other node took). Adds that old id to `moved`.
    """
    cls = by_id.get(node.spec_node_id)
    if cls is not None:
        return cls, None
    candidates = gone.get(_type_name(node.spec_node_id), [])
    if len(candidates) == 1 and candidates[0][0] not in moved:
        old_id, cls = candidates[0]
        moved.add(old_id)
        return cls, old_id
    return None, None


def _definition(
    node: NodeSchemaRecord, class_ids: dict[str, str], own_id: str | None = None
) -> dict[str, Any]:
    """
    A node schema's DR fields as its class's operational definition (#1513),
    x-dr-distinguish keys resolved to existing classes (others left out).
    """
    return {
        "standard_reference": node.standard,
        "evidence_signals": list(node.evidence),
        "distinguish_from": [
            {"class_id": class_ids[key], "when": when}
            for key, when in node.distinguish
            if key in class_ids and class_ids[key] != own_id
        ],
    }


def _as_distinguish(entries: list[dict[str, str]], dr_ids: dict[str, str]) -> dict[str, str]:
    """A class's distinguish_from as x-dr-distinguish: DR node id (else class id) -> when."""
    return {dr_ids.get(e["class_id"], e["class_id"]): e["when"] for e in entries}


class DrDriftPlanner:
    """Plans the drift between a DR spec checkout and the dr_spec taxonomy."""

    def __init__(self, repo: OntologyRepository) -> None:
        self._repo = repo

    def plan(self, location: str) -> DriftPlan:
        """
        Compare the spec at `location` (a DR `spec/` directory) with the taxonomy.

        Raises:
            DriftError: If the spec can't be read, the taxonomy hasn't been
                imported yet, or the spec can't be matched unambiguously
        """
        spec_dir = Path(location).expanduser()
        if not (spec_dir / "dist" / "manifest.json").is_file():
            raise DriftError(f"{spec_dir} is not a DR spec directory (no dist/manifest.json)")
        taxonomy = self._repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
        if not isinstance(taxonomy, Taxonomy):
            raise DriftError(
                f"No '{DR_TAXONOMY_IDENTIFIER}' taxonomy yet: import the DR spec first"
                " (scripts/import_dr_ontology.py)"
            )
        try:
            return _Planner(self._repo, taxonomy, spec_dir).run()
        except (OSError, ValueError) as exc:
            if isinstance(exc, DriftError):
                raise
            raise DriftError(str(exc)) from exc


class _Planner:
    def __init__(self, repo: OntologyRepository, taxonomy: Taxonomy, spec_dir: Path) -> None:
        self._repo = repo
        self._taxonomy = taxonomy
        self._spec_dir = spec_dir
        spec_version, self._layers = read_manifest(spec_dir)
        self._plan = DriftPlan(
            taxonomy_id=taxonomy.id,
            source=DR_DRIFT_SOURCE,
            source_revision=read_source_revision(spec_dir, spec_version),
        )
        self._spec_version = spec_version
        self._ops: list[OperationDraft] = []
        # Deletes by kind; relationship types go first, classes last.
        self._deletes: dict[OperationKind, list[OperationDraft]] = {
            K.PROPERTY: [],
            K.PREDICATE: [],
            K.ATTRIBUTE: [],
            K.CLASS: [],
        }

    # ------------------------------------------------------------------ run

    def run(self) -> DriftPlan:
        nodes = list(iter_node_schemas(self._spec_dir))
        records = list(iter_relationship_schemas(self._spec_dir))
        self._plan_taxonomy()
        scheme_ids = self._plan_schemes()
        class_ids = self._plan_classes(nodes, scheme_ids)
        self._plan_attributes(nodes, class_ids)
        self._plan_properties(records, class_ids)
        deletes = [d for kind_deletes in self._deletes.values() for d in kind_deletes]
        for seq, draft in enumerate([*self._ops, *deletes], start=1):
            draft.seq = seq
            self._plan.operations.append(draft)
        return self._plan

    # ------------------------------------------------------------ recording

    def _create(self, kind: OperationKind, ref: str, fields: dict[str, Any], source_id: str) -> str:
        self._ops.append(OperationDraft(seq=0, op=T.CREATE, kind=kind, ref=ref, fields=fields))
        self._plan.entries.append(DriftEntry(kind=kind.value, source_id=source_id, change="create"))
        return f"${ref}"

    def _changed(
        self,
        kind: OperationKind,
        entity: Any,
        source_id: str,
        pairs: dict[str, tuple[Any, Any]],
        compare: dict[str, tuple[Any, Any]] | None = None,
        move: dict[str, Any] | None = None,
        change: str = "update",
        carry: dict[str, Any] | None = None,
    ) -> None:
        """
        Plan an update of the fields whose values differ, and a move if given.

        Args:
            pairs: Field -> (the taxonomy's value, the spec's value); the spec's
                value is what the update sets
            compare: Field -> (taxonomy, spec) values to compare, and show in the
                drift report, instead of the pair (a reference's id and metadata
                rather than the whole list)
            move: The move's fields, if the entity moves
            change: What the drift report calls it (update or move)
            carry: Fields the update also sets, unchanged, whenever it sets any
        """
        compare = compare or {}
        shown: dict[str, dict[str, Any]] = {}
        fields: dict[str, Any] = {}
        for name, (current, spec) in pairs.items():
            seen = compare.get(name, (current, spec))
            if seen[0] != seen[1]:
                fields[name] = spec
                shown[name] = {"taxonomy": seen[0], "source": seen[1]}
        if fields:
            fields = {**(carry or {}), **fields}
            self._ops.append(
                OperationDraft(seq=0, op=T.UPDATE, kind=kind, target_id=entity.id, fields=fields)
            )
        if move:
            self._ops.append(
                OperationDraft(seq=0, op=T.MOVE, kind=kind, target_id=entity.id, fields=move)
            )
            shown["concept_scheme_id"] = {
                "taxonomy": entity.concept_scheme_id,
                "source": move["concept_scheme_id"],
            }
        if shown:
            self._plan.entries.append(
                DriftEntry(
                    kind=kind.value,
                    source_id=source_id,
                    change=change,
                    entity_id=entity.id,
                    fields=shown,
                )
            )

    def _delete(self, kind: OperationKind, entity: Any, source_id: str) -> None:
        self._deletes[kind].append(
            OperationDraft(seq=0, op=T.DELETE, kind=kind, target_id=entity.id)
        )
        self._plan.entries.append(
            DriftEntry(kind=kind.value, source_id=source_id, change="delete", entity_id=entity.id)
        )

    # ------------------------------------------------------------- taxonomy

    def _plan_taxonomy(self) -> None:
        taxonomy = self._taxonomy
        pairs: dict[str, tuple[Any, Any]] = {}
        vision, summary = read_charter(self._spec_dir)
        if vision is not None:
            pairs["vision"] = (_text(taxonomy.vision), vision)
            if summary is not None:
                pairs["description"] = (_text(taxonomy.description), summary)
        self._predicates = self._plan_predicates()
        self._changed(K.TAXONOMY, taxonomy, DR_TAXONOMY_IDENTIFIER, pairs)

    def _plan_predicates(self) -> set[str]:
        """
        Plan the predicate changes that make the taxonomy's catalog match the
        spec's: a create for a new predicate, an update of a description or DR
        field, a delete for one the spec dropped (after the relationship-type
        deletes, so its types go first). Returns the predicates there will be.
        """
        stored = {p.identifier: p for p in self._repo.list_predicates(self._taxonomy.id)}
        catalog = read_predicate_catalog(self._spec_dir)
        if catalog is None:
            return set(stored)
        known = dr_predicate_catalog(self._repo) or {}
        for predicate_id in sorted(catalog.keys() | stored.keys()):
            spec, current, existing = (
                catalog.get(predicate_id),
                known.get(predicate_id),
                stored.get(predicate_id),
            )
            if spec is None:
                self._deletes[K.PREDICATE].append(
                    OperationDraft(seq=0, op=T.DELETE, kind=K.PREDICATE, target_id=existing.id)
                )
                self._plan.entries.append(
                    DriftEntry(
                        kind="predicate",
                        source_id=predicate_id,
                        change="delete",
                        entity_id=existing.id,
                    )
                )
                continue
            reference = dr_predicate_reference(predicate_id, spec).to_dict()
            if existing is None:
                self._create(
                    K.PREDICATE,
                    f"predicate:{predicate_id}",
                    {
                        "identifier": predicate_id,
                        "description": spec.get("description"),
                        "external_references": [reference],
                    },
                    predicate_id,
                )
                continue
            current = current or {}
            shown = {
                name: {"taxonomy": current.get(name), "source": spec.get(name)}
                for name in sorted(spec.keys() | current.keys())
                if current.get(name) != spec.get(name)
            }
            if not shown:
                continue
            fields: dict[str, Any] = {}
            if "description" in shown:
                fields["description"] = spec.get("description")
            if set(shown) - {"description"}:
                fields["external_references"] = _with_dr_ref(existing, reference)
            self._ops.append(
                OperationDraft(
                    seq=0, op=T.UPDATE, kind=K.PREDICATE, target_id=existing.id, fields=fields
                )
            )
            self._plan.entries.append(
                DriftEntry(
                    kind="predicate",
                    source_id=predicate_id,
                    change="update",
                    entity_id=existing.id,
                    fields=shown,
                )
            )
        return set(catalog)

    # -------------------------------------------------------------- schemes

    def _plan_schemes(self) -> dict[str, str]:
        descriptions = read_layer_descriptions(self._spec_dir)
        ids: dict[str, str] = {}
        for layer in self._layers:
            layer_id = layer["id"]
            identifier = layer_id.replace("-", "_")
            existing = self._repo.get_by_identifier(identifier)
            if existing is None:
                ids[layer_id] = self._create(
                    K.SCHEME,
                    f"scheme:{identifier}",
                    {
                        "taxonomy_id": self._taxonomy.id,
                        "title": layer["name"],
                        "description": descriptions.get(layer_id),
                        "identifier": identifier,
                    },
                    layer_id,
                )
                continue
            if getattr(existing, "taxonomy_id", None) != self._taxonomy.id or isinstance(
                existing, Class
            ):
                raise DriftError(
                    f"Identifier {identifier!r} (layer {layer_id}) belongs to another entity"
                )
            pairs: dict[str, tuple[Any, Any]] = {"title": (existing.title, layer["name"])}
            if layer_id in descriptions:
                pairs["description"] = (_text(existing.description), descriptions[layer_id])
            self._changed(K.SCHEME, existing, layer_id, pairs)
            ids[layer_id] = existing.id
        return ids

    # -------------------------------------------------------------- classes

    def _taxonomy_classes(self) -> list[Class]:
        return [
            cls
            for scheme in self._repo.list_concept_schemes(taxonomy_id=self._taxonomy.id, limit=None)
            for cls in self._repo.list_classes(concept_scheme_id=scheme.id, limit=None)
        ]

    def _plan_classes(
        self, nodes: list[NodeSchemaRecord], scheme_ids: dict[str, str]
    ) -> dict[str, str]:
        spec_ids = {node.spec_node_id for node in nodes}
        by_id: dict[str, Class] = {}
        gone: dict[str, list[tuple[str, Class]]] = {}
        for cls in self._taxonomy_classes():
            ref = _dr_ref(cls)
            if ref is None:
                continue
            if ref.identifier in spec_ids:
                by_id[ref.identifier] = cls
            else:
                gone.setdefault(_type_name(ref.identifier), []).append((ref.identifier, cls))
        # The class each node type is now, matched as the loop below matches them,
        # so x-dr-distinguish can name any of them (a type new in this spec has no
        # class yet; the next re-import names it, once its create has applied).
        existing: dict[str, str] = {}
        matched: set[str] = set()
        for node in nodes:
            found, _ = _match(node, by_id, gone, matched)
            if found is not None:
                existing[node.spec_node_id] = found.id
        dr_ids = {
            cls.id: ref.identifier
            for cls in self._taxonomy_classes()
            if (ref := _dr_ref(cls)) is not None
        }

        class_ids: dict[str, str] = {}
        moved: set[str] = set()
        for node in nodes:
            scheme_id = scheme_ids.get(node.layer_id)
            if scheme_id is None:
                raise DriftError(
                    f"Node schema {node.spec_node_id} is in layer {node.layer_id!r}, which"
                    " the manifest doesn't list"
                )
            cls, old_id = _match(node, by_id, gone, moved)
            if cls is None:
                identifier = slugify_spec_node_id(node.spec_node_id)
                if self._repo.get_by_identifier(identifier) is not None:
                    raise DriftError(
                        f"Node type {node.spec_node_id} is new, but its identifier"
                        f" {identifier!r} is already taken"
                    )
                class_ids[node.spec_node_id] = self._create(
                    K.CLASS,
                    f"class:{identifier}",
                    {
                        "concept_scheme_id": scheme_id,
                        "title": node.title,
                        "description": node.description,
                        "identifier": identifier,
                        "external_references": [_reference(node.spec_node_id)],
                        **_definition(node, existing),
                    },
                    node.spec_node_id,
                )
                continue
            definition = _definition(node, existing, cls.id)
            pairs: dict[str, tuple[Any, Any]] = {
                "title": (cls.title, node.title),
                "description": (_text(cls.description), _text(node.description)),
                "standard_reference": (cls.standard_reference, definition["standard_reference"]),
                "evidence_signals": (cls.evidence_signals, definition["evidence_signals"]),
                "distinguish_from": (cls.distinguish_from, definition["distinguish_from"]),
            }
            if old_id is not None:
                pairs["external_references"] = (
                    [r.to_dict() for r in cls.external_references],
                    _with_dr_ref(cls, _reference(node.spec_node_id)),
                )
            move = None
            if cls.concept_scheme_id != scheme_id:
                move = {"concept_scheme_id": scheme_id, "parent_class_id": None}
            # distinguish shows in DR's terms, as x-dr-distinguish
            compare = {
                "distinguish_from": (
                    _as_distinguish(cls.distinguish_from, dr_ids),
                    _as_distinguish(definition["distinguish_from"], dr_ids),
                )
            }
            if old_id is not None:
                compare["external_references"] = (old_id, node.spec_node_id)
            change = "move" if old_id is not None or move else "update"
            self._changed(K.CLASS, cls, node.spec_node_id, pairs, compare, move, change)
            class_ids[node.spec_node_id] = cls.id
        for candidates in gone.values():
            for old_id, cls in candidates:
                if old_id not in moved:
                    self._delete(K.CLASS, cls, old_id)
        return class_ids

    # ----------------------------------------------------------- attributes

    def _plan_attributes(self, nodes: list[NodeSchemaRecord], class_ids: dict[str, str]) -> None:
        for node in nodes:
            class_id = class_ids[node.spec_node_id]
            identifiers = {r.name: attribute_identifier(r.name) for r in node.attributes}
            if len(set(identifiers.values())) < len(identifiers):
                raise DriftError(
                    f"Node schema {node.spec_node_id}: two attributes have the same identifier"
                )
            existing: list[AttributeDefinition] = (
                []
                if class_id.startswith("$")
                else self._repo.list_attribute_definitions(class_id=class_id, limit=None)
            )
            by_name = {ref.identifier: a for a in existing if (ref := _dr_ref(a)) is not None}
            by_identifier = {a.identifier: a for a in existing}
            matched: set[str] = set()
            for order, record in enumerate(node.attributes):
                source_id = f"{node.spec_node_id}#{record.name}"
                allowed = list(record.allowed_values) if record.allowed_values else None
                reference = _reference(record.name, record.metadata)
                attr = by_name.get(record.name) or by_identifier.get(identifiers[record.name])
                if attr is None:
                    self._create(
                        K.ATTRIBUTE,
                        f"attribute:{node.spec_node_id}#{record.name}",
                        {
                            "class_id": class_id,
                            "identifier": identifiers[record.name],
                            "title": record.name,
                            "datatype": record.datatype,
                            "description": record.description,
                            "is_required": record.is_required,
                            "allowed_values": allowed,
                            "sort_order": order,
                            "external_references": [reference],
                        },
                        source_id,
                    )
                    continue
                matched.add(attr.id)
                current = _dr_ref(attr)
                pairs = {
                    "title": (attr.title, record.name),
                    "description": (_text(attr.description), _text(record.description)),
                    "datatype": (getattr(attr.datatype, "value", attr.datatype), record.datatype),
                    "is_required": (attr.is_required, record.is_required),
                    "allowed_values": (attr.allowed_values or None, allowed),
                    "external_references": (
                        [r.to_dict() for r in attr.external_references],
                        _with_dr_ref(attr, reference),
                    ),
                }
                compare = {
                    "external_references": (
                        (current.identifier, _json(current.metadata)) if current else None,
                        (record.name, reference["metadata"]),
                    )
                }
                self._changed(K.ATTRIBUTE, attr, source_id, pairs, compare)
            for attr in existing:
                ref = _dr_ref(attr)
                if attr.id not in matched and ref is not None:
                    self._delete(K.ATTRIBUTE, attr, f"{node.spec_node_id}#{ref.identifier}")

    # ----------------------------------------------------- relationship types

    def _plan_properties(
        self, records: list[RelationshipSchemaRecord], class_ids: dict[str, str]
    ) -> None:
        taxonomy_classes = {cls.id for cls in self._taxonomy_classes()}
        by_id = {
            dr_id: prop
            for dr_id, prop in dr_property_definitions(self._repo).items()
            if prop.domain_class_id in taxonomy_classes or prop.range_class_id in taxonomy_classes
        }
        spec_ids = {r.full_identifier for r in records}
        gone = {dr_id: prop for dr_id, prop in by_id.items() if dr_id not in spec_ids}
        by_triple: dict[tuple[str | None, str | None, str | None], list[str]] = {}
        for dr_id, prop in gone.items():
            key = (prop.domain_class_id, prop.canonical_predicate, prop.range_class_id)
            by_triple.setdefault(key, []).append(dr_id)
        matched: dict[str, PropertyDefinition] = {}
        for record in records:
            prop = by_id.get(record.full_identifier)
            if prop is None:
                key = (
                    class_ids.get(record.source_spec_node_id),
                    record.predicate,
                    class_ids.get(record.destination_spec_node_id),
                )
                found = by_triple.get(key, [])
                if len(found) == 1 and found[0] in gone:
                    prop = gone.pop(found[0])
            if prop is not None:
                matched[record.full_identifier] = prop
        identifiers = assign_relationship_identifiers(
            records,
            self._repo,
            {
                r.full_identifier: p.id if (p := matched.get(r.full_identifier)) else None
                for r in records
            },
            only=[r.full_identifier for r in records if r.full_identifier not in matched],
        )
        undefined = sorted({r.predicate for r in records} - self._predicates)
        if undefined:
            raise DriftError(
                f"The spec's relationship types use predicates its catalog doesn't define"
                f" ({', '.join(undefined)})"
            )
        for record in records:
            domain = class_ids.get(record.source_spec_node_id)
            range_ = class_ids.get(record.destination_spec_node_id)
            if domain is None or range_ is None:
                raise DriftError(
                    f"Relationship schema {record.full_identifier} names a node type the"
                    " spec doesn't define"
                )
            reference = _reference(record.full_identifier, record.attributes)
            prop = matched.get(record.full_identifier)
            if prop is None:
                self._create(
                    K.PROPERTY,
                    f"property:{record.full_identifier}",
                    {
                        "identifier": identifiers[record.full_identifier],
                        "title": _property_title(record),
                        "description": record.description,
                        "canonical_predicate": record.predicate,
                        "domain_class_id": domain,
                        "range_class_id": range_,
                        "external_references": [reference],
                    },
                    record.full_identifier,
                )
                continue
            current = _dr_ref(prop)
            pairs = {
                "title": (prop.title, _property_title(record)),
                "description": (_text(prop.description), _text(record.description)),
                "canonical_predicate": (prop.canonical_predicate, record.predicate),
                "domain_class_id": (prop.domain_class_id, domain),
                "range_class_id": (prop.range_class_id, range_),
                "external_references": (
                    [r.to_dict() for r in prop.external_references],
                    _with_dr_ref(prop, reference),
                ),
            }
            compare = {
                "external_references": (
                    (current.identifier, _json(current.metadata)) if current else None,
                    (record.full_identifier, reference["metadata"]),
                )
            }
            # A new DR id is checked against the triple the update gives (its
            # classes' DR ids), so a renamed one carries its triple along.
            carry = None
            if current is None or current.identifier != record.full_identifier:
                carry = {
                    "canonical_predicate": record.predicate,
                    "domain_class_id": domain,
                    "range_class_id": range_,
                }
            self._changed(K.PROPERTY, prop, record.full_identifier, pairs, compare, carry=carry)
        for dr_id, prop in gone.items():
            self._delete(K.PROPERTY, prop, dr_id)
