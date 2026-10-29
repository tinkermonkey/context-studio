"""
Context Studio bundle (v0): plan a bundle import as proposal operations; export one.

A bundle is one JSON document describing one taxonomy: its summary and vision,
concept schemes, classes and their attributes, relationship types (properties),
individuals and relationships. Planning and exporting both work on a dict;
reading and writing files is left to the scripts.

    {
      "format": "context-studio-bundle", "version": 0, "source": "house",
      "taxonomy": {"identifier", "title", "description", "vision"},
      "schemes": [{"identifier", "title", "description"}],
      "classes": [{"identifier", "scheme", "parent", "title", "description",
                   "attributes": [{"identifier", "title", "datatype", "description",
                                   "required", "allowed_values"}]}],
      "properties": [{"identifier", "title", "description", "predicate",
                      "domain", "range", "constraints": {}}],
      "individuals": [{"id", "classes": [...], "title", "description", "data": {}}],
      "relationships": [{"source", "property", "target", "attributes": {}}]
    }

Planning. `plan_bundle` only reads: it compares the bundle with the workspace
and returns the operations that would make the workspace match, as drafts for
a change proposal (`domain.versioning.bundle_import` proposes and applies them).
A bundle that matches the workspace plans no operations. The taxonomy, schemes,
classes and properties are matched on `identifier`. Individuals are matched on
the source's ExternalReference identifier, then on their UUID: an individual
created in Context Studio exports its UUID as its `id`. Relationships are
matched on their (source, property, target) triple; their `attributes` (JSON
scalars, e.g. a kit's quantity, unit and optional) may use only the names the
property lists in `constraints.edge_properties`. A create names its new entity
with a ref ("class:house_room"), so later operations point at it as "$class:...".

References. A class, property or individual the plan creates carries an
ExternalReference(source, identifier or id). A matched property or individual
that already has the source's reference keeps it, identifier included, and only
its metadata is set; one without gets a reference only if the bundle carries
`constraints` or `data` for it. A relationship type that is not the source's is
matched only if every end it has lies in this taxonomy. What v0 cannot model is
carried in that reference's metadata, out of the definitions that drive vector
matching: a property's `constraints` and an individual's `data`.

Deletes. Classes, relationship types and individuals that carry this source's
reference, attributes on the bundle's classes, and relationships between the
source's individuals (or of a relationship type being deleted) that are no
longer in the bundle are planned as deletes, which are breaking.

Exporting is the inverse, scoped to one taxonomy: links that leave it (a
property whose domain or range is another taxonomy's class, a relationship to
an individual elsewhere) cannot be expressed and are skipped. Individuals'
data properties have no v0 field, so they do not travel to another workspace.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any, Iterable, TypeVar

from domain.ontology.entities import (
    AttributeDefinition,
    Class,
    ConceptScheme,
    Individual,
    PropertyDefinition,
    Taxonomy,
    same_attributes,
    validate_relationship_attributes,
)
from domain.ontology.ports import OntologyRepository
from domain.ontology.value_objects import ExternalReference
from domain.versioning.proposals import OperationDraft, OperationKind, OperationType

BUNDLE_FORMAT = "context-studio-bundle"
BUNDLE_VERSION = 0
_RELATIONSHIP_KEYS = {"source", "property", "target", "attributes"}
_Keyed = TypeVar("_Keyed", ConceptScheme, Class)

K, T = OperationKind, OperationType


class BundleError(ValueError):
    """The bundle is malformed or conflicts with what the workspace already holds."""


@dataclass
class KindCounts:
    """Planned creates, updates and deletes, and unchanged entities, for one kind."""

    created: int = 0
    updated: int = 0
    unchanged: int = 0
    deleted: int = 0

    def record(self, outcome: str) -> None:
        setattr(self, outcome, getattr(self, outcome) + 1)


@dataclass
class BundlePlan:
    """
    The operations that make the workspace match a bundle.

    Attributes:
        source: The bundle's source
        taxonomy: The bundle's taxonomy entry (identifier, title, description, vision)
        taxonomy_id: The matching taxonomy, or None when the import would create it
            (its schemes then point at the placeholder NEW_TAXONOMY)
        operations: Drafts in apply order: creates, then updates and moves, then deletes
        counts: Per kind of entity, what the plan does
        deletes: A description of each entity the plan deletes
    """

    source: str
    taxonomy: dict[str, Any]
    taxonomy_id: str | None = None
    operations: list[OperationDraft] = field(default_factory=list)
    counts: dict[str, KindCounts] = field(default_factory=dict)
    deletes: list[str] = field(default_factory=list)

    def kind(self, name: str) -> KindCounts:
        return self.counts.setdefault(name, KindCounts())

    @property
    def changed(self) -> int:
        """How many entities the plan creates, updates or deletes."""
        return sum(c.created + c.updated + c.deleted for c in self.counts.values())


# The taxonomy id a plan uses when the taxonomy does not exist yet.
NEW_TAXONOMY = "<new taxonomy>"


def check_bundle_header(bundle: dict[str, Any]) -> None:
    """
    Check a bundle's format, version, source and taxonomy identifier.

    Raises:
        BundleError: If the bundle is not a v0 bundle or lacks a source or taxonomy identifier
    """
    if bundle.get("format") != BUNDLE_FORMAT or bundle.get("version") != BUNDLE_VERSION:
        raise BundleError(
            f"Not a {BUNDLE_FORMAT} v{BUNDLE_VERSION} bundle "
            f"(format={bundle.get('format')!r}, version={bundle.get('version')!r})"
        )
    if not bundle.get("source") or not bundle.get("taxonomy", {}).get("identifier"):
        raise BundleError("A bundle needs a 'source' and a 'taxonomy.identifier'")


def plan_bundle(repo: OntologyRepository, bundle: dict[str, Any]) -> BundlePlan:
    """
    Plan the operations that make the workspace match a bundle; writes nothing.

    Raises:
        BundleError: If the bundle is malformed, an identifier already belongs
            to another taxonomy, or a reference inside the bundle does not resolve
    """
    check_bundle_header(bundle)
    return _Planner(repo, bundle).run()


def _ref(kind: str, key: str) -> str:
    return f"{kind}:{key}"


def _text(value: Any) -> str:
    return value or ""


class _Planner:
    def __init__(self, repo: OntologyRepository, bundle: dict[str, Any]) -> None:
        self._repo = repo
        self._bundle = bundle
        self._source = bundle["source"]
        self.plan = BundlePlan(source=self._source, taxonomy=bundle["taxonomy"])
        self._creates: list[OperationDraft] = []
        self._updates: list[OperationDraft] = []
        self._deletes: list[OperationDraft] = []
        self._deleted_ids: set[str] = set()
        self._bundle_triples: set[tuple[str, str, str]] = set()

    # ------------------------------------------------------------------ run

    def run(self) -> BundlePlan:
        # Checked before anything else: a bad edge refuses the whole bundle.
        edge_properties = _edge_properties(self._bundle)
        for spec in self._bundle.get("relationships", []):
            _relationship_attributes(spec, edge_properties)
        taxonomy = self._plan_taxonomy(self._bundle["taxonomy"])
        taxonomy_id = taxonomy.id if taxonomy else None
        self.plan.taxonomy_id = taxonomy_id
        taxonomy_classes = self._taxonomy_classes(taxonomy_id)
        scheme_ids = self._plan_schemes(taxonomy_id, self._bundle.get("schemes", []))
        class_ids = self._plan_classes(taxonomy_id, scheme_ids, self._bundle.get("classes", []))
        taxonomy_class_ids = {cls.id for cls in taxonomy_classes}
        property_ids = self._plan_properties(
            class_ids, taxonomy_class_ids, self._bundle.get("properties", [])
        )
        individual_ids = self._plan_individuals(
            taxonomy_id, class_ids, taxonomy_class_ids, self._bundle.get("individuals", [])
        )
        self._plan_relationships(
            individual_ids, property_ids, self._bundle.get("relationships", [])
        )
        self._plan_deletes(taxonomy_id, taxonomy_classes, class_ids, property_ids, individual_ids)
        for seq, draft in enumerate([*self._creates, *self._updates, *self._deletes], start=1):
            draft.seq = seq
            self.plan.operations.append(draft)
        self.plan.deletes.sort()
        return self.plan

    def _create(self, kind: OperationKind, ref: str, fields: dict[str, Any]) -> str:
        """Plan a create; returns the "$ref" later operations point at it with."""
        self._creates.append(
            OperationDraft(
                seq=0,
                op=T.CREATE,
                kind=kind,
                ref=ref,
                fields={name: value for name, value in fields.items() if value is not None},
            )
        )
        return f"${ref}"

    def _update(
        self,
        kind: OperationKind,
        target_id: str,
        fields: dict[str, Any],
        op: OperationType = T.UPDATE,
    ) -> None:
        self._updates.append(
            OperationDraft(seq=0, op=op, kind=kind, target_id=target_id, fields=fields)
        )

    def _delete(self, kind: OperationKind, entity: Any, description: str, counted: str) -> None:
        if entity.id in self._deleted_ids:
            return
        self._deleted_ids.add(entity.id)
        self._deletes.append(OperationDraft(seq=0, op=T.DELETE, kind=kind, target_id=entity.id))
        self.plan.deletes.append(description)
        self.plan.kind(counted).record("deleted")

    # ------------------------------------------------------------- taxonomy

    def _plan_taxonomy(self, spec: dict[str, Any]) -> Taxonomy | None:
        counts = self.plan.kind("taxonomy")
        existing = self._repo.get_by_identifier(spec["identifier"])
        if existing is not None and not isinstance(existing, Taxonomy):
            raise BundleError(
                f"Identifier {spec['identifier']!r} already belongs to a"
                f" {type(existing).__name__}, not a taxonomy"
            )
        if existing is None:
            counts.record("created")
            return None
        changed = _changed(
            {
                "title": (existing.title, spec["title"]),
                "description": (_text(existing.description), _text(spec.get("description"))),
                "vision": (_text(existing.vision), _text(spec.get("vision"))),
            }
        )
        if changed:
            self._update(K.TAXONOMY, existing.id, changed)
        counts.record("updated" if changed else "unchanged")
        return existing

    # -------------------------------------------------------------- schemes

    def _plan_schemes(self, taxonomy_id: str | None, specs: list[dict[str, Any]]) -> dict[str, str]:
        counts = self.plan.kind("scheme")
        ids: dict[str, str] = {}
        for spec in specs:
            identifier = spec["identifier"]
            existing = self._in_taxonomy(ConceptScheme, taxonomy_id, identifier)
            if existing is None:
                ids[identifier] = self._create(
                    K.SCHEME,
                    _ref("scheme", identifier),
                    {
                        "taxonomy_id": taxonomy_id or NEW_TAXONOMY,
                        "title": spec["title"],
                        "description": spec.get("description"),
                        "identifier": identifier,
                    },
                )
                counts.record("created")
                continue
            changed = _changed(
                {
                    "title": (existing.title, spec["title"]),
                    "description": (_text(existing.description), _text(spec.get("description"))),
                }
            )
            if changed:
                self._update(K.SCHEME, existing.id, changed)
            counts.record("updated" if changed else "unchanged")
            ids[identifier] = existing.id
        return ids

    # -------------------------------------------------------------- classes

    def _plan_classes(
        self, taxonomy_id: str | None, scheme_ids: dict[str, str], specs: list[dict[str, Any]]
    ) -> dict[str, str]:
        counts = self.plan.kind("class")
        ids: dict[str, str] = {}
        for spec in _parents_first(specs):
            identifier = spec["identifier"]
            scheme_id = scheme_ids.get(spec["scheme"])
            if scheme_id is None:
                raise BundleError(f"Class {identifier!r} names unknown scheme {spec['scheme']!r}")
            parent_id = None
            if spec.get("parent"):
                parent_id = ids.get(spec["parent"])
                if parent_id is None:
                    raise BundleError(
                        f"Class {identifier!r} names unknown parent {spec['parent']!r}"
                    )
            existing = self._in_taxonomy(Class, taxonomy_id, identifier)
            if existing is None:
                ids[identifier] = self._create(
                    K.CLASS,
                    _ref("class", identifier),
                    {
                        "concept_scheme_id": scheme_id,
                        "title": spec["title"],
                        "description": spec.get("description"),
                        "parent_class_id": parent_id,
                        "identifier": identifier,
                        "external_references": [
                            ExternalReference(source=self._source, identifier=identifier).to_dict()
                        ],
                    },
                )
                counts.record("created")
                self._plan_attributes(identifier, ids[identifier], {}, spec.get("attributes", []))
                continue
            counts.record(self._plan_class_update(existing, spec, scheme_id, parent_id))
            ids[identifier] = existing.id
            current = {
                a.identifier: a
                for a in self._repo.list_attribute_definitions(class_id=existing.id, limit=None)
            }
            self._plan_attributes(
                identifier, existing.id, current, spec.get("attributes", []), existing
            )
        return ids

    def _plan_class_update(
        self, existing: Class, spec: dict[str, Any], scheme_id: str, parent_id: str | None
    ) -> str:
        changed = _changed(
            {
                "title": (existing.title, spec["title"]),
                "description": (_text(existing.description), _text(spec.get("description"))),
            }
        )
        if changed:
            self._update(K.CLASS, existing.id, changed)
        move: dict[str, Any] = {}
        # A class moving to another scheme names its parent there (or None).
        if existing.concept_scheme_id != scheme_id:
            move = {"concept_scheme_id": scheme_id, "parent_class_id": parent_id}
        elif existing.parent_class_id != parent_id:
            move = {"parent_class_id": parent_id}
        if move:
            self._update(K.CLASS, existing.id, move, op=T.MOVE)
        return "updated" if changed or move else "unchanged"

    def _plan_attributes(
        self,
        class_key: str,
        class_id: str,
        current: dict[str, AttributeDefinition],
        specs: list[dict[str, Any]],
        cls: Class | None = None,
    ) -> None:
        counts = self.plan.kind("attribute")
        wanted_identifiers = {spec["identifier"] for spec in specs}
        for identifier, attribute in current.items():
            if identifier not in wanted_identifiers and cls is not None:
                self._delete(
                    K.ATTRIBUTE,
                    attribute,
                    f"AttributeDefinition {attribute.title!r} ({identifier}) on {cls.title!r}",
                    "attribute",
                )
        sort_orders = _sort_orders(current, specs)
        for spec in specs:
            existing = current.get(spec["identifier"])
            wanted = {
                "title": spec["title"],
                "description": spec.get("description") or None,
                "datatype": spec["datatype"],
                "is_required": bool(spec.get("required", False)),
                "allowed_values": spec.get("allowed_values") or None,
                "sort_order": sort_orders[spec["identifier"]],
            }
            if existing is None:
                self._create(
                    K.ATTRIBUTE,
                    _ref("attribute", f"{class_key}/{spec['identifier']}"),
                    {"class_id": class_id, "identifier": spec["identifier"], **wanted},
                )
                counts.record("created")
                continue
            have = {
                "title": existing.title,
                "description": existing.description or None,
                "datatype": str(getattr(existing.datatype, "value", existing.datatype)),
                "is_required": existing.is_required,
                "allowed_values": existing.allowed_values or None,
                "sort_order": existing.sort_order,
            }
            changed = {name: value for name, value in wanted.items() if have[name] != value}
            if changed:
                self._update(K.ATTRIBUTE, existing.id, changed)
            counts.record("updated" if changed else "unchanged")

    # ----------------------------------------------------------- properties

    def _plan_properties(
        self,
        class_ids: dict[str, str],
        taxonomy_class_ids: set[str],
        specs: list[dict[str, Any]],
    ) -> dict[str, str]:
        counts = self.plan.kind("property")
        ids: dict[str, str] = {}
        for spec in specs:
            identifier = spec["identifier"]
            domain_id = self._class_ref(class_ids, spec.get("domain"), f"property {identifier}")
            range_id = self._class_ref(class_ids, spec.get("range"), f"property {identifier}")
            existing = self._repo.get_property_definition_by_identifier(identifier)
            if existing is not None and not (
                self._owns(existing) or _within(existing, taxonomy_class_ids)
            ):
                raise BundleError(
                    f"Relationship type {identifier!r} already exists, was not loaded from"
                    f" {self._source!r} and does not lie within this taxonomy; prefix the"
                    " bundle's identifiers"
                )
            if existing is None:
                ids[identifier] = self._create(
                    K.PROPERTY,
                    _ref("property", identifier),
                    {
                        "identifier": identifier,
                        "title": spec["title"],
                        "description": spec.get("description"),
                        "canonical_predicate": spec.get("predicate"),
                        "domain_class_id": domain_id,
                        "range_class_id": range_id,
                        "external_references": [
                            self._reference(identifier, spec.get("constraints")).to_dict()
                        ],
                    },
                )
                counts.record("created")
                continue
            references = self._references(existing, identifier, spec.get("constraints"))
            changed = _changed(
                {
                    "title": (existing.title, spec["title"]),
                    "description": (_text(existing.description), _text(spec.get("description"))),
                    "canonical_predicate": (existing.canonical_predicate, spec.get("predicate")),
                    "domain_class_id": (existing.domain_class_id, domain_id),
                    "range_class_id": (existing.range_class_id, range_id),
                }
            )
            if existing.external_references != references:
                changed["external_references"] = [r.to_dict() for r in references]
            if changed:
                self._update(K.PROPERTY, existing.id, changed)
            counts.record("updated" if changed else "unchanged")
            ids[identifier] = existing.id
        return ids

    # ---------------------------------------------------------- individuals

    def _plan_individuals(
        self,
        taxonomy_id: str | None,
        class_ids: dict[str, str],
        taxonomy_class_ids: set[str],
        specs: list[dict[str, Any]],
    ) -> dict[str, str]:
        counts = self.plan.kind("individual")
        existing_by_reference = self._owned_individuals(taxonomy_id)
        ids: dict[str, str] = {}
        for spec in specs:
            bundle_id = spec["id"]
            wanted_classes = [
                self._class_id(class_ids, name, f"individual {bundle_id}")
                for name in spec["classes"]
            ]
            existing = existing_by_reference.get(bundle_id) or self._individual_by_uuid(
                bundle_id, taxonomy_class_ids
            )
            if existing is None:
                ids[bundle_id] = self._create(
                    K.INDIVIDUAL,
                    _ref("individual", bundle_id),
                    {
                        "class_ids": wanted_classes,
                        "title": spec["title"],
                        "description": spec.get("description"),
                        "external_references": [
                            self._reference(bundle_id, spec.get("data")).to_dict()
                        ],
                    },
                )
                counts.record("created")
                continue
            changed = _changed(
                {
                    "title": (existing.title, spec["title"]),
                    "description": (_text(existing.description), _text(spec.get("description"))),
                }
            )
            references = self._references(existing, bundle_id, spec.get("data"))
            if existing.external_references != references:
                changed["external_references"] = [r.to_dict() for r in references]
            # Only this taxonomy's classes: a bundle cannot speak for the others.
            kept = [
                c for c in existing.class_ids if c not in taxonomy_class_ids or c in wanted_classes
            ]
            classes = kept + [c for c in wanted_classes if c not in kept]
            if classes != list(existing.class_ids):
                changed["class_ids"] = classes
            if changed:
                self._update(K.INDIVIDUAL, existing.id, changed)
            counts.record("updated" if changed else "unchanged")
            ids[bundle_id] = existing.id
        return ids

    def _individual_by_uuid(
        self, bundle_id: str, taxonomy_class_ids: set[str]
    ) -> Individual | None:
        """An individual created in Context Studio, exported with its UUID as its id."""
        individual = self._repo.get_individual(bundle_id)
        if individual is None or not set(individual.class_ids) & taxonomy_class_ids:
            return None
        return individual

    # -------------------------------------------------------- relationships

    def _plan_relationships(
        self,
        individual_ids: dict[str, str],
        property_ids: dict[str, str],
        specs: list[dict[str, Any]],
    ) -> None:
        counts = self.plan.kind("relationship")
        edge_properties = _edge_properties(self._bundle)
        for spec in specs:
            attributes = _relationship_attributes(spec, edge_properties)
            try:
                source_id = individual_ids[spec["source"]]
                target_id = individual_ids[spec["target"]]
                property_id = property_ids[spec["property"]]
            except KeyError as exc:
                raise BundleError(f"Relationship {spec} names unknown {exc}") from None
            self._bundle_triples.add((source_id, property_id, target_id))
            existing = []
            if not any(_is_ref(i) for i in (source_id, target_id, property_id)):
                existing = self._repo.list_relationships(
                    source_id=source_id, target_id=target_id, property_id=property_id, limit=None
                )
            if not existing:
                self._create(
                    K.RELATIONSHIP,
                    _ref("relationship", f"{spec['source']}/{spec['property']}/{spec['target']}"),
                    {
                        "source_id": source_id,
                        "target_id": target_id,
                        "property_definition_id": property_id,
                        "attributes": attributes or None,
                    },
                )
                counts.record("created")
            elif same_attributes(existing[0].attributes, attributes):
                counts.record("unchanged")
            else:
                self._update(K.RELATIONSHIP, existing[0].id, {"attributes": attributes})
                counts.record("updated")

    # -------------------------------------------------------------- deletes

    def _plan_deletes(
        self,
        taxonomy_id: str | None,
        taxonomy_classes: list[Class],
        class_ids: dict[str, str],
        property_ids: dict[str, str],
        individual_ids: dict[str, str],
    ) -> None:
        """
        Relationships first, then individuals, properties and classes (children
        first), so nothing is deleted while something planned to go still uses it.
        Attribute deletes were planned with their classes.
        """
        loaded = {*class_ids.values(), *property_ids.values(), *individual_ids.values()}
        owned_individuals = self._owned_individuals(taxonomy_id)
        titles = {i.id: i.title for i in owned_individuals.values()}
        predicates = {prop_id: identifier for identifier, prop_id in property_ids.items()}
        for individual_id in titles:
            for rel in self._repo.list_relationships(source_id=individual_id, limit=None):
                # Both ends the source's: a link to an individual made in Context
                # Studio is not the bundle's to drop.
                if (
                    rel.target_id in titles
                    and rel.property_definition_id in predicates
                    and (rel.source_id, rel.property_definition_id, rel.target_id)
                    not in self._bundle_triples
                ):
                    self._delete(
                        K.RELATIONSHIP,
                        rel,
                        f"Relationship {titles[rel.source_id]!r}"
                        f" {predicates[rel.property_definition_id]}"
                        f" {titles[rel.target_id]!r}",
                        "relationship",
                    )
        stale_properties = [
            prop
            for prop in self._repo.list_property_definitions(limit=None)
            if self._owns(prop) and prop.id not in loaded
        ]
        # A relationship type can't be deleted while relationships use it.
        for prop in stale_properties:
            for rel in self._repo.list_relationships(property_id=prop.id, limit=None):
                self._delete(
                    K.RELATIONSHIP,
                    rel,
                    f"Relationship {rel.source_id} {prop.identifier} {rel.target_id}",
                    "relationship",
                )
        for individual in owned_individuals.values():
            if individual.id not in loaded:
                self._delete(
                    K.INDIVIDUAL, individual, _describe(individual, self._source), "individual"
                )
        for prop in stale_properties:
            self._delete(K.PROPERTY, prop, _describe(prop, self._source), "property")
        depth = _depths(taxonomy_classes)
        for cls in sorted(taxonomy_classes, key=lambda c: -depth[c.id]):
            if self._owns(cls) and cls.id not in loaded:
                self._delete(K.CLASS, cls, _describe(cls, self._source), "class")

    # -------------------------------------------------------------- helpers

    def _reference(self, identifier: str, metadata: dict[str, Any] | None) -> ExternalReference:
        return ExternalReference(
            source=self._source,
            identifier=identifier,
            metadata=MappingProxyType(dict(metadata)) if metadata else None,
        )

    def _owns(self, entity: Any) -> bool:
        return any(ref.source == self._source for ref in entity.external_references)

    def _references(
        self, entity: Any, identifier: str, metadata: dict[str, Any] | None
    ) -> list[ExternalReference]:
        """
        The entity's references after the import.

        If the entity already has this source's reference, only that reference's
        metadata is set: its identifier may differ from the bundle key (the DR importer
        keys references by spec id) and is kept. Otherwise a reference is added only
        when the bundle carries metadata for the entity.
        """
        references = list(entity.external_references)
        wanted = self._reference(identifier, metadata)
        for position, existing in enumerate(references):
            if existing.source == self._source:
                references[position] = replace(existing, metadata=wanted.metadata)
                return references
        return [*references, wanted] if metadata else references

    def _taxonomy_classes(self, taxonomy_id: str | None) -> list[Class]:
        return _taxonomy_classes(self._repo, taxonomy_id) if taxonomy_id else []

    def _owned_individuals(self, taxonomy_id: str | None) -> dict[str, Individual]:
        found: dict[str, Individual] = {}
        for cls in self._taxonomy_classes(taxonomy_id):
            for individual in self._repo.list_individuals(class_id=cls.id, limit=None):
                for ref in individual.external_references:
                    if ref.source == self._source:
                        found[ref.identifier] = individual
        return found

    def _in_taxonomy(
        self, kind: type[_Keyed], taxonomy_id: str | None, identifier: str
    ) -> _Keyed | None:
        """The scheme or class with this identifier, refusing one owned elsewhere."""
        entity = self._repo.get_by_identifier(identifier)
        if entity is None:
            return None
        if not isinstance(entity, kind) or entity.taxonomy_id != taxonomy_id:
            raise BundleError(
                f"Identifier {identifier!r} already belongs to another taxonomy or kind;"
                " identifiers are unique across the workspace, so prefix the bundle's"
                " identifiers"
            )
        return entity

    @staticmethod
    def _class_ref(class_ids: dict[str, str], name: str | None, where: str) -> str | None:
        return None if name is None else _Planner._class_id(class_ids, name, where)

    @staticmethod
    def _class_id(class_ids: dict[str, str], name: str, where: str) -> str:
        if name not in class_ids:
            raise BundleError(f"{where} names unknown class {name!r}")
        return class_ids[name]


def _changed(pairs: dict[str, tuple[Any, Any]]) -> dict[str, Any]:
    """The fields whose (have, want) differ, with the wanted value ("" becomes None: clear it)."""
    return {
        name: want if want != "" else None for name, (have, want) in pairs.items() if have != want
    }


def _is_ref(value: str) -> bool:
    return value.startswith("$")


def _describe(entity: Any, source: str) -> str:
    reference = _source_reference(entity, source)
    key = reference.identifier if reference else entity.id
    return f"{type(entity).__name__} {entity.title!r} ({key})"


def _depths(classes: list[Class]) -> dict[str, int]:
    """Each class's depth in its hierarchy (a root is 0)."""
    parents = {cls.id: cls.parent_class_id for cls in classes}
    depths: dict[str, int] = {}
    for class_id in parents:
        depth, current, seen = 0, parents.get(class_id), {class_id}
        while current is not None and current in parents and current not in seen:
            seen.add(current)
            depth += 1
            current = parents[current]
        depths[class_id] = depth
    return depths


