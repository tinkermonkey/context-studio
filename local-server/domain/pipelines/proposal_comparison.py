"""
Comparing two pipelines' proposals for the same source.

Two individual extractions of one source by two implementations propose many
of the same individuals. Their individual creates
are paired by the merge key of their titles (`individual_key`) into four
groups: both with the same classes, both with different classes, only in A,
only in B. A pair is decided once for both proposals: the chosen copy lands,
and the other proposal's copy closes as a duplicate of it (see
`ProposalService.decide_copies`). Each decision records, for both pipelines,
whether its pick was kept, had its class changed, or was not an element.

Agreements are not proof: a random sample of the same-class pairs (stable for
the two proposals, and prefix-stable as the sample grows) is checked first;
then the rest of the agreements can be accepted at once, which records how
many of the sample were changed.

Relationships are not compared.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from domain.pipelines.individual_extraction.labels import individual_key
from domain.versioning.exceptions import ChangeProposalStateError
from domain.versioning.gold import DecisionKind, ProposalDecision
from domain.versioning.proposals import (
    INDIVIDUAL_EXTRACTION,
    ORIGIN,
    AlternativeKind,
    ChangeProposal,
    CopyDecision,
    CopyOutcome,
    CopyResult,
    OperationKind,
    OperationRef,
    OperationStatus,
    OperationType,
    ProposalStatus,
    ProposedOperation,
    RejectionReason,
)
from domain.versioning.provenance import SOURCE_ID

if TYPE_CHECKING:
    from domain.ontology.ports import OntologyRepository
    from domain.versioning.proposal_service import ProposalService

DEFAULT_SAMPLE_SIZE = 10


class ComparisonGroup(str, Enum):
    """How the two proposals agree on an element."""

    SAME_CLASS = "same_class"
    CLASS_DIFFERS = "class_differs"
    ONLY_A = "only_a"
    ONLY_B = "only_b"


_GROUP_ORDER = {group: n for n, group in enumerate(ComparisonGroup)}


class PairState(str, Enum):
    """Where a pair's decision stands."""

    OPEN = "open"
    DECIDED = "decided"
    PARTLY_DECIDED = "partly_decided"
    FAILED = "failed"


class Verdict(str, Enum):
    """
    A reviewer's decision on a pair: keep it (the copies agree, or the only
    one is right), take A's class or B's, or neither is an element.
    """

    KEEP = "keep"
    A_CLASS = "a_class"
    B_CLASS = "b_class"
    NOT_ELEMENT = "not_element"


class ComparisonVerdict(str, Enum):
    """A decision as one pipeline's copy saw it (ProposalDecision.comparison)."""

    KEPT = "kept"
    CLASS_CHANGED = "class_changed"
    NOT_ELEMENT = "not_element"


class ProposalsNotComparableError(ValueError):
    """The two proposals are not two individual extractions of one source."""


class InvalidPairDecisionError(ValueError):
    """A pair decision that can't be taken as given; nothing is changed."""


class SampleUncheckedError(Exception):
    """The rest of the agreements can't be accepted while a sample pair is open."""


class SampleTooSmallError(ValueError):
    """The rest of the agreements can't be accepted on a sample smaller than the minimum."""


@dataclass(frozen=True)
class Pair:
    """
    One element as the two proposals propose it.

    Attributes:
        pair_id: Stable id of the pair: its operations' ids
        group: How the two proposals agree on it
        a, b: Each proposal's individual create; None when only the other has it
    """

    group: ComparisonGroup
    a: ProposedOperation | None
    b: ProposedOperation | None

    @property
    def pair_id(self) -> str:
        return f"{self.a.id if self.a else ''}~{self.b.id if self.b else ''}"

    @property
    def operations(self) -> list[ProposedOperation]:
        return [o for o in (self.a, self.b) if o is not None]

    @property
    def state(self) -> PairState:
        operations = self.operations
        decided = [o for o in operations if o.decided]
        if len(decided) == len(operations):
            return PairState.DECIDED
        if any(o.status is OperationStatus.FAILED for o in operations):
            return PairState.FAILED
        return PairState.PARTLY_DECIDED if decided else PairState.OPEN


