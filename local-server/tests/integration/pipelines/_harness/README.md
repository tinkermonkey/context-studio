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
