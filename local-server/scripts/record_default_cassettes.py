#!/usr/bin/env python
"""
One-time bootstrap recorder for the `default` LLM pipeline's cassettes
(karpathy_loop_design.md §4.2, #1109 Phase 2).

`scripts/quality_tournament.py`'s `build_registry()` deliberately does NOT
register the `default` LLM pipeline (`IndividualExtractionOrchestrator`)
because Loop A/B never make live LLM calls -- every tournament variant must be
fully replayable offline, and no cassettes have been recorded for
`individual_extraction` yet. This script records that cassette set: it runs the
real `default` pipeline once per corpus scenario through the same
`RecordingLLMProvider` the quality suite's live/recording branch uses (see
`tests/integration/pipelines/test_quality_individual_extraction.py::
test_live_quality_scenario`), capturing each prompt->response pair to the
standard cassette path so a future `default` variant can replay it with
`CassetteLLMProvider`.

This is one-time bootstrap setup, not a loop experiment. It reuses the existing
recording machinery verbatim -- the `RecordingLLMProvider` and the
`sha256(system|user|model|temperature|seed)` key scheme in
`tests/integration/pipelines/_harness/cassettes.py` -- but writes to a
DEDICATED directory (`cassettes/individual_extraction_default/`), separate from
the quality suite's own `cassettes/individual_extraction/` set, because this
recorder overrides the model to the phase-1 default (OpenRouter Gemini Flash)
while the quality suite records against each fixture's pinned model, and
`RecordingLLMProvider.flush()` overwrites rather than merges.

SAFETY: the default behavior (no flag, or `--dry-run`) makes ZERO live LLM
calls. It only prints which scenarios and cassette paths would be recorded, the
model id, and the total call count. Live recording -- which spends real money --
requires the explicit `--record` flag. The corpus fixtures pin
`model=claude-opus-4-7`, but recording overrides it to the phase-1 default model
(`quality_tournament.DEFAULT_PIPELINE_MODEL`, currently OpenRouter Gemini Flash);
the tournament's `default`-variant replay applies the SAME override so the
cassette keys (which include the model) match.

Usage (from local-server/, venv active):
    python scripts/record_default_cassettes.py            # dry run (default, no calls)
    python scripts/record_default_cassettes.py --dry-run  # dry run (explicit)
    python scripts/record_default_cassettes.py --record   # LIVE -- spends money
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
    WAVE4_INFORMAL_SCENARIOS,
    OntologyContext,
    ontology_context_for,
)

# Standard cassette location, matching the `cassette_dir` fixture and the live/
# recording branch of test_quality_individual_extraction.py. Do not change --
# CassetteLLMProvider replay reads from exactly this path.
# A dedicated directory, SEPARATE from the quality suite's own
# `cassettes/individual_extraction/` set. The two must not share files: the
# quality suite records against each fixture's pinned model (claude-opus-4-7),
# while this recorder overrides the model to the phase-1 default
# (OpenRouter Gemini Flash), and RecordingLLMProvider.flush() overwrites rather
# than merges — so a shared path would clobber the quality suite's cassettes.
_CASSETTE_DIR = (
    Path(__file__).parent.parent
    / "tests"
    / "integration"
    / "fixtures"
    / "cassettes"
    / "individual_extraction_default"
)


def union_scenarios() -> list[str]:
    """
    Return the ordered, de-duplicated union of every corpus scenario to record.

    Union of `INDIVIDUAL_EXTRACTION_SCENARIOS` (the dev/holdout split),
    `DR_BOOTSTRAP_SCENARIOS` (Wave 1 diagnostics), and
    `WAVE4_INFORMAL_SCENARIOS` (Wave 4 diagnostics) -- every scenario the Loop B
    `default` variant will be replayed against. Order preserved for stable
    output; duplicates dropped (the three lists are disjoint today, but the
    de-dup keeps this correct if that ever changes).
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for scenario in (
        list(INDIVIDUAL_EXTRACTION_SCENARIOS)
        + list(DR_BOOTSTRAP_SCENARIOS)
        + list(WAVE4_INFORMAL_SCENARIOS)
    ):
        if scenario not in seen:
            seen.add(scenario)
            ordered.append(scenario)
    return ordered


def cassette_path_for(scenario: str) -> Path:
    """Return the standard cassette path for one scenario."""
    return _CASSETTE_DIR / f"individual_extraction_{scenario}.json"


def _fixture_model(scenario: str) -> str:
    """Read the pinned model id from a scenario's input fixture."""
    return load_fixture("individual_extraction", scenario).get("model", "")


def print_plan(scenarios: list[str]) -> None:
    """
    Print the dry-run plan: no LLM calls, no ontology builds, no network.

    Lists each scenario, its ontology context, the model that WOULD be used
    (the phase-1 override, not the fixture-pinned model), and the cassette path
    that WOULD be written, then the total live-call count.
    """
    from scripts.quality_tournament import DEFAULT_PIPELINE_MODEL

    print("DRY RUN -- no LLM calls will be made. Pass --record to record for real.\n")
    print(f"cassette directory: {_CASSETTE_DIR}\n")

    for scenario in scenarios:
        context = ontology_context_for(scenario)
        print(
            f"  {scenario:<38} [{context.value:<11}] model={DEFAULT_PIPELINE_MODEL}\n"
            f"      -> {cassette_path_for(scenario)}"
        )

    print(
        f"\nWould record {len(scenarios)} scenario(s) "
        f"= {len(scenarios)} live LLM call(s) (one per scenario)."
    )
    print(
        f"Model: {DEFAULT_PIPELINE_MODEL} (phase-1 override of the fixture-pinned "
        "claude-opus-4-7; routes to OpenRouter)."
    )


