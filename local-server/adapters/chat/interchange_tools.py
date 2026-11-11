"""
Round-trip tools for a client mirroring a taxonomy (DR today), MCP only: submit
a DR reflection plan as a change proposal, then fetch what was decided, in
the formats DR's scripts read.

- `submit_reflection_plan`: a `dr-reflection-plan/1` plan becomes a proposal,
  as `scripts/import_dr_reflection_plan.py` makes it
  (`adapters/interchange/dr_reflection_plan.py`).
- `get_spec_changes`: a proposal's applied spec changes as
  `cs-dr-spec-changes/1`, as `scripts/export_dr_spec_changes.py` writes them.
- `get_decisions`: a proposal's decisions, as
  `GET /api/proposals/{id}/decisions` serves them.

Decisions are a person's, in Context Studio's review queue; these tools only
propose and read. A result longer than MAX_PROPOSAL_CHARS pages its entries
(pass the offset its truncated note gives); entries are never cut, since the
client writes them into its source.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from adapters.chat.proposal_tools import (
    MAX_PROPOSAL_CHARS,
    _capped,
    _dry_run,
    _stored,
    _view,
    proposal_ref,
)
from adapters.chat.tools import (
    ToolArgumentError,
    ToolBase,
    dumps,
    error_outcome,
    int_arg,
    required_str,
)
from adapters.interchange.dr_decisions import decisions_for
from adapters.interchange.dr_reflection_plan import PLAN_FORMAT, PlanError, import_reflection_plan
from adapters.interchange.dr_relationships import DR_TAXONOMY_IDENTIFIER
from adapters.interchange.dr_spec_changes import SPEC_CHANGES_FORMAT, spec_changes_for
from domain.chat.value_objects import ToolOutcome
from domain.ontology.entities import Taxonomy
from domain.ontology.ports import OntologyRepository
from domain.pipelines.exceptions import PipelineInputError
from domain.pipelines.requested_via import REQUESTED_VIA, ensure_may_propose_to
from domain.versioning.exceptions import ChangeProposalNotFoundError, ProposalValidationError
from domain.versioning.proposal_service import ProposalService
from domain.versioning.proposals import ChangeProposal, ProposalSource

_logger = logging.getLogger(__name__)

# The lists of a cs-dr-spec-changes/1 document, in the order get_spec_changes pages them.
SPEC_CHANGE_LISTS = (
    "changes",
    "node_changes",
    "attribute_changes",
    "predicate_changes",
    "skipped",
    "records",
)
_REVIEW = (
    "A person decides each operation in Context Studio's review queue; these tools never decide."
)


class SubmitReflectionPlanTool(ToolBase):
    """Propose a DR reflection plan as one change proposal on the dr_spec taxonomy."""

    name = "submit_reflection_plan"
    description = (
        f"Submit a DR reflection plan (format {PLAN_FORMAT}, the JSON object DR's"
        " spec-enrich proposal-export.ts writes) as one change proposal on the dr_spec"
        " taxonomy, exactly as scripts/import_dr_reflection_plan.py proposes it. Each plan"
        " operation (kind property: create, update or delete of a relationship type, by DR"
        " relationship id) keeps its seq, the key get_decisions joins back on; the plan's"
        " predicate_retirements become predicate deletes after them, and its"
        " source_revision is recorded. The whole plan is checked first: if any operation"
        " doesn't resolve against the workspace (an unknown relationship id or spec node)"
        " or is invalid, nothing is stored and the result lists every problem (stored"
        " false), so fix the plan and submit it whole again. With dry_run true nothing is"
        " stored: you get each operation's scope, stale flag, blockers and auto_apply. A"
        " stored proposal waits as pending: " + _REVIEW + " Follow it with get_proposal;"
        " once decided, get_decisions and get_spec_changes return what to write into the"
        " spec."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "taxonomy_id": {
                "type": "string",
                "description": "The dr_spec taxonomy: its id or identifier (dr_spec)",
            },
            "plan": {
                "type": "object",
                "description": (
                    f"The {PLAN_FORMAT} plan: format, layer, title, rationale,"
                    " source_revision, operations, predicate_retirements"
                ),
            },
            "dry_run": {
                "type": "boolean",
                "description": "Validate and preview only; store and apply nothing",
            },
        },
        "required": ["taxonomy_id", "plan"],
    }

    def __init__(
        self, service: ProposalService, repo: OntologyRepository, source: ProposalSource
    ) -> None:
        self._service = service
        self._repo = repo
        self._source = source

    def run(self, args: dict[str, Any]) -> ToolOutcome:
        taxonomy_id = required_str(args, "taxonomy_id")
        plan = args.get("plan")
        if not isinstance(plan, dict):
            raise ToolArgumentError(f"'plan' must be a {PLAN_FORMAT} JSON object")
        dry_run = args.get("dry_run", False)
        if not isinstance(dry_run, bool):
            raise ToolArgumentError("'dry_run' must be true or false")
        taxonomy = self._repo.get_taxonomy(taxonomy_id)
        if taxonomy is None:
            # By identifier too, as a plan names it ("dr_spec")
            found = self._repo.get_by_identifier(taxonomy_id)
            taxonomy = found if isinstance(found, Taxonomy) else None
        if taxonomy is None:
            return error_outcome(
                f"No taxonomy found with id {taxonomy_id!r}.", "Taxonomy not found"
            )
        if taxonomy.identifier != DR_TAXONOMY_IDENTIFIER:
            return error_outcome(
                f"A {PLAN_FORMAT} plan changes DR's spec, the '{DR_TAXONOMY_IDENTIFIER}'"
                f" taxonomy; {taxonomy.title} ({taxonomy_id}) is not it.",
                "Not the DR spec taxonomy",
            )
        try:
            # Only a mirrored taxonomy's client, over MCP, proposes changes to it.
            ensure_may_propose_to(taxonomy, {REQUESTED_VIA: self._source.value})
        except PipelineInputError as exc:
            return error_outcome(str(exc), "Plan not proposed")

        try:
            proposal = import_reflection_plan(
                plan, self._service, self._repo, source=self._source, dry_run=dry_run
            )
        except PlanError as exc:
            return _not_stored(exc.problems)
        except ProposalValidationError as exc:
            return _not_stored(
                [
                    {"seq": e.seq, "code": e.code, "message": e.message}
                    if e.seq is not None
                    else {"code": e.code, "message": e.message}
                    for e in exc.errors
                ]
            )
        except Exception:  # noqa: BLE001 - the agent gets an answer, the log the detail
            _logger.exception("submit_reflection_plan could not propose a plan")
            return error_outcome(
                f"The plan could not be {'checked' if dry_run else 'proposed'} because of a"
                " server error.",
                "Plan not checked" if dry_run else "Plan not proposed",
            )
        try:
            view = _view(self._service, proposal, dry_run=dry_run)
        except Exception:  # noqa: BLE001 - stored already: never invite a duplicate
            _logger.exception("submit_reflection_plan could not describe proposal %s", proposal.id)
            if dry_run:
                return error_outcome(
                    "The dry run passed validation, but its details could not be read"
                    " because of a server error.",
                    "Dry run details unavailable",
                )
            return _stored(proposal, None)
        return _dry_run(view, self.name) if dry_run else _stored(proposal, view)


def _not_stored(problems: list[Any]) -> ToolOutcome:
    """A plan that can't be proposed: every problem, nothing stored."""
    payload: dict[str, Any] = {
        "stored": False,
        "id": None,
        "problems": problems,
        "next": (
            "Nothing was stored. Fix these problems in the plan, then call"
            " submit_reflection_plan again with the whole plan."
        ),
    }
    content, _ = _capped(payload, "problems", lambda _: "fix these and resend to see the rest")
    return ToolOutcome(content=content, summary=f"Plan not proposed: {len(problems)} problems")


