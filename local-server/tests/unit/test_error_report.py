"""Unit tests for the missed-triple failure-stage classifier and report writer (§3.2)."""

import json

from tests.integration.pipelines._harness.error_report import (
    CANDIDATE_MISSING,
    LABEL_MISMATCH,
    PREDICATE_MISMATCH,
    RELATION_NOT_DERIVED,
    ScenarioReport,
    build_missed_triples,
    classify_stage,
    find_source_sentence,
    generate_run_id,
    write_report,
)


class TestClassifyStage:
    """Tests for the four-stage failure waterfall."""

    def test_candidate_missing(self):
        stage, nearest = classify_stage(("x", "p", "y"), [("a", "q", "b")])
        assert stage == CANDIDATE_MISSING
        assert nearest is None

    def test_relation_not_derived(self):
        """Both entities appear somewhere, but never paired together."""
        stage, nearest = classify_stage(
            ("a", "p", "b"), [("a", "q", "c"), ("d", "r", "b")]
        )
        assert stage == RELATION_NOT_DERIVED
        assert nearest is None

    def test_label_mismatch(self):
        """A relation was derived between normalized-matching endpoints, exact labels differ."""
        stage, nearest = classify_stage(("a", "p", "improves"), [("a", "q", "improve")])
        assert stage == LABEL_MISMATCH
        assert nearest == ("a", "q", "improve")

    def test_predicate_mismatch(self):
        """Endpoint labels match exactly; only the predicate differs."""
        stage, nearest = classify_stage(("a", "causes", "b"), [("a", "enables", "b")])
        assert stage == PREDICATE_MISMATCH
        assert nearest == ("a", "enables", "b")

    def test_empty_actual_is_candidate_missing(self):
        stage, nearest = classify_stage(("a", "p", "b"), [])
        assert stage == CANDIDATE_MISSING
        assert nearest is None

    def test_embedding_tier_match_is_not_candidate_missing(self):
        """
        A subject present only via the fallback bag-of-stems embedding proxy
        (>= 0.85 cosine, tier 0.7 — not lemma/stem-equal) must not be
        classified candidate_missing: candidate_recall already counts it as
        present, and the two diagnostics must agree on what "present" means.
        """
        stage, nearest = classify_stage(
            ("quick_brown_fox", "p", "b"), [("quick_brown_fox_jumps", "q", "b")]
        )
        assert stage == LABEL_MISMATCH
        assert nearest == ("quick_brown_fox_jumps", "q", "b")

    def test_custom_embed_fn_is_threaded_through(self):
        """An injected embed_fn (not just the stdlib fallback) affects classification."""
        vectors = {"a": [1.0, 0.0], "b": [1.0, 0.0], "x": [0.0, 1.0]}
        stage, _ = classify_stage(
            ("a", "p", "x"), [("b", "q", "x")], embed_fn=lambda label: vectors[label]
        )
        assert stage == LABEL_MISMATCH


class TestFindSourceSentence:
    """Tests for the sentence-lookup heuristic."""

    def test_finds_sentence_mentioning_subject_or_object(self):
        text = "Alpha creates Beta. Gamma manages Delta."
        sentence = find_source_sentence(text, ("Alpha", "creates", "Beta"))
        assert sentence == "Alpha creates Beta."

    def test_no_match_returns_empty_string(self):
        text = "Alpha creates Beta. Gamma manages Delta."
        sentence = find_source_sentence(text, ("Zzyzx", "relates", "Omega"))
        assert sentence == ""

    def test_empty_text_returns_empty_string(self):
        assert find_source_sentence("", ("Alpha", "creates", "Beta")) == ""


class TestBuildMissedTriples:
    """Tests for the per-scenario missed-triple report builder."""

    def test_only_strict_misses_are_reported(self):
        expected = [("a", "p", "b"), ("c", "q", "d")]
        actual = [("a", "p", "b")]  # first triple is an exact strict match
        missed = build_missed_triples("some source text", expected, actual)
        assert len(missed) == 1
        assert missed[0].expected == ("c", "q", "d")

    def test_no_misses_when_everything_matches(self):
        expected = [("a", "p", "b")]
        missed = build_missed_triples("text", expected, expected)
        assert missed == []


class TestWriteReport:
    """Tests for the JSON + markdown report writer."""

    def _sample_report(self, scenario: str, split: str, strict_f1: float, soft_f1: float):
        return ScenarioReport(
            scenario=scenario,
            split=split,
            strict={"precision": strict_f1, "recall": strict_f1, "f1": strict_f1},
            soft={"precision": soft_f1, "recall": soft_f1, "f1": soft_f1},
            candidate_recall=0.5,
            predicate_recall=0.4,
            label_accuracy={"strict": 0.3, "soft": 0.6, "derived_count": 2},
            missed_triples=build_missed_triples(
                "Alpha never relates to Beta.", [("Alpha", "relates_to", "Beta")], []
            ),
        )

    def test_writes_json_and_markdown(self, tmp_path):
        reports = [
            self._sample_report("scenario_a", "dev", 0.2, 0.5),
            self._sample_report("scenario_b", "holdout", 0.1, 0.3),
        ]
        run_id = generate_run_id()
        json_path, markdown_path = write_report(run_id, reports, tmp_path)

        assert json_path.exists()
        assert markdown_path.exists()

        payload = json.loads(json_path.read_text())
        assert payload["run_id"] == run_id
        assert set(payload["scenarios"]) == {"scenario_a", "scenario_b"}
        assert payload["dev_mean"]["strict_f1"] == 0.2
        assert payload["holdout_mean"]["strict_f1"] == 0.1
        assert payload["failure_stage_counts"]

        digest = markdown_path.read_text()
        assert "Top failure classes" in digest
        assert "scenario_a" in digest or "scenario_b" in digest

    def test_run_ids_are_unique(self):
        assert generate_run_id() != generate_run_id()
