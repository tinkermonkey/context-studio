"""
Find the sections of a source text that extraction skips by default (#1575, #1570).

Product sheets and manuals carry text that yields junk when extracted: the
warranty, safety notices, legal small print, contact details, and copies of
the whole text in other languages. This module finds those sections with
simple, explainable heuristics, so the chunker can leave them out:

- **Sections.** The text splits into sections at page starts, at the source's
  headings, after blank lines, and at heading-like lines (a short line that
  is mostly upper case, or that names a boilerplate topic, such as "Limited
  Lifetime Warranty").
- **Language.** A section of at least ``MIN_WORDS`` words is in another
  language when the common short words (stopwords) of French, Spanish or
  German in it outnumber the English ones more than two to one. The
  workspace's language is English: no setting names another.
- **Boilerplate.** A section is boilerplate when at least ``MIN_HITS`` of its
  words are warranty, safety, legal or contact terms and they make up at least
  ``MIN_DENSITY`` of it; a heading that names the topic counts as
  ``HEADING_HITS`` terms. Its reason is the topic with the most terms.
- **Short sections** (too few words to judge, and no boilerplate) take the
  verdict of the section before them, else the one after, so a page number or
  a one-line label inside a skipped copy is skipped with it.

Neighbouring sections skipped for the same reason are reported as one.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from domain.extraction.chunking import Heading, page_of, selected_spans

# The run input (and extract option) that turns skipping off when false
SKIP_INPUT = "skip_boilerplate"
NOTHING_LEFT = (
    "Everything on the selected pages looks like boilerplate or another language;"
    f" set {SKIP_INPUT} to false to extract it"
)

OTHER_LANGUAGE = "other_language"
WARRANTY = "warranty"
SAFETY = "safety"
LEGAL = "legal"
CONTACT = "contact"

# Fewer words than this are too few to judge a section's language by
MIN_WORDS = 12
# Another language's stopwords must outnumber the English ones by this factor
LANGUAGE_RATIO = 2
MIN_OTHER_STOPWORDS = 3
# Boilerplate: at least this many terms, making up at least this share of the words
MIN_HITS = 3
MIN_DENSITY = 0.05
# A heading naming a boilerplate topic counts as this many of its terms
HEADING_HITS = 3
# A heading-like line is at most this long
MAX_HEADING_CHARS = 80
MAX_HEADING_WORDS = 10
PREVIEW_CHARS = 80

_WORD = re.compile(r"[^\W\d_]+")
_LINE = re.compile(r"[^\n]*\n?")
_SPACES = re.compile(r"\s+")

# Common short words found only in that language (words shared with English,
# such as "a", "on", "in" and "an", are left out of every list)
_ENGLISH = frozenset(
    "the and with this that for your you are from not will into before after then these"
    " those have has be is it of to or by at as if all any which when should must can do"
    " does only other its their they them such than use".split()
)
_OTHER = frozenset(
    # French
    "le la les des du et est pour avec dans une sur pas que qui vous votre vos ou au aux"
    " ce cette ces ne par sont être été il elle nous leur sans peut tout tous toute de un"
    # Spanish
    " el los las del y es para con en por su sus se al usted este esta estos como más lo"
    " sin puede todos debe"
    # German
    " der die das und ist mit für nicht ein eine zu von sie auf den dem im sich werden"
    " wird oder bei auch nur".split()
)

# Terms of each boilerplate topic, counted in a section's lower-cased text
_TERMS: dict[str, re.Pattern[str]] = {
    WARRANTY: re.compile(
        r"\bwarrant\w*|\bguarantee\w*|\bpurchaser\w*|\bproof of purchase\b|\bmerchantab\w*"
        r"|\bconsequential\b|\bincidental\b|\bdefects?\b|\bliab(?:le|ility)\b|\bimplied\b"
        r"|\bexclusions?\b|\bremed(?:y|ies)\b|\bjurisdictions?\b|\bworkmanship\b"
        r"|\bfitness for a particular purpose\b|\bdamages\b|\blegal rights\b"
    ),
    SAFETY: re.compile(
        r"\bwarnings?\b|\bcaution\b|\bdanger\w*|\bhazard\w*|\binjur(?:y|ies)\b|\bdeath\b"
        r"|\bpacemakers?\b|\bmedical devices?\b|\bdefibrillators?\b|\bproposition 65\b"
        r"|\bp65warnings\b|\bcancer\b|\bbirth defects\b|\breproductive harm\b|\bchoking\b"
        r"|\bout of (?:the )?reach of children\b|\belectric shock\b"
    ),
    LEGAL: re.compile(
        r"©|\bcopyright\w*|\ball rights reserved\b|\btrademarks?\b|\bregistered\b"
        r"|\bpatents?\b|\bterms and conditions\b|\bprivacy\b"
    ),
    CONTACT: re.compile(
        r"\bcustomer service\b|\bcontact\b|\bcall\b|\bvisit\b|\bhours\b|\bmonday\b|\bfriday\b"
        r"|\be-?mail\b|\b(?:www\.)?[\w-]+\.(?:com|ca|org|net)\b"
        r"|\b1[-. ]?8\d\d[-. ]?\w{3}[-. ]?\w{4}\b|\(\d{3}\)\s?\d{3}-\d{4}"
    ),
}

# Headings that name a boilerplate topic (in English, French or Spanish)
_HEADINGS: dict[str, re.Pattern[str]] = {
    WARRANTY: re.compile(r"\bwarrant(?:y|ies)\b|\bgarantie\b|\bgarant[íi]a\b"),
    SAFETY: re.compile(
        r"^\W*(?:warning|caution|danger|important safety|safety (?:information|instructions"
        r"|warnings?|notices?)|avertissement|advertencia|precauci[óo]n|mise en garde)\b"
    ),
    LEGAL: re.compile(r"\bcopyright\b|\blegal notices?\b|\btrademarks?\b|\ball rights reserved\b"),
    CONTACT: re.compile(
        r"\bcustomer service\b|\bcontact us\b|\bservice (?:à la )?client\w*"
        r"|\bservicio al cliente\b|^\W*questions\W*$"
    ),
}


@dataclass(frozen=True)
class SkippedSection:
    """
    A span of the text extraction skips.

    Attributes:
        start: Offset of its first character in the whole text
        end: Offset just past its last character
        reason: other_language, warranty, safety, legal or contact
    """

    start: int
    end: int
    reason: str

    def to_json(self, text: str, page_starts: Sequence[int] = ()) -> dict[str, object]:
        """The section for a run's output: offsets, pages, reason and how it starts."""
        preview = _SPACES.sub(" ", text[self.start : self.end]).strip()
        if len(preview) > PREVIEW_CHARS:
            preview = preview[: PREVIEW_CHARS - 1].rstrip() + "…"
        return {
            "start": self.start,
            "end": self.end,
            "page_first": page_of(self.start, page_starts) if page_starts else None,
            "page_last": page_of(self.end - 1, page_starts) if page_starts else None,
            "reason": self.reason,
            "preview": preview,
        }


