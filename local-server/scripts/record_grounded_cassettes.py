#!/usr/bin/env python
"""
One-time bootstrap recorder for the `grounded_v1` NLP-grounded typing variant's cassettes.

`scripts/quality_tournament.py`'s `_make_grounded_v1_variant()` evaluates the
NLP-grounded typing pipeline via `ExtractionService(extraction_mode="nlp_grounded")`
+ `IndividualExtractionOrchestrator` (domain/extraction/services.py, issue #1141) —
spaCy extracts noun chunks, the vector index retrieves candidate ontology classes,
and the LLM only confirms the best fit per chunk; the same relationship-derivation
pass `default` uses is then reused unchanged. Because Loop A/B never make live LLM
calls, every tournament variant must be fully replayable offline. This script
records that cassette set: it runs the variant once per corpus scenario through a
`RecordingLLMProvider`, using the SAME construction `_make_grounded_v1_variant`
uses, capturing every per-chunk confirm call and the relationship/concept-typing
calls to the standard cassette path so the tournament can replay via
`CassetteLLMProvider`.

This is one-time bootstrap setup, not a loop experiment. It reuses the existing
recording machinery verbatim -- the `RecordingLLMProvider` and the
`sha256(system|user|model|temperature|seed)` key scheme in
`tests/integration/pipelines/_harness/cassettes.py` -- but writes to a
DEDICATED directory (`cassettes/individual_grounded_typing/`), one scenario
per file.

Unlike `default` (which the tournament replays against an override model —
DEFAULT_PIPELINE_MODEL — for cost reasons), `_make_grounded_v1_variant` does
NOT override the fixture's model: it replays each scenario against whatever
`load_fixture` returns, which pins `model: claude-opus-4-7`. It DOES need to
resolve `ontology_id`, though: `ExtractionService.extract_triples()` looks up
the ontology via `OntologyRepository.get_taxonomy()`, which takes the
taxonomy's real id (a UUID) — not the fixture's symbolic identifier
("dr_spec"). This script mirrors `_make_grounded_v1_variant`'s construction
exactly (same ExtractionService(extraction_mode="nlp_grounded") +
IndividualExtractionOrchestrator wiring, same eval ontology, same
ontology_id resolution) so the recorded prompt hashes match what the
tournament will actually replay. Because it uses the real model, and issues one
LLM call per matched noun chunk (in addition to the relationship-derivation and
concept-typing calls), the true call count is much larger than one-per-scenario
-- always dry-run first to see the real count before recording.

SAFETY: the default behavior (no flag, or `--dry-run`) makes ZERO live LLM
calls. It only prints which scenarios and cassette paths would be recorded and
the model id. Live recording -- which spends real money against claude-opus-4-7,
potentially many calls per scenario -- requires the explicit `--record` flag.

Usage (from local-server/, venv active):
    python scripts/record_grounded_cassettes.py            # dry run (default, no calls)
    python scripts/record_grounded_cassettes.py --dry-run  # dry run (explicit)
    python scripts/record_grounded_cassettes.py --record   # LIVE -- spends money
"""

import argparse
import asyncio
import os
import sys
from typing import Any, cast
from uuid import uuid4

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path

from tests.fixtures.pipeline_fixtures import load_fixture
from tests.integration.pipelines._harness.dataset_split import (
    DR_BOOTSTRAP_SCENARIOS,
    INDIVIDUAL_EXTRACTION_SCENARIOS,
    RELABELED_ARXIV_SCENARIOS,
    WAVE4_INFORMAL_SCENARIOS,
)

# Cassette location for the grounded_v1 variant's calls (per-chunk typing
# confirms + relationship derivation + concept-object typing).
# One file per scenario named `individual_grounded_typing_<scenario>.json`.
_CASSETTE_DIR = (
    Path(__file__).parent.parent
    / "tests"
    / "integration"
    / "fixtures"
    / "cassettes"
    / "individual_grounded_typing"
)


