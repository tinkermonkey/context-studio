"""
Proposal tools for the chat assistant and the MCP server: propose changes to a
taxonomy, then follow them.

An agent proposes; a person reviews. These tools can only make and read change
proposals. Accepting, rejecting, applying or reverting operations, and setting a
taxonomy's approval policy, are a person's decisions in the app and are never
offered as tools.

`build_proposal_tools` is instantiated once per caller with its ProposalSource
(chat or MCP). Every result names its proposals with kind "proposal", so chat
answers can link them as `entity:proposal/<id>` and MCP results end with their
review page links. Results are compact JSON capped at MAX_PROPOSAL_CHARS: when a
result is longer, whole entries are dropped and the result says so.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional, Sequence

from adapters.chat.tools import (
    ToolArgumentError,
    ToolBase,
    dumps,
    error_outcome,
    int_arg,
    optional_str,
    required_str,
)
from adapters.web.schemas.proposals import proposal_response
from domain.chat.value_objects import EntityRef, ToolOutcome
from domain.versioning.exceptions import (
    ChangeProposalNotFoundError,
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

PROPOSAL_KIND = "proposal"
MAX_OPERATIONS = 200
# Large enough for a full 200-operation propose result.
MAX_PROPOSAL_CHARS = 16000
# A result too large even with one entry has its texts cut to this length.
CLIPPED_TEXT_CHARS = 300
DEFAULT_LIMIT = 20
MAX_LIMIT = 50
# An in-use blocker lists at most this many of its relationships; the review page has all.
MAX_BLOCKER_EDGES = 10
# Dropped from get_proposal's operations first when a result is too large.
BULKY_OPERATION_KEYS = ("fields", "base", "applied_fields", "evidence")


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
    in-use blocker lists at most MAX_BLOCKER_EDGES relationships (edges_total
    says how many there are).
    """
    view = _compact(proposal_response(service, proposal, dry_run=dry_run).model_dump(mode="json"))
    for operation in view["operations"]:
        blockers = operation.get("blockers")
        if blockers and len(blockers.get("edges", ())) > MAX_BLOCKER_EDGES:
            blockers["edges_total"] = len(blockers["edges"])
            blockers["edges"] = blockers["edges"][:MAX_BLOCKER_EDGES]
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
    payload: dict[str, Any], list_key: str, note: Callable[[int], str]
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
    """
    total = len(payload[list_key])

    def fit(current: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        items = list(current[list_key])
        content = dumps(current)
        while len(items) > 1 and len(content) > MAX_PROPOSAL_CHARS:
            items = items[: max(len(items) * 3 // 4, 1)]
            truncated = f"showing {len(items)} of {total}; {note(len(items))}"
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
                "Property delete only: the relationship type that replaces the deleted one,"
                ' by id, identifier or "$<ref>" of an earlier property create. Name it'
                " whenever another type expresses the deleted one; review flags a replacement"
                " that links a different pair of classes"
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
        " (whether the approval policy would apply it at once), then propose for real.\n"
        "Kind property is a relationship type (property definition); attribute is a"
        " data attribute of a class; relationship links two classes or individuals.\n"
        "Fields per kind (* required on create):\n"
        f"{_field_guide()}\n"
        "A relationship update sets only its attributes; to change its ends, delete it"
        " and create another. A DR relationship type (a property with a"
        " documentation_robotics external reference) keeps its spec cardinality,"
        " strength and evidence lines in that reference's metadata:"
        ' {"cardinality", "strength", "evidence": [...]}. Give them on a create; to'
        " change them, update external_references, which replaces the whole list, so"
        " send every reference and every metadata key. Id fields"
        f' ({", ".join(sorted(ID_FIELDS))}) take an existing id or "$<ref>" of an'
        " earlier create in the same proposal."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "taxonomy_id": {"type": "string", "description": "The taxonomy the changes are about"},
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

        drafts, errors = _drafts(raw)
        if errors:
            return _not_stored(errors, drafts, checked=False)
        try:
            proposal = self._service.propose(
                taxonomy_id, title, drafts, self._source, rationale=rationale, dry_run=dry_run
            )
            view = _view(self._service, proposal, dry_run=dry_run)
        except ProposalValidationError as exc:
            return _not_stored(exc.errors, drafts)
        except Exception:  # noqa: BLE001 - the agent gets an answer, the log the detail
            _logger.exception("propose_changes could not store a proposal")
            return error_outcome(
                "The proposal could not be stored because of a server error.",
                "Proposal not stored",
            )
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
            for k in ("ref", "rationale", "replacement")
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
_DRY_RUN_KEYS = ("seq", "op", "kind", "scope", "auto_apply", "stale", "blockers")


def _outcomes(view: dict[str, Any], keys: Sequence[str]) -> list[dict[str, Any]]:
    """Each operation of a proposal view, by the given keys and its replacement check."""
    return [{k: o[k] for k in (*keys, "replacement_check") if k in o} for o in view["operations"]]


def _stored(proposal: ChangeProposal, view: dict[str, Any]) -> ToolOutcome:
    """A stored proposal: each operation's status, scope and blockers, and what happens next."""
    counts = _counts(proposal)
    payload: dict[str, Any] = {
        "stored": True,
        "id": proposal.id,
        "kind": PROPOSAL_KIND,
        "title": proposal.title,
        "taxonomy_id": proposal.taxonomy_id,
        "status": proposal.status.value,
        "counts": counts,
        "operations": _outcomes(view, _OUTCOME_KEYS),
        "next": _next_step(counts),
    }
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
        "operations": operations,
        "next": " ".join(notes),
    }
    content, _ = _capped(
        payload, "operations", lambda _: "the rest validated; propose to see them all"
    )
    return ToolOutcome(content=content, summary=f"Dry run “{view['title']}”: {auto} would apply")


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
        " evidence and probability, and once decided applied_fields (a reviewer's edit),"
        " resolution (what happened to a delete's relationships) and reason. Empty"
        " values are left out. A large proposal's operations page with offset."
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
        offset = int_arg(args, "offset", 0, 0, MAX_OPERATIONS)
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
                f"{', '.join(BULKY_OPERATION_KEYS)} are too large for one result; the review"
                " page shows them"
            )
            content, _ = _capped(
                payload, "operations", lambda kept: f"pass offset {offset + kept} for the rest"
            )
        return ToolOutcome(
            content=content,
            summary=_summary("Proposal", proposal.title, payload["counts"]),
            entities=(proposal_ref(proposal),),
        )


def _proposal_summary(proposal: ChangeProposal) -> dict[str, Any]:
    return {
        "id": proposal.id,
        "kind": PROPOSAL_KIND,
        "title": proposal.title,
        "taxonomy_id": proposal.taxonomy_id,
        "source": proposal.source.value,
        "created_at": proposal.created_at.isoformat(),
        "status": proposal.status.value,
        "counts": _counts(proposal),
    }


class ListProposalsTool(_ProposalTool):
    """Proposals, newest first."""

    name = "list_proposals"
    description = (
        "List change proposals, newest first, optionally for one taxonomy and with one"
        " status (open: awaiting decisions; done: every operation applied or rejected;"
        " reverted). Each has its id, title, source and operation counts by status."
        " Done proposals with applied operations are the record of what changed in a"
        " taxonomy; read one with get_proposal."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "taxonomy_id": {"type": "string", "description": "Only proposals about this taxonomy"},
            "status": {"type": "string", "enum": [s.value for s in ProposalStatus]},
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
        proposals = self._service.list_proposals(
            taxonomy_id=taxonomy_id, status=status, limit=limit, offset=offset
        )
        total = self._service.count_proposals(taxonomy_id=taxonomy_id, status=status)
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
