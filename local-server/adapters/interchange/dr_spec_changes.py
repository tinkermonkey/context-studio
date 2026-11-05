"""
A decided change proposal's DR relationship-type changes, for DR to write
into its spec.

Any proposal whose property-definition operations touch DR relationship types
(see `dr_relationships.py`), whether a reflection plan or one proposed over
MCP or in the app, exports as one `cs-dr-spec-changes/1` document:

    {"format": "cs-dr-spec-changes/1", "proposal_id", "title",
     "changes": [{
        "seq", "op_id", "op": "create" | "update" | "delete",
        "relationship_id",            # the type after the operation (a delete: the one removed)
        "previous_relationship_id",   # update only, when its triple changed
        "identifier",                 # Context Studio's identifier for the type
        "predicate", "source_spec_node_id", "destination_spec_node_id",
        "set": {"description"?, "cardinality"?, "strength"?, "evidence"?},
        "replacement_relationship_id" # delete only: the type the delete names as its
                                      # replacement, else the one its relationships moved to
     }],
     "skipped": [{"seq", "op_id", "why"}]}

`set` holds only the spec values the operation applied: for a create, every
one it gave; for an update, those that differ from what they replaced (a
description Context Studio generated for a changed triple is left out, as DR
writes its own). A key not in `set` stays as the spec has it. `evidence` is
the x-dr-evidence lines; null for cardinality or strength, or an empty
evidence list, means the operation removed it. Only applied operations
export; the rest are listed in `skipped` with why.

The triple comes from the domain and range classes' DR references (a "$ref"
to a class the proposal created resolves to that class) and the predicate,
and must agree with the type's DR relationship id. A relationship type
between DR spec classes without a DR reference can't land in DR's spec, so
the export refuses it rather than skip it.

What an update didn't set is read from the workspace as it is now, so export
and land proposals in the order they were applied: exported after a later
change to the same type, an older proposal's triple comes out wrong (DR's
writer then refuses it, as the file it names is gone).
"""

from __future__ import annotations

from typing import Any

from adapters.interchange.dr_relationships import (
    DR_ATTRIBUTE_KEYS,
    DR_SOURCE,
    Triple,
    dr_relationship_id,
)
from domain.ontology.ports import OntologyRepository
from domain.versioning.proposals import (
    ChangeProposal,
    OperationKind,
    OperationStatus,
    OperationType,
    ProposalStatus,
    ProposedOperation,
)

SPEC_CHANGES_FORMAT = "cs-dr-spec-changes/1"


def spec_changes_for(proposal: ChangeProposal, repo: OntologyRepository) -> dict[str, Any]:
    """
    The proposal's applied DR relationship-type changes as a `cs-dr-spec-changes/1` document.

    Raises:
        ValueError: If the proposal was reverted, or an applied operation's
            triple can't be resolved or disagrees with its DR relationship id
    """
    if proposal.status is ProposalStatus.REVERTED:
        raise ValueError(
            f"Change proposal {proposal.id} was reverted; its decisions no longer hold"
        )
    changes: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    # "$<ref>" -> the entity the proposal's create of that ref made.
    refs = {o.ref: o.result_entity_id for o in proposal.operations if o.ref}
    for operation in proposal.operations:
        why = _not_exported(operation)
        change = None if why else _change(operation, repo, refs)
        if change is None:
            skipped.append(
                {
                    "seq": operation.seq,
                    "op_id": operation.id,
                    "why": why or "not a DR relationship type",
                }
            )
        else:
            changes.append(change)
    return {
        "format": SPEC_CHANGES_FORMAT,
        "proposal_id": proposal.id,
        "title": proposal.title,
        "changes": changes,
        "skipped": skipped,
    }


def _not_exported(operation: ProposedOperation) -> str | None:
    if operation.kind is not OperationKind.PROPERTY:
        return f"a {operation.kind.value} operation, not a relationship type"
    if operation.status is not OperationStatus.APPLIED:
        return operation.status.value
    return None


