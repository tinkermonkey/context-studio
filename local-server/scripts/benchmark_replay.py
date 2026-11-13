"""
Run the default individual-extraction pipeline over the benchmark documents,
in process, and score it against their gold extractions.

Each document goes through the path a user's source takes: its markdown
headings are read, the text is chunked, each chunk is extracted with the two
LLM stages, the chunks' triples are merged, and the merged triples are planned
as the individual and relationship creates a proposal would hold. Those planned
creates are what is scored (tests/integration/pipelines/_harness/benchmark.py).

The ontology is built from the pinned DR spec snapshot the gold files were made
against, with real embeddings and a schema vector index, so each prompt carries
the class catalog retrieved for its chunk, as in the app.

Offline by default: every LLM call is answered from a recorded cassette
(tests/integration/fixtures/cassettes/extraction_benchmark/<document>.json). A
document with no cassette is reported as not recorded; a cassette that no
longer answers the pipeline's prompts is reported as stale, never as a score.

Usage (from local-server/, venv active):
    python scripts/benchmark_replay.py                       # replay and score
    python scripts/benchmark_replay.py --record --spend      # record with the live LLM (costs)
    python scripts/benchmark_replay.py --record --spend --document edit_check
"""

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.connection import create_local_db_engine, create_session_factory
from adapters.persistence.sqlite.extraction_repo import SQLiteExtractionRepository
from adapters.persistence.sqlite.extraction_run_repo import SQLiteExtractionRunRepository
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.schema_vector_index import SqliteSchemaVectorIndex
from adapters.sources.readers import MarkdownReader
from domain.extraction.services import ExtractionService
from domain.ontology.ports import OntologyRepository
from domain.ontology.services import OntologyService
from domain.pipelines.entities import PipelineType
from domain.pipelines.individual_extraction.orchestrator import (
    IndividualExtractionOrchestrator,
    IndividualExtractionState,
)
from domain.pipelines.individual_extraction.source_operations import plan_individual_operations
from domain.pipelines.ports import LLMProvider
from domain.versioning.proposals import OperationKind
from scripts.dr_ontology_loader import DR_TAXONOMY_IDENTIFIER, import_dr_ontology
from tests.fakes.fake_nlp_processor import FakeNLPProcessor
from tests.fakes.fake_reference_source import FakeReferenceSource
from tests.integration.pipelines._harness.benchmark import (
    BENCHMARK_DIR,
    BenchmarkScore,
    Passage,
    Predicted,
    PredictedRelationship,
    benchmark_documents,
    failure_counts,
    load_gold,
    mean_metrics,
    score,
)
from tests.integration.pipelines._harness.cassettes import (
    CassetteLLMProvider,
    RecordingLLMProvider,
)
from tests.integration.pipelines._harness.dr_spec import dr_spec_dir

# The DR spec version the gold extractions were made against.
BENCHMARK_DR_SPEC_VERSION = "0.11.0"
# The model the cassettes are recorded with: cheap, routed through OpenRouter.
# The cassette key includes the model, so changing it means recording again.
BENCHMARK_MODEL = "google/gemini-3-flash-preview"
EMBEDDING_MODEL = "all-MiniLM-L12-v2"
CASSETTE_DIR = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "integration"
    / "fixtures"
    / "cassettes"
    / "extraction_benchmark"
)
# Which documents the loop optimises on, and which only vetoes (never selects).
DEV_DOCUMENTS = ("edit_check", "gitlab_architecture")
HOLDOUT_DOCUMENTS = ("wikimedia_enterprise",)
SOURCE_ID = "benchmark"


@dataclass(frozen=True)
class BenchmarkOntology:
    """The DR ontology the benchmark runs against, in an in-memory database."""

    session_factory: Any
    repo: OntologyRepository
    taxonomy_id: str
    embedding: Any
    schema_index: Any
    class_refs: dict[str, str]
    predicates: dict[str, str]


@cache
def benchmark_ontology() -> BenchmarkOntology:
    """Build the pinned DR ontology once per process (about a minute)."""
    engine = create_local_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    repo = cast(OntologyRepository, SQLiteOntologyRepository(session_factory))
    embedding = SentenceTransformerEmbedding(model_name=EMBEDDING_MODEL)
    # schema_index=None while importing: index once afterwards, not per entity
    service = OntologyService(
        repository=repo,
        embedding_service=embedding,
        event_publisher=InProcessEventPublisher(),
        schema_index=None,
    )
    import_dr_ontology(service, repo, dr_spec_dir(BENCHMARK_DR_SPEC_VERSION))
    schema_index = SqliteSchemaVectorIndex(session_factory, embedding)
    schema_index.reindex_all()
    taxonomy = repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    if taxonomy is None:
        raise RuntimeError("The DR spec snapshot imported no taxonomy")
    # The only taxonomy in this database is the DR one
    classes = repo.list_classes(limit=None)
    class_refs = {
        c.id: (c.external_references[0].identifier if c.external_references else c.identifier)
        for c in classes
    }
    predicates = {p.id: p.identifier for p in repo.list_predicates(taxonomy.id)}
    return BenchmarkOntology(
        session_factory, repo, taxonomy.id, embedding, schema_index, class_refs, predicates
    )


