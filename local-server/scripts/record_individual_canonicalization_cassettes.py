"""
Record LLM cassettes for the open_v1 individual-extraction label-canonicalization call.

The `open_v1` canonicalization stage issues one cheap LLM call per document,
mapping each extracted individual's snake_case label to a canonical ontology
title chosen from vector-retrieved candidates (see
domain/pipelines/individual_extraction/open_orchestrator.py). Loop A/B never
makes live LLM calls, so the tournament replays these calls from cassettes.

This script records one cassette per scenario under
tests/integration/fixtures/cassettes/individual_canonicalization/, wiring the
exact same eval ontology (scripts/eval_ontology.build_eval_ontology) and real
embedding service the tournament grounds against, so the canonicalization
prompt — and therefore its cassette hash — matches at replay time. Scenarios
whose ontology does not resolve (or that surface no candidate titles) make no
LLM call and get no cassette; the stage self-skips for them at replay too.

SAFETY: with no flags (or `--dry-run`) it makes no LLM call, builds no
ontology and writes nothing: it prints which scenarios it would run, the model
and the cassette paths. Recording calls the live LLM, which costs money, and
overwrites the committed cassettes: it needs both `--record` and `--spend`.

Usage (from local-server/, venv active):
    python scripts/record_individual_canonicalization_cassettes.py                   # dry run
    python scripts/record_individual_canonicalization_cassettes.py --record --spend  # LIVE

Recording requires a live LLM provider (OPENAI_API_KEY, ANTHROPIC_API_KEY, or
OPENROUTER_API_KEY). Re-run only when the canonicalization prompt or the eval
ontology vocabulary changes.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import cast
from uuid import uuid4

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.embedding.caching_embedding_service import CachingEmbeddingService
from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from adapters.llm.provider_router import LLMProviderRouter
from adapters.nlp.spacy_processor import SpacyNLPProcessor
from config import get_settings
from domain.ontology.ports import OntologyRepository
from domain.pipelines.entities import PipelineType
from domain.pipelines.individual_extraction.orchestrator import (
    IndividualExtractionState,
)
from scripts import benchmark_replay
from scripts.eval_ontology import build_eval_ontology
from scripts.quality_tournament import scenario_input
from tests.integration.pipelines._harness.cassettes import RecordingLLMProvider
from tests.integration.pipelines._harness.dataset_split import (
    DR_BOOTSTRAP_SCENARIOS,
    INDIVIDUAL_EXTRACTION_SCENARIOS,
    WAVE4_INFORMAL_SCENARIOS,
)

_CASSETTE_DIR = (
    Path(__file__).parent.parent
    / "tests"
    / "integration"
    / "fixtures"
    / "cassettes"
    / "individual_canonicalization"
)
_CASSETTE_PREFIX = "individual_canon_"

_SCENARIOS = (
    list(INDIVIDUAL_EXTRACTION_SCENARIOS)
    + list(DR_BOOTSTRAP_SCENARIOS)
    + list(WAVE4_INFORMAL_SCENARIOS)
)


def _real_llm_provider() -> LLMProviderRouter:
    """Build the live provider router from configured API keys, or exit if none set."""
    llm_config = get_settings().llm
    if not (
        llm_config.openai_api_key or llm_config.anthropic_api_key or llm_config.openrouter_api_key
    ):
        print(
            "ERROR: no LLM API key configured. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, "
            "or OPENROUTER_API_KEY to record canonicalization cassettes."
        )
        raise SystemExit(1)
    return LLMProviderRouter(
        openai_api_key=llm_config.openai_api_key,
        anthropic_api_key=llm_config.anthropic_api_key,
        openrouter_api_key=llm_config.openrouter_api_key,
    )


async def _record() -> int:
    nlp = SpacyNLPProcessor()
    if not nlp.is_ready():
        print("ERROR: spaCy model not loaded. Run: python -m spacy download en_core_web_sm")
        return 1
    embedding = CachingEmbeddingService(SentenceTransformerEmbedding())
    eval_repo, eval_index = build_eval_ontology(embedding)
    real_provider = _real_llm_provider()
    # The run's model, temperature and output-token limit are the open_v1
    # default configuration's (the resolver's), as the tournament replays them;
    # never the corpus fixture's pinned model
    selection = _selection()
    config = {**selection.config, "llm_canonicalization": True}

    _CASSETTE_DIR.mkdir(parents=True, exist_ok=True)
    recorded = 0
    for scenario in _SCENARIOS:
        provider = RecordingLLMProvider(real_provider, cassette_path_for(scenario))
        orch = selection.implementation(
            llm_provider=provider,
            nlp_processor=nlp,
            embedding_service=embedding,
            schema_index=eval_index,
            config=config,
            ontology_repo=cast(OntologyRepository, eval_repo),
        )
        state = IndividualExtractionState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            input_data=selection.run_input(scenario_input(scenario)),
        )
        await orch.execute(state)
        if provider._recordings:
            provider.flush()
            recorded += 1
            print(f"  recorded {scenario} ({len(provider._recordings)} call(s))")
        else:
            print(f"  skipped  {scenario} (no canonicalization call)")

    print(f"\nrecorded {recorded} cassette(s) under {_CASSETTE_DIR}")
    return 0


def _selection():
    """What the recording runs: open_v1's default configuration, through the resolver."""
    return benchmark_replay.pipeline_resolver().resolve(benchmark_replay.PIPELINE_TYPE, "open_v1")


def cassette_path_for(scenario: str) -> Path:
    """Where a scenario's canonicalization cassette is."""
    return _CASSETTE_DIR / f"{_CASSETTE_PREFIX}{scenario}.json"


def print_plan() -> None:
    """The dry run: what a recording would run and write. No LLM call, no ontology build."""
    model = _selection().parameters.get("model")
    print("DRY RUN -- no LLM calls will be made. Pass --record --spend to record for real.\n")
    print(f"cassette directory: {_CASSETTE_DIR}\n")
    for scenario in _SCENARIOS:
        print(f"  {scenario:<38} -> {cassette_path_for(scenario).name}")
    print(
        f"\nWould run {len(_SCENARIOS)} scenario(s), at most one live LLM call each "
        "(a scenario with no candidate titles makes none), and overwrite their cassettes."
    )
    print(f"Model: {model}, from open_v1's default configuration.")


def main(argv: list[str] | None = None) -> int:
    """Print the plan, or record canonicalization cassettes with --record --spend."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print what would be recorded (the default)"
    )
    parser.add_argument(
        "--record", action="store_true", help="Record with the live LLM (costs money)"
    )
    parser.add_argument("--spend", action="store_true", help="Confirm --record may call the LLM")
    args = parser.parse_args(argv)
    if args.record and args.dry_run:
        parser.error("--record and --dry-run are opposites")
    if not args.record:
        print_plan()
        return 0
    if not args.spend:
        raise SystemExit("--record calls the live LLM, which costs money; pass --spend to go ahead")
    return asyncio.run(_record())


if __name__ == "__main__":
    raise SystemExit(main())
