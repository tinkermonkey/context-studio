# Shared Quality Testing Harness

This directory contains the foundational infrastructure for all pipeline quality testing in Phase B.

## Overview

The harness provides:

- **Dual-mode execution**: Cassette replay (deterministic, zero network) or live (real LLM calls)
- **LLM-level recording**: Records `(prompt_hash → LLMResponse)` pairs as compact JSON cassettes
- **Fixture loading**: Unified interface for input, expected output, and distractor fixtures
- **Metric computation**: Pure functions for P/R/F1, Jaccard, MRR, Brier, cosine, and delta overlap
- **JSONL emission**: Structured, queryable metrics artifact with versioning

## Modules

### `metrics.py`

Pure metric computation with zero infrastructure imports. Exposes:

- `precision_recall_f1(expected, actual) → PrecisionRecallF1`
- `jaccard_similarity(expected, actual) → float`
- `mean_reciprocal_rank(expected, ranked_list) → float`
- `brier_score(probabilities, labels) → float`
- `cosine_similarity(vec_a, vec_b) → float`
- `delta_set_overlap(exp_added, act_added, exp_removed, act_removed) → float`

All metrics return values in `[0, 1]` (Brier is lower-is-better; others higher-is-better).

### `cassettes.py`

LLM-level recording and replay.

- `RecordingLLMProvider`: Wraps a real LLM provider, records calls to disk, flushes on completion
- `CassetteLLMProvider`: Replays from disk, raises `CassetteStaleError` if prompt not found
- `CassetteStaleError`: Directs user to `--refresh-cassettes` flag

**Key design:**
- Prompt hash is computed from `(system_prompt, user_prompt, model, temperature, seed)`
- Cassette is a flat JSON dict: `{hash → {content, tokens_in, tokens_out, model, finish_reason}}`
- Network is blocked during cassette-mode execution via existing `block_network` fixture

### `runner.py`

Orchestrates fixture loading and pipeline execution.

- `QualityRunner`: Manages fixture loading, metric collection
- Methods: `load_fixture()`, `load_expected_output()`, `load_distractors()`

All fixture loading delegates to `tests/fixtures/pipeline_fixtures.py`, which supports:
1. Per-scenario directory layout: `{pipeline_type}/{scenario}/input.json`
2. Flat layout (legacy): `{pipeline_type}/{scenario}_input.json`

### `report.py`

JSONL metrics emission and floor gating.

- `MetricsEmitter`: Appends versioned JSONL rows to `_metrics/`
- `FloorGate`: Asserts metrics against configurable floors
- `ABReport`: Formats side-by-side A/B comparison output

## Execution Modes

### Recorded (Default)

```bash
pytest tests/integration/pipelines/test_quality_*.py
```

- Loads cassette from disk
- Network is blocked (any real call fails immediately)
- Deterministic, repeatable
- Fast (cassette replay is instant)

### Refresh Cassettes

```bash
pytest tests/integration/pipelines/test_quality_*.py --refresh-cassettes
```

- Re-records all cassettes against live LLM provider
- Requires valid API credentials
- Overwrites on-disk cassettes
- **CI never uses this flag** — cassettes are committed to repo

### Live (Real LLM)

```bash
pytest tests/integration/pipelines/test_quality_*.py -m real_llm
```

- Bypasses cassette, calls real LLM provider directly
- Requires `@pytest.mark.real_llm` marker
- Requires `@pytest.mark.external_network` marker (implies network access)
- Used for validation and multi-model A/B comparison

## Metrics Artifact

Appended to `tests/integration/fixtures/pipelines/_metrics/{pipeline_type}.jsonl`.

Each row is a versioned envelope:

```json
{
  "schema_version": 1,
  "timestamp": "2026-06-03T14:30:00Z",
  "run_id": "a1b2c3d4-...",
  "pipeline_type": "individual_extraction",
  "scenario": "fielding_rest",
  "model": "claude-sonnet-4-6",
  "config_ref": "individual-extraction-default",
  "config_version": 1,
  "mode": "cassette",
  "source": "automated",
  "duration_ms": 1234,
  "tokens_in": 500,
  "tokens_out": 200,
  "metrics": {
    "precision": 0.85,
    "recall": 0.72,
    "f1": 0.78,
    "brier": 0.18
  }
}
```

## Querying Metrics

### DuckDB

