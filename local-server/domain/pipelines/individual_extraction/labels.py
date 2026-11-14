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
English rules (plural-only nouns such as "glasses" stay as they are). It is
only a merge key; it is never shown.

A diagram letter is not always a mere callout: "Screw (B)" and "Screw (D)" are
two parts of one diagram. `LabelKeys` keys the labels found together (one
run's triples, one class's existing individuals) and keeps the letter in the
key and the shown label when the same name is found with different letters.

Nor is a corporate suffix always a mere variant: "Wikimedia Enterprise" can be
a product and "Wikimedia Enterprise LLC" the company behind it. Given the
classes a run typed its labels with, `LabelKeys` keeps the suffix in the key
when the name with a suffix and the name without one share no class.
"""

from __future__ import annotations

import re
from collections.abc import Hashable, Iterable

# A trailing diagram callout: "adhesive disk (A)"
_DIAGRAM_LETTER = re.compile(r"\s*\(\s*([A-Za-z])\s*\)\s*$")
# A diagram letter kept in a key: "(b)"
_KEY_LETTER = re.compile(r"\([a-z]\)")
_APOSTROPHES = re.compile(r"['‘’ʼ`´]")
_CORPORATE_SUFFIXES = frozenset({"inc", "incorporated", "corp", "corporation", "llc", "ltd", "co"})
# A corporate suffix kept in a key, whichever suffix it was: "wikimedia enterprise (inc)"
_CORPORATE_MARK = "(inc)"
# Punctuation left dangling once a corporate suffix is dropped: "Moen, Inc.", "Smith & Co."
_DANGLING = ",&"
_TRAILING_PUNCTUATION = ".,;:"
# Nouns that are plural in form only: "Safety Glasses" is not "Safety Glass"
_PLURAL_ONLY = frozenset({"glasses", "pliers", "scissors", "shears", "goggles", "tongs"})


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
    while _ends_with_corporate_suffix(tokens):
        tokens.pop()
        while len(tokens) > 1 and not tokens[-1].strip(_DANGLING):
            tokens.pop()
        tokens[-1] = tokens[-1].rstrip(_DANGLING) or tokens[-1]
    if tokens:
        tokens[-1] = _singular(tokens[-1].rstrip(_TRAILING_PUNCTUATION) or tokens[-1])
    return " ".join(token.lower() for token in tokens)


class LabelKeys:
    """
    The merge keys of individual labels found together: one run's triples, or
    one class's existing individuals.

    A label's key is its `individual_key`, unless the labels name the same
    thing with different diagram letters ("Screw (B)", "screws (D)"): those are
    different parts, so the letter stays in their key ("screw (b)") and in the
    label shown, and the name without a letter ("Screw") is another individual.
    With one letter only, the letter is a callout and drops ("screws (D)" is
    "Screw").

    ``typed`` says which classes a run typed the labels with, as (label, class)
    pairs. When a name is typed both with a corporate suffix and without one,
    and the two forms share no class ("Wikimedia Enterprise" a product,
    "Wikimedia Enterprise LLC" a business), they are different things: the
    suffixed labels get a key of their own ("wikimedia enterprise (inc)"), so
    each keeps its own label. Forms that share a class ("Moen" and "Moen Inc.",
    both businesses), or of which only one is typed, are one individual.
    """

    def __init__(
        self,
        labels: Iterable[str | None],
        typed: Iterable[tuple[str | None, Hashable]] = (),
    ) -> None:
        letters: dict[str, set[str]] = {}
        for label in labels:
            letter = _diagram_letter(label)
            if letter is not None:
                letters.setdefault(individual_key(label), set()).add(letter)
        self._lettered = {key for key, found in letters.items() if len(found) > 1}
        # Key -> the classes of its labels without a corporate suffix, and with one
        plain: dict[str, set[Hashable]] = {}
        corporate: dict[str, set[Hashable]] = {}
        for label, class_id in typed:
            forms = corporate if has_corporate_suffix(label) else plain
            forms.setdefault(individual_key(label), set()).add(class_id)
        self._corporate = {
            key
            for key, classes in corporate.items()
            if key in plain and plain[key].isdisjoint(classes)
        }

    def key(self, label: str | None) -> str:
        """A label's merge key among these labels."""
        name = individual_key(label)
        key = name
        if name in self._corporate and has_corporate_suffix(label):
            key = f"{name} {_CORPORATE_MARK}"
        letter = _diagram_letter(label)
        return f"{key} ({letter.lower()})" if letter and name in self._lettered else key

    def preferred_label(self, labels: Iterable[str | None]) -> str:
        """
        The label to show for labels that share a key: `preferred_label`, with
        their diagram letter when the letter is part of the key.
        """
        labels = list(labels)
        shown = preferred_label(labels)
        for label in labels:
            letter = _diagram_letter(label)
            if letter and individual_key(label) in self._lettered:
                return f"{shown} ({letter})"
        return shown


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


def without_corporate_mark(key: str) -> str:
    """
    A key without the corporate suffix `LabelKeys` kept in it
    ("wikimedia enterprise (inc)" -> "wikimedia enterprise"); any other key as is.
    """
    return key.removesuffix(f" {_CORPORATE_MARK}")


def head_word(key: str) -> str | None:
    """A multi-word key's last word ("mounting bracket" -> "bracket"); None for one word."""
    words = key.split()
    return words[-1] if len(words) > 1 else None


def without_leading_word(key: str) -> str | None:
    """
    A key of three or more words without its first word, a leading brand or
    maker ("moen handheld shower" -> "handheld shower"); None for a shorter
    key, whose first word is part of the name ("hand shower" is not "shower").
    A diagram letter kept in the key is not a word.
    """
    words = key.split()
    named = words[:-1] if words and _KEY_LETTER.fullmatch(words[-1]) else words
    return " ".join(words[1:]) if len(named) >= 3 else None


def _diagram_letter(label: str | None) -> str | None:
    """A label's trailing diagram letter, uppercased ("disk (a)" -> "A"), else None."""
    text = " ".join(str(label or "").split())
    match = _DIAGRAM_LETTER.search(text)
    if match is None or not text[: match.start()].strip():
        return None
    return match.group(1).upper()


def _ends_with_corporate_suffix(tokens: list[str]) -> bool:
    """Whether a name's last word is a corporate suffix (a suffix alone is the name)."""
    return len(tokens) > 1 and tokens[-1].lower().strip(".,") in _CORPORATE_SUFFIXES


def has_corporate_suffix(label: str | None) -> bool:
    """Whether a label ends with a corporate suffix that `individual_key` drops."""
    return _ends_with_corporate_suffix(_APOSTROPHES.sub("", surface_label(label)).split())


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
    if lower in _PLURAL_ONLY:
        return word
    if lower.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if lower.endswith(("ches", "shes", "sses", "xes", "zes")):
        return word[:-2]
    if lower.endswith("s") and not lower.endswith(("ss", "us", "is")):
        return word[:-1]
    return word
