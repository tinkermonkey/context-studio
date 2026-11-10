"""
A decided change proposal's DR relationship-type, node-type and attribute
changes, for DR to write into its spec.

Any proposal whose property-definition, class or attribute definition
operations touch the DR spec
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
     "node_changes": [{               # class operations on DR node types
        "seq", "op_id", "op": "create" | "update" | "move" | "delete",
        "spec_node_id",               # "{layer}.{type}" after it (a delete: the one removed)
        "previous_spec_node_id",      # move only: the id before it
        "layer_id",                   # spec_node_id's layer
        "identifier",                 # Context Studio's identifier for the class
        "set": {"title"?, "description"?},
        "replacement_spec_node_id",   # delete only: the class the delete names as its
                                      # replacement (followed through the proposal's other deletes)
        "note",                       # delete only, when that chain is a cycle
        "decided_at", "decided_by"
     }],
     "attribute_changes": [{          # attribute definition operations on DR node types
        "seq", "op_id", "op": "create" | "update" | "delete",
        "spec_node_id",               # the node type the attribute is on
        "attribute",                  # its DR name (its DR reference's identifier)
        "identifier",                 # Context Studio's identifier for it
        "set": {"datatype"?, "is_required"?, "allowed_values"?, "description"?},
        "schema",                     # create only, when any: its other JSON Schema keywords
        "decided_at", "decided_by"
     }],
     "predicate_changes": [{          # predicate creates and updates in the dr_spec catalog
        "seq", "op_id", "op": "create" | "update",
        "predicate",                  # the predicate's identifier
        "set": {"description"?, "inverse"?, "category"?, "archimate_alignment"?,
                "semantics"?},        # a create: all of them (archimate_alignment null
                                      # when not given); an update: only those it
                                      # changed, semantics only the changed flags
        "decided_at", "decided_by"
     }],
     "skipped": [{"seq", "op_id", "why"}  # an operation not exported
                 | {"seq": null, "op_id": null, "retire_predicate", "why",
                    "relationship_ids"}],  # a retirement types still use
     "records": [{                    # the schema change records, as DR's change-record actions
        "action": "rename" | "delete" | "create" | "rename-type" | "retire-predicate",
        "kind": "cs:rename" | "cs:reverse" | "cs:retarget" | "cs:delete" | "cs:create"
                | "cs:move" | "cs:retire-predicate",
        "from", "to",                 # DR relationship ids (rename-type: spec node ids;
                                      # retire-predicate: predicates);
                                      # to is null for a dropped delete
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

A class is a DR node type when its scheme is a layer of the dr_spec taxonomy
(the layer its DR classes' spec node ids share). Its DR reference's
identifier is its spec node id, which a create must give, in its scheme's
layer, and an update may not change. A move to another scheme moves it to
that layer: the type is kept, so "motivation.capability" moved to the
business scheme becomes "business.capability". A move of the parent class
only is skipped (DR's spec has no class hierarchy), as is an update of
nothing but the color. A move, and a delete with a replacement, also give
a `rename-type` record, so `dr upgrade` moves model elements of the old type
to the new one. Until DR's spec with a move is re-imported, the moved class
keeps its old DR id; the importer refuses a spec with a moved node type,
as it can't follow one yet.

An attribute's `set` holds the attribute definition's datatype (the JSON
Schema type), is_required (whether the node's required list names it),
allowed_values (its enum) and description. A create gives all it set, and
`schema`, the other JSON Schema keywords its DR reference keeps (metadata
"schema"; see the importer). An update gives only those it changed,
allowed_values null when it removed them; one that changed none of them (a
title, default value or order) is skipped. A date attribute is a JSON Schema
string with format date: a create sends datatype "string" and `schema`
format "date" (the importer reads that back as a date); an update to or
from a date is skipped, as `set` can't carry format.

A predicate delete in the dr_spec catalog retires the predicate into the
replacement it names: an applied one comes back as a `retire-predicate`
record {from, to} (its rationale as note), as #1440 agreed with DR. It applies
only once no relationship type uses the predicate (DR's relationship ids
embed it, so the proposal deletes or renames them first); one not applied
that DR relationship types still use is listed in `skipped` with their ids. A
DR reflection plan's `predicate_retirements` arrive as such deletes.

What an update didn't set is read from the workspace as it is now, so export
and land proposals in the order they were applied: exported after a later
change to the same type, an older proposal's triple comes out wrong (DR's
writer then refuses it, as the file it names is gone).
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Callable, Mapping

from adapters.interchange.dr_decisions import decided_fields
from adapters.interchange.dr_predicates import dr_predicate_metadata
from adapters.interchange.dr_relationships import (
    DR_ATTRIBUTE_KEYS,
    DR_ATTRIBUTE_SCHEMA,
    DR_SOURCE,
    DR_TAXONOMY_IDENTIFIER,
    Triple,
    dr_property_definitions,
    dr_relationship_id,
)
from domain.ontology.ports import OntologyRepository
from domain.ontology.value_objects import DataType
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
_EXPORTED_KINDS = (
    OperationKind.PROPERTY,
    OperationKind.CLASS,
    OperationKind.ATTRIBUTE,
    OperationKind.PREDICATE,
)
# The attribute definition fields an attribute change carries in `set`.
_ATTRIBUTE_FIELDS = ("datatype", "is_required", "allowed_values", "description")
# DR's JSON Schema writes a date attribute as a string with format date.
_DR_DATE = ("string", "date")


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
    node_changes: list[dict[str, Any]] = []
    attribute_changes: list[dict[str, Any]] = []
    predicate_changes: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    dr_taxonomy = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    dr_taxonomy_id = dr_taxonomy.id if dr_taxonomy else None
    # "$<ref>" -> the entity the proposal's create of that ref made.
    refs = {o.ref: o.result_entity_id for o in proposal.operations if o.ref}
    # The relationship types and classes this proposal deleted, by id -> the delete.
    deletes = _applied_deletes(proposal, OperationKind.PROPERTY)
    class_deletes = _applied_deletes(proposal, OperationKind.CLASS)
    layers = _dr_layers(repo)
    for operation in proposal.operations:
        if operation.kind is OperationKind.PREDICATE and operation.op is OperationType.DELETE:
            continue  # a retirement: see _retirements
        why = _not_exported(operation)
        change = None
        if why is None and operation.kind is OperationKind.PREDICATE:
            found = _predicate_change(operation, repo, dr_taxonomy_id)
            found_in, change = predicate_changes, found if isinstance(found, dict) else None
            why = found if isinstance(found, str) else None
        elif why is None and operation.kind is OperationKind.PROPERTY:
            change, found_in = _change(operation, repo, refs, deletes), changes
            why = None if change else "not a DR relationship type"
        elif why is None:
            if operation.kind is OperationKind.CLASS:
                found = _node_change(operation, repo, refs, class_deletes, layers)
                found_in, what = node_changes, "not a DR node type"
            else:
                found = _attribute_change(operation, repo, refs, class_deletes)
                found_in, what = attribute_changes, "not an attribute of a DR node type"
            change = found if isinstance(found, dict) else None
            why = found if isinstance(found, str) else None if change else what
        if change is None:
            skipped.append({"seq": operation.seq, "op_id": operation.id, "why": why})
        else:
            change.update(decided_fields((decisions or {}).get(operation.id)))
            found_in.append(change)  # type: ignore[union-attr]
    retirements, unretired = _retirements(proposal, repo, decisions)
    return {
        "format": SPEC_CHANGES_FORMAT,
        "proposal_id": proposal.id,
        "title": proposal.title,
        "source_revision": proposal.source_revision.to_dict() if proposal.source_revision else None,
        "landed": proposal.landed.to_dict() if proposal.landed else None,
        "changes": changes,
        "node_changes": node_changes,
        "attribute_changes": attribute_changes,
        "predicate_changes": predicate_changes,
        "skipped": [*skipped, *unretired],
        "records": [
            *dr_change_actions(proposal, repo, decisions),
            *_node_actions(proposal, node_changes, decisions),
            *retirements,
        ],
    }


def _applied_deletes(proposal: ChangeProposal, kind: OperationKind) -> dict[str, ProposedOperation]:
    """The entities of a kind this proposal deleted (applied as proposed), by id -> the delete."""
    return {
        o.target_id: o
        for o in proposal.operations
        if o.kind is kind
        and o.op is OperationType.DELETE
        and o.status is OperationStatus.APPLIED
        and o.applied_fields is None
        and o.target_id
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
    if operation.kind not in _EXPORTED_KINDS:
        return f"a {operation.kind.value} operation, which DR's spec doesn't hold"
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
    replacement_property_id, cycle = _final_replacement(
        operation, repo.get_property_definition, refs, deletes
    )
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
    exists: Callable[[str], Any],
    refs: dict[str, str | None],
    deletes: dict[str, ProposedOperation],
) -> tuple[str | None, bool]:
    """
    The entity that ends up replacing a delete's target, and whether its chain
    is a cycle: each delete's named replacement, else its resolution's (a
    relationship type's), followed through the proposal's other deletes of
    the same kind to one that still exists.
    """
    seen = {operation.target_id}
    current = operation
    while True:
        named = current.proposed_replacement_id
        if named and named.startswith("$"):
            named = refs.get(named[1:])
        moved_to = current.resolution.replacement_property_id if current.resolution else None
        candidate = next(
            (c for c in (named, moved_to) if c and (c in deletes or exists(c) is not None)),
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


# --------------------------------------------------------------- predicates


def _retirements(
    proposal: ChangeProposal,
    repo: OntologyRepository,
    decisions: Mapping[str, ProposalDecision] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    The proposal's DR predicate deletes (each names its replacement) as DR's
    `retire-predicate` records, and the ones skipped. A retirement holds only
    once no DR relationship type uses the retired predicate: an applied delete
    holds (it applies only once none does). One not applied that types still
    use, judged against the workspace as it is now, is skipped with the ids of
    those types; one not applied for another reason is skipped with its status.
    """
    records: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    deletes = [
        o
        for o in proposal.operations
        if o.kind is OperationKind.PREDICATE
        and o.op is OperationType.DELETE
        and o.base.get("identifier")
        and _is_dr_predicate_base(o.base, repo)
    ]
    if not deletes:
        return records, skipped
    using: dict[str, list[str]] = {}
    for relationship_id, prop in dr_property_definitions(repo).items():
        if prop.canonical_predicate:
            using.setdefault(prop.canonical_predicate, []).append(relationship_id)
    refs = {o.ref: o.result_entity_id for o in proposal.operations if o.ref}
    for operation in deletes:
        retired = operation.base["identifier"]
        into = _replacement_identifier(operation, repo, refs)
        if operation.status is not OperationStatus.APPLIED:
            still = sorted(using.get(retired, []))
            if not still:
                skipped.append(
                    {"seq": operation.seq, "op_id": operation.id, "why": operation.status.value}
                )
                continue
            count = (
                "a relationship type still uses it"
                if len(still) == 1
                else f"{len(still)} relationship types still use it"
            )
            skipped.append(
                {
                    "seq": None,
                    "op_id": None,
                    "retire_predicate": retired,
                    "why": f"retiring {retired} into {into}: {count}",
                    "relationship_ids": still,
                }
            )
            continue
        decision = (decisions or {}).get(operation.id)
        record = {
            "action": "retire-predicate",
            "kind": "cs:retire-predicate",
            "from": retired,
            "to": into,
            "p": operation.probability if operation.probability is not None else 1.0,
            "proposal_id": proposal.id,
            "operation_id": operation.id,
            "applied_at": decision.decided_at.isoformat() if decision else None,
        }
        if operation.rationale:
            record["note"] = operation.rationale
        records.append(record)
    return records, skipped


def _is_dr_predicate_base(base: dict[str, Any], repo: OntologyRepository) -> bool:
    """Whether a deleted predicate (its snapshot) was in the dr_spec taxonomy's catalog."""
    taxonomy = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    return taxonomy is not None and base.get("taxonomy_id") == taxonomy.id


def _replacement_identifier(
    operation: ProposedOperation, repo: OntologyRepository, refs: dict[str, str | None]
) -> str | None:
    """The identifier of the predicate a predicate delete names as its replacement."""
    named = operation.proposed_replacement_id
    if named and named.startswith("$"):
        named = refs.get(named[1:])
    predicate = repo.get_predicate(named) if named else None
    return predicate.identifier if predicate else None


# --------------------------------------------------------------- predicates


def _predicate_change(
    operation: ProposedOperation, repo: OntologyRepository, dr_taxonomy_id: str | None
) -> dict[str, Any] | str:
    """
    An applied create or update of a dr_spec predicate as a `predicate_changes`
    entry, or why it isn't one. A create's `set` holds description, inverse,
    category, archimate_alignment (null when not given) and all four semantics;
    an update's holds only the keys it changed (semantics only the changed flags).
    """
    label = f"seq {operation.seq}"
    predicate_id = (
        operation.result_entity_id
        if operation.op is OperationType.CREATE
        else operation.target_id
    )
    predicate = repo.get_predicate(predicate_id or "")
    if predicate is None:
        raise ValueError(f"{label}: its predicate no longer exists")
    if predicate.taxonomy_id != dr_taxonomy_id:
        return "not a DR predicate"
    fields = operation.fields
    after = dr_predicate_metadata(fields.get("external_references"))
    if operation.op is OperationType.CREATE:
        if after is None:
            raise ValueError(
                f"{label}: it creates the DR predicate {predicate.identifier} without a DR"
                f" reference (source {DR_SOURCE!r}) carrying inverse, category and"
                " semantics, so it can't land in DR's predicates.json; give it one"
            )
        values: dict[str, Any] = {
            "description": fields.get("description"),
            "inverse": after.get("inverse"),
            "category": after.get("category"),
            "archimate_alignment": after.get("archimate_alignment"),
            "semantics": after.get("semantics"),
        }
    else:
        values = {}
        if "description" in fields and fields["description"] != operation.base.get("description"):
            values["description"] = fields["description"]
        if after is not None:
            before = dr_predicate_metadata(operation.base.get("external_references")) or {}
            for key in ("inverse", "category", "archimate_alignment"):
                if key in after and after[key] != before.get(key):
                    values[key] = after[key]
            semantics = {
                flag: value
                for flag, value in (after.get("semantics") or {}).items()
                if value != (before.get("semantics") or {}).get(flag)
            }
            if semantics:
                values["semantics"] = semantics
        if not values:
            return "it changes nothing DR's predicates.json holds"
    return {
        "seq": operation.seq,
        "op_id": operation.id,
        "op": operation.op.value,
        "predicate": predicate.identifier,
        "set": values,
    }


# --------------------------------------------------------------- attributes


def _attribute_change(
    operation: ProposedOperation,
    repo: OntologyRepository,
    refs: dict[str, str | None],
    class_deletes: dict[str, ProposedOperation],
) -> dict[str, Any] | str | None:
    """
    An applied attribute definition operation as a change of a DR node type's
    attribute, keyed by the node's spec node id and the attribute's DR name
    (its DR reference's identifier). `set` holds the definition's datatype,
    is_required, allowed_values and description: all a create gave, the ones
    an update changed (allowed_values null removes them). A create also
    gives `schema`, the other JSON Schema keywords its DR reference keeps.
    """
    label = f"seq {operation.seq}"
    if operation.op is OperationType.CREATE:
        fields = operation.fields
        class_id = _resolve_ref(fields.get("class_id"), refs, label)
        references = fields.get("external_references") or []
        identifier = fields.get("identifier")
    elif operation.op is OperationType.UPDATE:
        attribute = repo.get_attribute_definition(operation.target_id or "")
        if attribute is None:
            raise ValueError(f"{label}: its attribute definition no longer exists")
        class_id, identifier = attribute.class_id, attribute.identifier
        references = [r.to_dict() for r in attribute.external_references]
    else:
        base = operation.base
        class_id, identifier = base.get("class_id"), base.get("identifier")
        references = base.get("external_references") or []
    node_id = _node_id_of(repo, class_id, class_deletes)
    if node_id is None:
        return None
    name = dr_relationship_id(references)
    if name is None:
        raise ValueError(
            f"{label}: it {operation.op.value}s an attribute of the DR node type {node_id} "
            f"without a DR reference (source {DR_SOURCE!r}, identifier the DR attribute "
            "name), so it can't land in DR's spec; give it one"
        )
    schema: dict[str, Any] = {}
    if operation.op is OperationType.CREATE:
        values: dict[str, Any] | str
        values, schema = _created_attribute(operation.fields, references)
    elif operation.op is OperationType.UPDATE:
        values = _updated_attribute(operation.fields, operation.base)
    else:
        values = {}
    if isinstance(values, str):
        return values
    entry = {
        "seq": operation.seq,
        "op_id": operation.id,
        "op": operation.op.value,
        "spec_node_id": node_id,
        "attribute": name,
        "identifier": identifier,
        "set": values,
    }
    if schema:
        entry["schema"] = schema
    return entry


def _node_id_of(
    repo: OntologyRepository, class_id: Any, class_deletes: dict[str, ProposedOperation]
) -> str | None:
    """A class's spec node id; for a class the proposal deleted, as its delete saw it."""
    cls = repo.get_class(class_id) if isinstance(class_id, str) else None
    if cls is not None:
        return dr_relationship_id(cls.external_references)
    delete = class_deletes.get(class_id) if isinstance(class_id, str) else None
    return dr_relationship_id(delete.base.get("external_references") or []) if delete else None


def _created_attribute(
    fields: dict[str, Any], references: list[Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    A created attribute's values, and the other JSON Schema keywords its DR
    reference keeps. An untyped attribute (schema "type" null) still a
    string gives no datatype.
    """
    schema = dict(_dr_metadata(references).get(DR_ATTRIBUTE_SCHEMA) or {})
    untyped = "type" in schema and schema.pop("type") is None
    values = {
        name: fields[name]
        for name in _ATTRIBUTE_FIELDS
        if fields.get(name) not in (None, [])
        and not (name == "datatype" and untyped and fields[name] == "string")
    }
    values["is_required"] = bool(fields.get("is_required"))
    if values.get("datatype") == DataType.DATE.value:
        values["datatype"], schema["format"] = _DR_DATE
    return values, schema


def _updated_attribute(fields: dict[str, Any], base: dict[str, Any]) -> dict[str, Any] | str:
    """The values an update changed; a reason when it changed none DR holds."""
    values = {
        name: (fields[name] or None) if name == "allowed_values" else fields[name]
        for name in _ATTRIBUTE_FIELDS
        if name in fields and fields[name] != base.get(name)
    }
    if "datatype" in values and DataType.DATE.value in (values["datatype"], base.get("datatype")):
        return (
            "it changes an attribute to or from a date, which DR's spec holds as a string "
            "with format date, a JSON Schema keyword an update can't send; change it in DR"
        )
    return values or "it changes nothing DR's spec holds for an attribute"


def _dr_metadata(references: Any) -> dict[str, Any]:
    """The metadata of the DR reference among references (dicts or objects)."""
    for ref in references or []:
        source = ref.get("source") if isinstance(ref, dict) else getattr(ref, "source", None)
        if source == DR_SOURCE:
            metadata = ref.get("metadata") if isinstance(ref, dict) else ref.metadata
            return dict(metadata or {})
    return {}


# --------------------------------------------------------------- node types


def _dr_layers(repo: OntologyRepository) -> dict[str, str | None]:
    """
    The dr_spec taxonomy's schemes by id -> the DR layer each holds: the layer
    prefix most of its DR classes' spec node ids ("{layer}.{type}") share
    (a class moved in but not yet re-imported keeps its old prefix). None
    when a scheme has no DR class or two prefixes tie.
    """
    taxonomy = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    if taxonomy is None:
        return {}
    layers: dict[str, str | None] = {}
    for scheme in repo.list_concept_schemes(taxonomy_id=taxonomy.id, limit=None):
        prefixes = Counter(
            node_id.split(".", 1)[0]
            for cls in repo.list_classes(concept_scheme_id=scheme.id, limit=None)
            if (node_id := dr_relationship_id(cls.external_references)) and "." in node_id
        ).most_common(2)
        tied = len(prefixes) == 2 and prefixes[0][1] == prefixes[1][1]
        layers[scheme.id] = prefixes[0][0] if prefixes and not tied else None
    return layers


def _layer_of(layers: dict[str, str | None], scheme_id: Any, label: str) -> str | None:
    """A scheme's DR layer; None when it isn't one of the DR spec's schemes."""
    if scheme_id not in layers:
        return None
    layer = layers[scheme_id]
    if layer is None:
        raise ValueError(
            f"{label}: its scheme {scheme_id} is in the DR spec, but no layer can be read "
            "from its classes' DR references"
        )
    return layer


def _check_node_id(node_id: str, layer: str, label: str) -> None:
    """A DR spec node id is "{layer}.{type}", in the class's layer."""
    prefix, _, type_name = node_id.partition(".")
    if prefix != layer or not type_name or "." in type_name:
        raise ValueError(
            f"{label}: its DR id {node_id!r} is not '{layer}.<type>', a node type of the "
            f"{layer!r} layer its scheme holds"
        )


def _node_change(
    operation: ProposedOperation,
    repo: OntologyRepository,
    refs: dict[str, str | None],
    deletes: dict[str, ProposedOperation],
    layers: dict[str, str | None],
) -> dict[str, Any] | str | None:
    """
    An applied class operation as a DR node type change; a string says why it
    doesn't export, None that the class isn't a DR node type.
    """
    label = f"seq {operation.seq}"
    if operation.op is OperationType.CREATE:
        return _node_create(operation, refs, layers, label)
    if operation.op is OperationType.MOVE:
        return _node_move(operation, repo, refs, layers, label)
    if operation.op is OperationType.UPDATE:
        return _node_update(operation, repo, layers, label)
    return _node_delete(operation, repo, refs, deletes, label)


def _node_create(
    operation: ProposedOperation,
    refs: dict[str, str | None],
    layers: dict[str, str | None],
    label: str,
) -> dict[str, Any] | None:
    fields = operation.fields
    layer = _layer_of(layers, _resolve_ref(fields.get("concept_scheme_id"), refs, label), label)
    node_id = dr_relationship_id(fields.get("external_references") or [])
    if layer is None:
        if node_id is not None:
            raise ValueError(
                f"{label}: it created a class with DR id {node_id!r} outside the DR spec's layers"
            )
        return None
    if node_id is None:
        raise ValueError(
            f"{label}: it created a class in the DR layer {layer!r} without a DR reference "
            f"(source {DR_SOURCE!r}, identifier '{layer}.<type>'), so it can't land in "
            "DR's spec; give it one"
        )
    _check_node_id(node_id, layer, label)
    values = {key: fields[key] for key in ("title", "description") if fields.get(key) is not None}
    return _node_entry(operation, "create", node_id, fields.get("identifier"), values)


def _node_update(
    operation: ProposedOperation,
    repo: OntologyRepository,
    layers: dict[str, str | None],
    label: str,
) -> dict[str, Any] | str | None:
    fields, base = operation.fields, operation.base
    cls = repo.get_class(operation.target_id or "")
    if cls is None:
        raise ValueError(f"{label}: its class no longer exists")
    node_id = dr_relationship_id(cls.external_references)
    if "external_references" in fields:
        before = dr_relationship_id(base.get("external_references") or [])
        after = dr_relationship_id(fields["external_references"] or [])
        if before != after:
            raise ValueError(
                f"{label}: it changed the class's DR id from {before!r} to {after!r}, which "
                "DR's spec can't follow; move the class, or delete it with a replacement"
            )
    if node_id is None:
        if _layer_of(layers, cls.concept_scheme_id, label) is not None:
            raise ValueError(
                f"{label}: it changed a class in the DR spec without a DR reference "
                f"(source {DR_SOURCE!r}), so it can't land in DR's spec; give it one"
            )
        return None
    values = {
        key: fields[key]
        for key in ("title", "description")
        if key in fields and fields[key] != base.get(key)
    }
    if not values:
        return "it changes nothing DR's spec holds for a node type"
    return _node_entry(operation, "update", node_id, cls.identifier, values)


def _node_move(
    operation: ProposedOperation,
    repo: OntologyRepository,
    refs: dict[str, str | None],
    layers: dict[str, str | None],
    label: str,
) -> dict[str, Any] | str | None:
    """
    A move to another scheme moves the node type to that scheme's layer: DR's
    spec node id "{layer}.{type}" keeps its type and takes the new layer.
    """
    fields = operation.fields
    if "concept_scheme_id" not in fields:
        return "a parent class move; DR's spec has no class hierarchy"
    cls = repo.get_class(operation.target_id or "")
    if cls is None:
        raise ValueError(f"{label}: its class no longer exists")
    node_id = dr_relationship_id(cls.external_references)
    previous = _layer_of(layers, operation.base.get("concept_scheme_id"), label)
    layer = _layer_of(layers, _resolve_ref(fields["concept_scheme_id"], refs, label), label)
    if node_id is None and previous is None and layer is None:
        return None
    if node_id is None or previous is None or layer is None:
        raise ValueError(
            f"{label}: it moved a class into or out of the DR spec's layers, or one without "
            f"a DR reference (source {DR_SOURCE!r}), so it can't land in DR's spec"
        )
    type_name = node_id.partition(".")[2]
    entry = _node_entry(operation, "move", f"{layer}.{type_name}", cls.identifier, {})
    entry["previous_spec_node_id"] = f"{previous}.{type_name}"
    return entry


def _node_delete(
    operation: ProposedOperation,
    repo: OntologyRepository,
    refs: dict[str, str | None],
    deletes: dict[str, ProposedOperation],
    label: str,
) -> dict[str, Any] | None:
    """
    A deleted node type, with the class the delete names as its replacement,
    followed through the proposal's other class deletes as for relationship
    types (see `_delete`).
    """
    base = operation.base
    node_id = dr_relationship_id(base.get("external_references") or [])
    if node_id is None:
        return None
    entry = _node_entry(operation, "delete", node_id, base.get("identifier"), {})
    replacement_class_id, cycle = _final_replacement(operation, repo.get_class, refs, deletes)
    if cycle:
        entry["note"] = (
            "its replacement chain comes back round to a class this proposal deletes, so no "
            "node type survives to replace it"
        )
    if replacement_class_id:
        replacement = repo.get_class(replacement_class_id)
        replacement_id = (
            dr_relationship_id(replacement.external_references) if replacement else None
        )
        if replacement_id is None:
            raise ValueError(
                f"{label}: its replacement {replacement_class_id} is not a DR node type"
            )
        entry["replacement_spec_node_id"] = replacement_id
    return entry


def _node_entry(
    operation: ProposedOperation, op: str, node_id: str, identifier: Any, values: dict
) -> dict[str, Any]:
    return {
        "seq": operation.seq,
        "op_id": operation.id,
        "op": op,
        "spec_node_id": node_id,
        "layer_id": node_id.partition(".")[0],
        "identifier": identifier,
        "set": values,
    }


def _node_actions(
    proposal: ChangeProposal,
    node_changes: list[dict[str, Any]],
    decisions: Mapping[str, ProposalDecision] | None,
) -> list[dict[str, Any]]:
    """
    DR's `rename-type` change actions for the node type changes whose elements
    a model migration can carry over: a move (to its new id) and a delete
    with a replacement (to the replacement).
    """
    probabilities = {o.id: o.probability for o in proposal.operations}
    actions = []
    for change in node_changes:
        if change["op"] == "move":
            from_, to, kind = change["previous_spec_node_id"], change["spec_node_id"], "cs:move"
        elif change.get("replacement_spec_node_id"):
            from_, to = change["spec_node_id"], change["replacement_spec_node_id"]
            kind = "cs:delete"
        else:
            continue
        decision = (decisions or {}).get(change["op_id"])
        actions.append(
            {
                "action": "rename-type",
                "kind": kind,
                "from": from_,
                "to": to,
                "swap": False,
                "p": probabilities.get(change["op_id"]) or 1.0,
                "proposal_id": proposal.id,
                "operation_id": change["op_id"],
                "applied_at": decision.decided_at.isoformat() if decision else None,
            }
        )
    return actions


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
