"""
Proposal tools for the chat assistant and the MCP server: propose changes to a
taxonomy, then follow them.

An agent proposes; a person reviews. These tools can only make and read change
proposals. Accepting, rejecting, applying or reverting operations, and setting a
taxonomy's approval policy or mirrored flag, are a person's decisions in the app
and are never offered as tools. The one exception is `mark_proposal_landed`, MCP
only: a client mirroring a taxonomy reports that it wrote a decided proposal into
its source, which decides nothing. `dr_spec_drift` (MCP only too) re-imports
the DR spec as a drift report or proposal: what it proposes waits for review.

`build_proposal_tools` is instantiated once per caller with its ProposalSource
(chat or MCP). Every result names its proposals with kind "proposal", so chat
answers can link them as `entity:proposal/<id>` and MCP results end with their
review page links. Results are compact JSON capped at MAX_PROPOSAL_CHARS: when a
result is longer, whole entries are dropped and the result says so.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Optional, Sequence

from pydantic import TypeAdapter

from adapters.chat.tools import (
    ToolArgumentError,
    ToolBase,
    dumps,
    error_outcome,
    int_arg,
    optional_str,
    required_str,
)
from adapters.serialization.views import proposal_response
from domain.chat.value_objects import EntityRef, ToolOutcome
from domain.ontology.value_objects import SourceRevision
from domain.versioning.drift import DriftEntry, DriftError, DriftImportService
from domain.versioning.exceptions import (
    ChangeProposalNotFoundError,
    ChangeProposalStateError,
    OperationError,
    ProposalValidationError,
)
from domain.versioning.proposal_service import (
    ID_FIELDS,
    MAX_SEQ,
    OPERATION_FIELDS,
    ProposalService,
)
from domain.versioning.proposals import (
    MOVE_FIELDS,
    ChangeProposal,
    OperationDraft,
    OperationKind,
    OperationStatus,
    OperationType,
    ProposalSource,
    ProposalStatus,
)

_logger = logging.getLogger(__name__)

SOURCE_REVISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "repo": {"type": "string", "description": "The source repository"},
        "commit": {"type": "string", "description": "The commit"},
        "spec_version": {"type": "string", "description": "The source's version label"},
    },
    "additionalProperties": False,
}

PROPOSAL_KIND = "proposal"
# A cleanup pass reached 477 operations (#1466); a larger pass is a bundle import.
MAX_OPERATIONS = 500
# A propose or get_proposal result longer than this pages its operations.
MAX_PROPOSAL_CHARS = 16000
# A result too large even with one entry has its texts cut to this length.
CLIPPED_TEXT_CHARS = 300
DEFAULT_LIMIT = 20
MAX_LIMIT = 50
# An in-use blocker lists at most this many relationships and move targets; the review
# page has all.
MAX_BLOCKER_EDGES = 10
# Dropped from get_proposal's operations first when a result is too large; fields and
# applied_fields stay, and the operations page instead.
BULKY_OPERATION_KEYS = ("base", "evidence")
# What dr_spec_drift entries can be filtered by.
DRIFT_KINDS = ("taxonomy", "scheme", "class", "property", "attribute", "predicate")
DRIFT_CHANGES = ("create", "update", "move", "delete")


def proposal_ref(proposal: ChangeProposal) -> EntityRef:
    """The link reference for a proposal: its review page."""
    return EntityRef(id=proposal.id, kind=PROPOSAL_KIND, title=proposal.title)


def _counts(proposal: ChangeProposal) -> dict[str, int]:
    """Operations per status, every status present."""
    counts = {s.value: 0 for s in OperationStatus}
    for operation in proposal.operations:
        counts[operation.status.value] += 1
    return counts


def _view(service: ProposalService, proposal: ChangeProposal, dry_run: bool = False) -> dict:
    """
    The proposal as REST returns it (the same serializer, so the two can't
    drift), compacted: nulls and empty lists or objects are left out, and each
    in-use blocker lists at most MAX_BLOCKER_EDGES relationships and move
    targets (edges_total and replacements_total say how many there are), and
    dry_run appears only when true.
    """
    view = _compact(proposal_response(service, proposal, dry_run=dry_run).model_dump(mode="json"))
    if not view.get("dry_run"):
        view.pop("dry_run", None)
    for operation in view["operations"]:
        blockers = operation.get("blockers") or {}
        for key in ("edges", "replacements"):
            if len(blockers.get(key, ())) > MAX_BLOCKER_EDGES:
                blockers[f"{key}_total"] = len(blockers[key])
                blockers[key] = blockers[key][:MAX_BLOCKER_EDGES]
    return view


def _compact(value: Any) -> Any:
    """The value without None, empty lists or empty objects, at any depth."""
    if isinstance(value, dict):
        kept = {k: _compact(v) for k, v in value.items()}
        return {k: v for k, v in kept.items() if v is not None and v != [] and v != {}}
    if isinstance(value, list):
        return [_compact(v) for v in value]
    return value


def _capped(
    payload: dict[str, Any],
    list_key: str,
    note: Callable[[int], str],
    total: Optional[int] = None,
    offset: int = 0,
) -> tuple[str, list[Any]]:
    """
    Serialize a result within MAX_PROPOSAL_CHARS; returns the content and the
    entries of its list that were kept.

    Whole entries are dropped from the end of the list first, never the last
    one, so paging with offset always advances. If that is not enough, every
    text longer than CLIPPED_TEXT_CHARS is cut and the result says so.

    Args:
        payload: The result
        list_key: The list to cut
        note: What to do about the cut entries, given how many were kept
        total: How many entries there are in all, when the list is one page
            of them (default: the list's length)
        offset: Where the list starts among them, for a page
    """
    total = len(payload[list_key]) + offset if total is None else total

    def fit(current: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        items = list(current[list_key])
        content = dumps(current)
        while len(items) > 1 and len(content) > MAX_PROPOSAL_CHARS:
            items = items[: max(len(items) * 3 // 4, 1)]
            shown = f"{offset + 1}-{offset + len(items)}" if offset else str(len(items))
            truncated = f"showing {shown} of {total}; {note(len(items))}"
            current = {**current, list_key: items, "truncated": truncated}
            content = dumps(current)
        return content, current

    content, fitted = fit(payload)
    if len(content) > MAX_PROPOSAL_CHARS:
        clipped = _clipped(payload)
        clipped["clipped"] = (
            f"texts longer than {CLIPPED_TEXT_CHARS} characters are cut; the review page"
            " shows them whole"
        )
        content, fitted = fit(clipped)
    return content, list(fitted[list_key])


def _clipped(value: Any) -> Any:
    """The value with every text longer than CLIPPED_TEXT_CHARS cut, marked with an ellipsis."""
    if isinstance(value, str) and len(value) > CLIPPED_TEXT_CHARS:
        return value[:CLIPPED_TEXT_CHARS] + "…"
    if isinstance(value, dict):
        return {k: _clipped(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clipped(v) for v in value]
    return value


def _field_guide() -> str:
    """What each kind of operation may set, from the service's own validation tables."""
    lines = []
    for kind in OperationKind:
        spec = OPERATION_FIELDS[kind]
        create = [f"{f}*" for f in sorted(spec.required)] + sorted(spec.create - spec.required)
        parts = [f"create {', '.join(create)}"]
        if spec.update:
            parts.append(f"update {', '.join(sorted(spec.update))}")
        if spec.clearable:
            parts.append(f"null clears {', '.join(sorted(spec.clearable))}")
        if kind in MOVE_FIELDS:
            parts.append(f"move {', '.join(sorted(MOVE_FIELDS[kind]))}")
        lines.append(f"- {kind.value}: {'; '.join(parts)}")
    return "\n".join(lines)


_EVIDENCE_SCHEMA = {
    "type": "array",
    "description": "Supporting quotes or links",
    "items": {
        "type": "object",
        "properties": {
            "quote": {"type": "string", "description": "A quote from a source"},
            "url": {"type": "string", "description": "Where it comes from"},
            "entity_id": {"type": "string", "description": "A workspace entity it rests on"},
        },
    },
}

OPERATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "seq": {
            "type": "integer",
            "minimum": 0,
            "maximum": MAX_SEQ,
            "description": "Unique position in the proposal; operations apply in seq order",
        },
        "op": {"type": "string", "enum": [t.value for t in OperationType]},
        "kind": {"type": "string", "enum": [k.value for k in OperationKind]},
        "target_id": {
            "type": "string",
            "description": "The existing entity (update, move, delete); omit for a create",
        },
        "ref": {
            "type": "string",
            "description": (
                'Create only: a name for the new entity, so later operations can use "$<ref>"'
                " in an id field"
            ),
        },
        "fields": {
            "type": "object",
            "description": (
                "Create: every field (* required); update: only the changed ones; move: the"
                " new parent or scheme; delete: none"
            ),
        },
        "rationale": {"type": "string", "description": "Why this change"},
        "notes": {
            "type": "string",
            "description": (
                "Free-text notes to keep with this change (e.g. a maintainer's notes); never"
                " applied to the entity"
            ),
        },
        "evidence": _EVIDENCE_SCHEMA,
        "probability": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "description": "Your confidence in this change, 0 to 1",
        },
        "replacement": {
            "type": "string",
            "description": (
                "Property, class or predicate delete only: the relationship type, class or"
                ' predicate that replaces the deleted one, by id, identifier or "$<ref>" of an'
                " earlier create of the same kind. Name it whenever another type expresses the"
                " deleted one; review flags a relationship type replacement that links a"
                " different pair of classes. A predicate delete needs one while relationship"
                " types still use the predicate: they move to it"
            ),
        },
    },
    "required": ["seq", "op", "kind"],
}