def comparable_individuals(proposal: ChangeProposal) -> list[ProposedOperation]:
    """The operations a comparison pairs: individual creates the pipeline proposed."""
    return [
        o
        for o in proposal.operations
        if o.op is OperationType.CREATE
        and o.kind is OperationKind.INDIVIDUAL
        and not o.added_by_reviewer
    ]


def _title(operation: ProposedOperation) -> str:
    return str(operation.fields.get("title") or "")


def _classes(operation: ProposedOperation) -> frozenset[str]:
    return frozenset(operation.fields.get("class_ids") or ())


def pair_operations(a: ChangeProposal, b: ChangeProposal) -> list[Pair]:
    """
    Pair the two proposals' individual creates (any status) by the merge key of
    their titles. Within one key, copies with the same classes pair first, then
    the rest in seq order, one to one; what is left is only in A or only in B.
    Pairs are ordered by group, then by A's seq, then B's.
    """
    by_key_a = _by_key(comparable_individuals(a))
    by_key_b = _by_key(comparable_individuals(b))
    pairs: list[Pair] = []
    for key in sorted(set(by_key_a) | set(by_key_b)):
        left, right = list(by_key_a.get(key, ())), list(by_key_b.get(key, ()))
        matched: list[tuple[ProposedOperation, ProposedOperation]] = []
        for op_a in list(left):
            op_b = next((o for o in right if _classes(o) == _classes(op_a)), None)
            if op_b is not None:
                matched.append((op_a, op_b))
                left.remove(op_a)
                right.remove(op_b)
        matched += list(zip(left, right))
        pairs += [
            Pair(
                (
                    ComparisonGroup.SAME_CLASS
                    if _classes(op_a) == _classes(op_b)
                    else ComparisonGroup.CLASS_DIFFERS
                ),
                op_a,
                op_b,
            )
            for op_a, op_b in matched
        ]
        pairs += [Pair(ComparisonGroup.ONLY_A, o, None) for o in left[len(right) :]]
        pairs += [Pair(ComparisonGroup.ONLY_B, None, o) for o in right[len(left) :]]
    return sorted(
        pairs,
        key=lambda p: (
            _GROUP_ORDER[p.group],
            p.a.seq if p.a else -1,
            p.b.seq if p.b else -1,
        ),
    )


def _by_key(operations: Sequence[ProposedOperation]) -> dict[str, list[ProposedOperation]]:
    found: dict[str, list[ProposedOperation]] = {}
    for operation in sorted(operations, key=lambda o: o.seq):
        found.setdefault(individual_key(_title(operation)), []).append(operation)
    return found


def sample_ids(pairs: Sequence[Pair], a_id: str, b_id: str, sample_size: int) -> list[str]:
    """
    The same-class pairs to check first: the first sample_size of them shuffled
    by a generator seeded with the two proposals' ids, so the sample is the same
    on every read, and a larger one contains a smaller one.
    """
    same = [p.pair_id for p in pairs if p.group is ComparisonGroup.SAME_CLASS]
    # Seeded with the ids sorted: comparing B with A draws the same sample.
    random.Random(":".join(sorted((a_id, b_id)))).shuffle(same)
    return same[: max(0, min(len(same), sample_size))]


def comparability_problem(a: ChangeProposal, b: ChangeProposal) -> str | None:
    """Why two proposals can't be compared, if they can't."""
    if a.id == b.id:
        return "A proposal is compared with another one"
    for proposal in (a, b):
        metadata = proposal.client_metadata or {}
        pipeline = metadata.get("pipeline") or (metadata.get(ORIGIN) or {}).get("pipeline_type")
        if not proposal.extracted_from_source or pipeline != INDIVIDUAL_EXTRACTION:
            return f"Proposal {proposal.id} is not an individual extraction from a source"
        if proposal.superseded_by_extraction:
            return (
                f"Proposal {proposal.id} was superseded by a newer run of the same"
                " implementation; compare the newer one"
            )
    if a.taxonomy_id != b.taxonomy_id:
        return "The proposals are about different taxonomies"
    if a.dataset_id != b.dataset_id:
        return "The proposals are in different datasets"
    if (a.client_metadata or {}).get(SOURCE_ID) != (b.client_metadata or {}).get(SOURCE_ID):
        return "The proposals are extractions of different sources"
    return None


