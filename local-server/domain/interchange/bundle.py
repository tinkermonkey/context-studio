"""
Context Studio bundle (v0): load a bundle into the ontology, export one from it.

A bundle is one JSON document describing one taxonomy: its summary and vision,
concept schemes, classes and their attributes, relationship types (properties),
individuals and relationships. Loading and exporting both work on a dict;
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
      "relationships": [{"source", "property", "target"}]
    }

Loading. Every write goes through OntologyService, so changes are evented, and
each write is one service call made after comparing, so reloading an unchanged
bundle writes nothing. The taxonomy, schemes, classes and properties are
matched on `identifier`. Individuals are matched on the source's
ExternalReference identifier, then on their UUID: an individual created in
Context Studio exports its UUID as its `id`. Relationships are matched on their
(source, property, target) triple.

References. A class, property or individual the loader creates carries an
ExternalReference(source, identifier or id). A matched property or individual
has its source reference set only if it already has one or the bundle carries
`constraints` or `data` for it; otherwise its references are left alone. A
relationship type that is not the source's is matched only if every end it has
lies in this taxonomy. What
v0 cannot model is carried in that reference's metadata, out of the
definitions that drive vector matching: a property's `constraints` and an
individual's `data`. Relationships with attributes are rejected.

The loader never deletes. Classes, relationship types and individuals that
carry this source's reference, attributes on its classes, and relationships
between its individuals that are no longer in the bundle are reported as stale.

Exporting is the inverse, scoped to one taxonomy: links that leave it (a
property whose domain or range is another taxonomy's class, a relationship to
an individual elsewhere) cannot be expressed and are skipped. Individuals'
data properties have no v0 field, so they do not travel to another workspace.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Iterable, TypeVar

from domain.ontology.entities import (
    AttributeDefinition,
    Class,
    ConceptScheme,
    Individual,
    PropertyDefinition,
    Taxonomy,
)
from domain.ontology.ports import OntologyRepository
from domain.ontology.value_objects import ExternalReference

if TYPE_CHECKING:
    from domain.ontology.services import OntologyService

BUNDLE_FORMAT = "context-studio-bundle"
BUNDLE_VERSION = 0
_RELATIONSHIP_KEYS = {"source", "property", "target"}
_Keyed = TypeVar("_Keyed", ConceptScheme, Class)


class BundleError(ValueError):
    """The bundle is malformed or conflicts with what the workspace already holds."""


@dataclass
class KindCounts:
    """Created, updated and unchanged counts for one kind of entity."""

    created: int = 0
    updated: int = 0
    unchanged: int = 0

    def record(self, outcome: str) -> None:
        setattr(self, outcome, getattr(self, outcome) + 1)


@dataclass
class BundleImportSummary:
    """What a bundle load did, per kind, plus stale entities it left in place."""

    source: str
    counts: dict[str, KindCounts] = field(default_factory=dict)
    stale: list[str] = field(default_factory=list)

    def kind(self, name: str) -> KindCounts:
        return self.counts.setdefault(name, KindCounts())

    @property
    def changed(self) -> int:
        """How many entities were created or updated."""
        return sum(c.created + c.updated for c in self.counts.values())


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


def load_bundle(
    service: OntologyService, repo: OntologyRepository, bundle: dict[str, Any]
) -> BundleImportSummary:
    """
    Idempotently load a bundle into the workspace.

    `service` should be wired with no vector indexes during a bulk load; the
    caller reindexes once afterwards.

    Raises:
        BundleError: If the bundle is malformed, an identifier already belongs
            to another taxonomy, or a reference inside the bundle does not resolve
    """
    check_bundle_header(bundle)
    return _Loader(service, repo, bundle).run()


class _Loader:
    def __init__(
        self, service: OntologyService, repo: OntologyRepository, bundle: dict[str, Any]
    ) -> None:
        self._service = service
        self._repo = repo
        self._bundle = bundle
        self._source = bundle["source"]
        self.summary = BundleImportSummary(source=self._source)
        self._stale: list[str] = []
        self._bundle_triples: set[tuple[str, str, str]] = set()

    # ------------------------------------------------------------------ run

    def run(self) -> BundleImportSummary:
        taxonomy = self._upsert_taxonomy(self._bundle["taxonomy"])
        scheme_ids = self._upsert_schemes(taxonomy.id, self._bundle.get("schemes", []))
        class_ids = self._upsert_classes(taxonomy.id, scheme_ids, self._bundle.get("classes", []))
        taxonomy_class_ids = {cls.id for cls in self._taxonomy_classes(taxonomy.id)}
        property_ids = self._upsert_properties(
            class_ids, taxonomy_class_ids, self._bundle.get("properties", [])
        )
        individual_ids = self._upsert_individuals(
            taxonomy.id, class_ids, taxonomy_class_ids, self._bundle.get("individuals", [])
        )
        self._upsert_relationships(
            individual_ids, property_ids, self._bundle.get("relationships", [])
        )
        self._report_stale(taxonomy.id, class_ids, property_ids, individual_ids)
        return self.summary

    # ------------------------------------------------------------- taxonomy

    def _upsert_taxonomy(self, spec: dict[str, Any]) -> Taxonomy:
        counts = self.summary.kind("taxonomy")
        existing = self._repo.get_by_identifier(spec["identifier"])
        if existing is not None and not isinstance(existing, Taxonomy):
            raise BundleError(
                f"Identifier {spec['identifier']!r} already belongs to a"
                f" {type(existing).__name__}, not a taxonomy"
            )
        if existing is None:
            counts.record("created")
            return self._service.create_taxonomy(
                title=spec["title"],
                description=spec.get("description"),
                identifier=spec["identifier"],
                vision=spec.get("vision"),
            )
        wanted = {
            "title": spec["title"],
            "description": spec.get("description") or "",
            "vision": spec.get("vision") or "",
        }
        current = {
            "title": existing.title,
            "description": existing.description or "",
            "vision": existing.vision or "",
        }
        if wanted == current:
            counts.record("unchanged")
            return existing
        counts.record("updated")
        return self._service.update_taxonomy(existing.id, **wanted)

    # -------------------------------------------------------------- schemes

    def _upsert_schemes(self, taxonomy_id: str, specs: list[dict[str, Any]]) -> dict[str, str]:
        counts = self.summary.kind("scheme")
        ids: dict[str, str] = {}
        for spec in specs:
            existing = self._in_taxonomy(ConceptScheme, taxonomy_id, spec["identifier"])
            if existing is None:
                scheme = self._service.create_scheme(
                    taxonomy_id=taxonomy_id,
                    title=spec["title"],
                    description=spec.get("description"),
                    identifier=spec["identifier"],
                )
                counts.record("created")
            elif (existing.title, existing.description or "") == (
                spec["title"],
                spec.get("description") or "",
            ):
                scheme = existing
                counts.record("unchanged")
            else:
                scheme = self._service.update_concept_scheme(
                    existing.id, title=spec["title"], description=spec.get("description") or ""
                )
                counts.record("updated")
            ids[spec["identifier"]] = scheme.id
        return ids

    # -------------------------------------------------------------- classes

    def _upsert_classes(
        self, taxonomy_id: str, scheme_ids: dict[str, str], specs: list[dict[str, Any]]
    ) -> dict[str, str]:
        counts = self.summary.kind("class")
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
                cls = self._service.create_class(
                    concept_scheme_id=scheme_id,
                    title=spec["title"],
                    description=spec.get("description"),
                    parent_class_id=parent_id,
                    identifier=identifier,
                )
                cls = self._service.update_class(
                    cls.id,
                    external_references=[
                        ExternalReference(source=self._source, identifier=identifier)
                    ],
                )
                counts.record("created")
            else:
                cls, outcome = self._update_class(existing, spec, scheme_id, parent_id)
                counts.record(outcome)
            ids[identifier] = cls.id
            self._upsert_attributes(cls, spec.get("attributes", []))
        return ids

    def _update_class(
        self, existing: Class, spec: dict[str, Any], scheme_id: str, parent_id: str | None
    ) -> tuple[Class, str]:
        cls, outcome = existing, "unchanged"
        if (existing.title, existing.description or "") != (
            spec["title"],
            spec.get("description") or "",
        ):
            cls = self._service.update_class(
                existing.id, title=spec["title"], description=spec.get("description") or ""
            )
            outcome = "updated"
        # Scheme first: the new parent (loaded earlier, parents first) is already there.
        if existing.concept_scheme_id != scheme_id:
            cls = self._service.move_class_to_scheme(existing.id, scheme_id)
            outcome = "updated"
        if existing.parent_class_id != parent_id:
            cls = self._service.move_class(existing.id, parent_id)
            outcome = "updated"
        return cls, outcome

    def _upsert_attributes(self, cls: Class, specs: list[dict[str, Any]]) -> None:
        counts = self.summary.kind("attribute")
        current = {
            a.identifier: a
            for a in self._service.list_attribute_definitions(class_id=cls.id, limit=None)
        }
        wanted_identifiers = [spec["identifier"] for spec in specs]
        for identifier, attribute in current.items():
            if identifier not in wanted_identifiers:
                self._stale.append(
                    f"AttributeDefinition {attribute.title!r} ({identifier}) on {cls.title!r}"
                )
        # Attributes authored in Context Studio may all have sort_order 0. If the
        # bundle lists them in the order they already sort in, keep their sort_order.
        keep_order = [a.identifier for a in _attribute_order(current.values())] == (
            wanted_identifiers
        )
        for position, spec in enumerate(specs):
            existing = current.get(spec["identifier"])
            # "" and [] (not None) so that dropping a description or an enum clears it:
            # the service reads None as "leave unchanged".
            wanted = {
                "title": spec["title"],
                "description": spec.get("description") or "",
                "datatype": spec["datatype"],
                "is_required": bool(spec.get("required", False)),
                "allowed_values": spec.get("allowed_values") or [],
                "sort_order": existing.sort_order if keep_order and existing else position,
            }
            if existing is None:
                self._service.create_attribute_definition(
                    class_id=cls.id,
                    identifier=spec["identifier"],
                    **{**wanted, "description": spec.get("description")},
                )
                counts.record("created")
                continue
            have = {
                "title": existing.title,
                "description": existing.description or "",
                "datatype": str(getattr(existing.datatype, "value", existing.datatype)),
                "is_required": existing.is_required,
                "allowed_values": existing.allowed_values or [],
                "sort_order": existing.sort_order,
            }
            if have == wanted:
                counts.record("unchanged")
            else:
                self._service.update_attribute_definition(existing.id, **wanted)
                counts.record("updated")

    # ----------------------------------------------------------- properties

    def _upsert_properties(
        self,
        class_ids: dict[str, str],
        taxonomy_class_ids: set[str],
        specs: list[dict[str, Any]],
    ) -> dict[str, str]:
        counts = self.summary.kind("property")
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
                prop = self._service.create_property_definition(
                    identifier=identifier,
                    title=spec["title"],
                    description=spec.get("description"),
                    canonical_predicate=spec.get("predicate"),
                    domain_class_id=domain_id,
                    range_class_id=range_id,
                    external_references=[self._reference(identifier, spec.get("constraints"))],
                )
                counts.record("created")
            else:
                prop = self._update_property(existing, spec, domain_id, range_id)
            ids[identifier] = prop.id
        return ids

    def _update_property(
        self,
        existing: PropertyDefinition,
        spec: dict[str, Any],
        domain_id: str | None,
        range_id: str | None,
    ) -> PropertyDefinition:
        counts = self.summary.kind("property")
        references = self._references(existing, spec["identifier"], spec.get("constraints"))
        have = (
            existing.title,
            existing.description or "",
            existing.canonical_predicate,
            existing.domain_class_id,
            existing.range_class_id,
            existing.external_references,
        )
        wanted = (
            spec["title"],
            spec.get("description") or "",
            spec.get("predicate"),
            domain_id,
            range_id,
            references,
        )
        if have == wanted:
            counts.record("unchanged")
            return existing
        counts.record("updated")
        return self._service.update_property_definition(
            existing.id,
            title=spec["title"],
            description=spec.get("description") or "",
            canonical_predicate=spec.get("predicate"),
            update_canonical_predicate=True,
            domain_class_id=domain_id,
            range_class_id=range_id,
            update_domain_class_id=True,
            update_range_class_id=True,
            external_references=references,
        )

    # ---------------------------------------------------------- individuals

    def _upsert_individuals(
        self,
        taxonomy_id: str,
        class_ids: dict[str, str],
        taxonomy_class_ids: set[str],
        specs: list[dict[str, Any]],
    ) -> dict[str, str]:
        counts = self.summary.kind("individual")
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
                individual = self._service.create_individual(
                    wanted_classes,
                    title=spec["title"],
                    description=spec.get("description"),
                    external_references=[self._reference(bundle_id, spec.get("data"))],
                )
                counts.record("created")
            else:
                individual = self._update_individual(
                    existing, spec, wanted_classes, taxonomy_class_ids
                )
            ids[bundle_id] = individual.id
        return ids

    def _individual_by_uuid(
        self, bundle_id: str, taxonomy_class_ids: set[str]
    ) -> Individual | None:
        """An individual created in Context Studio, exported with its UUID as its id."""
        individual = self._repo.get_individual(bundle_id)
        if individual is None or not set(individual.class_ids) & taxonomy_class_ids:
            return None
        return individual

    def _update_individual(
        self,
        existing: Individual,
        spec: dict[str, Any],
        wanted_classes: list[str],
        taxonomy_class_ids: set[str],
    ) -> Individual:
        counts = self.summary.kind("individual")
        references = self._references(existing, spec["id"], spec.get("data"))
        changed = False
        if (existing.title, existing.description or "", existing.external_references) != (
            spec["title"],
            spec.get("description") or "",
            references,
        ):
            existing = self._service.update_individual(
                existing.id,
                title=spec["title"],
                description=spec.get("description") or "",
                external_references=references,
            )
            changed = True
        for class_id in wanted_classes:
            if class_id not in existing.class_ids:
                existing = self._service.add_class_to_individual(existing.id, class_id)
                changed = True
        # Only this taxonomy's classes: a bundle cannot speak for the others.
        for class_id in list(existing.class_ids):
            if class_id in taxonomy_class_ids and class_id not in wanted_classes:
                existing = self._service.remove_class_from_individual(existing.id, class_id)
                changed = True
        counts.record("updated" if changed else "unchanged")
        return existing

    # -------------------------------------------------------- relationships

    def _upsert_relationships(
        self,
        individual_ids: dict[str, str],
        property_ids: dict[str, str],
        specs: list[dict[str, Any]],
    ) -> None:
        counts = self.summary.kind("relationship")
        for spec in specs:
            extra = set(spec) - _RELATIONSHIP_KEYS
            if extra:
                raise BundleError(
                    f"Relationship {spec} carries attributes {sorted(extra)}; v0 bundles"
                    " cannot load relationships with attributes"
                )
            try:
                source_id = individual_ids[spec["source"]]
                target_id = individual_ids[spec["target"]]
                property_id = property_ids[spec["property"]]
            except KeyError as exc:
                raise BundleError(f"Relationship {spec} names unknown {exc}") from None
            self._bundle_triples.add((source_id, property_id, target_id))
            if self._repo.list_relationships(
                source_id=source_id, target_id=target_id, property_id=property_id, limit=None
            ):
                counts.record("unchanged")
                continue
            self._service.create_relationship(source_id, target_id, property_id)
            counts.record("created")

    # ---------------------------------------------------------------- stale

    def _report_stale(
        self,
        taxonomy_id: str,
        class_ids: dict[str, str],
        property_ids: dict[str, str],
        individual_ids: dict[str, str],
    ) -> None:
        loaded = {*class_ids.values(), *property_ids.values(), *individual_ids.values()}
        owned_individuals = self._owned_individuals(taxonomy_id)
        candidates: Iterable[Any] = (
            *self._taxonomy_classes(taxonomy_id),
            *self._repo.list_property_definitions(limit=None),
            *owned_individuals.values(),
        )
        titles = {i.id: i.title for i in owned_individuals.values()}
        predicates = {prop_id: identifier for identifier, prop_id in property_ids.items()}
        dropped_relationships = [
            f"Relationship {titles[rel.source_id]!r} {predicates[rel.property_definition_id]}"
            f" {titles.get(rel.target_id, rel.target_id)!r}"
            for individual_id in titles
            for rel in self._repo.list_relationships(source_id=individual_id, limit=None)
            if rel.property_definition_id in predicates
            and (rel.source_id, rel.property_definition_id, rel.target_id)
            not in self._bundle_triples
        ]
        self.summary.stale = sorted(
            [
                *stale_entities(candidates, self._source, loaded),
                *self._stale,
                *dropped_relationships,
            ]
        )

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
        The entity's references after a load.

        This source's reference is set (in place) when the entity already has one or
        the bundle carries metadata for it; otherwise the references are left alone.
        """
        if not metadata and not self._owns(entity):
            return list(entity.external_references)
        reference = self._reference(identifier, metadata)
        result: list[ExternalReference] = []
        for existing in entity.external_references:
            if existing.source != self._source:
                result.append(existing)
            elif reference not in result:
                result.append(reference)
        if reference not in result:
            result.append(reference)
        return result

    def _taxonomy_classes(self, taxonomy_id: str) -> list[Class]:
        return _taxonomy_classes(self._repo, taxonomy_id)

    def _owned_individuals(self, taxonomy_id: str) -> dict[str, Individual]:
        found: dict[str, Individual] = {}
        for cls in self._taxonomy_classes(taxonomy_id):
            for individual in self._repo.list_individuals(class_id=cls.id, limit=None):
                for ref in individual.external_references:
                    if ref.source == self._source:
                        found[ref.identifier] = individual
        return found

    def _in_taxonomy(self, kind: type[_Keyed], taxonomy_id: str, identifier: str) -> _Keyed | None:
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
        return None if name is None else _Loader._class_id(class_ids, name, where)

    @staticmethod
    def _class_id(class_ids: dict[str, str], name: str, where: str) -> str:
        if name not in class_ids:
            raise BundleError(f"{where} names unknown class {name!r}")
        return class_ids[name]


class BundleExporter:
    """
    Export one taxonomy as a v0 bundle, the inverse of `load_bundle`.

    Loading the exported bundle back into the same workspace writes nothing.
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
    ) -> list[dict[str, str]]:
        triples = {
            (
                individual_keys[rel.source_id],
                property_keys[rel.property_definition_id],
                individual_keys[rel.target_id],
            )
            for individual_id in individual_keys
            for rel in self._repo.list_relationships(source_id=individual_id, limit=None)
            if rel.target_id in individual_keys and rel.property_definition_id in property_keys
        }
        return [{"source": s, "property": p, "target": t} for s, p, t in sorted(triples)]


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
