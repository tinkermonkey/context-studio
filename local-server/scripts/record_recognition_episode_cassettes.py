"""
Record per-document LLM cassettes for the individual-recognition episodes
(issue #1142 Phase 2).

Writes one cassette per document for the recognition episodes
(``surface_variants``, ``kubernetes_energy``, ``distractor_same_class``,
``cross_doc_convergence``) so
``tests/integration/pipelines/_harness/episode_runner.py`` can replay each
episode's full extraction pipeline deterministically via
``CassetteLLMProvider``, without live LLM access.

Each document's pass-1 (individual identification) and pass-2 (relationship)
responses below were authored by reading the fixture text against the exact
prompts ``ExtractionService`` builds (no live LLM provider was available to
record against), then run for real through
``IndividualExtractionOrchestrator`` wrapped in ``RecordingLLMProvider`` --
every downstream code path (prompt construction, response parsing, ontology
canonicalization) executes exactly as it would recording against a live
model; only the final response content is hand-authored rather than
API-sourced.

Pass-1 typing triples mirror the ground-truth surfaces in each episode's
``expected_entities.json`` exactly, since these documents are short,
unambiguous sentences a careful reading extracts completely.

Usage:
    python scripts/record_recognition_episode_cassettes.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import cast
from unittest.mock import Mock
from uuid import uuid4

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.connection import create_local_db_engine, create_session_factory
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.extraction.services import ExtractionService
from domain.ontology.services import OntologyService
from domain.ontology.ports import OntologyRepository
from domain.pipelines.entities import PipelineType
from domain.pipelines.individual_extraction.orchestrator import (
    IndividualExtractionOrchestrator,
    IndividualExtractionState,
)
from domain.pipelines.ports import LLMResponse
from scripts.dr_ontology_loader import DR_TAXONOMY_IDENTIFIER, import_dr_ontology
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.integration.pipelines._harness.cassettes import RecordingLLMProvider

_DR_SPEC_DIR_CANDIDATES = [
    Path(__file__).resolve().parents[2] / "documentation_robotics" / "spec",
    Path("/reference/documentation_robotics/spec"),
]
_EPISODES_DIR = (
    Path(__file__).parent.parent
    / "tests"
    / "integration"
    / "fixtures"
    / "pipelines"
    / "individual_recognition"
)


def _find_dr_spec_dir() -> Path | None:
    return next((p for p in _DR_SPEC_DIR_CANDIDATES if p.is_dir()), None)


def _typing_triple(surface: str, class_ref: str) -> dict:
    return {
        "subject": {"kind": "individual", "id": "", "label": surface},
        "predicate": {"label": "is_a"},
        "object": {"kind": "class", "label": class_ref},
        "confidence": 0.95,
    }


def _relationship_triple(
    subject_label: str, predicate_label: str, object_label: str, confidence: float = 0.85
) -> dict:
    return {
        "subject": {"kind": "individual", "id": "", "label": subject_label},
        "predicate": {"label": predicate_label},
        "object": {"kind": "individual", "id": "", "label": object_label},
        "confidence": confidence,
    }


# Hand-authored per-document responses -- see module docstring.
_DOCUMENTS = {
    "surface_variants": {
        "doc_01": {
            "pass1": [
                _typing_triple("Kubernetes", "technology.systemsoftware"),
                _typing_triple("Nf-PEAK", "application.applicationcomponent"),
                _typing_triple("RAPL Counter", "technology.systemsoftware"),
                _typing_triple("Data Object", "application.dataobject"),
            ],
            # No relationships stated between individuals in this document --
            # each sentence relates an individual only to a generic noun
            # ("workloads", "tasks", "a measurement"), not to another
            # identified individual.
            "pass2": [],
        },
        "doc_02": {
            "pass1": [
                _typing_triple("kubernetes", "technology.systemsoftware"),
                _typing_triple("Nf-PEAK", "application.applicationcomponent"),
                _typing_triple("RAPL counters", "technology.systemsoftware"),
                _typing_triple("data objects", "application.dataobject"),
            ],
            "pass2": [],
        },
    },
    "kubernetes_energy": {
        "doc_01": {
            "pass1": [
                _typing_triple("Kubernetes", "technology.systemsoftware"),
                _typing_triple("Nextflow", "application.applicationcomponent"),
                _typing_triple("Nf-PEAK", "application.applicationcomponent"),
            ],
            "pass2": [
                # "Nextflow is a workflow engine executed on Kubernetes clusters."
                _relationship_triple("Nextflow", "depends-on", "Kubernetes"),
                # "Nf-PEAK ... attributes ... energy to individual Nextflow tasks."
                _relationship_triple("Nf-PEAK", "depends-on", "Nextflow"),
            ],
        },
        "doc_02": {
            "pass1": [
                _typing_triple("K8s", "technology.systemsoftware"),
                _typing_triple("the Nextflow engine", "application.applicationcomponent"),
                _typing_triple("Nf-PEAK", "application.applicationcomponent"),
                _typing_triple("RAPL counters", "technology.systemsoftware"),
            ],
            "pass2": [
                # "K8s clusters host ... workloads. The Nextflow engine dispatches
                # pipeline tasks across nodes[.]"
                _relationship_triple("the Nextflow engine", "depends-on", "K8s"),
                # "Nf-PEAK measures the energy each task consumes[.]"
                _relationship_triple("Nf-PEAK", "depends-on", "the Nextflow engine"),
                # "RAPL counters report node-level energy that Nf-PEAK apportions
                # per task."
                _relationship_triple("Nf-PEAK", "depends-on", "RAPL counters"),
            ],
        },
    },
    "distractor_same_class": {
        "doc_01": {
            "pass1": [
                _typing_triple("Beacon Primary Node", "technology.node"),
            ],
            "pass2": [],
        },
        "doc_02": {
            "pass1": [
                _typing_triple("Beacon Standby Node", "technology.node"),
            ],
            "pass2": [],
        },
        "doc_03": {
            "pass1": [
                _typing_triple("Beacon Primary Node", "technology.node"),
                _typing_triple("Beacon Standby Node", "technology.node"),
            ],
            "pass2": [],
        },
    },
    "cross_doc_convergence": {
        "doc_01": {
            "pass1": [
                _typing_triple("Ingest Worker", "application.applicationcomponent"),
                _typing_triple("Airflow Scheduler", "technology.systemsoftware"),
            ],
            "pass2": [],
        },
        "doc_02": {
            "pass1": [
                _typing_triple("ingest worker", "application.applicationcomponent"),
                _typing_triple("Metrics Store", "application.dataobject"),
            ],
            "pass2": [],
        },
        "doc_03": {
            "pass1": [
                _typing_triple("Ingest-Workers", "application.applicationcomponent"),
                _typing_triple("Airflow Scheduler", "technology.systemsoftware"),
                _typing_triple("metrics store", "application.dataobject"),
            ],
            "pass2": [],
        },
    },
}


class _ScriptedExtractionLLM:
    """Returns the hand-authored pass-1/pass-2 responses for one document.

    Distinguishes the two passes the same way the pipeline's own pass-2 system
    prompt is written to be distinguished elsewhere in this codebase: by the
    marker text unique to ``_build_relationship_extraction_prompt``.
    """

    def __init__(self, pass1_triples: list[dict], pass2_triples: list[dict]) -> None:
        self._pass1_content = json.dumps({"triples": pass1_triples})
        self._pass2_content = json.dumps({"triples": pass2_triples})

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
        content = self._pass2_content if is_relationship_pass else self._pass1_content
        return LLMResponse(
            content=content,
            tokens_in=1,
            tokens_out=1,
            duration_ms=0.0,
            finish_reason="stop",
            model=model,
        )

    async def complete_async(self, **kwargs) -> LLMResponse:
        return self.complete(**kwargs)

    def is_model_available(self, model: str) -> bool:
        """Check if a model is available (always true for this test double)."""
        return True

    def list_available_models(self) -> list[str]:
        """Get list of available models (empty for this test double)."""
        return []


async def _record_document(
    dr_ontology_dir: Path,
    doc_fixture: dict,
    pass1_triples: list[dict],
    pass2_triples: list[dict],
    cassette_path: Path,
) -> int:
    """Record one document's cassette by running the real orchestrator against
    a scripted LLM double, exactly as production wiring would against a live
    provider."""
    engine = create_local_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    repo = SQLiteOntologyRepository(session_factory)
    embedding = FakeEmbeddingService()
    ontology_service = OntologyService(
        repository=cast(OntologyRepository, repo),
        embedding_service=embedding,
        event_publisher=InProcessEventPublisher(),
        schema_index=None,
    )
    import_dr_ontology(ontology_service, cast(OntologyRepository, repo), dr_ontology_dir)
    taxonomy = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    if taxonomy is None:
        raise RuntimeError(
            f"Import of {dr_ontology_dir} did not create the '{DR_TAXONOMY_IDENTIFIER}' taxonomy"
        )

    recorder = RecordingLLMProvider(
        _ScriptedExtractionLLM(pass1_triples, pass2_triples), cassette_path
    )
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
    result_state = await orchestrator.execute(state)
    if result_state.result is None:
        raise RuntimeError(
            f"IndividualExtractionOrchestrator returned no result while recording "
            f"'{cassette_path}' (status={result_state.current_status}); refusing to "
            "flush a partial cassette"
        )
    recorder.flush()
    return len(recorder._recordings)


async def _record_all() -> int:
    dr_ontology_dir = _find_dr_spec_dir()
    if dr_ontology_dir is None:
        print(
            "ERROR: documentation_robotics/spec checkout not found (checked "
            f"{[str(p) for p in _DR_SPEC_DIR_CANDIDATES]})."
        )
        return 1

    total = 0
    for episode, docs in _DOCUMENTS.items():
        episode_dir = _EPISODES_DIR / episode
        cassette_dir = episode_dir / "cassettes"
        cassette_dir.mkdir(parents=True, exist_ok=True)
        for doc, calls in docs.items():
            doc_fixture = json.loads((episode_dir / f"{doc}.json").read_text())
            cassette_path = cassette_dir / f"{doc}.json"
            n = await _record_document(
                dr_ontology_dir, doc_fixture, calls["pass1"], calls["pass2"], cassette_path
            )
            print(f"  recorded {episode}/{doc} ({n} call(s)) -> {cassette_path}")
            total += 1

    print(f"\nrecorded {total} cassette(s) under {_EPISODES_DIR}/<episode>/cassettes/")
    return 0


def main() -> int:
    """Record cassettes for every document in every recognition episode."""
    return asyncio.run(_record_all())


if __name__ == "__main__":
    raise SystemExit(main())
