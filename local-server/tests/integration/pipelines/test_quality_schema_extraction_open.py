"""
Quality measurement for the open_v1 schema extraction implementation (rule mode).

Runs the OPEN spaCy pipeline (open extraction → cluster → PascalCase synthesis)
end-to-end through the SAME quality-metric path as the default implementation,
fully deterministically and OFFLINE (no LLM, no network). It asserts a valid
output contract and an honest rule-mode baseline, and prints the metric table.

Rule mode is a free, deterministic baseline that does NOT meet the production
class_jaccard>=0.60 floor — exact-string-match against hand-labeled CamelCase
ground truth requires the llm/hybrid synthesis modes (recorded cassettes) and
closed-loop knob tuning. This test pins the baseline and proves the open
pipeline assembles the correct contract; the floor itself is driven by Phase 6.
"""

import os
import sys

# Force HuggingFace/transformers to use the local cache only — the embedding
# model is already downloaded; this avoids the integration conftest's network block.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from uuid import uuid4

from adapters.clustering.sklearn_clusterer import SklearnClusterer
from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from adapters.nlp.spacy_processor import SpacyNLPProcessor
from domain.pipelines.entities import PipelineType
from domain.pipelines.schema_extraction.configurations.open_v1 import get_open_v1_config
from domain.pipelines.schema_extraction.open_orchestrator import (
    OpenSchemaExtractionOrchestrator,
)
from domain.extraction.open_extraction import RelationCandidate
from domain.pipelines.schema_extraction.orchestrator import (
    CandidateClass,
    SchemaExtractionState,
)
from tests.fixtures.pipeline_fixtures import load_expected_output, load_fixture
from tests.integration.pipelines.test_quality_schema_extraction import (
    QUALITY_SCENARIOS,
    compute_quality_metrics,
)

# Honest rule-mode baseline (well below the 0.60 production floor, which needs
# llm/hybrid synthesis + cassettes + closed-loop tuning).
RULE_MODE_MEAN_CLASS_JACCARD_FLOOR = 0.30


def _pipeline_input(scenario: str) -> dict:
    fixture = load_fixture("schema_extraction", scenario)
    pipeline_input = dict(fixture)
    if "text" in pipeline_input and "documents" not in pipeline_input:
        pipeline_input["documents"] = [pipeline_input.pop("text")]
    return pipeline_input


@pytest.fixture(scope="module")
def open_orchestrator():
    nlp = SpacyNLPProcessor()
    if not nlp.is_ready():
        pytest.skip("spaCy model not installed")
    return OpenSchemaExtractionOrchestrator(
        llm_provider=None,
        nlp_processor=nlp,
        embedding_service=SentenceTransformerEmbedding(),
        clusterer=SklearnClusterer(),
        config=get_open_v1_config(),  # rule synthesis mode
    )


@pytest.mark.nlp
@pytest.mark.asyncio
async def test_open_v1_produces_valid_contract(open_orchestrator):
    """open_v1 returns the schema-extraction contract with CamelCase classes."""
    pipeline_input = _pipeline_input("distributed_systems")
    state = SchemaExtractionState(
        run_id=str(uuid4()),
        pipeline_type=PipelineType.SCHEMA_EXTRACTION,
        input_data=pipeline_input,
    )
    result_state = await open_orchestrator.execute(state)
    result = result_state.result

    assert result is not None
    assert "candidates" in result and "connections" in result
    classes = [c for c in result["candidates"] if c.get("kind") == "class"]
    assert len(classes) >= 1
    # Rule synthesis emits PascalCase labels (no spaces, leading uppercase).
    for cls in classes:
        label = cls["label"]
        assert label and label[0].isupper() and " " not in label
        assert 0.0 <= cls["confidence"] <= 1.0


@pytest.mark.nlp
@pytest.mark.asyncio
async def test_open_v1_rule_mode_baseline(open_orchestrator):
    """Measure open_v1 rule-mode across all scenarios; pin the honest baseline."""
    rows = []
    for scenario in QUALITY_SCENARIOS:
        pipeline_input = _pipeline_input(scenario)
        expected_output = load_expected_output("schema_extraction", scenario)
        state = SchemaExtractionState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            input_data=pipeline_input,
        )
        result_state = await open_orchestrator.execute(state)
        actual_output = {
            "status": result_state.current_status.value,
            "result": result_state.result or {},
        }
        metrics = compute_quality_metrics(expected_output, actual_output)
        rows.append((scenario, metrics))
        # Every scenario must produce at least one class candidate.
        assert any(
            c.get("kind") == "class" for c in (result_state.result or {}).get("candidates", [])
        ), f"{scenario} produced no class candidates"

    mean_class_jaccard = sum(m["class_jaccard"] for _, m in rows) / len(rows)

    print("\n── open_v1 rule-mode quality (offline, deterministic) ──")
    print(f"{'scenario':<28} class_jac  prop_jac  conn_ovl  brier")
    for scenario, m in rows:
        print(
            f"{scenario:<28} {m['class_jaccard']:>8.2f}  {m['property_jaccard']:>8.2f}  "
            f"{m['connection_overlap']:>8.2f}  {m['brier']:>6.2f}"
        )
    print(f"{'MEAN class_jaccard':<28} {mean_class_jaccard:>8.3f}  (floor for prod: 0.60)")

    assert mean_class_jaccard >= RULE_MODE_MEAN_CLASS_JACCARD_FLOOR, (
        f"open_v1 rule-mode mean class_jaccard {mean_class_jaccard:.3f} fell below the "
        f"baseline {RULE_MODE_MEAN_CLASS_JACCARD_FLOOR}"
    )


# ---------------------------------------------------------------------------
# _build_relations — connections must survive (regression guard, model-free)
# ---------------------------------------------------------------------------


def _orchestrator_no_models():
    return OpenSchemaExtractionOrchestrator(
        llm_provider=None,
        nlp_processor=None,
        embedding_service=None,
        clusterer=None,
        config=get_open_v1_config(),
    )


def test_build_relations_matches_classes_via_lemmas():
    # Class labels come from lemmas (ConsensusAlgorithm); the relation refs are
    # raw plural surface phrases. The lemma-based match must still connect them.
    classes = [CandidateClass(label="ConsensusAlgorithm"), CandidateClass(label="StateAgreement")]
    rel = RelationCandidate(
        subject="consensus algorithms",
        predicate="ensures",
        object="state agreements",
        subject_index=0,
        verb_index=1,
        object_index=2,
        sentence_index=0,
        subject_lemmas=("consensus", "algorithm"),
        object_lemmas=("state", "agreement"),
    )
    properties, connections = _orchestrator_no_models()._build_relations([rel], classes)

    assert len(connections) == 1
    assert connections[0].subject_ref == "ConsensusAlgorithm"
    assert connections[0].predicate == "ensures"
    assert connections[0].object_ref == "StateAgreement"
    # The predicate also becomes a property definition.
    assert [p.label for p in properties] == ["ensures"]


def test_build_relations_drops_unmatched_relations():
    classes = [CandidateClass(label="ConsensusAlgorithm")]
    rel = RelationCandidate(
        subject="foo",
        predicate="bars",
        object="baz",
        subject_index=0,
        verb_index=1,
        object_index=2,
        sentence_index=0,
        subject_lemmas=("foo",),
        object_lemmas=("baz",),
    )
    properties, connections = _orchestrator_no_models()._build_relations([rel], classes)
    assert connections == []
    assert properties == []