```sql
-- Latest F1 scores by pipeline and model
SELECT 
  pipeline_type, 
  model,
  timestamp,
  CAST(metrics->>'f1' AS FLOAT) AS f1,
  CAST(metrics->>'precision' AS FLOAT) AS precision
FROM read_json_auto('tests/integration/fixtures/pipelines/_metrics/*.jsonl')
WHERE pipeline_type = 'individual_extraction'
ORDER BY timestamp DESC
LIMIT 20;
```

### Combining Automated and Human-Eval Metrics

Human evaluation ratings are aggregated into metrics by `scripts/human_eval/aggregate.py` and written to `_metrics/human_eval.jsonl`. To combine automated metrics with human-eval ratings:

```sql
-- Join automated metrics with human-eval consensus
WITH automated AS (
  SELECT * FROM read_json_auto('_metrics/*.jsonl')
  WHERE source = 'automated'
),
human_eval AS (
  SELECT * FROM read_json_auto('_metrics/human_eval.jsonl')
  WHERE source = 'human_eval'
)
SELECT
  a.config_ref,
  a.config_version,
  a.pipeline_type,
  a.timestamp AS auto_timestamp,
  h.timestamp AS human_timestamp,
  CAST(a.metrics->>'mean_cosine' AS FLOAT) AS auto_metric,
  CAST(h.metrics->>'accept_rate' AS FLOAT) AS human_accept_rate,
  CAST(h.metrics->>'revise_rate' AS FLOAT) AS human_revise_rate,
  CAST(h.metrics->>'reject_rate' AS FLOAT) AS human_reject_rate
FROM automated a
LEFT JOIN human_eval h
  ON a.config_ref = h.config_ref
  AND a.config_version = h.config_version
ORDER BY a.config_version DESC;
```

### jq

```bash
# List all individual_extraction runs with their F1 scores
cat tests/integration/fixtures/pipelines/_metrics/individual_extraction.jsonl | jq -s '
  [.[] | select(.pipeline_type == "individual_extraction")]
  | sort_by(.timestamp) | reverse | .[0:5]
  | .[] | {model, scenario, f1: .metrics.f1, precision: .metrics.precision, timestamp}
'
```

```bash
# Compare two models side-by-side
cat tests/integration/fixtures/pipelines/_metrics/*.jsonl | jq -s '
  group_by(.pipeline_type) |
  map({
    pipeline: .[0].pipeline_type,
    by_model: (
      group_by(.model) |
      map({
        model: .[0].model,
        latest: (sort_by(.timestamp) | reverse[0] | .metrics)
      })
    )
  })
'
```

## Per-Scenario Fixture Layout

Quality tests use per-scenario directory structure for co-location and clarity:

```
tests/integration/fixtures/pipelines/
├── individual_extraction/
│   ├── README.md              # Provenance for all fixtures
│   ├── fielding_rest/
│   │   ├── input.json         # Pipeline input
│   │   ├── expected.json      # Expected output
│   │   └── cassette.json      # Recorded LLM responses
│   ├── shapiro_crdt/
│   │   ├── input.json
│   │   ├── expected.json
│   │   └── cassette.json
│   └── ...
├── schema_extraction/
│   ├── README.md
│   ├── microservices_api/
│   │   ├── input.json
│   │   ├── expected.json
│   │   ├── distractors.json   # Off-topic paragraphs
│   │   └── cassette.json
│   └── ...
└── ...
```

Fixture README must record:
- Source of each fixture (paper, specification, etc.)
- Manual curation notes (distractors, expected output rationale)
- Date recorded and by whom

## Integration with pytest

### Conftest Fixtures

```python
@pytest.fixture
def quality_llm_provider(request, llm_provider_mode, cassette_path, llm_provider):
    """Provides LLM provider based on execution mode."""
    # Automatic: selects cassette vs recording vs live
```

### Markers

```python
@pytest.mark.real_llm        # Run against live LLM
@pytest.mark.external_network # Allow network access (implied by real_llm)
```

### Command-line Options

```
--refresh-cassettes          # Re-record all cassettes
```

## Fixture Loading

All quality tests must use the unified fixture loading interface:

```python
from tests.fixtures.pipeline_fixtures import (
    load_fixture,
    load_expected_output,
    load_distractors,
)

# Load a fixture
input_data = load_fixture("individual_extraction", "fielding_rest")

# Load expected output
expected = load_expected_output("individual_extraction", "fielding_rest")

# Load distractors (if present)
distractors = load_distractors("individual_extraction", "fielding_rest")
```

All three functions support both flat (legacy) and per-scenario directory layouts.

## Example Quality Suite Structure

