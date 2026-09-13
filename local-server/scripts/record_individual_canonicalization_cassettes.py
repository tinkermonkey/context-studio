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

Usage:
    python scripts/record_individual_canonicalization_cassettes.py

Requires a live LLM provider (OPENAI_API_KEY, ANTHROPIC_API_KEY, or
OPENROUTER_API_KEY). Re-run only when the canonicalization prompt or the eval
ontology vocabulary changes.
"""

from __future__ import annotations

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
from domain.pipelines.individual_extraction.configurations.open_v1 import (
    get_open_v1_config,
)
from domain.pipelines.individual_extraction.open_orchestrator import (
    OpenIndividualExtractionOrchestrator,
)
from domain.pipelines.individual_extraction.orchestrator import (
    IndividualExtractionState,
)
from scripts.eval_ontology import build_eval_ontology
from tests.fixtures.pipeline_fixtures import load_fixture
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
    config = {**get_open_v1_config(), "llm_canonicalization": True}

    _CASSETTE_DIR.mkdir(parents=True, exist_ok=True)
    recorded = 0
    for scenario in _SCENARIOS:
        cassette_path = _CASSETTE_DIR / f"{_CASSETTE_PREFIX}{scenario}.json"
        provider = RecordingLLMProvider(real_provider, cassette_path)
        orch = OpenIndividualExtractionOrchestrator(
            llm_provider=provider,
            nlp_processor=nlp,
            embedding_service=embedding,
            schema_index=eval_index,
            config=config,
            ontology_repo=cast(OntologyRepository, eval_repo),
        )
        fixture = dict(load_fixture("individual_extraction", scenario))
        state = IndividualExtractionState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            input_data=fixture,
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


def main() -> int:
    """Record canonicalization cassettes for every individual-extraction scenario."""
    return asyncio.run(_record())


if __name__ == "__main__":
    raise SystemExit(main())
