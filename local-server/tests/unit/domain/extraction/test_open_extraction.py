"""
Unit tests for open-extraction pure functions.

These exercise domain/extraction/open_extraction.py with hand-built
OpenExtractionResult inputs (no spaCy), so they run in milliseconds and pin the
ported legacy logic: dependency-role priority, connected-verb tracing, TF-IDF
filtering, and concept/relation candidate building.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from domain.extraction.open_extraction import (
    ConceptCandidate,
    ConceptPriority,
    OpenExtractionParams,
    build_concept_candidates,
    build_relation_candidates,
    build_wider_relation_candidates,
    find_connected_verb,
    priority_for_dep,
    select_cluster_representatives,
    unconsumed_noun_chunk_heads,
)
from domain.extraction.ports import (
    ClusterAssignment,
    NounChunkSpan,
    OpenExtractionResult,
    OpenToken,
)


def _tok(
    index,
    text,
    pos,
    dep,
    head_index,
    *,
    lemma=None,
    tag="X",
    sent=0,
    is_stop=False,
    is_alpha=True,
):
    """Build an OpenToken with sensible char offsets for tests."""
    return OpenToken(
        index=index,
        text=text,
        lemma=(lemma or text).lower(),
        pos=pos,
        tag=tag,
        dep=dep,
        head_index=head_index,
        start=index,
        end=index + len(text),
        sentence_index=sent,
        is_stop=is_stop,
        is_alpha=is_alpha,
    )


def _chunk(text, start_token, end_token, root_index, sent=0):
    return NounChunkSpan(
        text=text,
        start_token=start_token,
        end_token=end_token,
        root_index=root_index,
        start=0,
        end=len(text),
        sentence_index=sent,
    )


def _kafka_doc():
    """'Kafka streams events.' — subject/verb/object."""
    tokens = [
        _tok(0, "Kafka", "PROPN", "nsubj", 1, lemma="kafka"),
        _tok(1, "streams", "VERB", "ROOT", 1, lemma="stream"),
        _tok(2, "events", "NOUN", "dobj", 1, lemma="event"),
        _tok(3, ".", "PUNCT", "punct", 1, lemma=".", is_alpha=False),
    ]
    chunks = [_chunk("Kafka", 0, 1, 0), _chunk("events", 2, 3, 2)]
    return OpenExtractionResult(
        tokens=tokens, noun_chunks=chunks, sentence_count=1, language="en"
    )


# ---------------------------------------------------------------------------
# priority_for_dep
# ---------------------------------------------------------------------------


def test_priority_for_dep_critical():
    assert priority_for_dep("nsubj") == ConceptPriority.CRITICAL
    assert priority_for_dep("nsubjpass") == ConceptPriority.CRITICAL


def test_priority_for_dep_important():
    for dep in ("dobj", "pobj", "attr", "dative"):
        assert priority_for_dep(dep) == ConceptPriority.IMPORTANT


def test_priority_for_dep_contextual_and_default():
    for dep in ("amod", "compound", "conj", "appos", "ROOT", "weird-unknown"):
        assert priority_for_dep(dep) == ConceptPriority.CONTEXTUAL


# ---------------------------------------------------------------------------
# find_connected_verb
# ---------------------------------------------------------------------------


def test_find_connected_verb_climbs_to_head():
    doc = _kafka_doc()
    assert find_connected_verb(doc.tokens, 0) == "streams"
    assert find_connected_verb(doc.tokens, 2) == "streams"


def test_find_connected_verb_returns_none_without_verb():
    tokens = [
        _tok(0, "the", "DET", "det", 1, is_stop=True),
        _tok(1, "cat", "NOUN", "ROOT", 1, lemma="cat"),
    ]
    assert find_connected_verb(tokens, 1) is None


def test_find_connected_verb_child_fallback():
    # 'systems that scale' — root noun with a relative-clause verb child.
    tokens = [
        _tok(0, "systems", "NOUN", "ROOT", 0, lemma="system"),
        _tok(1, "that", "PRON", "nsubj", 2, is_stop=True),
        _tok(2, "scale", "VERB", "relcl", 0, lemma="scale"),
    ]
    assert find_connected_verb(tokens, 0) == "scale"


def test_find_connected_verb_out_of_range():
    assert find_connected_verb([], 0) is None
    assert find_connected_verb(_kafka_doc().tokens, 99) is None


# ---------------------------------------------------------------------------
# build_concept_candidates
# ---------------------------------------------------------------------------


def test_build_concept_candidates_priority_and_verb():
    doc = _kafka_doc()
    cands = build_concept_candidates(doc, OpenExtractionParams(tf_idf_threshold=0.0))
    by_lemma = {c.lemma: c for c in cands}
    assert set(by_lemma) == {"kafka", "event"}
    assert by_lemma["kafka"].priority == ConceptPriority.CRITICAL
    assert by_lemma["event"].priority == ConceptPriority.IMPORTANT
    assert by_lemma["kafka"].connected_verb == "streams"
    # Sorted by priority: CRITICAL first.
    assert cands[0].priority == ConceptPriority.CRITICAL


def test_build_concept_candidates_standalone_token():
    # 'Systems are scalable.' — 'scalable' is a predicate ADJ outside any chunk.
    tokens = [
        _tok(0, "Systems", "NOUN", "nsubj", 2, lemma="system"),
        _tok(1, "are", "AUX", "ROOT", 2, lemma="be", is_stop=True),
        _tok(2, "scalable", "ADJ", "acomp", 1, lemma="scalable"),
        _tok(3, ".", "PUNCT", "punct", 2, lemma=".", is_alpha=False),
    ]
    chunks = [_chunk("Systems", 0, 1, 0)]
    doc = OpenExtractionResult(
        tokens=tokens, noun_chunks=chunks, sentence_count=1, language="en"
    )
    cands = build_concept_candidates(doc, OpenExtractionParams(tf_idf_threshold=0.0))
    lemmas = {c.lemma for c in cands}
    assert "scalable" in lemmas  # standalone ADJ surfaced
    assert "system" in lemmas


def test_build_concept_candidates_prefilters_short_and_stopword_chunks():
    tokens = [
        _tok(0, "of", "ADP", "prep", 1, is_stop=True),
        _tok(1, "it", "PRON", "nsubj", 1, is_stop=True),
    ]
    # All-stopword chunk + a too-short chunk both get skipped.
    chunks = [_chunk("it", 1, 2, 1), _chunk("of", 0, 1, 0)]
    doc = OpenExtractionResult(
        tokens=tokens, noun_chunks=chunks, sentence_count=1, language="en"
    )
    cands = build_concept_candidates(
        doc, OpenExtractionParams(tf_idf_threshold=0.0, include_standalone=False)
    )
    assert cands == []


def test_critical_bypasses_threshold_others_filtered():
    # A CONTEXTUAL chunk with a frequency profile that scores below threshold is
    # dropped, while a CRITICAL chunk is kept regardless of score.
    tokens = [
        _tok(0, "system", "NOUN", "nsubj", 1, lemma="system"),
        _tok(1, "uses", "VERB", "ROOT", 1, lemma="use"),
        _tok(2, "cache", "NOUN", "compound", 3, lemma="cache"),
        _tok(3, "layer", "NOUN", "dobj", 1, lemma="layer"),
    ]
    chunks = [
        _chunk("system", 0, 1, 0),  # nsubj -> CRITICAL
        _chunk("cache", 2, 3, 2),  # compound -> CONTEXTUAL
    ]
    doc = OpenExtractionResult(
        tokens=tokens, noun_chunks=chunks, sentence_count=1, language="en"
    )
    # Very high threshold filters everything except CRITICAL.
    cands = build_concept_candidates(
        doc, OpenExtractionParams(tf_idf_threshold=999.0, include_standalone=False)
    )
    lemmas = {c.lemma for c in cands}
    assert "system" in lemmas
    assert "cache" not in lemmas


# ---------------------------------------------------------------------------
# build_relation_candidates
# ---------------------------------------------------------------------------


def test_build_relation_candidates_subject_verb_object():
    doc = _kafka_doc()
    rels = build_relation_candidates(doc)
    assert len(rels) == 1
    rel = rels[0]
    assert rel.subject == "Kafka"
    assert rel.predicate == "stream"  # verb lemma
    assert rel.object == "events"


def test_build_relation_candidates_prepositional_object():
    # 'Data flows through pipelines.' — pobj reached via the prep.
    tokens = [
        _tok(0, "Data", "PROPN", "nsubj", 1, lemma="data"),
        _tok(1, "flows", "VERB", "ROOT", 1, lemma="flow"),
        _tok(2, "through", "ADP", "prep", 1, lemma="through", is_stop=True),
        _tok(3, "pipelines", "NOUN", "pobj", 2, lemma="pipeline"),
        _tok(4, ".", "PUNCT", "punct", 1, lemma=".", is_alpha=False),
    ]
    chunks = [_chunk("Data", 0, 1, 0), _chunk("pipelines", 3, 4, 3)]
    doc = OpenExtractionResult(
        tokens=tokens, noun_chunks=chunks, sentence_count=1, language="en"
    )
    rels = build_relation_candidates(doc)
    assert len(rels) == 1
    assert rels[0].subject == "Data"
    assert rels[0].predicate == "flow"
    assert rels[0].object == "pipelines"


def test_build_relation_candidates_none_without_subject():
    # Verb with an object but no subject yields no relation.
    tokens = [
        _tok(0, "Run", "VERB", "ROOT", 0, lemma="run"),
        _tok(1, "tests", "NOUN", "dobj", 0, lemma="test"),
    ]
    doc = OpenExtractionResult(
        tokens=tokens, noun_chunks=[_chunk("tests", 1, 2, 1)], sentence_count=1, language="en"
    )
    assert build_relation_candidates(doc) == []


# ---------------------------------------------------------------------------
# select_cluster_representatives
# ---------------------------------------------------------------------------


def _cand(lemma, priority=ConceptPriority.CONTEXTUAL, score=0.5):
    return ConceptCandidate(
        text=lemma,
        lemma=lemma,
        priority=priority,
        score=score,
        root_index=0,
        sentence_index=0,
        connected_verb=None,
        start=0,
        end=len(lemma),
    )


def test_select_cluster_representatives_picks_best_per_cluster():
    candidates = [
        _cand("service", ConceptPriority.IMPORTANT, 0.4),
        _cand("services", ConceptPriority.CRITICAL, 0.3),  # same cluster, higher priority
        _cand("database", ConceptPriority.CONTEXTUAL, 0.9),
    ]
    assignments = [
        ClusterAssignment(0, 0),
        ClusterAssignment(1, 0),
        ClusterAssignment(2, 1),
    ]
    reps = select_cluster_representatives(candidates, assignments)
    lemmas = {r.lemma for r in reps}
    # Cluster 0 -> 'services' (CRITICAL beats IMPORTANT); cluster 1 -> 'database'.
    assert lemmas == {"services", "database"}
    # Sorted by priority: CRITICAL representative first.
    assert reps[0].lemma == "services"


def test_select_cluster_representatives_keeps_noise_individually():
    candidates = [_cand("alpha"), _cand("beta"), _cand("gamma")]
    assignments = [
        ClusterAssignment(0, -1),
        ClusterAssignment(1, -1),
        ClusterAssignment(2, 0),
    ]
    reps = select_cluster_representatives(candidates, assignments)
    assert {r.lemma for r in reps} == {"alpha", "beta", "gamma"}


def test_select_cluster_representatives_empty():
    assert select_cluster_representatives([], []) == []


def test_select_cluster_representatives_length_mismatch_raises():
    import pytest

    with pytest.raises(ValueError):
        select_cluster_representatives([_cand("a")], [])


# ---------------------------------------------------------------------------
# Coverage completion: unconsumed noun chunks + wider dependency capture
# ---------------------------------------------------------------------------


def _conjunct_doc():
    """'The technician navigates routes and jobs.' — object conjunct fan-out."""
    tokens = [
        _tok(0, "The", "DET", "det", 1, lemma="the", is_stop=True),
        _tok(1, "technician", "NOUN", "nsubj", 2, lemma="technician"),
        _tok(2, "navigates", "VERB", "ROOT", 2, lemma="navigate"),
        _tok(3, "routes", "NOUN", "dobj", 2, lemma="route"),
        _tok(4, "and", "CCONJ", "cc", 3, lemma="and", is_stop=True),
        _tok(5, "jobs", "NOUN", "conj", 3, lemma="job"),
        _tok(6, ".", "PUNCT", "punct", 2, lemma=".", is_alpha=False),
    ]
    chunks = [
        _chunk("The technician", 0, 2, 1),
        _chunk("routes", 3, 4, 3),
        _chunk("jobs", 5, 6, 5),
    ]
    return OpenExtractionResult(
        tokens=tokens, noun_chunks=chunks, sentence_count=1, language="en"
    )


def _passive_agent_doc():
    """'The route is navigated by the technician.' — passive agent."""
    tokens = [
        _tok(0, "The", "DET", "det", 1, lemma="the", is_stop=True),
        _tok(1, "route", "NOUN", "nsubjpass", 3, lemma="route"),
        _tok(2, "is", "AUX", "auxpass", 3, lemma="be", is_stop=True),
        _tok(3, "navigated", "VERB", "ROOT", 3, lemma="navigate"),
        _tok(4, "by", "ADP", "agent", 3, lemma="by", is_stop=True),
        _tok(5, "the", "DET", "det", 6, lemma="the", is_stop=True),
        _tok(6, "technician", "NOUN", "pobj", 4, lemma="technician"),
        _tok(7, ".", "PUNCT", "punct", 3, lemma=".", is_alpha=False),
    ]
    chunks = [_chunk("The route", 0, 2, 1), _chunk("the technician", 5, 7, 6)]
    return OpenExtractionResult(
        tokens=tokens, noun_chunks=chunks, sentence_count=1, language="en"
    )


def _xcomp_doc():
    """'Users want to navigate routes.' — xcomp control complement."""
    tokens = [
        _tok(0, "Users", "NOUN", "nsubj", 1, lemma="user"),
        _tok(1, "want", "VERB", "ROOT", 1, lemma="want"),
        _tok(2, "to", "PART", "aux", 3, lemma="to", is_stop=True),
        _tok(3, "navigate", "VERB", "xcomp", 1, lemma="navigate"),
        _tok(4, "routes", "NOUN", "dobj", 3, lemma="route"),
        _tok(5, ".", "PUNCT", "punct", 1, lemma=".", is_alpha=False),
    ]
    chunks = [_chunk("Users", 0, 1, 0), _chunk("routes", 4, 5, 4)]
    return OpenExtractionResult(
        tokens=tokens, noun_chunks=chunks, sentence_count=1, language="en"
    )


def test_unconsumed_noun_chunk_heads_reports_only_unconsumed():
    doc = _conjunct_doc()
    relations = build_relation_candidates(doc)
    heads = unconsumed_noun_chunk_heads(doc, relations)
    # 'The technician' (subject) and 'routes' (object) are consumed by the SVO
    # relation; only 'jobs' remains uncovered.
    assert heads == [(5, "jobs")]


def test_wider_capture_fans_out_object_conjunct():
    doc = _conjunct_doc()
    relations = build_relation_candidates(doc)
    wider = build_wider_relation_candidates(doc, relations)
    pairs = {(r.subject_index, r.object_index) for r in wider}
    # technician --navigate--> jobs (the conjunct), pairing the new entity with
    # the existing subject.
    assert (1, 5) in pairs
    fanned = next(r for r in wider if r.object_index == 5)
    assert fanned.predicate == "navigate"
    assert fanned.object == "jobs"
    assert fanned.subject == "The technician"


def test_wider_capture_passive_agent():
    doc = _passive_agent_doc()
    relations = build_relation_candidates(doc)
    # The passive with no direct object yields no SVO relation at all.
    assert relations == []
    wider = build_wider_relation_candidates(doc, relations)
    # technician (agent) --navigate--> route (passive subject).
    assert len(wider) == 1
    rel = wider[0]
    assert rel.subject_index == 6 and rel.object_index == 1
    assert rel.predicate == "navigate"


def test_wider_capture_xcomp_control_complement():
    doc = _xcomp_doc()
    relations = build_relation_candidates(doc)
    wider = build_wider_relation_candidates(doc, relations)
    # The matrix subject 'Users' controls 'navigate', pairing with its object.
    pairs = {(r.subject, r.predicate, r.object) for r in wider}
    assert ("Users", "navigate", "routes") in pairs


def test_wider_capture_restrict_to_heads_filters():
    doc = _conjunct_doc()
    relations = build_relation_candidates(doc)
    # Restricting to a head not touched by any wider relation yields nothing.
    assert build_wider_relation_candidates(doc, relations, restrict_to_heads=frozenset()) == []
    # Restricting to the 'jobs' root keeps the fan-out relation.
    kept = build_wider_relation_candidates(doc, relations, restrict_to_heads=frozenset({5}))
    assert [(r.subject_index, r.object_index) for r in kept] == [(1, 5)]


def test_wider_capture_dedups_and_drops_self_referential():
    doc = _conjunct_doc()
    relations = build_relation_candidates(doc)
    wider = build_wider_relation_candidates(doc, relations)
    keys = [(r.subject_index, r.verb_index, r.object_index) for r in wider]
    assert len(keys) == len(set(keys))
    assert all(r.subject_index != r.object_index for r in wider)