class BundleExporter:
    """
    Export one taxonomy as a v0 bundle, the inverse of `plan_bundle`.

    Planning the exported bundle against the same workspace plans nothing.
    Entries are sorted by key so that a bundle kept in a repository diffs cleanly.
    """

    def __init__(self, repository: OntologyRepository) -> None:
        self._repo = repository

    def export(self, taxonomy_id: str, source: str | None = None) -> dict[str, Any]:
        """
        Export a taxonomy as a bundle dict.

        Args:
            taxonomy_id: The taxonomy to export
            source: The bundle source; its ExternalReferences supply individuals'
                ids, properties' constraints and individuals' data. Defaults to the
                taxonomy's identifier.

        Raises:
            BundleError: If the taxonomy does not exist, or it, one of its schemes or
                one of its classes has no identifier
        """
        taxonomy = self._repo.get_taxonomy(taxonomy_id)
        if taxonomy is None:
            raise BundleError(f"No taxonomy {taxonomy_id!r}")
        schemes = self._repo.list_concept_schemes(taxonomy_id=taxonomy_id, limit=None)
        classes = _taxonomy_classes(self._repo, taxonomy_id)
        # An entity saved without an identifier reads back with a display-only
        # fallback that does not resolve; a load would then create a duplicate.
        keyed: list[Taxonomy | ConceptScheme | Class] = [taxonomy, *schemes, *classes]
        missing = [
            f"{type(e).__name__} {e.title!r}"
            for e in keyed
            if not e.identifier
            or getattr(self._repo.get_by_identifier(e.identifier), "id", None) != e.id
        ]
        if missing:
            raise BundleError(
                "Bundles key the taxonomy, schemes and classes by identifier; these have"
                f" no stored identifier: {', '.join(missing)}"
            )
        keys = {e.id: str(e.identifier) for e in keyed}
        source = source or keys[taxonomy.id]
        scheme_keys = {s.id: keys[s.id] for s in schemes}
        class_keys = {c.id: keys[c.id] for c in classes}
        properties = self._properties(source, class_keys)
        individuals = self._individuals(classes)
        individual_keys = {i.id: _bundle_id(i, source) for i in individuals}
        return {
            "format": BUNDLE_FORMAT,
            "version": BUNDLE_VERSION,
            "source": source,
            "taxonomy": {
                "identifier": taxonomy.identifier,
                "title": taxonomy.title,
                "description": taxonomy.description,
                "vision": taxonomy.vision,
            },
            "schemes": sorted(
                (
                    {"identifier": s.identifier, "title": s.title, "description": s.description}
                    for s in schemes
                ),
                key=lambda s: s["identifier"],
            ),
            "classes": sorted(
                (self._class(c, scheme_keys, class_keys) for c in classes),
                key=lambda c: c["identifier"],
            ),
            "properties": sorted(
                (_property(p, source, class_keys) for p in properties),
                key=lambda p: p["identifier"],
            ),
            "individuals": sorted(
                (_individual(i, source, individual_keys[i.id], class_keys) for i in individuals),
                key=lambda i: i["id"],
            ),
            "relationships": self._relationships(
                individual_keys, {p.id: p.identifier for p in properties}
            ),
        }

    def _class(
        self, cls: Class, scheme_keys: dict[str, str], class_keys: dict[str, str]
    ) -> dict[str, Any]:
        spec: dict[str, Any] = {
            "identifier": cls.identifier,
            "scheme": scheme_keys[cls.concept_scheme_id],
            "title": cls.title,
            "description": cls.description,
        }
        if cls.parent_class_id:
            spec["parent"] = class_keys[cls.parent_class_id]
        attributes = _attribute_order(
            self._repo.list_attribute_definitions(class_id=cls.id, limit=None)
        )
        if attributes:
            spec["attributes"] = [_attribute(a) for a in attributes]
        return spec

    def _properties(self, source: str, class_keys: dict[str, str]) -> list[PropertyDefinition]:
        """Properties this source loaded or that touch the taxonomy, if both ends fit."""
        return [
            prop
            for prop in self._repo.list_property_definitions(limit=None)
            if (
                any(r.source == source for r in prop.external_references)
                or prop.domain_class_id in class_keys
                or prop.range_class_id in class_keys
            )
            and all(
                end is None or end in class_keys
                for end in (prop.domain_class_id, prop.range_class_id)
            )
        ]

    def _individuals(self, classes: list[Class]) -> list[Individual]:
        found: dict[str, Individual] = {}
        for cls in classes:
            for individual in self._repo.list_individuals(class_id=cls.id, limit=None):
                found[individual.id] = individual
        return list(found.values())

    def _relationships(
        self, individual_keys: dict[str, str], property_keys: dict[str, str]
    ) -> list[dict[str, Any]]:
        by_triple = {
            (
                individual_keys[rel.source_id],
                property_keys[rel.property_definition_id],
                individual_keys[rel.target_id],
            ): rel.attributes
            for individual_id in individual_keys
            for rel in self._repo.list_relationships(source_id=individual_id, limit=None)
            if rel.target_id in individual_keys and rel.property_definition_id in property_keys
        }
        relationships: list[dict[str, Any]] = []
        for (source, prop, target), attributes in sorted(by_triple.items()):
            spec: dict[str, Any] = {"source": source, "property": prop, "target": target}
            if attributes:
                spec["attributes"] = dict(sorted(attributes.items()))
            relationships.append(spec)
        return relationships


