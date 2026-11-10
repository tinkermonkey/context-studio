"""
What the splitter reads about a note's subject, and how the names it returns
map back to entities.

The context follows DR's split-notes.ts typeContext: the subject's current
schema (definition and attributes), its classes nearby, and the relationship
types it takes part in. Every entity is named by its Context Studio identifier
(its id when it has none), the names the splitter is asked to return in
affected_ids, so they resolve: a class, scheme, taxonomy or relationship type
by id or identifier, an attribute by id or "<class identifier>.<attribute
identifier>".
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Optional, Union

from domain.ontology.entities import (
    AttributeDefinition,
    Class,
    ConceptScheme,
    PropertyDefinition,
    Taxonomy,
)
from domain.ontology.ports import OntologyRepository
from domain.pipelines.refinement.neighborhood import SchemaNeighborhoodTraversal

Subject = Union[Taxonomy, ConceptScheme, Class, PropertyDefinition, AttributeDefinition]


def entity_name(entity: Union[Taxonomy, ConceptScheme, Class, PropertyDefinition]) -> str:
    """How the context names an entity: its identifier, else its id."""
    return entity.identifier or entity.id


class NoteContextRenderer:
    """Renders a note subject's context with Context Studio identifiers."""

    def __init__(self, repo: OntologyRepository, traversal: SchemaNeighborhoodTraversal) -> None:
        self._repo = repo
        self._traversal = traversal
        self._properties: Optional[list[PropertyDefinition]] = None

    def subject(self, subject_id: Optional[str]) -> Optional[Subject]:
        """The entity a resolved subject id names, if any."""
        if not subject_id:
            return None
        repo = self._repo
        return (
            repo.get_class(subject_id)
            or repo.get_property_definition(subject_id)
            or repo.get_attribute_definition(subject_id)
            or repo.get_concept_scheme(subject_id)
            or repo.get_taxonomy(subject_id)
        )

    def heading(self, subject: Optional[Subject], taxonomy: Taxonomy) -> str:
        """What the note is about, for the prompt's first line."""
        if isinstance(subject, Class):
            scheme = self._repo.get_concept_scheme(subject.concept_scheme_id)
            where = f" (scheme {entity_name(scheme)})" if scheme else ""
            return f"the class {entity_name(subject)}{where}"
        if isinstance(subject, PropertyDefinition):
            return f"the relationship type {entity_name(subject)}"
        if isinstance(subject, AttributeDefinition):
            return f"the attribute {self._attribute_name(subject)}"
        if isinstance(subject, ConceptScheme):
            return f"the scheme {entity_name(subject)}"
        return f"the {taxonomy.title} taxonomy"

    def render(self, subject: Optional[Subject], taxonomy: Taxonomy) -> str:
        """The context block: the subject as it stands and the names around it."""
        if isinstance(subject, Class):
            return self._class_context(subject)
        if isinstance(subject, AttributeDefinition):
            owner = self._repo.get_class(subject.class_id)
            return self._class_context(owner) if owner else "(the attribute's class is gone)"
        if isinstance(subject, PropertyDefinition):
            return self._property_context(subject)
        if isinstance(subject, ConceptScheme):
            return self._scheme_context(subject)
        return self._taxonomy_context(taxonomy)

    def _class_context(self, cls: Class) -> str:
        repo = self._repo
        neighborhood = self._traversal.get_class_neighborhood(cls.id)
        parts = [f"Current schema:\n{self._describe_class(cls)}"]
        if neighborhood.parent_class:
            parts.append(f"Parent class: {self._brief(neighborhood.parent_class)}")
        if neighborhood.child_classes:
            children = ", ".join(entity_name(c) for c in neighborhood.child_classes)
            parts.append(f"Subclasses: {children}")
        scheme = repo.get_concept_scheme(cls.concept_scheme_id)
        if scheme is not None:
            siblings = [
                entity_name(c)
                for c in repo.list_classes(concept_scheme_id=scheme.id, limit=None)
                if c.id != cls.id
            ]
            parts.append(f"Sibling classes in {entity_name(scheme)}: {', '.join(siblings)}")
        relationship_types = {p.id: p for p in neighborhood.property_definitions or []}
        for prop in self._all_properties():
            if cls.id in (prop.domain_class_id, prop.range_class_id):
                relationship_types.setdefault(prop.id, prop)
        lines = [f"  {self._edge(p)}" for p in relationship_types.values()]
        parts.append(f"Relationship types ({len(lines)}):" + "".join(f"\n{line}" for line in lines))
        return "\n".join(parts)

    def _property_context(self, prop: PropertyDefinition) -> str:
        neighborhood = self._traversal.get_property_neighborhood(prop.id)
        parts = [
            "Current relationship type:",
            f"{self._edge(prop)}: {prop.description or '(no description)'}",
        ]
        for label, side in (
            ("Domain", neighborhood.domain_neighborhood),
            ("Range", neighborhood.range_neighborhood),
        ):
            cls = self._repo.get_class(side.class_id) if side else None
            if cls is not None:
                parts.append(f"{label} class: {self._brief(cls)}")
        if neighborhood.sibling_properties:
            parts.append("Other relationship types from the domain class:")
            parts += [f"  {self._edge(p)}" for p in neighborhood.sibling_properties]
        return "\n".join(parts)

    def _scheme_context(self, scheme: ConceptScheme) -> str:
        classes = self._repo.list_classes(concept_scheme_id=scheme.id, limit=None)
        lines = [f"  {self._brief(c)}" for c in classes]
        return f"Scheme {entity_name(scheme)} ({scheme.title}), classes:\n" + "\n".join(lines)

    def _taxonomy_context(self, taxonomy: Taxonomy) -> str:
        schemes = self._repo.list_concept_schemes(taxonomy_id=taxonomy.id, limit=None)
        lines = [f"  {entity_name(s)} ({s.title})" for s in schemes]
        return (
            f"Taxonomy {taxonomy.title}: {taxonomy.description or '(no description)'}\n"
            "Schemes:\n" + "\n".join(lines)
        )

    def _describe_class(self, cls: Class) -> str:
        """DR's describeNodeForPrompt: the class, its definition and its attributes."""
        attributes = self._repo.list_attribute_definitions(class_id=cls.id, limit=None)
        lines = [
            f"  - {a.identifier}{' (required)' if a.is_required else ''}:"
            f" {getattr(a.datatype, 'value', a.datatype)}"
            f"{' enum[' + '|'.join(a.allowed_values) + ']' if a.allowed_values else ''}"
            f"{' — ' + a.description if a.description else ''}"
            for a in attributes
        ]
        head = f"{entity_name(cls)} ({cls.title}): {cls.description or '(no description)'}"
        return head + "\n" + ("\n".join(lines) or "  (no attributes)")

    def _brief(self, cls: Class) -> str:
        return f"{entity_name(cls)} ({cls.title})"

    def _edge(self, prop: PropertyDefinition) -> str:
        """A relationship type as "<identifier>: <domain> --[<predicate>]--> <range>"."""
        domain = self._class_name(prop.domain_class_id)
        range_ = self._class_name(prop.range_class_id)
        predicate = prop.canonical_predicate or prop.title
        return f"{entity_name(prop)}: {domain} --[{predicate}]--> {range_}"

    def _class_name(self, class_id: Optional[str]) -> str:
        cls = self._repo.get_class(class_id) if class_id else None
        return entity_name(cls) if cls else "(any)"

    def _attribute_name(self, attribute: AttributeDefinition) -> str:
        return f"{self._class_name(attribute.class_id)}.{attribute.identifier}"

    def _all_properties(self) -> list[PropertyDefinition]:
        """Every relationship type, read once per run, to find a class's incoming ones."""
        if self._properties is None:
            self._properties = self._repo.list_property_definitions(limit=None)
        return self._properties


