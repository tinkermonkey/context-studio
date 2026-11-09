"""
ProposalService: propose ontology changes, then apply, reject or revert them.

A proposal is validated as a whole when it is made (nothing is stored if any
operation is invalid) and decided per operation afterwards. Applying runs the
chosen operations in seq order through OntologyService with the proposal's id
as the batch run id, so every change event they produce is tagged with it and
reverting the run undoes the proposal. Applies are not atomic: each operation
records its own outcome, and revert is the recovery path. One operation that
takes several steps (a relationship-type delete resolved by moving or deleting
the relationships using it) runs them in one transaction.

Values in an operation's `fields` and `base` use the JSON encoding of entity
snapshots (`domain.ontology.snapshots`): enums as their value, external
references as dicts. A field value "$name" in an id field points at the entity
an earlier create in the same proposal makes (its `ref` is "name").

An individual's attribute values are `data_properties`: attribute identifier
-> value. On a create they are its values; on an update, the values to set,
null removing one, others kept. Each must be an attribute of the individual's
classes (theirs or inherited from a parent class) and fit its datatype and
allowed values. A value for an attribute of a class the proposal itself
creates ("$ref") is checked when applied. Setting a value that wasn't there is
additive; changing or removing one is editorial, or breaking for a required
attribute.
"""

from __future__ import annotations

import json
import logging
import threading
from contextlib import nullcontext
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable, Iterable, Mapping, Sequence
from uuid import uuid4

from domain.interchange.services import get_current_batch_run_id, set_batch_run_context
from domain.ontology.entities import Class, validate_relationship_attributes
from domain.ontology.events import GraphInvalidated
from domain.ontology.exceptions import EntityNotFoundError, OntologyError
from domain.ontology.snapshots import decode_field, entity_snapshot
from domain.ontology.value_objects import DataPropertyValue, DataType, SourceRevision
from domain.versioning.approval_policy import auto_apply_ids
from domain.versioning.exceptions import (
    ChangeProposalNotFoundError,
    ChangeProposalStateError,
    OperationError,
    ProposalValidationError,
)
from domain.versioning.gold import (
    DECIDED_BY_POLICY,
    DECIDED_BY_USER,
    DecisionFilter,
    ProposalDecision,
    by_operation,
    decision_of,
    proposed_snapshot,
)
from domain.versioning.in_use import (
    ChainLink,
    ClassEnd,
    DeleteBlockers,
    InUseInspector,
    PairMatch,
    ReplacementCheck,
    compare_pair,
    moved_ends,
    reverses,
)
from domain.versioning.proposals import (
    TYPE_KEY_FIELDS,
    ChangeProposal,
    ChangeScope,
    InUseResolution,
    Landing,
    OperationDraft,
    OperationKind,
    OperationStatus,
    OperationType,
    ProposalSource,
    ProposalStatus,
    ProposedOperation,
    ResolutionStrategy,
    ResolvedEdge,
    SchemaChangeAction,
    TypeChange,
    classify_scope,
)

if TYPE_CHECKING:
    from domain.ontology.entities import AttributeDefinition
    from domain.ontology.ports import OntologyRepository
    from domain.ontology.services import OntologyService
    from domain.ports import EventPublisher, TransactionScope
    from domain.versioning.ports import (
        ApprovalPolicyRepository,
        ChangeProposalRepository,
        ProposalApplyRules,
    )
    from domain.versioning.revert_service import RevertResult, RevertService

_logger = logging.getLogger(__name__)

# Reason codes an applied operation can fail with; stored as "<code>: <detail>".
TARGET_CHANGED = "target_changed"
TARGET_MISSING = "target_missing"
UNRESOLVED_REF = "unresolved_ref"
APPLY_ERROR = "error"
INVALID_EDIT = "invalid_edit"
RULE_REFUSED = "refused"
UNRESOLVABLE = "unresolvable"

REVERTED_REASON = "proposal reverted"

_REF_PREFIX = "$"

# A proposal's title is a short summary; its rationale may run to a few pages.
MAX_TITLE_CHARS = 500
MAX_RATIONALE_CHARS = 8000
# Operation seq values fit SQLite's integer column with room to spare.
MAX_SEQ = 1_000_000
# Snapshot fields that change on every write; a delete's staleness ignores them.
_VOLATILE_FIELDS = frozenset({"last_modified", "version"})

K = OperationKind

# Fields that follow another entity rather than being set on this one: a class's
# taxonomy_id follows its scheme's. Staleness ignores them.
_DERIVED_FIELDS: dict[OperationKind, frozenset[str]] = {K.CLASS: frozenset({"taxonomy_id"})}

# The JSON type each settable field must have (None is checked separately).
_TEXT_FIELDS = frozenset(
    {
        "title",
        "description",
        "color",
        "identifier",
        "vision",
        "canonical_predicate",
        "datatype",
        "default_value",
    }
)
_BOOL_FIELDS = frozenset({"is_required", "is_relevant"})
_INT_FIELDS = frozenset({"sort_order"})
_TEXT_LIST_FIELDS = frozenset({"allowed_values", "class_ids"})
# An individual's attribute values: identifier -> value (see the module docstring).
DATA_FIELD = "data_properties"
_JSON_VALUE_TYPES = (str, int, float, bool, list, dict, type(None))
# The JSON type a value of each attribute datatype must have.
_DATATYPE_TYPES: dict[DataType, tuple[type, ...]] = {
    DataType.STRING: (str,),
    DataType.INTEGER: (int,),
    DataType.NUMBER: (int, float),
    DataType.BOOLEAN: (bool,),
    DataType.ARRAY: (list,),
    DataType.OBJECT: (dict,),
}
# The type hint a stored value carries, as the domain's examples write it
# (xsd for scalars; rdf:JSON, RDF 1.1's JSON literal, for arrays and objects).
_DATATYPE_HINTS: dict[DataType, str] = {
    DataType.STRING: "xsd:string",
    DataType.INTEGER: "xsd:integer",
    DataType.NUMBER: "xsd:decimal",
    DataType.BOOLEAN: "xsd:boolean",
    DataType.ARRAY: "rdf:JSON",
    DataType.OBJECT: "rdf:JSON",
}

# The kinds whose delete may name a replacement, and what to call them.
_REPLACEABLE: dict[OperationKind, str] = {K.PROPERTY: "relationship type", K.CLASS: "class"}

# Id fields and the kinds of entity they may point at.
ID_FIELDS: dict[str, tuple[OperationKind, ...]] = {
    "taxonomy_id": (K.TAXONOMY,),
    "concept_scheme_id": (K.SCHEME,),
    "parent_class_id": (K.CLASS,),
    "class_id": (K.CLASS,),
    "class_ids": (K.CLASS,),
    "domain_class_id": (K.CLASS,),
    "range_class_id": (K.CLASS,),
    "property_definition_id": (K.PROPERTY,),
    "source_id": (K.CLASS, K.INDIVIDUAL),
    "target_id": (K.CLASS, K.INDIVIDUAL),
}


@dataclass(frozen=True)
class OperationFields:
    """What an operation on one kind of entity may set."""

    create: frozenset[str]
    required: frozenset[str]
    update: frozenset[str] = frozenset()
    # Update fields that accept None, meaning "clear it"
    clearable: frozenset[str] = frozenset()


OPERATION_FIELDS: dict[OperationKind, OperationFields] = {
    K.TAXONOMY: OperationFields(
        create=frozenset({"title", "description", "color", "identifier", "vision"}),
        required=frozenset({"title"}),
        update=frozenset({"title", "description", "color", "vision", "external_references"}),
        clearable=frozenset({"description", "color", "vision"}),
    ),
    K.SCHEME: OperationFields(
        create=frozenset({"taxonomy_id", "title", "description", "color", "identifier"}),
        required=frozenset({"taxonomy_id", "title"}),
        update=frozenset({"title", "description", "color"}),
        clearable=frozenset({"description", "color"}),
    ),
    K.CLASS: OperationFields(
        create=frozenset(
            {
                "concept_scheme_id",
                "title",
                "description",
                "color",
                "parent_class_id",
                "identifier",
                "external_references",
            }
        ),
        required=frozenset({"concept_scheme_id", "title"}),
        update=frozenset({"title", "description", "color", "external_references"}),
        clearable=frozenset({"description", "color"}),
    ),
    K.PROPERTY: OperationFields(
        create=frozenset(
            {
                "identifier",
                "title",
                "description",
                "canonical_predicate",
                "domain_class_id",
                "range_class_id",
                "external_references",
            }
        ),
        required=frozenset({"identifier", "title"}),
        update=frozenset(
            {
                "identifier",
                "title",
                "description",
                "canonical_predicate",
                "is_relevant",
                "domain_class_id",
                "range_class_id",
                "external_references",
            }
        ),
        clearable=frozenset(
            {
                "description",
                "canonical_predicate",
                "is_relevant",
                "domain_class_id",
                "range_class_id",
            }
        ),
    ),
    K.ATTRIBUTE: OperationFields(
        create=frozenset(
            {
                "class_id",
                "identifier",
                "title",
                "datatype",
                "description",
                "is_required",
                "allowed_values",
                "default_value",
                "sort_order",
                "external_references",
            }
        ),
        required=frozenset({"class_id", "identifier", "title", "datatype"}),
        update=frozenset(
            {
                "title",
                "description",
                "datatype",
                "is_required",
                "allowed_values",
                "default_value",
                "sort_order",
                "external_references",
            }
        ),
        clearable=frozenset({"description", "allowed_values", "default_value"}),
    ),
    K.INDIVIDUAL: OperationFields(
        create=frozenset({"class_ids", "title", "description", "external_references", DATA_FIELD}),
        required=frozenset({"class_ids", "title"}),
        update=frozenset({"title", "description", "external_references", "class_ids", DATA_FIELD}),
        clearable=frozenset({"description"}),
    ),
    K.RELATIONSHIP: OperationFields(
        create=frozenset({"source_id", "target_id", "property_definition_id", "attributes"}),
        required=frozenset({"source_id", "target_id", "property_definition_id"}),
        update=frozenset({"attributes"}),
    ),
}


class _Invalid(Exception):
    """One validation problem with one operation."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class _ApplyFailed(Exception):
    """An operation can't be applied; becomes its FAILED status and reason."""

    def __init__(self, code: str, detail: str):
        self.reason = f"{code}: {detail}"
        super().__init__(self.reason)


