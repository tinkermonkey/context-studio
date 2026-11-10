"""
The notes a notes-to-claims run splits, read from its scope.

A note's ref is stable, so a re-run replaces its claims rather than adding new
ones (a claim's key is "<note ref>#<n>"):

- a client's note keeps the ref the client gave it (DR sends its note ids,
  "node:<spec node id>" or "rel:<spec node id>"); its subject is a Context
  Studio id or identifier (a client maps its own ids, e.g. DR's spec node id
  "api.callback" to the class identifier "api_callback");
- a maintainer's note on a proposal operation is "op:<operation id>";
- a reviewer's decision reason is "decision:<decision id>".
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Optional

from domain.pipelines.exceptions import PipelineInputError
from domain.versioning.claims import NoteSource
from domain.versioning.gold import ProposalDecision
from domain.versioning.proposals import (
    ChangeProposal,
    OperationKind,
    OperationType,
)

OPERATION_NOTE_PREFIX = "op:"
DECISION_NOTE_PREFIX = "decision:"
# Operations on these kinds have a subject a note can be about
SUBJECT_KINDS = (
    OperationKind.SCHEME,
    OperationKind.CLASS,
    OperationKind.PROPERTY,
    OperationKind.ATTRIBUTE,
)
# A create has no target yet: its note is about the owner its fields name, the
# first of these that names an existing entity (not a "$<ref>" of another create)
OWNER_FIELDS = {
    OperationKind.ATTRIBUTE: ("class_id",),
    OperationKind.CLASS: ("parent_class_id", "concept_scheme_id"),
    OperationKind.PROPERTY: ("domain_class_id",),
}
# The proposed fields shown with a note, as DR's typeContext shows a proposal's
PROPOSED_FIELDS = ("description", "distinguish_from", "standard_reference")


@dataclass(frozen=True)
class Note:
    """
    One note to split.

    Attributes:
        ref: Stable within the taxonomy; the claims' keys are "<ref>#<n>"
        text: The note
        source: A maintainer's or a reviewer's note
        subject: What the note is about, as a Context Studio id or identifier
            (None: the taxonomy)
        proposed: The definition fields proposed alongside the note (description,
            distinguish_from, standard_reference), if any
        proposed_new: What a create proposed alongside the note makes, e.g.
            "class api_webhook" (its subject is then the new entity's owner)
    """

    ref: str
    text: str
    source: NoteSource
    subject: Optional[str] = None
    proposed: Mapping[str, Any] = field(default_factory=dict)
    proposed_new: Optional[str] = None


def client_notes(value: Any) -> list[Note]:
    """
    Notes a client sent: [{ref, subject, text, source?}]. subject is a Context
    Studio id or identifier (of a class, relationship type, attribute as
    "<class identifier>.<attribute identifier>", scheme or the taxonomy);
    source is "maintainer" (the default) or "reviewer".

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
        _note(
            f"{OPERATION_NOTE_PREFIX}{operation.id}",
            operation.notes or "",
            NoteSource.MAINTAINER,
            operation.kind,
            operation.op,
            operation.target_id or operation.result_entity_id,
            operation.fields,
        )
        for operation in proposal.operations
        if operation.notes
    ]
    return [*notes, *decision_notes(decisions)]


def decision_notes(decisions: Iterable[ProposalDecision]) -> list[Note]:
    """The reviewers' reasons on decisions, as notes about each decision's subject."""
    return [
        _note(
            f"{DECISION_NOTE_PREFIX}{decision.id}",
            decision.reason,
            NoteSource.REVIEWER,
            decision.kind,
            decision.op,
            decision.result_entity_id or decision.proposed.get("target_id"),
            decision.proposed.get("fields") or {},
        )
        for decision in decisions
        if decision.reason
    ]


def _note(
    ref: str,
    text: str,
    source: NoteSource,
    kind: OperationKind,
    op: OperationType,
    target: Optional[str],
    fields: Mapping[str, Any],
) -> Note:
    """A note on an operation: about its target, else the owner a create names."""
    subject = None
    if kind in SUBJECT_KINDS:
        subject = target or _owner(kind, fields)
    proposed_new = None
    if op is OperationType.CREATE and not target:
        name = fields.get("identifier") or fields.get("title")
        proposed_new = f"{kind.value} {name}" if name else kind.value
    proposed = {}
    if kind in (OperationKind.CLASS, OperationKind.PROPERTY):
        proposed = {name: fields[name] for name in PROPOSED_FIELDS if fields.get(name)}
    return Note(ref, text, source, subject, proposed, proposed_new)


def _owner(kind: OperationKind, fields: Mapping[str, Any]) -> Optional[str]:
    """The existing entity a create's fields put it under, if any."""
    for name in OWNER_FIELDS.get(kind, ()):
        value = fields.get(name)
        if isinstance(value, str) and value and not value.startswith("$"):
            return value
    return None
