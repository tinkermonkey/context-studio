"""
Context Studio bundle (v0) -> ontology loader.

A bundle is one JSON file describing another project's ontology: its taxonomy
(with summary and vision), concept schemes, classes and their attributes,
relationship types (properties), individuals and relationships. Phase B of the
ontology workbench reuses the same format for export.

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

Every write goes through OntologyService, so changes are evented. Idempotent:
schemes, classes and properties are keyed on `identifier`; classes, properties
and individuals also carry an ExternalReference(source, identifier or id).
Relationships are keyed on their (source, property, target) triple. Re-loading
the same bundle changes nothing.

What v0 cannot model yet is carried, not dropped: a property's `constraints`
(cardinality, symmetry, edge attribute names) and an individual's `data`
(aliases, estimates) are kept in the bundle source's ExternalReference
metadata, out of the definitions that drive vector matching. Relationships
with attributes are rejected.

The loader never deletes. Entities that carry this source's reference but are
no longer in the bundle are reported as stale.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Iterable

from domain.ontology.entities import (
    Class,
    ConceptScheme,
    Individual,
    PropertyDefinition,
    Taxonomy,
)
from domain.ontology.ports import OntologyRepository
from domain.ontology.services import OntologyService
from domain.ontology.value_objects import ExternalReference

BUNDLE_FORMAT = "context-studio-bundle"
BUNDLE_VERSION = 0
_RELATIONSHIP_KEYS = {"source", "property", "target"}


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


def read_bundle(path: Path) -> dict[str, Any]:
    """Read and check a bundle file's header."""
    try:
        bundle = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise BundleError(f"Malformed JSON in {path}: {exc}") from exc
    if bundle.get("format") != BUNDLE_FORMAT or bundle.get("version") != BUNDLE_VERSION:
        raise BundleError(
            f"{path} is not a {BUNDLE_FORMAT} v{BUNDLE_VERSION} file "
            f"(format={bundle.get('format')!r}, version={bundle.get('version')!r})"
        )
    if not bundle.get("source") or not bundle.get("taxonomy", {}).get("identifier"):
        raise BundleError(f"{path} needs a 'source' and a 'taxonomy.identifier'")
    return bundle


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
    loader = _Loader(service, repo, bundle)
    return loader.run()


