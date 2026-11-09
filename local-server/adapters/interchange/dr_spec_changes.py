"""
A decided change proposal's DR relationship-type changes, for DR to write
into its spec.

Any proposal whose property-definition operations touch DR relationship types
(see `dr_relationships.py`), whether a reflection plan or one proposed over
MCP or in the app, exports as one `cs-dr-spec-changes/1` document:

    {"format": "cs-dr-spec-changes/1", "proposal_id", "title",
     "source_revision": {"repo", "commit", "spec_version"} | null,
                                      # the spec revision the proposal was drafted against
     "landed": {"repo", "commit", "spec_version", "landed_at"} | null,
                                      # set once DR marked it landed
     "changes": [{
        "seq", "op_id", "op": "create" | "update" | "delete",
        "relationship_id",            # the type after the operation (a delete: the one removed)
        "previous_relationship_id",   # update only, when its triple changed
        "identifier",                 # Context Studio's identifier for the type
        "predicate", "source_spec_node_id", "destination_spec_node_id",
        "set": {"description"?, "cardinality"?, "strength"?, "evidence"?},
        "replacement_relationship_id" # delete only: the type the delete names as its
                                      # replacement, else the one its relationships moved to
                                      # (followed through the proposal's other deletes)
        "note",                       # delete only, when that chain is a cycle
        "decided_at", "decided_by"    # the operation's recorded decision (null if none)
     }],
     "skipped": [{"seq", "op_id", "why"}],
     "records": [{                    # the schema change records, as DR's change-record actions
        "action": "rename" | "delete" | "create",
        "kind": "cs:rename" | "cs:reverse" | "cs:retarget" | "cs:delete" | "cs:create",
        "from", "to",                 # DR relationship ids; to is null for a dropped delete
        "swap", "p", "proposal_id", "operation_id", "applied_at",
        "note"?                       # why a delete or retarget drops relationships
     }]}

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

`records` are the proposal's schema change records
(`domain.versioning.change_records`) keyed by DR relationship id, in the
action vocabulary of DR's `applied-*.json` change records, which DR's
generate-relationship-migration.ts composes for `dr upgrade`: a reverse is a
rename of kind cs:reverse (its relationships swap ends); a retarget, whose
new triple the generator can't migrate to, is a delete of the old triple
plus a create of the new: the delete's `to` is the type its resolution moved
the relationships to (null when it deleted them, or none used it). A delete
keeps its `to` only when that type links the same pair of spec nodes or the
reverse. They are read from what each operation recorded as it applied, so
they hold for a forced apply too. For an unedited proposal they match the
actions DR's cs-decisions-to-spec.ts derives from `changes`, except that a
chain of replaced deletes is left for the generator to fold, and a
retarget's resolution (which `changes` doesn't carry) is kept.

What an update didn't set is read from the workspace as it is now, so export
and land proposals in the order they were applied: exported after a later
change to the same type, an older proposal's triple comes out wrong (DR's
writer then refuses it, as the file it names is gone).
"""

from __future__ import annotations

from typing import Any, Mapping

from adapters.interchange.dr_decisions import decided_fields
from adapters.interchange.dr_relationships import (
    DR_ATTRIBUTE_KEYS,
    DR_SOURCE,
    Triple,
    dr_relationship_id,
)
from domain.ontology.ports import OntologyRepository
from domain.versioning.change_records import (
    SchemaChangeAction,
    SchemaChangeRecord,
    schema_change_records,
)
from domain.versioning.gold import ProposalDecision
from domain.versioning.proposals import (
    ChangeProposal,
    OperationKind,
    OperationStatus,
    OperationType,
    ProposalStatus,
    ProposedOperation,
)

SPEC_CHANGES_FORMAT = "cs-dr-spec-changes/1"


def spec_changes_for(
    proposal: ChangeProposal,
    repo: OntologyRepository,
    decisions: Mapping[str, ProposalDecision] | None = None,
) -> dict[str, Any]:
    """
    The proposal's applied DR relationship-type changes as a `cs-dr-spec-changes/1` document.

    Args:
        decisions: Operation id -> its recorded decision, for each change's
            decided_at and decided_by

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
    # The relationship types this proposal deleted, by id -> the delete.
    deletes = {
        o.target_id: o
        for o in proposal.operations
        if o.kind is OperationKind.PROPERTY
        and o.op is OperationType.DELETE
        and o.status is OperationStatus.APPLIED
        and o.applied_fields is None
        and o.target_id
    }
    for operation in proposal.operations:
        why = _not_exported(operation)
        change = None if why else _change(operation, repo, refs, deletes)
        if change is None:
            skipped.append(
                {
                    "seq": operation.seq,
                    "op_id": operation.id,
                    "why": why or "not a DR relationship type",
                }
            )
        else:
            change.update(decided_fields((decisions or {}).get(operation.id)))
            changes.append(change)
    return {
        "format": SPEC_CHANGES_FORMAT,
        "proposal_id": proposal.id,
        "title": proposal.title,
        "source_revision": proposal.source_revision.to_dict() if proposal.source_revision else None,
        "landed": proposal.landed.to_dict() if proposal.landed else None,
        "changes": changes,
        "skipped": skipped,
        "records": dr_change_actions(proposal, repo, decisions),
    }


def dr_change_actions(
    proposal: ChangeProposal,
    repo: OntologyRepository,
    decisions: Mapping[str, ProposalDecision] | None = None,
) -> list[dict[str, Any]]:
    """The schema change records on DR relationship types, as DR's change-record actions."""
    records = schema_change_records(
        proposal,
        decisions,
        key=lambda fields: dr_relationship_id(fields.get("external_references") or []),
    )
    return [action for record in records for action in _dr_actions(record)]


