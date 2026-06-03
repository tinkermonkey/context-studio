# Human Evaluation Tools

Interactive tools for rating pipeline candidates from refinement pipelines (`schema_node_definition_refinement` and `schema_node_connection_refinement`).

## Overview

The human evaluation workflow consists of two steps:

1. **`rate.py`**: Interactive CLI that fetches pipeline runs from the API and presents candidates for human rating
2. **`aggregate.py`**: Aggregates ratings into metrics per configuration and writes to `_metrics/`

## Installation

Requires `requests` library:

```bash
pip install requests
```

## Quick Start

### Step 1: Rate Candidates

```bash
python scripts/human_eval/rate.py \
  --pipeline definition_refinement \
  --rater "john@example.com" \
  --output _ratings/human_eval.jsonl
```

Options:
- `--pipeline`: One of `definition_refinement` or `connection_refinement` (required)
- `--rater`: Rater identifier, e.g., username or email (required)
- `--api-url`: Base URL of the API (default: `http://localhost:8000`)
- `--output`: Output JSONL file (default: `_ratings/human_eval.jsonl`)
- `--skip-duplicate`: Skip candidates already rated by this rater
- `--verbose`: Verbose logging

The interactive CLI will:
1. Fetch completed runs for the specified pipeline
2. For each run, display candidates one at a time
3. Prompt for rating: **[a]ccept**, **[r]evise**, **[j]reject**, **[s]kip**, or **[q]uit**
4. Optionally collect a rationale for the rating
5. Append a JSONL row per rating without overwriting existing entries

### Step 2: Aggregate Ratings

After ratings have been collected, aggregate them into metrics:

```bash
python scripts/human_eval/aggregate.py \
  --ratings _ratings/human_eval.jsonl \
  --pipeline schema_node_definition_refinement \
  --output _metrics/human_eval.jsonl
```

Options:
- `--ratings`: Input JSONL file with ratings (default: `_ratings/human_eval.jsonl`)
- `--output`: Output JSONL file for metrics (default: `_metrics/human_eval.jsonl`)
- `--pipeline`: Pipeline type to aggregate for (default: `schema_node_definition_refinement`)
- `--api-url`: Base URL of the API for fetching run metadata (default: `http://localhost:8000`)
- `--verbose`: Verbose logging

Aggregation produces metrics per `(config_ref, config_version)`:
- `accept_rate`: Percentage of candidates rated as "accept"
- `revise_rate`: Percentage of candidates rated as "revise"
- `reject_rate`: Percentage of candidates rated as "reject"
- `n`: Total number of rated candidates

## JSONL Format

### Rating Entries

Each rating is a JSONL row with keys:

```json
{
  "schema_version": 1,
  "timestamp": "2026-06-03T12:34:56+00:00",
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "candidate_id": "candidate-0",
  "rater": "john@example.com",
  "rating": "accept",
  "rationale": "Definition is clear and well-scoped"
}
```

Multiple raters can rate the same candidate—each appends a new row rather than overwriting.

### Metrics Entries

Aggregated metrics in the standard metrics envelope:

```json
{
  "schema_version": 1,
  "timestamp": "2026-06-03T12:35:00+00:00",
  "run_id": null,
  "pipeline_type": "schema_node_definition_refinement",
  "scenario": "human_evaluation",
  "model": "human_eval",
  "config_ref": "default",
  "config_version": 1,
  "mode": "human_eval",
  "source": "human_eval",
  "duration_ms": 0.0,
  "tokens_in": 0,
  "tokens_out": 0,
  "metrics": {
    "accept_rate": 0.85,
    "revise_rate": 0.10,
    "reject_rate": 0.05
  }
}
```

## Querying Combined Metrics

To join automated metrics with human-eval metrics in DuckDB:

