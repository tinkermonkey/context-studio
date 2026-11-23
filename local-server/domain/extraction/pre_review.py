"""
Pre-review: a stage that reviews extracted individuals before a person does.

Designed in the DR changeset ``extraction-pre-review-stage`` and assessed by
documentation/extraction/experiments/2026-11-22-pre-review-stage.md. Phase 0
builds only what is free: the split witness, the precondition for asking the
split question. The stage's LLM call comes after Phase 0.
"""

from __future__ import annotations

import re

# A list inside a title: a comma, "and", "&" or "+" between words, or a slash
# joining two words ("Torx T20, T25", "Compression nut and ferrule",
# "Straight and Phillips blade screwdriver"). It marks where the split question
# applies; it never decides the answer: most DR titles it marks are one item
# ("Newcomers and Junior Contributors", "GNU/Linux").
_LIST_MARK = re.compile(r"\w,\s+\w|\s(?:and|&|\+)\s|[A-Za-z]/[A-Za-z]", re.IGNORECASE)


def split_witness(title: str) -> bool:
    """Whether a title looks like a list of several things, so the split question applies."""
    return bool(_LIST_MARK.search(title or ""))
