"""
Level 2 (full-pipeline) cassette replay for the individual-recognition
episodes (issue #1142 Phase 2).

Replays the committed per-document cassettes recorded by
``scripts/record_recognition_episode_cassettes.py`` through
``run_full_pipeline_episode`` (real LLM extraction via ``CassetteLLMProvider``,
real embeddings) and compares the resulting recognition metrics against the
existing Level 1 (GT-mention-only) results asserted in
``test_individual_recognition_episode.py``, per ADR-2's two-level design.

Also verifies ADR-1 (Cassette Determinism Under Accumulating Graph State):
a document's pass-1 prompt -- and therefore its cassette hash key -- does not
depend on individuals already materialized in the graph by prior documents.
"""

import os
import sys
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.connection import (
    create_local_db_engine,
    create_session_factory,
)
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.extraction.services import ExtractionService
from domain.ontology.entities import Individual
from domain.ontology.services import OntologyService
from scripts.dr_ontology_loader import DR_TAXONOMY_IDENTIFIER, import_dr_ontology
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.integration.pipelines._harness.cassettes import _compute_prompt_hash
from tests.integration.pipelines._harness.dataset_split import RECOGNITION_EPISODES
from tests.integration.pipelines._harness.episode_runner import (
    run_full_pipeline_episode,
)
from tests.integration.pipelines._harness.metrics import (
    entity_key_clusters,
    recognition_metrics,
)
from tests.integration.pipelines.conftest import _find_dr_spec_dir

_EPISODES = Path(__file__).parent.parent / "fixtures" / "pipelines" / "individual_recognition"


@pytest.fixture(scope="module")
def dr_ontology_dir() -> Path:
    spec_dir = _find_dr_spec_dir()
    if spec_dir is None:
        pytest.skip("DR spec checkout not available")
    assert spec_dir is not None
    return spec_dir


@pytest.fixture(scope="module")
def real_embedding_service():
    """Real (offline, cached) embeddings -- matches the Level 1 harness, so
    Level 1 and Level 2 recognition run under identical embedding conditions."""
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding

    try:
        emb = SentenceTransformerEmbedding()
        emb.embed("warmup")
    except OSError as exc:
        pytest.skip(f"SentenceTransformer unavailable offline: {exc}")
    return emb


class TestCassetteReplayAgainstLevel1:
    @pytest.mark.asyncio
    async def test_surface_variants_replay_matches_level1(
        self, dr_ontology_dir, real_embedding_service
    ):
        """Level 2 (full pipeline, real cassettes) reproduces Level 1's perfect
        surface-variant dedup: every casing/pluralization variant merges, no
        false merges (test_recognition_solves_surface_variants: precision=1.0,
        recall=1.0, node_count_ratio=1.0)."""
        cassette_dir = _EPISODES / "surface_variants" / "cassettes"
        result = await run_full_pipeline_episode(
            "surface_variants", cassette_dir, dr_ontology_dir, real_embedding_service
        )
        assert not result.extraction_misses

        metrics = recognition_metrics(result.mentions)
        print(f"\n── Level 2 recognition (surface_variants) ── {metrics}")

        assert metrics.dedup_precision == 1.0
        assert metrics.dedup_recall == 1.0
        assert metrics.node_count_ratio == 1.0

    @pytest.mark.asyncio
    async def test_kubernetes_energy_replay_matches_level1(
        self, dr_ontology_dir, real_embedding_service
    ):
        """Level 2 stays precision-safe on the hard abbreviation-alias episode,
        consistent with Level 1 (test_recognition_is_precision_safe_on_hard_aliases:
        dedup_precision >= 0.9, no false merges). The embedding does not know
        K8s=Kubernetes or "the Nextflow engine"=Nextflow, so those two entities
        are expected to stay split into two nodes each -- a recognition (not
        extraction) limitation, unaffected by cassette replay."""
        cassette_dir = _EPISODES / "kubernetes_energy" / "cassettes"
        result = await run_full_pipeline_episode(
            "kubernetes_energy", cassette_dir, dr_ontology_dir, real_embedding_service
        )
        assert not result.extraction_misses

        metrics = recognition_metrics(result.mentions)
        print(f"\n── Level 2 recognition (kubernetes_energy) ── {metrics}")

        assert metrics.dedup_precision >= 0.9  # the FR4.3 safety guarantee

    @pytest.mark.asyncio
    async def test_distractor_same_class_replay_matches_level1(
        self, dr_ontology_dir, real_embedding_service
    ):
        """Level 2 stays false-merge-free on the same-class distractor episode,
        consistent with Level 1 (test_recognition_keeps_same_class_distractors_distinct:
        dedup_precision=1.0, node_count_ratio=1.0). "Beacon Primary Node" and
        "Beacon Standby Node" share class technology.node and co-occur in
        doc_03, exercising within-document discrimination."""
        cassette_dir = _EPISODES / "distractor_same_class" / "cassettes"
        result = await run_full_pipeline_episode(
            "distractor_same_class",
            cassette_dir,
            dr_ontology_dir,
            real_embedding_service,
        )
        assert not result.extraction_misses

        metrics = recognition_metrics(result.mentions)
        print(f"\n── Level 2 recognition (distractor_same_class) ── {metrics}")

        assert metrics.dedup_precision == 1.0
        assert metrics.node_count_ratio == 1.0

    @pytest.mark.asyncio
    async def test_cross_doc_convergence_replay_matches_level1(
        self, dr_ontology_dir, real_embedding_service
    ):
        """Level 2 reproduces Level 1's perfect 3-document convergence
        (test_recognition_converges_surface_variants_across_three_documents:
        precision=1.0, node_count_ratio=1.0). "Ingest Worker" / "ingest worker"
        / "Ingest-Workers" appears in all 3 documents and must resolve to a
        single node."""
        cassette_dir = _EPISODES / "cross_doc_convergence" / "cassettes"
        result = await run_full_pipeline_episode(
            "cross_doc_convergence",
            cassette_dir,
            dr_ontology_dir,
            real_embedding_service,
        )
        assert not result.extraction_misses

        metrics = recognition_metrics(result.mentions)
        print(f"\n── Level 2 recognition (cross_doc_convergence) ── {metrics}")

        assert metrics.dedup_precision == 1.0
        assert metrics.node_count_ratio == 1.0


