"""Pure metric computation module for pipeline quality evaluation.

This module contains no infrastructure imports — only Python stdlib (math, re).
All metrics are deterministic functions of input lists/sets.
"""

import math
import re
from dataclasses import dataclass
from typing import Any, Callable, Optional

# A comparable triple key, as produced by extract_triple_key(): (subject, predicate, object).
Triple = tuple[str, str, str]

# A label similarity function: label -> embedding vector. When supplied to the
# soft-matching functions below, cosine_similarity(embed_fn(a), embed_fn(b)) is used
# in place of the pure-stdlib bag-of-stems fallback. Keeps this module infrastructure-free
# while still letting callers (e.g. the quality test suites) wire in a real embedding
# adapter for higher-fidelity subject/object matching.
EmbedFn = Callable[[str], list[float]]


@dataclass
class PrecisionRecallF1:
    """Triple metric: precision, recall, F1 score."""

    precision: float
    recall: float
    f1: float


def precision_recall_f1(expected: list[Any], actual: list[Any]) -> PrecisionRecallF1:
    """
    Compute precision, recall, and F1 score.

    Args:
        expected: List of expected items
        actual: List of actual items

    Returns:
        PrecisionRecallF1 with precision, recall, and f1 scores in [0, 1]
    """
    expected_set = set(expected)
    actual_set = set(actual)

    if len(actual_set) == 0:
        precision = 1.0 if len(expected_set) == 0 else 0.0
    else:
        precision = len(expected_set & actual_set) / len(actual_set)

    if len(expected_set) == 0:
        recall = 1.0 if len(actual_set) == 0 else 0.0
    else:
        recall = len(expected_set & actual_set) / len(expected_set)

    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * (precision * recall) / (precision + recall)

    return PrecisionRecallF1(
        precision=round(precision, 4), recall=round(recall, 4), f1=round(f1, 4)
    )


def jaccard_similarity(expected: list[Any], actual: list[Any]) -> float:
    """
    Compute Jaccard similarity (set overlap).

    Args:
        expected: List of expected items
        actual: List of actual items

    Returns:
        Jaccard index in [0, 1]
    """
    expected_set = set(expected)
    actual_set = set(actual)

    intersection = len(expected_set & actual_set)
    union = len(expected_set | actual_set)

    if union == 0:
        return 1.0

    return round(intersection / union, 4)


def reciprocal_rank(expected: list[str], ranked_list: list[str]) -> float:
    """
    Compute reciprocal rank (RR) for a single query.

    Finds the rank position of the first match from expected in ranked_list.
    For ranking quality of individual queries; not averaged across queries.

    Args:
        expected: List of correct item identifiers
        ranked_list: List of candidates in rank order

    Returns:
        RR in [0, 1], or 0.0 if no match found
    """
    expected_set = set(expected)

    for rank, item in enumerate(ranked_list, start=1):
        if item in expected_set:
            return round(1.0 / rank, 4)

    return 0.0


