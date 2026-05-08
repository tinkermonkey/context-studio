# Agent-Driven Iteration Tooling

This document describes the benchmarking iteration loop for knowledge graph extraction pipeline improvements.

## Quick Start

From the `local-server/` directory:

```bash
# 1. Edit the experimental config
vim configs/extraction-experimental.json

# 2. Run the benchmark experiment (both datasets, auto-diff against baseline)
make benchmark-experiment PIPELINE=configs/extraction-experimental.json

# 3. Review the output summary and decision guidance

# 4. If results are broadly positive, promote the config to default
cp configs/extraction-experimental.json configs/extraction-default.json

# 5. Append entry to iteration log
vim logs/extraction-iteration-log.md
```

## How It Works

### 1. Configuration Changes

Edit `configs/extraction-experimental.json` with your hypothesis changes:

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
4. Generates cross-dataset comparison report
5. Auto-diffs current results against the baseline (`reports/baseline-comparison.json`)
6. Prints human + agent-readable summary with decision guidance

### 3. Interpreting Results

The diff summary shows:

```
📊 Dataset: text2kg-bench/wikidata-tekgen
├─ Avg F1:     0.0000 → 0.1234 (↑ +0.1234)
├─ Avg Precision: ...
├─ Avg Recall: ...
└─ Total Cost:    $0.00 → $5.43 (↓ +$5.43)
```

**Interpretation:**
- Green arrows (↑↓): Directional changes
- **F1 improvement > +0.05:** Strong signal to promote
- **F1 improvement 0-0.05:** Marginal, check for regressions
- **F1 decline < -0.05:** Investigate before promoting

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
│   └── extraction-experimental.json (iteration scratch space)
├── reports/                         (benchmark outputs, gitignored)
│   ├── extraction-experimental-tekgen.json
│   ├── extraction-experimental-webnlg.json
│   ├── extraction-experimental-comparison.json
│   └── baseline-comparison.json     (reference baseline)
├── .benchmark-cache/               (LLM response cache, gitignored)
│   └── *.json (cached responses keyed by prompt hash)
└── logs/
    └── extraction-iteration-log.md  (append-only iteration record)
```

## Workflow for Agents

Agents can drive the full loop by:

1. **Read** latest baseline from `reports/baseline-comparison.json`
2. **Read** iteration log from `logs/extraction-iteration-log.md`
3. **Hypothesis:** Form a targeted improvement (e.g., "improve recall by adding entity type hints")
4. **Edit** `configs/extraction-experimental.json`
5. **Run** `make benchmark-experiment PIPELINE=configs/extraction-experimental.json`
6. **Parse** diff output (look for F1 delta, regressions)
7. **Decision:** If broadly improved, promote and log entry
8. **Append** to iteration log with results and decision

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
