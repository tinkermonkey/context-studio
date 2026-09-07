#!/usr/bin/env python
"""
One-time bootstrap recorder for the `grounded_v1` NLP-grounded typing variant's cassettes.

`scripts/quality_tournament.py`'s `build_registry()` deliberately does NOT
register the `grounded_v1` NLP-grounded typing variant
(`OpenIndividualExtractionOrchestrator` with `nlp_grounded_typing=True`)
because Loop A/B never make live LLM calls — every tournament variant must be
fully replayable offline, and no cassettes have been recorded for the per-chunk
typing confirmation calls yet. This script records that cassette set: it runs the
`grounded_v1` variant once per corpus scenario through the same
`RecordingLLMProvider` the quality suite uses, capturing each per-chunk confirm
prompt->response pair to the standard cassette path so a future `grounded_v1`
variant can replay it with `CassetteLLMProvider`.

This is one-time bootstrap setup, not a loop experiment. It reuses the existing
recording machinery verbatim -- the `RecordingLLMProvider` and the
`sha256(system|user|model|temperature|seed)` key scheme in
`tests/integration/pipelines/_harness/cassettes.py` -- but writes to a
DEDICATED directory (`cassettes/individual_grounded_typing/`), one scenario
per file.

SAFETY: the default behavior (no flag, or `--dry-run`) makes ZERO live LLM
calls. It only prints which scenarios and cassette paths would be recorded, the
model id, and the total call count. Live recording -- which spends real money --
requires the explicit `--record` flag. The per-chunk confirm calls use the same
model as the quality suite fixtures (claude-opus-4-7), not the phase-1 default;
unlike the `default` variant's LLM calls (which use Gemini Flash via OpenRouter),
grounded typing's confirm calls use the pinned fixture model so the cassette
keys match when replayed.

Usage (from local-server/, venv active):
    python scripts/record_grounded_cassettes.py            # dry run (default, no calls)
    python scripts/record_grounded_cassettes.py --dry-run  # dry run (explicit)
    python scripts/record_grounded_cassettes.py --record   # LIVE -- spends money
"""

import argparse
import asyncio
import os
import sys
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

# Cassette location for the grounded_v1 variant's per-chunk confirm calls.
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

    Lists each scenario and the cassette path that WOULD be written, then the
    total live-call count.
    """
    print("DRY RUN -- no LLM calls will be made. Pass --record to record for real.\n")
    print(f"cassette directory: {_CASSETTE_DIR}\n")

    for scenario in scenarios:
        print(f"  {scenario:<38}\n" f"      -> {cassette_path_for(scenario)}")

    print(
        f"\nWould record {len(scenarios)} scenario(s) "
        f"= ~{len(scenarios)} live LLM call(s) (one or more confirm calls per scenario)."
    )
    print("Model: claude-opus-4-7 (fixture-pinned model, same as quality suite).")


def record_all(scenarios: list[str]) -> int:
    """
    Record the cassette set live. Makes real, billable LLM calls.

    Runs the `grounded_v1` variant once per scenario through the same
    `RecordingLLMProvider` machinery the quality suite uses, capturing per-chunk
    confirm prompt->response pairs to the cassette. Each scenario is graded
    against its assigned ontology context (placeholder or the imported DR spec),
    built with the same conftest helpers the quality suite uses so the recorded
    prompts -- and therefore the cassette keys -- match what the offline
    replay will produce.
    """
    from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
    from adapters.nlp.spacy_processor import SpacyNLPProcessor
    from config import get_settings
    from domain.pipelines.entities import PipelineType
    from domain.pipelines.individual_extraction.open_orchestrator import (
        OpenIndividualExtractionOrchestrator,
    )
    from domain.pipelines.individual_extraction.orchestrator import (
        IndividualExtractionState,
    )
    from scripts.eval_ontology import build_eval_ontology
    from scripts.quality_tournament import (
        _grounded_cassette_path,
    )
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

    # Build the eval ontology once for all scenarios (grounded_v1 uses it for typing)
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

    # Base config for grounded_v1: nlp_grounded_typing=True, with reasonable defaults
    base_config = {
        "nlp_grounded_typing": True,
        "ground_to_schema": False,
        "require_schema_match": False,
        "nlp_typing_top_k": 8,
        "nlp_typing_threshold": 0.2,
        "nlp_typing_matching_mode": None,
        "llm_canonicalization": True,
        "ground_predicates": False,
        "coverage_completion": False,
        "predicate_form": "surface",
        "relation_confidence": 0.7,
        "similarity_threshold": 0.45,
        "kinds_to_search": ["class"],
        "predicate_similarity_threshold": 0.45,
    }

    print(f"RECORDING {len(scenarios)} scenario(s) " f"= ~{len(scenarios)} live LLM call(s).")
    print(f"cassette directory: {_CASSETTE_DIR}\n")

    _CASSETTE_DIR.mkdir(parents=True, exist_ok=True)

    recorded = 0
    skipped = 0
    for scenario in scenarios:
        cassette_path = _grounded_cassette_path(scenario)
        recording_provider = RecordingLLMProvider(real_llm_provider, cassette_path)

        fixture_input = dict(load_fixture("individual_extraction", scenario))

        state = IndividualExtractionState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            input_data=fixture_input,
        )

        # Use fake services except for the recording LLM provider and eval ontology
        # (grounded_v1 needs the real LLM and the eval ontology for typing)
        orch = OpenIndividualExtractionOrchestrator(
            llm_provider=recording_provider,
            nlp_processor=nlp,
            embedding_service=embedding,
            schema_index=eval_index,
            config=base_config,
            ontology_repo=eval_repo,
        )

        try:
            asyncio.run(orch.execute(state))
            recording_provider.flush()
            print(f"  recorded {scenario:<38} -> {cassette_path}")
            recorded += 1
        except Exception as exc:
            print(f"  ERROR {scenario:<35} ({type(exc).__name__}: {exc})")
            skipped += 1

    print(f"\nDone. Recorded {recorded} cassette(s); skipped/failed {skipped}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Record the `grounded_v1` NLP-grounded typing variant's cassette set "
            "for offline Loop B replay (karpathy_loop_design.md §4.2, Phase 3)."
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
    args = parser.parse_args()

    scenarios = union_scenarios()
    if args.record:
        return record_all(scenarios)
    else:
        print_plan(scenarios)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
