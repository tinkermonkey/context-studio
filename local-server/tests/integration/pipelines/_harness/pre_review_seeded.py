"""
Seeded errors for the pre-review stage: build them from gold, score a stage on them.

Phase 1 of documentation/extraction/experiments/2026-11-22-pre-review-stage.md.
A document's gold extraction is handed to the stage as if it were a perfect
extraction (each gold title, its gold class, its first evidence quote), with
errors planted in it:

- **merge**: two named gold individuals of one class whose evidence sits in
  one paragraph, and whose titles do not already read as lists, joined into
  one item ("A and B" or "A, B") with A's quote;
- **retype, realistic**: a gold individual given a class it is easily taken
  for: one single_call gave it in a recording, or one whose definition says to
  use the gold class instead (or that the gold class's definition says to use);
- **retype, same layer**: a gold individual given another class of its layer,
  at random.

Every other gold individual is a **control**, untouched; a control whose title
the split witness marks is reported apart (a split trap). Building and scoring
cost nothing; only running a real stage does.

What the stage answers is scored per item:

- a **fix** puts a seeded item right: a merge split into parts that name both
  gold individuals, a retype moved to the gold class or an acceptable one;
- a **harm** makes a correct item wrong: a control split, or retyped to a class
  gold does not accept;
- a **neutral** change moves a control between acceptable classes;
- a seeded item the stage left as it was is **missed**; one it changed without
  putting it right is **changed wrongly**.
"""

from __future__ import annotations

import math
import random
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from domain.extraction.entities import PreReviewAnswer, PreReviewQuestion, PreReviewVerdict
from domain.extraction.pre_review import split_witness
from tests.integration.pipelines._harness.benchmark import (
    STATEMENT_LAYER,
    Gold,
    GoldIndividual,
    class_reference,
    layer_of,
    name_key,
)

MERGE = "merge"
RETYPE_REALISTIC = "retype_realistic"
RETYPE_SAME_LAYER = "retype_same_layer"
CONTROL = "control"
SPLIT_TRAP = "split_trap"
STRATA = (MERGE, RETYPE_REALISTIC, RETYPE_SAME_LAYER, CONTROL, SPLIT_TRAP)

# Per document and take, as the decision rule sets them
MERGES = 8
REALISTIC_RETYPES = 6
SAME_LAYER_RETYPES = 6

_USE_INSTEAD = re.compile(r"\bUse (\w+) instead\b")
_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")


@dataclass(frozen=True)
class ReviewItem:
    """One extracted individual as the stage is given it."""

    index: int
    title: str
    class_ref: str
    quote: str
    witness: bool


@dataclass(frozen=True)
class Seed:
    """What an item is: which stratum, which gold individuals it stands for, what was planted."""

    stratum: str
    gold_keys: tuple[str, ...]
    planted_class: str | None = None


@dataclass(frozen=True)
class SeededDocument:
    """A document's gold as a stage's input, with errors planted: items and seeds by index."""

    document_id: str
    take: int
    text: str
    items: tuple[ReviewItem, ...]
    seeds: Mapping[int, Seed]

    def stratum_counts(self) -> dict[str, int]:
        counts = dict.fromkeys(STRATA, 0)
        for seed in self.seeds.values():
            counts[seed.stratum] += 1
        return counts


# A stage: given a seeded document, its verdicts by item index (an item with none was kept)
Stage = Callable[[SeededDocument], Mapping[int, PreReviewVerdict]]


# ---------------------------------------------------------------- the classes


@dataclass(frozen=True)
class ClassCatalog:
    """What seeding needs of the schema: every class reference, its layer, and its confusables."""

    refs: tuple[str, ...]
    # Class reference -> the classes its definition says to use instead, or that say to use it
    confusable: Mapping[str, frozenset[str]]

    @classmethod
    def from_bundle(cls, bundle: Mapping[str, Any]) -> "ClassCatalog":
        """Read the classes and their "Use X instead" sentences from a schema bundle."""
        classes = list(bundle["classes"])
        ref_of = {c["identifier"]: class_reference(c) for c in classes}
        by_title: dict[str, list[str]] = {}
        for c in classes:
            by_title.setdefault(str(c.get("title") or ""), []).append(ref_of[c["identifier"]])
        pairs: dict[str, set[str]] = {ref: set() for ref in ref_of.values()}
        for c in classes:
            ref = ref_of[c["identifier"]]
            for title in _USE_INSTEAD.findall(str(c.get("description") or "")):
                named = by_title.get(title, [])
                # A title several layers share is read in this class's layer when it can be
                same_layer = [r for r in named if layer_of(r) == layer_of(ref)]
                for other in same_layer or named:
                    if other != ref:
                        pairs[ref].add(other)
                        pairs[other].add(ref)
        return cls(
            refs=tuple(sorted(ref_of.values())),
            confusable={ref: frozenset(others) for ref, others in pairs.items()},
        )

    def same_layer(self, ref: str) -> list[str]:
        return [r for r in self.refs if layer_of(r) == layer_of(ref) and r != ref]


