"""
Reviewer selections for applying a pipeline run.

A reviewer can apply exactly what they accepted instead of everything above a
confidence floor: an explicit set of accepted candidate ids (see
``candidate_ids``) and, for individual extraction, a per-mention recognition
decision (merge into an existing individual, or keep as a separate node).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

from domain.pipelines.exceptions import ApplySelectionError

MERGE = "merge"
SEPARATE = "separate"


@dataclass(frozen=True)
class RecognitionDecision:
    """
    A reviewer's decision for one extracted individual mention.

    Attributes:
        mention_label: The mention's surface text, matched case-insensitively
            (see ``candidate_ids.mention_key``) — the same key recognition
            preview reports hits under.
        decision: ``"merge"`` adopts ``individual_id`` (an individual that
            already exists, of any class); ``"separate"`` skips recognition so
            the mention is minted as a new individual.
        individual_id: Merge target; required for ``"merge"``, ignored otherwise.
    """

    mention_label: str
    decision: Literal["merge", "separate"]
    individual_id: str | None = None


def check_accepted_ids(accepted_candidate_ids: Iterable[str] | None, known_ids: set[str]) -> None:
    """
    Raise ApplySelectionError naming every accepted id the run does not contain.

    No-op when ``accepted_candidate_ids`` is None (threshold-only apply).
    """
    if accepted_candidate_ids is None:
        return
    unknown = sorted(set(accepted_candidate_ids) - known_ids)
    if unknown:
        raise ApplySelectionError(f"Unknown candidate ids for this run: {', '.join(unknown)}")
