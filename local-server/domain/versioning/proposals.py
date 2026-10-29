"""
Change proposals: ontology changes an agent, a pipeline, a bundle import or a
person proposes, held until someone decides on them.

A proposal is a run: its id is the batch run id that tags the change events of
everything applied from it, so reverting the run undoes the proposal. Each
operation is one create, update, move or delete of one ontology entity, and
records its own outcome.

Scope follows the DR design charter's vocabulary. The system classifies it
(`classify_scope`); an agent's claim can only make it stricter:

- editorial: wording or presentation only (title, description, vision, color,
  sort order)
- additive: something new, or more of something (a create, an extra allowed
  value, an extra class on an individual, a new reference, an extra attribute
  on a relationship)
- breaking: anything that removes, moves or redefines (a delete, a move, an
  identifier, domain or range, datatype or requiredness change, a new required
  attribute, a relationship attribute removed or changed)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from domain.ontology.entities import same_attribute_value


class ProposalSource(str, Enum):
    """Who or what made the proposal."""

    CHAT = "chat"
    MCP = "mcp"
    PIPELINE = "pipeline"
    BUNDLE = "bundle"
    USER = "user"


class ProposalStatus(str, Enum):
    """A proposal is open while any operation awaits a decision."""

    OPEN = "open"
    DONE = "done"
    REVERTED = "reverted"


class OperationType(str, Enum):
    """What an operation does to its target."""

    CREATE = "create"
    UPDATE = "update"
    MOVE = "move"
    DELETE = "delete"


class OperationKind(str, Enum):
    """The kind of ontology entity an operation targets."""

    TAXONOMY = "taxonomy"
    SCHEME = "scheme"
    CLASS = "class"
    PROPERTY = "property"
    ATTRIBUTE = "attribute"
    INDIVIDUAL = "individual"
    RELATIONSHIP = "relationship"


class ChangeScope(str, Enum):
    """How much a change can break, in increasing order."""

    EDITORIAL = "editorial"
    ADDITIVE = "additive"
    BREAKING = "breaking"

    @property
    def rank(self) -> int:
        return _SCOPE_RANK[self]


_SCOPE_RANK = {ChangeScope.EDITORIAL: 0, ChangeScope.ADDITIVE: 1, ChangeScope.BREAKING: 2}


class OperationStatus(str, Enum):
    """Where an operation stands."""

    PENDING = "pending"
    APPLIED = "applied"
    REJECTED = "rejected"
    FAILED = "failed"


# Fields whose change is wording or presentation only.
EDITORIAL_FIELDS = frozenset({"title", "description", "vision", "color", "sort_order"})
# List fields where a superset of the current value only adds.
ADDITIVE_LIST_FIELDS = frozenset(
    {"allowed_values", "class_ids", "external_references", "lexical_senses"}
)
# Map fields where keeping every current key and value only adds.
ADDITIVE_MAP_FIELDS = frozenset({"attributes"})

# What a move can change, per kind: a scheme moves to another taxonomy, and a
# class to another parent, another scheme, or both. Nothing else can move.
MOVE_FIELDS = {
    OperationKind.SCHEME: frozenset({"taxonomy_id"}),
    OperationKind.CLASS: frozenset({"parent_class_id", "concept_scheme_id"}),
}


def classify_scope(
    op: OperationType,
    fields: dict[str, Any],
    base: dict[str, Any] | None = None,
    claimed: ChangeScope | None = None,
) -> ChangeScope:
    """
    The scope of an operation; a claimed scope can only make it stricter.

    Args:
        op: What the operation does
        fields: The fields it sets (for an update, only the changed ones)
        base: The current values of those fields; a field set to its current
            value changes nothing, and a list field counts as additive only
            when its current value is given and every item of it is kept (a
            field missing from base is unknown, so breaking)
        claimed: A scope the proposer asserted, if any

    Returns:
        The stricter of the computed and the claimed scope
    """
    computed = _computed_scope(op, fields, base or {})
    if claimed is not None and claimed.rank > computed.rank:
        return claimed
    return computed


def _computed_scope(op: OperationType, fields: dict[str, Any], base: dict[str, Any]) -> ChangeScope:
    if op in (OperationType.DELETE, OperationType.MOVE):
        return ChangeScope.BREAKING
    if op is OperationType.CREATE:
        # A required attribute makes every existing individual of its class invalid.
        return ChangeScope.BREAKING if fields.get("is_required") is True else ChangeScope.ADDITIVE
    scope = ChangeScope.EDITORIAL
    for name, value in fields.items():
        if name in EDITORIAL_FIELDS or (name in base and base[name] == value):
            continue  # wording only, or a field set to the value it already has
        if name in ADDITIVE_LIST_FIELDS and name in base and _only_adds(base[name], value):
            scope = ChangeScope.ADDITIVE
            continue
        if name in ADDITIVE_MAP_FIELDS and name in base and _only_adds_keys(base[name], value):
            scope = ChangeScope.ADDITIVE
            continue
        return ChangeScope.BREAKING
    return scope


def _only_adds(current: Any, proposed: Any) -> bool:
    """Whether a list field keeps every current item (a None current value is empty)."""
    if not isinstance(proposed, list):
        return False
    return all(item in proposed for item in current or [])


def _only_adds_keys(current: Any, proposed: Any) -> bool:
    """Whether a map field keeps every current key and its value (None current is empty)."""
    if not isinstance(proposed, dict):
        return False
    return all(
        key in proposed and same_attribute_value(proposed[key], value)
        for key, value in (current or {}).items()
    )


@dataclass
class ProposedOperation:
    """
    One change to one ontology entity, as proposed.

    Attributes:
        seq: Position in the proposal; operations apply in this order
        op: Create, update, move or delete
        kind: The kind of entity targeted
        target_id: The existing entity (update, move, delete)
        ref: A name a create gives its new entity, so later operations in the
            same proposal can point at it with "$<ref>"
        fields: For a create, every field; for an update, only the changed ones;
            for a move, only MOVE_FIELDS (a scheme's taxonomy_id; a class's
            parent_class_id and/or concept_scheme_id)
        base: The current values of the touched fields when proposed (for a
            delete, the whole entity); compared at apply time to detect that
            the target changed since
        rationale: Why this change
        evidence: Supporting quotes or links ({"quote", "url", "entity_id"})
        probability: The proposer's confidence, 0 to 1
        scope: How much the change can break (see classify_scope)
        status: Pending, applied, rejected or failed
        result_entity_id: The entity created or changed, once applied
        reason: Why it failed or was rejected
        applied_fields: Set when a reviewer edited the operation before applying
            it: the fields actually applied, always as an update (an edited
            delete applies as an update). None when applied as proposed or not
            applied. `fields` keeps what was proposed.
        id: Unique id
    """

    seq: int
    op: OperationType
    kind: OperationKind
    target_id: str | None = None
    ref: str | None = None
    fields: dict[str, Any] = field(default_factory=dict)
    base: dict[str, Any] = field(default_factory=dict)
    rationale: str | None = None
    evidence: list[dict[str, Any]] = field(default_factory=list)
    probability: float | None = None
    scope: ChangeScope = ChangeScope.BREAKING
    status: OperationStatus = OperationStatus.PENDING
    result_entity_id: str | None = None
    reason: str | None = None
    applied_fields: dict[str, Any] | None = None
    id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        if self.op is OperationType.CREATE:
            if self.target_id is not None:
                raise ValueError("A create has no target_id; name it with ref instead")
        elif not self.target_id:
            raise ValueError(f"An {self.op.value} needs a target_id")
        if self.op is OperationType.UPDATE:
            if not self.fields:
                raise ValueError("An update needs at least one field")
            if self.kind is OperationKind.RELATIONSHIP and set(self.fields) != {"attributes"}:
                raise ValueError(
                    "A relationship update sets only attributes; to change its ends or"
                    " type, delete it and create another"
                )
            moving = sorted(MOVE_FIELDS.get(self.kind, frozenset()) & set(self.fields))
            if moving:
                raise ValueError(f"Use a move to change {', '.join(moving)}")
        if self.op is OperationType.MOVE:
            move_fields = MOVE_FIELDS.get(self.kind)
            if move_fields is None:
                raise ValueError(f"A {self.kind.value} can't be moved")
            if not self.fields or not set(self.fields) <= move_fields:
                raise ValueError(
                    f"A {self.kind.value} move sets only {', '.join(sorted(move_fields))}"
                )
        if self.ref is not None and self.op is not OperationType.CREATE:
            raise ValueError("Only a create can carry a ref")
        if self.probability is not None and not 0.0 <= self.probability <= 1.0:
            raise ValueError("probability must be between 0 and 1")

    @property
    def decided(self) -> bool:
        """
        Whether the operation is settled: applied or rejected. A failed one is
        not; it can be applied again (e.g. forced past a stale target) or rejected.
        """
        return self.status in (OperationStatus.APPLIED, OperationStatus.REJECTED)


@dataclass
class ChangeProposal:
    """
    A set of proposed ontology changes on one taxonomy, decided per operation.

    Attributes:
        id: Unique id, shared with the batch run its applied changes are tagged with
        taxonomy_id: The taxonomy the changes are about
        title: A short summary
        rationale: Why these changes, as a whole
        source: Who or what proposed them
        source_detail: More about the source (MCP client name, conversation id,
            bundle file name)
        created_at: When it was proposed
        status: Open while any operation is pending
        operations: The proposed operations, in seq order
    """

    id: str
    taxonomy_id: str
    title: str
    source: ProposalSource
    created_at: datetime
    rationale: str | None = None
    source_detail: str | None = None
    status: ProposalStatus = ProposalStatus.OPEN
    operations: list[ProposedOperation] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.title or not self.title.strip():
            raise ValueError("A proposal needs a title")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        seqs = [o.seq for o in self.operations]
        if len(seqs) != len(set(seqs)):
            raise ValueError("Operation seq values must be unique within a proposal")
        self.operations.sort(key=lambda o: o.seq)

    @property
    def pending(self) -> list[ProposedOperation]:
        """Operations still awaiting a decision: pending or failed."""
        return [o for o in self.operations if not o.decided]

    def settle_status(self) -> ProposalStatus:
        """
        Mark the proposal done once every operation is applied or rejected (a
        failed one keeps it open; a reverted proposal stays reverted).
        """
        if self.status is ProposalStatus.OPEN and not self.pending:
            self.status = ProposalStatus.DONE
        return self.status