def recorded_mistypes(gold: Gold, recorded: Iterable[tuple[str, str]]) -> dict[str, set[str]]:
    """
    Gold key -> the classes a recorded run gave that individual which gold does
    not accept, from the run's (title, class reference) pairs matched by name.
    """
    by_name: dict[str, GoldIndividual] = {}
    for individual in gold.individuals:
        for name in individual.names:
            by_name.setdefault(name, individual)
    found: dict[str, set[str]] = {}
    for title, class_ref in recorded:
        individual = by_name.get(name_key(title))
        if individual is not None and not individual.accepts(class_ref):
            found.setdefault(individual.key, set()).add(class_ref)
    return found


# ---------------------------------------------------------------- building


def build_seeded(
    gold: Gold,
    catalog: ClassCatalog,
    take: int,
    mistypes: Mapping[str, Iterable[str]] | None = None,
    merges: int = MERGES,
    realistic: int = REALISTIC_RETYPES,
    same_layer: int = SAME_LAYER_RETYPES,
) -> SeededDocument:
    """
    A document's gold as the stage's input, with errors planted. The same take
    gives the same seeds; another take, others. Fewer seeds than asked are
    planted when gold has too few candidates (stratum_counts says how many).
    """
    rnd = random.Random(f"{gold.document_id}:{take}")
    usable = [g for g in gold.individuals if g.evidence]
    used: set[str] = set()

    merged = _merge_pairs(gold, usable, rnd, merges)
    used.update(key for pair in merged for key in (pair[0].key, pair[1].key))

    retyped: list[tuple[GoldIndividual, str, str]] = []
    order = [g for g in usable if g.key not in used]
    rnd.shuffle(order)
    for individual in order:
        if sum(1 for _, _, s in retyped if s == RETYPE_REALISTIC) >= realistic:
            break
        options = sorted(
            ref
            for ref in set(catalog.confusable.get(individual.class_ref, ())) | set(
                (mistypes or {}).get(individual.key, ())
            )
            if not individual.accepts(ref)
        )
        if options:
            retyped.append((individual, rnd.choice(options), RETYPE_REALISTIC))
            used.add(individual.key)
    for individual in order:
        if sum(1 for _, _, s in retyped if s == RETYPE_SAME_LAYER) >= same_layer:
            break
        if individual.key in used:
            continue
        options = [r for r in catalog.same_layer(individual.class_ref) if not individual.accepts(r)]
        if options:
            retyped.append((individual, rnd.choice(options), RETYPE_SAME_LAYER))
            used.add(individual.key)

    entries: list[tuple[int, str, str, str, Seed]] = []
    for number, (first, second) in enumerate(merged):
        joiner = " and " if number % 2 == 0 else ", "
        entries.append(
            (
                first.evidence[0].start,
                f"{first.title}{joiner}{second.title}",
                first.class_ref,
                first.evidence[0].quote,
                Seed(MERGE, (first.key, second.key)),
            )
        )
    for individual, planted, stratum in retyped:
        entries.append(
            (
                individual.evidence[0].start,
                individual.title,
                planted,
                individual.evidence[0].quote,
                Seed(stratum, (individual.key,), planted),
            )
        )
    for individual in usable:
        if individual.key in used:
            continue
        stratum = SPLIT_TRAP if split_witness(individual.title) else CONTROL
        entries.append(
            (
                individual.evidence[0].start,
                individual.title,
                individual.class_ref,
                individual.evidence[0].quote,
                Seed(stratum, (individual.key,)),
            )
        )
    # In the order the document says them, as an extraction lists them
    entries.sort(key=lambda entry: (entry[0], entry[1]))
    items = tuple(
        ReviewItem(index, title, class_ref, quote, split_witness(title))
        for index, (_, title, class_ref, quote, _) in enumerate(entries)
    )
    seeds = {index: entry[4] for index, entry in enumerate(entries)}
    return SeededDocument(gold.document_id, take, gold.source_text, items, seeds)