class TestStructuralReproducibilityAcrossCorpus:
    """
    Issue #1142 Phase 5: two full-pipeline runs over the same committed, real
    cassette-backed episode produce identical entity-to-cluster structure --
    for every episode in the corpus, replayed through the actual recorded
    cassettes. ``test_recognition_episode_runner.py::
    test_structural_reproducibility_across_runs`` covers the narrower case
    (one episode, synthetic cassettes recorded on the fly) that validates the
    runner's own plumbing; this covers the full four-episode corpus against
    the real committed cassettes, so the guarantee holds end-to-end.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("episode", RECOGNITION_EPISODES)
    async def test_two_runs_produce_identical_cluster_structure(
        self, episode, dr_ontology_dir, real_embedding_service
    ):
        cassette_dir = _EPISODES / episode / "cassettes"
        first = await run_full_pipeline_episode(
            episode, cassette_dir, dr_ontology_dir, real_embedding_service
        )
        second = await run_full_pipeline_episode(
            episode, cassette_dir, dr_ontology_dir, real_embedding_service
        )

        first_ids = {m["node_id"] for m in first.mentions}
        second_ids = {m["node_id"] for m in second.mentions}
        # Fresh UUIDs each run -- confirms this isn't a no-op comparison.
        assert first_ids.isdisjoint(second_ids)

        assert recognition_metrics(first.mentions) == recognition_metrics(second.mentions)
        assert entity_key_clusters(first.mentions) == entity_key_clusters(second.mentions)
        assert first.extraction_misses == second.extraction_misses


class TestCassetteHashGraphStateIndependence:
    @pytest.mark.asyncio
    async def test_pass1_prompt_hash_independent_of_graph_state(self, dr_ontology_dir):
        """ADR-1: a document's pass-1 prompt -- and therefore its cassette hash
        key -- is identical whether built against a pristine graph or one that
        already holds individuals materialized by a prior document's apply()."""
        engine = create_local_db_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        session_factory = create_session_factory(engine)
        repo = SQLiteOntologyRepository(session_factory)
        embedding = FakeEmbeddingService()
        ontology_service = OntologyService(
            repository=repo,
            embedding_service=embedding,
            event_publisher=InProcessEventPublisher(),
            schema_index=None,
        )
        import_dr_ontology(ontology_service, repo, dr_ontology_dir)
        taxonomy = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
        assert taxonomy is not None

        service = ExtractionService(
            ontology_repo=repo,
            embedding_service=embedding,
            llm=Mock(),
            nlp=Mock(),
            reference_sources=[],
            event_publisher=InProcessEventPublisher(),
            extraction_repo=Mock(),
            extraction_run_repo=Mock(),
        )
        text = "Nf-PEAK measures the energy each task consumes."

        system_before, user_before = service._build_individual_extraction_prompt(text, taxonomy)
        hash_before = _compute_prompt_hash(system_before, user_before, "claude-opus-4-7", 0.0, None)

        # Materialize individuals into the graph, as apply() would after an
        # earlier document in the same episode.
        by_alias, _ = service._class_index(taxonomy)
        cls = by_alias["technology.systemsoftware"]
        repo.save_individual(
            Individual(id=str(uuid4()), class_ids=[str(cls.id)], title="Kubernetes")
        )

        system_after, user_after = service._build_individual_extraction_prompt(text, taxonomy)
        hash_after = _compute_prompt_hash(system_after, user_after, "claude-opus-4-7", 0.0, None)

        assert (system_before, user_before) == (system_after, user_after)
        assert hash_before == hash_after
