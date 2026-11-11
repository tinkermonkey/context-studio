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
from domain.ontology.value_objects import SourceRevision


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
    # A predicate in the proposal's taxonomy's catalog
    PREDICATE = "predicate"


class ResolutionStrategy(str, Enum):
    """What happens to the relationships still using a relationship type being deleted."""

    MOVE = "move"
    DELETE = "delete"


class AlternativeKind(str, Enum):
    """What an alternative to an operation offers instead of it."""

    # An individual already in the dataset that the create may be (a near match)
    EXISTING = "existing"


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
EDITORIAL_FIELDS = frozenset(
    {
        "title",
        "description",
        "vision",
        "color",
        "sort_order",
        # A class's operational definition: it explains the class, changes nothing in it
        "distinguish_from",
        "evidence_signals",
        "standard_reference",
    }
)
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
        if name in EDITORIAL_FIELDS or (name in base and _same_value(base[name], value)):
            continue  # wording only, or a field set to the value it already has
        if name in ADDITIVE_LIST_FIELDS and name in base and _only_adds(base[name], value):
            scope = ChangeScope.ADDITIVE
            continue
        if name in ADDITIVE_MAP_FIELDS and name in base and _only_adds_keys(base[name], value):
            scope = ChangeScope.ADDITIVE
            continue
        return ChangeScope.BREAKING
    return scope


def _same_value(a: Any, b: Any) -> bool:
    """Whether two JSON values are equal and of the same types throughout (True is not 1)."""
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same_value(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_same_value(x, y) for x, y in zip(a, b))
    return same_attribute_value(a, b)


def _only_adds(current: Any, proposed: Any) -> bool:
    """
    Whether a list field keeps every current item (a None current value is empty).
    An item is kept when some proposed item equals it, or extends it with new keys
    (a reference gaining metadata keys, say).
    """
    if not isinstance(proposed, list):
        return False
    return all(any(_extends(item, new) for new in proposed) for item in current or [])


def _extends(current: Any, proposed: Any) -> bool:
    """
    Whether proposed keeps current: the same typed value, or, for dicts, every
    current key kept and itself extended. A None value may become a dict (a
    reference without metadata gaining some); changing or removing a key, or any
    other value, does not extend.
    """
    if isinstance(current, dict) and isinstance(proposed, dict):
        return all(
            key in proposed and _extends(value, proposed[key]) for key, value in current.items()
        )
    if current is None and isinstance(proposed, dict):
        return True
    return same_attribute_value(current, proposed)


def _only_adds_keys(current: Any, proposed: Any) -> bool:
    """Whether a map field keeps every current key and its value (None current is empty)."""
    if not isinstance(proposed, dict):
        return False
    return all(
        key in proposed and same_attribute_value(proposed[key], value)
        for key, value in (current or {}).items()
    )


@dataclass(frozen=True)
class ResolvedEdge:
    """
    One relationship a resolved delete moved or deleted.

    Attributes:
        relationship_id: The relationship that used the deleted type
        source_id, target_id: Its ends (the relationship made in its place by
            a reversed move runs the other way)
        source_title, target_title: The ends' titles when it was resolved
        moved_to_id: The relationship of the replacement type made in its place
            (a move only)
    """

    relationship_id: str
    source_id: str
    target_id: str
    source_title: str
    target_title: str
    moved_to_id: str | None = None


