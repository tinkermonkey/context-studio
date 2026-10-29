"""
ProposalService: propose ontology changes, then apply, reject or revert them.

A proposal is validated as a whole when it is made (nothing is stored if any
operation is invalid) and decided per operation afterwards. Applying runs the
chosen operations in seq order through OntologyService with the proposal's id
as the batch run id, so every change event they produce is tagged with it and
reverting the run undoes the proposal. Applies are not atomic: each operation
records its own outcome, and revert is the recovery path.

Values in an operation's `fields` and `base` use the JSON encoding of entity
snapshots (`domain.ontology.snapshots`): enums as their value, external
references as dicts. A field value "$name" in an id field points at the entity
an earlier create in the same proposal makes (its `ref` is "name").
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable, Iterable, Mapping, Sequence
from uuid import uuid4

from domain.interchange.services import get_current_batch_run_id, set_batch_run_context
from domain.ontology.entities import validate_relationship_attributes
from domain.ontology.exceptions import OntologyError
from domain.ontology.snapshots import decode_field, entity_snapshot
from domain.versioning.approval_policy import auto_apply_ids
from domain.versioning.exceptions import (
    ChangeProposalNotFoundError,
    ChangeProposalStateError,
    OperationError,
    ProposalValidationError,
)
from domain.versioning.proposals import (
    ChangeProposal,
    ChangeScope,
    OperationDraft,
    OperationKind,
    OperationStatus,
    OperationType,
    ProposalSource,
    ProposalStatus,
    ProposedOperation,
    classify_scope,
)

if TYPE_CHECKING:
    from domain.ontology.ports import OntologyRepository
    from domain.ontology.services import OntologyService
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

REVERTED_REASON = "proposal reverted"

_REF_PREFIX = "$"
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
        update=frozenset({"title", "description", "color", "vision"}),
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
            }
        ),
        clearable=frozenset({"description", "allowed_values", "default_value"}),
    ),
    K.INDIVIDUAL: OperationFields(
        create=frozenset({"class_ids", "title", "description", "external_references"}),
        required=frozenset({"class_ids", "title"}),
        update=frozenset({"title", "description", "external_references", "class_ids"}),
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
        """
        self._proposals = proposals
        self._ontology = ontology_service
        self._repo = ontology_repo
        self._revert = revert_service
        self._policies = approval_policies
        self._apply_rules = tuple(apply_rules)
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

        Returns:
            The stored proposal, with any auto-applied outcomes (with dry_run,
            the unstored proposal)

        Raises:
            ProposalValidationError: With every problem found; nothing is stored
        """
        errors: list[OperationError] = []
        if self._repo.get_taxonomy(taxonomy_id) is None:
            errors.append(OperationError(None, "taxonomy_not_found", f"No taxonomy {taxonomy_id}"))
        if not operations:
            errors.append(
                OperationError(None, "invalid", "A proposal needs at least one operation")
            )

        built: list[ProposedOperation] = []
        refs: dict[str, OperationKind] = {}
        touched: dict[tuple[str, str], int] = {}
        deleted: dict[str, int] = {}
        seen_seqs: set[int] = set()
        for draft in sorted(operations, key=lambda d: d.seq):
            try:
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
            policy = self._policies.get(proposal.taxonomy_id)
            auto = auto_apply_ids(
                policy,
                proposal.operations,
                self._classes,
                lambda operation: self._inside_taxonomy(operation, proposal.taxonomy_id),
                id_fields=frozenset(ID_FIELDS),
            )
            # apply takes the proposal's lock itself; propose never holds it.
            return self.apply(proposal.id, auto) if auto else proposal
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

    def _classes(self, operation: ProposedOperation) -> list[set[str]]:
        """
        Per class the operation's entity will be typed by, its id and identifier:
        an individual's current classes plus any it is given, an attribute's
        class, or a class itself. A "$ref" class gets an empty set (no rule
        names it).
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
        elif operation.kind is K.CLASS and target:
            class_ids = [target]
        classes: list[set[str]] = []
        for class_id in class_ids:
            if not isinstance(class_id, str) or _is_ref(class_id):
                classes.append(set())
                continue
            cls = self._repo.get_class(class_id)
            identifier = cls.identifier if cls is not None else None
            classes.append({class_id, identifier} if identifier else {class_id})
        return classes

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
        operation.scope = classify_scope(op, operation.fields, operation.base, claimed)
        return operation

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
    ) -> ChangeProposal:
        """
        Apply the chosen operations, in seq order, under the proposal's run id.

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

        Args:
            proposal_id: The proposal
            operation_ids: The operations to apply
            force_stale: Operations to apply even if their target changed since proposed
            edits: Operation id -> the fields to apply instead of the proposed ones

        Returns:
            The proposal with updated outcomes

        Raises:
            ChangeProposalNotFoundError: If the proposal does not exist
            ChangeProposalStateError: If the proposal is reverted, or an operation
                is already applied or rejected; nothing is applied
            ValueError: If an operation id is not in the proposal, or an edit is
                misplaced (its operation isn't being applied or isn't a property
                update or delete, it is empty, or it points at a "$ref");
                nothing is applied
        """
        with self._lock(proposal_id):
            proposal = self._get(proposal_id)
            if proposal.status is ProposalStatus.REVERTED:
                raise ChangeProposalStateError(f"Change proposal {proposal_id} is reverted")
            chosen = self._chosen(proposal, operation_ids, "apply")
            edits = dict(edits or {})
            self._check_edits_placed(chosen, edits)
            force = set(force_stale)
            refs = {o.ref: o for o in proposal.operations if o.ref}

            previous_run = get_current_batch_run_id()
            set_batch_run_context(proposal.id)
            try:
                for operation in chosen:
                    forced = operation.id in force
                    if operation.id in edits:
                        others = {i: e for i, e in edits.items() if i != operation.id}
                        edit = edits[operation.id]
                        self._apply_edited(proposal, operation, edit, others, forced)
                    else:
                        self._apply_one(operation, refs, proposal.id, forced)
                    self._proposals.save_operations(proposal.id, [operation])
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
            result = self._dispatch(operation, fields, proposal.id, OperationType.UPDATE)
            base = {
                name: operation.base[name] if name in operation.base else before.get(name)
                for name in fields
            }
            operation.applied_fields = fields
            operation.scope = classify_scope(OperationType.UPDATE, fields, base)
            return result

        self._record_outcome(operation, proposal.id, run)

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
            return self._dispatch(operation, fields, run_id, operation.op)

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
        changed = sorted(
            name
            for name, value in operation.base.items()
            if name not in ignored and snapshot.get(name) != value
        )
        if changed:
            raise _ApplyFailed(TARGET_CHANGED, f"{', '.join(changed)} changed since proposed")

    # ----------------------------------------------------------- reject / revert

    def reject(
        self, proposal_id: str, operation_ids: Iterable[str], note: str | None = None
    ) -> ChangeProposal:
        """
        Reject pending or failed operations, with an optional note as the reason.

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
            self._proposals.save_operations(proposal.id, chosen)
            proposal.settle_status()
            self._proposals.set_status(proposal.id, proposal.status)
            return self._get(proposal_id)

    def revert(self, proposal_id: str) -> RevertResult:
        """
        Undo everything applied from the proposal and mark it reverted.

        Operations still undecided (pending or failed) are rejected ("proposal
        reverted"), since a reverted proposal takes no more decisions. Applied and
        rejected operations keep their recorded outcomes.

        Raises:
            ChangeProposalNotFoundError: If the proposal does not exist
            RevertConflictError, RevertRefusedError: From RevertService when the
                run can't be undone; nothing is changed and the status is left as it was
        """
        with self._lock(proposal_id):
            proposal = self._get(proposal_id)

            def close_proposal(_result: RevertResult) -> None:
                # Inside the revert's transaction: the status commits with the revert.
                undecided = proposal.pending
                for operation in undecided:
                    operation.status = OperationStatus.REJECTED
                    operation.reason = REVERTED_REASON
                if undecided:
                    self._proposals.save_operations(proposal.id, undecided)
                self._proposals.set_status(proposal.id, ProposalStatus.REVERTED)

            return self._revert.revert_with_summary(proposal.id, on_reverted=close_proposal)

    # ------------------------------------------------------------------ helpers

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
    ) -> list[ChangeProposal]:
        """Proposals, newest first, optionally filtered."""
        return self._proposals.list_proposals(taxonomy_id, status, source, limit, offset)

    def count_proposals(
        self,
        taxonomy_id: str | None = None,
        status: ProposalStatus | None = None,
        source: ProposalSource | None = None,
    ) -> int:
        """How many proposals match the filters."""
        return self._proposals.count_proposals(taxonomy_id, status, source)

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
        values = {name: decode_field(name, value) for name, value in fields.items()}

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