def _is_ref(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(_REF_PREFIX) and len(value) > 1


def _data_values(snapshot_values: Any) -> dict[str, Any]:
    """An individual's snapshot data_properties as identifier -> value."""
    return {item["property_identifier"]: item["value"] for item in snapshot_values or []}


def _value_problem(attribute: AttributeDefinition, value: Any) -> str | None:
    """Why a (non-None) value doesn't fit an attribute's datatype or allowed values."""
    datatype = DataType(attribute.datatype)
    wrong_type = not isinstance(value, _DATATYPE_TYPES[datatype]) or (
        datatype in (DataType.INTEGER, DataType.NUMBER) and isinstance(value, bool)
    )
    if wrong_type:
        return f"is {datatype.value}, so {value!r} doesn't fit"
    allowed = attribute.allowed_values
    if allowed and not isinstance(value, dict):
        # Allowed values are text: a number or boolean matches its JSON text ("3", "true").
        items = value if isinstance(value, list) else [value]
        unknown = [
            item
            for item in items
            if (item if isinstance(item, str) else json.dumps(item)) not in allowed
        ]
        if unknown:
            return f"allows only {allowed}, not {unknown}"
    return None


def _has_field_type(name: str, value: Any) -> bool:
    """Whether a (non-None) field value has the JSON type its field takes."""
    if name in _TEXT_LIST_FIELDS:
        return isinstance(value, list) and all(isinstance(item, str) for item in value)
    if name in _TEXT_FIELDS or name in ID_FIELDS:
        return isinstance(value, str)
    if name in _BOOL_FIELDS:
        return isinstance(value, bool)
    if name in _INT_FIELDS:
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "external_references":
        return isinstance(value, list) and all(isinstance(item, dict) for item in value)
    if name == DATA_FIELD:
        return isinstance(value, dict) and all(
            isinstance(key, str) and key and isinstance(item, _JSON_VALUE_TYPES)
            for key, item in value.items()
        )
    if name == "attributes":
        try:
            validate_relationship_attributes(value)
        except ValueError:
            return False
        return True
    return True


class ProposalService:
    """Propose, apply, reject and revert change proposals."""

    def __init__(
        self,
        proposals: ChangeProposalRepository,
        ontology_service: OntologyService,
        ontology_repo: OntologyRepository,
        revert_service: RevertService,
        approval_policies: ApprovalPolicyRepository | None = None,
        apply_rules: Sequence[ProposalApplyRules] = (),
        transaction_scope: TransactionScope | None = None,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        """
        Args:
            proposals: Stores proposals and operation outcomes
            ontology_service: The write path for every change an operation makes
            ontology_repo: Reads targets for validation, base capture and staleness
            revert_service: Undoes everything applied under a proposal's run id
            approval_policies: Taxonomies' approval policies; without them
                nothing auto-applies
            apply_rules: Rules some property definitions are under (each
                says which it governs); the rest get only the generic checks
            transaction_scope: Makes an operation of several steps (a resolved
                relationship-type delete) atomic; without one, a step failing
                keeps the steps before it
            event_publisher: Invalidates the graphs a multi-step operation
                touched once its transaction commits (the steps' own
                invalidations run before the commit, so a rebuild could cache
                the old graph)
        """
        self._proposals = proposals
        self._ontology = ontology_service
        self._repo = ontology_repo
        self._revert = revert_service
        self._policies = approval_policies
        self._apply_rules = tuple(apply_rules)
        self._transaction_scope = transaction_scope
        self._event_publisher = event_publisher
        # One lock per proposal: a desktop app runs one process, so two requests
        # deciding on the same proposal are serialized here.
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    # ------------------------------------------------------------------ propose

    def propose(
        self,
        taxonomy_id: str,
        title: str,
        operations: Sequence[OperationDraft],
        source: ProposalSource,
        rationale: str | None = None,
        source_detail: str | None = None,
        dry_run: bool = False,
        source_revision: SourceRevision | None = None,
        client_metadata: Mapping[str, Any] | None = None,
    ) -> ChangeProposal:
        """
        Validate and store a proposal; every operation starts pending.

        Each operation is checked against the current graph: its target exists,
        its fields are ones it may set, a create has its required fields, id
        fields point at existing entities of the right kind or at the ref of an
        earlier create, and no two operations touch the same field of the same
        target (or a target another operation deletes). Scope is computed and
        `base` captured from the target's current values (its whole snapshot
        for a delete).

        Operations the taxonomy's approval policy allows are then applied at
        once, under the proposal's run (see `domain.versioning.approval_policy`).

        Args:
            dry_run: Validate only: return the proposal, scopes and bases filled
                in, without storing or applying anything
            source_revision: The revision of the taxonomy's external source the
                proposal was drafted against; without one, the revision the
                taxonomy was last imported at, if it records one
            client_metadata: Kept on the proposal for the proposing client
                (see ChangeProposal.client_metadata)

        Returns:
            The stored proposal, with any auto-applied outcomes (with dry_run,
            the unstored proposal)

        Raises:
            ProposalValidationError: With every problem found; nothing is stored
        """
        errors: list[OperationError] = []
        taxonomy = self._repo.get_taxonomy(taxonomy_id)
        if taxonomy is None:
            errors.append(OperationError(None, "taxonomy_not_found", f"No taxonomy {taxonomy_id}"))
        elif source_revision is None:
            source_revision = taxonomy.source_revision
        if not operations:
            errors.append(
                OperationError(None, "invalid", "A proposal needs at least one operation")
            )
        for name, value, limit in (
            ("title", title, MAX_TITLE_CHARS),
            ("rationale", rationale, MAX_RATIONALE_CHARS),
        ):
            if isinstance(value, str) and len(value) > limit:
                errors.append(
                    OperationError(
                        None, "too_long", f"{name} is {len(value)} characters; at most {limit}"
                    )
                )

        built: list[ProposedOperation] = []
        refs: dict[str, OperationKind] = {}
        touched: dict[tuple[str, str], int] = {}
        deleted: dict[str, int] = {}
        seen_seqs: set[int] = set()
        for draft in sorted(operations, key=lambda d: d.seq):
            try:
                seq = draft.seq
                if isinstance(seq, bool) or not isinstance(seq, int) or not 0 <= seq <= MAX_SEQ:
                    raise _Invalid("invalid", f"seq must be an integer from 0 to {MAX_SEQ}")
                if draft.seq in seen_seqs:
                    raise _Invalid("invalid", "seq values must be unique")
                seen_seqs.add(draft.seq)
                operation = self._validated(draft, refs)
                self._check_conflicts(operation, touched, deleted)
                built.append(operation)
            except _Invalid as exc:
                errors.append(OperationError(draft.seq, exc.code, exc.message))
            if draft.ref and draft.op == OperationType.CREATE:
                # Register the ref even when the create is invalid, so its
                # dependents report the create's error rather than unknown_ref.
                try:
                    refs.setdefault(draft.ref, OperationKind(draft.kind))
                except ValueError:
                    pass

        try:
            proposal = ChangeProposal(
                id=str(uuid4()),
                taxonomy_id=taxonomy_id,
                title=title,
                rationale=rationale,
                source=ProposalSource(source),
                source_detail=source_detail,
                created_at=datetime.now(timezone.utc),
                operations=built,
                source_revision=source_revision,
                client_metadata=dict(client_metadata or {}),
            )
        except ValueError as exc:
            errors.append(OperationError(None, "invalid", str(exc)))
        if errors:
            raise ProposalValidationError(errors)
        if dry_run:
            return proposal
        return self._auto_apply(self._proposals.create(proposal))

    # --------------------------------------------------------------- auto-apply

    def _auto_apply(self, proposal: ChangeProposal) -> ChangeProposal:
        """
        Apply what the taxonomy's approval policy allows, under the proposal's run.

        Never raises: the proposal is already stored, so an error (a stored
        policy that no longer parses, a failing repository) is logged and the
        proposal returned as it stands, its status settled, for review.
        """
        if self._policies is None:
            return proposal
        try:
            auto = self._policy_auto_apply_ids(proposal)
            # apply takes the proposal's lock itself; propose never holds it.
            if not auto:
                return proposal
            return self.apply(proposal.id, auto, decided_by=DECIDED_BY_POLICY)
        except Exception:  # noqa: BLE001 - the stored proposal must reach the caller
            _logger.exception("Auto-apply of proposal %s failed; left for review", proposal.id)
        try:
            with self._lock(proposal.id):
                current = self._get(proposal.id)
                current.settle_status()
                self._proposals.set_status(current.id, current.status)
                return current
        except Exception:  # noqa: BLE001
            _logger.exception("Could not re-read proposal %s after auto-apply", proposal.id)
            return proposal

    def auto_apply_operation_ids(self, proposal: ChangeProposal) -> list[str]:
        """
        Ids of the operations the taxonomy's approval policy applies as soon as
        they are proposed, in seq order: the same selection `_auto_apply` makes,
        so a dry run's verdict and a real propose share one path. A
        relationship-type delete still in use is never among them. Empty without
        a policy, or when the stored policy can't be read (propose then leaves
        everything for review too).
        """
        if self._policies is None:
            return []
        try:
            return self._policy_auto_apply_ids(proposal)
        except Exception:  # noqa: BLE001 - as in _auto_apply: nothing applies
            _logger.exception("Approval policy of %s could not be read", proposal.taxonomy_id)
            return []

    def _policy_auto_apply_ids(self, proposal: ChangeProposal) -> list[str]:
        """
        What the policy allows, less the relationship-type deletes still in use:
        applying one as proposed would fail, so it waits for a reviewer to
        resolve its relationships. Nothing auto-applies to a mirrored taxonomy:
        its source applies a change first, so a person decides each one.
        """
        taxonomy = self._repo.get_taxonomy(proposal.taxonomy_id)
        if taxonomy is None or taxonomy.mirrored:
            return []
        creates = {o.ref: o for o in proposal.operations if o.ref}
        inspector = InUseInspector(self._repo)
        allowed = auto_apply_ids(
            self._policies.get(proposal.taxonomy_id) if self._policies else None,
            proposal.operations,
            lambda operation: self._classes(operation, creates, inspector),
            lambda operation: self._inside_taxonomy(operation, proposal.taxonomy_id),
            id_fields=frozenset(ID_FIELDS),
            source=proposal.source,
        )
        if not allowed:
            return allowed
        blocked = self.in_use_blockers(proposal)
        return [i for i in allowed if i not in blocked]

    def _classes(
        self,
        operation: ProposedOperation,
        creates: Mapping[str, ProposedOperation],
        inspector: InUseInspector,
    ) -> list[set[str]]:
        """
        Per class the operation's entity is typed by, the keys a policy rule may
        name it by: the id and identifier of the class and of every class above
        it (a rule naming a class covers its subclasses too).

        The classes are an individual's current classes plus any it is given;
        an attribute's class; a class itself, or for a class create its
        proposed parent (none at the top of a scheme); and for a relationship,
        the classes of its source and of its target (a class end is its own
        class). A "$ref" class is keyed by its create's identifier and parent.
        """
        target, fields = operation.target_id, operation.fields
        class_ids: list[Any] = []
        if operation.kind is K.INDIVIDUAL:
            individual = self._repo.get_individual(target) if target else None
            class_ids = list(individual.class_ids if individual else [])
            class_ids += [c for c in fields.get("class_ids") or [] if c not in class_ids]
        elif operation.kind is K.ATTRIBUTE:
            attribute = self._repo.get_attribute_definition(target) if target else None
            class_ids = [attribute.class_id if attribute else fields.get("class_id")]
        elif operation.kind is K.CLASS:
            parent = fields.get("parent_class_id")
            class_ids = [target] if target else [parent] if parent is not None else []
        elif operation.kind is K.RELATIONSHIP:
            relationship = self._repo.get_relationship(target) if target else None
            if relationship is not None:
                ends = [relationship.source_id, relationship.target_id]
            else:
                ends = [fields.get("source_id"), fields.get("target_id")]
            for end in ends:
                class_ids += self._end_class_ids(end, creates)
        return [self._class_keys(c, creates, inspector) for c in class_ids]

    def _end_class_ids(self, end: Any, creates: Mapping[str, ProposedOperation]) -> list[Any]:
        """A relationship end's classes: an individual's, or a class end itself (None: unknown)."""
        if not isinstance(end, str):
            return [None]
        if _is_ref(end):
            create = creates.get(end[1:])
            if create is not None and create.kind is K.INDIVIDUAL:
                return list(create.fields.get("class_ids") or []) or [None]
            return [end] if create is not None and create.kind is K.CLASS else [None]
        individual = self._repo.get_individual(end)
        if individual is not None:
            return list(individual.class_ids) or [None]
        return [end] if self._repo.get_class(end) is not None else [None]

    def _class_keys(
        self,
        class_id: Any,
        creates: Mapping[str, ProposedOperation],
        inspector: InUseInspector,
    ) -> set[str]:
        """The ids and identifiers of a class and every class above it."""
        if not isinstance(class_id, str):
            return set()
        if _is_ref(class_id):
            # A class the proposal creates: its identifier, then its parent's keys
            # (a ref only points at an earlier create, so this ends).
            create = creates.get(class_id[1:])
            if create is None or create.kind is not K.CLASS:
                return set()
            identifier = create.fields.get("identifier")
            keys = {identifier} if isinstance(identifier, str) and identifier else set()
            return keys | self._class_keys(create.fields.get("parent_class_id"), creates, inspector)
        keys: set[str] = set()
        for ancestor_id in inspector.ancestors_of(class_id):
            keys.add(ancestor_id)
            cls = self._repo.get_class(ancestor_id)
            if cls is not None and cls.identifier:
                keys.add(cls.identifier)
        return keys

    def _inside_taxonomy(self, operation: ProposedOperation, taxonomy_id: str) -> bool:
        """
        Whether the operation's target and every existing entity its id fields
        point at belong to this taxonomy alone. "$ref" values are skipped (their
        creates are checked themselves). Property definitions are global: an
        operation on one is never inside, but a relationship may use one.
        """
        if operation.kind is K.PROPERTY:
            return False
        if operation.kind is K.TAXONOMY:
            return operation.op is not OperationType.CREATE and operation.target_id == taxonomy_id
        if operation.target_id is not None and self._taxonomies(
            (operation.kind,), operation.target_id
        ) != {taxonomy_id}:
            return False
        for name, value in operation.fields.items():
            kinds = ID_FIELDS.get(name)
            if kinds is None or value is None or name == "property_definition_id":
                continue
            for item in value if isinstance(value, list) else [value]:
                if _is_ref(item):
                    continue
                if self._taxonomies(kinds, item) != {taxonomy_id}:
                    return False
        return True

    def _taxonomies(self, kinds: tuple[OperationKind, ...], entity_id: Any) -> set[str]:
        """The taxonomies an entity of one of these kinds belongs to (empty if none or missing)."""
        for kind in kinds:
            entity = self._load(kind, entity_id)
            if entity is None:
                continue
            if kind is K.TAXONOMY:
                return {entity.id}
            if kind in (K.SCHEME, K.CLASS):
                return {entity.taxonomy_id}
            if kind is K.ATTRIBUTE:
                return self._taxonomies((K.CLASS,), entity.class_id)
            if kind is K.INDIVIDUAL:
                found: set[str] = set()
                for class_id in entity.class_ids:
                    found |= self._taxonomies((K.CLASS,), class_id)
                return found
            if kind is K.RELATIONSHIP:
                ends = (K.CLASS, K.INDIVIDUAL)
                return self._taxonomies(ends, entity.source_id) | self._taxonomies(
                    ends, entity.target_id
                )
            return set()  # a property definition is global
        return set()

    def _validated(
        self, draft: OperationDraft, refs: dict[str, OperationKind]
    ) -> ProposedOperation:
        """Build one ProposedOperation from a draft, checked against the graph."""
        probability = draft.probability
        if probability is not None and (
            isinstance(probability, bool) or not isinstance(probability, (int, float))
        ):
            raise _Invalid("invalid", f"probability must be a number, not {probability!r}")
        if draft.target_id is not None and not isinstance(draft.target_id, str):
            raise _Invalid("invalid", f"target_id must be a string, not {draft.target_id!r}")
        try:
            op = OperationType(draft.op)
            kind = OperationKind(draft.kind)
            claimed = ChangeScope(draft.claimed_scope) if draft.claimed_scope else None
            if not isinstance(draft.fields or {}, dict):
                raise ValueError("fields must be an object")
            if not isinstance(draft.evidence or [], list):
                raise ValueError("evidence must be a list")
            for item in draft.evidence or []:
                if not isinstance(item, dict) or not all(
                    isinstance(k, str) and isinstance(v, str) for k, v in item.items()
                ):
                    raise ValueError(
                        'each evidence item must be an object of text values ("quote",'
                        f' "url", "entity_id"), not {item!r}'
                    )
            operation = ProposedOperation(
                seq=draft.seq,
                op=op,
                kind=kind,
                target_id=draft.target_id,
                ref=draft.ref,
                fields=dict(draft.fields or {}),
                rationale=draft.rationale,
                evidence=list(draft.evidence or []),
                probability=probability,
            )
        except (TypeError, ValueError) as exc:
            raise _Invalid("invalid", str(exc)) from exc

        if op is OperationType.CREATE and operation.ref and operation.ref in refs:
            raise _Invalid("duplicate_ref", f"ref '{operation.ref}' is already used")
        self._check_field_names(operation)
        self._check_values(operation)
        self._check_id_fields(operation, refs)
        operation.proposed_replacement_id = self._replacement_id(draft.replacement, operation, refs)

        target = None
        if op is not OperationType.CREATE:
            target = self._load(kind, operation.target_id)  # type: ignore[arg-type]
            if target is None:
                raise _Invalid("target_not_found", f"No {kind.value} {operation.target_id}")
        if op is OperationType.MOVE and kind is K.CLASS:
            self._check_class_move(operation, target)

        if op is OperationType.DELETE:
            operation.base = entity_snapshot(target)
        elif op is not OperationType.CREATE:
            snapshot = entity_snapshot(target)
            operation.base = {name: snapshot.get(name) for name in operation.fields}
            if DATA_FIELD in operation.fields:
                # Only the values the update touches: absent ones as None.
                current = _data_values(snapshot.get(DATA_FIELD))
                operation.base[DATA_FIELD] = {
                    key: current.get(key) for key in operation.fields[DATA_FIELD]
                }
        others = {name: value for name, value in operation.fields.items() if name != DATA_FIELD}
        operation.scope = classify_scope(op, others, operation.base, claimed)
        if kind is K.INDIVIDUAL and DATA_FIELD in operation.fields:
            attributes = self._check_data_proposed(operation, target)
            data_scope = self._data_scope(operation, attributes)
            if data_scope.rank > operation.scope.rank:
                operation.scope = data_scope
        return operation

    def _check_data_proposed(
        self, operation: ProposedOperation, target: Any
    ) -> dict[str, AttributeDefinition]:
        """
        An individual operation's data_properties fit the attributes of the
        classes it will have; returns those attributes. A create's values can't
        be null. Attributes of a "$ref" class aren't known yet: values the
        existing classes don't define are checked when applied.
        """
        values = operation.fields[DATA_FIELD]
        if operation.op is OperationType.CREATE:
            nulls = sorted(key for key, value in values.items() if value is None)
            if nulls:
                raise _Invalid("invalid", f"data_properties {nulls} can't be null on a create")
        class_ids = operation.fields.get("class_ids") or (target.class_ids if target else [])
        attributes = self._attributes_of(class_ids)
        present = _data_values(entity_snapshot(target).get(DATA_FIELD)) if target else {}
        try:
            self._check_data(
                values, attributes, present, deferred=any(_is_ref(c) for c in class_ids)
            )
        except ValueError as exc:
            raise _Invalid("invalid", str(exc)) from exc
        return attributes

    @staticmethod
    def _data_scope(
        operation: ProposedOperation, attributes: dict[str, AttributeDefinition]
    ) -> ChangeScope:
        """
        Setting a value that wasn't there is additive; changing or removing one
        is editorial, or breaking for a required attribute.
        """
        if operation.op is OperationType.CREATE:
            return ChangeScope.ADDITIVE
        scope = ChangeScope.EDITORIAL
        base = operation.base.get(DATA_FIELD) or {}
        for key, value in operation.fields[DATA_FIELD].items():
            current = base.get(key)
            if current is None and value is not None:
                found = ChangeScope.ADDITIVE
            elif value == current and type(value) is type(current):
                continue
            else:
                attribute = attributes.get(key)
                required = attribute is not None and attribute.is_required
                found = ChangeScope.BREAKING if required else ChangeScope.EDITORIAL
            if found.rank > scope.rank:
                scope = found
        return scope

    def _attributes_of(self, class_ids: Iterable[Any]) -> dict[str, AttributeDefinition]:
        """
        The attributes an individual of these classes has: each class's own,
        then its parent's and so on up; the first class (in order) to define
        an identifier wins. "$ref" classes are skipped.
        """
        found: dict[str, AttributeDefinition] = {}
        for class_id in class_ids:
            current, seen = class_id, set()
            while isinstance(current, str) and not _is_ref(current) and current not in seen:
                seen.add(current)
                for attribute in self._repo.list_attribute_definitions(
                    class_id=current, limit=None
                ):
                    found.setdefault(attribute.identifier, attribute)
                cls = self._repo.get_class(current)
                current = cls.parent_class_id if cls is not None else None
        return found

    @staticmethod
    def _check_data(
        values: Mapping[str, Any],
        attributes: dict[str, AttributeDefinition],
        present: Mapping[str, Any],
        deferred: bool = False,
    ) -> None:
        """
        Each value is for one of the attributes and fits it; None removes a
        value (one the individual has may be removed even if no attribute
        defines it any more).

        Args:
            deferred: Skip values no attribute defines (a "$ref" class may)

        Raises:
            ValueError: Naming the first value that doesn't fit, and why
        """
        for key, value in values.items():
            attribute = attributes.get(key)
            if attribute is None:
                if deferred or (value is None and key in present):
                    continue
                known = ", ".join(sorted(attributes)) or "none"
                raise ValueError(
                    f"data_properties '{key}' is not an attribute of the individual's classes "
                    f"(theirs and inherited: {known})"
                )
            if value is None:
                continue
            problem = _value_problem(attribute, value)
            if problem:
                raise ValueError(f"data_properties '{key}' {problem}")

    def _data_for(
        self, class_ids: list[str], values: Mapping[str, Any], current: list[DataPropertyValue]
    ) -> list[DataPropertyValue]:
        """
        An individual's attribute values once these are set (None removes
        one), checked against its classes' attributes as they are now.

        Raises:
            ValueError: If a value doesn't fit
        """
        attributes = self._attributes_of(class_ids)
        by_key = {value.property_identifier: value for value in current}
        self._check_data(values, attributes, by_key)
        for key, value in values.items():
            if value is None:
                by_key.pop(key, None)
            else:
                datatype = _DATATYPE_HINTS[DataType(attributes[key].datatype)]
                by_key[key] = DataPropertyValue(key, value, datatype)
        return list(by_key.values())

    def _replacement_id(
        self, name: Any, operation: ProposedOperation, refs: dict[str, OperationKind]
    ) -> str | None:
        """
        A delete's named replacement, resolved: an existing entity of the same
        kind (named by id or identifier), or "$<ref>" of an earlier create of
        that kind. Property (relationship type) and class deletes may name one.
        """
        if name is None:
            return None
        kind = operation.kind
        if operation.op is not OperationType.DELETE or kind not in _REPLACEABLE:
            raise _Invalid(
                "invalid",
                "Only a property (relationship type) or class delete can name a replacement",
            )
        what = _REPLACEABLE[kind]
        if not isinstance(name, str) or not name:
            raise _Invalid(
                "invalid", f'replacement must be a {what} id, identifier or "$<ref>", not {name!r}'
            )
        if _is_ref(name):
            ref_kind = refs.get(name[1:])
            if ref_kind is None:
                raise _Invalid(
                    "unknown_ref", f"replacement {name} names no create earlier in the proposal"
                )
            if ref_kind is not kind:
                raise _Invalid(
                    "replacement_not_found",
                    f"replacement {name} is a {ref_kind.value}, not a {kind.value}",
                )
            return name
        if kind is K.PROPERTY:
            found = self._repo.get_property_definition(
                name
            ) or self._repo.get_property_definition_by_identifier(name)
        else:
            found = self._repo.get_class(name)
            if found is None:
                by_identifier = self._repo.get_by_identifier(name)
                found = by_identifier if isinstance(by_identifier, Class) else None
        if found is None:
            raise _Invalid(
                "replacement_not_found",
                f"replacement {name} is not the id or identifier of a {what}",
            )
        if found.id == operation.target_id:
            raise _Invalid("invalid", f"A {what} can't replace itself")
        return found.id

    @staticmethod
    def _check_field_names(operation: ProposedOperation) -> None:
        spec = OPERATION_FIELDS[operation.kind]
        names = set(operation.fields)
        if operation.op is OperationType.CREATE:
            allowed, label = spec.create, "create"
            missing = sorted(
                name for name in spec.required if operation.fields.get(name) in (None, "", [])
            )
            if missing:
                raise _Invalid("missing_field", f"A {operation.kind.value} create needs {missing}")
        elif operation.op is OperationType.UPDATE:
            allowed, label = spec.update, "update"
            cleared = sorted(
                name
                for name, value in operation.fields.items()
                if value is None and name in allowed and name not in spec.clearable
            )
            if cleared:
                raise _Invalid("invalid", f"{cleared} can't be cleared")
        elif operation.op is OperationType.DELETE:
            if names:
                raise _Invalid("unknown_field", "A delete takes no fields")
            return
        else:
            return  # a move's fields are checked by ProposedOperation
        unknown = sorted(names - allowed)
        if unknown:
            raise _Invalid("unknown_field", f"A {operation.kind.value} {label} can't set {unknown}")

    @staticmethod
    def _check_values(operation: ProposedOperation) -> None:
        """Each value has its field's type, and encoded values decode to their domain types."""
        for name, value in operation.fields.items():
            if value is None:
                continue
            if not _has_field_type(name, value):
                raise _Invalid("invalid", f"{name} has the wrong type: {value!r}")
            if name == "class_ids":
                if not value:
                    raise _Invalid("invalid", "class_ids can't be empty")
                if len(set(value)) != len(value):
                    raise _Invalid("invalid", "class_ids has duplicates")
            if name == DATA_FIELD:
                continue  # an identifier -> value map, checked against the classes
            try:
                decode_field(name, value)
            except (TypeError, KeyError, ValueError, AttributeError) as exc:
                raise _Invalid("invalid", f"{name} is not valid: {exc}") from exc

    def _check_id_fields(
        self, operation: ProposedOperation, refs: dict[str, OperationKind]
    ) -> None:
        """Each id field names an existing entity of an allowed kind, or an earlier ref."""
        for name, value in operation.fields.items():
            kinds = ID_FIELDS.get(name)
            if kinds is None or value is None:
                continue
            values = value if isinstance(value, list) else [value]
            for item in values:
                if _is_ref(item):
                    ref_kind = refs.get(item[1:])
                    if ref_kind is None:
                        raise _Invalid(
                            "unknown_ref",
                            f"{name} {item} names no create earlier in the proposal",
                        )
                    if ref_kind not in kinds:
                        raise _Invalid(
                            "endpoint_not_found",
                            f"{name} {item} is a {ref_kind.value}, not a "
                            f"{' or '.join(k.value for k in kinds)}",
                        )
                elif not any(self._load(kind, item) is not None for kind in kinds):
                    raise _Invalid(
                        "endpoint_not_found",
                        f"{name} {item} is not an existing "
                        f"{' or '.join(k.value for k in kinds)}",
                    )

    def _check_class_move(self, operation: ProposedOperation, cls: Any) -> None:
        """A class changing scheme also names its new parent (or None) and has no subclasses."""
        if "concept_scheme_id" not in operation.fields:
            return
        if "parent_class_id" not in operation.fields:
            raise _Invalid(
                "missing_field",
                "A class moving to another scheme needs parent_class_id (a class in "
                "that scheme, or null)",
            )
        if self._repo.list_classes(parent_class_id=cls.id, limit=1):
            raise _Invalid("invalid", "A class with subclasses can't move to another scheme")
        parent_id = operation.fields["parent_class_id"]
        scheme_id = operation.fields["concept_scheme_id"]
        if parent_id is None or _is_ref(parent_id) or _is_ref(scheme_id):
            return
        parent = self._repo.get_class(parent_id)
        if parent is not None and parent.concept_scheme_id != scheme_id:
            raise _Invalid("invalid", f"parent_class_id {parent_id} is not in scheme {scheme_id}")

    @staticmethod
    def _check_conflicts(
        operation: ProposedOperation,
        touched: dict[tuple[str, str], int],
        deleted: dict[str, int],
    ) -> None:
        """
        No two operations touch the same field of one target, and a deleted target
        appears in no other operation: the later one would always be stale.
        """
        target = operation.target_id
        if target is None:
            return
        if target in deleted:
            raise _Invalid("conflicting_op", f"seq {deleted[target]} already deletes {target}")
        if operation.op is OperationType.DELETE:
            earlier = sorted({seq for (t, _), seq in touched.items() if t == target})
            if earlier:
                raise _Invalid("conflicting_op", f"{target} is also changed by seq {earlier[0]}")
            deleted[target] = operation.seq
            return
        for name in operation.fields:
            if (target, name) in touched:
                raise _Invalid(
                    "conflicting_op",
                    f"seq {touched[(target, name)]} already changes {name} of {target}",
                )
        for name in operation.fields:
            touched[(target, name)] = operation.seq

    # -------------------------------------------------------------------- apply

    def apply(
        self,
        proposal_id: str,
        operation_ids: Iterable[str],
        force_stale: Iterable[str] = (),
        edits: Mapping[str, dict[str, Any]] | None = None,
        resolutions: Mapping[str, InUseResolution] | None = None,
        decided_by: str = DECIDED_BY_USER,
        chosen_alternatives: Mapping[str, dict[str, Any]] | None = None,
    ) -> ChangeProposal:
        """
        Apply the chosen operations, in seq order, under the proposal's run id.

        Each operation that applies records a decision (see `domain.versioning.gold`)
        by decided_by: applied, or applied_with_edits when edited.

        Pending and failed operations can be applied (a failed one again, e.g.
        with force_stale after a target_changed). Each records its own outcome:
        applied with the entity it made or changed, or failed with a reason
        (target_changed, target_missing, unresolved_ref, invalid_edit, refused,
        error). Operations already applied stay applied when a later one fails.
        Property-definition creates and updates are also checked by the rules
        that govern them, if any (refused).

        A reviewer can correct a property-definition update or delete before
        applying it: its edit is the complete set of fields to apply, as an
        update, instead of the proposed ones (an edited delete keeps its seq and
        applies as an update). The edit is checked like a proposed update, then
        by the rules that govern its target, if any; a problem fails only that
        operation (invalid_edit). Staleness still compares the proposed base,
        so fields only the edit touches are not checked for it. An applied edit
        is recorded as the operation's applied_fields, and its scope is
        recomputed from them; a failed one records nothing, so applying the
        operation again without an edit applies it as proposed.

        A relationship-type (property) delete that relationships still use fails
        as proposed (in use). A resolution lets it apply: move those
        relationships to another type (each must fit its domain and range,
        inheritance-aware, allow its attributes and not duplicate one, or
        nothing moves; a type whose domain and range are the deleted type's
        reversed takes each with its ends swapped), or delete them too; then the
        type is deleted. The steps run through OntologyService in one
        transaction under the proposal's run, so a failing step keeps none of
        them (unresolvable, or the step's error) and Revert restores the type
        and its relationships together. An applied resolution is recorded with
        the relationships it moved or deleted; a failed one records nothing,
        like an edit.

        A relationship-type update (proposed or edited) migrates the
        relationships using the type in the same transaction: one that
        reverses its domain and range swaps the ends of each in place (same id,
        attributes and provenance); a rename keeps them as they are. A
        retarget (another pair of classes) of a type relationships use needs a
        resolution, as an in-use delete does: move them to another type or
        delete them first (only a retarget takes one; see `in_use_blockers`).
        Each applied property create, update and delete records what it did
        to the type and its relationships as its type_change, which its schema
        change record is read from (`domain.versioning.change_records`).
        Revert undoes the update and the migration together.

        Args:
            proposal_id: The proposal
            operation_ids: The operations to apply
            force_stale: Operations to apply even if their target changed since proposed
            edits: Operation id -> the fields to apply instead of the proposed ones
            resolutions: Operation id -> how to resolve the relationships still
                using the relationship type a delete removes, or a retarget
                no longer fits
            decided_by: Who decided: "user" (a reviewer), "policy" (auto-apply)
                or an agent source
            chosen_alternatives: Operation id -> the alternative the reviewer
                chose over the proposal's pick, recorded in its decision when
                it applies

        Returns:
            The proposal with updated outcomes

        Raises:
            ChangeProposalNotFoundError: If the proposal does not exist
            ChangeProposalStateError: If the proposal is reverted, or an operation
                is already applied or rejected; nothing is applied
            ValueError: If an operation id is not in the proposal, or an edit is
                misplaced (its operation isn't being applied or isn't a property
                update or delete, it is empty, or it points at a "$ref"), or a
                resolution is (its operation isn't being applied, isn't a
                property delete or update), or a chosen alternative is (its
                operation isn't being applied with an edit, or it is empty);
                nothing is applied
        """
        with self._lock(proposal_id):
            proposal = self._get(proposal_id)
            if proposal.status is ProposalStatus.REVERTED:
                raise ChangeProposalStateError(f"Change proposal {proposal_id} is reverted")
            chosen = self._chosen(proposal, operation_ids, "apply")
            edits = dict(edits or {})
            self._check_edits_placed(chosen, edits)
            resolutions = dict(resolutions or {})
            self._check_resolutions_placed(proposal, chosen, edits, resolutions)
            alternatives = dict(chosen_alternatives or {})
            self._check_alternatives_placed(chosen, edits, alternatives)
            force = set(force_stale)
            refs = {o.ref: o for o in proposal.operations if o.ref}

            proposed = {o.id: proposed_snapshot(o) for o in chosen}
            previous_run = get_current_batch_run_id()
            set_batch_run_context(proposal.id)
            try:
                for operation in chosen:
                    forced = operation.id in force
                    resolution = resolutions.get(operation.id)
                    # Per operation: relationship deletes applied earlier in this call are gone.
                    covered = self._covered(proposal)
                    if operation.id in edits:
                        others = {i: e for i, e in edits.items() if i != operation.id}
                        edit = edits[operation.id]
                        self._apply_edited(
                            proposal, operation, edit, others, forced, resolution, covered
                        )
                    elif resolution is not None and operation.op is OperationType.DELETE:
                        self._apply_resolved(
                            operation, resolution, refs, proposal.id, forced, covered
                        )
                    else:
                        self._apply_one(operation, refs, proposal.id, forced, resolution, covered)
                    decisions = []
                    if operation.status is OperationStatus.APPLIED:
                        decisions.append(
                            decision_of(
                                proposal,
                                operation,
                                decided_by,
                                datetime.now(timezone.utc),
                                proposed[operation.id],
                                chosen_alternative=alternatives.get(operation.id),
                            )
                        )
                    self._proposals.save_operations(proposal.id, [operation], decisions)
            finally:
                set_batch_run_context(previous_run)

            proposal.settle_status()
            self._proposals.set_status(proposal.id, proposal.status)
            return self._get(proposal_id)

    @staticmethod
    def _check_edits_placed(
        chosen: list[ProposedOperation], edits: dict[str, dict[str, Any]]
    ) -> None:
        """Each edit is a non-empty object for a property update or delete being applied."""
        by_id = {o.id: o for o in chosen}
        misplaced = sorted(i for i in edits if i not in by_id)
        if misplaced:
            raise ValueError(f"Edits for operations not being applied: {misplaced}")
        for operation_id, fields in edits.items():
            operation = by_id[operation_id]
            label = f"seq {operation.seq}"
            if operation.kind is not K.PROPERTY or operation.op not in (
                OperationType.UPDATE,
                OperationType.DELETE,
            ):
                raise ValueError(
                    f"{label} is a {operation.kind.value} {operation.op.value}; only a "
                    "property update or delete can be edited"
                )
            if not isinstance(fields, dict) or not fields:
                raise ValueError(f"{label}: an edit needs at least one field")
            refs = sorted(
                name for name, value in fields.items() if name in ID_FIELDS and _is_ref(value)
            )
            if refs:
                raise ValueError(f"{label}: an edit can't point at a $ref ({refs})")

    @staticmethod
    def _check_alternatives_placed(
        chosen: list[ProposedOperation],
        edits: dict[str, dict[str, Any]],
        alternatives: dict[str, dict[str, Any]],
    ) -> None:
        """Each chosen alternative is non-empty, for an operation being applied with an edit."""
        misplaced = sorted(set(alternatives) - {o.id for o in chosen})
        if misplaced:
            raise ValueError(f"Chosen alternatives for operations not being applied: {misplaced}")
        for operation_id, alternative in alternatives.items():
            if not isinstance(alternative, dict) or not alternative:
                raise ValueError(f"The chosen alternative for {operation_id} is empty")
            if operation_id not in edits:
                raise ValueError(
                    f"The chosen alternative for {operation_id} needs the edit that applies it"
                )

    @staticmethod
    def _check_resolutions_placed(
        proposal: ChangeProposal,
        chosen: list[ProposedOperation],
        edits: dict[str, dict[str, Any]],
        resolutions: dict[str, InUseResolution],
    ) -> None:
        """
        Each resolution is for a property delete or update being applied (an
        edited delete applies as an update, so its resolution is a retarget's),
        and doesn't move relationships to a type the proposal also deletes. A
        delete this call applies with an edit keeps its type (it applies as an
        update), so relationships can move to it. Operations apply in seq
        order: if that edit retargets the type after the move, the retarget
        fails for want of a resolution of the moved relationships; if the edit
        fails, the moved relationships stay on the type, whose delete stays
        awaiting and blocked by them. Either way nothing is half-applied.
        """
        deleted = {
            o.target_id: o.seq
            for o in proposal.pending
            if o.kind is K.PROPERTY and o.op is OperationType.DELETE and o.id not in edits
        }
        by_id = {o.id: o for o in chosen}
        misplaced = sorted(i for i in resolutions if i not in by_id)
        if misplaced:
            raise ValueError(f"Resolutions for operations not being applied: {misplaced}")
        for operation_id in resolutions:
            operation = by_id[operation_id]
            if operation.kind is not K.PROPERTY or operation.op not in (
                OperationType.DELETE,
                OperationType.UPDATE,
            ):
                raise ValueError(
                    f"seq {operation.seq} is a {operation.kind.value} {operation.op.value}; "
                    "only a property delete or update takes a resolution"
                )
            replacement = resolutions[operation_id].replacement_property_id
            if replacement is not None and replacement in deleted:
                raise ValueError(
                    f"seq {operation.seq} moves its relationships to {replacement}, which "
                    f"seq {deleted[replacement]} deletes"
                )

    def _rules_for(
        self, operation: ProposedOperation, fields: dict[str, Any]
    ) -> ProposalApplyRules | None:
        """The rules that govern a property operation, if any."""
        return next((r for r in self._apply_rules if r.governs(operation, fields)), None)

    def _apply_edited(
        self,
        proposal: ChangeProposal,
        operation: ProposedOperation,
        edit: dict[str, Any],
        other_edits: dict[str, dict[str, Any]],
        forced: bool,
        resolution: InUseResolution | None = None,
        covered: Mapping[str, int] | None = None,
    ) -> None:
        """Apply a reviewer's edit of a property update or delete, as an update."""

        def run() -> str:
            self._check_fresh(operation, forced)
            fields = self._checked_edit(operation, edit)
            rules = self._rules_for(operation, fields)
            if rules is not None:
                try:
                    fields = rules.prepare(proposal, operation, fields, other_edits)
                except ValueError as exc:
                    raise _ApplyFailed(INVALID_EDIT, str(exc)) from exc
                fields = self._checked_edit(operation, fields)
            target_id: str = operation.target_id  # type: ignore[assignment]
            before = entity_snapshot(self._load(K.PROPERTY, target_id))
            result = self._update_type(
                operation,
                fields,
                resolution,
                proposal.id,
                lambda: self._dispatch(operation, fields, proposal.id, OperationType.UPDATE),
                covered,
            )
            base = {
                name: operation.base[name] if name in operation.base else before.get(name)
                for name in fields
            }
            operation.applied_fields = fields
            # Keep what the applied fields replaced, so the change reads before -> after.
            operation.base = {**operation.base, **base}
            operation.scope = classify_scope(OperationType.UPDATE, fields, base)
            return result

        self._record_outcome(operation, proposal.id, run)

    def _apply_resolved(
        self,
        operation: ProposedOperation,
        resolution: InUseResolution,
        refs: dict[str, ProposedOperation],
        run_id: str,
        forced: bool,
        covered: Mapping[str, int] | None = None,
    ) -> None:
        """
        Apply a relationship-type delete with a resolution of the relationships
        using it: move or delete each, then delete the type, in one transaction.
        """

        def run() -> str:
            self._check_fresh(operation, forced)
            target_id: str = operation.target_id  # type: ignore[assignment]
            before = self._type_fields(target_id)
            with self._atomic():
                inspector = InUseInspector(self._repo)
                edges = inspector.edges(target_id)
                _check_uncovered(
                    (e.relationship_id for e in edges), covered, needs_resolution=False
                )
                taxonomies = self._taxonomies_of(edges)
                resolved, replacement, swap = self._resolve_edges(
                    target_id, resolution, inspector, edges, run_id
                )
                self._ontology.delete_property_definition(target_id)
            # Committed: invalidate again, so no graph rebuilt mid-transaction stays cached.
            for taxonomy_id in sorted(taxonomies):
                self._invalidate_graph(taxonomy_id)
            # Nothing used the type after all: it applied as proposed.
            if not resolved:
                operation.type_change = self._delete_change(before, operation, refs)
                return target_id
            operation.resolution = _recorded(resolution, resolved, replacement, swap)
            operation.type_change = TypeChange(
                SchemaChangeAction.DELETE,
                before=before,
                swap=swap,
                replacement=self._type_fields(replacement.id) if replacement else None,
            )
            return target_id

        self._record_outcome(operation, run_id, run)

    def _resolve_edges(
        self,
        target_id: str,
        resolution: InUseResolution,
        inspector: InUseInspector,
        edges: list[Any],
        run_id: str,
    ) -> tuple[list[ResolvedEdge], Any, bool]:
        """
        Move the relationships using a type to the resolution's replacement, or
        delete them, inside the caller's transaction. Returns what was resolved,
        the replacement (a move) and whether the moved ones swapped ends.
        """
        expected = resolution.relationship_ids
        if expected is not None and {e.relationship_id for e in edges} != set(expected):
            raise _ApplyFailed(
                UNRESOLVABLE,
                f"the relationships using the type changed since reviewed: "
                f"{len(edges)} now, {len(set(expected))} reviewed; review them again",
            )
        replacement, swap = None, False
        if resolution.strategy is ResolutionStrategy.MOVE:
            replacement_id: str = resolution.replacement_property_id  # type: ignore
            replacement = self._repo.get_property_definition(replacement_id)
            if replacement is None or replacement.id == target_id:
                raise _ApplyFailed(UNRESOLVABLE, f"no other relationship type {replacement_id}")
            # A reversed replacement takes each relationship with its ends swapped.
            swap = reverses(self._repo.get_property_definition(target_id), replacement)
            misfits = inspector.misfits(replacement, edges, swap)
            if misfits:
                raise _ApplyFailed(
                    UNRESOLVABLE,
                    f"{len(misfits)} of {len(edges)} relationship(s) don't fit "
                    f"{replacement.identifier}: {'; '.join(misfits)}",
                )
        resolved: list[ResolvedEdge] = []
        for edge in edges:
            self._ontology.delete_relationship(edge.relationship_id)
            moved_to = None
            if replacement is not None:
                source, target = moved_ends(edge, swap)
                moved_to = self._ontology.create_relationship(
                    source.id,
                    target.id,
                    replacement.id,
                    source_run_id=run_id,
                    attributes=edge.attributes,
                ).id
            resolved.append(
                ResolvedEdge(
                    relationship_id=edge.relationship_id,
                    source_id=edge.source.id,
                    target_id=edge.target.id,
                    source_title=edge.source.title,
                    target_title=edge.target.title,
                    moved_to_id=moved_to,
                )
            )
        return resolved, replacement, swap

    def _update_type(
        self,
        operation: ProposedOperation,
        fields: dict[str, Any],
        resolution: InUseResolution | None,
        run_id: str,
        update: Callable[[], str],
        covered: Mapping[str, int] | None = None,
    ) -> str:
        """
        Run a relationship-type update with the relationships using the type
        migrated, in one transaction, and record what it did (TypeChange): a
        reverse swaps their ends in place (OntologyService.reverse_relationships);
        a rename keeps them; a retarget of a type in use needs a resolution,
        which moves or deletes them first.
        """
        target_id: str = operation.target_id  # type: ignore[assignment]
        before = self._type_fields(target_id)
        old_pair = (before.get("domain_class_id"), before.get("range_class_id"))
        new_pair = (
            fields.get("domain_class_id", old_pair[0]),
            fields.get("range_class_id", old_pair[1]),
        )
        pair = compare_pair(old_pair, new_pair)
        if resolution is not None and pair is not PairMatch.DIFFERENT:
            raise _ApplyFailed(
                UNRESOLVABLE,
                "only a retarget takes a resolution: a rename keeps the relationships "
                "using the type, and a reverse swaps their ends",
            )
        resolved: list[ResolvedEdge] = []
        replacement, swap = None, False
        with self._atomic():
            inspector = InUseInspector(self._repo)
            edges = inspector.edges(target_id) if pair is not PairMatch.SAME else []
            # A reverse swaps relationships in place and a retarget moves or deletes
            # them: neither may touch ones the proposal's own deletes still cover.
            if pair is not PairMatch.SAME:
                _check_uncovered(
                    (e.relationship_id for e in edges),
                    covered,
                    needs_resolution=pair is PairMatch.DIFFERENT and resolution is None,
                )
            if pair is PairMatch.DIFFERENT and edges and resolution is None:
                raise _ApplyFailed(
                    APPLY_ERROR,
                    f"{len(edges)} relationship(s) use the type, so a retarget needs a "
                    "resolution: move them to another type or delete them",
                )
            taxonomies = self._taxonomies_of(edges)
            if resolution is not None:
                resolved, replacement, swap = self._resolve_edges(
                    target_id, resolution, inspector, edges, run_id
                )
            result = update()
            if pair is PairMatch.REVERSED and edges:
                reversed_type = self._repo.get_property_definition(target_id)
                allowed = reversed_type.edge_attribute_names() if reversed_type else set()
                unknown = sorted({name for e in edges for name in e.attributes} - allowed)
                if unknown:
                    raise _ApplyFailed(
                        UNRESOLVABLE,
                        f"its relationships carry attributes {unknown} the reversed type "
                        "no longer allows",
                    )
                self._ontology.reverse_relationships(target_id)
                swap = True
        # Committed: invalidate again, so no graph rebuilt mid-transaction stays cached.
        for taxonomy_id in sorted(taxonomies):
            self._invalidate_graph(taxonomy_id)
        after = self._type_fields(target_id)
        if resolution is not None and resolved:
            operation.resolution = _recorded(resolution, resolved, replacement, swap)
        action = {
            PairMatch.SAME: SchemaChangeAction.RENAME,
            PairMatch.REVERSED: SchemaChangeAction.REVERSE,
        }.get(pair, SchemaChangeAction.RETARGET)
        if action is not SchemaChangeAction.RENAME or before != after:
            operation.type_change = TypeChange(
                action,
                before=before,
                after=after,
                swap=swap or pair is PairMatch.REVERSED,
                replacement=self._type_fields(replacement.id) if replacement else None,
            )
        return result

    def _type_fields(self, property_id: str) -> dict[str, Any]:
        """A type's id and TYPE_KEY_FIELDS, as snapshot JSON."""
        snapshot = entity_snapshot(self._load(K.PROPERTY, property_id))
        return {"id": property_id, **{name: snapshot.get(name) for name in TYPE_KEY_FIELDS}}

    def _delete_change(
        self,
        before: dict[str, Any],
        operation: ProposedOperation,
        refs: dict[str, ProposedOperation],
    ) -> TypeChange:
        """
        A delete no relationships used: replaced by the type it names, when that
        links the same pair of classes or the reverse (`compare_pair`).
        """
        named = operation.proposed_replacement_id
        if named and _is_ref(named):
            create = refs.get(named[1:])
            applied = create is not None and create.status is OperationStatus.APPLIED
            named = create.result_entity_id if applied else None  # type: ignore[union-attr]
        if not named or self._load(K.PROPERTY, named) is None:
            return TypeChange(SchemaChangeAction.DELETE, before=before)
        replacement = self._type_fields(named)
        pair = compare_pair(
            (before.get("domain_class_id"), before.get("range_class_id")),
            (replacement.get("domain_class_id"), replacement.get("range_class_id")),
        )
        if pair is PairMatch.DIFFERENT:
            return TypeChange(SchemaChangeAction.DELETE, before=before)
        return TypeChange(
            SchemaChangeAction.DELETE,
            before=before,
            swap=pair is PairMatch.REVERSED,
            replacement=replacement,
        )

    def _taxonomies_of(self, edges: list[Any]) -> set[str]:
        """The taxonomies of the classes typing the edges' ends."""
        class_ids = {c for e in edges for end in (e.source, e.target) for c in end.class_ids}
        found: set[str] = set()
        for class_id in class_ids:
            cls = self._repo.get_class(class_id)
            if cls is not None:
                found.add(cls.taxonomy_id)
        return found

    def _invalidate_graph(self, taxonomy_id: str) -> None:
        if self._event_publisher is None:
            return
        failures = self._event_publisher.publish(
            GraphInvalidated(taxonomy_id=taxonomy_id, reason="proposal_resolution")
        )
        for name, exc in failures:
            _logger.warning("GraphInvalidated handler %s failed: %s", name, exc)

    def _atomic(self) -> Any:
        """One transaction for the steps of one operation, when a scope is wired."""
        return self._transaction_scope.atomic() if self._transaction_scope else nullcontext()

    def _checked_edit(self, operation: ProposedOperation, fields: dict[str, Any]) -> dict[str, Any]:
        """The edit's fields, checked as a proposed property update of the target."""
        try:
            as_update = ProposedOperation(
                seq=operation.seq,
                op=OperationType.UPDATE,
                kind=K.PROPERTY,
                target_id=operation.target_id,
                fields=dict(fields),
            )
            self._check_field_names(as_update)
            self._check_values(as_update)
            self._check_id_fields(as_update, {})
        except _Invalid as exc:
            raise _ApplyFailed(INVALID_EDIT, exc.message) from exc
        except (TypeError, ValueError) as exc:
            raise _ApplyFailed(INVALID_EDIT, str(exc)) from exc
        return as_update.fields

    def _apply_one(
        self,
        operation: ProposedOperation,
        refs: dict[str, ProposedOperation],
        run_id: str,
        forced: bool,
        resolution: InUseResolution | None = None,
        covered: Mapping[str, int] | None = None,
    ) -> None:
        def run() -> str:
            fields = {
                name: self._resolved(value, refs) if name in ID_FIELDS else value
                for name, value in operation.fields.items()
            }
            if operation.op is not OperationType.CREATE:
                self._check_fresh(operation, forced)
            if operation.kind is K.PROPERTY and operation.op in (
                OperationType.CREATE,
                OperationType.UPDATE,
            ):
                rules = self._rules_for(operation, fields)
                if rules is not None:
                    try:
                        rules.check(operation, fields)
                    except ValueError as exc:
                        raise _ApplyFailed(RULE_REFUSED, str(exc)) from exc
            if operation.kind is K.PROPERTY and operation.op is OperationType.UPDATE:
                return self._update_type(
                    operation,
                    fields,
                    resolution,
                    run_id,
                    lambda: self._dispatch(operation, fields, run_id, operation.op),
                    covered,
                )
            if operation.kind is K.PROPERTY and operation.op is OperationType.DELETE:
                using = self._repo.list_relationships(property_id=operation.target_id, limit=None)
                _check_uncovered((r.id for r in using), covered, needs_resolution=True)
                before = self._type_fields(operation.target_id)  # type: ignore[arg-type]
                result = self._dispatch(operation, fields, run_id, operation.op)
                operation.type_change = self._delete_change(before, operation, refs)
                return result
            result = self._dispatch(operation, fields, run_id, operation.op)
            if operation.kind is K.PROPERTY and operation.op is OperationType.CREATE:
                operation.type_change = TypeChange(
                    SchemaChangeAction.CREATE, after=self._type_fields(result)
                )
            return result

        self._record_outcome(operation, run_id, run)

    def _record_outcome(
        self, operation: ProposedOperation, run_id: str, run: Callable[[], str]
    ) -> None:
        """
        Run one operation's apply and record it: applied with the entity it made
        or changed, or failed with a reason (and no applied fields or new scope).
        """
        operation.reason = None
        operation.applied_fields = None
        operation.resolution = None
        operation.type_change = None
        scope = operation.scope
        try:
            operation.result_entity_id = run()
            operation.status = OperationStatus.APPLIED
        except _ApplyFailed as exc:
            operation.status = OperationStatus.FAILED
            operation.reason = exc.reason
        except (OntologyError, ValueError) as exc:
            operation.status = OperationStatus.FAILED
            operation.reason = f"{APPLY_ERROR}: {exc}"
        except Exception as exc:  # noqa: BLE001 - one operation's failure must not stop the rest
            _logger.exception("Proposal %s op seq %s raised unexpectedly", run_id, operation.seq)
            operation.status = OperationStatus.FAILED
            operation.reason = f"{APPLY_ERROR}: {exc}"
        if operation.status is OperationStatus.FAILED:
            operation.applied_fields = None
            operation.resolution = None
            operation.type_change = None
            operation.scope = scope
            _logger.info(
                "Proposal %s op seq %s failed: %s", run_id, operation.seq, operation.reason
            )

    def _resolved(self, value: Any, refs: dict[str, ProposedOperation]) -> Any:
        """Replace "$ref" values with the id of the entity that create made."""
        if isinstance(value, list):
            return [self._resolved(item, refs) for item in value]
        if not _is_ref(value):
            return value
        source = refs.get(value[1:])
        if source is None or source.status is not OperationStatus.APPLIED:
            state = "missing" if source is None else source.status.value
            seq = f" (seq {source.seq})" if source is not None else ""
            raise _ApplyFailed(UNRESOLVED_REF, f"{value}{seq} is {state}, not applied")
        return source.result_entity_id

    def _check_fresh(self, operation: ProposedOperation, forced: bool) -> None:
        """Fail if the target is gone, or (unless forced) its touched fields changed."""
        current = self._load(operation.kind, operation.target_id)  # type: ignore[arg-type]
        if current is None:
            raise _ApplyFailed(TARGET_MISSING, f"{operation.kind.value} {operation.target_id}")
        if forced:
            return
        snapshot = entity_snapshot(current)
        ignored = _VOLATILE_FIELDS | _DERIVED_FIELDS.get(operation.kind, frozenset())
        if DATA_FIELD in operation.fields and operation.op is OperationType.UPDATE:
            # An update's base holds only the values it touches (see _validated).
            current = _data_values(snapshot.get(DATA_FIELD))
            touched = operation.base[DATA_FIELD] or {}
            snapshot[DATA_FIELD] = {key: current.get(key) for key in touched}
        changed = sorted(
            name
            for name, value in operation.base.items()
            if name not in ignored and snapshot.get(name) != value
        )
        if changed:
            raise _ApplyFailed(TARGET_CHANGED, f"{', '.join(changed)} changed since proposed")

    # ----------------------------------------------------------- reject / revert

    def reject(
        self,
        proposal_id: str,
        operation_ids: Iterable[str],
        note: str | None = None,
        decided_by: str | None = DECIDED_BY_USER,
    ) -> ChangeProposal:
        """
        Reject pending or failed operations, with an optional note as the reason.

        Each records a rejected decision by decided_by; None records none, for
        a closing nobody judged (a bundle import superseding an older plan).

        Raises:
            ChangeProposalNotFoundError: If the proposal does not exist
            ChangeProposalStateError: If an operation is already applied or rejected
            ValueError: If an operation id is not in the proposal
        """
        with self._lock(proposal_id):
            proposal = self._get(proposal_id)
            chosen = self._chosen(proposal, operation_ids, "reject")
            for operation in chosen:
                operation.status = OperationStatus.REJECTED
                operation.reason = note
            decisions = []
            if decided_by is not None:
                now = datetime.now(timezone.utc)
                decisions = [decision_of(proposal, o, decided_by, now) for o in chosen]
            self._proposals.save_operations(proposal.id, chosen, decisions)
            proposal.settle_status()
            self._proposals.set_status(proposal.id, proposal.status)
            return self._get(proposal_id)

    def revert(self, proposal_id: str, reverted_by: str = DECIDED_BY_USER) -> RevertResult:
        """
        Undo everything applied from the proposal and mark it reverted.

        Operations still undecided (pending or failed) are rejected ("proposal
        reverted"), since a reverted proposal takes no more decisions; nobody
        judged them, so they record no decision. Applied and rejected operations
        keep their recorded outcomes; the applied ones' decisions are marked
        superseded by reverted_by (a rejection still stands).

        A proposal its client has landed on a mirrored taxonomy can't be
        reverted here: the source already holds it, so the client proposes the
        reversal instead. Unlanded, it can (that is how it is abandoned).

        Raises:
            ChangeProposalNotFoundError: If the proposal does not exist
            ChangeProposalStateError: If it is landed on a mirrored taxonomy
            RevertConflictError, RevertRefusedError: From RevertService when the
                run can't be undone; nothing is changed and the status is left as it was
        """
        with self._lock(proposal_id):
            proposal = self._get(proposal_id)
            if proposal.landed is not None and self._mirrored(proposal.taxonomy_id):
                raise ChangeProposalStateError(
                    f"Change proposal {proposal_id} has landed in the taxonomy's source;"
                    " propose the reversal from the source instead of reverting it here"
                )

            def close_proposal(_result: RevertResult) -> None:
                # Inside the revert's transaction: the status commits with the revert.
                undecided = proposal.pending
                for operation in undecided:
                    operation.status = OperationStatus.REJECTED
                    operation.reason = REVERTED_REASON
                if undecided:
                    self._proposals.save_operations(proposal.id, undecided)
                self._proposals.supersede_decisions(
                    proposal.id, datetime.now(timezone.utc), reverted_by
                )
                self._proposals.set_status(proposal.id, ProposalStatus.REVERTED)

            return self._revert.revert_with_summary(proposal.id, on_reverted=close_proposal)

    # ------------------------------------------------------------------ landing

    def mark_landed(self, proposal_id: str, revision: SourceRevision) -> ChangeProposal:
        """
        Record that the client landed the decided proposal in its source at this
        revision. Marking it again with the same revision changes nothing; another
        revision replaces the landing (a re-landing records its latest commit).

        Raises:
            ChangeProposalNotFoundError: If the proposal does not exist
            ChangeProposalStateError: If it is still open (only a decided
                proposal can land) or reverted
            ValueError: If the revision has no commit
        """
        with self._lock(proposal_id):
            proposal = self._get(proposal_id)
            if proposal.status is not ProposalStatus.DONE:
                raise ChangeProposalStateError(
                    f"Change proposal {proposal_id} is {proposal.status.value}; only a"
                    " done proposal can be marked landed"
                )
            if proposal.landed is not None and proposal.landed.revision == revision:
                return proposal
            self._proposals.set_landed(
                proposal_id, Landing(revision=revision, landed_at=datetime.now(timezone.utc))
            )
            return self._get(proposal_id)

    def clear_landing(self, proposal_id: str) -> ChangeProposal:
        """
        Forget that the proposal landed (a person correcting a wrong mark).

        Raises:
            ChangeProposalNotFoundError: If the proposal does not exist
        """
        with self._lock(proposal_id):
            proposal = self._get(proposal_id)
            if proposal.landed is None:
                return proposal
            self._proposals.set_landed(proposal_id, None)
            return self._get(proposal_id)

    def _mirrored(self, taxonomy_id: str) -> bool:
        taxonomy = self._repo.get_taxonomy(taxonomy_id)
        return taxonomy is not None and taxonomy.mirrored

    # ------------------------------------------------------------------ helpers

    def list_decisions(
        self, filters: DecisionFilter, limit: int | None = None, offset: int = 0
    ) -> list[ProposalDecision]:
        """
        Decisions matching the filters, oldest first (limit None: all).

        Raises:
            EntityNotFoundError: If filters name a taxonomy that does not exist
        """
        self._check_taxonomy(filters)
        return self._proposals.list_decisions(filters, limit, offset)

    def count_decisions(self, filters: DecisionFilter) -> int:
        """Count decisions matching the filters (EntityNotFoundError as list_decisions)."""
        self._check_taxonomy(filters)
        return self._proposals.count_decisions(filters)

    def decisions_of(self, proposal_id: str) -> dict[str, ProposalDecision]:
        """Operation id -> its latest decision, superseded or not."""
        return by_operation(
            self._proposals.list_decisions(
                DecisionFilter(proposal_id=proposal_id, include_superseded=True)
            )
        )

    def _check_taxonomy(self, filters: DecisionFilter) -> None:
        if filters.taxonomy_id is not None and self._repo.get_taxonomy(filters.taxonomy_id) is None:
            raise EntityNotFoundError("Taxonomy", filters.taxonomy_id)

    def get(self, proposal_id: str) -> ChangeProposal:
        """The proposal, or ChangeProposalNotFoundError."""
        return self._get(proposal_id)

    def _lock(self, proposal_id: str) -> threading.Lock:
        """
        The lock that serializes apply, reject and revert of one proposal
        (in-process). Only an existing proposal gets one, so the map holds at
        most one lock per proposal decided on in this process.

        Raises:
            ChangeProposalNotFoundError: If the proposal does not exist
        """
        self._get(proposal_id)
        with self._locks_guard:
            return self._locks.setdefault(proposal_id, threading.Lock())

    def list_proposals(
        self,
        taxonomy_id: str | None = None,
        status: ProposalStatus | None = None,
        source: ProposalSource | None = None,
        limit: int = 50,
        offset: int = 0,
        landed: bool | None = None,
    ) -> list[ChangeProposal]:
        """
        Proposals, newest first, optionally filtered. landed False with status
        done lists the decided proposals their client hasn't landed yet.
        """
        return self._proposals.list_proposals(
            taxonomy_id, status, source, limit, offset, landed=landed
        )

    def count_proposals(
        self,
        taxonomy_id: str | None = None,
        status: ProposalStatus | None = None,
        source: ProposalSource | None = None,
        landed: bool | None = None,
    ) -> int:
        """How many proposals match the filters."""
        return self._proposals.count_proposals(taxonomy_id, status, source, landed=landed)

    def stale_operation_ids(self, proposal: ChangeProposal) -> set[str]:
        """
        Ids of the pending or failed operations that applying now would fail as
        stale: the target is gone, or a field it touches changed since proposed.
        Creates are never stale.
        """
        stale: set[str] = set()
        for operation in proposal.pending:
            if operation.op is OperationType.CREATE:
                continue
            try:
                self._check_fresh(operation, forced=False)
            except _ApplyFailed:
                stale.add(operation.id)
        return stale

    def in_use_blockers(self, proposal: ChangeProposal) -> dict[str, DeleteBlockers]:
        """
        For each pending or failed relationship-type (property) delete whose type
        relationships still use: those relationships, with each end's classes,
        and the other types every one of them fits (never a type another
        awaiting operation of the proposal deletes). Relationships an awaiting
        relationship delete of the proposal removes don't count (a bundle
        import deletes them before their type), so a delete they all cover has
        none; applying it waits until those relationship deletes are applied
        or rejected, so it acts on the same relationships review showed.
        Applying a blocked delete as proposed fails; it needs a
        resolution (see `apply`). The same for each pending or failed property
        update that retargets its type (another pair of domain and range
        classes) while relationships use it.
        """
        return self.in_use(proposal, with_usage=False)[0]

    def type_usage(self, proposal: ChangeProposal) -> dict[str, DeleteBlockers]:
        """
        For each pending or failed property update that keeps its type's pair
        (a rename or reverse, which needs no resolution) while relationships use
        the type: those relationships and the types they all fit, as
        `in_use_blockers` lists them. A reviewer's edit that retargets such an
        update instead needs a resolution of them.
        """
        return self.in_use(proposal)[1]

    def in_use(
        self, proposal: ChangeProposal, with_usage: bool = True
    ) -> tuple[dict[str, DeleteBlockers], dict[str, DeleteBlockers]]:
        """
        `in_use_blockers` and (unless with_usage is False) `type_usage` in one
        pass: each update's target is loaded once, and one inspector (with its
        caches of types and classes) serves every operation.
        """
        deletes, retargets, keeps = [], [], []
        for o in proposal.pending:
            if o.kind is not K.PROPERTY:
                continue
            if o.op is OperationType.DELETE and o.target_id:
                deletes.append(o)
            elif o.op is OperationType.UPDATE:
                if self._retargets(o):
                    retargets.append(o)
                elif with_usage and o.target_id:
                    keeps.append(o)
        inspector = InUseInspector(self._repo)
        return (
            self._blockers_of(proposal, deletes + retargets, inspector),
            self._blockers_of(proposal, keeps, inspector),
        )

    @staticmethod
    def _covered(proposal: ChangeProposal) -> dict[str, int]:
        """
        Relationship id -> seq of the awaiting relationship delete of the
        proposal that removes it. Blockers leave these relationships out, so
        applying a type operation they use waits until those deletes are
        applied or rejected (`_check_uncovered`): both see the same set.
        """
        return {
            str(o.target_id): o.seq
            for o in proposal.pending
            if o.kind is K.RELATIONSHIP and o.op is OperationType.DELETE and o.target_id
        }

    def _blockers_of(
        self,
        proposal: ChangeProposal,
        operations: list[ProposedOperation],
        inspector: InUseInspector,
    ) -> dict[str, DeleteBlockers]:
        """The relationships using each operation's type, and the types they all fit."""
        if not operations:
            return {}
        deleted = {
            o.id: str(o.target_id)
            for o in proposal.pending
            if o.kind is K.PROPERTY and o.op is OperationType.DELETE and o.target_id
        }
        covered = self._covered(proposal)
        found: dict[str, DeleteBlockers] = {}
        for operation in operations:
            target_id = str(operation.target_id)
            others = set(deleted.values()) - {target_id}
            blockers = inspector.blockers(target_id, excluded=others, covered=covered)
            if blockers is None:
                continue
            named = self._replacement_property_id(proposal, operation)
            if named is not None:
                # The proposer's named replacement goes first, when it fits.
                blockers = replace(
                    blockers,
                    replacements=tuple(
                        sorted(blockers.replacements, key=lambda r: r.property_id != named)
                    ),
                )
            found[operation.id] = blockers
        return found

    def _retargets(self, operation: ProposedOperation) -> bool:
        """Whether a property update, as proposed, gives its type another pair of classes."""
        target = self._load(K.PROPERTY, operation.target_id)  # type: ignore[arg-type]
        if target is None:
            return False
        current = (target.domain_class_id, target.range_class_id)
        proposed = (
            operation.fields.get("domain_class_id", current[0]),
            operation.fields.get("range_class_id", current[1]),
        )
        return compare_pair(current, proposed) is PairMatch.DIFFERENT

    def replacement_checks(self, proposal: ChangeProposal) -> dict[str, ReplacementCheck]:
        """
        For each property delete that names its replacement: the replacement and
        how its domain and range compare with the deleted type's (as proposed,
        from its base): the same pair, reversed, or a different pair; missing
        once the replacement is gone, or its create rejected.

        The replacement is judged as it will be once the proposal applies: an
        awaiting update of it in the same proposal overlays its domain, range,
        identifier and title; a "$ref" replacement is read from its create's
        fields until that is applied; one the proposal deletes is read from that
        delete's base. The comparison is exact, as DR's pairOf: an untyped
        deleted type (no domain or range) against a typed replacement, or a
        superclass or subclass of either end, is a different pair.

        A replacement the proposal also deletes (an awaiting or applied delete)
        is followed through each delete's own replacement to the end of the
        chain, or round a cycle (see ReplacementCheck.chain).
        """
        creates = {o.ref: o for o in proposal.operations if o.ref}
        deletes = {
            o.target_id: o
            for o in proposal.operations
            if o.kind is K.PROPERTY
            and o.op is OperationType.DELETE
            and o.target_id
            and o.status is not OperationStatus.REJECTED
        }
        checks: dict[str, ReplacementCheck] = {}
        for operation in proposal.operations:
            replacement_id = operation.proposed_replacement_id
            if not replacement_id or operation.kind is not K.PROPERTY:
                continue
            deleted = (operation.base.get("domain_class_id"), operation.base.get("range_class_id"))
            ends = {
                "deleted_domain": self._class_end(deleted[0], creates),
                "deleted_range": self._class_end(deleted[1], creates),
            }
            values = self._replacement_values(proposal, replacement_id, creates, deletes)
            chain, cycle = self._replacement_chain(proposal, operation, creates, deletes)
            if values is None:
                checks[operation.id] = ReplacementCheck(
                    replacement_id, None, None, None, PairMatch.MISSING, **ends
                )
                continue
            pair = (values.get("domain_class_id"), values.get("range_class_id"))
            checks[operation.id] = ReplacementCheck(
                replacement_id,
                values.get("id"),
                values.get("identifier"),
                values.get("title"),
                compare_pair(deleted, pair),
                **ends,
                domain=self._class_end(pair[0], creates),
                range=self._class_end(pair[1], creates),
                chain=chain,
                cycle=cycle,
            )
        return checks

    @staticmethod
    def _replacement_property_id(
        proposal: ChangeProposal, operation: ProposedOperation
    ) -> str | None:
        """The id of the type a delete names as its replacement ("$ref": once applied)."""
        replacement_id = operation.proposed_replacement_id
        if replacement_id and _is_ref(replacement_id):
            create = next((o for o in proposal.operations if o.ref == replacement_id[1:]), None)
            applied = create is not None and create.status is OperationStatus.APPLIED
            return create.result_entity_id if applied else None  # type: ignore[union-attr]
        return replacement_id

    def _replacement_values(
        self,
        proposal: ChangeProposal,
        replacement_id: str,
        creates: dict[str, ProposedOperation],
        deletes: dict[Any, ProposedOperation],
    ) -> dict[str, Any] | None:
        """
        A replacement's id, identifier, title, domain and range once the
        proposal applies; None when it is gone (or its create rejected).
        """
        if _is_ref(replacement_id):
            create = creates.get(replacement_id[1:])
            if create is None or create.status is OperationStatus.REJECTED:
                return None
            if create.status is not OperationStatus.APPLIED:
                return {**create.fields, "id": None}
            replacement_id = str(create.result_entity_id)
        found = self._load(K.PROPERTY, replacement_id)
        if found is not None:
            values = {
                "id": found.id,
                "identifier": found.identifier,
                "title": found.title,
                "domain_class_id": found.domain_class_id,
                "range_class_id": found.range_class_id,
            }
        elif replacement_id in deletes:
            # Deleted by this proposal already: as it was when proposed.
            values = {**deletes[replacement_id].base, "id": None}
        else:
            return None
        for update in proposal.pending:
            if update.op is OperationType.UPDATE and update.target_id == replacement_id:
                values.update(
                    {
                        name: update.fields[name]
                        for name in ("identifier", "title", "domain_class_id", "range_class_id")
                        if name in update.fields
                    }
                )
        return values

    def _replacement_chain(
        self,
        proposal: ChangeProposal,
        operation: ProposedOperation,
        creates: dict[str, ProposedOperation],
        deletes: dict[Any, ProposedOperation],
    ) -> tuple[tuple[ChainLink, ...], bool]:
        """
        When the proposal also deletes the delete's replacement: each
        replacement in turn, following each delete's own replacement, to one
        it doesn't delete (or none), and whether the chain comes back round to a
        type already in it. Empty when the replacement stays.
        """
        current = operation.proposed_replacement_id
        if current not in deletes:
            return (), False
        seen = {operation.target_id}
        links: list[ChainLink] = []
        while current is not None:
            deleter = deletes.get(current)
            values = self._replacement_values(proposal, current, creates, {})
            if deleter is not None:
                identifier = deleter.base.get("identifier")
            else:
                identifier = values.get("identifier") if values else None
            links.append(
                ChainLink(current, identifier, deleter.seq if deleter is not None else None)
            )
            if deleter is None:
                return tuple(links), False
            seen.add(current)
            current = deleter.proposed_replacement_id
            if current in seen:
                return tuple(links), True
        return tuple(links), False

    def _class_end(self, class_id: Any, creates: dict[str, ProposedOperation]) -> ClassEnd:
        """A domain or range class with its title ("$ref": its create's title)."""
        if not isinstance(class_id, str):
            return ClassEnd(None, None)
        if _is_ref(class_id):
            create = creates.get(class_id[1:])
            title = create.fields.get("title") if create is not None else None
            return ClassEnd(class_id, title if isinstance(title, str) else class_id)
        cls = self._repo.get_class(class_id)
        return ClassEnd(class_id, cls.title if cls is not None else class_id)

    def _get(self, proposal_id: str) -> ChangeProposal:
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ChangeProposalNotFoundError(proposal_id)
        return proposal

    @staticmethod
    def _chosen(
        proposal: ChangeProposal, operation_ids: Iterable[str], action: str
    ) -> list[ProposedOperation]:
        by_id = {o.id: o for o in proposal.operations}
        ids = list(dict.fromkeys(operation_ids))
        unknown = [i for i in ids if i not in by_id]
        if unknown:
            raise ValueError(f"Change proposal {proposal.id} has no operations {unknown}")
        chosen = sorted((by_id[i] for i in ids), key=lambda o: o.seq)
        decided = [
            o.seq for o in chosen if o.status in (OperationStatus.APPLIED, OperationStatus.REJECTED)
        ]
        if decided:
            raise ChangeProposalStateError(
                f"Can't {action} operations of change proposal {proposal.id} that are "
                f"already applied or rejected (seq {decided})"
            )
        return chosen

    def _load(self, kind: OperationKind, entity_id: str) -> Any:
        getter: Callable[[str], Any] = {
            K.TAXONOMY: self._repo.get_taxonomy,
            K.SCHEME: self._repo.get_concept_scheme,
            K.CLASS: self._repo.get_class,
            K.PROPERTY: self._repo.get_property_definition,
            K.ATTRIBUTE: self._repo.get_attribute_definition,
            K.INDIVIDUAL: self._repo.get_individual,
            K.RELATIONSHIP: self._repo.get_relationship,
        }[kind]
        if not isinstance(entity_id, str):
            return None
        return getter(entity_id)

    # ----------------------------------------------------------------- dispatch

    def _dispatch(
        self,
        operation: ProposedOperation,
        fields: dict[str, Any],
        run_id: str,
        op: OperationType,
    ) -> str:
        """
        Make the change through OntologyService; returns the entity id made or changed.

        `op` is what to do: the operation's own op, or an update when a
        reviewer's edit turned a delete into one.
        """
        kind, target = operation.kind, operation.target_id
        svc = self._ontology
        values = {
            name: value if name == DATA_FIELD else decode_field(name, value)
            for name, value in fields.items()
        }

        if op is OperationType.DELETE:
            delete = {
                K.TAXONOMY: svc.delete_taxonomy,
                K.SCHEME: svc.delete_scheme,
                K.CLASS: svc.delete_class,
                K.PROPERTY: svc.delete_property_definition,
                K.ATTRIBUTE: svc.delete_attribute_definition,
                K.INDIVIDUAL: svc.delete_individual,
                K.RELATIONSHIP: svc.delete_relationship,
            }[kind]
            delete(target)
            return target  # type: ignore[return-value]

        if op is OperationType.CREATE:
            return self._create(kind, values, run_id)

        if op is OperationType.MOVE:
            if kind is K.SCHEME:
                return svc.update_concept_scheme(target, taxonomy_id=values["taxonomy_id"]).id
            return self._move_class(target, values)  # type: ignore[arg-type]

        return self._update(kind, target, values)  # type: ignore[arg-type]

    def _create(self, kind: OperationKind, v: dict[str, Any], run_id: str) -> str:
        svc = self._ontology
        if kind is K.TAXONOMY:
            return svc.create_taxonomy(**v).id
        if kind is K.SCHEME:
            return svc.create_scheme(**v).id
        if kind is K.CLASS:
            return svc.create_class(**v, source_run_id=run_id).id
        if kind is K.PROPERTY:
            return svc.create_property_definition(**v, source_run_id=run_id).id
        if kind is K.ATTRIBUTE:
            v["datatype"] = getattr(v["datatype"], "value", v["datatype"])
            return svc.create_attribute_definition(**v, source_run_id=run_id).id
        if kind is K.INDIVIDUAL:
            if DATA_FIELD in v:
                v[DATA_FIELD] = self._data_for(v["class_ids"], v[DATA_FIELD], [])
            return svc.create_individual(**v, source_run_id=run_id).id
        return svc.create_relationship(**v, source_run_id=run_id).id

    def _update(self, kind: OperationKind, target: str, v: dict[str, Any]) -> str:
        svc = self._ontology
        cleared = {name: "" for name, value in v.items() if value is None}
        if kind is K.TAXONOMY:
            return svc.update_taxonomy(target, **{**v, **cleared}).id
        if kind is K.SCHEME:
            return svc.update_concept_scheme(target, **{**v, **cleared}).id
        if kind is K.CLASS:
            return svc.update_class(target, **{**v, **cleared}).id
        if kind is K.ATTRIBUTE:
            if "allowed_values" in cleared:
                cleared["allowed_values"] = []  # type: ignore[assignment]
            if v.get("datatype") is not None:
                v["datatype"] = getattr(v["datatype"], "value", v["datatype"])
            return svc.update_attribute_definition(target, **{**v, **cleared}).id
        if kind is K.INDIVIDUAL:
            return self._update_individual(target, v)
        if kind is K.RELATIONSHIP:
            return svc.update_relationship(target, v["attributes"]).id
        return self._update_property(target, v)

    def _update_property(self, target: str, v: dict[str, Any]) -> str:
        kwargs: dict[str, Any] = {}
        for name in ("identifier", "title", "external_references"):
            if name in v:
                kwargs[name] = v[name]
        if "description" in v:
            kwargs["description"] = v["description"] if v["description"] is not None else ""
        for name in ("canonical_predicate", "is_relevant", "domain_class_id", "range_class_id"):
            if name in v:
                kwargs[name] = v[name]
                kwargs[f"update_{name}"] = True
        return self._ontology.update_property_definition(target, **kwargs).id

    def _update_individual(self, target: str, v: dict[str, Any]) -> str:
        svc = self._ontology
        text = {name: v[name] for name in ("title", "external_references") if name in v}
        if "description" in v:
            text["description"] = v["description"] if v["description"] is not None else ""
        if DATA_FIELD in v:
            # Checked first, against the classes it will have, so a misfit changes nothing.
            individual = svc.get_individual(target)
            classes = list(v.get("class_ids") or individual.class_ids)
            text[DATA_FIELD] = self._data_for(classes, v[DATA_FIELD], individual.data_properties)
        if text:
            svc.update_individual(target, **text)
        if "class_ids" in v:
            wanted: list[str] = list(v["class_ids"])
            current = svc.get_individual(target).class_ids
            # Add before removing, so the individual always keeps a class.
            for class_id in wanted:
                if class_id not in current:
                    svc.add_class_to_individual(target, class_id)
            for class_id in list(current):
                if class_id not in wanted:
                    svc.remove_class_from_individual(target, class_id)
            if svc.get_individual(target).class_ids != wanted:
                svc.reorder_individual_classes(target, wanted)
        return target

    def _move_class(self, target: str, v: dict[str, Any]) -> str:
        """Scheme first (move_class needs the parent in the class's current scheme), then parent."""
        svc = self._ontology
        if "concept_scheme_id" in v:
            svc.move_class_to_scheme(target, v["concept_scheme_id"])
            try:
                svc.move_class(target, v.get("parent_class_id"))
            except (OntologyError, ValueError) as exc:
                raise ValueError(
                    f"moved to scheme {v['concept_scheme_id']} but not to parent "
                    f"{v.get('parent_class_id')}: {exc}; revert the proposal to undo"
                ) from exc
            return target
        return svc.move_class(target, v["parent_class_id"]).id


def _check_uncovered(
    relationship_ids: Iterable[str],
    covered: Mapping[str, int] | None,
    needs_resolution: bool,
) -> None:
    """
    Fail a relationship-type delete, retarget or reverse while relationships
    using the type still await the proposal's own relationship deletes. Review
    leaves those relationships out (see `_covered`), so the apply must not act
    on them either: the reviewed set and the applied set stay the same.

    Args:
        relationship_ids: The relationships using the type now
        covered: Relationship id -> seq of the awaiting delete that removes it
        needs_resolution: Whether the others (not covered) need a resolution
            this apply lacks, so the message says that too
    """
    covered = covered or {}
    ids = list(relationship_ids)
    seqs = sorted({covered[i] for i in ids if i in covered})
    if not seqs:
        return
    listed = ", ".join(str(s) for s in seqs)
    message = (
        f"relationships using the type are deleted by seq {listed} of this proposal,"
        " not applied yet; apply or reject those first"
    )
    others = sum(1 for i in ids if i not in covered)
    if others and needs_resolution:
        message += f"; the other {others} relationship(s) using it need a resolution too"
    raise _ApplyFailed(UNRESOLVABLE, message)


def _recorded(
    resolution: InUseResolution, resolved: list[ResolvedEdge], replacement: Any, swap: bool
) -> InUseResolution:
    """A resolution as applied: the replacement and the relationships moved or deleted."""
    return InUseResolution(
        strategy=resolution.strategy,
        replacement_property_id=replacement.id if replacement else None,
        replacement_identifier=replacement.identifier if replacement else None,
        reversed=swap,
        edges=resolved,
    )
