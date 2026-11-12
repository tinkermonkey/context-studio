"""
Label normalization for merging extracted individuals (#1575).

Extraction names the same thing several ways across a source: "Moen",
"Moen Inc." and "Moen Incorporated"; "Painter's Tape" and "painters tape";
"Screw" and "screws (D)", where "(D)" points at a diagram. `individual_key`
folds these into one key so they merge into one individual; `preferred_label`
picks the form to show for the merged individual.

The key drops a trailing diagram letter ("(A)"), apostrophes, case, extra
whitespace and trailing corporate suffixes (Inc., Incorporated, Corp.,
Corporation, LLC, Ltd., Co.), and singularizes the last word with simple
English rules. It is only a merge key; it is never shown.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

# A trailing diagram callout: "adhesive disk (A)"
_DIAGRAM_LETTER = re.compile(r"\s*\(\s*[A-Za-z]\s*\)\s*$")
_APOSTROPHES = re.compile(r"['‘’ʼ`´]")
_CORPORATE_SUFFIXES = frozenset({"inc", "incorporated", "corp", "corporation", "llc", "ltd", "co"})
# Punctuation left dangling once a corporate suffix is dropped: "Moen, Inc.", "Smith & Co."
_DANGLING = ",&"
_TRAILING_PUNCTUATION = ".,;:"


def surface_label(label: str | None) -> str:
    """A label as shown: whitespace collapsed, without a trailing diagram letter."""
    text = " ".join(str(label or "").split())
    return _DIAGRAM_LETTER.sub("", text).strip() or text


def individual_key(label: str | None) -> str:
    """
    The merge key of an individual's label: labels with the same key name the
    same individual.

    >>> individual_key("screws (D)") == individual_key("Screw")
    True
    >>> individual_key("Moen, Inc.") == individual_key("Moen")
    True
    """
    tokens = _APOSTROPHES.sub("", surface_label(label)).split()
    while len(tokens) > 1 and tokens[-1].lower().strip(".,") in _CORPORATE_SUFFIXES:
        tokens.pop()
        while len(tokens) > 1 and not tokens[-1].strip(_DANGLING):
            tokens.pop()
        tokens[-1] = tokens[-1].rstrip(_DANGLING) or tokens[-1]
    if tokens:
        tokens[-1] = _singular(tokens[-1].rstrip(_TRAILING_PUNCTUATION) or tokens[-1])
    return " ".join(token.lower() for token in tokens)


def preferred_label(labels: Iterable[str | None]) -> str:
    """
    The label to show for labels that share a key, as shown: one already in its
    key's form (singular, no corporate suffix) before one that isn't, then one
    starting with a capital, then the first found; e.g. "Moen" over
    "Moen Incorporated", "Screw" over "screws (D)", "Painter's Tape" over
    "painters tape".
    """
    shown = [s for s in (surface_label(label) for label in labels) if s]
    if not shown:
        return ""
    return min(
        enumerate(shown),
        key=lambda item: (
            _plain(item[1]) != individual_key(item[1]),
            item[1][:1].islower(),
            item[0],
        ),
    )[1]


def head_word(key: str) -> str | None:
    """A multi-word key's last word ("mounting bracket" -> "bracket"); None for one word."""
    words = key.split()
    return words[-1] if len(words) > 1 else None


def without_leading_word(key: str) -> str | None:
    """A multi-word key without its first word ("moen handheld shower" -> "handheld shower")."""
    words = key.split()
    return " ".join(words[1:]) if len(words) > 1 else None


def _plain(label: str) -> str:
    """A shown label with only apostrophes, case and trailing punctuation normalized."""
    return _APOSTROPHES.sub("", label).lower().rstrip(_TRAILING_PUNCTUATION)


def _singular(word: str) -> str:
    """
    A plural English word's singular, by simple suffix rules; any other word as
    is. Short words, acronyms ("AWS") and words with digits or symbols are left alone.
    """
    if len(word) <= 3 or word.isupper() or not word.replace("-", "").isalpha():
        return word
    lower = word.lower()
    if lower.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if lower.endswith(("ches", "shes", "sses", "xes", "zes")):
        return word[:-2]
    if lower.endswith("s") and not lower.endswith(("ss", "us", "is")):
        return word[:-1]
    return word
