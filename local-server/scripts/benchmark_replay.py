"""
Run an individual-extraction implementation over the benchmark documents, in
process, and score it against their gold extractions.

What runs is chosen the way every run is chosen: an implementation of the
pipeline type and one of its configurations (`--implementation`,
`--configuration`), selected through the pipeline resolver
(`domain/pipelines/selection.py`). The orchestrator comes from the
implementation registry and the model, temperature, output-token limit and
stage prompts from the configuration, as
`domain/pipelines/individual_extraction/bootstrap.py` registers them; nothing
here names a model. With no flags the target is the type's default
implementation (`find_then_type`) with the configuration its recordings were
made with (`RECORDED_WITH`, else the implementation's default configuration).
The two-pass implementation's id is `default`: a name, not the type's default.

Each document goes through the path a user's source takes: its markdown
headings are read, the text is chunked, each chunk is extracted by the
implementation's LLM stages, the chunks' triples are merged, and the merged
triples are planned as the individual and relationship creates a proposal would
hold. Those planned creates are what is scored
(tests/integration/pipelines/_harness/benchmark.py).

The ontology is built from the pinned DR spec snapshot the gold files were made
against, with real embeddings and a schema vector index, so each prompt carries
the class catalog the app would offer.

Offline by default: every LLM call is answered from a recorded cassette. Each
target has its own folder under tests/integration/fixtures/cassettes/
(`cassette_dir`): `extraction_benchmark/` for the two-pass implementation (id `default`),
`extraction_benchmark_<implementation>/` for any other, and a
`__<configuration>` suffix for a configuration other than the one the
implementation's benchmark runs with. A document with no cassette is reported
as not recorded; a cassette that no longer answers the pipeline's prompts is
reported as stale, never as a score.

Usage (from local-server/, venv active):
    python scripts/benchmark_replay.py                                  # replay and score
    python scripts/benchmark_replay.py --implementation find_then_type  # another implementation
    python scripts/benchmark_replay.py --all                            # every recorded target
    python scripts/benchmark_replay.py --record --spend                 # record, live LLM (costs)
    python scripts/benchmark_replay.py --record --spend --implementation find_then_type \
        --configuration extraction-find-then-type --document edit_check
"""

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Mapping, cast
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
from domain.pipelines.exceptions import (
    ConfigurationDisabledError,
    PipelineExecutionError,
    UnknownConfigurationError,
    UnknownImplementationError,
)
from domain.pipelines.individual_extraction.bootstrap import register_individual_extraction
from domain.pipelines.individual_extraction.orchestrator import (
    IndividualExtractionOrchestrator,
    IndividualExtractionState,
)
from domain.pipelines.individual_extraction.source_operations import plan_individual_operations
from domain.pipelines.ports import LLMProvider
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from domain.pipelines.selection import PipelineResolver, PipelineSelection
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
EMBEDDING_MODEL = "all-MiniLM-L12-v2"
PIPELINE_TYPE = PipelineType.INDIVIDUAL_EXTRACTION
# The folder of the two-pass implementation's recordings (id `default`); every
# other target's folder is named after it (cassette_dir).
CASSETTE_DIR = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "integration"
    / "fixtures"
    / "cassettes"
    / "extraction_benchmark"
)
# The implementation whose recordings are in CASSETTE_DIR itself: the first
# benchmark recorded, before the implementation could be chosen.
UNSUFFIXED_IMPLEMENTATION = "default"
# The configuration each implementation's committed recordings were made with,
# by name. The cassette key includes the model, so naming the configuration
# keeps the recordings answering whatever the implementation's default
# configuration becomes: the two-pass implementation (id `default`) was
# recorded with Gemini 3 Flash, which is `extraction-openrouter-default`, not
# its default configuration `extraction-default` (Claude Haiku 5.5 since
# PR #1598). To measure another configuration, ask for it with
# --configuration: it gets a cassette folder of its own.
RECORDED_WITH: dict[str, str] = {
    "default": "extraction-openrouter-default",
    "find_then_type": "extraction-find-then-type",
}


