"""
The splitter's prompt and reply, ported from DR's split-notes.ts.

DR's prompt is about its architecture specification and its spec ids; here it
is about a Context Studio taxonomy, and the affected ids are the identifiers the
note's context lists. The reply has DR's output shape:
{claims: [{text, category, affected_ids, proposed_change}]}.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Optional

from domain.pipelines.llm_json import extract_json


@dataclass(frozen=True)
class SplitClaim:
    """One claim as the splitter returned it (affected ids not yet resolved)."""

    text: str
    category: Optional[str] = None
    affected_ids: list[str] = field(default_factory=list)
    proposed_change: Optional[str] = None


def system_prompt(taxonomy_title: str, categories: Mapping[str, str]) -> str:
    """DR's split-notes system prompt, about a Context Studio taxonomy."""
    return "\n".join(
        [
            "You split a maintainer's or reviewer's note into atomic claims. A note is free"
            f" text written while defining or reviewing one class (or relationship type) of"
            f" the {taxonomy_title} taxonomy. It may bundle several unrelated concerns in one"
            " paragraph.",
            "For each distinct concern produce one claim:",
            "- text: the claim restated as one self-contained sentence that names the class,"
            " attribute, allowed value or relationship type it is about (a reader must not"
            " need the original note).",
            "- category: one of the ids below.",
            "- affected_ids: the identifiers the claim is about, as the context names them:"
            " class identifiers, attribute paths '<class identifier>.<attribute identifier>',"
            " and relationship type identifiers (the name before the colon in the context's"
            " relationship lines).",
            "- proposed_change: the concrete change the note implies, in one sentence, or"
            " 'none stated'.",
            "Do not merge concerns, do not add concerns the note does not make, do not judge"
            " whether the note is right.",
            "",
            "Categories:",
            *(f"- {key}: {meaning}" for key, meaning in categories.items()),
            "",
            "Reply with JSON only, in this shape:",
            '{"claims": [{"text": "...", "category": "...", "affected_ids": ["..."],'
            ' "proposed_change": "..."}]}',
        ]
    )


def user_prompt(about: str, text: str, context: str) -> str:
    """DR's split-notes user message: the note, then its subject's context."""
    return (
        f'Note about {about}:\n\n"""{text}"""\n\n' f"Context (for resolving names only):\n{context}"
    )


def parse_split(content: str, categories: Mapping[str, str]) -> list[SplitClaim]:
    """
    The claims in the splitter's reply. A category outside the vocabulary is
    dropped (left None). A proposed change is kept as written ("none stated"
    included); an empty one is None.

    Raises:
        ValueError: If the reply is not JSON in the expected shape (a claim
            without text included, so a note's claims are never renumbered)
    """
    try:
        data = extract_json(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"the reply is not JSON ({exc.msg})") from exc
    items = data.get("claims") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ValueError("the reply has no claims list")
    claims = []
    for n, item in enumerate(items, start=1):
        text = item.get("text") if isinstance(item, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"claim {n} has no text")
        category = item.get("category")
        affected = item.get("affected_ids") or []
        change = item.get("proposed_change")
        claims.append(
            SplitClaim(
                text=text.strip(),
                category=category if isinstance(category, str) and category in categories else None,
                affected_ids=(
                    [a for a in affected if isinstance(a, str) and a.strip()]
                    if isinstance(affected, list)
                    else []
                ),
                proposed_change=(
                    change.strip() if isinstance(change, str) and change.strip() else None
                ),
            )
        )
    return claims