@dataclass(frozen=True)
class SampleStats:
    """How far the check of the agreements' sample has got."""

    size: int
    checked: int
    changed: int


@dataclass(frozen=True)
class Comparison:
    """Two proposals for the same source, paired."""

    a: ChangeProposal
    b: ChangeProposal
    pairs: list[Pair]
    sample: list[str]
    decisions: dict[str, ProposalDecision] = field(default_factory=dict)

    @property
    def sample_stats(self) -> SampleStats:
        in_sample = [p for p in self.pairs if p.pair_id in set(self.sample)]
        checked = [p for p in in_sample if p.state is PairState.DECIDED]
        return SampleStats(len(in_sample), len(checked), sum(1 for p in checked if self.changed(p)))

    def checked_sample(self) -> list[Pair]:
        """
        The decided pairs a decision recorded as checked in a sample of these
        two proposals (comparison.sample), whatever the sample's size now.
        """
        found = []
        for pair in self.pairs:
            if pair.state is not PairState.DECIDED:
                continue
            for operation, other in ((pair.a, self.b), (pair.b, self.a)):
                decision = self.decisions.get(operation.id) if operation else None
                record = (decision.comparison if decision else None) or {}
                if record.get("sample") and record.get("with_proposal_id") == other.id:
                    found.append(pair)
                    break
        return found

    def changed(self, pair: Pair) -> bool:
        """Whether deciding a (decided) pair changed what the two pipelines agreed on."""
        for operation in pair.operations:
            decision = self.decisions.get(operation.id)
            comparison = (decision.comparison if decision else None) or {}
            if comparison.get("verdict") not in (None, ComparisonVerdict.KEPT.value):
                return True
            if operation.status is OperationStatus.REJECTED and (
                operation.reason_code is not RejectionReason.DUPLICATE
            ):
                return True
            if decision is not None and decision.decision is DecisionKind.APPLIED_WITH_EDITS:
                return True
        return False

    def counts(self) -> dict[str, int]:
        counts = {group.value: 0 for group in ComparisonGroup}
        for pair in self.pairs:
            counts[pair.group.value] += 1
        counts["open"] = sum(1 for p in self.pairs if p.state is not PairState.DECIDED)
        return counts

    def pair(self, a_operation_id: str | None, b_operation_id: str | None) -> Pair:
        """
        The pair the given operations belong to (each on its side).

        Raises:
            InvalidPairDecisionError: If no operation is given, one is not an
                individual create its proposal's pipeline proposed, or the two
                are not one pair
        """
        if not a_operation_id and not b_operation_id:
            raise InvalidPairDecisionError("Name the A or the B operation of a pair")
        for side, operation_id, proposal in (
            ("A", a_operation_id, self.a),
            ("B", b_operation_id, self.b),
        ):
            if operation_id and operation_id not in {
                o.id for o in comparable_individuals(proposal)
            }:
                raise InvalidPairDecisionError(
                    f"{operation_id} is not an individual create of proposal {side}"
                )
        pair = next(
            (
                p
                for p in self.pairs
                if (a_operation_id is None or (p.a is not None and p.a.id == a_operation_id))
                and (b_operation_id is None or (p.b is not None and p.b.id == b_operation_id))
            ),
            None,
        )
        if pair is None:
            raise InvalidPairDecisionError("The two operations are not one pair")
        return pair


@dataclass(frozen=True)
class PairDecision:
    """
    A reviewer's decision on a pair.

    Attributes:
        a_operation_id, b_operation_id: The pair's copies to decide (one may be
            left out: only that copy is decided)
        verdict: keep, a_class, b_class or not_element
        reason_code: Why it is not an element (not_element only)
        match_entity_id: An existing individual the landing copy lists as a
            near match, to apply it as instead of creating one
        review_ms: The time the reviewer spent on the pair
    """

    verdict: Verdict
    a_operation_id: str | None = None
    b_operation_id: str | None = None
    reason_code: RejectionReason | None = None
    match_entity_id: str | None = None
    review_ms: int | None = None


@dataclass(frozen=True)
class PairResult:
    """A decided pair, as it stands after the decision."""

    pair: Pair
    outcome: CopyOutcome
    failure_reason: str | None
    comparison: Comparison


