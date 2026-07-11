"""
Open knowledge-graph extraction: pure functions over OpenExtractionResult.

These build *concept* candidates (from noun chunks and prominent
NOUN/PROPN/ADJ tokens) and *relation* candidates (from verbs and their
dependency arguments) without the hard filtering of the LLM pipelines. They
port the salvageable logic from the legacy spaCy gap processor — dependency-role
priority tiers, connected-verb tracing, and a single-document TF-IDF
self-information filter — rewritten as referentially-transparent functions with
no spaCy / infrastructure imports.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from enum import IntEnum

from domain.extraction.ports import (
    ClusterAssignment,
    NounChunkSpan,
    OpenExtractionResult,
    OpenToken,
)

# ============================================================================
# Dependency-role priority tiers (ported from legacy spacy_gap.py)
# ============================================================================


class ConceptPriority(IntEnum):
    """
    Priority tier for a concept candidate, derived from its grammatical role.

    Lower value = higher priority (used directly as the primary sort key).
    """

    CRITICAL = 0  # subject positions: the actors/topics of clauses
    IMPORTANT = 1  # object positions: direct/prepositional objects, attributes
    CONTEXTUAL = 2  # modifiers/coordinations and everything else


_CRITICAL_DEPS = frozenset({"nsubj", "nsubjpass"})
_IMPORTANT_DEPS = frozenset({"dobj", "pobj", "attr", "dative"})
# CONTEXTUAL is the default tier (conj, appos, compound, amod, and all others).


def priority_for_dep(dep: str) -> ConceptPriority:
    """
    Map a spaCy dependency label to a concept-priority tier.

    Args:
        dep: Dependency relation label (e.g. 'nsubj', 'dobj', 'amod')

    Returns:
        The ConceptPriority tier; CONTEXTUAL for any unrecognized label.
    """
    if dep in _CRITICAL_DEPS:
        return ConceptPriority.CRITICAL
    if dep in _IMPORTANT_DEPS:
        return ConceptPriority.IMPORTANT
    return ConceptPriority.CONTEXTUAL


# ============================================================================
# Tunable parameters + candidate value objects
# ============================================================================


@dataclass(frozen=True)
class OpenExtractionParams:
    """
    Tunable parameters for open extraction (the closed-loop optimization knobs).

    Attributes:
        tf_idf_threshold: Minimum self-information score for a CONTEXTUAL/IMPORTANT
            candidate to survive; CRITICAL candidates bypass it. The primary
            "openness" dial — lower keeps more.
        max_verb_depth: Maximum head-pointer climbs when tracing a connected verb.
        min_chunk_chars: Noun chunks shorter than this (stripped) are skipped.
        standalone_pos: Coarse POS tags eligible as standalone concept candidates
            when a token is not already covered by a noun chunk.
        include_standalone: Whether to emit standalone-token concept candidates in
            addition to noun-chunk candidates.
    """

    tf_idf_threshold: float = 0.1
    max_verb_depth: int = 5
    min_chunk_chars: int = 3
    standalone_pos: frozenset[str] = frozenset({"NOUN", "PROPN", "ADJ"})
    include_standalone: bool = True

    def __post_init__(self) -> None:
        """Validate open-extraction tuning knobs (perturbed by the optimizer)."""
        if self.max_verb_depth < 1:
            raise ValueError(f"max_verb_depth must be >= 1, got {self.max_verb_depth}")
        if self.min_chunk_chars < 0:
            raise ValueError(f"min_chunk_chars must be >= 0, got {self.min_chunk_chars}")
        if self.tf_idf_threshold < 0.0:
            raise ValueError(
                f"tf_idf_threshold must be >= 0.0, got {self.tf_idf_threshold}"
            )


@dataclass(frozen=True)
class ConceptCandidate:
    """
    A concept candidate surfaced by open extraction.

    Attributes:
        text: Surface text of the concept (noun-chunk text or token text)
        lemma: Lowercased lemma of the concept's root token (clustering key)
        priority: Grammatical-role priority tier
        score: TF-IDF self-information score (0.0 if no qualifying words)
        root_index: Token index of the concept's root token
        sentence_index: Sentence the concept was found in
        connected_verb: Lemma/text of the governing verb, if any
        start: Character offset where the concept begins
        end: Character offset where the concept ends (exclusive)
    """

    text: str
    lemma: str
    priority: ConceptPriority
    score: float
    root_index: int
    sentence_index: int
    connected_verb: str | None
    start: int
    end: int
    label_lemmas: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate concept-candidate offset/index invariants."""
        if self.start < 0:
            raise ValueError(f"start must be >= 0, got {self.start}")
        if self.end < self.start:
            raise ValueError(
                f"end must be >= start, got start={self.start}, end={self.end}"
            )
        if self.root_index < 0:
            raise ValueError(f"root_index must be >= 0, got {self.root_index}")
        if self.sentence_index < 0:
            raise ValueError(f"sentence_index must be >= 0, got {self.sentence_index}")
        if not math.isfinite(self.score):
            raise ValueError(f"score must be finite, got {self.score}")