class _ProposalTool(ToolBase):
    """Base for proposal tools: a missing proposal is an error outcome."""

    def __init__(self, service: ProposalService, source: ProposalSource) -> None:
        self._service = service
        self._source = source

    def _run_safely(self, args: dict[str, Any]) -> ToolOutcome:
        try:
            return super()._run_safely(args)
        except ChangeProposalNotFoundError:
            return error_outcome(
                f"No proposal found with id {args.get('id')!r}.", "Proposal not found"
            )


class ProposeChangesTool(_ProposalTool):
    """Propose a set of changes to one taxonomy, for a person to review."""

    name = "propose_changes"
    description = (
        "Propose changes to one taxonomy. You cannot change the workspace directly: a"
        " person reviews the proposal in Context Studio and accepts or rejects each"
        " operation; the taxonomy's approval policy may apply some at once. Read the"
        " taxonomy's vision (get_entity on it) first and judge each change against it."
        " Look up every id you use; never guess one. The whole proposal is validated"
        " first: if any operation is invalid nothing is stored and the result lists"
        " each problem by seq (stored false), so fix them and send all the operations"
        " again. Otherwise each operation comes back applied (by policy), pending or"
        " failed, with its scope (editorial, additive or breaking). A relationship-type"
        " delete whose type relationships still use has blockers: those relationships"
        " (edges), the types they could all move to (replacements) or why none fits"
        " (move_unavailable_reason); a reviewer must resolve them before it applies."
        " A delete naming its replacement has replacement_check (see get_proposal)."
        " With dry_run true nothing is stored or applied: you get the same check, each"
        " operation's scope, stale flag, blockers, replacement check and auto_apply"
        " (eligible to auto-apply: the approval policy would apply it at once and no"
        " blockers stop it; applying can still fail), then propose for real.\n"
        "Kind property is a relationship type (property definition); attribute is a"
        " data attribute of a class; relationship links two classes or individuals."
        " A property's canonical_predicate must be one of its taxonomy's predicates"
        " (list_predicates; the taxonomy of its domain class, else its range class,"
        " else the proposal's) or one a predicate create earlier in the proposal adds,"
        " and can't be cleared. Kind predicate is a relation verb in the proposal's"
        " taxonomy's catalog: its identifier (e.g. part_of, navigates-to) never changes;"
        " to rename one, create the new one and delete the old with it as replacement."
        " A DR predicate keeps inverse, category, archimate_alignment and semantics"
        " ({directionality, transitivity, symmetry, reflexivity}) in its"
        " documentation_robotics reference's metadata.\n"
        "Fields per kind (* required on create):\n"
        f"{_field_guide()}\n"
        "A relationship update sets only its attributes; to change its ends, delete it"
        " and create another. A DR relationship type (a property with a"
        " documentation_robotics external reference) keeps its spec strength and"
        " evidence lines in that reference's metadata:"
        ' {"strength", "evidence": [...]}. Give them on a create; to'
        " change them, update external_references, which replaces the whole list, so"
        " send every reference and every metadata key. A relationship type's structure"
        " is its own fields: min_per_source, max_per_source and max_per_target (null:"
        " no limit; DR's cardinality maps to them: many-to-one is max_per_source 1,"
        " one-to-many max_per_target 1, one-to-one both), hierarchy (no cycles) and"
        " symmetric (both need the same domain and range). Its edge attributes (values"
        " its relationships carry, such as a quantity) are attribute operations with"
        " property_definition_id instead of class_id; a relationship's attributes must"
        " fit them (datatype, allowed values, required). An individual's data_properties"
        " map attribute identifiers (of its classes, inherited ones included) to values"
        " of the attribute's datatype (a number is an integer or decimal, a date is"
        ' "YYYY-MM-DD" text); on an update, only those given change and null'
        " removes one. A class's operational definition: distinguish_from is"
        ' [{"class_id": an existing class of the taxonomy, "when": when to use it'
        " instead}], evidence_signals a list of text, standard_reference text; null"
        " clears each. Id fields"
        f' ({", ".join(sorted(ID_FIELDS))}) take an existing id or "$<ref>" of an'
        " earlier create in the same proposal.\n"
        f"At most {MAX_OPERATIONS} operations per proposal. For a larger pass, export"
        " the taxonomy's bundle (GET /api/v1/interchange/bundles/{taxonomy_id}), edit"
        " it and import it (POST /api/v1/interchange/bundles): the import proposes"
        " every change it plans as one proposal."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "taxonomy_id": {"type": "string", "description": "The taxonomy the changes are about"},
            "dataset": {
                "type": "string",
                "description": (
                    "The dataset (identifier or id) its individual and relationship"
                    " operations are in. Needed only when the taxonomy has several datasets"
                    " (see list_datasets); every individual they reference must be in it"
                ),
            },
            "title": {"type": "string", "description": "A short summary of the proposal"},
            "rationale": {"type": "string", "description": "Why these changes, as a whole"},
            "operations": {
                "type": "array",
                "minItems": 1,
                "maxItems": MAX_OPERATIONS,
                "items": OPERATION_SCHEMA,
            },
            "dry_run": {
                "type": "boolean",
                "description": "Validate and preview only; store and apply nothing",
            },
            "source_revision": {
                **SOURCE_REVISION_SCHEMA,
                "description": (
                    "For a taxonomy that mirrors your source (a spec in your repository):"
                    " the revision you drafted the proposal against. Without it, the"
                    " revision the taxonomy was last imported at is recorded."
                ),
            },
        },
        "required": ["taxonomy_id", "title", "operations"],
    }

    def run(self, args: dict[str, Any]) -> ToolOutcome:
        taxonomy_id = required_str(args, "taxonomy_id")
        title = required_str(args, "title")
        rationale = optional_str(args, "rationale")
        dry_run = args.get("dry_run", False)
        if not isinstance(dry_run, bool):
            raise ToolArgumentError("'dry_run' must be true or false")
        raw = args.get("operations")
        if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_OPERATIONS:
            raise ToolArgumentError(f"'operations' must be a list of 1 to {MAX_OPERATIONS} items")

        revision = _revision(args.get("source_revision"), "source_revision")
        drafts, errors = _drafts(raw)
        if errors:
            return _not_stored(errors, drafts, checked=False)
        try:
            proposal = self._service.propose(
                taxonomy_id,
                title,
                drafts,
                self._source,
                rationale=rationale,
                dry_run=dry_run,
                source_revision=revision,
                dataset_id=optional_str(args, "dataset"),
            )
        except ProposalValidationError as exc:
            return _not_stored(exc.errors, drafts)
        except Exception:  # noqa: BLE001 - the agent gets an answer, the log the detail
            _logger.exception("propose_changes could not store a proposal")
            return error_outcome(
                f"The proposal could not be {'checked' if dry_run else 'stored'} because of"
                " a server error.",
                "Proposal not checked" if dry_run else "Proposal not stored",
            )
        try:
            view = _view(self._service, proposal, dry_run=dry_run)
        except Exception:  # noqa: BLE001 - stored already: never invite a duplicate
            _logger.exception("propose_changes could not describe proposal %s", proposal.id)
            if dry_run:
                return error_outcome(
                    "The dry run passed validation, but its details could not be read"
                    " because of a server error.",
                    "Dry run details unavailable",
                )
            return _stored(proposal, None)
        return _dry_run(view) if dry_run else _stored(proposal, view)