def _merge_pairs(
    gold: Gold, usable: Sequence[GoldIndividual], rnd: random.Random, wanted: int
) -> list[tuple[GoldIndividual, GoldIndividual]]:
    """Disjoint pairs of named individuals of one class whose first evidence is in one paragraph."""
    paragraph = _paragraph_index(gold.source_text)
    # A title that already reads as a list would make a merge whose parts can't be told apart
    named = [
        g for g in usable if layer_of(g.class_ref) != STATEMENT_LAYER and not split_witness(g.title)
    ]
    candidates = [
        (a, b)
        for i, a in enumerate(named)
        for b in named[i + 1 :]
        if a.class_ref == b.class_ref
        and paragraph(a.evidence[0].start) == paragraph(b.evidence[0].start)
        and name_key(a.title) != name_key(b.title)
    ]
    rnd.shuffle(candidates)
    pairs: list[tuple[GoldIndividual, GoldIndividual]] = []
    taken: set[str] = set()
    for a, b in candidates:
        if len(pairs) >= wanted:
            break
        if a.key in taken or b.key in taken:
            continue
        first, second = sorted((a, b), key=lambda g: g.evidence[0].start)
        pairs.append((first, second))
        taken.update((a.key, b.key))
    return pairs


def _paragraph_index(text: str) -> Callable[[int], int]:
    breaks = [match.end() for match in _PARAGRAPH_BREAK.finditer(text)]

    def index(offset: int) -> int:
        return sum(1 for b in breaks if b <= offset)

    return index


# ---------------------------------------------------------------- scoring


@dataclass
class StratumScore:
    """What a stage did to one stratum's items."""

    items: int = 0
    fixed: int = 0
    harmed: int = 0
    neutral: int = 0
    missed: int = 0
    changed_wrongly: int = 0
    unsure: int = 0
    # Harms by the question that made them (split or retype)
    harmed_by: dict[str, int] = field(default_factory=lambda: {"split": 0, "retype": 0})

    def add(self, other: "StratumScore") -> None:
        for name in ("items", "fixed", "harmed", "neutral", "missed", "changed_wrongly", "unsure"):
            setattr(self, name, getattr(self, name) + getattr(other, name))
        for question, count in other.harmed_by.items():
            self.harmed_by[question] = self.harmed_by.get(question, 0) + count


@dataclass
class SeededScore:
    """A stage's score on one seeded document (or several, summed)."""

    strata: dict[str, StratumScore] = field(
        default_factory=lambda: {stratum: StratumScore() for stratum in STRATA}
    )

    def add(self, other: "SeededScore") -> None:
        for stratum, score in other.strata.items():
            self.strata[stratum].add(score)

    def recovery(self, *strata: str) -> float:
        items = sum(self.strata[s].items for s in strata)
        return self.strata_sum("fixed", *strata) / items if items else 0.0

    def strata_sum(self, name: str, *strata: str) -> int:
        return sum(getattr(self.strata[s], name) for s in strata)

    def control_harms(self, question: str | None = None) -> tuple[int, int]:
        """Harms on the untouched items (controls and split traps), and how many there were."""
        controls = (CONTROL, SPLIT_TRAP)
        harmed = (
            self.strata_sum("harmed", *controls)
            if question is None
            else sum(self.strata[s].harmed_by.get(question, 0) for s in controls)
        )
        return harmed, self.strata_sum("items", *controls)

    def precision(self) -> float | None:
        """Fixes over fixes and harms, every stratum; None when the stage changed nothing it is judged on."""
        fixed = self.strata_sum("fixed", *STRATA)
        harmed = self.strata_sum("harmed", *STRATA)
        return fixed / (fixed + harmed) if fixed + harmed else None

    def to_json(self) -> dict[str, Any]:
        return {stratum: vars(score) for stratum, score in self.strata.items()}