def cassette_path(document_id: str) -> Path:
    return CASSETTE_DIR / f"{document_id}.json"


async def extract_document(
    ontology: BenchmarkOntology,
    provider: LLMProvider,
    document_id: str,
    model: str = BENCHMARK_MODEL,
    config: dict[str, Any] | None = None,
) -> tuple[list[Predicted], list[PredictedRelationship]]:
    """
    Extract one benchmark document as a source and return what a proposal
    would hold: the planned individual and relationship creates.
    """
    data = (BENCHMARK_DIR / document_id / "source.md").read_bytes()
    source = MarkdownReader().read(data)
    service = ExtractionService(
        ontology_repo=ontology.repo,
        embedding_service=ontology.embedding,
        llm=provider,
        nlp=FakeNLPProcessor(),
        reference_sources=[FakeReferenceSource()],
        event_publisher=InProcessEventPublisher(),
        extraction_repo=SQLiteExtractionRepository(ontology.session_factory),
        extraction_run_repo=SQLiteExtractionRunRepository(ontology.session_factory),
        schema_index=ontology.schema_index,
    )
    orchestrator = IndividualExtractionOrchestrator(
        llm_provider=provider, extraction_service=service, config=config
    )
    state = IndividualExtractionState(
        run_id=str(uuid4()),
        pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
        input_data={
            "text": source.text,
            "ontology_id": ontology.taxonomy_id,
            "model": model,
            "temperature": 0.0,
            "headings": [
                {"start": h.start, "title": h.title, "level": h.level} for h in source.headings
            ],
        },
    )
    result = (await orchestrator.execute(state)).result or {}
    plan = plan_individual_operations(
        result.get("triples", []),
        ontology.repo,
        taxonomy_id=ontology.taxonomy_id,
        dataset_id=None,
        source_id=SOURCE_ID,
        page_starts=[],
    )
    return predictions_from_plan(plan.operations, ontology)


def predictions_from_plan(
    operations: list[Any], ontology: BenchmarkOntology
) -> tuple[list[Predicted], list[PredictedRelationship]]:
    """Planned operations as predictions: creates only, classes as DR references."""
    titles: dict[str, str] = {}
    individuals: list[Predicted] = []
    relationships: list[PredictedRelationship] = []
    properties = {p.id: p for p in ontology.repo.list_property_definitions(limit=None)}
    for planned in operations:
        draft = planned.draft
        if draft.kind is OperationKind.INDIVIDUAL:
            title = str(draft.fields.get("title") or "")
            titles[f"${draft.ref}"] = title
            individuals.append(
                Predicted(
                    title=title,
                    class_refs=tuple(
                        ontology.class_refs[c]
                        for c in draft.fields.get("class_ids", ())
                        if c in ontology.class_refs
                    ),
                    evidence=tuple(
                        Passage(e["start"], e["end"], str(e.get("quote") or ""))
                        for e in draft.evidence
                        if isinstance(e.get("start"), int) and isinstance(e.get("end"), int)
                    ),
                )
            )
    for planned in operations:
        draft = planned.draft
        if draft.kind is not OperationKind.RELATIONSHIP:
            continue
        prop = properties.get(draft.fields.get("property_definition_id"))
        source, target = (titles.get(draft.fields.get(k), "") for k in ("source_id", "target_id"))
        predicate = (
            ontology.predicates.get(prop.predicate_id) or prop.canonical_predicate if prop else None
        )
        if predicate and source and target:
            relationships.append(PredictedRelationship(source, predicate, target))
    return individuals, relationships


@dataclass
class DocumentResult:
    """One document's outcome: a score, or why there is none."""

    document_id: str
    status: str  # "scored", "not_recorded" or "stale"
    score: BenchmarkScore | None = None
    calls: int = 0
    misses: int = 0