```python
import pytest
from tests.integration.pipelines._harness.runner import QualityRunner
from tests.integration.pipelines._harness.report import MetricsEmitter, FloorGate

QUALITY_FLOORS = {
    "precision": 0.60,
    "recall": 0.50,
    "f1": 0.50,
    "brier": 0.25,
}

@pytest.fixture
def quality_runner(quality_llm_provider):
    return QualityRunner(quality_llm_provider)

@pytest.fixture
def metrics_emitter():
    return MetricsEmitter(Path("tests/integration/fixtures/pipelines/_metrics"))

def test_quality_individual_extraction_across_corpus(
    quality_runner,
    metrics_emitter,
):
    """Quality gate: all fixtures must meet floor metrics."""
    floor_gate = FloorGate(QUALITY_FLOORS)
    
    scenarios = ["fielding_rest", "shapiro_crdt", "cloud_provisioning", ...]
    all_metrics = {}
    
    for scenario in scenarios:
        input_data = quality_runner.load_fixture("individual_extraction", scenario)
        expected = quality_runner.load_expected_output("individual_extraction", scenario)
        
        # Execute pipeline and compute metrics
        actual = run_extraction(input_data)
        metrics = compute_triple_metrics(expected, actual)
        all_metrics[scenario] = metrics
        
        # Emit JSONL row
        metrics_emitter.emit(
            pipeline_type="individual_extraction",
            scenario=scenario,
            model="claude-sonnet-4-6",
            config_ref="individual-extraction-default",
            config_version=1,
            metrics=metrics,
        )
    
    # Aggregate and gate
    aggregate = aggregate_metrics(all_metrics)
    floor_gate.assert_metrics(aggregate, "individual_extraction")
```

## End-to-End Chain Testing

The E2E chain test (`test_quality_e2e_chain.py`) exercises all 5 pipelines in sequence with a shared temp SQLite database:

1. schema_extraction → apply
2. individual_extraction → apply
3. schema_node_grounding → apply
4. schema_node_definition_refinement → apply
5. schema_node_connection_refinement → apply

**Fixtures:** Located at `tests/integration/fixtures/pipelines/e2e_chain/{scenario}/`
- `input.json`: 3-5 curated documents
- `expected.json`: Hand-curated final ontology with classes, properties, relationships, and external references

**Cassettes:** Per-stage LLM recordings at `_e2e_chain/{scenario}/cassettes/`
- `e2e_chain_{scenario}_schema_extraction.json`
- `e2e_chain_{scenario}_individual_extraction.json`
- `e2e_chain_{scenario}_schema_node_grounding.json`
- `e2e_chain_{scenario}_definition_refinement.json`
- `e2e_chain_{scenario}_connection_refinement.json`

**Metrics:**
- Class/property/relationship set match (binary: 1.0 if exact match, 0.0 otherwise)
- Mean description cosine similarity (≥ 0.75)
- External reference top-3 mean reciprocal rank (≥ 0.80)

**JSONL rows carry `pipeline_type = "_e2e_chain"` to distinguish from per-pipeline rows.**

## A/B Testing (Phase B.6)

The harness supports multi-model A/B comparison to evaluate LLM or configuration changes without separate test passes.

### Running A/B Comparison Across Multiple Configs

To compare two or more LLM configurations or models side-by-side:

#### 1. Record cassettes for each config

If your A/B test uses different LLM providers or configurations, record cassettes for each separately:

```bash
# Record for config A (e.g., Claude Sonnet 4.6)
pytest tests/integration/pipelines/test_quality_individual_extraction.py \
  --refresh-cassettes

# Record for config B (e.g., GPT-4 Turbo) with different cassette path
pytest tests/integration/pipelines/test_quality_individual_extraction.py \
  --refresh-cassettes \
  -k "gpt4"
```

For production A/B runs, commit both cassette sets to version control.

#### 2. Implement an A/B test

Use `QualityRunner.run_ab()` to orchestrate the comparison:

```python
import pytest
from pathlib import Path
from tests.integration.pipelines._harness.runner import QualityRunner
from tests.integration.pipelines._harness.cassettes import CassetteLLMProvider
from tests.integration.pipelines._harness.report import ABReport, FloorGate
from tests.integration.pipelines._harness.metrics import precision_recall_f1

SCENARIOS = ["fielding_rest", "shapiro_crdt", "cloud_provisioning", ...]
METRIC_FLOORS = {
    "precision": 0.60,
    "recall": 0.50,
    "f1": 0.50,
}

async def extract_individual_candidates(llm_provider, fixture_input):
    """Execute extraction pipeline, return output."""
    # Pipeline-specific orchestration
    orchestrator = IndividualExtractionOrchestrator(llm_provider=llm_provider)
    return await orchestrator.execute(fixture_input)

def compute_extraction_metrics(expected, actual):
    """Compute precision/recall/F1 from expected and actual outputs."""
    expected_ids = [e["id"] for e in expected.get("candidates", [])]
    actual_ids = [a["id"] for a in actual.get("candidates", [])]
    metrics = precision_recall_f1(expected_ids, actual_ids)
    return {
        "precision": metrics.precision,
        "recall": metrics.recall,
        "f1": metrics.f1,
    }

@pytest.mark.asyncio
async def test_quality_individual_extraction_ab(quality_runner):
    """Compare individual extraction across Claude Sonnet and GPT-4."""
    cassette_dir = Path(__file__).parent / "_cassettes"
    
    config_specs = [
        ("claude-sonnet-4.6", CassetteLLMProvider(cassette_dir / "individual_extraction_sonnet.json")),
        ("gpt4-turbo", CassetteLLMProvider(cassette_dir / "individual_extraction_gpt4.json")),
    ]
    
    results = await quality_runner.run_ab(
        config_specs=config_specs,
        scenario_list=SCENARIOS,
        pipeline_type="individual_extraction",
        executor_fn=extract_individual_candidates,
        metrics_fn=compute_extraction_metrics,
        cassette_dir=cassette_dir,
        validate_cassettes=True,
    )
    
    # Format and display comparison
    floor_gate = FloorGate(METRIC_FLOORS)
    report = ABReport.format_comparison_multi(results, floors=METRIC_FLOORS)
    print(report)
    
    # Gate on aggregate metrics per config
    for config_ref, scenario_metrics in results.items():
        aggregate_metrics = aggregate_scenarios(scenario_metrics)
        try:
            floor_gate.assert_metrics(aggregate_metrics, f"individual_extraction/{config_ref}")
        except AssertionError as e:
            print(f"\n{config_ref} failed floor gate:\n{e}")
            raise
```

#### 3. Review comparison output

The A/B report displays:
- Per-config metric columns
- Deltas between first and each subsequent config
- ✗ markers for metrics that miss configured floors

Example output:
```
Multi-Config A/B Comparison (2 configs)

Scenario              Metric               claude-sonnet-4.6 gpt4-turbo       Δ(claude - gpt4)
-------------------------------------------------------------------------------------------------------
fielding_rest        precision            0.8500           0.7800          +0.0700
fielding_rest        recall               0.9200           0.8500          +0.0700
fielding_rest        f1                   0.8800           0.8100          +0.0700
shapiro_crdt         precision            0.7200✗          0.6900✗         +0.0300
...
```

### Cassette Naming for A/B Runs

When using multiple configs with cassettes, include the config identifier in the cassette path to avoid collisions:

```python
# For config A
cassette_a = CassetteLLMProvider(
    Path("_cassettes") / "individual_extraction_sonnet.json"
)

# For config B  
cassette_b = CassetteLLMProvider(
    Path("_cassettes") / "individual_extraction_gpt4.json"
)
```

Cassettes are immutable once recorded, enabling bit-exact reproducibility and safe side-by-side comparison.

### Querying A/B Results

After an A/B run, query the JSONL metrics by `config_ref`:

```bash
# Compare latest results by config
cat tests/integration/fixtures/pipelines/_metrics/individual_extraction.jsonl | jq -s '
  group_by(.config_ref) |
  map({
    config: .[0].config_ref,
    latest_run: (sort_by(.timestamp) | reverse[0]),
    avg_f1: (map(.metrics.f1) | add / length)
  })
'
```

```sql
-- DuckDB: per-scenario comparison
SELECT
  config_ref,
  scenario,
  CAST(metrics->>"f1" AS FLOAT) as f1,
  CAST(metrics->>"precision" AS FLOAT) as precision,
  timestamp
FROM read_json_auto('_metrics/individual_extraction.jsonl')
WHERE pipeline_type = 'individual_extraction'
ORDER BY config_ref, scenario, timestamp DESC;
```

## Network Blocking

The `block_network` fixture (in parent conftest) is autouse — it blocks all network calls by default.

Tests can opt-out with `@pytest.mark.external_network`:

```python
@pytest.mark.real_llm
@pytest.mark.external_network
def test_quality_live():
    """Runs with live LLM and network access."""
```

Cassette-mode tests get network blocking automatically, enforcing the guarantee that cassettes are the only I/O path.