def _drafts(raw: Sequence[Any]) -> tuple[list[OperationDraft], list[OperationError]]:
    """
    Operation drafts from tool input, and the problems the service can't report
    itself (an item that isn't an object, a missing seq, a non-text ref).
    """
    drafts: list[OperationDraft] = []
    errors: list[OperationError] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            errors.append(OperationError(None, "invalid", f"operations[{index}] is not an object"))
            continue
        seq = item.get("seq")
        if isinstance(seq, bool) or not isinstance(seq, int):
            errors.append(
                OperationError(None, "invalid", f"operations[{index}] needs an integer seq")
            )
            continue
        bad_text = [
            k
            for k in ("ref", "rationale", "notes", "replacement")
            if item.get(k) is not None and not isinstance(item.get(k), str)
        ]
        if bad_text:
            errors.append(OperationError(seq, "invalid", f"{', '.join(bad_text)} must be text"))
            continue
        drafts.append(
            OperationDraft(
                seq=seq,
                op=item.get("op", ""),
                kind=item.get("kind", ""),
                target_id=item.get("target_id"),
                ref=item.get("ref"),
                fields=item.get("fields") or {},
                rationale=item.get("rationale"),
                notes=item.get("notes"),
                evidence=item.get("evidence") or [],
                probability=item.get("probability"),
                replacement=item.get("replacement"),
            )
        )
    return drafts, errors


