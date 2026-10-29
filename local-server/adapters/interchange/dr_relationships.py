"""
Documentation Robotics (DR) relationship types in the workspace, and the rules
a change proposal's operations on them are under.

The DR spec is held as the `dr_spec` taxonomy (see
`scripts/dr_ontology_loader.py`): one class per spec node, and one property
definition per relationship schema, each keyed back to DR by an external
reference (source "documentation_robotics"; a class's identifier is its spec
node id, a property definition's the relationship id
"{source}.{predicate}.{destination}"). The loader, the reflection-plan importer
(`scripts/dr_reflection_plan.py`) and `DrRelationshipRules`, which ProposalService
applies to changes of DR relationship types, share what is here.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping

from domain.ontology.entities import PropertyDefinition
from domain.ontology.ports import OntologyRepository
from domain.ontology.value_objects import ExternalReference
from domain.versioning.proposals import ChangeProposal, OperationStatus, ProposedOperation

DR_SOURCE = "documentation_robotics"
DR_TAXONOMY_IDENTIFIER = "dr_spec"
# The dr_spec taxonomy's DR reference; its metadata holds the spec's predicate
# catalog ({"spec_version", "predicates": {id: {inverse, category, description}}}).
DR_SPEC_REFERENCE = "spec"

_IDENTIFIER_MAX_LENGTH = 64
_TRUNCATED_LENGTH = 59


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


def dr_property_definitions(repo: OntologyRepository) -> dict[str, PropertyDefinition]:
    """The workspace's property definitions by their DR relationship id (external reference)."""
    return {
        ref.identifier: prop
        for prop in repo.list_property_definitions(limit=None)
        for ref in prop.external_references
        if ref.source == DR_SOURCE
    }


def assign_relationship_identifiers(
    records: Iterable[RelationshipSchemaRecord],
    repo: OntologyRepository,
    owners: dict[str, str | None],
) -> dict[str, str]:
    """
    The identifier each relationship schema of a spec gets, as the loader assigns it.

    Like `compress_relationship_identifiers`, plus: a form held by an entity
    outside this spec's own property definitions (a non-DR or stale property
    definition, a taxonomy, scheme or class) falls back to the hashed form.
    The reflection-plan importer calls this on the spec a plan would produce,
    so the identifiers it proposes are the ones a re-import computes.

    Args:
        records: Every relationship schema of the spec
        repo: The workspace
        owners: Each record's full id -> the property definition that holds it
            (None for a schema with none yet)
    """
    own = {prop_id for prop_id in owners.values() if prop_id}

    def taken(identifier: str) -> bool:
        holder = repo.get_property_definition_by_identifier(identifier)
        if holder is not None:
            return holder.id not in own
        return repo.get_by_identifier(identifier) is not None

    return compress_relationship_identifiers(records, taken)