class UnknownTargetError(ValueError):
    """The implementation or configuration asked for is not one the benchmark can run."""


@dataclass(frozen=True)
class BenchmarkTarget:
    """
    What a benchmark run runs: an implementation with one of its
    configurations, as the pipeline resolver selects it.
    """

    implementation: str
    configuration: str
    selection: PipelineSelection

    @property
    def orchestrator(self) -> type[IndividualExtractionOrchestrator]:
        """The implementation's orchestrator class, from the implementation registry."""
        return self.selection.implementation

    @property
    def config(self) -> dict[str, Any]:
        """The configuration's contents: provider, model, temperature, stage prompts."""
        return self.selection.config

    @property
    def model(self) -> str:
        """The model the run uses: the configuration's, as the resolver gives it."""
        return str(self.selection.parameters.get("model") or "")

    @property
    def temperature(self) -> float:
        return float(self.selection.parameters.get("temperature") or 0.0)

    def run_input(self, input_data: Mapping[str, Any]) -> dict[str, Any]:
        """
        A run's input with the configuration's model, temperature and
        output-token limit filled in, by the resolver's rule
        (PipelineSelection.run_input). The output-token limit is not part of a
        cassette's key, so a change of it leaves recordings answering.
        """
        return self.selection.run_input(input_data)

    @property
    def flags(self) -> str:
        """The command-line flags that choose this target."""
        return f"--implementation {self.implementation} --configuration {self.configuration}"

    def describe(self) -> dict[str, str]:
        return {
            "implementation": self.implementation,
            "configuration": self.configuration,
            "model": self.model,
        }


@cache
def pipeline_registries() -> tuple[PipelineImplementationRegistry, PipelineConfigurationRegistry]:
    """Individual extraction's implementations and configurations, as the app registers them."""
    implementations = PipelineImplementationRegistry()
    configurations = PipelineConfigurationRegistry()
    register_individual_extraction(implementations, configurations)
    return implementations, configurations


def pipeline_resolver() -> PipelineResolver:
    """The resolver every run is selected through, over the registries above."""
    return PipelineResolver(*pipeline_registries())


def default_implementation() -> str:
    """The pipeline type's default implementation, as registration declares it."""
    try:
        return pipeline_resolver().implementation(PIPELINE_TYPE)[0]
    except UnknownImplementationError as exc:
        raise UnknownTargetError(str(exc)) from exc


def default_configuration(implementation: str) -> str:
    """An implementation's default configuration, as registration declares it."""
    _, configurations = pipeline_registries()
    configuration = configurations.default_configuration(PIPELINE_TYPE, implementation)
    if configuration is None:
        raise UnknownTargetError(f"implementation {implementation!r} has no default configuration")
    return configuration


def benchmark_configuration(implementation: str) -> str:
    """The configuration an implementation's benchmark runs with when none is asked for."""
    return RECORDED_WITH.get(implementation) or default_configuration(implementation)


def resolve_target(
    implementation: str | None = None, configuration: str | None = None
) -> BenchmarkTarget:
    """
    The benchmark target for an implementation and a configuration, selected
    through the pipeline resolver: the implementation defaults to the type's
    default (registration declares it: `find_then_type` since PR #1598), the
    configuration to the one the implementation's recordings were made with
    (RECORDED_WITH), else to its default.

    Raises:
        UnknownTargetError: If the implementation is not registered or cannot
            extract a source chunk by chunk, or the configuration is not one of
            the implementation's
    """
    resolver = pipeline_resolver()
    try:
        implementation, orchestrator = resolver.implementation(PIPELINE_TYPE, implementation)
    except UnknownImplementationError as exc:
        raise UnknownTargetError(f"no implementation {implementation!r}: {exc}") from exc
    if not issubclass(orchestrator, IndividualExtractionOrchestrator):
        raise UnknownTargetError(
            f"implementation {implementation!r} does not extract a source chunk by chunk, "
            "so the benchmark cannot run it"
        )
    configuration = configuration or RECORDED_WITH.get(implementation)
    try:
        selection = resolver.resolve(PIPELINE_TYPE, implementation, configuration)
    except (UnknownConfigurationError, ConfigurationDisabledError) as exc:
        raise UnknownTargetError(
            f"no configuration {configuration!r} of implementation {implementation!r}: {exc}"
        ) from exc
    return BenchmarkTarget(implementation, selection.configuration_ref, selection)


