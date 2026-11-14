# Cassette Re-Recording Guide

## Context
The extraction service prompts were updated to implement two-pass extraction (individual identification + relationship derivation). This invalidated all existing cassettes, requiring them to be re-recorded with the new prompts.

Previously, cassettes were incorrectly "rehashed" using `rehash_cassettes.py`, which added new prompt-hash keys but reused stale response content from before the prompt changes. This approach is fundamentally broken because:
1. New prompts produce different responses from the LLM
2. Copying old responses under new hash keys defeats the purpose of cassette-based replay
3. The tournament produces 0.0 F1 scores when cassette hashes don't match current prompts

## Proper Re-Recording Procedure

### Prerequisites
- An API key for OpenAI, Anthropic, or OpenRouter (configured in `config.json`)
- Python venv activated in `local-server/`
- All dependencies installed (`pip install -r requirements.txt`)

### Step 1: Record Default Pipeline Cassettes

The default pipeline uses the phase-1 model (Google Gemini Flash via OpenRouter) for cost efficiency.

```bash
cd local-server
python scripts/record_default_cassettes.py --dry-run  # Preview what will be recorded
python scripts/record_default_cassettes.py --record   # Make real LLM calls
```

This records one cassette per scenario (17 scenarios total), each containing both:
- Pass 1 response: Individual identification and typing
- Pass 2 response: Relationship derivation

Cost estimate: ~2-5 USD (depends on model and token usage)

### Step 2: (removed) Grounded Pipeline Cassettes

The `grounded_v1` tournament variant (NLP-grounded typing) and its recorder
(`scripts/record_grounded_cassettes.py`) were removed on 2026-11-14: its cassettes had been
deleted when the prompts gained source spans (#1243), so it never registered, and its last scored
result was a STAY. There is nothing to record for it. The benchmark's cassettes are recorded with
`python scripts/benchmark_replay.py --record --spend --implementation <id> --configuration <ref>`
(see `experiments/README.md`).

### Step 3: Run Quality Tournament

Once cassettes are recorded, run the tournament to verify the accept gate passes:

```bash
python scripts/quality_tournament.py --pipeline individual --passes 1 --restarts 0
```

This evaluates both variants (`default` and `open_v1`) on the dev/holdout split and produces:
- A scoreboard markdown digest
- Per-variant error reports  
- Metrics telemetry (JSONL format)

The accept gate passes when:
- `default` variant has strict-F1 ≥ 0.941 AND soft-F1 ≥ 0.952 on the dev split
- No regression from the baseline

### Step 4: Commit Results

```bash
git add tests/integration/fixtures/cassettes/individual_extraction_default/
git commit -m "Re-record cassettes with updated two-pass extraction prompts"

python scripts/quality_tournament.py --pipeline individual | tee tournament_results.txt
git add experiments/reports/
git commit -m "Run quality tournament with re-recorded cassettes — accept gate results"
```

## Verification Checklist

- [ ] All cassette files in `individual_extraction_default/` exist
- [ ] Each cassette has the expected number of hash entries (newly recorded cassettes should have 1-4 entries, all with real LLM responses)
- [ ] Tournament runs without CassetteStaleError or hash-mismatch errors
- [ ] Tournament produces a markdown scoreboard and per-variant error reports
- [ ] `default` variant metrics meet the promotion thresholds:
  - Strict-F1 ≥ 0.941
  - Soft-F1 ≥ 0.952

## Troubleshooting

### CassetteStaleError
This error means the current prompt hash doesn't match any key in the cassette file. Solutions:
1. Ensure you ran the recording script after any prompt changes
2. Check that the ontology context is correctly resolved (e.g., DR spec checkout exists)
3. Delete problematic cassettes and re-record them with `--only <scenario>`

### Tournament produces 0.0 F1 scores
This usually means cassette replay is failing. Check:
1. Cassette files exist for all required scenarios
2. Prompt generation matches what was recorded (check ontology resolution, model override, temperature)
3. No recent prompt changes without corresponding cassette re-recording

### LLM API Errors
If the recorder encounters API rate limits or authentication errors:
1. Check that your API key is correctly configured in `config.json`
2. For OpenRouter models, ensure you have sufficient credits
3. Use `--only <scenario>` to resume recording from a specific scenario

## Design Rationale

The two-pass extraction design (issue #1141, karpathy_loop_design.md §7):
1. Pass 1 identifies and grounds individuals to ontology classes
2. Pass 2 derives relationships using a closed vocabulary of ontology-defined predicates

This design improves predicate accuracy (0.34 relation_not_derived → 0.04) by constraining the LLM to the ontology's permitted vocabulary, while pre-recording cassettes keeps the tournament fast and reproducible (no live LLM calls during evaluation).

The cassette recording infrastructure supports this by allowing:
- Controlled, one-time LLM calls during recording
- Deterministic offline replay during tournament evaluation
- Easy extension to new variants (add a new recording script, cassettes auto-register in the tournament)