def _change(
    operation: ProposedOperation, repo: OntologyRepository, refs: dict[str, str | None]
) -> dict[str, Any] | None:
    label = f"seq {operation.seq}"
    if operation.op is OperationType.CREATE:
        return _create(operation, repo, label, refs)
    if operation.op is OperationType.UPDATE or operation.applied_fields is not None:
        # An edited delete was applied as an update.
        return _update(operation, repo, label, refs)
    if operation.op is OperationType.DELETE:
        return _delete(operation, repo, label, refs)
    return None


def _create(
    operation: ProposedOperation,
    repo: OntologyRepository,
    label: str,
    refs: dict[str, str | None],
) -> dict | None:
    fields = operation.fields
    domain = _resolve_ref(fields.get("domain_class_id"), refs, label)
    range_ = _resolve_ref(fields.get("range_class_id"), refs, label)
    relationship_id = dr_relationship_id(fields.get("external_references") or [])
    if relationship_id is None:
        _refuse_if_dr_spec(repo, label, "created a relationship type", domain, range_)
        return None
    triple = _resolved(
        repo, label, relationship_id, fields.get("canonical_predicate"), domain, range_
    )
    values: dict[str, Any] = {}
    if fields.get("description") is not None:
        values["description"] = fields["description"]
    values.update(_attributes(fields.get("external_references")))
    return _entry(operation, "create", triple, fields.get("identifier"), values)


def _update(
    operation: ProposedOperation,
    repo: OntologyRepository,
    label: str,
    refs: dict[str, str | None],
) -> dict | None:
    applied = operation.applied_fields if operation.applied_fields is not None else operation.fields
    base = operation.base
    prop = repo.get_property_definition(operation.result_entity_id or operation.target_id or "")
    current = dict(
        external_references=[r.to_dict() for r in prop.external_references] if prop else [],
        canonical_predicate=prop.canonical_predicate if prop else None,
        domain_class_id=prop.domain_class_id if prop else None,
        range_class_id=prop.range_class_id if prop else None,
        identifier=prop.identifier if prop else None,
    )

    def value(name: str) -> Any:
        found = applied[name] if name in applied else current[name]
        return _resolve_ref(found, refs, label) if name.endswith("_class_id") else found

    relationship_id = dr_relationship_id(value("external_references") or [])
    previous_id = dr_relationship_id(base.get("external_references") or [])
    if relationship_id is None:
        if previous_id is not None:
            raise ValueError(
                f"{label}: it removed the DR reference of {previous_id}, so DR's spec can't "
                "follow; give the type its DR reference back, or delete the type instead"
            )
        if prop is None:
            raise ValueError(f"{label}: its relationship type no longer exists")
        _refuse_if_dr_spec(
            repo,
            label,
            "left a relationship type",
            value("domain_class_id"),
            value("range_class_id"),
        )
        return None
    previous = previous_id or relationship_id
    triple = _resolved(
        repo,
        label,
        relationship_id,
        value("canonical_predicate"),
        value("domain_class_id"),
        value("range_class_id"),
    )
    values: dict[str, Any] = {}
    description = applied.get("description")
    if (
        "description" in applied
        and description != base.get("description")
        and not (previous != triple.id and description == triple.default_description)
    ):
        values["description"] = description
    if "external_references" in applied:
        after = _attributes(applied["external_references"])
        before = _attributes(base["external_references"]) if "external_references" in base else None
        for key in DR_ATTRIBUTE_KEYS:
            if before is None:
                if key in after:
                    values[key] = after[key]
            elif after.get(key) != before.get(key):
                values[key] = after.get(key, [] if key == "evidence" else None)
    entry = _entry(operation, "update", triple, value("identifier"), values)
    if previous != triple.id:
        entry["previous_relationship_id"] = previous
    return entry