def compress_relationship_identifiers(
    records: Iterable[RelationshipSchemaRecord],
    is_taken: Callable[[str], bool] = lambda identifier: False,
) -> dict[str, str]:
    """
    Map each relationship record's full long-form id to a compressed identifier
    that is <=64 chars and globally unique across all records.

    Three independent reasons a compressed id needs the hash-suffix fallback:
    - the layer-stripped form alone exceeds 64 chars,
    - two distinct relationships (different source/destination layers) strip
      down to the identical short form (e.g. 'ux.view' and 'data-store.view'
      both stripping to 'view'), or
    - `is_taken` says something outside these records already holds the form.

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

    for full_id, compressed_id in compressed.items():
        if is_taken(compressed_id):
            compressed[full_id] = _hashed_relationship_identifier(by_full_id[full_id])
            if is_taken(compressed[full_id]):
                raise ValueError(
                    f"Relationship '{full_id}': identifiers '{compressed_id}' and "
                    f"'{compressed[full_id]}' are both held by other entities"
                )

    final_ids = list(compressed.values())
    if len(final_ids) != len(set(final_ids)):
        raise ValueError("Relationship identifier compression produced duplicate identifiers")
    too_long = [identifier for identifier in final_ids if len(identifier) > _IDENTIFIER_MAX_LENGTH]
    if too_long:
        raise ValueError(
            f"Relationship identifiers exceed {_IDENTIFIER_MAX_LENGTH} chars: {too_long}"
        )

    return compressed


@dataclass(frozen=True)
class Triple:
    """A DR relationship id split into its parts."""

    source: str
    predicate: str
    destination: str

    @classmethod
    def parse(cls, relationship_id: str) -> "Triple":
        """'api.operation.delivers.api.response' -> (api.operation, delivers, api.response)."""
        parts = relationship_id.split(".")
        if len(parts) != 5 or not all(parts):
            raise ValueError(
                f"'{relationship_id}' is not a {{source}}.{{predicate}}.{{destination}} id"
            )
        return cls(f"{parts[0]}.{parts[1]}", parts[2], f"{parts[3]}.{parts[4]}")

    @property
    def id(self) -> str:
        return f"{self.source}.{self.predicate}.{self.destination}"

    def record(self) -> RelationshipSchemaRecord:
        return RelationshipSchemaRecord(
            source_spec_node_id=self.source,
            source_layer=self.source.split(".")[0],
            destination_spec_node_id=self.destination,
            destination_layer=self.destination.split(".")[0],
            predicate=self.predicate,
            title=f"{self.source} {self.predicate} {self.destination}",
            description=None,
        )

    def fields(self) -> dict[str, str]:
        """The triple in DR's vocabulary, as DR's decisions file carries it."""
        return {
            "predicate": self.predicate,
            "source_spec_node_id": self.source,
            "destination_spec_node_id": self.destination,
        }


def dr_relationship_id(external_references: Iterable[Any]) -> str | None:
    """The DR relationship id among external references (objects or their dicts), if any."""
    for ref in external_references or []:
        source = ref.get("source") if isinstance(ref, dict) else getattr(ref, "source", None)
        identifier = (
            ref.get("identifier") if isinstance(ref, dict) else getattr(ref, "identifier", None)
        )
        if source == DR_SOURCE and isinstance(identifier, str):
            return identifier
    return None


def dr_spec_classes(repo: OntologyRepository) -> dict[str, str]:
    """
    The dr_spec taxonomy's classes: spec node id -> class id.

    Raises:
        ValueError: If the DR spec has not been imported
    """
    taxonomy = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    if taxonomy is None:
        raise ValueError(f"No '{DR_TAXONOMY_IDENTIFIER}' taxonomy; import the DR spec first")
    return {
        ref.identifier: cls.id
        for scheme in repo.list_concept_schemes(taxonomy_id=taxonomy.id, limit=None)
        for cls in repo.list_classes(concept_scheme_id=scheme.id, limit=None)
        for ref in cls.external_references
        if ref.source == DR_SOURCE
    }


def dr_predicate_catalog(repo: OntologyRepository) -> dict[str, dict[str, Any]] | None:
    """
    The DR predicate catalog the last spec import stored on the dr_spec
    taxonomy, by predicate id; None if no import stored one (an older import,
    or a spec without dist/base.json).
    """
    taxonomy = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    for ref in getattr(taxonomy, "external_references", None) or []:
        if ref.source == DR_SOURCE and ref.identifier == DR_SPEC_REFERENCE and ref.metadata:
            predicates = ref.metadata.get("predicates")
            if isinstance(predicates, dict) and predicates:
                return dict(predicates)
    return None


def swapped_dr_reference(
    target: PropertyDefinition, current: Triple, new: Triple
) -> list[dict[str, Any]]:
    """The target's external references with its DR id moved to the new triple, as dicts."""
    return [
        (
            ExternalReference(
                source=ref.source, identifier=new.id, uri=ref.uri, metadata=ref.metadata
            )
            if ref.source == DR_SOURCE and ref.identifier == current.id
            else ref
        ).to_dict()
        for ref in target.external_references
    ]