class EntityRefResolver:
    """
    Maps the names a split returns to the taxonomy's entity ids: an id, an
    identifier (taxonomy, scheme, class or relationship type), or
    "<class id or identifier>.<attribute identifier>". A name that matches
    nothing, or an entity outside the taxonomy, resolves to None.
    """

    def __init__(
        self, repo: OntologyRepository, in_taxonomy: Callable[[set[str]], set[str]]
    ) -> None:
        """
        Args:
            repo: The ontology
            in_taxonomy: Ids -> those a claim of the taxonomy may name
                (ClaimService.in_taxonomy for the run's taxonomy)
        """
        self._repo = repo
        self._in_taxonomy = in_taxonomy
        self._resolved: dict[str, Optional[str]] = {}

    def resolve(self, ref: str) -> Optional[str]:
        ref = ref.strip()
        if ref not in self._resolved:
            entity_id = self._candidate(ref) if ref else None
            if entity_id is not None and not self._in_taxonomy({entity_id}):
                entity_id = None
            self._resolved[ref] = entity_id
        return self._resolved[ref]

    def _candidate(self, ref: str) -> Optional[str]:
        repo = self._repo
        if (
            repo.get_class(ref)
            or repo.get_property_definition(ref)
            or repo.get_attribute_definition(ref)
            or repo.get_concept_scheme(ref)
            or repo.get_taxonomy(ref)
        ):
            return ref
        entity = repo.get_by_identifier(ref) or repo.get_property_definition_by_identifier(ref)
        if entity is not None:
            return entity.id
        owner, _, name = ref.rpartition(".")
        class_id = self._class_id(owner) if owner and name else None
        if class_id is None:
            return None
        return next(
            (
                a.id
                for a in repo.list_attribute_definitions(class_id=class_id, limit=None)
                if a.identifier == name
            ),
            None,
        )

    def _class_id(self, ref: str) -> Optional[str]:
        if self._repo.get_class(ref) is not None:
            return ref
        entity = self._repo.get_by_identifier(ref)
        return entity.id if isinstance(entity, Class) else None