@dataclass(frozen=True)
class RestResult:
    """
    What accepting the rest of the agreements did.

    Attributes:
        landed: How many pairs landed
        failed: (pair id, why) of pairs whose landing copy failed
        skipped: (pair id, why: near_match or no_passage) of pairs left for a
            person: a copy lists near matches, or cites no passage
        sample: The sample's check, as recorded with every pair accepted
    """

    landed: int
    failed: list[tuple[str, str]]
    skipped: list[tuple[str, str]]
    sample: SampleStats


class ProposalComparisonService:
    """Compare two proposals for the same source, and decide their pairs once for both."""

    def __init__(self, proposals: ProposalService, ontology_repo: OntologyRepository) -> None:
        self._proposals = proposals
        self._repo = ontology_repo

    def compare(self, a_id: str, b_id: str, sample_size: int = DEFAULT_SAMPLE_SIZE) -> Comparison:
        """
        Pair two proposals' individual creates.

        Raises:
            ChangeProposalNotFoundError: If a proposal does not exist
            ProposalsNotComparableError: If they are the same proposal, or not
                two individual extractions of one source in one dataset
        """
        a, b = self._proposals.get(a_id), self._proposals.get(b_id)
        problem = comparability_problem(a, b)
        if problem is not None:
            raise ProposalsNotComparableError(problem)
        pairs = pair_operations(a, b)
        decisions = {**self._proposals.decisions_of(a.id), **self._proposals.decisions_of(b.id)}
        return Comparison(a, b, pairs, sample_ids(pairs, a.id, b.id, sample_size), decisions)

    def class_titles(self, comparison: Comparison) -> dict[str, str]:
        """The title of every class the compared operations name, by id."""
        titles: dict[str, str] = {}
        for pair in comparison.pairs:
            for operation in pair.operations:
                for class_id in (operation.applied_fields or operation.fields).get(
                    "class_ids"
                ) or ():
                    if class_id not in titles:
                        cls = self._repo.get_class(class_id)
                        titles[class_id] = cls.title if cls is not None else class_id
        return titles

    def alternative_titles(self, comparison: Comparison) -> dict[str, str]:
        """The current title of every near match the compared operations list, by id."""
        return {
            **self._proposals.alternative_titles(comparison.a),
            **self._proposals.alternative_titles(comparison.b),
        }

    def decide(
        self,
        a_id: str,
        b_id: str,
        decision: PairDecision,
        sample_size: int = DEFAULT_SAMPLE_SIZE,
    ) -> PairResult:
        """
        Decide a pair once for both proposals.

        A decision names both copies of the pair; one alone only when the
        pair has one, or its other copy is already decided (its decision then
        names that copy). keep lands A's copy (or the only one given),
        a_class lands A's and b_class B's, with its own classes; the other copy
        closes as a duplicate of it. not_element rejects every copy given with
        the reason_code. match_entity_id applies the landing copy as that near
        match. Each copy's decision records the comparison, its verdict
        comparing its proposed classes with what landed.

        Raises:
            ChangeProposalNotFoundError, ProposalsNotComparableError: As `compare`
            InvalidPairDecisionError: If the decision is malformed (see PairDecision)
            ChangeProposalStateError: If a copy is already decided, or a
                proposal is reverted or superseded; nothing is changed
        """
        comparison = self.compare(a_id, b_id, sample_size)
        _check_standing(comparison)
        pair = comparison.pair(decision.a_operation_id, decision.b_operation_id)
        for side, given, copy in (
            ("A", decision.a_operation_id, pair.a),
            ("B", decision.b_operation_id, pair.b),
        ):
            if copy is not None and not given and not copy.decided:
                # Deciding one copy alone would land the element twice.
                raise InvalidPairDecisionError(
                    f"Name both copies of the pair: {side}'s is still undecided"
                )
        a = pair.a if decision.a_operation_id else None
        b = pair.b if decision.b_operation_id else None
        copy_decision = self._copy_decision(comparison, pair, a, b, decision)
        [result] = self._proposals.decide_copies([copy_decision])
        after = self.compare(a_id, b_id, sample_size)
        decided = after.pair(decision.a_operation_id, decision.b_operation_id)
        return PairResult(decided, result.outcome, result.failure_reason, after)

    def _copy_decision(
        self,
        comparison: Comparison,
        pair: Pair,
        a: ProposedOperation | None,
        b: ProposedOperation | None,
        decision: PairDecision,
    ) -> CopyDecision:
        verdict = Verdict(decision.verdict)
        if decision.reason_code is not None and verdict is not Verdict.NOT_ELEMENT:
            raise InvalidPairDecisionError("A reason_code is only for not_element")
        if verdict in (Verdict.A_CLASS, Verdict.B_CLASS) and (a is None or b is None):
            raise InvalidPairDecisionError(f"{verdict.value} needs both operations")
        if verdict is Verdict.KEEP and a is not None and b is not None:
            if _classes(a) != _classes(b):
                raise InvalidPairDecisionError(
                    "The two copies have different classes: take a_class or b_class"
                )
        if verdict is Verdict.NOT_ELEMENT and decision.match_entity_id is not None:
            raise InvalidPairDecisionError("A match_entity_id is only for an element that lands")
        sampled = pair.pair_id in comparison.sample
        if verdict is Verdict.NOT_ELEMENT:
            copies = [o for o in (a, b) if o is not None]
            return CopyDecision(
                close=tuple(_ref(comparison, o) for o in copies),
                reason_code=RejectionReason(decision.reason_code or RejectionReason.OTHER),
                review_ms=decision.review_ms,
                comparisons=_records(comparison, pair, a, b, None, sampled, None),
            )
        land: ProposedOperation = b if verdict is Verdict.B_CLASS or a is None else a  # type: ignore[assignment]
        other = a if land is b else b
        alternative = None
        if decision.match_entity_id is not None:
            if land.alternative(decision.match_entity_id) is None:
                raise InvalidPairDecisionError(
                    f"{decision.match_entity_id} is not a near match the landing copy lists"
                )
            alternative = {
                "kind": AlternativeKind.EXISTING.value,
                "entity_id": decision.match_entity_id,
            }
        landed = self._landed_classes(land, decision.match_entity_id)
        return CopyDecision(
            land=_ref(comparison, land),
            close=(_ref(comparison, other),) if other is not None else (),
            chosen_alternative=alternative,
            review_ms=decision.review_ms,
            comparisons=_records(comparison, pair, a, b, landed, sampled, None),
        )

    def _landed_classes(
        self, land: ProposedOperation, match_entity_id: str | None
    ) -> frozenset[str]:
        """
        The classes the element lands with: the near match's it is applied as,
        the individual it already made (as edited), or its own as proposed.
        """
        entity_id = match_entity_id or (
            land.result_entity_id if land.status is OperationStatus.APPLIED else None
        )
        individual = self._repo.get_individual(entity_id) if entity_id else None
        if individual is not None:
            return frozenset(individual.class_ids)
        return frozenset((land.applied_fields or land.fields).get("class_ids") or ())

    def accept_rest(
        self, a_id: str, b_id: str, sample_size: int = DEFAULT_SAMPLE_SIZE
    ) -> RestResult:
        """
        Accept every same-class pair outside the sample whose two copies are
        both pending: A's copy lands and B's closes as its duplicate. A pair
        whose copy lists near matches, or cites no passage, is left for a
        person (skipped). The sample must be at least the default size (or
        every agreement, when fewer), and every pair in it decided. Each
        decision records how many sample pairs were actually checked and how
        many of those were changed (from their decisions' comparison records,
        not the sample_size asked). Calling it again changes nothing more.

        Raises:
            ChangeProposalNotFoundError, ProposalsNotComparableError: As `compare`
            SampleTooSmallError: If sample_size is below the minimum
            SampleUncheckedError: While a sample pair is not decided
            ChangeProposalStateError: If a proposal is reverted or superseded
        """
        comparison = self.compare(a_id, b_id, sample_size)
        _check_standing(comparison)
        agreements = sum(1 for p in comparison.pairs if p.group is ComparisonGroup.SAME_CLASS)
        minimum = min(DEFAULT_SAMPLE_SIZE, agreements)
        if sample_size < minimum:
            raise SampleTooSmallError(
                f"Check at least {minimum} of the {agreements} agreements before accepting the"
                f" rest (sample_size {sample_size})"
            )
        stats = comparison.sample_stats
        unchecked = [
            p.pair_id
            for p in comparison.pairs
            if p.pair_id in comparison.sample and p.state is not PairState.DECIDED
        ]
        if unchecked:
            raise SampleUncheckedError(
                f"{len(unchecked)} of the {stats.size} sample pairs are not decided yet"
            )
        # What was actually checked, whatever sample_size this call names.
        checked = comparison.checked_sample()
        bulk = {
            "sample_size": len(checked),
            "sample_changed": sum(1 for p in checked if comparison.changed(p)),
        }
        decisions: list[tuple[str, CopyDecision]] = []
        skipped: list[tuple[str, str]] = []
        for pair in comparison.pairs:
            if (
                pair.group is not ComparisonGroup.SAME_CLASS
                or pair.pair_id in comparison.sample
                or any(o.status is not OperationStatus.PENDING for o in pair.operations)
            ):
                continue
            if any(o.alternatives for o in pair.operations):
                skipped.append((pair.pair_id, "near_match"))
                continue
            if any(comparison_lacks_passage(comparison, o) for o in pair.operations):
                skipped.append((pair.pair_id, "no_passage"))
                continue
            records = _records(
                comparison, pair, pair.a, pair.b, _classes(pair.a), False, bulk  # type: ignore[arg-type]
            )
            decisions.append(
                (
                    pair.pair_id,
                    CopyDecision(
                        land=_ref(comparison, pair.a),  # type: ignore[arg-type]
                        close=(_ref(comparison, pair.b),),  # type: ignore[arg-type]
                        comparisons=records,
                    ),
                )
            )
        results: list[CopyResult] = (
            self._proposals.decide_copies([d for _, d in decisions]) if decisions else []
        )
        landed = sum(1 for r in results if r.outcome is CopyOutcome.LANDED)
        failed = [
            (pair_id, r.failure_reason or "")
            for (pair_id, _), r in zip(decisions, results)
            if r.outcome is CopyOutcome.FAILED
        ]
        return RestResult(landed, failed, skipped, stats)