def _not_stored(
    errors: Sequence[OperationError], drafts: Sequence[OperationDraft], checked: bool = True
) -> ToolOutcome:
    """
    A rejected proposal: every problem, so the agent can fix them and resend.

    Args:
        errors: The problems found
        drafts: The operations that could be read
        checked: Whether the service validated the drafts; when the input
            itself was malformed they are listed as unchecked instead of valid
    """
    invalid = [
        {"seq": e.seq, "status": "invalid", "code": e.code, "message": e.message}
        for e in errors
        if e.seq is not None
    ]
    general = [{"code": e.code, "message": e.message} for e in errors if e.seq is None]
    others = sorted({d.seq for d in drafts} - {e.seq for e in errors})
    payload: dict[str, Any] = {
        "stored": False,
        "id": None,
        "errors": general,
        "operations": invalid,
        ("valid_seqs" if checked else "unchecked_seqs"): others,
        "next": (
            "Nothing was stored. Fix the errors and invalid operations, then call"
            " propose_changes again with all the operations."
        ),
    }
    content, _ = _capped(payload, "operations", lambda _: "fix these and resend to see the rest")
    return ToolOutcome(content=content, summary=f"Proposal not stored: {len(errors)} problems")


# What propose_changes reports of each operation (get_proposal has the rest).
_OUTCOME_KEYS = ("seq", "status", "scope", "result_entity_id", "reason", "blockers")
_DRY_RUN_KEYS = (
    "seq",
    "op",
    "kind",
    "scope",
    "auto_apply",
    "stale",
    "blockers",
    "dataset_impact",
)