def _edge_properties(bundle: dict[str, Any]) -> dict[str, list[str]]:
    """Per bundle property identifier, the attribute names its constraints allow."""
    return {
        prop["identifier"]: (prop.get("constraints") or {}).get("edge_properties") or []
        for prop in bundle.get("properties", [])
    }


def _relationship_attributes(
    spec: dict[str, Any], edge_properties: dict[str, list[str]]
) -> dict[str, Any]:
    """
    A bundle relationship's attributes, checked against its property's edge_properties.

    Raises:
        BundleError: For keys other than source, property, target and attributes,
            attributes that are not an object of JSON scalars, or names the
            property's constraints.edge_properties does not list
    """
    extra = set(spec) - _RELATIONSHIP_KEYS
    if extra:
        raise BundleError(
            f"Relationship {spec} has unknown keys {sorted(extra)}; edge values go in"
            " 'attributes'"
        )
    attributes = spec.get("attributes") or {}
    try:
        validate_relationship_attributes(attributes)
    except ValueError as exc:
        raise BundleError(f"Relationship {spec}: {exc}") from None
    allowed = edge_properties.get(str(spec.get("property")), [])
    unknown = sorted(set(attributes) - set(allowed))
    if unknown:
        listed = ", ".join(allowed) if allowed else "none"
        raise BundleError(
            f"Relationship {spec} carries attributes {unknown} that property"
            f" {spec.get('property')!r} does not list in constraints.edge_properties"
            f" (allowed: {listed})"
        )
    return dict(attributes)