class DrRelationshipRules:
    """
    ProposalApplyRules for the DR spec's relationship types.

    They govern a property-definition operation whose target is a DR
    relationship type (it has a DR relationship id) or that would touch the
    DR spec: its fields bring a DR relationship id, or the target's or the
    new domain or range is a dr_spec class. That holds whichever proposal
    the operation is in. An edit of a governed target without a DR
    relationship id is refused.

    A reviewer edits a DR relationship type's triple in Context Studio fields:
    canonical_predicate (DR's predicate), domain_class_id and range_class_id
    (the classes of DR's source and destination spec nodes), plus title or
    description. Fields the edit leaves out keep the target's current values.
    The edit is refused, with the reason, unless both classes are imported DR
    spec classes, the predicate is in the spec's predicate catalog (stored on
    the dr_spec taxonomy at import; see `dr_predicate_catalog`), no other
    relationship type has the triple, and no other operation of the proposal
    (pending, failed, or edited in the same apply) produces it. The applied
    fields always carry the whole triple: the predicate and both classes, the
    identifier a re-import of the edited spec computes, and the DR external
    reference (whatever the edit gave for those two). A title still the
    default for the old triple follows the new one.
    """

    def __init__(self, repo: OntologyRepository) -> None:
        self._repo = repo

    def governs(self, operation: ProposedOperation, fields: dict[str, Any]) -> bool:
        target = (
            self._repo.get_property_definition(operation.target_id)
            if operation.target_id
            else None
        )
        if target is not None and dr_relationship_id(target.external_references):
            return True
        if dr_relationship_id(fields.get("external_references") or []):
            return True
        taxonomy = self._repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
        if taxonomy is None:
            return False
        class_ids = [fields.get("domain_class_id"), fields.get("range_class_id")]
        if target is not None:
            class_ids += [target.domain_class_id, target.range_class_id]
        for class_id in class_ids:
            cls = self._repo.get_class(class_id) if isinstance(class_id, str) else None
            if cls is not None and cls.taxonomy_id == taxonomy.id:
                return True
        return False

    def prepare(
        self,
        proposal: ChangeProposal,
        operation: ProposedOperation,
        fields: dict[str, Any],
        other_edits: Mapping[str, dict[str, Any]],
    ) -> dict[str, Any]:
        target = self._repo.get_property_definition(operation.target_id or "")
        if target is None:
            raise ValueError(f"No property definition {operation.target_id}")
        current = self._triple_of(target)
        catalog = dr_predicate_catalog(self._repo)
        if catalog is None:
            raise ValueError(
                "the DR spec was imported without its predicate catalog; re-import the "
                "DR spec to load it"
            )
        classes = dr_spec_classes(self._repo)
        spec_nodes = {class_id: node for node, class_id in classes.items()}
        properties = dr_property_definitions(self._repo)
        new = self._edited(fields, current, spec_nodes)

        if new.predicate not in catalog:
            raise ValueError(f"predicate '{new.predicate}' is not in the DR predicate catalog")
        holder = properties.get(new.id)
        if holder is not None and holder.id != target.id:
            raise ValueError(f"{new.id} already exists")
        for other in proposal.operations:
            if other.id != operation.id and self._produces(other, other_edits, spec_nodes) == new:
                raise ValueError(f"seq {other.seq} also produces {new.id}")

        completed = dict(fields)
        completed["canonical_predicate"] = new.predicate
        completed["domain_class_id"] = classes[new.source]
        completed["range_class_id"] = classes[new.destination]
        if new == current:
            completed["identifier"] = target.identifier
        else:
            completed["identifier"] = self._identifier(new, current, target, properties)
            if "title" not in fields and target.title == current.record().title:
                completed["title"] = new.record().title
        completed["external_references"] = swapped_dr_reference(target, current, new)
        return completed

    @staticmethod
    def _triple_of(prop: PropertyDefinition) -> Triple:
        relationship_id = dr_relationship_id(prop.external_references)
        if relationship_id is None:
            raise ValueError(f"{prop.identifier} has no DR relationship id")
        return Triple.parse(relationship_id)

    @staticmethod
    def _edited(fields: dict[str, Any], current: Triple, spec_nodes: dict[str, str]) -> Triple:
        """The triple the edit produces from the current one."""

        def node(name: str, fallback: str) -> str:
            if name not in fields:
                return fallback
            found = spec_nodes.get(fields[name]) if isinstance(fields[name], str) else None
            if found is None:
                raise ValueError(f"{name} {fields[name]!r} is not an imported DR spec class")
            return found

        predicate = fields.get("canonical_predicate", current.predicate)
        if not isinstance(predicate, str) or not predicate or "." in predicate:
            raise ValueError(f"predicate {predicate!r} is not a DR predicate")
        return Triple(
            node("domain_class_id", current.source),
            predicate,
            node("range_class_id", current.destination),
        )

    def _produces(
        self,
        operation: ProposedOperation,
        edits: Mapping[str, dict[str, Any]],
        spec_nodes: dict[str, str],
    ) -> Triple | None:
        """
        The triple another operation would produce if applied: its edit's, or
        its proposed one. Applied ones are already in the workspace and
        rejected ones never will be, so they produce none; nor does a delete.
        """
        if operation.status not in (OperationStatus.PENDING, OperationStatus.FAILED):
            return None
        try:
            if operation.id in edits:
                target = self._repo.get_property_definition(operation.target_id or "")
                if target is None:
                    return None
                return self._edited(edits[operation.id], self._triple_of(target), spec_nodes)
            relationship_id = dr_relationship_id(operation.fields.get("external_references"))
            return Triple.parse(relationship_id) if relationship_id else None
        except ValueError:
            return None  # an edit that is itself invalid fails on its own

    def _identifier(
        self,
        new: Triple,
        current: Triple,
        target: PropertyDefinition,
        properties: dict[str, PropertyDefinition],
    ) -> str:
        """The identifier a re-import computes for the new triple in place of the current one."""
        owners: dict[str, str | None] = {}
        for relationship_id, prop in properties.items():
            try:
                Triple.parse(relationship_id)
            except ValueError:
                continue
            owners[relationship_id] = prop.id
        owners.pop(current.id, None)
        owners[new.id] = target.id
        records = [Triple.parse(relationship_id).record() for relationship_id in owners]
        return assign_relationship_identifiers(records, self._repo, owners)[new.id]