def score_seeded(
    document: SeededDocument, gold: Gold, verdicts: Mapping[int, PreReviewVerdict]
) -> SeededScore:
    """Score a stage's verdicts on a seeded document, item by item."""
    gold_by_key = {g.key: g for g in gold.individuals}
    names = {g.key: g.names for g in gold.individuals}
    result = SeededScore()
    for item in document.items:
        seed = document.seeds[item.index]
        cell = result.strata[seed.stratum]
        cell.items += 1
        verdict = verdicts.get(item.index)
        answer = verdict.answer if verdict is not None else PreReviewAnswer.KEEP
        if answer is PreReviewAnswer.UNSURE:
            cell.unsure += 1
        if seed.stratum == MERGE:
            if answer is PreReviewAnswer.SPLIT and _parts_name_all(verdict, seed.gold_keys, names):
                cell.fixed += 1
            elif answer in (PreReviewAnswer.SPLIT, PreReviewAnswer.RETYPE):
                cell.changed_wrongly += 1
            else:
                cell.missed += 1
            continue
        individual = gold_by_key[seed.gold_keys[0]]
        if seed.stratum in (RETYPE_REALISTIC, RETYPE_SAME_LAYER):
            if answer is PreReviewAnswer.RETYPE and individual.accepts(verdict.class_ref or ""):
                cell.fixed += 1
            elif answer in (PreReviewAnswer.SPLIT, PreReviewAnswer.RETYPE):
                cell.changed_wrongly += 1
            else:
                cell.missed += 1
            continue
        # A control or a split trap: correct as given
        if answer is PreReviewAnswer.SPLIT:
            cell.harmed += 1
            cell.harmed_by[PreReviewQuestion.SPLIT.value] += 1
        elif answer is PreReviewAnswer.RETYPE:
            if individual.accepts(verdict.class_ref or ""):
                cell.neutral += 1
            else:
                cell.harmed += 1
                cell.harmed_by[PreReviewQuestion.RETYPE.value] += 1
    return result


def _parts_name_all(
    verdict: PreReviewVerdict | None,
    keys: Sequence[str],
    names: Mapping[str, frozenset[str]],
) -> bool:
    """Whether a split's parts name every one of the gold individuals, each by a different part."""
    if verdict is None:
        return False
    parts = [name_key(part.title) for part in verdict.parts]
    remaining = list(parts)
    for key in keys:
        match = next((p for p in remaining if p in names[key]), None)
        if match is None:
            return False
        remaining.remove(match)
    return True


def wilson(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    """The Wilson score interval of a proportion (95% by default); (0, 1) with no trials."""
    if trials == 0:
        return 0.0, 1.0
    p = successes / trials
    centre = p + z * z / (2 * trials)
    spread = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials))
    denominator = 1 + z * z / trials
    return max(0.0, (centre - spread) / denominator), min(1.0, (centre + spread) / denominator)


# ---------------------------------------------------------------- the gate


@dataclass(frozen=True)
class QuestionGate:
    """Phase 1's gate for one question: recovery, and harms on the untouched items."""

    question: str
    recovery: float
    needed: float
    harms: int
    controls: int
    harm_rate: float
    harm_upper: float
    passed: bool


# The decision rule's thresholds (2026-11-22, set in advance)
RETYPE_RECOVERY = 0.5
SPLIT_RECOVERY = 0.6
MAX_HARM_RATE = 0.03
MAX_HARM_UPPER = 0.06


def gate(score: SeededScore) -> list[QuestionGate]:
    """Phase 1's gate, per question: does it recover enough without harming the controls?"""
    gates = []
    for question, recovery, needed in (
        (PreReviewQuestion.RETYPE.value, score.recovery(RETYPE_REALISTIC), RETYPE_RECOVERY),
        (PreReviewQuestion.SPLIT.value, score.recovery(MERGE), SPLIT_RECOVERY),
    ):
        harms, controls = score.control_harms(question)
        rate = harms / controls if controls else 0.0
        upper = wilson(harms, controls)[1]
        gates.append(
            QuestionGate(
                question=question,
                recovery=recovery,
                needed=needed,
                harms=harms,
                controls=controls,
                harm_rate=rate,
                harm_upper=upper,
                passed=recovery >= needed and rate <= MAX_HARM_RATE and upper <= MAX_HARM_UPPER,
            )
        )
    return gates