class _ProposalReadTool(ToolBase):
    """Base for the tools that read one proposal's outcome in a client's format."""

    input_schema = {
        "type": "object",
        "properties": {
            "proposal_id": {"type": "string", "description": "Proposal id"},
            "offset": {
                "type": "integer",
                "minimum": 0,
                "description": "Entries to skip, for a result too large for one page",
            },
        },
        "required": ["proposal_id"],
    }

    def __init__(self, service: ProposalService) -> None:
        self._service = service

    def run(self, args: dict[str, Any]) -> ToolOutcome:
        proposal_id = required_str(args, "proposal_id")
        try:
            proposal = self._service.get(proposal_id)
        except ChangeProposalNotFoundError:
            return error_outcome(
                f"No proposal found with id {proposal_id!r}.", "Proposal not found"
            )
        try:
            header, lists = self._document(proposal)
        except ValueError as exc:  # reverted, or an applied change DR can't express
            return error_outcome(str(exc), f"{self.name}: not available")
        total = sum(len(entries) for entries in lists.values())
        offset = int_arg(args, "offset", 0, 0, total)
        return ToolOutcome(
            content=_page(header, lists, offset),
            summary=f"{self.name}: {total} entries for “{proposal.title}”",
            entities=(proposal_ref(proposal),),
        )

    def _document(self, proposal: ChangeProposal) -> tuple[dict[str, Any], dict[str, list[Any]]]:
        """The result's header and its lists of entries, in paging order."""
        raise NotImplementedError


