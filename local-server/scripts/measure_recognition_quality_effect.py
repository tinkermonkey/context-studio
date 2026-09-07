#!/usr/bin/env python
"""
Recognition A/B measurement for individual extraction (issue #1137, Phase 5).

Quantifies whether the recognition stage changes extraction quality by running
the existing open_v1 quality corpus (QUALITY_SCENARIOS) through the same
strict/soft-F1 + failure-stage error-report harness
(tests/integration/pipelines/_harness/error_report.py --
test_quality_individual_extraction_open.py::test_open_v1_soft_metrics_and_error_report
runs this exact harness with recognition off today) twice:

  - 'recognition off': the open_v1 rule-mode pipeline exactly as that test
    runs it -- no recognition wired in. This is the existing baseline.
  - 'recognition on': the same raw triples, additionally passed through
    CascadeIndividualRecognizer over a SqliteIndividualVectorIndex (the real
    production recognition adapter -- see adapters/recognition/
    individual_recognizer.py), applied per scenario the same way
    ExtractionService._recognize_individuals resolves mentions during
    extraction: distinct individual mentions (case-insensitive) are offered to
    the recognizer against a graph that starts empty for that scenario and
    accumulates as its own mentions are minted, so a later surface-variant
    mention of an earlier one can resolve to it.

Writes one error report pair (JSON + markdown digest, the existing harness
output format) per configuration under experiments/reports/, then prints the
label_mismatch and strict/soft-F1 deltas between the two runs. Introduces no
new metric -- every number comes from _harness/error_report.py and
_harness/metrics.py, unchanged.

Usage (from local-server/, venv active):
    python scripts/measure_recognition_quality_effect.py
"""

import asyncio
import copy
import json
import os
import sys

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from adapters.nlp.spacy_processor import SpacyNLPProcessor
from adapters.persistence.sqlite.individual_vector_index import (
    SqliteIndividualVectorIndex,
)
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.recognition.individual_recognizer import CascadeIndividualRecognizer
from domain.ontology.entities import Class, ConceptScheme, Individual, Taxonomy
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
from tests.fixtures.pipeline_fixtures import load_expected_output, load_fixture
from tests.integration.pipelines._harness.dataset_split import split_for
from tests.integration.pipelines._harness.error_report import (
    ScenarioReport,
    build_missed_triples,
    generate_run_id,
    write_report,
)
from tests.integration.pipelines._harness.metrics import (
    candidate_recall,
    label_accuracy,
    predicate_recall,
    soft_precision_recall_f1,
)
from tests.integration.pipelines.test_quality_individual_extraction import (
    QUALITY_SCENARIOS,
    compute_quality_metrics,
    extract_triple_key,
)

_EXPERIMENTS_REPORTS_DIR = Path(__file__).parent.parent / "experiments" / "reports"


async def _run_raw_triples(orchestrator, scenario: str) -> list[dict]:
    """Run open_v1 against one scenario's fixture; return its raw triples, unmodified."""
    fixture = load_fixture("individual_extraction", scenario)
    state = IndividualExtractionState(
        run_id=str(uuid4()),
        pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
        input_data=dict(fixture),
    )
    result_state = await orchestrator.execute(state)
    return (result_state.result or {}).get("triples", [])


def _recognize_scenario_triples(triples: list[dict], embedding) -> list[dict]:
    """
    Route one scenario's own raw triples through the real recognition adapter.

    Mirrors ExtractionService._recognize_individuals: a distinct individual
    mention (case-insensitive) is offered to CascadeIndividualRecognizer
    against this scenario's own graph, which starts empty and accumulates as
    the scenario's mentions are minted -- a resolved mention adopts the
    matched node's canonical title; an unresolved one mints a new node (under
    a single placeholder class, since open_v1 rule mode emits no class
    grounding) and is indexed for later mentions in the same scenario to
    match against. Returns a deep copy; the input is untouched.
    """
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    repo = SQLiteOntologyRepository(session_factory)

    taxonomy = Taxonomy(id=str(uuid4()), identifier="recognition_probe", title="Recognition probe")
    repo.save_taxonomy(taxonomy)
    scheme = ConceptScheme(
        id=str(uuid4()),
        identifier="recognition_probe_scheme",
        taxonomy_id=taxonomy.id,
        title="Recognition probe scheme",
    )
    repo.save_concept_scheme(scheme)
    placeholder_class = Class(
        id=str(uuid4()),
        identifier="individual",
        concept_scheme_id=scheme.id,
        taxonomy_id=taxonomy.id,
        title="Individual",
        description="Untyped extracted individual (open_v1 rule mode emits no class grounding)",
    )
    repo.save_class(placeholder_class)

    index = SqliteIndividualVectorIndex(session_factory, embedding)
    recognizer = CascadeIndividualRecognizer(
        individual_index=index, embedding_service=embedding, llm=None
    )

    relabeled = copy.deepcopy(triples)
    resolved: dict[str, tuple[str, str]] = {}
    for triple in relabeled:
        for role in ("subject", "object"):
            node = triple.get(role, {})
            if node.get("kind") != "individual":
                continue
            label = (node.get("label") or "").strip()
            if not label:
                continue
            key = label.lower()
            if key not in resolved:
                match = recognizer.recognize(label=label, context="", class_ids=[])
                if match is not None:
                    resolved[key] = (match.individual_id, match.title)
                else:
                    new_id = str(uuid4())
                    repo.save_individual(
                        Individual(id=new_id, class_ids=[placeholder_class.id], title=label)
                    )
                    index.index_individual(new_id, label, None)
                    resolved[key] = (new_id, label)
            node["id"], node["label"] = resolved[key]
    return relabeled