def _dr_actions(record: SchemaChangeRecord) -> list[dict[str, Any]]:
    """
    One record as DR actions. A retarget is a delete of the old triple, whose
    model relationships go where the retarget's resolution moved them (null
    when it deleted them, or there were none), plus a create of the new one.
    """
    shared = {
        k: v for k, v in record.to_json().items() if k not in ("action", "from", "to", "moved_to")
    }

    def action(name: str, from_: str, to: str | None, swap: bool, note: str | None = None):
        found = {
            "action": name,
            "kind": f"cs:{record.action.value}",
            "from": from_,
            "to": to,
            **shared,
            "swap": swap,
        }
        if note:
            found["note"] = note
        return found

    def delete(to: str | None, swap: bool, why: str) -> dict[str, Any]:
        if to is not None and _pair_of(record.from_, to) == "different":
            note = (
                f"{why} {to}, a different element pair, which a migration cannot apply "
                "mechanically, so model relationships of this triple are dropped"
            )
            return action("delete", record.from_, None, False, note)
        return action("delete", record.from_, to, swap if to else False)

    if record.action is SchemaChangeAction.CREATE:
        return [action("create", record.from_, record.to, False)]
    if record.action in (SchemaChangeAction.RENAME, SchemaChangeAction.REVERSE):
        return [action("rename", record.from_, record.to, record.swap)]
    if record.action is SchemaChangeAction.DELETE:
        return [delete(record.to, record.swap, "replaced by")]
    retargeted = record.to or record.from_
    return [
        delete(record.moved_to, record.swap, "its relationships moved to"),
        action("create", retargeted, retargeted, False, f"retarget of {record.from_}"),
    ]


def _pair_of(old: str, new: str) -> str:
    """Same, reversed or different pair of spec nodes, as DR's lib/triples.ts pairOf."""
    a, b = Triple.parse(old), Triple.parse(new)
    if (a.source, a.destination) == (b.source, b.destination):
        return "same"
    if (a.source, a.destination) == (b.destination, b.source):
        return "reversed"
    return "different"


def _not_exported(operation: ProposedOperation) -> str | None:
    if operation.kind is not OperationKind.PROPERTY:
        return f"a {operation.kind.value} operation, not a relationship type"
    if operation.status is not OperationStatus.APPLIED:
        return operation.status.value
    return None


def _change(
    operation: ProposedOperation,
    repo: OntologyRepository,
    refs: dict[str, str | None],
    deletes: dict[str, ProposedOperation],
) -> dict[str, Any] | None:
    label = f"seq {operation.seq}"
    if operation.op is OperationType.CREATE:
        return _create(operation, repo, label, refs)
    if operation.op is OperationType.UPDATE or operation.applied_fields is not None:
        # An edited delete was applied as an update.
        return _update(operation, repo, label, refs)
    if operation.op is OperationType.DELETE:
        return _delete(operation, repo, label, refs, deletes)
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
    deletes: dict[str, ProposedOperation],
) -> dict | None:
    """
    A deleted type, with the type replacing it: the one the delete names
    (`proposed_replacement_id`, a "$ref" resolved to its applied create), else
    the one its relationships moved to (the resolution). The replacement is the
    type as the proposal left it (domain.versioning.in_use compares pairs the
    same way); DR keeps it for the model migration only when it links the same
    pair of types or the reverse. A named replacement whose create was not
    applied, or that is gone, falls back to the resolution's, if any.

    A replacement this proposal also deleted is followed through that delete's
    own replacement, as the review showed it (ProposalService's replacement
    chain), to a type that still stands: A replaced by B, B by C exports C for
    A. A chain that comes back round leaves no replacement, with a note.
    """
    base = operation.base
    relationship_id = dr_relationship_id(base.get("external_references") or [])
    if relationship_id is None:
        return None
    triple = Triple.parse(relationship_id)
    entry = _entry(operation, "delete", triple, base.get("identifier"), {})
    replacement_property_id, cycle = _final_replacement(operation, repo, refs, deletes)
    if cycle:
        entry["note"] = (
            "its replacement chain comes back round to a type this proposal deletes, so no "
            "type survives to replace it"
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


def _final_replacement(
    operation: ProposedOperation,
    repo: OntologyRepository,
    refs: dict[str, str | None],
    deletes: dict[str, ProposedOperation],
) -> tuple[str | None, bool]:
    """
    The type that ends up replacing a delete's target, and whether its chain is a
    cycle: each delete's named replacement, else its resolution's, followed
    through the proposal's other deletes to one that still exists.
    """
    seen = {operation.target_id}
    current = operation
    while True:
        named = current.proposed_replacement_id
        if named and named.startswith("$"):
            named = refs.get(named[1:])
        moved_to = current.resolution.replacement_property_id if current.resolution else None
        candidate = next(
            (
                c
                for c in (named, moved_to)
                if c and (c in deletes or repo.get_property_definition(c) is not None)
            ),
            None,
        )
        if candidate is None:
            return None, False
        if candidate not in deletes:
            return candidate, False
        if candidate in seen:
            return None, True
        seen.add(candidate)
        current = deletes[candidate]


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