def brier_score(expected_probs: list[float], actual_labels: list[int]) -> float:
    """
    Compute Brier score (mean squared error of probabilities).

    Args:
        expected_probs: List of predicted probabilities in [0, 1]
        actual_labels: List of binary labels {0, 1}

    Returns:
        Brier score in [0, 1], lower is better
    """
    if len(expected_probs) != len(actual_labels):
        raise ValueError("Probability and label lists must have same length")

    if len(expected_probs) == 0:
        return 0.0

    squared_errors = [(prob - label) ** 2 for prob, label in zip(expected_probs, actual_labels)]

    return round(sum(squared_errors) / len(squared_errors), 4)


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Compute cosine similarity between two vectors.

    Args:
        vec_a: First vector (embedding)
        vec_b: Second vector (embedding)

    Returns:
        Cosine similarity in [-1, 1], typically [0, 1] for embeddings
    """
    if len(vec_a) != len(vec_b):
        raise ValueError("Vectors must have same dimension")

    if len(vec_a) == 0:
        return 1.0

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return round(dot_product / (norm_a * norm_b), 4)


def delta_set_overlap(
    expected_added: list[Any],
    actual_added: list[Any],
    expected_removed: list[Any],
    actual_removed: list[Any],
) -> float:
    """
    Compute set overlap for additions and removals combined (delta F1).

    For connection refinement: measures correctness of add/remove operations.
    Computes F1 over the union of added and removed items.

    Args:
        expected_added: Items that should have been added
        actual_added: Items actually added
        expected_removed: Items that should have been removed
        actual_removed: Items actually removed

    Returns:
        F1 score of the combined delta operation in [0, 1]
    """
    expected_delta = set(expected_added) | set(expected_removed)
    actual_delta = set(actual_added) | set(actual_removed)

    metrics = precision_recall_f1(list(expected_delta), list(actual_delta))
    return metrics.f1


@dataclass
class RankingMetrics:
    """Ranking metrics: top-1, top-3, MRR."""

    top1_precision: float
    top3_precision: float
    mrr: float


def mean_reciprocal_rank(expected_list: list[str], ranked_list: list[str]) -> float:
    """
    Compute Mean Reciprocal Rank (MRR) across a set of expected items.

    Averages the reciprocal rank of the first match for each expected item
    in the ranked list. Used for evaluating ranking quality.

    Args:
        expected_list: List of correct item identifiers
        ranked_list: List of candidates in rank order

    Returns:
        MRR in [0, 1], averaged across all expected items
    """
    if not expected_list:
        return 1.0

    set(expected_list)
    rr_sum = 0.0

    for expected_item in expected_list:
        found = False
        for rank, item in enumerate(ranked_list, start=1):
            if item == expected_item:
                rr_sum += 1.0 / rank
                found = True
                break
        if not found:
            # No match found; this expected item contributes 0 to RR sum
            pass

    return round(rr_sum / len(expected_list), 4)


def ranking_precision_at_k(expected: list[str], ranked_list: list[str], k: int) -> float:
    """
    Compute precision@k: fraction of top k results that are correct.

    Args:
        expected: List of correct item identifiers
        ranked_list: List of candidates in rank order (full list)
        k: Cutoff rank (1 for top-1, 3 for top-3)

    Returns:
        Precision@k in [0, 1]
    """
    if not expected:
        return 1.0

    expected_set = set(expected)
    top_k = set(ranked_list[:k])

    matches = len(expected_set & top_k)
    return round(matches / k, 4)


def ranking_metrics(expected: list[str], ranked_list: list[str]) -> RankingMetrics:
    """
    Compute complete ranking metrics (top-1, top-3, MRR).

    Args:
        expected: List of correct URIs or identifiers
        ranked_list: List of candidate URIs in rank order

    Returns:
        RankingMetrics dataclass with all three metrics
    """
    top1 = ranking_precision_at_k(expected, ranked_list, 1)
    top3 = ranking_precision_at_k(expected, ranked_list, 3)
    mrr = mean_reciprocal_rank(expected, ranked_list)

    return RankingMetrics(top1_precision=top1, top3_precision=top3, mrr=mrr)


# ---------------------------------------------------------------------------
# Soft triple matching (Karpathy loop §3.1) — tiered credit + coverage diagnostics.
#
# The strict `precision_recall_f1` above requires an exact (subject, predicate,
# object) string match and is kept as the acceptance floor. The functions below
# add a soft, tiered signal (partial credit for lemma/stem-normalized or
# embedding-close matches) plus three diagnostics that decompose a triple miss
# into "was the entity ever extracted", "was it ever related to anything", and
# "did the extracted label match the GT label" — see the module docstring in
# tests/integration/pipelines/_harness/error_report.py for the full failure-
# stage waterfall built on top of these primitives.
# ---------------------------------------------------------------------------

# Embedding-cosine threshold for treating two labels as the "same entity" when
# they don't share a lemma/stem-normalized form (soft-match tier 3, §3.1).
_EMBEDDING_MATCH_THRESHOLD = 0.85

_TIER_EXACT = 1.0
_TIER_NORMALIZED = 0.9
_TIER_EMBEDDING = 0.7
_TIER_NONE = 0.0

_SUFFIX_PATTERN = re.compile(r"[_\s/.\-]+")


def _stem_word(word: str) -> str:
    """
    Minimal, dependency-free suffix-stripping stemmer for verb/noun surface forms.

    Not a full lemmatizer (no POS awareness, no irregular-form dictionary) — it
    exists so this module can stay infrastructure-free while still collapsing
    the surface-form noise that dominates GT-authoring mismatches, e.g.
    'ensures'/'ensure', 'improves'/'improve', 'runs'/'run'.
    """
    if len(word) <= 3:
        return word
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith(("sses", "shes", "ches", "xes", "zes")):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    if word.endswith("ing") and len(word) > 5:
        return word[:-3]
    if word.endswith("ed") and len(word) > 4:
        return word[:-2]
    return word


def _label_tokens(label: str) -> list[str]:
    """Split a label into lowercased, stemmed content tokens (see `_stem_word`)."""
    words = _SUFFIX_PATTERN.split(label.lower())
    return [_stem_word(w) for w in words if w]


def normalize_label(label: str) -> str:
    """
    Lemma/stem-normalize a triple-slot label for measurement comparison.

    Used both to GT-normalize predicate labels at load time (so 'ensures' and
    'ensure' are counted as the same fact — a measurement correction, applied
    identically wherever comparable triple keys are built, strict or soft) and
    internally by the soft-match tiers below to compare subject/object labels
    after collapsing surface-form noise. See `_stem_word` for the normalization
    rule; this is a heuristic, not a full lemmatizer.

    Returns "" unchanged for an empty label.
    """
    if not label:
        return label
    return "_".join(_label_tokens(label))


def _label_similarity(a: str, b: str, embed_fn: Optional[EmbedFn] = None) -> float:
    """
    Cosine similarity between two labels.

    Uses `embed_fn` (label -> vector) if supplied. Otherwise falls back to a
    pure-stdlib proxy: cosine similarity over stemmed bag-of-words count
    vectors. The fallback keeps this module usable with zero infrastructure
    dependencies (e.g. in fast unit tests); callers that already have an
    embedding adapter wired up (as the individual-extraction quality suite
    does) should pass it for higher-fidelity subject/object matching.
    """
    if embed_fn is not None:
        return cosine_similarity(embed_fn(a), embed_fn(b))

    tokens_a = _label_tokens(a)
    tokens_b = _label_tokens(b)
    if not tokens_a or not tokens_b:
        return 0.0
    vocab = sorted(set(tokens_a) | set(tokens_b))
    vec_a = [float(tokens_a.count(w)) for w in vocab]
    vec_b = [float(tokens_b.count(w)) for w in vocab]
    return cosine_similarity(vec_a, vec_b)


def label_match_tier(a: str, b: str, embed_fn: Optional[EmbedFn] = None) -> float:
    """
    Classify how closely two triple-slot labels match, as one of four tiers.

    Returns 1.0 for an exact string match, 0.9 when they agree only after
    lemma/stem normalization, 0.7 when they are not lexically close but their
    embedding cosine similarity is >= 0.85, and 0.0 otherwise.
    """
    if a == b:
        return _TIER_EXACT
    if normalize_label(a) == normalize_label(b):
        return _TIER_NORMALIZED
    if _label_similarity(a, b, embed_fn) >= _EMBEDDING_MATCH_THRESHOLD:
        return _TIER_EMBEDDING
    return _TIER_NONE


def _triple_credit(expected: Triple, actual: Triple, embed_fn: Optional[EmbedFn] = None) -> float:
    """
    Tiered credit for how well one actual triple matches one expected triple (§3.1).

    1.0 - exact (subject, predicate, object) string match.
    0.9 - all three slots match after lemma/stem normalization.
    0.7 - subject & object match by embedding cosine >= 0.85 and the predicate
          matches by lemma/stem.
    0.0 - otherwise.
    """
    if expected == actual:
        return _TIER_EXACT

    exp_subj, exp_pred, exp_obj = expected
    act_subj, act_pred, act_obj = actual

    if (
        normalize_label(exp_subj) == normalize_label(act_subj)
        and normalize_label(exp_pred) == normalize_label(act_pred)
        and normalize_label(exp_obj) == normalize_label(act_obj)
    ):
        return _TIER_NORMALIZED

    if normalize_label(exp_pred) == normalize_label(act_pred):
        subj_sim = _label_similarity(exp_subj, act_subj, embed_fn)
        obj_sim = _label_similarity(exp_obj, act_obj, embed_fn)
        if subj_sim >= _EMBEDDING_MATCH_THRESHOLD and obj_sim >= _EMBEDDING_MATCH_THRESHOLD:
            return _TIER_EMBEDDING

    return _TIER_NONE


def _max_weight_match_credit(
    expected: list[Triple], actual: list[Triple], embed_fn: Optional[EmbedFn] = None
) -> float:
    """
    Greedy max-weight one-to-one matching between expected and actual triples.

    Scores every (expected, actual) pair via `_triple_credit`, then greedily
    assigns the highest-credit pairs first, skipping any triple already
    matched, so a single actual triple cannot be double-counted against
    multiple expected triples (and vice versa). Deterministic given the
    deterministic tie-break on index order.
    """
    pairs: list[tuple[float, int, int]] = []
    for i, exp in enumerate(expected):
        for j, act in enumerate(actual):
            credit = _triple_credit(exp, act, embed_fn)
            if credit > 0:
                pairs.append((credit, i, j))
    pairs.sort(key=lambda p: (-p[0], p[1], p[2]))

    matched_expected: set[int] = set()
    matched_actual: set[int] = set()
    total_credit = 0.0
    for credit, i, j in pairs:
        if i in matched_expected or j in matched_actual:
            continue
        matched_expected.add(i)
        matched_actual.add(j)
        total_credit += credit
    return total_credit


def soft_precision_recall_f1(
    expected: list[Triple], actual: list[Triple], embed_fn: Optional[EmbedFn] = None
) -> PrecisionRecallF1:
    """
    Soft precision/recall/F1 over triples using tiered partial credit (§3.1).

    Mirrors `precision_recall_f1`'s edge-case handling, but replaces exact-set
    intersection size with the total credit from a greedy max-weight matching
    (see `_max_weight_match_credit`). This is the hill-climbing signal for the
    Karpathy loop — it moves on lemma variants and chunk-boundary differences
    that the strict metric always scores as a total miss.

    Args:
        expected: GT triples as (subject, predicate, object) string tuples.
        actual: Extracted triples in the same shape.
        embed_fn: Optional label -> embedding vector function for subject/object
            similarity (tier 3). Falls back to a stdlib bag-of-stems proxy.

    Returns:
        PrecisionRecallF1 with precision, recall, and f1 in [0, 1].
    """
    total_credit = _max_weight_match_credit(expected, actual, embed_fn) if expected and actual else 0.0

    if len(actual) == 0:
        precision = 1.0 if len(expected) == 0 else 0.0
    else:
        precision = total_credit / len(actual)

    if len(expected) == 0:
        recall = 1.0 if len(actual) == 0 else 0.0
    else:
        recall = total_credit / len(expected)

    f1 = 0.0 if precision + recall == 0 else 2 * (precision * recall) / (precision + recall)

    return PrecisionRecallF1(
        precision=round(precision, 4), recall=round(recall, 4), f1=round(f1, 4)
    )


def candidate_recall(
    expected: list[Triple], actual: list[Triple], embed_fn: Optional[EmbedFn] = None
) -> float:
    """
    Fraction of GT subject/object labels present among any extracted candidate (§3.1).

    Pools every subject and object label mentioned across the GT triples and
    checks each one against the pool of subject/object labels appearing
    anywhere in the actual triples (any match tier > 0 counts) — irrespective
    of whether they were ever paired into a relation. Isolates coverage
    failures from relation-derivation and labeling failures.

    Note: the pipeline does not currently expose a candidate list distinct
    from its final triples, so "candidate" here means "appeared as a
    subject/object of some extracted triple". If/when a true pre-matching
    candidate list becomes available, wire it in here without changing the
    scoring below.
    """
    gt_labels = {label for subj, _pred, obj in expected for label in (subj, obj)}
    if not gt_labels:
        return 1.0

    candidate_labels = [label for subj, _pred, obj in actual for label in (subj, obj)]
    if not candidate_labels:
        return 0.0

    matched = sum(
        1
        for gt_label in gt_labels
        if any(label_match_tier(gt_label, candidate, embed_fn) > 0 for candidate in candidate_labels)
    )
    return round(matched / len(gt_labels), 4)


def predicate_recall(
    expected: list[Triple], actual: list[Triple], embed_fn: Optional[EmbedFn] = None
) -> float:
    """
    Fraction of GT (subject, object) pairs for which some relation was derived (§3.1).

    For each GT triple, checks whether any actual triple pairs matching
    subject and object labels (any match tier > 0, in the same direction),
    regardless of predicate. Isolates relation-derivation failures from
    predicate-labeling failures — a pair can count here even if every
    candidate predicate for it is wrong.
    """
    if not expected:
        return 1.0
    if not actual:
        return 0.0

    matched = sum(
        1
        for subj, _pred, obj in expected
        if any(
            label_match_tier(subj, a_subj, embed_fn) > 0 and label_match_tier(obj, a_obj, embed_fn) > 0
            for a_subj, _a_pred, a_obj in actual
        )
    )
    return round(matched / len(expected), 4)


def label_accuracy(
    expected: list[Triple], actual: list[Triple], embed_fn: Optional[EmbedFn] = None
) -> dict[str, float]:
    """
    Of the GT pairs for which some relation was derived, how many labels matched (§3.1).

    Restricts to the same "derived pair" population as `predicate_recall`
    (some actual triple connects matching subject/object labels, regardless of
    predicate), then reports what fraction of those pairs have exactly the GT
    subject/object labels ("strict") versus only a lemma/stem-normalized or
    embedding-close match ("soft", tier >= 0.9). A wide strict/soft gap
    isolates a label-normalization problem rather than an extraction problem.

    Returns:
        Dict with "strict", "soft" (both in [0, 1]) and "derived_count" (the
        denominator). When no pair was derived, strict/soft both default to
        1.0 (vacuously accurate — there is nothing to be wrong about) and
        derived_count is 0.
    """
    derived_tiers: list[float] = []
    for subj, _pred, obj in expected:
        candidates = [
            (a_subj, a_obj)
            for a_subj, _a_pred, a_obj in actual
            if label_match_tier(subj, a_subj, embed_fn) > 0 and label_match_tier(obj, a_obj, embed_fn) > 0
        ]
        if not candidates:
            continue
        best_tier = max(
            min(label_match_tier(subj, a_subj, embed_fn), label_match_tier(obj, a_obj, embed_fn))
            for a_subj, a_obj in candidates
        )
        derived_tiers.append(best_tier)

    if not derived_tiers:
        return {"strict": 1.0, "soft": 1.0, "derived_count": 0}

    strict = sum(1 for tier in derived_tiers if tier >= _TIER_EXACT) / len(derived_tiers)
    soft = sum(1 for tier in derived_tiers if tier >= _TIER_NORMALIZED) / len(derived_tiers)
    return {
        "strict": round(strict, 4),
        "soft": round(soft, 4),
        "derived_count": len(derived_tiers),
    }