@dataclass
class InUseResolution:
    """
    A reviewer's choice for deleting a relationship type that relationships still use.

    Attributes:
        strategy: Move the relationships to another type, or delete them too;
            either way the type is deleted afterwards
        replacement_property_id: The type they move to (a move only)
        replacement_identifier: That type's identifier, recorded when applied
        reversed: The replacement's domain and range are the deleted type's
            reversed, so each moved relationship was made with its ends
            swapped; recorded when applied
        edges: The relationships moved or deleted, recorded when applied
        relationship_ids: The relationships the reviewer saw using the type
            (a request only, not stored); the apply fails if the relationships
            using it at apply time differ. None skips the check.
    """

    strategy: ResolutionStrategy
    replacement_property_id: str | None = None
    replacement_identifier: str | None = None
    reversed: bool = False
    edges: list[ResolvedEdge] = field(default_factory=list)
    relationship_ids: list[str] | None = None

    def __post_init__(self) -> None:
        self.strategy = ResolutionStrategy(self.strategy)
        if self.strategy is ResolutionStrategy.MOVE and not self.replacement_property_id:
            raise ValueError("A move needs replacement_property_id")
        if self.strategy is ResolutionStrategy.DELETE and self.replacement_property_id:
            raise ValueError("A delete takes no replacement_property_id")

    def to_json(self) -> dict[str, Any]:
        """The JSON stored with the operation."""
        return {
            "strategy": self.strategy.value,
            "replacement_property_id": self.replacement_property_id,
            "replacement_identifier": self.replacement_identifier,
            "reversed": self.reversed,
            "edges": [vars(edge).copy() for edge in self.edges],
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "InUseResolution":
        return cls(
            strategy=ResolutionStrategy(data["strategy"]),
            replacement_property_id=data.get("replacement_property_id"),
            replacement_identifier=data.get("replacement_identifier"),
            reversed=bool(data.get("reversed")),
            edges=[ResolvedEdge(**edge) for edge in data.get("edges") or []],
        )


# A relationship type's fields its pair and keys are read from (as snapshot JSON).
TYPE_KEY_FIELDS = (
    "identifier",
    "canonical_predicate",
    "domain_class_id",
    "range_class_id",
    "external_references",
)


class SchemaChangeAction(str, Enum):
    """What an applied operation did to a relationship type."""

    CREATE = "create"
    RENAME = "rename"
    REVERSE = "reverse"
    RETARGET = "retarget"
    DELETE = "delete"


@dataclass
class TypeChange:
    """
    What an applied relationship-type operation did to the type and the
    relationships using it, recorded as it applied (see
    `domain.versioning.change_records`).

    Attributes:
        action: Create; rename (the same pair of classes); reverse (the pair
            swapped: its relationships swapped ends); retarget (another pair);
            delete
        before: The type's id and TYPE_KEY_FIELDS just before (None: a create)
        after: The same just after (None: a delete)
        swap: Its relationships swapped ends: a reverse, or a move to a
            reversed replacement
        replacement: The id and TYPE_KEY_FIELDS of the type its relationships
            moved to (a retarget's or delete's resolution), or of the type a
            delete names as its replacement when that links the same pair of
            classes or the reverse; None otherwise
    """

    action: SchemaChangeAction
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    swap: bool = False
    replacement: dict[str, Any] | None = None

    def to_json(self) -> dict[str, Any]:
        """The JSON stored with the operation."""
        return {
            "action": self.action.value,
            "before": self.before,
            "after": self.after,
            "swap": self.swap,
            "replacement": self.replacement,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "TypeChange":
        return cls(
            action=SchemaChangeAction(data["action"]),
            before=data.get("before"),
            after=data.get("after"),
            swap=bool(data.get("swap")),
            replacement=data.get("replacement"),
        )


@dataclass
class OperationDraft:
    """
    One operation as a proposer submits it, before validation.

    Attributes mirror ProposedOperation; `claimed_scope` is the scope the
    proposer asserts, which can only make the computed scope stricter.
    `replacement` names the relationship type replacing the one a property
    delete removes: its id, its identifier, or "$<ref>" of an earlier property
    create; it is stored, resolved, as `proposed_replacement_id`. `base` and
    `status` are not submitted: the service captures and tracks them.
    `alternatives` are an individual create's near matches (see
    ProposedOperation).
    """

    seq: int
    op: OperationType | str
    kind: OperationKind | str
    target_id: str | None = None
    ref: str | None = None
    fields: dict[str, Any] = field(default_factory=dict)
    rationale: str | None = None
    notes: str | None = None
    evidence: list[dict[str, Any]] = field(default_factory=list)
    probability: float | None = None
    claimed_scope: ChangeScope | str | None = None
    replacement: str | None = None
    alternatives: list[dict[str, Any]] = field(default_factory=list)


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
        notes: Free-text notes the proposer keeps with the change (e.g. a
            maintainer's notes); never applied to the entity. None when empty
        evidence: Supporting quotes or links ({"quote", "url", "entity_id"}),
            or passages in a source ({"source_id", "page", "start", "end",
            "quote"}; see `domain.versioning.provenance`)
        probability: The proposer's confidence, 0 to 1
        scope: How much the change can break (see classify_scope)
        status: Pending, applied, rejected or failed
        result_entity_id: The entity created or changed, once applied
        reason: Why it failed or was rejected
        applied_fields: Set when a reviewer edited the operation before applying
            it: the fields actually applied, always as an update (an edited
            delete applies as an update). None when applied as proposed or not
            applied. `fields` keeps what was proposed.
        resolution: How an applied relationship-type delete resolved the
            relationships still using the type, if they were moved or deleted
        proposed_replacement_id: A property or class delete only: the
            relationship type or class the proposer says replaces the deleted
            one, as an id or "$<ref>" of an earlier create of the same kind (see
            `domain.versioning.in_use` for how a relationship type's pair of
            classes is compared with the deleted type's). A class's replacement
            changes nothing in Context Studio; it tells a client that mirrors
            the taxonomy (e.g. DR) what to migrate the deleted type's elements to
        type_change: Set when an applied property operation created or deleted
            the type, or changed its pair or keys: what it did (see TypeChange)
        alternatives: An individual create only: individuals already in the
            proposal's dataset it may be (near matches), each {"kind":
            "existing", "entity_id", "similarity"}. Applying it with one of them
            chosen creates nothing: the operation resolves to that individual,
            so "$ref" uses of it point there (see `matched`)
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
    notes: str | None = None
    evidence: list[dict[str, Any]] = field(default_factory=list)
    probability: float | None = None
    scope: ChangeScope = ChangeScope.BREAKING
    status: OperationStatus = OperationStatus.PENDING
    result_entity_id: str | None = None
    reason: str | None = None
    applied_fields: dict[str, Any] | None = None
    resolution: InUseResolution | None = None
    proposed_replacement_id: str | None = None
    type_change: TypeChange | None = None
    alternatives: list[dict[str, Any]] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        if self.alternatives and (
            self.op is not OperationType.CREATE or self.kind is not OperationKind.INDIVIDUAL
        ):
            raise ValueError("Only an individual create can carry alternatives")
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
        if self.proposed_replacement_id is not None and (
            self.op is not OperationType.DELETE
            or self.kind
            not in (OperationKind.PROPERTY, OperationKind.CLASS, OperationKind.PREDICATE)
        ):
            raise ValueError(
                "Only a property (relationship type), class or predicate delete can name a"
                " replacement"
            )

    @property
    def decided(self) -> bool:
        """
        Whether the operation is settled: applied or rejected. A failed one is
        not; it can be applied again (e.g. forced past a stale target) or rejected.
        """
        return self.status in (OperationStatus.APPLIED, OperationStatus.REJECTED)

    def alternative(self, entity_id: Any) -> dict[str, Any] | None:
        """The "existing" alternative naming this entity, if the operation has one."""
        return next(
            (
                a
                for a in self.alternatives
                if a.get("kind") == AlternativeKind.EXISTING.value
                and a.get("entity_id") == entity_id
            ),
            None,
        )

    @property
    def matched(self) -> bool:
        """
        Applied as one of its "existing" alternatives: it created nothing, and
        result_entity_id is that existing individual. (A created entity's id is
        new, so it never equals an alternative's.)
        """
        return (
            self.status is OperationStatus.APPLIED
            and self.result_entity_id is not None
            and self.alternative(self.result_entity_id) is not None
        )


@dataclass(frozen=True)
class Landing:
    """
    Where and when the client landed a decided proposal in its source.

    Attributes:
        revision: The source revision that holds the change; its commit is required
        landed_at: When it was marked landed
    """

    revision: SourceRevision
    landed_at: datetime

    def __post_init__(self) -> None:
        if not self.revision.commit:
            raise ValueError("A landing needs the commit that holds the change")
        if self.landed_at.tzinfo is None:
            raise ValueError("landed_at must be timezone-aware")

    def to_dict(self) -> dict[str, Any]:
        """{repo, commit, spec_version, landed_at} with landed_at as ISO 8601."""
        return {**self.revision.to_dict(), "landed_at": self.landed_at.isoformat()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Landing":
        revision = {k: v for k, v in data.items() if k != "landed_at"}
        return cls(
            revision=SourceRevision.from_dict(revision),
            landed_at=datetime.fromisoformat(data["landed_at"]),
        )


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
        source_revision: The revision of the taxonomy's external source the
            proposal was drafted against (a mirrored taxonomy's spec), if known
        landed: Set once the client has landed the decided proposal in its
            source; independent of status (a done proposal is decided, not
            necessarily landed)
        client_metadata: What the proposing client keeps on the proposal for
            itself (JSON values, e.g. a DR plan's predicate retirements);
            Context Studio stores and returns it, and acts on none of it
        dataset_id: The dataset its individual and relationship operations are
            in: every individual they reference belongs to it, and individuals
            it creates go into it. None when it has no such operations.
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
    source_revision: SourceRevision | None = None
    landed: Landing | None = None
    client_metadata: dict[str, Any] = field(default_factory=dict)
    dataset_id: str | None = None

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