def cassette_dir(target: BenchmarkTarget) -> Path:
    """
    Where a target's recordings are: CASSETTE_DIR for the two-pass
    implementation (id `default`, the first benchmark recorded),
    `<CASSETTE_DIR>_<implementation>` for any other, and a
    `__<configuration>` suffix for a configuration other than the one the
    implementation's benchmark runs with.
    """
    name = CASSETTE_DIR.name
    if target.implementation != UNSUFFIXED_IMPLEMENTATION:
        name += f"_{target.implementation}"
    if target.configuration != benchmark_configuration(target.implementation):
        name += f"__{target.configuration}"
    return CASSETTE_DIR.with_name(name)


def recorded_targets() -> list[BenchmarkTarget]:
    """Every target that has a recording of at least one benchmark document."""
    implementations, configurations = pipeline_registries()
    targets = []
    for implementation, orchestrator in implementations.list_by_type(PIPELINE_TYPE).items():
        if not issubclass(orchestrator, IndividualExtractionOrchestrator):
            continue
        for configuration, _ in configurations.list_configs(PIPELINE_TYPE, implementation):
            target = resolve_target(implementation, configuration)
            if any(cassette_path(d, target).exists() for d in benchmark_documents()):
                targets.append(target)
    return targets


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


def cassette_path(document_id: str, target: BenchmarkTarget | None = None) -> Path:
    """Where a target's recording of a document is."""
    return cassette_dir(target or resolve_target()) / f"{document_id}.json"


async def extract_document(
    ontology: BenchmarkOntology,
    provider: LLMProvider,
    document_id: str,
    target: BenchmarkTarget | None = None,
) -> tuple[list[Predicted], list[PredictedRelationship]]:
    """
    Extract one benchmark document as a source and return what a proposal
    would hold: the planned individual and relationship creates.

    The run is the target's: its implementation's orchestrator, given its
    configuration (so the configuration's stage prompts are the ones sent), and
    the input the resolver gives a run of it (the configuration's model,
    temperature and output-token limit). Another model is another
    configuration, so another target with recordings of its own.
    """
    target = target or resolve_target()
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
    orchestrator = target.orchestrator(
        llm_provider=provider, extraction_service=service, config=dict(target.config)
    )
    state = IndividualExtractionState(
        run_id=str(uuid4()),
        pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
        input_data=target.run_input(
            {
                "text": source.text,
                "ontology_id": ontology.taxonomy_id,
                "headings": [
                    {"start": h.start, "title": h.title, "level": h.level} for h in source.headings
                ],
            }
        ),
    )
    result = (await orchestrator.execute(state)).result or {}
    failed = result.get("failed_chunks") or []
    if failed:
        # The run completed without what those chunks hold: not a run to score
        raise PipelineExecutionError(
            f"extraction failed for {len(failed)} chunk(s) of {document_id}: "
            f"{failed[0].get('failure_reason')}"
        )
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
    status: str  # "scored", "not_recorded", "stale" or "failed"
    score: BenchmarkScore | None = None
    calls: int = 0
    misses: int = 0
    detail: str = ""


