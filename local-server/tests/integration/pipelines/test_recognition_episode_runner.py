"""
Integration tests for the full-pipeline recognition-episode runner (issue #1142 Phase 1).

Exercises ``run_full_pipeline_episode`` against two of the four episode fixtures
(``surface_variants``, ``kubernetes_energy``) using synthetic per-document cassettes
recorded against a scripted LLM double -- these cassettes only need to make the
runner's own plumbing (state accumulation, the mention->node mapping, structural
reproducibility) independently testable, distinct from Phase 2 (recording real
cassettes against a live LLM), which is covered against the full four-episode
corpus in ``test_recognition_episode_cassette_replay.py``. The recorded content
mirrors each episode's ``expected_entities.json`` exactly, so extraction is
"perfect" by construction -- these tests validate the runner, not extraction
quality.
"""

import json
import os
import sys
from pathlib import Path
from typing import cast
from unittest.mock import Mock
from uuid import uuid4

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.connection import create_local_db_engine, create_session_factory
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.extraction.services import ExtractionService
from domain.ontology.ports import OntologyRepository
from domain.ontology.services import OntologyService
from domain.pipelines.entities import PipelineType
from domain.pipelines.individual_extraction.orchestrator import (
    IndividualExtractionOrchestrator,
    IndividualExtractionState,
)
from domain.pipelines.ports import LLMResponse
from scripts.dr_ontology_loader import DR_TAXONOMY_IDENTIFIER, import_dr_ontology
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.integration.pipelines._harness.cassettes import RecordingLLMProvider
from tests.integration.pipelines._harness.episode_runner import (
    NOT_EXTRACTED,
    NOT_MATERIALIZED,
    run_full_pipeline_episode,
)
from tests.integration.pipelines._harness.metrics import entity_key_clusters, recognition_metrics
from tests.integration.pipelines.conftest import _find_dr_spec_dir

_EPISODES = Path(__file__).parent.parent / "fixtures" / "pipelines" / "individual_recognition"


def _typing_triple(surface: str, class_ref: str) -> dict:
    return {
        "subject": {"kind": "individual", "id": None, "label": surface},
        "predicate": {"label": "is_a"},
        "object": {"kind": "class", "label": class_ref},
        "confidence": 0.95,
    }


class _ScriptedExtractionLLM:
    """
    Test double for the pass-1/pass-2 two-pass LLM calls.

    Returns ``pass1_triples`` for the individual-identification prompt and no
    relationships for the second pass (recognition metrics don't need
    relationships) -- distinguished by the marker text unique to the
    relationship-pass system prompt (``_build_relationship_extraction_prompt``).
    """

    def __init__(self, pass1_triples: list[dict]) -> None:
        self._pass1_content = json.dumps({"triples": pass1_triples})

    def complete(
        self,
        system_prompt,
        user_prompt,
        model,
        temperature=0.0,
        max_tokens=8000,
        response_format=None,
        timeout=None,
        seed=None,
    ) -> LLMResponse:
        is_relationship_pass = "already-identified individuals" in system_prompt.lower()
        content = json.dumps({"triples": []}) if is_relationship_pass else self._pass1_content
        return LLMResponse(
            content=content, tokens_in=1, tokens_out=1, duration_ms=0.0,
            finish_reason="stop", model=model,
        )

    async def complete_async(self, **kwargs) -> LLMResponse:
        return self.complete(**kwargs)

    def is_model_available(self, model: str) -> bool:
        """Check if a model is available (always true for this test double)."""
        return True

    def list_available_models(self) -> list[str]:
        """Get list of available models (empty for this test double)."""
        return []


async def _record_cassette(
    dr_ontology_dir: Path, doc_fixture: dict, pass1_triples: list[dict], cassette_path: Path
) -> None:
    """Record one document's cassette by running the real orchestrator against a scripted LLM."""
    engine = create_local_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    repo = SQLiteOntologyRepository(session_factory)
    embedding = FakeEmbeddingService()
    ontology_service = OntologyService(
        repository=cast(OntologyRepository, repo), embedding_service=embedding,
        event_publisher=InProcessEventPublisher(), schema_index=None,
    )
    import_dr_ontology(ontology_service, cast(OntologyRepository, repo), dr_ontology_dir)
    taxonomy = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    if taxonomy is None:
        raise RuntimeError(
            f"Import of {dr_ontology_dir} did not create the '{DR_TAXONOMY_IDENTIFIER}' taxonomy"
        )

    recorder = RecordingLLMProvider(_ScriptedExtractionLLM(pass1_triples), cassette_path)
    extraction_service = ExtractionService(
        ontology_repo=cast(OntologyRepository, repo),
        embedding_service=embedding,
        llm=recorder,
        nlp=Mock(),
        reference_sources=[],
        event_publisher=InProcessEventPublisher(),
        extraction_repo=Mock(),
        extraction_run_repo=Mock(),
    )
    orchestrator = IndividualExtractionOrchestrator(
        llm_provider=recorder, extraction_service=extraction_service
    )
    state = IndividualExtractionState(
        run_id=str(uuid4()),
        pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
        input_data={
            "text": doc_fixture["text"],
            "ontology_id": taxonomy.id,
            "model": doc_fixture["model"],
            "temperature": doc_fixture["temperature"],
        },
    )
    await orchestrator.execute(state)
    recorder.flush()