def _outcomes(view: dict[str, Any], keys: Sequence[str]) -> list[dict[str, Any]]:
    """Each operation of a proposal view, by the given keys and its replacement check."""
    return [{k: o[k] for k in (*keys, "replacement_check") if k in o} for o in view["operations"]]


def _stored(proposal: ChangeProposal, view: Optional[dict[str, Any]]) -> ToolOutcome:
    """
    A stored proposal: each operation's status, scope and blockers, and what
    happens next. Without a view (it could not be read), each operation's
    status and scope only, and a note that the details are unavailable.
    """
    counts = _counts(proposal)
    if view is not None:
        operations = _outcomes(view, _OUTCOME_KEYS)
    else:
        operations = [
            {"seq": o.seq, "status": o.status.value, "scope": o.scope.value}
            for o in proposal.operations
        ]
    payload: dict[str, Any] = {
        "stored": True,
        "id": proposal.id,
        "kind": PROPOSAL_KIND,
        "title": proposal.title,
        "taxonomy_id": proposal.taxonomy_id,
        "dataset_id": proposal.dataset_id,
        "status": proposal.status.value,
        "counts": counts,
        "operations": operations,
        "next": _next_step(counts),
    }
    if view is None:
        payload["details_unavailable"] = (
            "The proposal is stored; its blockers and checks could not be read. Do not"
            " propose it again: get_proposal shows them."
        )
    content, _ = _capped(
        payload, "operations", lambda kept: f"get_proposal with offset {kept} shows the rest"
    )
    return ToolOutcome(
        content=content,
        summary=_summary("Proposed", proposal.title, counts),
        entities=(proposal_ref(proposal),),
    )


def _dry_run(view: dict[str, Any]) -> ToolOutcome:
    """A dry run: what proposing would do, with nothing stored."""
    operations = _outcomes(view, _DRY_RUN_KEYS)
    auto = sum(1 for o in operations if o.get("auto_apply"))
    blocked = sum(1 for o in operations if "blockers" in o)
    notes = [
        f"Nothing was stored. Proposed, {auto} would apply at once under the approval"
        f" policy and {len(operations) - auto} would wait for review."
    ]
    if blocked:
        notes.append(f"{blocked} blocked by relationships still using the type.")
    notes.append("Call propose_changes again without dry_run to store it.")
    payload: dict[str, Any] = {
        "stored": False,
        "dry_run": True,
        "id": None,
        "title": view["title"],
        "taxonomy_id": view["taxonomy_id"],
        "dataset_id": view.get("dataset_id"),
        "operations": operations,
        "next": " ".join(notes),
    }
    note = "the rest validated; split the proposal to see them"
    if len(dumps(payload)) > MAX_PROPOSAL_CHARS:
        payload = _dry_run_digest(payload)
        note = "attention_seqs lists every operation that needs attention"
    content, _ = _capped(payload, "operations", lambda _: note)
    return ToolOutcome(content=content, summary=f"Dry run “{view['title']}”: {auto} would apply")


def _needs_attention(operation: dict[str, Any]) -> bool:
    """
    A dry-run operation that is blocked, stale, or names a replacement that
    isn't the same pair of classes or that the proposal also deletes.
    """
    check = operation.get("replacement_check") or {}
    flagged = check and (
        check.get("pair") != "same" or check.get("replacement_deleted") or check.get("cycle")
    )
    return bool(operation.get("blockers") or operation.get("stale") or flagged)


def _dry_run_digest(payload: dict[str, Any]) -> dict[str, Any]:
    """
    A dry run too large to list whole: the operations that need attention in
    full, and every other one by seq, split by whether it would auto-apply.
    """
    operations = payload["operations"]
    attention = [o for o in operations if _needs_attention(o)]
    plain = [o for o in operations if not _needs_attention(o)]
    return {
        **payload,
        "operations": attention,
        "attention_seqs": [o["seq"] for o in attention],
        "auto_apply_seqs": [o["seq"] for o in plain if o.get("auto_apply")],
        "review_seqs": [o["seq"] for o in plain if not o.get("auto_apply")],
        "digest": (
            "too many operations to list whole: operations details those blocked, stale"
            " or with a flagged replacement (attention_seqs lists them all); the rest"
            " validated and are listed by seq"
        ),
    }


def _next_step(counts: dict[str, int]) -> str:
    notes = []
    if counts["applied"]:
        notes.append(f"{counts['applied']} applied under the taxonomy's approval policy.")
    if counts["pending"]:
        notes.append(
            f"{counts['pending']} pending: a person reviews them in Context Studio, and"
            " none of them changes the workspace until accepted. Follow up with get_proposal."
        )
    if counts["failed"]:
        notes.append(f"{counts['failed']} failed to apply; the reason says why.")
    return " ".join(notes)


