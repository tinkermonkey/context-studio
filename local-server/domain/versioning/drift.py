"""
Drift between a mirrored taxonomy and its source: report it, or propose it.

A mirrored taxonomy follows a client's source of truth (DR's spec). The source
still changes on its own, so a re-import compares the source, as it is now,
with the taxonomy and plans the operations that would make the taxonomy match
(a `DriftPlanner` adapter does that for one kind of source). A dry run reports
the drift and stores nothing; otherwise the plan is proposed as one change
proposal, for a person to review like any other: a re-import never writes to
the taxonomy directly.

A real run supersedes the open proposals of earlier re-imports of the same
source (`supersede_earlier_imports`): the new one repeats whatever still
applies. One that finds no drift records the source's revision on the
taxonomy, as the taxonomy then matches it, along with any label of that
revision the taxonomy's external references keep (`taxonomy_references`).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from domain.ontology.value_objects import ExternalReference, SourceRevision
from domain.versioning.bundle_import import bundle_source_detail, supersede_earlier_imports
from domain.versioning.proposals import ChangeProposal, OperationDraft, ProposalSource

if TYPE_CHECKING:
    from domain.ontology.services import OntologyService
    from domain.versioning.proposal_service import ProposalService


class DriftError(ValueError):
    """The source can't be read, or the taxonomy can't be compared with it."""


@dataclass(frozen=True)
class DriftEntry:
    """
    One entity that differs between the taxonomy and its source.

    Attributes:
        kind: taxonomy, scheme, class, property, attribute or predicate (a
            predicate is reported only: no operation removes its drift yet)
        source_id: The entity's id in the source (a DR id; an attribute's is
            "<node id>#<attribute name>")
        change: create (only in the source), update, move (it changed scheme in
            the source; it may differ otherwise too) or delete (only in the taxonomy)
        entity_id: The taxonomy's entity (None for a create)
        fields: Each differing field's value in the taxonomy and in the source:
            {name: {"taxonomy": ..., "source": ...}}. A create lists the values it
            would set (taxonomy None; unset ones left out); a delete lists nothing.
    """

    kind: str
    source_id: str
    change: str
    entity_id: str | None = None
    fields: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass
class DriftPlan:
    """
    The drift between a taxonomy and its source, and the operations that remove it.

    Attributes:
        taxonomy_id: The mirrored taxonomy
        source: Names the source in the proposal (its source_detail is
            "bundle:<source>", so a later re-import supersedes it)
        source_revision: The source's revision as read
        entries: What differs, by entity
        operations: Drafts that make the taxonomy match, in apply order
        taxonomy_references: The taxonomy's external references with the
            source's revision label on them brought up to date (DR's spec
            reference keeps the spec version), recorded with the revision when
            nothing differs; None when they already match. It isn't drift: no
            operation sets it.
    """

    taxonomy_id: str
    source: str
    source_revision: SourceRevision | None
    entries: list[DriftEntry] = field(default_factory=list)
    operations: list[OperationDraft] = field(default_factory=list)
    taxonomy_references: list[ExternalReference] | None = None


class DriftPlanner(Protocol):
    """Compares one kind of source with the taxonomy that mirrors it."""

    def plan(self, location: str) -> DriftPlan:
        """
        Read the source at `location` and plan the drift.

        Raises:
            DriftError: If the source can't be read or its taxonomy doesn't exist yet
        """
        ...


@dataclass
class DriftResult:
    """
    A re-import: the drift found and, unless nothing differs, its proposal.

    Attributes:
        plan: The drift and the planned operations
        proposal: The proposal (unstored on a dry run), or None when nothing differs
        dry_run: Whether nothing was stored
    """

    plan: DriftPlan
    proposal: ChangeProposal | None
    dry_run: bool


class DriftImportService:
    """Re-import a mirrored taxonomy's source as a dry run or a proposal."""

    def __init__(
        self,
        proposals: ProposalService,
        ontology_service: OntologyService,
        planner: DriftPlanner,
    ) -> None:
        self._proposals = proposals
        self._ontology = ontology_service
        self._planner = planner
        # A re-import plans against the taxonomy as it stands: one at a time.
        self._lock = threading.Lock()

    def reimport(self, location: str, dry_run: bool = True) -> DriftResult:
        """
        Compare the source at `location` with its taxonomy.

        Args:
            location: Where the source is (for DR, the spec directory)
            dry_run: Report the drift and validate its proposal only; store nothing

        Returns:
            The drift, and its proposal unless nothing differs

        Raises:
            DriftError: If the source can't be read or compared
            ProposalValidationError: If the planned operations don't validate;
                nothing is stored
        """
        with self._lock:
            plan = self._planner.plan(location)
            proposal = self._propose(plan, dry_run) if plan.operations else None
            if dry_run:
                return DriftResult(plan, proposal, True)
            supersede_earlier_imports(self._proposals, plan.taxonomy_id, plan.source, proposal)
            if proposal is None and not plan.entries:
                self._ontology.set_taxonomy_source_revision(
                    plan.taxonomy_id,
                    plan.source_revision,
                    external_references=plan.taxonomy_references,
                )
            return DriftResult(plan, proposal, False)

    def _propose(self, plan: DriftPlan, dry_run: bool) -> ChangeProposal:
        revision = plan.source_revision
        at = ""
        if revision is not None:
            label = revision.spec_version or ""
            commit = f" ({revision.commit[:8]})" if revision.commit else ""
            at = f" at {label}{commit}".rstrip() if label or commit else ""
        counts: dict[str, int] = {}
        for entry in plan.entries:
            counts[entry.change] = counts.get(entry.change, 0) + 1
        summary = ", ".join(f"{n} {change}" for change, n in sorted(counts.items()))
        return self._proposals.propose(
            plan.taxonomy_id,
            f"Re-import {plan.source}{at}",
            plan.operations,
            ProposalSource.BUNDLE,
            rationale=(
                f"Make the taxonomy match its source {plan.source}{at}: {summary}"
                f" ({len(plan.entries)} entities differ)."
            ),
            source_detail=bundle_source_detail(plan.source),
            dry_run=dry_run,
            source_revision=revision,
        )
