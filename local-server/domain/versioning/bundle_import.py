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

A new import supersedes the taxonomy's open proposals from earlier imports of
the same bundle source (their source_detail is "bundle:<source>"): their
undecided operations are rejected, since the new plan repeats whatever still
applies. An import whose plan is empty supersedes them too, as applying them
would undo what the bundle now says.

An import goes into one dataset of the taxonomy (#1487): the one named, else
the one the bundle names in its `dataset`, else the taxonomy's only one. It
plans only that dataset's individuals, and supersedes only earlier imports into
the same dataset (or ones made before datasets, which named none).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from domain.interchange.bundle import BundleError, BundlePlan, check_bundle_header, plan_bundle
from domain.versioning.gold import DECIDED_BY_BUNDLE
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

# Why a new import rejects what is undecided in an earlier import's open proposal:
# a newer proposal of the same bundle replaces it, or the bundle now matches.
SUPERSEDED_PREFIX = "superseded by bundle proposal "
SUPERSEDED_REASON = SUPERSEDED_PREFIX + "{}"
MATCHED_PREFIX = "superseded: the "
MATCHED_REASON = MATCHED_PREFIX + "{!r} bundle now matches the workspace"
_PAGE = 200


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
        file_name: str | None = None,
        dataset: str | None = None,
    ) -> BundleImportResult:
        """
        Plan a bundle and propose the plan.

        Args:
            bundle: The bundle dict
            apply: Also apply every non-breaking operation the policy did not
            dry_run: Plan and validate only; store and change nothing
            file_name: The file the bundle came from, named in the proposal's rationale
            dataset: The dataset (identifier or id) to import the data into; else
                the one the bundle names, else the taxonomy's only one

        Returns:
            The plan and the proposal (None when there is nothing to propose)

        Raises:
            BundleError: If the bundle is malformed or conflicts with the workspace
            ProposalValidationError: If the plan does not validate; nothing is stored
        """
        check_bundle_header(bundle)
        named = dataset or (bundle.get("dataset") or {}).get("identifier")
        with self._lock:
            dataset_id = self._dataset_id(bundle, named, create=not dry_run)
            plan = plan_bundle(self._repo, bundle, dataset_id)
            if dry_run:
                proposal = None
                if plan.taxonomy_id is not None and plan.operations:
                    proposal = self._propose(plan, file_name, dataset_id, dry_run=True)
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
            try:
                if created_taxonomy_id is not None:
                    dataset_id = self._dataset_id(bundle, named, create=True)
                    plan = plan_bundle(self._repo, bundle, dataset_id)
                proposal = self._propose(plan, file_name, dataset_id) if plan.operations else None
            except Exception:
                # Whatever went wrong, a first import leaves no empty taxonomy behind.
                if created_taxonomy_id is not None:
                    self._ontology.delete_taxonomy(created_taxonomy_id)
                raise
            # Even an empty plan supersedes: older proposals would undo the bundle.
            supersede_earlier_imports(
                self._proposals,
                plan.taxonomy_id,  # type: ignore[arg-type]
                plan.source,
                proposal,
                dataset_id=(proposal.dataset_id if proposal is not None else None) or dataset_id,
            )
            if proposal is not None and apply:
                chosen = [o.id for o in proposal.pending if o.scope is not ChangeScope.BREAKING]
                if chosen:
                    proposal = self._proposals.apply(
                        proposal.id, chosen, decided_by=DECIDED_BY_BUNDLE
                    )
            return BundleImportResult(plan, proposal, False, created_taxonomy_id is not None)

    def _dataset_id(self, bundle: dict[str, Any], named: str | None, create: bool) -> str | None:
        """
        The id of the dataset the import goes into: the one named (identifier or
        id) in the bundle's taxonomy, else its only one; None when the taxonomy
        doesn't exist yet, or names none and has none or several. With `create`,
        a dataset named for a taxonomy that has none yet is made.

        Raises:
            BundleError: If the taxonomy has datasets but not the one named
        """
        taxonomy = self._repo.get_by_identifier(str(bundle["taxonomy"].get("identifier")))
        if taxonomy is None:
            return None
        datasets = self._ontology.list_datasets(taxonomy.id)
        if named is None:
            return datasets[0].id if len(datasets) == 1 else None
        found = next((d for d in datasets if named in (d.id, d.identifier)), None)
        if found is not None:
            return found.id
        if not datasets:
            if not create:
                return None  # a dry run: the real import makes it
            title = (bundle.get("dataset") or {}).get("title") or named
            return self._ontology.create_dataset(taxonomy.id, named, title).id
        listed = ", ".join(d.identifier for d in datasets) or "none"
        raise BundleError(f"No dataset {named!r} in taxonomy {taxonomy.title!r} (it has: {listed})")

    def _propose(
        self,
        plan: BundlePlan,
        file_name: str | None,
        dataset_id: str | None = None,
        dry_run: bool = False,
    ) -> ChangeProposal:
        counts = ", ".join(
            f"{kind}: {c.created} created, {c.updated} updated, {c.deleted} deleted"
            for kind, c in plan.counts.items()
            if c.created or c.updated or c.deleted
        )
        origin = f" from {file_name}" if file_name else ""
        return self._proposals.propose(
            plan.taxonomy_id,  # type: ignore[arg-type]
            f"Import bundle {plan.source}: {plan.taxonomy['title']}",
            plan.operations,
            ProposalSource.BUNDLE,
            rationale=f"Make the workspace match the {plan.source!r} bundle{origin} ({counts}).",
            source_detail=bundle_source_detail(plan.source),
            dry_run=dry_run,
            dataset_id=dataset_id,
        )


def supersede_earlier_imports(
    proposals: ProposalService,
    taxonomy_id: str,
    source: str,
    proposal: ChangeProposal | None,
    dataset_id: str | None = None,
) -> None:
    """
    Reject what is undecided in the taxonomy's open proposals from earlier
    imports of the same source (other bundle-source proposals are left): the
    new proposal repeats whatever still applies, and with no new proposal the
    source matches the workspace, so applying them would undo it. An import
    into another dataset is left too (one made before datasets named none).
    """
    detail = bundle_source_detail(source)
    offset = 0
    older: list[ChangeProposal] = []
    while True:
        page = proposals.list_proposals(
            taxonomy_id=taxonomy_id,
            status=ProposalStatus.OPEN,
            source=ProposalSource.BUNDLE,
            limit=_PAGE,
            offset=offset,
        )
        older += page
        if len(page) < _PAGE:
            break
        offset += _PAGE
    reason = (
        SUPERSEDED_REASON.format(proposal.id)
        if proposal is not None
        else MATCHED_REASON.format(source)
    )
    for other in older:
        if other.source_detail != detail or not other.pending:
            continue
        # Another dataset's import is left alone (one made before datasets named none).
        if other.dataset_id is not None and other.dataset_id != dataset_id:
            continue
        if proposal is not None and other.id == proposal.id:
            continue
        # Nobody judged these: no decision is recorded.
        proposals.reject(other.id, [o.id for o in other.pending], note=reason, decided_by=None)


def bundle_source_detail(source: str) -> str:
    """The source_detail an import of a bundle from this source records on its proposal."""
    return f"bundle:{source}"