def _summary(label: str, title: str, counts: dict[str, int]) -> str:
    parts = [f"{n} {status}" for status, n in counts.items() if n]
    return f"{label} “{title}”: {', '.join(parts)}"


class GetProposalTool(_ProposalTool):
    """One proposal with each operation's status and stale flag."""

    name = "get_proposal"
    description = (
        "Get one change proposal by id: its status (open while any operation awaits a"
        " decision, done, or reverted) and each operation's seq, op, kind, target,"
        " fields, status (pending, applied, rejected or failed), scope and stale flag."
        " A stale operation's target changed or is gone since it was proposed: a"
        " reviewer may still apply it, or you can propose the change again against the"
        " current values. A property delete that names its replacement has"
        " replacement_check: its pair is same, reversed or different (the replacement"
        " links a different pair of classes than the deleted type, so it can't take over"
        " its relationships), or missing; replacement_deleted means the proposal deletes"
        " the replacement too (chain follows each delete's replacement; cycle means the"
        " deletes name each other and none survives). A pending relationship-type delete"
        " still in use has blockers (see propose_changes). Each operation also has its"
        " base (the touched values when proposed; a delete's whole entity), rationale,"
        " notes, evidence and probability, and once decided applied_fields (a reviewer's edit),"
        " resolution (what happened to a delete's relationships) and reason. Empty"
        " values are left out. A large proposal leaves out base and evidence, keeps"
        " fields, and pages its operations: pass the offset its truncated note gives."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "Proposal id"},
            "offset": {
                "type": "integer",
                "minimum": 0,
                "description": "Operations to skip, for a proposal too large for one result",
            },
        },
        "required": ["id"],
    }

    def run(self, args: dict[str, Any]) -> ToolOutcome:
        proposal = self._service.get(required_str(args, "id"))
        offset = int_arg(args, "offset", 0, 0, len(proposal.operations))
        view = _view(self._service, proposal)
        payload: dict[str, Any] = {
            **_proposal_summary(proposal),
            **{k: v for k, v in view.items() if k != "operations"},
            "offset": offset,
            "operations": view["operations"][offset:],
        }
        content = dumps(payload)
        if len(content) > MAX_PROPOSAL_CHARS:
            # The bulky values go first (the review page shows them), then whole operations.
            payload["operations"] = [
                {k: v for k, v in o.items() if k not in BULKY_OPERATION_KEYS}
                for o in payload["operations"]
            ]
            payload["fields_omitted"] = (
                f"{' and '.join(BULKY_OPERATION_KEYS)} are left out to fit (the review page"
                " shows them); fields and applied_fields are kept"
            )
            total = len(view["operations"])

            def note(kept: int) -> str:
                return f"pass offset {offset + kept} for the rest"

            content, kept = _capped(payload, "operations", note, total, offset)
            if len(content) > MAX_PROPOSAL_CHARS:
                # One operation's own fields are too large: they go too.
                payload["operations"] = [
                    {k: v for k, v in o.items() if k not in ("fields", "applied_fields")}
                    for o in kept
                ]
                payload["fields_omitted_seqs"] = [o["seq"] for o in kept]
                if offset + len(kept) < total:
                    payload["truncated"] = (
                        f"showing {offset + 1}-{offset + len(kept)} of {total};"
                        f" {note(len(kept))}"
                    )
                content, _ = _capped(payload, "operations", note, total, offset)
        return ToolOutcome(
            content=content,
            summary=_summary("Proposal", proposal.title, payload["counts"]),
            entities=(proposal_ref(proposal),),
        )


def _timestamp(value: datetime) -> str:
    """A timestamp as REST writes it (UTC as Z), so list_proposals and get_proposal agree."""
    return TypeAdapter(datetime).dump_python(value, mode="json")


def _proposal_summary(proposal: ChangeProposal) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "id": proposal.id,
        "kind": PROPOSAL_KIND,
        "title": proposal.title,
        "taxonomy_id": proposal.taxonomy_id,
        "dataset_id": proposal.dataset_id,
        "source": proposal.source.value,
        "created_at": _timestamp(proposal.created_at),
        "status": proposal.status.value,
        "counts": _counts(proposal),
    }
    if proposal.landed is not None:
        summary["landed"] = {
            **{k: v for k, v in proposal.landed.revision.to_dict().items() if v is not None},
            "landed_at": _timestamp(proposal.landed.landed_at),
        }
    return summary


