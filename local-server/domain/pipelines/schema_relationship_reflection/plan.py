"""
Reflections and the change plan they imply.

A reflection is the decision model's answers to one relationship type's
sorting questions. Its outcome (DR's `reflectionOutcome()` in
`triage-reflect.ts`):

- reproduced:  every answer is the current source, target and predicate
- no_better:   no concrete alternative won (each answer is current or 'none')
- alternative: a different class or predicate won at least one question

Alternatives become a change plan, one row per relationship type (a port of
DR's `reflect-plan.ts`). Kinds:

- remove-duplicate:  the preferred predicate already joins the same pair
- rename-predicate:  change the predicate
- reverse:           swap source and target (and possibly the predicate)
- retarget:          change the source and/or target class
- compound:          more than one of the above at once
- conflict:          one type's replacement is another type that its own
                     reflection wants changed, so the two rows disagree

`p` is the minimum probability over a change's alternatives. (DR takes the
maximum for a conflict because there several claims about one triple
disagree; a run here asks once per relationship type, so each row holds one
change, DR's per-triple conflict cannot arise, and a conflict row keeps its
own p.)
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace

from domain.decision.value_objects import NONE_OPTION

from .questions import (
    PREDICATE_FOR,
    QUESTION_NAMES,
    REVERSE_PREFIX,
    SOURCE_FOR,
    TARGET_FOR,
    Triple,
)

REPRODUCED = "reproduced"
NO_BETTER = "no_better"
ALTERNATIVE = "alternative"

REMOVE_DUPLICATE = "remove-duplicate"
RENAME_PREDICATE = "rename-predicate"
REVERSE = "reverse"
RETARGET = "retarget"
COMPOUND = "compound"
CONFLICT = "conflict"
PLAN_KINDS = (REMOVE_DUPLICATE, RENAME_PREDICATE, REVERSE, RETARGET, COMPOUND, CONFLICT)
# Kinds whose changes always need a person: never applied by an approval policy
BREAKING_KINDS = frozenset({RETARGET, COMPOUND, CONFLICT})

MIN_REPORTED_PROBABILITY = 0.01


@dataclass(frozen=True)
class RankedAnswer:
    """One sorting answer: the choice and the distribution over options."""

    choice: str | None
    probabilities: Mapping[str, float]

    def probability(self, option: str) -> float:
        return float(self.probabilities.get(option, 0.0))

    def ranked(self) -> list[tuple[str, float]]:
        return sorted(self.probabilities.items(), key=lambda kv: (-kv[1], kv[0]))

    def top3(self) -> str:
        """The three likeliest options, e.g. 'a (0.81), none (0.12), b (0.02)'."""
        return ", ".join(f"{k} ({v:.2f})" for k, v in self.ranked()[:3])

    @classmethod
    def of(cls, choice: str | None, probabilities: Mapping[str, float]) -> "RankedAnswer":
        """Keep options of at least 1%, rounded to three places (as DR records them)."""
        kept = {
            k: round(float(v), 3)
            for k, v in probabilities.items()
            if float(v) >= MIN_REPORTED_PROBABILITY
        }
        return cls(choice=choice, probabilities=kept)


@dataclass(frozen=True)
class Reflection:
    """The sorting answers about one relationship type."""

    property_id: str
    triple: Triple
    answers: Mapping[str, RankedAnswer]
    candidates: Mapping[str, Sequence[str]]
    outcome: str
    alternatives: tuple[str, ...]
    evidence: str = ""
    latency_ms: float | None = None
    cost_usd: float | None = None

    def summary(self) -> str:
        """The answers in one sentence, for a reviewer."""
        t = self.triple
        a = self.answers
        alternatives = f" ({'; '.join(self.alternatives)})" if self.alternatives else ""
        return (
            f"Sorting answers: best source of '{t.predicate} {t.target}':"
            f" {a[SOURCE_FOR].top3()}; best destination of '{t.source} {t.predicate}':"
            f" {a[TARGET_FOR].top3()}; best predicate: {a[PREDICATE_FOR].top3()}."
            f" Outcome: {self.outcome}{alternatives}."
        )

    def to_json(self) -> dict:
        return {
            "property_id": self.property_id,
            "triple": str(self.triple),
            "source": self.triple.source,
            "predicate": self.triple.predicate,
            "target": self.triple.target,
            "outcome": self.outcome,
            "alternatives": list(self.alternatives),
            "answers": {
                q: {
                    "choice": a.choice,
                    "top3": a.top3(),
                    "probabilities": dict(a.probabilities),
                }
                for q, a in self.answers.items()
            },
            "candidates": {q: list(c) for q, c in self.candidates.items()},
            "latency_ms": self.latency_ms,
            "cost_usd": self.cost_usd,
        }


def _current(t: Triple) -> dict[str, str]:
    return {SOURCE_FOR: t.source, TARGET_FOR: t.target, PREDICATE_FOR: t.predicate}


def reflection_outcome(
    t: Triple, answers: Mapping[str, RankedAnswer]
) -> tuple[str, tuple[str, ...]]:
    """The outcome and the alternatives that won, e.g. ('source=x', 'predicate=reverse:p')."""
    alternatives = []
    for question, current in _current(t).items():
        choice = answers[question].choice
        if choice and choice != current and choice != NONE_OPTION:
            alternatives.append(f"{question.removesuffix('_for')}={choice}")
    if alternatives:
        return ALTERNATIVE, tuple(alternatives)
    reproduced = all(answers[q].choice == cur for q, cur in _current(t).items())
    return (REPRODUCED if reproduced else NO_BETTER), ()


@dataclass(frozen=True)
class Change:
    """The change one reflection implies."""

    kind: str
    replacement: Triple
    reversed: bool
    p: float
    alternatives: tuple[str, ...]


def change_of(reflection: Reflection, existing: Iterable[Triple]) -> Change:
    """The change an 'alternative' reflection implies (DR's oneChange)."""
    t = reflection.triple
    a = reflection.answers
    source, target, predicate = t.source, t.target, t.predicate
    parts: list[str] = []
    alternatives: list[str] = []
    reversed_ = False
    p = 1.0

    def won(question: str, current: str) -> str | None:
        choice = a[question].choice
        return choice if choice and choice != current and choice != NONE_OPTION else None

    def note(question: str, choice: str) -> None:
        nonlocal p
        probability = a[question].probability(choice)
        p = min(p, probability)
        alternatives.append(f"{question.removesuffix('_for')}={choice}|{probability:.2f}")

    if (choice := won(SOURCE_FOR, t.source)) is not None:
        source = choice
        parts.append(RETARGET)
        note(SOURCE_FOR, choice)
    if (choice := won(TARGET_FOR, t.target)) is not None:
        target = choice
        parts.append(RETARGET)
        note(TARGET_FOR, choice)
    if (choice := won(PREDICATE_FOR, t.predicate)) is not None:
        if choice.startswith(REVERSE_PREFIX):
            reversed_ = True
            predicate = choice.removeprefix(REVERSE_PREFIX)
            parts.append(REVERSE)
        else:
            predicate = choice
            parts.append("predicate")
        note(PREDICATE_FOR, choice)
    replacement = (
        Triple(target, predicate, source) if reversed_ else Triple(source, predicate, target)
    )
    kinds = list(dict.fromkeys(parts))
    if len(kinds) > 1:
        kind = COMPOUND
    elif kinds[0] in (REVERSE, RETARGET):
        kind = kinds[0]
    else:
        kind = REMOVE_DUPLICATE if replacement in set(existing) else RENAME_PREDICATE
    return Change(kind, replacement, reversed_, p, tuple(alternatives))


@dataclass(frozen=True)
class PlannedChange:
    """One row of the change plan: what to do with one relationship type."""

    property_id: str
    current: Triple
    kind: str
    replacement: Triple
    replacement_exists: bool
    p: float
    alternatives: tuple[str, ...]
    reflection: Reflection
    reversed: bool = False


def build_plan(
    reflections: Sequence[Reflection], existing: Iterable[Triple]
) -> list[PlannedChange]:
    """
    The change plan for the reflections with a concrete alternative, highest p first.

    Args:
        reflections: One reflection per relationship type (any outcome; only
            alternatives make rows)
        existing: Every relationship type of the taxonomy, as triples
    """
    known = set(existing)
    plan = []
    for reflection in reflections:
        if reflection.outcome != ALTERNATIVE:
            continue
        change = change_of(reflection, known)
        plan.append(
            PlannedChange(
                property_id=reflection.property_id,
                current=reflection.triple,
                kind=change.kind,
                replacement=change.replacement,
                replacement_exists=change.replacement in known,
                p=change.p,
                alternatives=change.alternatives,
                reflection=reflection,
                reversed=change.reversed,
            )
        )
    plan = _mark_contradictions(plan)
    return sorted(plan, key=lambda row: (-row.p, str(row.current), row.property_id))


def _mark_contradictions(plan: list[PlannedChange]) -> list[PlannedChange]:
    """
    A row whose replacement is the current triple of another row is a
    conflict, and so is that other row: one reflection prefers a type the
    other wants changed, so neither can be applied without deciding between them.
    """
    changing = {row.current for row in plan}

    def contradicts(row: PlannedChange) -> bool:
        return row.replacement != row.current and row.replacement in changing

    contradicted = {row.replacement for row in plan if contradicts(row)}
    marked = []
    for row in plan:
        if row.kind != CONFLICT and (contradicts(row) or row.current in contradicted):
            row = replace(row, kind=CONFLICT)
        marked.append(row)
    return marked


def plan_counts(plan: Sequence[PlannedChange]) -> dict[str, int]:
    """Rows per kind, every kind listed."""
    return {kind: sum(1 for row in plan if row.kind == kind) for kind in PLAN_KINDS}


def outcome_counts(reflections: Sequence[Reflection]) -> dict[str, int]:
    return {
        outcome: sum(1 for r in reflections if r.outcome == outcome)
        for outcome in (REPRODUCED, NO_BETTER, ALTERNATIVE)
    }


__all__ = [
    "ALTERNATIVE",
    "BREAKING_KINDS",
    "COMPOUND",
    "CONFLICT",
    "NO_BETTER",
    "PLAN_KINDS",
    "QUESTION_NAMES",
    "REMOVE_DUPLICATE",
    "RENAME_PREDICATE",
    "REPRODUCED",
    "RETARGET",
    "REVERSE",
    "PlannedChange",
    "RankedAnswer",
    "Reflection",
    "build_plan",
    "change_of",
    "outcome_counts",
    "plan_counts",
    "reflection_outcome",
]
