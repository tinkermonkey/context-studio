"""
Full-pipeline recognition-episode runner (issue #1142 Phase 1; ADR-2 Level 2 replay).

Runs a recognition episode's documents through the complete extraction
pipeline -- ``IndividualExtractionOrchestrator.execute()`` (cassette-replayed
LLM extraction, including extraction-time recognition) followed by
``IndividualExtractionApplyService.apply()`` (apply-time recognition +
materialization) -- in the episode's fixed document order, against one
ontology graph, individual vector index, ontology repository, and embedding
service that persist and accumulate for the whole run. This is the Level 2
replay: unlike the GT-mention-only Level 1 harness
(``test_individual_recognition_episode.py``), it exercises real LLM
extraction via ``CassetteLLMProvider``, so recognition quality reflects
LLM-extraction variance as well.

No changes to the recognition sites themselves (``ExtractionService.
_recognize_individuals``, ``IndividualExtractionApplyService.
_recognize_individual``, ``OntologyService._sync_individual_index``) --
every pipeline component here runs exactly as it does in production; this
module only wires them together and measures the outcome.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.connection import create_local_db_engine, create_session_factory
from adapters.persistence.sqlite.individual_vector_index import SqliteIndividualVectorIndex
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.recognition.individual_recognizer import CascadeIndividualRecognizer
from domain.extraction.services import ExtractionService
from domain.ontology.ports import EmbeddingService
from domain.ontology.services import OntologyService
from domain.pipelines.apply_result import ApplyResult
from domain.pipelines.entities import PipelineRun, PipelineType
from domain.pipelines.individual_extraction.apply_service import IndividualExtractionApplyService
from domain.pipelines.individual_extraction.orchestrator import (
    IndividualExtractionOrchestrator,
    IndividualExtractionState,
)
from scripts.dr_ontology_loader import DR_TAXONOMY_IDENTIFIER, import_dr_ontology
from tests.integration.pipelines._harness.cassettes import CassetteLLMProvider
from tests.integration.pipelines._harness.metrics import normalize_label

_EPISODES_DIR = (
    Path(__file__).parent.parent.parent / "fixtures" / "pipelines" / "individual_recognition"
)

# Why a mention lands out of the mention->node mapping recognition_metrics() scores.
NOT_EXTRACTED = "not_extracted"  # the LLM never produced a matching individual mention
NOT_MATERIALIZED = "not_materialized"  # extracted, but apply() could not resolve/create a node


@dataclass
class DocumentRunOutcome:
    """Per-document diagnostics from one episode run."""

    doc: str
    apply_result: ApplyResult
    tokens_used: int
    warnings: list[str] = field(default_factory=list)


@dataclass
class EpisodeRunResult:
    """
    Result of running one recognition episode through the full pipeline.

    ``mentions`` is directly consumable by ``recognition_metrics()``. Ground-truth
    mentions the pipeline never scored land in ``extraction_misses`` instead, tagged
    with why (``NOT_EXTRACTED`` vs. ``NOT_MATERIALIZED``) -- distinct from a
    *recognition failure*, where the mention was extracted and resolved to a node
    ``recognition_metrics()`` finds is the wrong one.
    """

    episode: str
    mentions: list[dict] = field(default_factory=list)
    extraction_misses: list[dict] = field(default_factory=list)
    documents: list[DocumentRunOutcome] = field(default_factory=list)


def _episode_mentions_by_doc(episode_dir: Path) -> dict[str, list[dict]]:
    expected = json.loads((episode_dir / "expected_entities.json").read_text())
    by_doc: dict[str, list[dict]] = {}
    for entity in expected:
        for mention in entity["mentions"]:
            by_doc.setdefault(mention["doc"], []).append(
                {
                    "entity_key": entity["entity_key"],
                    "canonical_title": entity["canonical_title"],
                    "surface": mention["surface"],
                }
            )
    return by_doc


def _extracted_individuals_by_normalized_label(
    triples: list[dict],
) -> dict[str, tuple[str, list[str]]]:
    """
    Map each distinct individual mention the LLM produced (normalized, first
    occurrence wins) to its raw label and grounded class ids.

    Normalized (lemma/stem) rather than exact-string keyed: extraction-time
    recognition (``ExtractionService._recognize_individuals``) may already have
    rewritten a triple's label to an existing node's canonical title before this
    function ever sees it, so comparing raw strings against the ground-truth
    surface would misclassify a resolved surface variant as an extraction miss.
    """
    extracted: dict[str, tuple[str, list[str]]] = {}
    for triple in triples:
        subject = triple.get("subject", {})
        if subject.get("kind") != "individual":
            continue
        label = (subject.get("label") or "").strip()
        if not label:
            continue
        key = normalize_label(label)
        if key not in extracted:
            extracted[key] = (label, subject.get("class_ids") or [])
    return extracted


def _resolve_node_for_label(repo: SQLiteOntologyRepository, label: str, class_ids: list[str]):
    """The individual now titled ``label`` (case-insensitive) within ``class_ids``, post-apply."""
    label_lower = label.strip().lower()
    for class_id in class_ids:
        for individual in repo.list_individuals(class_id=class_id, limit=None):
            if individual.title.strip().lower() == label_lower:
                return individual
    return None


def _ground_typing_class_ids(triples: list[dict], by_alias: dict) -> None:
    """
    Resolve each new ``is_a`` triple's ``subject.class_ids`` to the real class id
    its (already-canonicalized) ``object.label`` names, in place.

    ``ExtractionService``'s ``llm_two_pass`` pass-1 prompt only ever shows the LLM
    a class *reference string* (e.g. ``"technology.systemsoftware"``), never the
    class's internal id, so a well-formed response leaves ``subject.class_id``
    blank -- and ``IndividualExtractionApplyService.apply()`` (unchanged, per the
    Component Reuse table) requires ``subject.class_ids`` to hold real class ids
    before it will create a typed individual. Bridging reference -> id is exactly
    what ``ExtractionService._class_index``'s ``by_alias`` map already exists for
    (the same lookup canonicalization and apply-time recognition use); this only
    reuses it one step earlier, between orchestration and apply.
    """
    for triple in triples:
        subject = triple.get("subject", {})
        obj = triple.get("object", {})
        if subject.get("kind") != "individual" or obj.get("kind") != "class":
            continue
        if subject.get("class_ids"):
            continue
        cls = by_alias.get(str(obj.get("label") or "").strip().lower())
        if cls is not None:
            subject["class_ids"] = [str(cls.id)]


async def run_full_pipeline_episode(
    episode: str,
    cassette_dir: Path,
    dr_ontology_dir: Path,
    embedding_service: EmbeddingService,
) -> EpisodeRunResult:
    """
    Run one recognition episode's documents through the full extraction pipeline.

    For each ``doc_NN.json`` in the episode's fixture directory (lexicographic
    order): replays LLM extraction from ``cassette_dir / f"{doc}.json"`` via
    ``IndividualExtractionOrchestrator``, then materializes the triples via
    ``IndividualExtractionApplyService.apply()``. The ontology graph, individual
    vector index, and ontology repository are built once and shared across every
    document, so document N+1's recognition can resolve against individuals
    created while applying documents 1..N.

    Args:
        episode: Episode name (a directory under
            ``tests/integration/fixtures/pipelines/individual_recognition/``).
        cassette_dir: Directory containing one LLM cassette per document,
            named ``{doc_stem}.json`` (e.g. ``doc_01.json``).
        dr_ontology_dir: Path to the Documentation Robotics spec checkout to
            import as the episode's ontology (see ``scripts.dr_ontology_loader``).
        embedding_service: Embedding service shared across the whole run, wired
            into the individual vector index and recognizer exactly as callers
            would in production. Caller-supplied rather than constructed here so
            tests can inject a fake (avoiding network access to download a real
            model) while production callers pass a real adapter.

    Returns:
        EpisodeRunResult with the mention->node mapping and per-document diagnostics.
    """
    episode_dir = _EPISODES_DIR / episode
    doc_paths = sorted(episode_dir.glob("doc_*.json"))
    if not doc_paths:
        raise FileNotFoundError(
            f"No doc_*.json fixtures found for episode '{episode}' in {episode_dir}"
        )
    mentions_by_doc = _episode_mentions_by_doc(episode_dir)

    engine = create_local_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    repo = SQLiteOntologyRepository(session_factory)
    index = SqliteIndividualVectorIndex(session_factory, embedding_service)
    ontology_service = OntologyService(
        repository=repo,
        embedding_service=embedding_service,
        event_publisher=InProcessEventPublisher(),
        schema_index=None,
        individual_index=index,
    )
    import_dr_ontology(ontology_service, repo, dr_ontology_dir)
    taxonomy = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    if taxonomy is None:
        raise RuntimeError(
            f"Import of {dr_ontology_dir} did not create the '{DR_TAXONOMY_IDENTIFIER}' taxonomy"
        )

    recognizer = CascadeIndividualRecognizer(
        individual_index=index, embedding_service=embedding_service, llm=None
    )
    apply_service = IndividualExtractionApplyService(
        ontology_service, repo, individual_recognizer=recognizer
    )

    result = EpisodeRunResult(episode=episode)

    for doc_path in doc_paths:
        doc = doc_path.stem
        fixture = json.loads(doc_path.read_text())
        llm = CassetteLLMProvider(cassette_dir / f"{doc}.json")

        extraction_service = ExtractionService(
            ontology_repo=repo,
            embedding_service=embedding_service,
            llm=llm,
            nlp=Mock(),
            reference_sources=[],
            event_publisher=InProcessEventPublisher(),
            extraction_repo=Mock(),
            extraction_run_repo=Mock(),
            individual_index=index,
        )
        orchestrator = IndividualExtractionOrchestrator(
            llm_provider=llm, extraction_service=extraction_service
        )

        state = IndividualExtractionState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            input_data={
                "text": fixture["text"],
                "ontology_id": taxonomy.id,
                "model": fixture["model"],
                "temperature": fixture["temperature"],
            },
        )
        result_state = await orchestrator.execute(state)
        output = result_state.result or {}
        triples = output.get("triples", [])

        by_alias, _ = extraction_service._class_index(taxonomy)
        _ground_typing_class_ids(triples, by_alias)

        run = PipelineRun(
            id=state.run_id,
            batch_run_id=f"recognition-episode-{episode}",
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            configuration_ref="default",
            configuration_slug="default",
            configuration_version=1,
            output_summary=output,
        )
        apply_result = apply_service.apply(run)

        extracted = _extracted_individuals_by_normalized_label(triples)
        for gt_mention in mentions_by_doc.get(doc, []):
            hit = extracted.get(normalize_label(gt_mention["surface"]))
            if hit is None:
                result.extraction_misses.append(
                    {**gt_mention, "doc": doc, "reason": NOT_EXTRACTED}
                )
                continue
            label, class_ids = hit
            node = _resolve_node_for_label(repo, label, class_ids)
            if node is None:
                result.extraction_misses.append(
                    {**gt_mention, "doc": doc, "reason": NOT_MATERIALIZED}
                )
                continue
            result.mentions.append(
                {
                    "entity_key": gt_mention["entity_key"],
                    "canonical_title": gt_mention["canonical_title"],
                    "node_id": node.id,
                    "title": node.title,
                }
            )

        result.documents.append(
            DocumentRunOutcome(
                doc=doc,
                apply_result=apply_result,
                tokens_used=output.get("metadata", {}).get("tokens_used", 0),
                warnings=output.get("warnings", []),
            )
        )

    return result
