"""
Anchored edits of a long text field (#1630).

A proposer changes part of a `description` or `vision` by edits anchored on
the existing text instead of resending the whole value:

- ``{"after": anchor, "insert": text}`` inserts `text` right after `anchor`
- ``{"replace": anchor, "with": text}`` replaces `anchor` with `text`
- ``{"delete": anchor}`` removes `anchor`

Edits apply in order, each to the text the previous one left. An anchor must
appear exactly once in the text it is applied to.
"""

from typing import Any

# The update fields a proposer may give as anchored edits.
TEXT_EDIT_FIELDS = frozenset({"description", "vision"})

ANCHOR_NOT_FOUND = "anchor_not_found"
ANCHOR_NOT_UNIQUE = "anchor_not_unique"

_SHAPES = (
    frozenset({"after", "insert"}),
    frozenset({"replace", "with"}),
    frozenset({"delete"}),
)


class TextEditError(ValueError):
    """
    An edit that can't be applied.

    Attributes:
        index: The edit's position in its list, from 0; -1 when the list itself is malformed
        code: ANCHOR_NOT_FOUND, ANCHOR_NOT_UNIQUE, or None for a malformed edit
    """

    def __init__(self, index: int, message: str, code: str | None = None) -> None:
        super().__init__(f"edit {index + 1}: {message}" if index >= 0 else message)
        self.index = index
        self.code = code


def parse_text_edits(value: Any) -> list[dict[str, str]]:
    """
    Check a field's ``{"edits": [...]}`` value and return its edits.

    Raises TextEditError (code None) for anything that isn't a non-empty list
    of edits of one of the three shapes, with text values and non-empty anchors.
    """
    if not isinstance(value, dict) or set(value) != {"edits"}:
        raise TextEditError(-1, 'give anchored edits as {"edits": [...]}')
    edits = value["edits"]
    if not isinstance(edits, list) or not edits:
        raise TextEditError(-1, "edits must be a non-empty list")
    parsed = []
    for index, edit in enumerate(edits):
        if not isinstance(edit, dict) or frozenset(edit) not in _SHAPES:
            raise TextEditError(
                index,
                'each edit is {"after", "insert"}, {"replace", "with"} or {"delete"}',
            )
        if not all(isinstance(text, str) for text in edit.values()):
            raise TextEditError(index, "an edit's anchor and text must be strings")
        anchor = edit.get("after", edit.get("replace", edit.get("delete")))
        if not anchor:
            raise TextEditError(index, "an edit's anchor must not be empty")
        parsed.append(dict(edit))
    return parsed


def apply_text_edits(text: str | None, edits: list[dict[str, str]]) -> str:
    """
    Apply `edits` in order to `text` (None reads as empty) and return the result.

    Raises TextEditError naming the first edit whose anchor is missing from, or
    appears more than once in, the text it is applied to.
    """
    result = text or ""
    for index, edit in enumerate(edits):
        anchor = edit.get("after", edit.get("replace", edit.get("delete")))
        assert anchor is not None  # parse_text_edits guarantees one
        count = _occurrences(result, anchor)
        if count == 0:
            raise TextEditError(index, f"anchor {_quoted(anchor)} is not in the text", ANCHOR_NOT_FOUND)
        if count > 1:
            raise TextEditError(
                index,
                f"anchor {_quoted(anchor)} appears {count} times: extend it until it is unique",
                ANCHOR_NOT_UNIQUE,
            )
        start = result.index(anchor)
        end = start + len(anchor)
        if "after" in edit:
            replacement = anchor + edit["insert"]
        elif "replace" in edit:
            replacement = edit["with"]
        else:
            replacement = ""
        result = result[:start] + replacement + result[end:]
    return result


def _occurrences(text: str, anchor: str) -> int:
    """How many places `anchor` starts in `text`, overlapping ones included."""
    count, start = 0, text.find(anchor)
    while start != -1:
        count += 1
        start = text.find(anchor, start + 1)
    return count


def _quoted(anchor: str, limit: int = 60) -> str:
    """The anchor in quotes, shortened for an error message."""
    shown = anchor if len(anchor) <= limit else anchor[: limit - 1] + "…"
    return repr(shown)
