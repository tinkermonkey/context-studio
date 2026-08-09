"""
Unit tests for CascadeIndividualRecognizer.

Infra-free: a fake IndividualVectorIndex + embedding service (deterministic
text->vector map) and a fake LLM provider exercise the exact/vector/LLM-tiebreak
cascade without a DB, embedding model, or live LLM call.
"""

import json

import pytest

from adapters.recognition.individual_recognizer import CascadeIndividualRecognizer
from tests.fakes.fake_individual_vector_index import FakeIndividualVectorIndex
from tests.fakes.fake_llm_provider import FakeLLMProvider

CLASS_SW = "cls-systemsoftware"
CLASS_DB = "cls-datastore"

# Deterministic text->vector map shared by the query mention and the index's
# stored titles, so cosine similarity between any pair is known ahead of time.
_VEC = {
    "K8s": [1.0, 0.0, 0.0],
    "kubernetes": [1.0, 0.0, 0.0],  # exact-match casing test query
    "Kubernetes": [0.96, 0.28, 0.0],  # cos(K8s, Kubernetes) = 0.96 -> clear winner
    "Nextflow": [0.90, 0.4359, 0.0],  # cos(K8s, Nextflow) = 0.90 -> qualifies, not tied (gap 0.06)
    "Ambiguous Mention": [1.0, 0.0, 0.0],
    "Docker Swarm": [0.97, 0.2431, 0.0],  # cos(Ambiguous Mention, .) = 0.97
    "OpenShift": [0.95, 0.3122, 0.0],  # cos = 0.95 -> tied with Docker Swarm (gap 0.02)
    "Something Else": [1.0, 0.0, 0.0],
    "Unrelated Thing": [0.30, 0.9539, 0.0],  # cos = 0.30 -> below default threshold
}


class _VectorEmbedding:
    """Deterministic text->vector fake embedding service."""

    def __init__(self, vectors):
        self._vectors = vectors

    def embed(self, text):
        return self._vectors.get(text, [0.0, 0.0, 0.0])

    def embed_batch(self, texts):
        return [self.embed(t) for t in texts]


def _index_with_kubernetes_and_nextflow():
    # Scoped to the "K8s" query only -> cos 0.96 / 0.90 respectively.
    idx = FakeIndividualVectorIndex(_VEC)
    idx.add("kube-id", "Kubernetes", [CLASS_SW])
    idx.add("nextflow-id", "Nextflow", [CLASS_SW])
    return idx


def _index_with_ambiguous_candidates():
    # Scoped to the "Ambiguous Mention" query only -> cos 0.97 / 0.95, tied.
    idx = FakeIndividualVectorIndex(_VEC)
    idx.add("swarm-id", "Docker Swarm", [CLASS_SW])
    idx.add("openshift-id", "OpenShift", [CLASS_SW])
    return idx


def _index_with_unrelated_candidate():
    # Scoped to the "Something Else" query only -> cos 0.30.
    idx = FakeIndividualVectorIndex(_VEC)
    idx.add("unrelated-id", "Unrelated Thing", [CLASS_SW])
    return idx


def _recognizer(index, llm=None, **kwargs):
    return CascadeIndividualRecognizer(
        individual_index=index,
        embedding_service=_VectorEmbedding(_VEC),
        llm=llm,
        **kwargs,
    )


class TestConstructorValidation:
    def test_non_positive_top_k_raises(self):
        with pytest.raises(ValueError):
            _recognizer(_index_with_kubernetes_and_nextflow(), top_k=0)

        with pytest.raises(ValueError):
            _recognizer(_index_with_kubernetes_and_nextflow(), top_k=-1)


class TestExactMatch:
    def test_exact_label_resolves_immediately(self):
        recognizer = _recognizer(_index_with_kubernetes_and_nextflow())
        match = recognizer.recognize("kubernetes", context="", class_ids=[CLASS_SW])
        assert match.individual_id == "kube-id"
        assert match.title == "Kubernetes"
        assert match.score == 1.0
        assert match.method == "exact"


class TestClearVectorWinner:
    def test_single_clear_winner_returns_immediately(self):
        recognizer = _recognizer(_index_with_kubernetes_and_nextflow())
        match = recognizer.recognize("K8s", context="", class_ids=[CLASS_SW])
        assert match.individual_id == "kube-id"
        assert match.score == 0.96
        assert match.method == "vector"

    def test_below_threshold_yields_no_match(self):
        recognizer = _recognizer(_index_with_unrelated_candidate())
        match = recognizer.recognize("Something Else", context="", class_ids=[CLASS_SW])
        assert match is None

    def test_no_candidates_in_scope_yields_no_match(self):
        recognizer = _recognizer(_index_with_kubernetes_and_nextflow())
        match = recognizer.recognize("K8s", context="", class_ids=[CLASS_DB])
        assert match is None

    def test_threshold_is_independently_configurable(self):
        # The default 0.90 threshold resolves "K8s" (score 0.96); a stricter,
        # independently-configured 0.97 threshold on the same fixture refuses.
        strict = _recognizer(_index_with_kubernetes_and_nextflow(), threshold=0.97)
        assert strict.recognize("K8s", context="", class_ids=[CLASS_SW]) is None

        lenient = _recognizer(_index_with_kubernetes_and_nextflow(), threshold=0.90)
        assert lenient.recognize("K8s", context="", class_ids=[CLASS_SW]) is not None

    def test_per_call_threshold_overrides_the_configured_default(self):
        recognizer = _recognizer(_index_with_kubernetes_and_nextflow(), threshold=0.90)
        match = recognizer.recognize("K8s", context="", class_ids=[CLASS_SW], threshold=0.99)
        assert match is None