@dataclass(frozen=True)
class RelationCandidate:
    """
    A directed relation candidate: subject --(verb)--> object.

    Attributes:
        subject: Surface text of the subject argument
        predicate: Lemma of the connecting verb
        object: Surface text of the object argument
        subject_index: Token index of the subject's root
        verb_index: Token index of the verb
        object_index: Token index of the object's root
        sentence_index: Sentence the relation was found in
    """

    subject: str
    predicate: str
    object: str
    subject_index: int
    verb_index: int
    object_index: int
    sentence_index: int
    subject_lemmas: tuple[str, ...] = ()
    object_lemmas: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate relation-candidate token-index invariants.

        Subject, verb, and object indices must be non-negative. No positional
        ordering is enforced between them: dependency structure routinely places
        the subject or object on either side of the verb (e.g. passive voice),
        so subject_index < verb_index < object_index is not an invariant.
        """
        if self.subject_index < 0:
            raise ValueError(f"subject_index must be >= 0, got {self.subject_index}")
        if self.verb_index < 0:
            raise ValueError(f"verb_index must be >= 0, got {self.verb_index}")
        if self.object_index < 0:
            raise ValueError(f"object_index must be >= 0, got {self.object_index}")
        if self.sentence_index < 0:
            raise ValueError(f"sentence_index must be >= 0, got {self.sentence_index}")


# ============================================================================
# Connected-verb tracing (ported from legacy _find_connected_verb)
# ============================================================================


def find_connected_verb(
    tokens: Sequence[OpenToken],
    start_index: int,
    max_depth: int = 5,
) -> str | None:
    """
    Find the verb governing a token by climbing the dependency tree, then
    falling back to the token's immediate children.

    Args:
        tokens: All tokens in the document (tokens[i].index == i).
        start_index: Index of the token to trace from.
        max_depth: Maximum number of head-pointer climbs.

    Returns:
        The connecting verb's text, or None if none is found within max_depth.
    """
    if not 0 <= start_index < len(tokens):
        return None

    # 1. Climb head pointers looking for a VERB.
    current = tokens[start_index]
    depth = 0
    while depth < max_depth:
        if current.pos == "VERB":
            return current.text
        if current.head_index == current.index:  # spaCy root: head is self
            break
        current = tokens[current.head_index]
        depth += 1

    # 2. Fallback: scan immediate children of the start token for a VERB
    #    (children = tokens whose head_index == start_index).
    for tok in tokens:
        if tok.head_index == start_index and tok.index != start_index and tok.pos == "VERB":
            return tok.text
    return None


# ============================================================================
# TF-IDF self-information filter (ported from legacy _apply_tfidf_filtering)
# ============================================================================


def _build_term_frequencies(tokens: Sequence[OpenToken]) -> tuple[Counter[str], int]:
    """
    Build the single-document term pool from content tokens.

    Uses lowercased surface text (not lemmas) so the pool is in the same units
    as the candidate words scored against it (which come from text.split());
    a lemma pool would zero out every inflected surface candidate.
    """
    pool = [tok.text.lower() for tok in tokens if tok.is_alpha and not tok.is_stop]
    return Counter(pool), len(pool)


def _tfidf_score(text: str, term_freq: Counter[str], doc_length: int) -> float:
    """
    Single-document self-information score for a candidate phrase.

    Rare terms score higher (idf = log(1 / (tf + 0.01))). Returns the mean of
    the per-word tf*idf values over words longer than two characters, or 0.0 if
    there are no qualifying words.
    """
    words = [w.lower() for w in text.split() if len(w) > 2]
    if not words or doc_length == 0:
        return 0.0
    scores = []
    for word in words:
        tf = term_freq.get(word, 0) / doc_length
        idf = math.log(1.0 / (tf + 0.01))
        scores.append(tf * idf)
    return sum(scores) / len(scores) if scores else 0.0


# ============================================================================
# Candidate builders
# ============================================================================


def _covered_token_indices(noun_chunks: Sequence[NounChunkSpan]) -> set[int]:
    """Token indices that fall inside some noun chunk."""
    covered: set[int] = set()
    for chunk in noun_chunks:
        covered.update(range(chunk.start_token, chunk.end_token))
    return covered


def _all_stopwords(tokens: Sequence[OpenToken], chunk: NounChunkSpan) -> bool:
    """True if every token in a chunk is a stopword."""
    chunk_tokens = tokens[chunk.start_token : chunk.end_token]
    return bool(chunk_tokens) and all(tok.is_stop for tok in chunk_tokens)


def _chunk_label_lemmas(tokens: Sequence[OpenToken], chunk: NounChunkSpan) -> tuple[str, ...]:
    """
    Content-word lemmas of a noun chunk, in order, for label synthesis.

    Keeps alphabetic, non-stopword NOUN/PROPN/ADJ tokens (dropping determiners,
    prepositions, punctuation) and lowercases their lemmas — so 'the consensus
    algorithms' yields ('consensus', 'algorithm'), which PascalCases to
    'ConsensusAlgorithm'. Falls back to the root lemma if nothing qualifies.
    """
    out = [
        tok.lemma.lower()
        for tok in tokens[chunk.start_token : chunk.end_token]
        if tok.is_alpha and not tok.is_stop and tok.pos in {"NOUN", "PROPN", "ADJ"}
    ]
    if not out:
        out = [tokens[chunk.root_index].lemma.lower()]
    return tuple(out)


def pascal_label(lemmas: tuple[str, ...]) -> str:
    """PascalCase label from content lemmas: ('consensus', 'algorithm') -> 'ConsensusAlgorithm'."""
    return "".join(word.capitalize() for word in lemmas if word)


def synthesize_label(candidate: ConceptCandidate) -> str:
    """
    PascalCase ontology-style label from a candidate's content-word lemmas.

    ('consensus', 'algorithm') -> 'ConsensusAlgorithm'. Falls back to the
    candidate's surface words when no label lemmas were captured.
    """
    words = candidate.label_lemmas or tuple(w.lower() for w in candidate.text.split())
    return pascal_label(words)


def build_concept_candidates(
    result: OpenExtractionResult,
    params: OpenExtractionParams | None = None,
) -> list[ConceptCandidate]:
    """
    Build concept candidates from noun chunks and standalone content tokens.

    Applies dependency-role priority, connected-verb tracing, and TF-IDF
    filtering (CRITICAL candidates bypass the threshold). Returns candidates
    sorted by (priority, descending score).

    Args:
        result: Open NLP extraction output.
        params: Tunable parameters; defaults to OpenExtractionParams().

    Returns:
        Filtered, sorted list of ConceptCandidate. Same-lemma mentions are kept
        (clustering distils them downstream).
    """
    params = params or OpenExtractionParams()
    tokens = result.tokens
    term_freq, doc_length = _build_term_frequencies(tokens)
    candidates: list[ConceptCandidate] = []

    # Noun-chunk candidates.
    for chunk in result.noun_chunks:
        stripped = chunk.text.strip()
        if len(stripped) < params.min_chunk_chars:
            continue
        if _all_stopwords(tokens, chunk):
            continue
        root = tokens[chunk.root_index]
        candidates.append(
            ConceptCandidate(
                text=stripped,
                lemma=root.lemma.lower(),
                priority=priority_for_dep(root.dep),
                score=_tfidf_score(stripped, term_freq, doc_length),
                root_index=chunk.root_index,
                sentence_index=chunk.sentence_index,
                connected_verb=find_connected_verb(
                    tokens, chunk.root_index, params.max_verb_depth
                ),
                start=chunk.start,
                end=chunk.end,
                label_lemmas=_chunk_label_lemmas(tokens, chunk),
            )
        )

    # Standalone content-token candidates not already covered by a chunk.
    if params.include_standalone:
        covered = _covered_token_indices(result.noun_chunks)
        for tok in tokens:
            if tok.index in covered:
                continue
            if tok.pos not in params.standalone_pos:
                continue
            if tok.is_stop or not tok.is_alpha:
                continue
            text = tok.text.strip()
            if len(text) < params.min_chunk_chars:
                continue
            candidates.append(
                ConceptCandidate(
                    text=text,
                    lemma=tok.lemma.lower(),
                    priority=priority_for_dep(tok.dep),
                    score=_tfidf_score(text, term_freq, doc_length),
                    root_index=tok.index,
                    sentence_index=tok.sentence_index,
                    connected_verb=find_connected_verb(
                        tokens, tok.index, params.max_verb_depth
                    ),
                    start=tok.start,
                    end=tok.end,
                    label_lemmas=(tok.lemma.lower(),),
                )
            )

    # Filter: CRITICAL bypasses the threshold; others must clear it.
    kept = [
        c
        for c in candidates
        if c.priority == ConceptPriority.CRITICAL or c.score >= params.tf_idf_threshold
    ]
    kept.sort(key=lambda c: (c.priority, -c.score))
    return kept


def _phrase_for_token(result: OpenExtractionResult, token_index: int) -> str:
    """Containing noun-chunk text for a token, else the token's own text."""
    for chunk in result.noun_chunks:
        if chunk.start_token <= token_index < chunk.end_token:
            return chunk.text.strip()
    return result.tokens[token_index].text.strip()


