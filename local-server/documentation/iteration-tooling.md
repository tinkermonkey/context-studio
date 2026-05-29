# Agent-Driven Iteration Tooling

This document describes the benchmarking iteration loop for knowledge graph extraction pipeline improvements.

## Quick Start

From the `local-server/` directory:

```bash
# 1. Create an experimental config by copying the default as a starting point
cp configs/extraction-default.json configs/extraction-experimental.json

# 2. Edit the experimental config with your hypothesis changes
vim configs/extraction-experimental.json

# 3. Run the benchmark experiment (both datasets, auto-diff against baseline)
make benchmark-experiment PIPELINE=configs/extraction-experimental.json

# 4. Review the output summary and decision guidance

# 5. If results are broadly positive, promote the config to default
cp configs/extraction-experimental.json configs/extraction-default.json

# 6. Append entry to iteration log
vim logs/extraction-iteration-log.md
```

## How It Works

### 1. Configuration Changes

First create the experimental config by copying the default (`cp configs/extraction-default.json configs/extraction-experimental.json`), then edit it with your hypothesis changes:

```json
{
  "provider": "anthropic",
  "model": "claude-opus-4-7",
  "temperature": 0.0,
  "max_tokens": 4096,
  "system_prompt": "Your enhanced prompt here",
  "user_prompt_template": "...",
  "seed": 42
}
```

Supported parameters:
- `provider`: "anthropic" or "openai"
- `model`: Model identifier (e.g., "claude-opus-4-7")
- `temperature`: Floating-point 0.0-1.0 (controls creativity)
- `max_tokens`: Integer (max output length)
- `system_prompt`: System guidance for the model
- `user_prompt_template`: User message template (can contain `{ontology}` and `{text}` placeholders)
- `seed`: Optional integer for reproducible generation (passed to model if supported)

### 2. Run Benchmark Experiment

```bash
make benchmark-experiment PIPELINE=configs/extraction-experimental.json
```

This target:
1. Validates the pipeline config exists
2. Runs `run_benchmark.py` on **TekGen dataset** (text2kg-bench/wikidata-tekgen)
3. Runs `run_benchmark.py` on **WebNLG dataset** (text2kg-bench/dbpedia-webnlg)
4. Runs `run_canon_benchmark.py` on the **canon-software-architecture** corpus
5. Generates cross-dataset comparison report
6. Auto-diffs current results against the baseline (`reports/baseline-comparison.json`)
7. Prints human + agent-readable summary with decision guidance