class TestLLMTiebreak:
    def test_ambiguous_match_resolved_by_llm(self):
        llm = FakeLLMProvider(response_content=json.dumps({"individual_id": "swarm-id"}))
        recognizer = _recognizer(_index_with_ambiguous_candidates(), llm=llm)
        match = recognizer.recognize(
            "Ambiguous Mention", context="a container platform", class_ids=[CLASS_SW]
        )
        assert match.individual_id == "swarm-id"
        assert match.method == "llm"
        assert llm.call_count == 1

    def test_llm_may_decide_neither_candidate_matches(self):
        llm = FakeLLMProvider(response_content=json.dumps({"individual_id": "none"}))
        recognizer = _recognizer(_index_with_ambiguous_candidates(), llm=llm)
        match = recognizer.recognize("Ambiguous Mention", context="", class_ids=[CLASS_SW])
        assert match is None

    def test_ambiguous_match_with_no_llm_available_falls_back_to_top_candidate(self):
        recognizer = _recognizer(_index_with_ambiguous_candidates(), llm=None)
        match = recognizer.recognize("Ambiguous Mention", context="", class_ids=[CLASS_SW])
        assert match.individual_id == "swarm-id"  # highest-scoring of the tied pair
        assert match.method == "vector"

    def test_unparseable_llm_response_falls_back_to_top_candidate(self):
        llm = FakeLLMProvider(response_content="not valid json")
        recognizer = _recognizer(_index_with_ambiguous_candidates(), llm=llm)
        match = recognizer.recognize("Ambiguous Mention", context="", class_ids=[CLASS_SW])
        assert match.individual_id == "swarm-id"
        # The LLM didn't confirm this pick — a malformed response must not be
        # tagged "llm" in the provenance audit trail.
        assert match.method == "vector"

    def test_llm_choosing_an_id_outside_the_tied_set_falls_back_to_top_candidate(self):
        llm = FakeLLMProvider(response_content=json.dumps({"individual_id": "not-a-candidate"}))
        recognizer = _recognizer(_index_with_ambiguous_candidates(), llm=llm)
        match = recognizer.recognize("Ambiguous Mention", context="", class_ids=[CLASS_SW])
        assert match.individual_id == "swarm-id"
        assert match.method == "vector"

    def test_llm_call_failure_falls_back_to_top_candidate_instead_of_propagating(self):
        llm = FakeLLMProvider(should_fail=True)
        recognizer = _recognizer(_index_with_ambiguous_candidates(), llm=llm)
        match = recognizer.recognize("Ambiguous Mention", context="", class_ids=[CLASS_SW])
        assert match.individual_id == "swarm-id"
        assert match.method == "vector"

    def test_programming_bug_in_llm_call_propagates_instead_of_falling_back(self):
        class _BrokenLLMProvider(FakeLLMProvider):
            def complete(self, *args, **kwargs):
                raise TypeError("boom")

        recognizer = _recognizer(_index_with_ambiguous_candidates(), llm=_BrokenLLMProvider())
        with pytest.raises(TypeError):
            recognizer.recognize("Ambiguous Mention", context="", class_ids=[CLASS_SW])

    def test_tiebreak_prompt_includes_description_and_class_membership(self):
        llm = FakeLLMProvider(response_content=json.dumps({"individual_id": "swarm-id"}))
        idx = FakeIndividualVectorIndex(_VEC)
        idx.add("swarm-id", "Docker Swarm", [CLASS_SW], description="A container orchestrator.")
        idx.add("openshift-id", "OpenShift", [CLASS_SW], description="A Kubernetes distribution.")
        recognizer = _recognizer(idx, llm=llm)
        recognizer.recognize(
            "Ambiguous Mention", context="a container platform", class_ids=[CLASS_SW]
        )

        prompt = llm.last_call_args["user_prompt"]
        assert "A container orchestrator." in prompt
        assert "A Kubernetes distribution." in prompt
        assert CLASS_SW in prompt


class TestNoMatchFound:
    def test_empty_index_yields_no_match(self):
        recognizer = _recognizer(FakeIndividualVectorIndex(_VEC))
        match = recognizer.recognize("K8s", context="", class_ids=[CLASS_SW])
        assert match is None

    def test_blank_label_yields_no_match(self):
        recognizer = _recognizer(_index_with_kubernetes_and_nextflow())
        match = recognizer.recognize("   ", context="", class_ids=[CLASS_SW])
        assert match is None