def _token_label_lemmas(result: OpenExtractionResult, token_index: int) -> tuple[str, ...]:
    """Content-word lemmas of a token's enclosing chunk, else the token's lemma."""
    for chunk in result.noun_chunks:
        if chunk.start_token <= token_index < chunk.end_token:
            return _chunk_label_lemmas(result.tokens, chunk)
    return (result.tokens[token_index].lemma.lower(),)


def snake_label(lemmas: tuple[str, ...]) -> str:
    """snake_case label from content lemmas: ('consensus', 'algorithm') -> 'consensus_algorithm'."""
    return "_".join(word for word in lemmas if word)


def build_relation_candidates(result: OpenExtractionResult) -> list[RelationCandidate]:
    """
    Build directed subject --(verb)--> object relation candidates.

    For each VERB token, pairs its subject argument(s) (nsubj/nsubjpass whose
    head is the verb) with its object argument(s): direct objects/attributes/
    datives whose head is the verb, plus prepositional objects (pobj whose head
    is a preposition governed by the verb). Relations are dependency-structural
    and not TF-IDF filtered (the openness dial applies only to concept candidates).

    Args:
        result: Open NLP extraction output.

    Returns:
        List of RelationCandidate in document order.
    """
    tokens = result.tokens
    relations: list[RelationCandidate] = []

    for verb in tokens:
        if verb.pos != "VERB":
            continue

        subjects = [
            t for t in tokens if t.head_index == verb.index and t.dep in _CRITICAL_DEPS
        ]
        if not subjects:
            continue

        # Direct objects / attributes / datives governed by the verb.
        objects = [
            t
            for t in tokens
            if t.head_index == verb.index and t.dep in {"dobj", "attr", "dative"}
        ]
        # Prepositional objects: pobj -> prep(head) -> verb.
        for prep in tokens:
            if prep.head_index == verb.index and prep.dep == "prep":
                objects.extend(
                    t for t in tokens if t.head_index == prep.index and t.dep == "pobj"
                )

        for subj in subjects:
            for obj in objects:
                relations.append(
                    RelationCandidate(
                        subject=_phrase_for_token(result, subj.index),
                        predicate=verb.lemma.lower(),
                        object=_phrase_for_token(result, obj.index),
                        subject_index=subj.index,
                        verb_index=verb.index,
                        object_index=obj.index,
                        sentence_index=verb.sentence_index,
                        subject_lemmas=_token_label_lemmas(result, subj.index),
                        object_lemmas=_token_label_lemmas(result, obj.index),
                    )
                )

    return relations