def skipped_sections(
    text: str,
    *,
    page_starts: Sequence[int] | None = None,
    headings: Sequence[Heading] | None = None,
    pages: str | None = None,
) -> list[SkippedSection]:
    """
    The sections of ``text`` extraction skips: other-language copies and
    warranty, safety, legal and contact sections, in text order.

    Args:
        text: The whole source text
        page_starts: Offset at which each page starts
        headings: Headings in the text
        pages: Page selection (see chunking.parse_page_range); only those
            pages are looked at. Needs ``page_starts``.

    Returns:
        The skipped sections, neighbours skipped for the same reason merged

    Raises:
        ValueError: ``pages`` is malformed or given without ``page_starts``
    """
    breaks = set(page_starts or []) | {h.start for h in headings or []}
    titles = {h.start: h.title for h in headings or []}
    skipped: list[SkippedSection] = []
    for span_start, span_end in selected_spans(text, page_starts or [], pages):
        sections = _sections(text, span_start, span_end, breaks)
        verdicts = _verdicts(
            [_judge(text[start:end], titles.get(start)) for start, end in sections]
        )
        for (start, end), reason in zip(sections, verdicts):
            if reason is None:
                continue
            last = skipped[-1] if skipped else None
            if (
                last is not None
                and last.reason == reason
                and last.end >= span_start
                and not text[last.end : start].strip()
            ):
                skipped[-1] = SkippedSection(last.start, end, reason)
            else:
                skipped.append(SkippedSection(start, end, reason))
    return skipped