async def replay_document(
    document_id: str, target: BenchmarkTarget | None = None
) -> DocumentResult:
    """Replay one document from a target's cassette and score it."""
    target = target or resolve_target()
    path = cassette_path(document_id, target)
    if not path.exists():
        return DocumentResult(document_id, "not_recorded")
    provider = CassetteLLMProvider(path)
    individuals: list[Predicted] = []
    relationships: list[PredictedRelationship] = []
    failure = ""
    try:
        individuals, relationships = await extract_document(
            benchmark_ontology(), cast(LLMProvider, provider), document_id, target
        )
    except PipelineExecutionError as exc:
        # A prompt with no recording fails its chunk, and the run with it when
        # every chunk fails; with every prompt answered, the failure is the run's own
        failure = str(exc)
    if provider.misses:
        return DocumentResult(document_id, "stale", calls=provider.calls, misses=provider.misses)
    if failure:
        return DocumentResult(document_id, "failed", calls=provider.calls, detail=failure)
    result = score(load_gold(document_id), individuals, relationships)
    return DocumentResult(document_id, "scored", result, calls=provider.calls)


async def replay_all(
    documents: list[str] | None = None, target: BenchmarkTarget | None = None
) -> list[DocumentResult]:
    """Replay the documents (all of them by default) from a target's cassettes."""
    target = target or resolve_target()
    return [await replay_document(d, target) for d in documents or benchmark_documents()]


def recorded_models(target: BenchmarkTarget, documents: list[str]) -> list[str]:
    """
    The models a target's recordings of the documents hold: every distinct
    `model` of their cassette entries. A run asks for its configuration's
    model, so for recordings that answer it this is that one model; anything
    else means the recordings were made with another.
    """
    models: set[str] = set()
    for document_id in documents:
        path = cassette_path(document_id, target)
        if not path.exists():
            continue
        entries = json.loads(path.read_text())
        models.update(
            str(entry.get("model"))
            for entry in (entries.values() if isinstance(entries, dict) else entries)
            if isinstance(entry, dict) and entry.get("model")
        )
    return sorted(models)


def summarize(
    results: list[DocumentResult], target: BenchmarkTarget | None = None
) -> dict[str, Any]:
    """
    What was run (the target's implementation, configuration and model, when
    given, and the models its recordings hold: `recorded_models`), the dev and
    holdout means, the failure counts over dev, and whether the run can be
    trusted: `status` is "scored" only when every benchmark document scored.
    A run over some of the documents is "partial": a split's mean is given only
    when all of its documents scored, so one document never stands for dev. A
    document whose extraction failed with every prompt answered is "failed".
    """
    scored = {r.document_id: r.score for r in results if r.score is not None}
    status = "scored"
    if any(r.status == "stale" for r in results):
        status = "stale"
    elif any(r.status == "not_recorded" for r in results):
        status = "not_recorded"
    elif any(r.status == "failed" for r in results):
        status = "failed"
    dev = [scored[d] for d in DEV_DOCUMENTS if d in scored]
    holdout = [scored[d] for d in HOLDOUT_DOCUMENTS if d in scored]
    whole_dev = len(dev) == len(DEV_DOCUMENTS)
    whole_holdout = len(holdout) == len(HOLDOUT_DOCUMENTS)
    if status == "scored" and not (whole_dev and whole_holdout):
        status = "partial"
    recorded = (
        {"recorded_models": recorded_models(target, [r.document_id for r in results])}
        if target
        else {}
    )
    return {
        **(target.describe() if target else {}),
        **recorded,
        "status": status,
        "documents": {r.document_id: r.status for r in results},
        "dev": mean_metrics(dev) if whole_dev else {},
        "holdout": mean_metrics(holdout) if whole_holdout else {},
        "failure_counts": failure_counts(dev) if whole_dev else {},
    }


async def record_document(document_id: str, target: BenchmarkTarget) -> DocumentResult:
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
    path = cassette_path(document_id, target)
    path.parent.mkdir(parents=True, exist_ok=True)
    recorder = RecordingLLMProvider(router, path)
    try:
        individuals, relationships = await extract_document(
            benchmark_ontology(), cast(LLMProvider, recorder), document_id, target
        )
    except PipelineExecutionError as exc:
        raise SystemExit(f"{document_id}: {exc}; nothing was saved. Record it again.") from exc
    if recorder.incomplete_count:
        raise SystemExit(
            f"{document_id}: the provider cut short or errored on {recorder.incomplete_count} of "
            f"{recorder.call_count} responses; nothing was saved. Record it again."
        )
    recorder.flush()
    result = score(load_gold(document_id), individuals, relationships)
    return DocumentResult(document_id, "scored", result, calls=recorder.call_count)


