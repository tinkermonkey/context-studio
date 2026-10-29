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
from domain.chat.value_objects import EntityRef, ToolOutcome
from domain.versioning.exceptions import (
    ChangeProposalNotFoundError,
    OperationError,
    ProposalValidationError,
)
from domain.versioning.proposal_service import (
    ID_FIELDS,
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
    ProposedOperation,
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


def proposal_ref(proposal: ChangeProposal) -> EntityRef:
    """The link reference for a proposal: its review page."""
    return EntityRef(id=proposal.id, kind=PROPOSAL_KIND, title=proposal.title)


def _counts(proposal: ChangeProposal) -> dict[str, int]:
    """Operations per status, every status present."""
    counts = {s.value: 0 for s in OperationStatus}
    for operation in proposal.operations:
        counts[operation.status.value] += 1
    return counts


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
        " failed, with its scope (editorial, additive or breaking).\n"
        "Kind property is a relationship type (property definition); attribute is a"
        " data attribute of a class; relationship links two classes or individuals.\n"
        "Fields per kind (* required on create):\n"
        f"{_field_guide()}\n"
        "A relationship update sets only its attributes; to change its ends, delete it"
        " and create another. Id fields"
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
        },
        "required": ["taxonomy_id", "title", "operations"],
    }

    def run(self, args: dict[str, Any]) -> ToolOutcome:
        taxonomy_id = required_str(args, "taxonomy_id")
        title = required_str(args, "title")
        rationale = optional_str(args, "rationale")
        raw = args.get("operations")
        if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_OPERATIONS:
            raise ToolArgumentError(f"'operations' must be a list of 1 to {MAX_OPERATIONS} items")

        drafts, errors = _drafts(raw)
        if errors:
            return _not_stored(errors, drafts, checked=False)
        try:
            proposal = self._service.propose(
                taxonomy_id, title, drafts, self._source, rationale=rationale
            )
        except ProposalValidationError as exc:
            return _not_stored(exc.errors, drafts)
        except Exception:  # noqa: BLE001 - the agent gets an answer, the log the detail
            _logger.exception("propose_changes could not store a proposal")
            return error_outcome(
                "The proposal could not be stored because of a server error.",
                "Proposal not stored",
            )
        return _stored(proposal)


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
            for k in ("ref", "rationale")
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


def _stored(proposal: ChangeProposal) -> ToolOutcome:
    """A stored proposal: each operation's status and scope, and what happens next."""
    counts = _counts(proposal)
    operations = []
    for operation in proposal.operations:
        item: dict[str, Any] = {
            "seq": operation.seq,
            "status": operation.status.value,
            "scope": operation.scope.value,
        }
        if operation.result_entity_id:
            item["result_entity_id"] = operation.result_entity_id
        if operation.reason:
            item["reason"] = operation.reason
        operations.append(item)
    ref = proposal_ref(proposal)
    payload: dict[str, Any] = {
        "stored": True,
        "id": proposal.id,
        "kind": PROPOSAL_KIND,
        "title": proposal.title,
        "taxonomy_id": proposal.taxonomy_id,
        "status": proposal.status.value,
        "counts": counts,
        "operations": operations,
        "next": _next_step(counts),
    }
    content, _ = _capped(
        payload, "operations", lambda kept: f"get_proposal with offset {kept} shows the rest"
    )
    return ToolOutcome(
        content=content,
        summary=_summary("Proposed", proposal.title, counts),
        entities=(ref,),
    )


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
        " current values. A large proposal's operations page with offset."
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
        stale = self._service.stale_operation_ids(proposal)
        payload: dict[str, Any] = {
            **_proposal_summary(proposal),
            "rationale": proposal.rationale,
            "offset": offset,
            "operations": [_operation(o, o.id in stale) for o in proposal.operations[offset:]],
        }
        content = dumps(payload)
        if len(content) > MAX_PROPOSAL_CHARS:
            # Fields go first (the review page shows them), then whole operations.
            payload["operations"] = [
                {k: v for k, v in o.items() if k != "fields"} for o in payload["operations"]
            ]
            payload["fields_omitted"] = "too large for one result; the review page shows them"
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


def _operation(operation: ProposedOperation, stale: bool) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": operation.id,
        "seq": operation.seq,
        "op": operation.op.value,
        "kind": operation.kind.value,
    }
    if operation.target_id:
        item["target_id"] = operation.target_id
    if operation.ref:
        item["ref"] = operation.ref
    item["fields"] = operation.fields
    item["status"] = operation.status.value
    item["scope"] = operation.scope.value
    item["stale"] = stale
    if operation.result_entity_id:
        item["result_entity_id"] = operation.result_entity_id
    if operation.reason:
        item["reason"] = operation.reason
    return item


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