def _within(prop: PropertyDefinition, class_ids: set[str] | dict[str, str]) -> bool:
    """Whether a property has an end and every end it has is one of these classes."""
    ends = [end for end in (prop.domain_class_id, prop.range_class_id) if end is not None]
    return bool(ends) and all(end in class_ids for end in ends)


def _source_reference(entity: Any, source: str) -> ExternalReference | None:
    return next((r for r in entity.external_references if r.source == source), None)


def _bundle_id(individual: Individual, source: str) -> str:
    """The source's identifier for an individual, or its UUID if it was made here."""
    reference = _source_reference(individual, source)
    return reference.identifier if reference else individual.id


def _metadata(entity: Any, source: str) -> dict[str, Any]:
    reference = _source_reference(entity, source)
    return dict(reference.metadata) if reference and reference.metadata else {}


def _attribute(attribute: AttributeDefinition) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "identifier": attribute.identifier,
        "title": attribute.title,
        "datatype": str(getattr(attribute.datatype, "value", attribute.datatype)),
        "description": attribute.description,
    }
    if attribute.is_required:
        spec["required"] = True
    if attribute.allowed_values:
        spec["allowed_values"] = list(attribute.allowed_values)
    return spec


def _property(prop: PropertyDefinition, source: str, class_keys: dict[str, str]) -> dict[str, Any]:
    return {
        "identifier": prop.identifier,
        "title": prop.title,
        "description": prop.description,
        "predicate": prop.canonical_predicate,
        "domain": class_keys.get(prop.domain_class_id) if prop.domain_class_id else None,
        "range": class_keys.get(prop.range_class_id) if prop.range_class_id else None,
        "constraints": _metadata(prop, source),
    }