def _delete(
    operation: ProposedOperation,
    repo: OntologyRepository,
    label: str,
    refs: dict[str, str | None],
) -> dict | None:
    """
    A deleted type, with the type replacing it: the one the delete names
    (`proposed_replacement_id`, a "$ref" resolved to its applied create), else
    the one its relationships moved to (the resolution). The replacement is the
    type as the proposal left it (domain.versioning.in_use compares pairs the
    same way); DR keeps it for the model migration only when it links the same
    pair of types or the reverse. A named replacement whose create was not
    applied, or that is gone, falls back to the resolution's, if any.
    """
    base = operation.base
    relationship_id = dr_relationship_id(base.get("external_references") or [])
    if relationship_id is None:
        return None
    triple = Triple.parse(relationship_id)
    entry = _entry(operation, "delete", triple, base.get("identifier"), {})
    named = operation.proposed_replacement_id
    if named and named.startswith("$"):
        named = refs.get(named[1:])
    resolution = operation.resolution
    moved_to = resolution.replacement_property_id if resolution else None
    replacement_property_id = next(
        (
            candidate
            for candidate in (named, moved_to)
            if candidate and repo.get_property_definition(candidate) is not None
        ),
        None,
    )
    if replacement_property_id:
        replacement = repo.get_property_definition(replacement_property_id)
        replacement_id = (
            dr_relationship_id(replacement.external_references) if replacement else None
        )
        if replacement_id is None:
            raise ValueError(
                f"{label}: its replacement {replacement_property_id} is not a DR relationship type"
            )
        entry["replacement_relationship_id"] = replacement_id
    return entry


def _entry(
    operation: ProposedOperation, op: str, triple: Triple, identifier: Any, values: dict
) -> dict[str, Any]:
    return {
        "seq": operation.seq,
        "op_id": operation.id,
        "op": op,
        "relationship_id": triple.id,
        "identifier": identifier,
        "predicate": triple.predicate,
        "source_spec_node_id": triple.source,
        "destination_spec_node_id": triple.destination,
        "set": values,
    }


def _resolve_ref(value: Any, refs: dict[str, str | None], label: str) -> Any:
    """A "$<ref>" id field as the entity the proposal's create of that ref made."""
    if not (isinstance(value, str) and value.startswith("$") and len(value) > 1):
        return value
    entity_id = refs.get(value[1:])
    if entity_id is None:
        raise ValueError(f"{label}: {value} names no create of this proposal that was applied")
    return entity_id


def _refuse_if_dr_spec(repo: OntologyRepository, label: str, what: str, *class_ids: Any) -> None:
    """A type between DR spec classes without a DR reference is a spec change DR can't take."""
    for class_id in class_ids:
        cls = repo.get_class(class_id) if isinstance(class_id, str) else None
        if cls is not None and dr_relationship_id(cls.external_references) is not None:
            raise ValueError(
                f"{label}: it {what} on DR spec classes without a DR reference "
                f"(source {DR_SOURCE!r}), so it can't land in DR's spec; give it one"
            )


def _attributes(external_references: Any) -> dict[str, Any]:
    """The DR attributes on a DR reference (dicts), by DR_ATTRIBUTE_KEYS."""
    for ref in external_references or []:
        if isinstance(ref, dict) and ref.get("source") == DR_SOURCE:
            metadata = ref.get("metadata") or {}
            return {key: metadata[key] for key in DR_ATTRIBUTE_KEYS if key in metadata}
    return {}


def _resolved(
    repo: OntologyRepository,
    label: str,
    relationship_id: str,
    predicate: Any,
    domain_class_id: Any,
    range_class_id: Any,
) -> Triple:
    """The triple of the predicate and the classes' DR references; it must match the DR id."""
    triple = Triple(
        _spec_node(repo, label, "domain", domain_class_id),
        predicate if isinstance(predicate, str) else "",
        _spec_node(repo, label, "range", range_class_id),
    )
    if triple.id != relationship_id:
        raise ValueError(
            f"{label}: its predicate, domain and range give {triple.id}, but its DR "
            f"relationship id is {relationship_id}"
        )
    return triple


def _spec_node(repo: OntologyRepository, label: str, end: str, class_id: Any) -> str:
    cls = repo.get_class(class_id) if isinstance(class_id, str) else None
    node = dr_relationship_id(cls.external_references) if cls else None
    if node is None:
        raise ValueError(f"{label}: its {end} class {class_id!r} is not an imported DR spec class")
    return node