class ListProposalsTool(_ProposalTool):
    """Proposals, newest first."""

    name = "list_proposals"
    description = (
        "List change proposals, newest first, optionally for one taxonomy and with one"
        " status (open: awaiting decisions; done: every operation applied or rejected;"
        " reverted). Each has its id, title, source, operation counts by status and,"
        " once its client landed it in the taxonomy's source, landed (repo, commit,"
        " spec_version, landed_at). landed false with status done lists the decided"
        " proposals not yet landed. Done proposals with applied operations are the"
        " record of what changed in a taxonomy; read one with get_proposal."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "taxonomy_id": {"type": "string", "description": "Only proposals about this taxonomy"},
            "status": {"type": "string", "enum": [s.value for s in ProposalStatus]},
            "landed": {
                "type": "boolean",
                "description": "Only proposals landed (true) or not landed (false) in the source",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": MAX_LIMIT,
                "description": f"Maximum results (default {DEFAULT_LIMIT}, max {MAX_LIMIT})",
            },
            "offset": {"type": "integer", "minimum": 0, "description": "Proposals to skip"},
        },
    }

    def run(self, args: dict[str, Any]) -> ToolOutcome:
        taxonomy_id = optional_str(args, "taxonomy_id")
        status = _status(optional_str(args, "status"))
        limit = int_arg(args, "limit", DEFAULT_LIMIT, 1, MAX_LIMIT)
        offset = int_arg(args, "offset", 0, 0, 1_000_000)
        landed = args.get("landed")
        if landed is not None and not isinstance(landed, bool):
            raise ToolArgumentError("'landed' must be true or false")
        proposals = self._service.list_proposals(
            taxonomy_id=taxonomy_id, status=status, limit=limit, offset=offset, landed=landed
        )
        total = self._service.count_proposals(taxonomy_id=taxonomy_id, status=status, landed=landed)
        payload = {
            "items": [_proposal_summary(p) for p in proposals],
            "total": total,
            "offset": offset,
        }
        content, items = _capped(
            payload, "items", lambda kept: f"pass offset {offset + kept} for the rest"
        )
        shown = {item["id"] for item in items}
        return ToolOutcome(
            content=content,
            summary=f"{len(proposals)} of {total} proposals",
            entities=tuple(proposal_ref(p) for p in proposals if p.id in shown),
        )


class MarkProposalLandedTool(_ProposalTool):
    """A client reports that it landed a decided proposal in its source."""

    name = "mark_proposal_landed"
    description = (
        "Record that you landed a decided (done) proposal in the taxonomy's source: the"
        " repository, the commit that holds the change, and the spec version. Call it"
        " from your landing step after writing the proposal's changes into your source;"
        " it changes nothing in the taxonomy. The same revision again changes nothing;"
        " another revision replaces the landing. An open or reverted proposal can't be"
        " marked landed. list_proposals with status done and landed false lists what is"
        " still to land."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "Proposal id"},
            "repo": {"type": "string", "description": "The source repository"},
            "commit": {"type": "string", "description": "The commit that holds the change"},
            "spec_version": {"type": "string", "description": "The source's version label"},
        },
        "required": ["id", "commit"],
    }

    def run(self, args: dict[str, Any]) -> ToolOutcome:
        proposal_id = required_str(args, "id")
        revision = _revision(
            {k: args.get(k) for k in ("repo", "commit", "spec_version") if args.get(k) is not None},
            "the revision",
        )
        try:
            proposal = self._service.mark_landed(proposal_id, revision)  # type: ignore[arg-type]
        except ChangeProposalStateError as exc:
            return error_outcome(str(exc), "Proposal not marked landed")
        except ValueError as exc:
            raise ToolArgumentError(str(exc)) from None
        return ToolOutcome(
            content=dumps(_proposal_summary(proposal)),
            summary=f"Proposal marked landed: {proposal.title}",
            entities=(proposal_ref(proposal),),
        )