def _sections(text: str, start: int, end: int, breaks: set[int]) -> list[tuple[int, int]]:
    """
    Split text[start:end] into sections, trimmed of surrounding whitespace: a
    section starts at a page start or heading, after a blank line, or at a
    heading-like line.
    """
    sections: list[tuple[int, int]] = []
    section_start: int | None = None
    section_end = start
    after_blank = True
    position = start
    while position < end:
        match = _LINE.match(text, position, end)
        line_end = match.end() if match and match.end() > position else end
        line = text[position:line_end]
        stripped = line.strip()
        if not stripped:
            after_blank = True
        else:
            line_start = position + len(line) - len(line.lstrip())
            begins = (
                after_blank
                or any(position <= b <= line_start for b in breaks)
                or _heading_like(stripped)
            )
            if begins and section_start is not None:
                sections.append((section_start, section_end))
                section_start = None
            if section_start is None:
                section_start = line_start
            section_end = position + len(line.rstrip())
            after_blank = False
        position = line_end
    if section_start is not None:
        sections.append((section_start, section_end))
    return sections


def _heading_like(line: str) -> bool:
    """A short line that is mostly upper case or names a boilerplate topic."""
    if len(line) > MAX_HEADING_CHARS or line[-1] in ".,;":
        return False
    words = _WORD.findall(line)
    if not words or len(words) > MAX_HEADING_WORDS:
        return False
    letters = [c for c in line if c.isalpha()]
    upper = sum(1 for c in letters if c.isupper())
    if len(letters) >= 4 and upper >= 0.8 * len(letters):
        return True
    return _heading_topic(line) is not None


def _heading_topic(line: str) -> str | None:
    """The boilerplate topic a heading names, if any."""
    lowered = line.strip().lower()
    for topic, pattern in _HEADINGS.items():
        if pattern.search(lowered):
            return topic
    return None


def _first_line(section: str) -> str:
    return section.split("\n", 1)[0].strip()


def _judge(section: str, heading_title: str | None) -> str | None | bool:
    """
    A section's verdict: the reason it is skipped, None to keep it, or False
    when it is too short to judge.
    """
    lowered = section.lower()
    words = _WORD.findall(lowered)
    if len(words) >= MIN_WORDS:
        english = sum(1 for word in words if word in _ENGLISH)
        other = sum(1 for word in words if word in _OTHER)
        if other >= MIN_OTHER_STOPWORDS and other > LANGUAGE_RATIO * english:
            return OTHER_LANGUAGE

    hits = {topic: len(pattern.findall(lowered)) for topic, pattern in _TERMS.items()}
    first = _first_line(section)
    titles = [heading_title or "", first if _heading_like(first) else ""]
    for topic in {_heading_topic(title) for title in titles if title}:
        if topic is not None:
            hits[topic] += HEADING_HITS
    total = sum(hits.values())
    if total >= MIN_HITS and total >= MIN_DENSITY * max(len(words), 1):
        return max(hits, key=lambda topic: hits[topic])
    return None if len(words) >= MIN_WORDS else False


def _verdicts(judged: list[str | None | bool]) -> list[str | None]:
    """Each section's verdict, a short section taking its neighbour's."""
    verdicts: list[str | None | bool] = list(judged)
    previous: str | None | bool = False
    for i, verdict in enumerate(verdicts):
        if verdict is False:
            verdicts[i] = previous
        else:
            previous = verdict
    following: str | None | bool = None
    for i in range(len(verdicts) - 1, -1, -1):
        if verdicts[i] is False:
            verdicts[i] = following
        else:
            following = verdicts[i]
    return [v if isinstance(v, str) else None for v in verdicts]


def skipped_by_reason(sections: Sequence[SkippedSection]) -> dict[str, int]:
    """How many sections were skipped for each reason, most first."""
    counts: dict[str, int] = {}
    for section in sections:
        counts[section.reason] = counts.get(section.reason, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True))


def skip_summary(
    sections: Sequence[SkippedSection], text: str, page_starts: Sequence[int] = ()
) -> dict[str, object]:
    """The keys a run's output gains: skipped_sections and skipped_sections_by_reason."""
    return {
        "skipped_sections": [section.to_json(text, page_starts) for section in sections],
        "skipped_sections_by_reason": skipped_by_reason(sections),
    }


def skip_note(sections: Sequence[SkippedSection]) -> str:
    """A run warning saying what was skipped and how to extract it anyway."""
    counts = ", ".join(f"{reason} {n}" for reason, n in skipped_by_reason(sections).items())
    noun = "section" if len(sections) == 1 else "sections"
    return (
        f"Skipped {len(sections)} {noun} as boilerplate or another language ({counts});"
        f" set {SKIP_INPUT} to false to extract them"
    )