async def replay_document(document_id: str, config: dict[str, Any] | None = None) -> DocumentResult:
    """Replay one document from its cassette and score it."""
    path = cassette_path(document_id)
    if not path.exists():
        return DocumentResult(document_id, "not_recorded")
    provider = CassetteLLMProvider(path)
    individuals, relationships = await extract_document(
        benchmark_ontology(), cast(LLMProvider, provider), document_id, config=config
    )
    if provider.misses:
        return DocumentResult(document_id, "stale", calls=provider.calls, misses=provider.misses)
    result = score(load_gold(document_id), individuals, relationships)
    return DocumentResult(document_id, "scored", result, calls=provider.calls)


async def replay_all(
    documents: list[str] | None = None, config: dict[str, Any] | None = None
) -> list[DocumentResult]:
    return [await replay_document(d, config) for d in documents or benchmark_documents()]


def summarize(results: list[DocumentResult]) -> dict[str, Any]:
    """
    Dev and holdout means, the failure counts over dev, and whether the run can
    be trusted: `status` is "scored" only when every document scored.
    """
    scored = {r.document_id: r.score for r in results if r.score is not None}
    status = "scored"
    if any(r.status == "stale" for r in results):
        status = "stale"
    elif any(r.status == "not_recorded" for r in results):
        status = "not_recorded"
    dev = [scored[d] for d in DEV_DOCUMENTS if d in scored]
    holdout = [scored[d] for d in HOLDOUT_DOCUMENTS if d in scored]
    return {
        "status": status,
        "documents": {r.document_id: r.status for r in results},
        "dev": mean_metrics(dev),
        "holdout": mean_metrics(holdout),
        "failure_counts": failure_counts(dev),
    }


async def record_document(document_id: str, model: str) -> DocumentResult:
    """Extract one document with the live LLM, recording every call, and score it."""
    from adapters.llm.provider_router import LLMProviderRouter
    from config import get_config_manager

    llm = get_config_manager().get_settings().llm
    if not (llm.openai_api_key or llm.anthropic_api_key or llm.openrouter_api_key):
        raise SystemExit("No LLM API key is configured (local-server/.env); nothing to record with")
    router = LLMProviderRouter(
        openai_api_key=llm.openai_api_key,
        anthropic_api_key=llm.anthropic_api_key,
        openrouter_api_key=llm.openrouter_api_key,
    )
    path = cassette_path(document_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    recorder = RecordingLLMProvider(router, path)
    individuals, relationships = await extract_document(
        benchmark_ontology(), cast(LLMProvider, recorder), document_id, model=model
    )
    if recorder.incomplete_count:
        raise SystemExit(
            f"{document_id}: the provider cut short or errored on {recorder.incomplete_count} of "
            f"{recorder.call_count} responses; nothing was saved. Record it again."
        )
    recorder.flush()
    result = score(load_gold(document_id), individuals, relationships)
    return DocumentResult(document_id, "scored", result, calls=recorder.call_count)


def print_results(results: list[DocumentResult]) -> None:
    for r in results:
        if r.score is None:
            detail = f" ({r.misses} of {r.calls} calls have no recording)" if r.misses else ""
            print(f"{r.document_id:<24} {r.status}{detail}")
            continue
        m = r.score.metrics
        print(
            f"{r.document_id:<24} recall {m['recall']:.3f} (core {m['recall_core']:.3f})  "
            f"precision {m['precision']:.3f}  type accuracy {m['type_accuracy']:.3f}  "
            f"typed F1 {m['typed_f1']:.3f}  relationship recall {m['relationship_recall']:.3f}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--document", action="append", help="A document id (repeatable); all by default"
    )
    parser.add_argument("--record", action="store_true", help="Record cassettes with the live LLM")
    parser.add_argument("--spend", action="store_true", help="Confirm --record may call the LLM")
    parser.add_argument("--model", default=BENCHMARK_MODEL, help="The model to record with")
    parser.add_argument("--json", action="store_true", help="Print the summary as JSON")
    args = parser.parse_args()
    documents = args.document or benchmark_documents()
    if args.record:
        if not args.spend:
            raise SystemExit(
                "--record calls the live LLM, which costs money; pass --spend to go ahead"
            )
        if args.model != BENCHMARK_MODEL:
            print(
                f"note: replay expects {BENCHMARK_MODEL}; cassettes recorded with "
                f"{args.model} will read as stale"
            )
        results = [asyncio.run(record_document(d, args.model)) for d in documents]
    else:
        results = asyncio.run(replay_all(documents))
    print_results(results)
    summary = summarize(results)
    if args.json:
        print(json.dumps(summary, indent=1))
    else:
        print(f"status: {summary['status']}")
        if summary["dev"]:
            print(
                f"dev typed F1 {summary['dev']['typed_f1']:.3f}, "
                f"found F1 {summary['dev']['f1']:.3f}"
            )
    return 0 if summary["status"] == "scored" else 2


if __name__ == "__main__":
    sys.exit(main())