class GetSpecChangesTool(_ProposalReadTool):
    """A decided proposal's applied DR spec changes, as cs-dr-spec-changes/1."""

    name = "get_spec_changes"
    description = (
        f"Get a proposal's applied changes to DR's spec as {SPEC_CHANGES_FORMAT}, the same"
        " JSON scripts/export_dr_spec_changes.py writes, for DR's cs-decisions-to-spec.ts to"
        " write into spec/schemas: changes (relationship types), node_changes (node types),"
        " attribute_changes, predicate_changes, skipped (operations not exported, and why)"
        " and records (DR change-record actions), with the source_revision the proposal was"
        " drafted against and landed once you marked it landed. Works for any proposal on"
        " the DR spec, reflection plan or not; only applied operations export, so read it"
        " once the proposal is decided (" + _REVIEW + "). A reverted proposal is refused."
        " A large document pages: each page has the header and a slice of the entries, the"
        f" lists in the order {', '.join(SPEC_CHANGE_LISTS)}; pass the offset its truncated"
        " note gives and append each list's entries to the previous page's. Land the"
        " changes in the spec, then mark_proposal_landed."
    )

    def __init__(self, service: ProposalService, repo: OntologyRepository) -> None:
        super().__init__(service)
        self._repo = repo

    def _document(self, proposal: ChangeProposal) -> tuple[dict[str, Any], dict[str, list[Any]]]:
        document = spec_changes_for(proposal, self._repo, self._service.decisions_of(proposal.id))
        lists = {key: document.pop(key) for key in SPEC_CHANGE_LISTS}
        return document, lists


class GetDecisionsTool(_ProposalReadTool):
    """The decisions on a proposal, joined to the client's plan by seq."""

    name = "get_decisions"
    description = (
        "Get the decisions on a proposal, as GET /api/proposals/{id}/decisions serves them"
        " (the JSON scripts/export_dr_decisions.py writes for DR's proposal-import.ts"
        " --decisions): decisions holds one {seq, op_id, status, fields?, resolution?,"
        " reason, result_entity_id, decided_at, decided_by} per operation, joined to the"
        " reflection plan by seq. status is pending, applied, rejected or failed; fields"
        " (the applied triple in DR's vocabulary) appears when a reviewer edited the"
        " operation before applying it, resolution when a delete moved or deleted the"
        " relationships using the type. " + _REVIEW + " Pending operations await that"
        " decision. A reverted proposal is refused. A large result pages: pass the offset"
        " its truncated note gives."
    )

    def _document(self, proposal: ChangeProposal) -> tuple[dict[str, Any], dict[str, list[Any]]]:
        decisions = decisions_for(proposal, self._service.decisions_of(proposal.id))
        return {"proposal_id": proposal.id}, {"decisions": decisions}


def _page(header: Mapping[str, Any], lists: Mapping[str, list[Any]], offset: int) -> str:
    """
    The header and the entries from offset on, within MAX_PROPOSAL_CHARS.

    Entries count across the lists in order. Whole entries are dropped from the
    end, never the first, so paging always advances; an entry is never cut.
    The result is the whole document, unchanged, when it fits from offset 0.
    """
    flat = [(key, entry) for key, entries in lists.items() for entry in entries]
    total = len(flat)
    count = total - offset

    def build(count: int) -> dict[str, Any]:
        shown = flat[offset : offset + count]
        payload: dict[str, Any] = {
            **header,
            **{key: [entry for k, entry in shown if k == key] for key in lists},
        }
        if offset or count < total:
            payload["offset"] = offset
            payload["total"] = total
        if offset + count < total:
            payload["truncated"] = (
                f"showing entries {offset + 1}-{offset + count} of {total}; pass offset"
                f" {offset + count} for the rest"
            )
        return payload

    content = dumps(build(count))
    while count > 1 and len(content) > MAX_PROPOSAL_CHARS:
        count = max(count * 3 // 4, 1)
        content = dumps(build(count))
    return content


def build_interchange_tools(
    service: ProposalService, repo: OntologyRepository, source: ProposalSource
) -> list[ToolBase]:
    """
    The round-trip tools, MCP only: submit a reflection plan, then read what was decided.

    Args:
        service: Makes and reads proposals
        repo: Resolves plans and spec changes against the DR spec taxonomy
        source: Recorded on the proposals a submitted plan makes
    """
    return [
        SubmitReflectionPlanTool(service, repo, source),
        GetDecisionsTool(service),
        GetSpecChangesTool(service, repo),
    ]