class DrSpecDriftTool(ToolBase):
    """Report, or propose, the drift between the DR spec on disk and its taxonomy."""

    name = "dr_spec_drift"
    description = (
        "Compare the DR spec on disk with Context Studio's dr_spec taxonomy, matched by"
        " DR id (node types moved to another layer are followed), and list what differs:"
        " each entry has kind (taxonomy, scheme, class, property, attribute, predicate),"
        " source_id (the DR id; an attribute is '<node id>#<name>'), change (create,"
        " update, move, delete) and fields: each differing field's taxonomy and source"
        " value (null where one side has none; a create lists what it would set)."
        " groups counts every entry by kind, change and field names, whatever page is"
        " shown. Entries page: pass the offset the truncated note gives, and kind or"
        " change to narrow them. With dry_run true (the default) nothing is stored; with"
        " dry_run false the drift is proposed as one change proposal for a person to"
        " review (it supersedes the open proposal of an earlier re-import). Pass the"
        " spec/ directory of your DR checkout, the one holding dist/manifest.json."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "spec_dir": {
                "type": "string",
                "description": "Absolute path of the DR checkout's spec/ directory",
            },
            "dry_run": {
                "type": "boolean",
                "description": "Report only (default true); false proposes the drift",
            },
            "kind": {
                "type": "string",
                "enum": list(DRIFT_KINDS),
                "description": "Only entries of this kind",
            },
            "change": {
                "type": "string",
                "enum": list(DRIFT_CHANGES),
                "description": "Only entries with this change",
            },
            "offset": {
                "type": "integer",
                "minimum": 0,
                "description": "First entry to show, among those matching kind and change",
            },
        },
        "required": ["spec_dir"],
    }

    def __init__(self, service: DriftImportService) -> None:
        self._service = service

    def run(self, args: dict[str, Any]) -> ToolOutcome:
        spec_dir = required_str(args, "spec_dir")
        dry_run = args.get("dry_run", True)
        if not isinstance(dry_run, bool):
            raise ToolArgumentError("'dry_run' must be true or false")
        kind = _optional_choice(args, "kind", DRIFT_KINDS)
        change = _optional_choice(args, "change", DRIFT_CHANGES)
        try:
            result = self._service.reimport(spec_dir, dry_run=dry_run)
        except DriftError as exc:
            return error_outcome(str(exc), "Drift not checked")
        except ProposalValidationError as exc:
            errors = [{"seq": e.seq, "code": e.code, "message": e.message} for e in exc.errors]
            return error_outcome(
                dumps({"stored": False, "errors": errors}), "Drift proposal invalid"
            )
        plan, proposal = result.plan, result.proposal
        revision = plan.source_revision
        stored = proposal is not None and not result.dry_run
        payload: dict[str, Any] = _compact(
            {
                "taxonomy_id": plan.taxonomy_id,
                "source_revision": revision.to_dict() if revision else None,
                "dry_run": result.dry_run,
                "total": len(plan.entries),
                "proposal": _proposal_summary(proposal) if stored else None,  # type: ignore[arg-type]
                "operations": len(proposal.operations) if proposal and not stored else None,
            }
        )
        payload["groups"] = _drift_groups(plan.entries)
        matching = [
            entry
            for entry in plan.entries
            if (kind is None or entry.kind == kind) and (change is None or entry.change == change)
        ]
        offset = int_arg(args, "offset", 0, 0, len(matching))
        if kind or change:
            payload["matching"] = len(matching)
        if offset:
            payload["offset"] = offset

        def note(kept: int) -> str:
            rest = f"pass offset {offset + kept} for the next page"
            return f"{rest}; the proposal's review page lists every change" if stored else rest

        # Entries stay even when empty: "no drift" is the answer.
        payload["entries"] = [_drift_entry(entry) for entry in matching[offset:]]
        content, _ = _capped(payload, "entries", note, len(matching), offset)
        summary = f"{len(plan.entries)} entities differ" + (
            f"; proposed as {proposal.title}" if stored else ""
        )  # type: ignore[union-attr]
        return ToolOutcome(
            content=content,
            summary=summary,
            entities=(proposal_ref(proposal),) if stored else (),  # type: ignore[arg-type]
        )


def _optional_choice(args: dict[str, Any], name: str, choices: Sequence[str]) -> Optional[str]:
    """An optional argument that must be one of the choices, or None when absent."""
    value = args.get(name)
    if value is None:
        return None
    if value not in choices:
        raise ToolArgumentError(f"'{name}' must be one of {', '.join(choices)}")
    return str(value)


def _drift_entry(entry: DriftEntry) -> dict[str, Any]:
    """
    A drift entry for the tool. Unlike _compact, it keeps nulls inside fields,
    so a value one side lacks shows as null rather than vanishing.
    """
    view: dict[str, Any] = {"kind": entry.kind, "source_id": entry.source_id, "change": entry.change}
    if entry.entity_id:
        view["entity_id"] = entry.entity_id
    if entry.fields:
        view["fields"] = entry.fields
    return view


def _drift_groups(entries: Sequence[DriftEntry]) -> list[dict[str, Any]]:
    """
    Every entry counted by kind, change and, for an update or move, the names
    of the fields that differ; largest group first.
    """
    counts: dict[tuple[str, str, tuple[str, ...]], int] = {}
    for entry in entries:
        names = tuple(sorted(entry.fields)) if entry.change in ("update", "move") else ()
        key = (entry.kind, entry.change, names)
        counts[key] = counts.get(key, 0) + 1
    groups = []
    for (kind, change, names), count in sorted(counts.items(), key=lambda item: -item[1]):
        group: dict[str, Any] = {"kind": kind, "change": change, "count": count}
        if names:
            group["fields"] = list(names)
        groups.append(group)
    return groups


def _revision(value: Any, name: str) -> Optional[SourceRevision]:
    """A source revision argument ({repo, commit, spec_version}), or None when absent."""
    if value is None:
        return None
    try:
        return SourceRevision.from_dict(value)
    except ValueError as exc:
        raise ToolArgumentError(f"{name}: {exc}") from None


def _status(value: Optional[str]) -> Optional[ProposalStatus]:
    if value is None:
        return None
    try:
        return ProposalStatus(value)
    except ValueError:
        choices = ", ".join(s.value for s in ProposalStatus)
        raise ToolArgumentError(f"'status' must be one of {choices}") from None


def build_proposal_tools(service: ProposalService, source: ProposalSource) -> list[ToolBase]:
    """
    The proposal tools, in the order offered to the model: propose, then follow.

    Args:
        service: Makes and reads proposals
        source: Recorded on every proposal these tools make (chat or MCP)
    """
    return [
        ProposeChangesTool(service, source),
        GetProposalTool(service, source),
        ListProposalsTool(service, source),
    ]