# ============================================================================
# Cluster representative selection (pairs ClusteringPort output with candidates)
# ============================================================================


def select_cluster_representatives(
    candidates: list[ConceptCandidate],
    assignments: list[ClusterAssignment],
) -> list[ConceptCandidate]:
    """
    Pick one representative concept per cluster to distil the candidate set.

    Candidates and assignments are paired positionally (assignment.index is the
    candidate's position). For each real cluster (label >= 0), the
    highest-priority, highest-score candidate is the representative. Noise points
    (label -1) are each kept as their own representative so distinct one-off
    concepts are not discarded.

    Args:
        candidates: Concept candidates, in the order they were embedded/clustered.
        assignments: One ClusterAssignment per candidate (same length/order).

    Returns:
        Representatives sorted by (priority, descending score). Returns an empty
        list when given no candidates.

    Raises:
        ValueError: If candidates and assignments differ in length.
    """
    if len(candidates) != len(assignments):
        raise ValueError(
            f"candidates ({len(candidates)}) and assignments ({len(assignments)}) "
            "must be the same length"
        )

    best_by_label: dict[int, ConceptCandidate] = {}
    representatives: list[ConceptCandidate] = []
    for assignment in assignments:
        candidate = candidates[assignment.index]
        if assignment.label < 0:  # noise: keep individually
            representatives.append(candidate)
            continue
        incumbent = best_by_label.get(assignment.label)
        if incumbent is None or (candidate.priority, -candidate.score) < (
            incumbent.priority,
            -incumbent.score,
        ):
            best_by_label[assignment.label] = candidate

    representatives.extend(best_by_label.values())
    representatives.sort(key=lambda c: (c.priority, -c.score))
    return representatives