_UNRESOLVABLE_CLASS_REF = "nonexistent.unresolvable_class"


async def _record_episode_cassettes(
    dr_ontology_dir: Path,
    episode_dir: Path,
    cassette_dir: Path,
    omit: tuple[str, str] | None = None,
    bad_class_ref: tuple[str, str] | None = None,
) -> None:
    """
    Record a cassette per document for an episode, matching its expected_entities.json.

    ``omit``, when given, is an ``(doc, surface)`` pair to leave out of that
    document's recorded pass-1 response -- simulating a mention the LLM never
    extracted, to exercise the runner's extraction-miss path.

    ``bad_class_ref``, when given, is a ``(doc, surface)`` pair whose recorded
    triple carries ``_UNRESOLVABLE_CLASS_REF`` instead of its real class_ref --
    no alias in the DR taxonomy resolves it, so ``_ground_typing_class_ids``
    leaves ``class_ids`` empty and ``apply()`` skips materializing it. Simulates
    a mention the LLM extracts but the pipeline cannot resolve/create a node
    for, to exercise the runner's NOT_MATERIALIZED path.
    """
    expected = json.loads((episode_dir / "expected_entities.json").read_text())
    mentions_by_doc: dict[str, list[dict]] = {}
    for entity in expected:
        for mention in entity["mentions"]:
            mentions_by_doc.setdefault(mention["doc"], []).append(
                {"surface": mention["surface"], "class_ref": entity["class_ref"]}
            )

    cassette_dir.mkdir(parents=True, exist_ok=True)
    for doc_path in sorted(episode_dir.glob("doc_*.json")):
        doc = doc_path.stem
        fixture = json.loads(doc_path.read_text())
        triples = [
            _typing_triple(
                m["surface"],
                _UNRESOLVABLE_CLASS_REF if bad_class_ref == (doc, m["surface"]) else m["class_ref"],
            )
            for m in mentions_by_doc.get(doc, [])
            if omit is None or (doc, m["surface"]) != omit
        ]
        await _record_cassette(dr_ontology_dir, fixture, triples, cassette_dir / f"{doc}.json")


@pytest.fixture(scope="module")
def dr_ontology_dir() -> Path:
    spec_dir = _find_dr_spec_dir()
    if spec_dir is None:
        pytest.skip("DR spec checkout not available")
    return cast(Path, spec_dir)