def print_results(results: list[DocumentResult], file: Any = None) -> None:
    for r in results:
        if r.score is None:
            detail = f" ({r.misses} of {r.calls} calls have no recording)" if r.misses else ""
            detail = detail or (f" ({r.detail})" if r.detail else "")
            print(f"{r.document_id:<24} {r.status}{detail}", file=file)
            continue
        m = r.score.metrics
        print(
            f"{r.document_id:<24} recall {m['recall']:.3f} (core {m['recall_core']:.3f})  "
            f"precision {m['precision']:.3f}  type accuracy {m['type_accuracy']:.3f}  "
            f"typed F1 {m['typed_f1']:.3f}  relationship recall {m['relationship_recall']:.3f}",
            file=file,
        )


def print_target(target: BenchmarkTarget, file: Any = None) -> None:
    print(
        f"target: implementation {target.implementation}, configuration {target.configuration}, "
        f"model {target.model} (cassettes: {cassette_dir(target).name}/)",
        file=file,
    )


def print_summary(summary: dict[str, Any]) -> None:
    print(f"status: {summary['status']}")
    if summary["dev"]:
        print(f"dev typed F1 {summary['dev']['typed_f1']:.3f}, found F1 {summary['dev']['f1']:.3f}")


def is_scored(summary: dict[str, Any]) -> bool:
    """Whether a run's numbers can be read: every document asked for was scored."""
    return summary["status"] in ("scored", "partial")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--document", action="append", help="A document id (repeatable); all by default"
    )
    parser.add_argument("--record", action="store_true", help="Record cassettes with the live LLM")
    parser.add_argument("--spend", action="store_true", help="Confirm --record may call the LLM")
    parser.add_argument(
        "--implementation",
        help="The implementation of individual extraction to run (the registry's default)",
    )
    parser.add_argument(
        "--configuration",
        help=(
            "The implementation's configuration to run with (the one its recordings were "
            "made with, else its default)"
        ),
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Replay every target that has recordings; exits 0 only when all of them score",
    )
    parser.add_argument("--model", help=argparse.SUPPRESS)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the summary as JSON: standard output holds the JSON and nothing else",
    )
    args = parser.parse_args()
    if args.model:
        # A recording made with another model would overwrite the configuration's
        # own and replay as stale from then on; on replay the flag did nothing
        raise SystemExit(
            "--model is not taken: a run uses its configuration's model. Register a "
            "configuration that names the model and pass --configuration; it gets a cassette "
            "folder of its own"
        )
    documents = args.document or benchmark_documents()
    # With --json the lines for people go to standard error
    progress = sys.stderr if args.json else None
    if args.all:
        if args.record or args.implementation or args.configuration:
            raise SystemExit("--all replays every recorded target: no target, no --record")
        summaries = []
        for target in recorded_targets():
            print_target(target, progress)
            results = asyncio.run(replay_all(documents, target))
            print_results(results, progress)
            summaries.append(summarize(results, target))
            if not args.json:
                print_summary(summaries[-1])
        if args.json:
            print(json.dumps({"targets": summaries}, indent=1))
        return 0 if all(is_scored(s) for s in summaries) else 2
    try:
        target = resolve_target(args.implementation, args.configuration)
    except UnknownTargetError as exc:
        raise SystemExit(str(exc)) from exc
    print_target(target, progress)
    if args.record:
        if not args.spend:
            raise SystemExit(
                "--record calls the live LLM, which costs money; pass --spend to go ahead"
            )
        results = [asyncio.run(record_document(d, target)) for d in documents]
    else:
        results = asyncio.run(replay_all(documents, target))
    print_results(results, progress)
    summary = summarize(results, target)
    if args.json:
        print(json.dumps(summary, indent=1))
    else:
        print_summary(summary)
    return 0 if is_scored(summary) else 2


if __name__ == "__main__":
    sys.exit(main())