def record_all(scenarios: list[str]) -> int:
    """
    Record the cassette set live. Makes real, billable LLM calls.

    Mirrors the recording branch of
    `test_quality_individual_extraction.py::test_live_quality_scenario`: wrap a
    real `LLMProviderRouter` in `RecordingLLMProvider`, wire it into a fresh
    `ExtractionService`, run the `default` `IndividualExtractionOrchestrator`
    once per scenario, and flush the cassette. Each scenario is graded against
    its assigned ontology context (placeholder or the imported DR spec), built
    with the same conftest helpers the quality suite uses so the recorded
    prompts -- and therefore the cassette keys -- match what the offline
    replay will produce.
    """
    from adapters.events.in_process import InProcessEventPublisher
    from adapters.llm.provider_router import LLMProviderRouter
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
    from domain.pipelines.individual_extraction import (
        IndividualExtractionOrchestrator,
        IndividualExtractionState,
    )
    from scripts.default_pipeline_ontology import (
        DefaultPipelineOntologyResolver,
        dr_spec_available,
    )
    from scripts.quality_tournament import DEFAULT_PIPELINE_MODEL
    from tests.fakes.fake_embedding_service import FakeEmbeddingService
    from tests.fakes.fake_nlp_processor import FakeNLPProcessor
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
        real_llm_provider = LLMProviderRouter(
            openai_api_key=llm_config.openai_api_key,
            anthropic_api_key=llm_config.anthropic_api_key,
            openrouter_api_key=llm_config.openrouter_api_key,
        )
    except ValueError as exc:
        print(f"ERROR: LLM provider initialization failed: {exc}")
        return 1

    # Build each required ontology context at most once via the SHARED resolver
    # the tournament replay also uses (scripts/default_pipeline_ontology), so the
    # ontology titles the recorder bakes into the cassette prompts are exactly
    # what the replay resolves — the two paths cannot drift.
    resolver = DefaultPipelineOntologyResolver()
    _dr_available = dr_spec_available()

    print(
        f"RECORDING {len(scenarios)} scenario(s) "
        f"= {len(scenarios)} live LLM call(s). Model: {DEFAULT_PIPELINE_MODEL}"
    )
    print(f"cassette directory: {_CASSETTE_DIR}\n")

    _CASSETTE_DIR.mkdir(parents=True, exist_ok=True)

    recorded = 0
    skipped = 0
    for scenario in scenarios:
        context = ontology_context_for(scenario)
        if context is OntologyContext.DR_SPEC and not _dr_available:
            print(
                f"  SKIP {scenario}: DR spec checkout not found -- cannot build the "
                "dr_spec ontology this scenario is graded against."
            )
            skipped += 1
            continue

        ontology_repo, taxonomy, _index = resolver.get(context)

        # Fresh in-memory persistence for the extraction run bookkeeping; the
        # cassette only captures the LLM prompt->response, not this DB.
        engine = create_local_db_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        session_factory = create_session_factory(engine)

        cassette_path = cassette_path_for(scenario)
        recording_provider = RecordingLLMProvider(real_llm_provider, cassette_path)

        extraction_service = ExtractionService(
            ontology_repo=ontology_repo,
            embedding_service=FakeEmbeddingService(),
            llm=recording_provider,
            nlp=FakeNLPProcessor(),
            reference_sources=[FakeReferenceSource()],
            event_publisher=InProcessEventPublisher(),
            extraction_repo=SQLiteExtractionRepository(session_factory),
            extraction_run_repo=SQLiteExtractionRunRepository(session_factory),
        )
        orchestrator = IndividualExtractionOrchestrator(
            llm_provider=recording_provider,
            extraction_service=extraction_service,
        )

        # Load the fixture and point its ontology_id at the built taxonomy so
        # `extract_triples` resolves it. The extraction prompt keys on the
        # ontology's title, not this id string, so this override does not
        # perturb the cassette key.
        fixture_input = dict(load_fixture("individual_extraction", scenario))
        fixture_input["ontology_id"] = taxonomy.id
        # Override the fixture-pinned model (claude-opus-4-7) to the phase-1
        # default model. The cassette key includes the model, so this MUST match
        # the same override in quality_tournament._make_default_variant's replay.
        fixture_input["model"] = DEFAULT_PIPELINE_MODEL

        state = IndividualExtractionState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            input_data=fixture_input,
        )

        asyncio.run(orchestrator.execute(state))
        recording_provider.flush()

        print(f"  recorded {scenario:<38} -> {cassette_path}")
        recorded += 1

    print(f"\nDone. Recorded {recorded} cassette(s); skipped {skipped}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Record the `default` individual-extraction pipeline's cassette set "
            "for offline Loop B replay (karpathy_loop_design.md §4.2)."
        )
    )
    parser.add_argument(
        "--record",
        action="store_true",
        help="Actually record live -- makes real, billable LLM calls. Without "
        "this flag the script only prints the plan and makes no calls.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the plan without recording (this is also the default when "
        "no flag is given). If both --record and --dry-run are passed, the dry "
        "run wins.",
    )
    args = parser.parse_args()

    scenarios = union_scenarios()

    if args.dry_run or not args.record:
        print_plan(scenarios)
        return 0

    return record_all(scenarios)


if __name__ == "__main__":
    raise SystemExit(main())
