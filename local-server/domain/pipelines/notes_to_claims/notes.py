"""
The notes a notes-to-claims run splits, read from its scope.

A note's ref is stable, so a re-run replaces its claims rather than adding new
ones (a claim's key is "<note ref>#<n>"):

- a client's note keeps the ref the client gave it (DR sends its note ids,
  "node:<spec node id>" or "rel:<spec node id>");
- a maintainer's note on a proposal operation is "op:<operation id>";
- a reviewer's decision reason is "decision:<decision id>".
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Optional

from domain.pipelines.exceptions import PipelineInputError
from domain.versioning.claims import NoteSource
from domain.versioning.gold import ProposalDecision
from domain.versioning.proposals import ChangeProposal, OperationKind, ProposedOperation

OPERATION_NOTE_PREFIX = "op:"
DECISION_NOTE_PREFIX = "decision:"
# Operations on these kinds have a subject a note can be about
SUBJECT_KINDS = (
    OperationKind.SCHEME,
    OperationKind.CLASS,
    OperationKind.PROPERTY,
    OperationKind.ATTRIBUTE,
)


@dataclass(frozen=True)
class Note:
    """
    One note to split.

    Attributes:
        ref: Stable within the taxonomy; the claims' keys are "<ref>#<n>"
        text: The note
        source: A maintainer's or a reviewer's note
        subject: What the note is about, as an id or identifier (None: the taxonomy)
        proposed_definition: The definition proposed alongside the note, if any
    """

    ref: str
    text: str
    source: NoteSource
    subject: Optional[str] = None
    proposed_definition: Optional[str] = None


def client_notes(value: Any) -> list[Note]:
    """
    Notes a client sent: [{ref, subject, text, source?}], source "maintainer"
    (the default) or "reviewer".

    Raises:
        PipelineInputError: If a note is malformed or two share a ref
    """
    if not isinstance(value, list):
        raise PipelineInputError("scope notes must be a list of {ref, subject, text}")
    notes: list[Note] = []
    for n, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise PipelineInputError(f"note {n} must be an object with ref, subject and text")
        ref, text, subject = item.get("ref"), item.get("text"), item.get("subject")
        if not isinstance(ref, str) or not ref.strip():
            raise PipelineInputError(f"note {n} needs a ref")
        if not isinstance(text, str):
            raise PipelineInputError(f"note {ref} needs a text")
        if subject is not None and not isinstance(subject, str):
            raise PipelineInputError(f"note {ref}: subject must be an id or identifier")
        try:
            source = NoteSource(item.get("source") or NoteSource.MAINTAINER.value)
        except ValueError as exc:
            raise PipelineInputError(f"note {ref}: source must be maintainer or reviewer") from exc
        notes.append(Note(ref.strip(), text, source, (subject or "").strip() or None))
    refs = [note.ref for note in notes]
    repeated = sorted({ref for ref in refs if refs.count(ref) > 1})
    if repeated:
        raise PipelineInputError(f"Note refs repeat: {', '.join(repeated)}")
    return notes


def proposal_notes(proposal: ChangeProposal, decisions: Sequence[ProposalDecision]) -> list[Note]:
    """
    A proposal's notes: the maintainer notes on its operations, in seq order,
    then the reviewers' reasons on its decisions, oldest first.
    """
    notes = [
        Note(
            ref=f"{OPERATION_NOTE_PREFIX}{operation.id}",
            text=operation.notes or "",
            source=NoteSource.MAINTAINER,
            subject=_operation_subject(operation),
            proposed_definition=_definition(operation.kind, operation.fields),
        )
        for operation in proposal.operations
        if operation.notes
    ]
    return [*notes, *decision_notes(decisions)]


def decision_notes(decisions: Iterable[ProposalDecision]) -> list[Note]:
    """The reviewers' reasons on decisions, as notes about each decision's subject."""
    notes = []
    for decision in decisions:
        if not decision.reason:
            continue
        subject = None
        if decision.kind in SUBJECT_KINDS:
            subject = decision.result_entity_id or decision.proposed.get("target_id")
        notes.append(
            Note(
                ref=f"{DECISION_NOTE_PREFIX}{decision.id}",
                text=decision.reason,
                source=NoteSource.REVIEWER,
                subject=subject,
                proposed_definition=_definition(
                    decision.kind, decision.proposed.get("fields") or {}
                ),
            )
        )
    return notes


def _operation_subject(operation: ProposedOperation) -> Optional[str]:
    if operation.kind not in SUBJECT_KINDS:
        return None
    return operation.target_id or operation.result_entity_id


def _definition(kind: OperationKind, fields: dict[str, Any]) -> Optional[str]:
    """The description an operation proposes for a class or relationship type, if any."""
    if kind not in (OperationKind.CLASS, OperationKind.PROPERTY):
        return None
    description = fields.get("description")
    return description if isinstance(description, str) and description.strip() else None
