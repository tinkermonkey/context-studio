"""
In-memory fake IndividualRecognizer for domain unit tests.

Deterministic and infra-free: test doubles register an outcome per mention
label via ``add_match``; any unregistered label resolves to "no match" (None),
mirroring "no existing individual found". Every call is recorded on ``calls``
so tests can assert what the recognition stage offered the port (label,
context, class scoping).
"""

from __future__ import annotations

from typing import Sequence

from domain.extraction.ports import RecognitionMatch


class FakeIndividualRecognizer:
    def __init__(self) -> None:
        self._matches: dict[str, RecognitionMatch] = {}
        self.calls: list[dict] = []

    def add_match(self, label: str, match: RecognitionMatch) -> None:
        self._matches[label] = match

    def recognize(
        self,
        label: str,
        context: str,
        class_ids: Sequence[str],
        taxonomy_id: str | None = None,
        threshold: float | None = None,
    ) -> RecognitionMatch | None:
        self.calls.append(
            {
                "label": label,
                "context": context,
                "class_ids": list(class_ids),
                "taxonomy_id": taxonomy_id,
                "threshold": threshold,
            }
        )
        return self._matches.get(label)