def _individual(
    individual: Individual, source: str, bundle_id: str, class_keys: dict[str, str]
) -> dict[str, Any]:
    return {
        "id": bundle_id,
        "classes": [class_keys[c] for c in individual.class_ids if c in class_keys],
        "title": individual.title,
        "description": individual.description,
        "data": _metadata(individual, source),
    }


def _taxonomy_classes(repo: OntologyRepository, taxonomy_id: str) -> list[Class]:
    return [
        cls
        for scheme in repo.list_concept_schemes(taxonomy_id=taxonomy_id, limit=None)
        for cls in repo.list_classes(concept_scheme_id=scheme.id, limit=None)
    ]


def _attribute_order(attributes: Iterable[AttributeDefinition]) -> list[AttributeDefinition]:
    return sorted(attributes, key=lambda a: (a.sort_order, a.title))


def _sort_orders(
    current: dict[str, AttributeDefinition], specs: list[dict[str, Any]]
) -> dict[str, int]:
    """
    The sort_order each bundle attribute should have: its position in the bundle.

    Attributes authored in Context Studio may all sit at sort_order 0, ordered by
    title. When the bundle lists them in the order they already sort in, their
    sort_order is kept, unless they tie and a title changes: the tie would then
    break differently on the next load, so positions (all distinct) are written.
    """
    positions = {spec["identifier"]: position for position, spec in enumerate(specs)}
    if [a.identifier for a in _attribute_order(current.values())] != list(positions):
        return positions
    tied = len({a.sort_order for a in current.values()}) < len(current)
    retitled = any(current[spec["identifier"]].title != spec["title"] for spec in specs)
    if tied and retitled:
        return positions
    return {identifier: attribute.sort_order for identifier, attribute in current.items()}


def stale_entities(entities: Iterable[Any], source: str, loaded_ids: set[str]) -> list[str]:
    """
    Describe entities that carry `source`'s reference but were not loaded this time.

    Shared with the DR spec importer, which reports spec entities a newer spec
    version dropped.
    """
    stale = []
    for entity in entities:
        refs = [r for r in entity.external_references if r.source == source]
        if refs and entity.id not in loaded_ids:
            kind = type(entity).__name__
            stale.append(f"{kind} {entity.title!r} ({refs[0].identifier})")
    return sorted(stale)


def _parents_first(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Order class specs so every parent comes before its children."""
    by_identifier = {spec["identifier"]: spec for spec in specs}
    ordered: list[dict[str, Any]] = []
    placed: set[str] = set()

    def place(spec: dict[str, Any], trail: tuple[str, ...]) -> None:
        identifier = spec["identifier"]
        if identifier in placed:
            return
        if identifier in trail:
            raise BundleError(f"Class hierarchy has a cycle: {' -> '.join((*trail, identifier))}")
        parent = spec.get("parent")
        if parent and parent in by_identifier:
            place(by_identifier[parent], (*trail, identifier))
        placed.add(identifier)
        ordered.append(spec)

    for spec in specs:
        place(spec, ())
    return ordered