class TestRunFullPipelineEpisode:
    @pytest.mark.asyncio
    async def test_state_accumulates_across_documents(self, dr_ontology_dir, tmp_path):
        """
        A mention in doc_02 resolves to the individual created while applying doc_01
        -- the graph, individual index, and ontology repo persist across the run.
        """
        episode_dir = _EPISODES / "surface_variants"
        cassette_dir = tmp_path / "surface_variants"
        await _record_episode_cassettes(dr_ontology_dir, episode_dir, cassette_dir)

        result = await run_full_pipeline_episode(
            "surface_variants", cassette_dir, dr_ontology_dir, FakeEmbeddingService()
        )

        assert not result.extraction_misses
        assert len(result.documents) == 2

        doc_01, doc_02 = result.documents
        assert doc_01.apply_result.individuals_created == 4
        # Every surface variant in doc_02 resolves against a node doc_01 already created --
        # extraction-time recognition (ExtractionService._recognize_individuals, wired to the
        # same shared index) already resolves the mention before apply() ever sees it, so
        # nothing new gets minted for entities doc_01 already introduced.
        assert doc_02.apply_result.individuals_created == 0

        kubernetes_mentions = [m for m in result.mentions if m["entity_key"] == "kubernetes"]
        assert len(kubernetes_mentions) == 2
        node_ids = {m["node_id"] for m in kubernetes_mentions}
        assert len(node_ids) == 1
        assert next(iter(node_ids)) in doc_01.apply_result.created_individual_ids

    @pytest.mark.asyncio
    async def test_recognition_metrics_over_surface_variants(self, dr_ontology_dir, tmp_path):
        """The full-pipeline mapping scores identically to the Level 1 (GT-mention) replay
        when the LLM extracts every ground-truth mention -- casing/pluralization variants
        merge perfectly."""
        episode_dir = _EPISODES / "surface_variants"
        cassette_dir = tmp_path / "surface_variants"
        await _record_episode_cassettes(dr_ontology_dir, episode_dir, cassette_dir)

        result = await run_full_pipeline_episode(
            "surface_variants", cassette_dir, dr_ontology_dir, FakeEmbeddingService()
        )
        metrics = recognition_metrics(result.mentions)

        assert metrics.dedup_precision == 1.0
        assert metrics.dedup_recall == 1.0
        assert metrics.node_count_ratio == 1.0

    @pytest.mark.asyncio
    async def test_extraction_miss_excluded_from_mentions(self, dr_ontology_dir, tmp_path):
        """A mention the scripted LLM never produces is reported as an extraction miss,
        not scored as a recognition outcome."""
        episode_dir = _EPISODES / "surface_variants"
        cassette_dir = tmp_path / "surface_variants_miss"
        omitted = ("doc_02", "kubernetes")
        await _record_episode_cassettes(dr_ontology_dir, episode_dir, cassette_dir, omit=omitted)

        result = await run_full_pipeline_episode(
            "surface_variants", cassette_dir, dr_ontology_dir, FakeEmbeddingService()
        )

        assert len(result.extraction_misses) == 1
        miss = result.extraction_misses[0]
        assert (miss["doc"], miss["surface"]) == omitted
        assert miss["reason"] == NOT_EXTRACTED
        # Only doc_01's "Kubernetes" mention was scored -- doc_02's was never extracted.
        kubernetes_mentions = [m for m in result.mentions if m["entity_key"] == "kubernetes"]
        assert len(kubernetes_mentions) == 1
        # The other three entities' mentions (2 each) were still extracted and scored normally.
        assert len(result.mentions) == 7

    @pytest.mark.asyncio
    async def test_not_materialized_when_class_ref_unresolvable(self, dr_ontology_dir, tmp_path):
        """A mention the scripted LLM extracts but tags with a class_ref no taxonomy alias
        resolves is skipped by apply() (it requires resolvable class_ids to materialize a
        typed individual) -- reported as NOT_MATERIALIZED, not NOT_EXTRACTED, since the LLM
        did produce it."""
        episode_dir = _EPISODES / "surface_variants"
        cassette_dir = tmp_path / "surface_variants_bad_class"
        bad = ("doc_01", "Kubernetes")
        await _record_episode_cassettes(
            dr_ontology_dir, episode_dir, cassette_dir, bad_class_ref=bad
        )

        result = await run_full_pipeline_episode(
            "surface_variants", cassette_dir, dr_ontology_dir, FakeEmbeddingService()
        )

        assert len(result.extraction_misses) == 1
        miss = result.extraction_misses[0]
        assert (miss["doc"], miss["surface"]) == bad
        assert miss["reason"] == NOT_MATERIALIZED
        # doc_02's "kubernetes" mention carries its own (valid) class_ref, so it's
        # extracted and materialized normally, independent of doc_01's bad triple.
        kubernetes_mentions = [m for m in result.mentions if m["entity_key"] == "kubernetes"]
        assert len(kubernetes_mentions) == 1

    @pytest.mark.asyncio
    async def test_structural_reproducibility_across_runs(self, dr_ontology_dir, tmp_path):
        """
        Two runs over the same cassette-backed episode produce identical
        entity-to-cluster structure, even though new individuals get fresh
        (non-deterministic) UUIDs each run -- recognition_metrics() only compares
        pairwise same/different-node structure, never raw ids.
        """
        episode_dir = _EPISODES / "kubernetes_energy"
        cassette_dir = tmp_path / "kubernetes_energy"
        await _record_episode_cassettes(dr_ontology_dir, episode_dir, cassette_dir)

        first = await run_full_pipeline_episode(
            "kubernetes_energy", cassette_dir, dr_ontology_dir, FakeEmbeddingService()
        )
        second = await run_full_pipeline_episode(
            "kubernetes_energy", cassette_dir, dr_ontology_dir, FakeEmbeddingService()
        )

        first_ids = {m["node_id"] for m in first.mentions}
        second_ids = {m["node_id"] for m in second.mentions}
        # Fresh UUIDs each run -- confirms this isn't a no-op.
        assert first_ids.isdisjoint(second_ids)

        assert recognition_metrics(first.mentions) == recognition_metrics(second.mentions)
        # Which entity_keys landed on the same node, keyed by entity_key rather than raw
        # node_id (fresh each run) so the two runs' cluster structure is directly comparable.
        assert entity_key_clusters(first.mentions) == entity_key_clusters(second.mentions)