```sql
-- Load automated and human-eval metrics
WITH automated AS (
  SELECT * FROM read_json_auto('_metrics/schema_node_definition_refinement.jsonl')
  WHERE source = 'automated'
),
human_eval AS (
  SELECT * FROM read_json_auto('_metrics/human_eval.jsonl')
  WHERE source = 'human_eval'
)

-- Join on (config_ref, config_version)
SELECT
  a.config_ref,
  a.config_version,
  a.pipeline_type,
  a.timestamp AS auto_timestamp,
  h.timestamp AS human_timestamp,
  a.metrics.mean_cosine AS auto_mean_cosine,
  h.metrics.accept_rate AS human_accept_rate,
  h.metrics.revise_rate AS human_revise_rate,
  h.metrics.reject_rate AS human_reject_rate
FROM automated a
FULL OUTER JOIN human_eval h
  ON a.config_ref = h.config_ref
  AND a.config_version = h.config_version
ORDER BY a.config_version DESC;
```

## Workflow Example

```bash
# 1. Run pipelines and generate candidates
# (pipelines execute and create runs)

# 2. Rate candidates (multiple raters)
python scripts/human_eval/rate.py \
  --pipeline definition_refinement \
  --rater "alice@example.com" \
  --output _ratings/human_eval.jsonl

python scripts/human_eval/rate.py \
  --pipeline definition_refinement \
  --rater "bob@example.com" \
  --output _ratings/human_eval.jsonl

# 3. Aggregate all ratings
python scripts/human_eval/aggregate.py \
  --ratings _ratings/human_eval.jsonl \
  --pipeline schema_node_definition_refinement \
  --output _metrics/human_eval.jsonl

# 4. Query combined metrics
duckdb <<EOF
WITH automated AS (
  SELECT * FROM read_json_auto('_metrics/schema_node_definition_refinement.jsonl')
  WHERE source = 'automated'
),
human_eval AS (
  SELECT * FROM read_json_auto('_metrics/human_eval.jsonl')
  WHERE source = 'human_eval'
)
SELECT a.config_version, a.metrics.mean_cosine, h.metrics.accept_rate
FROM automated a
LEFT JOIN human_eval h ON a.config_version = h.config_version
ORDER BY a.config_version DESC;
EOF
```

## Multi-Rater Agreement

The JSONL format naturally supports multiple raters rating the same candidate:

```jsonl
{"run_id": "run-1", "candidate_id": "cand-0", "rater": "alice", "rating": "accept"}
{"run_id": "run-1", "candidate_id": "cand-0", "rater": "bob", "rating": "revise"}
{"run_id": "run-1", "candidate_id": "cand-0", "rater": "charlie", "rating": "accept"}
```

Aggregation computes rates across all ratings, capturing overall consensus and diversity of opinion.

## Troubleshooting

### API Connection Issues

If you get connection errors:
1. Verify the API is running: `curl http://localhost:8000/api/pipelines/types`
2. Check `--api-url` is correct
3. Ensure firewall allows connections

### Missing Runs

If no runs are found:
1. Verify pipelines have executed and completed
2. Check pipeline type matches: `definition_refinement` → `schema_node_definition_refinement`
3. List available runs: `curl http://localhost:8000/api/pipelines/runs?pipeline_type=schema_node_definition_refinement`

### Metadata Fetch Failures

If run metadata cannot be fetched from API:
1. Verify the API is running and accessible
2. Check pipeline runs are completed and have output_summary data

## API Reference

### GET /api/pipelines/runs

Fetch pipeline runs with filters:

```bash
curl "http://localhost:8000/api/pipelines/runs?pipeline_type=schema_node_definition_refinement&status=completed&limit=50"
```

Query parameters:
- `pipeline_type`: Filter by type
- `status`: Filter by status (completed, failed, etc.)
- `limit`: Maximum results (1-500)
- `offset`: Pagination offset

### GET /api/pipelines/runs/{run_id}/candidates

Fetch candidates for a run:

```bash
curl "http://localhost:8000/api/pipelines/runs/{run_id}/candidates"
```

Returns list of candidate objects with `id`, `label`, `proposed_definition`, `confidence`, etc.