To run only the canon benchmark in isolation (useful when iterating on schema
or loader changes that don't need a full TekGen/WebNLG run):

```bash
make benchmark-canon
```

### 3. Interpreting Results

The diff summary shows:

```
📊 Dataset: text2kg-bench/wikidata-tekgen
├─ Avg F1:     0.0000 → 0.1234 (↑ +0.1234)
├─ Avg Precision: ...
├─ Avg Recall: ...
└─ Total Cost:    $0.00 → $5.43 (↓ +$5.43)
```

The canon dataset adds a richer per-block:

```
📊 Dataset: canon-software-architecture
├─ Avg F1, Precision, Recall, Conformance, Cost (as above)
└─ Canon schema metrics:
    ├─ Avg node-type F1: baseline → current
    ├─ Hierarchy ratio  : baseline → current
    ├─ Multi-sense ratio: baseline → current
    ├─ Reference grnd.  : baseline → current
    ├─ Slug validity    : baseline → current
    ├─ Embedding present: baseline → current
    └─ Per node-type F1: taxonomy, concept_scheme, class, individual, property_definition
```

**Interpretation:**
- Green arrows (↑↓): Directional changes
- **TekGen/WebNLG F1 improvement > +0.05:** Strong signal to promote
- **TekGen/WebNLG F1 improvement 0-0.05:** Marginal, check for regressions
- **TekGen/WebNLG F1 decline < -0.05:** Investigate before promoting

**Canon-specific guidance:**
- **Slug validity must stay at 1.0.** Anything else means the migration
  invariant (`f319bb8dc961_add_color_column_and_require_identifier_`) is
  broken — that's a domain-purity bug, not an iteration result.
- **Hierarchy ratio must stay at 1.0** when the canon is loaded via the demo
  loader. Drops here indicate the loader regressed on `parent_class_id`
  resolution.
- **Multi-sense ratio movement is signal.** Today the demo loader doesn't
  materialise `lexical_senses` on `property_definitions`, so the ratio is
  near 0. A change that lifts it above zero is a real improvement; a change
  that drops it from a non-zero baseline is a regression.
- **Reference grounding rate** is bounded by the canon's `expected_external_refs`
  coverage. Don't expect ≥0.9 — the canon documents only the references it
  has high confidence in.
- **Per-node-type F1** lines surface which specific node type regressed. A
  drop in `class` F1 with everything else at 1.0 is a class-loader bug; a
  drop in `property_definition` F1 means properties aren't being persisted
  correctly.

**Cross-dataset rule for promotion:** an extractor change should improve
canon avg-F1 *and* maintain TekGen/WebNLG F1 within ±0.02 to be promoted.
A canon improvement at the cost of a Text2KG regression is not net positive;
both are valid baselines.

### 4. Promote to Default (if improved)

```bash
cp configs/extraction-experimental.json configs/extraction-default.json
git add configs/extraction-default.json
git commit -m "Promote extraction config: improved F1 from X to Y"
```

### 5. Update Iteration Log

Add a new entry to `logs/extraction-iteration-log.md` using the template:

```markdown
## YYYY-MM-DD — <short description of change>

- Config change: <what changed>
- Hypothesis: <why this should improve things>
- TekGen F1: <before> → <after>
- WebNLG F1: <before> → <after>
- Cost (TekGen): $X | Cost (WebNLG): $Y
- Hallucination rate: <value or N/A>
- Decision: promote to default / revert / investigate further
```

## Caching

### How It Works

- **Cache key:** SHA256 hash of (system_prompt + user_prompt_template + model + temperature)
- **Cache location:** `.benchmark-cache/` (gitignored)
- **Invalidation:** Automatic when config changes (different hash)

Benefits:
- Reruns are nearly free (cached responses used)
- Reproducible results across machines (same prompt = same response)
- Deterministic baselines (seed + cache = exact reproduction)

### Using Deterministic Seeds

To reproduce a prior run exactly:

1. Set the `seed` parameter in the config to a specific integer
2. Run `make benchmark-experiment`
3. Cached responses + seed ensure identical results

Example:
```json
{
  "provider": "anthropic",
  "model": "claude-opus-4-7",
  "seed": 42,
  "temperature": 0.0,
  ...
}
```

### Clearing Cache

To force recomputation (e.g., if underlying data changed):

```bash
rm -rf .benchmark-cache
make benchmark-experiment PIPELINE=configs/extraction-experimental.json
```

## File Organization

```
local-server/
├── configs/
│   ├── extraction-default.json      (production config)
│   └── extraction-experimental.json (created on-demand for iterations, not in git)
├── datafiles/
│   └── canon/
│       └── software_architecture/   (canon corpus: canon.json + paper_*.json × 15)
├── benchmark/
│   └── canon_metrics.py             (canon-specific pure metric functions)
├── reports/                         (benchmark outputs, gitignored)
│   ├── extraction-experimental-tekgen.json
│   ├── extraction-experimental-webnlg.json
│   ├── extraction-experimental-canon.json
│   ├── extraction-experimental-comparison.json
│   └── baseline-comparison.json     (reference baseline)
├── .benchmark-cache/               (LLM response cache, gitignored)
│   └── *.json (cached responses keyed by prompt hash)
└── logs/
    └── extraction-iteration-log.md  (append-only iteration record)
```

### Canon Iteration Lockstep

The canon corpus at `datafiles/canon/software_architecture/` is the **single
source of truth** for both:

1. The pipeline test cycle (`tests/integration/pipelines/`,
   `tests/integration/extraction_layers/`)
2. The demo dataset loader (`adapters/demo/canon_loader.py`,
   `POST /api/v1/admin/demo-datasets/software-architecture/load`)
3. The canon benchmark (`scripts/run_canon_benchmark.py` → this iteration loop)

When you discover that the canon gold itself needs to change (a paper was
miscategorised, a class was named wrong, a relationship was missing), update
the canon JSON and immediately re-run the canon benchmark and the pipeline
tests. The same edit should fix both the demo and the benchmark — they share a
directory and that lockstep is the point. If only one moves, something is
wrong.

## Workflow for Agents

Agents can drive the full loop by:

1. **Read** latest baseline from `reports/baseline-comparison.json`
2. **Read** iteration log from `logs/extraction-iteration-log.md`
3. **Hypothesis:** Form a targeted improvement (e.g., "improve recall by adding entity type hints")
4. **Create** `configs/extraction-experimental.json` by copying `configs/extraction-default.json`
5. **Edit** `configs/extraction-experimental.json` with hypothesis changes
6. **Run** `make benchmark-experiment PIPELINE=configs/extraction-experimental.json`
7. **Parse** diff output (look for F1 delta, regressions)
8. **Decision:** If broadly improved, promote and log entry
9. **Append** to iteration log with results and decision

## Cost Management

Both datasets stay within $50 USD budget per run (via stratified sampling in `run_benchmark.py`).

Monitor costs:
- Each full run prints `Total Cost: $X.XX`
- Comparison diffs show cost deltas
- Cache reduces re-runs to near-zero cost

## Troubleshooting

### Pipeline config not found
```
Error: Pipeline config not found: configs/extraction-experimental.json
```

Make sure the config file exists and path is correct.

### Make target fails
```bash
# Ensure you're in local-server/ directory
cd local-server
make benchmark-experiment PIPELINE=configs/extraction-experimental.json
```

### Results not matching baseline
If you expect results to match a prior run but don't:
- Check that `seed` parameter matches prior run
- Verify the exact `system_prompt` and `user_prompt_template` match
- Clear cache if underlying data changed: `rm -rf .benchmark-cache`

### No baseline found
First run initializes `reports/baseline-comparison.json` from current results.
Subsequent runs compare against this baseline automatically.

## Integration with CI/CD

Future iterations of this workflow can integrate with CI/CD:
- Automated nightly benchmarks
- Regression detection (F1 drop > threshold)
- Auto-promotion on sustained improvement
- Metrics dashboard for monitoring F1 trajectory

## References

- **Iteration Log:** `logs/extraction-iteration-log.md`
- **Benchmark Script:** `scripts/run_benchmark.py`
- **Comparison Script:** `scripts/compare_benchmarks.py`
- **Diff Script:** `scripts/diff_benchmarks.py`
- **Makefile:** `Makefile`
- **Cache Module:** `adapters/llm/prompt_cache.py`