async def _build_reports(
    orchestrator, embedding, embed_fn, recognize: bool
) -> list[ScenarioReport]:
    """Build the ScenarioReport list for QUALITY_SCENARIOS, exactly like the existing
    open_v1 error-report test, optionally routing each scenario's raw triples through
    recognition first."""
    reports = []
    for scenario in QUALITY_SCENARIOS:
        actual_triples = await _run_raw_triples(orchestrator, scenario)
        if recognize:
            actual_triples = _recognize_scenario_triples(actual_triples, embedding)

        fixture_input = load_fixture("individual_extraction", scenario)
        expected_output = load_expected_output("individual_extraction", scenario)
        expected_triples = expected_output.get("result", {}).get("triples", [])

        expected_keys = [extract_triple_key(t) for t in expected_triples]
        actual_keys = [extract_triple_key(t) for t in actual_triples]

        strict = compute_quality_metrics(expected_triples, actual_triples)
        soft = soft_precision_recall_f1(expected_keys, actual_keys, embed_fn)

        reports.append(
            ScenarioReport(
                scenario=scenario,
                split=split_for(scenario),
                strict={
                    "precision": strict["precision"],
                    "recall": strict["recall"],
                    "f1": strict["f1"],
                },
                soft={
                    "precision": soft.precision,
                    "recall": soft.recall,
                    "f1": soft.f1,
                },
                candidate_recall=candidate_recall(expected_keys, actual_keys, embed_fn),
                predicate_recall=predicate_recall(expected_keys, actual_keys, embed_fn),
                label_accuracy=label_accuracy(expected_keys, actual_keys, embed_fn),
                missed_triples=build_missed_triples(
                    fixture_input.get("text", ""), expected_keys, actual_keys, embed_fn
                ),
            )
        )
    return reports


def _print_metric_delta(label: str, baseline: float, recognition: float) -> None:
    delta = recognition - baseline
    print(f"{label:<24} off={baseline:.4f}  on={recognition:.4f}  delta={delta:+.4f}")


async def _amain() -> int:
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

    @lru_cache(maxsize=None)
    def _cached_embed(label: str) -> tuple:
        return tuple(embedding.embed(label))

    def embed_fn(label: str) -> list:
        return list(_cached_embed(label))

    orchestrator = OpenIndividualExtractionOrchestrator(
        llm_provider=None,
        nlp_processor=nlp,
        embedding_service=embedding,
        schema_index=None,
        config=get_open_v1_config(),
    )

    print(f"\n== baseline: recognition off ({len(QUALITY_SCENARIOS)} scenarios) ==")
    baseline_reports = await _build_reports(orchestrator, embedding, embed_fn, recognize=False)
    baseline_run_id = f"{generate_run_id()}_recognition_off"
    baseline_json, _baseline_md = write_report(
        baseline_run_id, baseline_reports, _EXPERIMENTS_REPORTS_DIR
    )
    print(f"   error report: {baseline_json}")

    print(f"\n== recognition on ({len(QUALITY_SCENARIOS)} scenarios) ==")
    recognition_reports = await _build_reports(orchestrator, embedding, embed_fn, recognize=True)
    recognition_run_id = f"{generate_run_id()}_recognition_on"
    recognition_json, _recognition_md = write_report(
        recognition_run_id, recognition_reports, _EXPERIMENTS_REPORTS_DIR
    )
    print(f"   error report: {recognition_json}")

    baseline_payload = json.loads(baseline_json.read_text())
    recognition_payload = json.loads(recognition_json.read_text())

    print("\n== recognition effect on the error-report corpus (#1137 Phase 5) ==")
    baseline_stage_counts = baseline_payload["failure_stage_counts"]
    recognition_stage_counts = recognition_payload["failure_stage_counts"]
    for stage in sorted(set(baseline_stage_counts) | set(recognition_stage_counts)):
        off = baseline_stage_counts.get(stage, 0)
        on = recognition_stage_counts.get(stage, 0)
        print(f"{stage:<24} off={off}  on={on}  delta={on - off:+d}")

    for split in ("dev_mean", "holdout_mean"):
        for metric in ("strict_f1", "soft_f1"):
            _print_metric_delta(
                f"{split}.{metric}",
                baseline_payload[split][metric],
                recognition_payload[split][metric],
            )

    print(f"\nbaseline (recognition off) report:    {baseline_json}")
    print(f"recognition-enabled report:            {recognition_json}")
    return 0


def main() -> int:
    return asyncio.run(_amain())


if __name__ == "__main__":
    raise SystemExit(main())
