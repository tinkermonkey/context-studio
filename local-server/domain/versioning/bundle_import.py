"""
Import a bundle as a change proposal: one write path for bundles, agents and people.

The bundle is planned against the workspace (`domain.interchange.bundle`) and the
plan proposed with source=bundle, so an import is reviewable, dry-runnable and
revertible. The taxonomy's approval policy auto-applies what it allows; with
`apply`, every non-breaking operation is applied as well. Breaking operations
(deletes among them) always wait for review.

A bundle that matches the workspace plans nothing, and no proposal is made.
A bundle whose taxonomy does not exist yet has it created first, directly (a
proposal is about an existing taxonomy); reverting the proposal leaves that
empty taxonomy in place.

A new import supersedes the open bundle proposals on the same taxonomy: their
undecided operations are rejected, since the new plan repeats whatever still applies.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from domain.interchange.bundle import BundlePlan, plan_bundle
from domain.versioning.exceptions import ProposalValidationError
from domain.versioning.proposals import (
    ChangeProposal,
    ChangeScope,
    ProposalSource,
    ProposalStatus,
)

if TYPE_CHECKING:
    from domain.ontology.ports import OntologyRepository
    from domain.ontology.services import OntologyService
    from domain.versioning.proposal_service import ProposalService

SUPERSEDED_REASON = "superseded by bundle proposal {}"


@dataclass
class BundleImportResult:
    """
    What a bundle import planned and proposed.

    Attributes:
        plan: The planned operations and per-kind counts
        proposal: The proposal (unstored on a dry run), or None when the plan is
            empty or a dry run would first create the taxonomy
        dry_run: Whether nothing was stored
        taxonomy_created: Whether the import created the taxonomy (on a dry run:
            would create it)
    """

    plan: BundlePlan
    proposal: ChangeProposal | None
    dry_run: bool
    taxonomy_created: bool


class BundleImportService:
    """Plan a bundle and propose it as one change proposal."""

    def __init__(
        self,
        proposals: ProposalService,
        ontology_service: OntologyService,
        ontology_repo: OntologyRepository,
    ) -> None:
        self._proposals = proposals
        self._ontology = ontology_service
        self._repo = ontology_repo
        # Imports plan against the workspace as it stands: one at a time.
        self._lock = threading.Lock()

    def import_bundle(
        self,
        bundle: dict[str, Any],
        apply: bool = False,
        dry_run: bool = False,
        source_detail: str | None = None,
    ) -> BundleImportResult:
        """
        Plan a bundle and propose the plan.

        Args:
            bundle: The bundle dict
            apply: Also apply every non-breaking operation the policy did not
            dry_run: Plan and validate only; store and change nothing
            source_detail: Where the bundle came from (a file name), kept on the proposal

        Returns:
            The plan and the proposal (None when there is nothing to propose)

        Raises:
            BundleError: If the bundle is malformed or conflicts with the workspace
            ProposalValidationError: If the plan does not validate; nothing is stored
        """
        with self._lock:
            plan = plan_bundle(self._repo, bundle)
            if dry_run:
                proposal = None
                if plan.taxonomy_id is not None and plan.operations:
                    proposal = self._propose(plan, source_detail, dry_run=True)
                return BundleImportResult(plan, proposal, True, plan.taxonomy_id is None)

            created_taxonomy_id = None
            if plan.taxonomy_id is None:
                spec = plan.taxonomy
                created_taxonomy_id = self._ontology.create_taxonomy(
                    title=spec["title"],
                    description=spec.get("description"),
                    identifier=spec["identifier"],
                    vision=spec.get("vision"),
                ).id
                plan = plan_bundle(self._repo, bundle)
            taxonomy_created = created_taxonomy_id is not None
            if not plan.operations:
                return BundleImportResult(plan, None, False, taxonomy_created)
            try:
                proposal = self._propose(plan, source_detail)
            except ProposalValidationError:
                if created_taxonomy_id is not None:
                    self._ontology.delete_taxonomy(created_taxonomy_id)
                raise
            self._supersede(proposal)
            if apply:
                chosen = [o.id for o in proposal.pending if o.scope is not ChangeScope.BREAKING]
                if chosen:
                    proposal = self._proposals.apply(proposal.id, chosen)
            return BundleImportResult(plan, proposal, False, taxonomy_created)

    def _propose(
        self, plan: BundlePlan, source_detail: str | None, dry_run: bool = False
    ) -> ChangeProposal:
        counts = ", ".join(
            f"{kind}: {c.created} created, {c.updated} updated, {c.deleted} deleted"
            for kind, c in plan.counts.items()
            if c.created or c.updated or c.deleted
        )
        return self._proposals.propose(
            plan.taxonomy_id,  # type: ignore[arg-type]
            f"Import bundle {plan.source}: {plan.taxonomy['title']}",
            plan.operations,
            ProposalSource.BUNDLE,
            rationale=f"Make the workspace match the {plan.source!r} bundle ({counts}).",
            source_detail=source_detail,
            dry_run=dry_run,
        )

    def _supersede(self, proposal: ChangeProposal) -> None:
        """Reject what is undecided in the taxonomy's other open bundle proposals."""
        older = self._proposals.list_proposals(
            taxonomy_id=proposal.taxonomy_id,
            status=ProposalStatus.OPEN,
            source=ProposalSource.BUNDLE,
            limit=500,
        )
        for other in older:
            if other.id != proposal.id and other.pending:
                self._proposals.reject(
                    other.id,
                    [o.id for o in other.pending],
                    note=SUPERSEDED_REASON.format(proposal.id),
                )
