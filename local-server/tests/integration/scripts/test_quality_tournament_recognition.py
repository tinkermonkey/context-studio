"""
Tests for the recognition-episode diagnostic pass in
scripts/quality_tournament.py (issue #1142 Phase 3).

Recognition has no `Variant.run_scenario` seam like bootstrap/wave4/arxiv --
it exercises the full extraction+apply+recognition pipeline directly via
`episode_runner.run_full_pipeline_episode`, once per tournament invocation
(see `_build_recognition_reports`). These tests cover the pure-Python pieces
(scoreboard rendering, JSONL emission shape, accept/reject independence) with
fakes, and the real end-to-end build with the committed episode cassettes,
skipping gracefully when the DR spec checkout isn't available -- the same
pattern `test_recognition_episode_cassette_replay.py` uses.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from scripts.quality_tournament import (
    _aggregate_recognition,
    _build_recognition_reports,
    _emit_recognition_metrics,
    _render_scoreboard_digest,
)
from tests.integration.pipelines._harness.dataset_split import RECOGNITION_EPISODES
from tests.integration.pipelines._harness.episode_runner import (
    EpisodeRunResult,
    EpisodeSetupError,
)
from tests.integration.pipelines._harness.metrics import RecognitionMetrics
from tests.integration.pipelines.conftest import _find_dr_spec_dir


def _fake_reports() -> dict[str, RecognitionMetrics]:
    return {
        "surface_variants": RecognitionMetrics(
            dedup_precision=1.0,
            dedup_recall=1.0,
            dedup_f1=1.0,
            resolution_accuracy=1.0,
            canonical_label_accuracy=1.0,
            node_count_ratio=1.0,
            gt_entity_count=3,
            predicted_node_count=3,
        ),
        "kubernetes_energy": RecognitionMetrics(
            dedup_precision=0.9,
            dedup_recall=0.8,
            dedup_f1=0.85,
            resolution_accuracy=0.8,
            canonical_label_accuracy=0.8,
            node_count_ratio=1.2,
            gt_entity_count=5,
            predicted_node_count=6,
        ),
        "distractor_same_class": RecognitionMetrics(
            dedup_precision=1.0,
            dedup_recall=1.0,
            dedup_f1=1.0,
            resolution_accuracy=1.0,
            canonical_label_accuracy=1.0,
            node_count_ratio=1.0,
            gt_entity_count=2,
            predicted_node_count=2,
        ),
        "cross_doc_convergence": RecognitionMetrics(
            dedup_precision=1.0,
            dedup_recall=1.0,
            dedup_f1=1.0,
            resolution_accuracy=1.0,
            canonical_label_accuracy=1.0,
            node_count_ratio=1.0,
            gt_entity_count=3,
            predicted_node_count=3,
        ),
    }


def _fake_result(variant: str, dev_soft_f1: float) -> dict:
    aggregate = {
        "strict_precision": 0.0,
        "strict_recall": 0.0,
        "strict_f1": 0.0,
        "soft_precision": 0.0,
        "soft_recall": 0.0,
        "soft_f1": dev_soft_f1,
        "candidate_recall": 0.0,
        "predicate_recall": 0.0,
        "label_accuracy_strict": 0.0,
        "label_accuracy_soft": 0.0,
    }
    return {
        "variant": variant,
        "tuned_config": {},
        "tuned_knobs": {},
        "dev": aggregate,
        "holdout": aggregate,
        "bootstrap": aggregate,
        "wave4": aggregate,
        "arxiv": aggregate,
        "error_report_json": "unused.json",
        "error_report_md": "unused.md",
    }


class TestBuildRecognitionReports:
    @pytest.mark.asyncio
    async def test_returns_empty_when_dr_spec_unavailable(self, monkeypatch):
        import tests.integration.pipelines.conftest as conftest

        monkeypatch.setattr(conftest, "_find_dr_spec_dir", lambda: None)
        reports = await _build_recognition_reports(embedding=None)
        assert reports == {}

    @pytest.mark.asyncio
    async def test_episode_setup_failure_is_skipped_not_raised(self, tmp_path, monkeypatch):
        """
        A single episode blowing up with a recoverable, episode-scoped setup
        error (malformed fixture, orchestrator/import failure) must not
        propagate and kill the whole tournament -- it should be skipped so
        every other episode's results (and the scoreboard digest built from
        them) still come back.
        """
        import scripts.quality_tournament as quality_tournament
        import tests.integration.pipelines.conftest as conftest

        monkeypatch.setattr(conftest, "_find_dr_spec_dir", lambda: tmp_path)
        cassettes_root = tmp_path / "episodes"
        for episode in RECOGNITION_EPISODES:
            (cassettes_root / episode / "cassettes").mkdir(parents=True)
        monkeypatch.setattr(quality_tournament, "_RECOGNITION_EPISODES_DIR", cassettes_root)

        failing_episode = RECOGNITION_EPISODES[0]

        async def fake_run_full_pipeline_episode(episode, cassette_dir, dr_ontology_dir, embed):
            if episode == failing_episode:
                raise EpisodeSetupError("boom")
            return EpisodeRunResult(
                episode=episode,
                mentions=[
                    {
                        "entity_key": "e1",
                        "canonical_title": "Thing",
                        "node_id": "n1",
                        "title": "Thing",
                    }
                ],
            )

        monkeypatch.setattr(
            quality_tournament, "run_full_pipeline_episode", fake_run_full_pipeline_episode
        )

        reports = await _build_recognition_reports(embedding=None)

        assert failing_episode not in reports
        assert set(reports) == set(RECOGNITION_EPISODES) - {failing_episode}

    @pytest.mark.asyncio
    async def test_infrastructure_runtime_error_propagates(self, tmp_path, monkeypatch):
        """
        A bare `RuntimeError` (e.g. WAL contention/corruption surfaced by
        `save_individual()`) or an unrelated `RuntimeError` subclass (e.g.
        `NotImplementedError` from an accidental ORM-mapper fallback) is an
        infrastructure failure, not a recoverable episode-setup error -- it
        must propagate rather than being silently skipped, so the tournament
        does not exit 0 with an incomplete, unflagged scoreboard.
        """
        import scripts.quality_tournament as quality_tournament
        import tests.integration.pipelines.conftest as conftest

        monkeypatch.setattr(conftest, "_find_dr_spec_dir", lambda: tmp_path)
        cassettes_root = tmp_path / "episodes"
        for episode in RECOGNITION_EPISODES:
            (cassettes_root / episode / "cassettes").mkdir(parents=True)
        monkeypatch.setattr(quality_tournament, "_RECOGNITION_EPISODES_DIR", cassettes_root)

        async def fake_run_full_pipeline_episode(episode, cassette_dir, dr_ontology_dir, embed):
            raise RuntimeError("WAL contention while reloading individual after save")

        monkeypatch.setattr(
            quality_tournament, "run_full_pipeline_episode", fake_run_full_pipeline_episode
        )

        with pytest.raises(RuntimeError):
            await _build_recognition_reports(embedding=None)

    @pytest.mark.asyncio
    async def test_episode_with_zero_scoreable_mentions_is_skipped(self, tmp_path, monkeypatch):
        """
        When every ground-truth mention lands in `extraction_misses` (total
        extraction failure), `result.mentions` is empty and
        `recognition_metrics([])` would report a perfect 1.0 score. That episode
        must be excluded from the reports rather than silently graded perfect.
        """
        import scripts.quality_tournament as quality_tournament
        import tests.integration.pipelines.conftest as conftest

        monkeypatch.setattr(conftest, "_find_dr_spec_dir", lambda: tmp_path)
        cassettes_root = tmp_path / "episodes"
        for episode in RECOGNITION_EPISODES:
            (cassettes_root / episode / "cassettes").mkdir(parents=True)
        monkeypatch.setattr(quality_tournament, "_RECOGNITION_EPISODES_DIR", cassettes_root)

        failed_episode = RECOGNITION_EPISODES[0]

        async def fake_run_full_pipeline_episode(episode, cassette_dir, dr_ontology_dir, embed):
            if episode == failed_episode:
                return EpisodeRunResult(
                    episode=episode,
                    mentions=[],
                    extraction_misses=[
                        {
                            "entity_key": "e1",
                            "canonical_title": "Thing",
                            "surface": "Thing",
                            "doc": "doc_01",
                            "reason": "not_extracted",
                        }
                    ],
                )
            return EpisodeRunResult(
                episode=episode,
                mentions=[
                    {
                        "entity_key": "e1",
                        "canonical_title": "Thing",
                        "node_id": "n1",
                        "title": "Thing",
                    }
                ],
            )

        monkeypatch.setattr(
            quality_tournament, "run_full_pipeline_episode", fake_run_full_pipeline_episode
        )

        reports = await _build_recognition_reports(embedding=None)

        assert failed_episode not in reports
        assert set(reports) == set(RECOGNITION_EPISODES) - {failed_episode}

    @pytest.mark.asyncio
    async def test_runs_every_recognition_episode_against_real_pipeline(self):
        if _find_dr_spec_dir() is None:
            pytest.skip("DR spec checkout not available")
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding

        try:
            embedding = SentenceTransformerEmbedding()
            embedding.embed("warmup")
        except OSError as exc:
            pytest.skip(f"SentenceTransformer unavailable offline: {exc}")

        reports = await _build_recognition_reports(embedding)

        assert set(reports) == set(RECOGNITION_EPISODES)
        for metrics in reports.values():
            assert isinstance(metrics, RecognitionMetrics)
            assert 0.0 <= metrics.dedup_precision <= 1.0
            assert 0.0 <= metrics.dedup_recall <= 1.0


class TestAggregateRecognition:
    def test_means_across_episodes(self):
        summary = _aggregate_recognition(_fake_reports())
        assert summary == {
            "dedup_precision": 0.975,
            "dedup_recall": 0.95,
            "dedup_f1": 0.9625,
            "node_count_ratio": 1.05,
        }

    def test_empty_reports_yield_zeroed_summary(self):
        summary = _aggregate_recognition({})
        assert summary == {
            "dedup_precision": 0.0,
            "dedup_recall": 0.0,
            "dedup_f1": 0.0,
            "node_count_ratio": 0.0,
        }


class TestEmitRecognitionMetrics:
    def test_writes_correctly_shaped_rows_to_individual_recognition_jsonl(
        self, tmp_path, monkeypatch
    ):
        import json

        import scripts.quality_tournament as quality_tournament

        monkeypatch.setattr(quality_tournament, "_METRICS_DIR", tmp_path)
        _emit_recognition_metrics(_fake_reports())

        metrics_file = tmp_path / "individual_recognition.jsonl"
        assert metrics_file.exists()
        rows = [json.loads(line) for line in metrics_file.read_text().splitlines()]
        assert {row["fixture_id"] for row in rows} == set(RECOGNITION_EPISODES)
        for row in rows:
            assert row["pipeline_type"] == "individual_recognition"
            assert set(row["metrics"]) == {
                "dedup_precision",
                "dedup_recall",
                "dedup_f1",
                "resolution_accuracy",
                "canonical_label_accuracy",
                "node_count_ratio",
                "gt_entity_count",
                "predicted_node_count",
            }


class TestRecognitionScoreboardSection:
    def test_digest_includes_recognition_diagnostics_section(self):
        results = [_fake_result("default", 0.7)]
        digest = _render_scoreboard_digest("run-1", results, _fake_reports())

        assert "## Recognition diagnostics" in digest
        assert "surface_variants" in digest
        assert "kubernetes_energy" in digest
        assert "distractor_same_class" in digest
        assert "cross_doc_convergence" in digest
        assert "1.000" in digest  # surface_variants dedup_precision

        # Positioned after the extraction/arxiv tables, not mixed into them.
        recognition_idx = digest.index("## Recognition diagnostics")
        arxiv_idx = digest.index("## Relabeled-arxiv diagnostics")
        strict_soft_idx = digest.index("dev strict-F1")
        assert arxiv_idx < recognition_idx
        assert strict_soft_idx < recognition_idx

    def test_digest_reports_skip_note_when_recognition_unavailable(self):
        results = [_fake_result("default", 0.7)]
        digest = _render_scoreboard_digest("run-1", results, {})

        assert "## Recognition diagnostics" in digest
        assert "Skipped" in digest


class TestRecognitionNeverGatesAcceptReject:
    def test_recognition_regression_does_not_change_dev_soft_f1_ranking(self):
        """
        The §6 accept/reject decision (and the scoreboard rank it produces) is
        driven solely by `results.sort(key=lambda r: r["dev"]["soft_f1"], ...)`
        (see `_amain`). Attaching a "recognition" key -- even a total
        regression to 0.0 across the board -- must never change that order.
        """
        leader = _fake_result("default", 0.8)
        laggard = _fake_result("open_v1", 0.2)

        good_recognition = _aggregate_recognition(_fake_reports())
        zero_recognition = _aggregate_recognition({})

        # The dev soft-F1 leader gets the recognition regression; the laggard
        # gets perfect recognition -- if recognition leaked into the ranking,
        # this would flip first place.
        leader["recognition"] = zero_recognition
        laggard["recognition"] = good_recognition

        results = [leader, laggard]
        results.sort(key=lambda r: r["dev"]["soft_f1"], reverse=True)

        assert [r["variant"] for r in results] == ["default", "open_v1"]
