"""
Tolerant JSON extraction from LLM replies.

Some models (e.g. Gemini via OpenRouter) wrap JSON in a Markdown code fence or
surround it with prose even when asked for bare JSON. ``extract_json`` recovers
the JSON payload in those cases and raises only when nothing parseable exists.
"""

from __future__ import annotations

import json
import re
from typing import Any

_FENCE_RE = re.compile(r"^```[A-Za-z0-9_-]*[ \t]*\n?(.*?)\s*```$", re.DOTALL)


def _strip_fence(text: str) -> str:
    """Remove a surrounding Markdown code fence (with optional language tag)."""
    match = _FENCE_RE.match(text)
    return match.group(1).strip() if match else text


def _matching_close(text: str, start: int) -> int:
    """Return the index of the bracket closing ``text[start]``, or -1 if none."""
    pairs = {"[": "]", "{": "}"}
    stack: list[str] = []
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch in pairs:
            stack.append(pairs[ch])
        elif ch in "]}":
            if not stack or stack.pop() != ch:
                return -1
            if not stack:
                return i
    return -1


def extract_json(text: str) -> Any:
    """
    Parse the JSON payload of an LLM reply.

    Tries, in order: the stripped text, the text with a surrounding Markdown code
    fence removed, then each balanced ``[...]`` / ``{...}`` span starting at an
    opening bracket (earliest first), respecting JSON string literals.

    Raises:
        json.JSONDecodeError: if no parseable JSON value is found.
    """
    candidate = _strip_fence((text or "").strip())
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        first_error = exc

    for start, ch in enumerate(candidate):
        if ch not in "[{":
            continue
        end = _matching_close(candidate, start)
        if end == -1:
            continue
        try:
            return json.loads(candidate[start : end + 1])
        except json.JSONDecodeError:
            continue
    raise first_error