def union_scenarios() -> list[str]:
    """
    Return the ordered, de-duplicated union of every corpus scenario to record.

    Union of `INDIVIDUAL_EXTRACTION_SCENARIOS` (the dev/holdout split),
    `DR_BOOTSTRAP_SCENARIOS` (Wave 1 diagnostics), `WAVE4_INFORMAL_SCENARIOS` (Wave 4 diagnostics),
    and `RELABELED_ARXIV_SCENARIOS` -- every scenario the Loop B `grounded_v1` variant will be
    replayed against. Order preserved for stable output; duplicates dropped (the lists are
    disjoint today, but the de-dup keeps this correct if that ever changes).
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for scenario in (
        list(INDIVIDUAL_EXTRACTION_SCENARIOS)
        + list(DR_BOOTSTRAP_SCENARIOS)
        + list(WAVE4_INFORMAL_SCENARIOS)
        + list(RELABELED_ARXIV_SCENARIOS)
    ):
        if scenario not in seen:
            seen.add(scenario)
            ordered.append(scenario)
    return ordered


def cassette_path_for(scenario: str) -> Path:
    """Return the standard cassette path for one scenario."""
    return _CASSETTE_DIR / f"individual_grounded_typing_{scenario}.json"


def print_plan(scenarios: list[str]) -> None:
    """
    Print the dry-run plan: no LLM calls, no ontology builds, no network.

    Lists each scenario, its cassette path, and the noun-chunk count spaCy
    finds for it (an upper bound on the per-chunk confirm calls that scenario
    will make) so the real live-call count is visible before recording.
    """
    print("DRY RUN -- no LLM calls will be made. Pass --record to record for real.\n")
    print(f"cassette directory: {_CASSETTE_DIR}\n")

    from adapters.nlp.spacy_processor import SpacyNLPProcessor

    nlp = SpacyNLPProcessor()
    nlp_ready = nlp.is_ready()

    total_chunks = 0
    for scenario in scenarios:
        fixture = dict(load_fixture("individual_extraction", scenario))
        text = fixture.get("text", "")
        chunk_count = "?"
        if nlp_ready and text:
            result = nlp.process_open(text)
            tokens = list(result.tokens)
            n = 0
            for chunk in result.noun_chunks:
                root = tokens[chunk.root_index] if 0 <= chunk.root_index < len(tokens) else None
                if root is not None and root.pos in ("NOUN", "PROPN") and not root.is_stop:
                    n += 1
            chunk_count = n
            total_chunks += n
        print(
            f"  {scenario:<38} model={fixture.get('model', '?'):<20} "
            f"~{chunk_count} noun chunk(s)\n"
            f"      -> {cassette_path_for(scenario)}"
        )

    print(
        f"\n{len(scenarios)} scenario(s). Each makes 1 relationship-derivation call "
        "+ 1 concept-typing call + up to 1 confirm call per matched noun chunk."
    )
    if nlp_ready:
        print(
            f"~{total_chunks} noun chunk(s) total across all scenarios (upper bound on "
            f"confirm calls; actual is lower -- only chunks with vector-index matches "
            f"trigger a call). Rough total live call estimate: "
            f"~{total_chunks + 2 * len(scenarios)}."
        )
    else:
        print("spaCy model not loaded -- cannot estimate noun-chunk/call counts.")
    print("Model: claude-opus-4-7 (fixture-pinned; NOT overridden, unlike `default`).")


def record_all(scenarios: list[str]) -> int:
    """
    Record the cassette set live. Makes real, billable LLM calls against claude-opus-4-7.

    Mirrors `scripts/quality_tournament.py::_make_grounded_v1_variant`'s
    `run_scenario` construction exactly -- same `ExtractionService(
    extraction_mode="nlp_grounded")` + `IndividualExtractionOrchestrator` wiring,
    same eval ontology (`scripts/eval_ontology.build_eval_ontology`), same
    ontology_id resolution (symbolic identifier -> taxonomy id) and
    un-overridden model -- so the recorded prompt hashes match what the
    tournament will replay.
    """
    from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
    from adapters.events.in_process import InProcessEventPublisher
    from adapters.nlp.spacy_processor import SpacyNLPProcessor
    from adapters.persistence.sqlite.connection import (
        create_local_db_engine,
        create_session_factory,
    )
    from adapters.persistence.sqlite.extraction_repo import SQLiteExtractionRepository
    from adapters.persistence.sqlite.extraction_run_repo import (
        SQLiteExtractionRunRepository,
    )
    from adapters.persistence.sqlite.models import Base
    from config import get_settings
    from domain.extraction.services import ExtractionService
    from domain.pipelines.entities import PipelineType
    from domain.pipelines.individual_extraction.orchestrator import (
        IndividualExtractionOrchestrator,
        IndividualExtractionState,
    )
    from scripts.eval_ontology import build_eval_ontology
    from tests.fakes.fake_reference_source import FakeReferenceSource
    from tests.integration.pipelines._harness.cassettes import RecordingLLMProvider

    settings = get_settings()
    llm_config = settings.llm
    if (
        not llm_config.openai_api_key
        and not llm_config.anthropic_api_key
        and not llm_config.openrouter_api_key
    ):
        print(
            "ERROR: no LLM provider configured. Set an API key in config.json "
            "(OpenAI, Anthropic, or OpenRouter) before recording."
        )
        return 1

    try:
        from adapters.llm.provider_router import LLMProviderRouter

        real_llm_provider = LLMProviderRouter(
            openai_api_key=llm_config.openai_api_key,
            anthropic_api_key=llm_config.anthropic_api_key,
            openrouter_api_key=llm_config.openrouter_api_key,
        )
    except ValueError as exc:
        print(f"ERROR: LLM provider initialization failed: {exc}")
        return 1

    nlp = SpacyNLPProcessor()
    if not nlp.is_ready():
        print("ERROR: spaCy model not loaded. Run: python -m spacy download en_core_web_sm")
        return 1
    embedding = SentenceTransformerEmbedding()
    try:
        embedding.embed_batch(["probe"])
    except Exception as exc:
        print(f"ERROR: embedding model probe failed ({type(exc).__name__}): {exc}")
        return 1

    eval_repo, eval_index = build_eval_ontology(embedding)

    print(f"RECORDING {len(scenarios)} scenario(s) against claude-opus-4-7.")
    print(f"cassette directory: {_CASSETTE_DIR}\n")

    _CASSETTE_DIR.mkdir(parents=True, exist_ok=True)

    recorded = 0
    skipped = 0
    for scenario in scenarios:
        cassette_path = cassette_path_for(scenario)
        recording_provider = RecordingLLMProvider(real_llm_provider, cassette_path)

        engine = create_local_db_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        session_factory = create_session_factory(engine)
        extraction_service = ExtractionService(
            ontology_repo=eval_repo,
            embedding_service=embedding,
            llm=cast(Any, recording_provider),
            nlp=nlp,
            reference_sources=[FakeReferenceSource()],
            event_publisher=InProcessEventPublisher(),
            extraction_repo=SQLiteExtractionRepository(session_factory),
            extraction_run_repo=SQLiteExtractionRunRepository(session_factory),
            schema_index=eval_index,
            extraction_mode="nlp_grounded",
        )
        orch = IndividualExtractionOrchestrator(
            llm_provider=cast(Any, recording_provider),
            extraction_service=extraction_service,
        )

        fixture = dict(load_fixture("individual_extraction", scenario))
        # Mirror _make_grounded_v1_variant's resolution exactly: extract_triples()
        # looks up ontology_id via get_taxonomy() (real id, not symbolic
        # identifier), so the fixture's symbolic "dr_spec" must be resolved to
        # the eval_repo's actual taxonomy id first, or every scenario fails with
        # "Ontology dr_spec not found" before making any LLM call.
        taxonomy = eval_repo.get_by_identifier(fixture["ontology_id"])
        if taxonomy is not None:
            fixture["ontology_id"] = taxonomy.id
        state = IndividualExtractionState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            input_data=fixture,
        )

        try:
            asyncio.run(orch.execute(state))
            recording_provider.flush()
            print(f"  recorded {scenario:<38} -> {cassette_path}")
            recorded += 1
        except Exception as exc:
            print(f"  ERROR {scenario:<35} ({type(exc).__name__}: {exc})")
            if cassette_path.exists():
                cassette_path.unlink()
                print("         (removed stale cassette file)")
            skipped += 1

    print(f"\nDone. Recorded {recorded} cassette(s); skipped/failed {skipped}.")
    if recorded == 0 or skipped > 0:
        if recorded == 0:
            print("ERROR: No cassettes were successfully recorded.")
        else:
            print("ERROR: Some cassettes failed to record; inconsistent cassette set detected.")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Record the `grounded_v1` NLP-grounded typing variant's cassette set "
            "for offline Loop B replay (karpathy_loop_design.md §4.2)."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print the plan without making LLM calls (default behavior)",
    )
    parser.add_argument(
        "--record",
        action="store_true",
        default=False,
        help="Record cassettes live (makes real LLM calls; requires --record to proceed)",
    )
    parser.add_argument(
        "--exclude",
        nargs="+",
        default=[],
        metavar="SCENARIO",
        help=(
            "Skip these scenario(s), e.g. the long Wave 1 bootstrap diagnostics "
            "(dr_bootstrap_claude, dr_bootstrap_readme) which dominate the noun-chunk "
            "count but never gate the promotion decision."
        ),
    )
    args = parser.parse_args()

    scenarios = [s for s in union_scenarios() if s not in set(args.exclude)]
    if args.record:
        return record_all(scenarios)
    else:
        print_plan(scenarios)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