class _Loader:
    def __init__(
        self, service: OntologyService, repo: OntologyRepository, bundle: dict[str, Any]
    ) -> None:
        self._service = service
        self._repo = repo
        self._bundle = bundle
        self._source = bundle["source"]
        self.summary = BundleImportSummary(source=self._source)

    # ------------------------------------------------------------------ run

    def run(self) -> BundleImportSummary:
        taxonomy = self._upsert_taxonomy(self._bundle["taxonomy"])
        scheme_ids = self._upsert_schemes(taxonomy.id, self._bundle.get("schemes", []))
        class_ids = self._upsert_classes(taxonomy.id, scheme_ids, self._bundle.get("classes", []))
        property_ids = self._upsert_properties(class_ids, self._bundle.get("properties", []))
        individual_ids = self._upsert_individuals(
            taxonomy.id, class_ids, self._bundle.get("individuals", [])
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
            existing = self._repo.get_by_identifier(spec["identifier"])
            if existing is not None:
                self._require_in_taxonomy(existing, ConceptScheme, taxonomy_id, spec["identifier"])
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
            existing = self._repo.get_by_identifier(identifier)
            if existing is not None:
                self._require_in_taxonomy(existing, Class, taxonomy_id, identifier)
            if existing is None:
                cls = self._service.create_class(
                    concept_scheme_id=scheme_id,
                    title=spec["title"],
                    description=spec.get("description"),
                    parent_class_id=parent_id,
                    identifier=identifier,
                )
                counts.record("created")
            else:
                cls, outcome = self._update_class(existing, spec, parent_id)
                counts.record(outcome)
            self._ensure_reference(cls, identifier, self._repo.save_class)
            ids[identifier] = cls.id
            self._upsert_attributes(cls.id, spec.get("attributes", []))
        return ids

    def _update_class(
        self, existing: Class, spec: dict[str, Any], parent_id: str | None
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
        if existing.parent_class_id != parent_id:
            cls = self._service.move_class(existing.id, parent_id)
            outcome = "updated"
        return cls, outcome

    def _upsert_attributes(self, class_id: str, specs: list[dict[str, Any]]) -> None:
        counts = self.summary.kind("attribute")
        current = {
            a.identifier: a
            for a in self._service.list_attribute_definitions(class_id=class_id, limit=None)
        }
        for order, spec in enumerate(specs):
            wanted = {
                "title": spec["title"],
                "description": spec.get("description"),
                "datatype": spec["datatype"],
                "is_required": bool(spec.get("required", False)),
                "allowed_values": spec.get("allowed_values"),
                "sort_order": order,
            }
            existing = current.get(spec["identifier"])
            if existing is None:
                self._service.create_attribute_definition(
                    class_id=class_id, identifier=spec["identifier"], **wanted
                )
                counts.record("created")
                continue
            have = {
                "title": existing.title,
                "description": existing.description,
                "datatype": str(getattr(existing.datatype, "value", existing.datatype)),
                "is_required": existing.is_required,
                "allowed_values": existing.allowed_values,
                "sort_order": existing.sort_order,
            }
            if have == wanted:
                counts.record("unchanged")
            else:
                self._service.update_attribute_definition(existing.id, **wanted)
                counts.record("updated")

    # ----------------------------------------------------------- properties

    def _upsert_properties(
        self, class_ids: dict[str, str], specs: list[dict[str, Any]]
    ) -> dict[str, str]:
        counts = self.summary.kind("property")
        ids: dict[str, str] = {}
        for spec in specs:
            identifier = spec["identifier"]
            domain_id = self._class_ref(class_ids, spec.get("domain"), f"property {identifier}")
            range_id = self._class_ref(class_ids, spec.get("range"), f"property {identifier}")
            reference = self._reference(identifier, spec.get("constraints"))
            existing = self._repo.get_property_definition_by_identifier(identifier)
            if existing is not None and not self._owns(existing):
                raise BundleError(
                    f"Relationship type {identifier!r} already exists and was not loaded"
                    f" from {self._source!r}; prefix the bundle's identifiers"
                )
            if existing is None:
                prop = self._service.create_property_definition(
                    identifier=identifier,
                    title=spec["title"],
                    description=spec.get("description"),
                    canonical_predicate=spec.get("predicate"),
                    domain_class_id=domain_id,
                    range_class_id=range_id,
                    external_references=[reference],
                )
                counts.record("created")
            else:
                prop = self._update_property(existing, spec, domain_id, range_id, reference)
            ids[identifier] = prop.id
        return ids

    def _update_property(
        self,
        existing: PropertyDefinition,
        spec: dict[str, Any],
        domain_id: str | None,
        range_id: str | None,
        reference: ExternalReference,
    ) -> PropertyDefinition:
        counts = self.summary.kind("property")
        references = self._with_reference(existing.external_references, reference)
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
        self, taxonomy_id: str, class_ids: dict[str, str], specs: list[dict[str, Any]]
    ) -> dict[str, str]:
        counts = self.summary.kind("individual")
        existing_by_id = self._owned_individuals(taxonomy_id)
        ids: dict[str, str] = {}
        for spec in specs:
            bundle_id = spec["id"]
            wanted_classes = [
                self._class_ref(class_ids, name, f"individual {bundle_id}")
                for name in spec["classes"]
            ]
            reference = self._reference(bundle_id, spec.get("data"))
            existing = existing_by_id.get(bundle_id)
            if existing is None:
                individual = self._service.create_individual(
                    wanted_classes,
                    title=spec["title"],
                    description=spec.get("description"),
                    external_references=[reference],
                )
                counts.record("created")
            else:
                individual = self._update_individual(existing, spec, wanted_classes, reference)
            ids[bundle_id] = individual.id
        return ids

    def _update_individual(
        self,
        existing: Individual,
        spec: dict[str, Any],
        wanted_classes: list[str],
        reference: ExternalReference,
    ) -> Individual:
        counts = self.summary.kind("individual")
        references = self._with_reference(existing.external_references, reference)
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
        for class_id in list(existing.class_ids):
            if class_id not in wanted_classes:
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
        candidates: Iterable[Any] = (
            *self._taxonomy_classes(taxonomy_id),
            *self._repo.list_property_definitions(limit=None),
            *self._owned_individuals(taxonomy_id).values(),
        )
        self.summary.stale = stale_entities(candidates, self._source, loaded)

    # -------------------------------------------------------------- helpers

    def _reference(self, identifier: str, metadata: dict[str, Any] | None) -> ExternalReference:
        return ExternalReference(
            source=self._source,
            identifier=identifier,
            metadata=MappingProxyType(dict(metadata)) if metadata else None,
        )

    def _owns(self, entity: Any) -> bool:
        return any(ref.source == self._source for ref in entity.external_references)

    def _with_reference(
        self, references: list[ExternalReference], reference: ExternalReference
    ) -> list[ExternalReference]:
        """The references with this source's entry replaced by `reference`."""
        others = [r for r in references if r.source != self._source]
        return [*others, reference]

    def _ensure_reference(self, entity: Any, identifier: str, save: Callable[[Any], Any]) -> None:
        if any(
            r.source == self._source and r.identifier == identifier
            for r in entity.external_references
        ):
            return
        entity.external_references.append(
            ExternalReference(source=self._source, identifier=identifier)
        )
        save(entity)

    def _taxonomy_classes(self, taxonomy_id: str) -> list[Class]:
        return [
            cls
            for scheme in self._repo.list_concept_schemes(taxonomy_id=taxonomy_id, limit=None)
            for cls in self._repo.list_classes(concept_scheme_id=scheme.id, limit=None)
        ]

    def _owned_individuals(self, taxonomy_id: str) -> dict[str, Individual]:
        found: dict[str, Individual] = {}
        for cls in self._taxonomy_classes(taxonomy_id):
            for individual in self._repo.list_individuals(class_id=cls.id, limit=None):
                for ref in individual.external_references:
                    if ref.source == self._source:
                        found[ref.identifier] = individual
        return found

    def _require_in_taxonomy(
        self, entity: Any, kind: type, taxonomy_id: str, identifier: str
    ) -> None:
        if not isinstance(entity, kind) or entity.taxonomy_id != taxonomy_id:
            raise BundleError(
                f"Identifier {identifier!r} already belongs to another taxonomy or kind;"
                " identifiers are unique across the workspace, so prefix the bundle's"
                " identifiers"
            )

    @staticmethod
    def _class_ref(class_ids: dict[str, str], name: str | None, where: str) -> str | None:
        if name is None:
            return None
        if name not in class_ids:
            raise BundleError(f"{where} names unknown class {name!r}")
        return class_ids[name]


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