def _check_standing(comparison: Comparison) -> None:
    """
    Both proposals still take decisions (a superseded one is not comparable at
    all): a decision covers both copies of its pair.
    """
    for proposal in (comparison.a, comparison.b):
        if proposal.status is ProposalStatus.REVERTED:
            raise ChangeProposalStateError(f"Change proposal {proposal.id} is reverted")


def _proposal_of(comparison: Comparison, operation: ProposedOperation) -> ChangeProposal:
    in_a = any(o.id == operation.id for o in comparison.a.operations)
    return comparison.a if in_a else comparison.b


def comparison_lacks_passage(comparison: Comparison, operation: ProposedOperation) -> bool:
    """Whether an operation of either compared proposal cites no passage in the source."""
    return _proposal_of(comparison, operation).lacks_passage(operation)


def _ref(comparison: Comparison, operation: ProposedOperation) -> OperationRef:
    return OperationRef(_proposal_of(comparison, operation).id, operation.id)


def _records(
    comparison: Comparison,
    pair: Pair,
    a: ProposedOperation | None,
    b: ProposedOperation | None,
    landed: frozenset[str] | None,
    sample: bool,
    bulk: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """
    The comparison record each decided copy's decision keeps, from its own
    pipeline's view: kept when what landed has the classes it proposed,
    class_changed otherwise; not_element without a landing (landed None). The
    other copy is the pair's, decided now or before.
    """
    records: dict[str, dict[str, Any]] = {}
    for operation, other, other_proposal in (
        (a, pair.b, comparison.b),
        (b, pair.a, comparison.a),
    ):
        if operation is None:
            continue
        if landed is None:
            verdict = ComparisonVerdict.NOT_ELEMENT
        elif _classes(operation) == landed:
            verdict = ComparisonVerdict.KEPT
        else:
            verdict = ComparisonVerdict.CLASS_CHANGED
        records[operation.id] = {
            "with_proposal_id": other_proposal.id,
            "with_operation_id": other.id if other is not None else None,
            "verdict": verdict.value,
            "sample": sample,
            "bulk": dict(bulk) if bulk is not None else None,
        }
    return records
