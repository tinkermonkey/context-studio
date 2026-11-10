"""
Claim tools for MCP clients (#1518): submit the claims a client split from its
notes, and list a taxonomy's claims with their triage and verdicts. Claims
change nothing in the taxonomy; changes still arrive as proposals.
"""

from __future__ import annotations

from typing import Any, Sequence

from pydantic import ValidationError

from adapters.chat.tools import (
    ToolArgumentError,
    ToolBase,
    dumps,
    error_outcome,
    int_arg,
    optional_str,
    required_str,
)
from adapters.web.schemas.claims import ClaimInput, ClaimResponse
from domain.chat.value_objects import ToolOutcome
from domain.ontology.exceptions import EntityNotFoundError
from domain.versioning.claims import ClaimFilter, ClaimService, Validity

_CLAIM_SCHEMA = {
    "type": "object",
    "properties": {
        "key": {"type": "string", "description": '"<note_ref>#<n>", unique in the taxonomy'},
        "text": {"type": "string", "description": "The claim, in a sentence or two"},
        "note_ref": {"type": "string", "description": "The note it came from"},
        "note_source": {"type": "string", "enum": ["maintainer", "reviewer"]},
        "note_text": {"type": "string", "description": "The note's full text"},
        "subject_id": {"type": "string", "description": "The entity the note was about"},
        "category_hint": {"type": "string"},
        "affected_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Entity ids the claim names; unknown ids move to unresolved_refs",
        },
        "unresolved_refs": {"type": "array", "items": {"type": "string"}},
        "proposed_change": {"type": "string"},
    },
    "required": ["key", "text", "note_ref", "note_source"],
}


def _claim_payload(claim: Any) -> dict[str, Any]:
    return ClaimResponse.from_domain(claim).model_dump(mode="json", exclude_none=True)


class SubmitClaimsTool(ToolBase):
    """Add or replace a taxonomy's claims by key."""

    name = "submit_claims"
    description = (
        "Submit atomic claims split from maintainer or reviewer notes on a taxonomy, so"
        " they can be triaged and judged. A claim whose key the taxonomy already has is"
        " replaced (its triage and verdict survive only if its text is unchanged)."
        " affected_ids that match no entity move to unresolved_refs. Claims change"
        " nothing in the taxonomy: propose changes with propose_changes."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "taxonomy_id": {"type": "string", "description": "The taxonomy the claims are about"},
            "claims": {"type": "array", "items": _CLAIM_SCHEMA, "minItems": 1, "maxItems": 1000},
        },
        "required": ["taxonomy_id", "claims"],
    }

    def __init__(self, service: ClaimService) -> None:
        self._service = service

    def run(self, args: dict[str, Any]) -> ToolOutcome:
        taxonomy_id = required_str(args, "taxonomy_id")
        raw = args.get("claims")
        if not isinstance(raw, list) or not raw:
            raise ToolArgumentError("'claims' must be a non-empty array")
        try:
            claims = [ClaimInput.model_validate(c).to_domain(taxonomy_id) for c in raw]
            stored = self._service.submit(taxonomy_id, claims)
        except ValidationError as exc:
            raise ToolArgumentError(str(exc)) from None
        except EntityNotFoundError as exc:
            return error_outcome(str(exc), "Not found")
        except ValueError as exc:
            raise ToolArgumentError(str(exc)) from None
        unresolved = sum(1 for c in stored if c.unresolved_refs)
        return ToolOutcome(
            content=dumps(
                {
                    "claims": [
                        {
                            "id": c.id,
                            "key": c.key,
                            "affected_ids": c.affected_ids,
                            "unresolved_refs": c.unresolved_refs,
                        }
                        for c in stored
                    ]
                }
            ),
            summary=f"Stored {len(stored)} claims ({unresolved} with unresolved references)",
        )


class ListClaimsTool(ToolBase):
    """A taxonomy's claims, with their triage and verdicts."""

    name = "list_claims"
    description = (
        "List a taxonomy's claims, oldest first, with each one's triage (a decision"
        " model's validity, category, severity and fix scope) and verdict (a person's"
        " judgment) when it has them. Filter by subject_id, note_ref, triaged,"
        " has_verdict or validity."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "taxonomy_id": {"type": "string"},
            "subject_id": {"type": "string"},
            "note_ref": {"type": "string"},
            "triaged": {"type": "boolean"},
            "has_verdict": {"type": "boolean"},
            "validity": {"type": "string", "enum": [v.value for v in Validity]},
            "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 50},
            "offset": {"type": "integer", "minimum": 0, "default": 0},
        },
        "required": ["taxonomy_id"],
    }

    def __init__(self, service: ClaimService) -> None:
        self._service = service

    def run(self, args: dict[str, Any]) -> ToolOutcome:
        validity = optional_str(args, "validity")
        for name in ("triaged", "has_verdict"):
            if args.get(name) is not None and not isinstance(args[name], bool):
                raise ToolArgumentError(f"'{name}' must be true or false")
        try:
            filters = ClaimFilter(
                taxonomy_id=required_str(args, "taxonomy_id"),
                subject_id=optional_str(args, "subject_id"),
                note_ref=optional_str(args, "note_ref"),
                triaged=args.get("triaged"),
                has_verdict=args.get("has_verdict"),
                validity=Validity(validity) if validity else None,
            )
        except ValueError as exc:
            raise ToolArgumentError(str(exc)) from None
        limit = int_arg(args, "limit", 50, 1, 500)
        offset = int_arg(args, "offset", 0, 0, 1_000_000)
        try:
            claims = self._service.list_claims(filters, limit, offset)
            total = self._service.count_claims(filters)
        except EntityNotFoundError as exc:
            return error_outcome(str(exc), "Taxonomy not found")
        return ToolOutcome(
            content=dumps({"claims": [_claim_payload(c) for c in claims], "total": total}),
            summary=f"{len(claims)} of {total} claims",
        )


def build_claim_tools(service: ClaimService) -> Sequence[ToolBase]:
    """The claim tools, for MCP clients."""
    return [SubmitClaimsTool(service), ListClaimsTool(service)]
