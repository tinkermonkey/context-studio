# Cassette Re-Recording Guide for Phase 3

This guide explains how to re-record LLM cassettes after prompt changes in the extraction pipeline.

## Background

Phase 3 updates the extraction prompts to include verbatim-quote instructions:
- Pass-1 prompt: directs model to return exact verbatim substrings in `provenance.raw`
- Pass-2 prompt: clarifies that relationship quotes should span both entities and connecting clause

Since cassette keys are hashes of `system_prompt|user_prompt|model|temperature|seed`, **any prompt change invalidates existing cassettes**. The cassettes must be re-recorded with live LLM calls to capture responses for the new prompt hashes.

## Cassette Sets Affected

The prompt changes affect both cassette directories:
1. **individual_extraction_default**: Pass-1 (individual typing) responses
   - Location: `tests/integration/fixtures/cassettes/individual_extraction_default/`
   - Scenarios: 14 (dev + bootstrap + wave4)
   - Model: google/gemini-3-flash-preview (via OpenRouter)

2. **individual_grounded_typing**: Pass-1 (NLP-grounded typing confirms) + Pass-2 (relationship derivation)
   - Location: `tests/integration/fixtures/cassettes/individual_grounded_typing/`
   - Scenarios: 16 (dev + bootstrap + wave4 + arxiv)
   - Model: claude-opus-4-7 (via configured provider)

## Prerequisites

### API Credentials
You must have API credentials configured in `config.json`:

```json
{
  "llm": {
    "openai_api_key": "sk-...",          // Optional: for OpenAI
    "anthropic_api_key": "sk-ant-...",   // Optional: for Anthropic
    "openrouter_api_key": "sk-or-..."    // Optional: for OpenRouter (used by default)
  }
}
```

For the default pipeline, OpenRouter credentials are required. For grounded_v1, use Anthropic (claude-opus-4-7).

### Environment Setup
```bash
cd local-server
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e .
```

## Recording Cassettes

### Step 1: Dry Run (No Costs)
Before recording, inspect the recording plan:

```bash
# Default pipeline cassettes (14 scenarios)
python scripts/record_default_cassettes.py

# Grounded variant cassettes (16 scenarios)  
python scripts/record_grounded_cassettes.py
```

This prints:
- Scenario names and ontology contexts
- Model that will be used
- Cassette output paths
- Total number of live LLM calls

### Step 2: Record Cassettes (Incurs Costs)
Once you've reviewed the plan, record with actual LLM calls:

```bash
# Record default pipeline (14 calls)
python scripts/record_default_cassettes.py --record

# Record grounded variant (variable cost - multiple calls per scenario)
python scripts/record_grounded_cassettes.py --record
```

**Cost Note**: 
- Default: ~14 calls (google/gemini-3-flash-preview, very cheap)
- Grounded: ~50-100 calls (claude-opus-4-7 per chunk, more expensive)

### Step 3: Verify Cassettes
Check that cassettes were written:

```bash
ls -la tests/integration/fixtures/cassettes/individual_extraction_default/ | wc -l
# Should show 14+ files (plus .gitkeep)

ls -la tests/integration/fixtures/cassettes/individual_grounded_typing/ | wc -l  
# Should show 16+ files (plus .gitkeep)
```

### Step 4: Re-record Specific Scenarios (Optional)
If only certain scenarios changed:

```bash
# Re-record just a few scenarios
python scripts/record_default_cassettes.py --record --only arxiv_byzantine_fault_tolerance arxiv_cloud_platform
```

## Running Quality Tournament

After cassettes are re-recorded, run the quality tournament:

```bash
python scripts/quality_tournament.py --pipeline individual
```

### Acceptance Criteria
The tournament must pass:
- **Dev strict-F1 ≥ 0.917** (no regression)
- **Dev soft-F1 ≥ 0.928** (no regression)

If the metrics regress below baseline:
1. Review the prompt changes
2. Iterate on wording if needed
3. Re-record cassettes
4. Re-run tournament

### Output
Tournament results are written to:
- `experiments/reports/quality_tournament_<timestamp>.json`
- `experiments/reports/quality_tournament_<timestamp>.md` (human-readable)

## Commit Cassettes

After successful tournament run:

```bash
# Stage the re-recorded cassettes
git add tests/integration/fixtures/cassettes/individual_extraction_default/
git add tests/integration/fixtures/cassettes/individual_grounded_typing/

# Stage tournament results
git add experiments/reports/

# Commit
git commit -m "Phase 3: Re-record cassettes after prompt updates

- Pass-1: added verbatim-quote instruction
- Pass-2: added relationship-spanning guidance
- Re-recorded via record_default_cassettes.py (14 scenarios, google/gemini-3-flash)
- Re-recorded via record_grounded_cassettes.py (16 scenarios, claude-opus-4-7)
- Tournament results: dev strict-F1 X.XXX / soft-F1 X.XXX (no regression)

Co-Authored-By: <Your Name>"
```

## Troubleshooting

### CassetteStaleError in Tests
If tests fail with "No recorded response for prompt hash X...", cassettes are stale:
- Prompts have changed since last recording
- Cassettes must be re-recorded with live LLM calls
- See "Recording Cassettes" section above

### API Key Errors
- "no LLM provider configured": Set API keys in config.json
- "Invalid API key": Check key is correct and active
- "Rate limit exceeded": Wait and retry, or use cheaper model

### Cassette Size Explosion
If cassettes become very large:
- Check if scenarios have duplicate responses (shouldn't happen)
- Verify cassette directory doesn't have stale files from old recording runs
- Use `--only` flag to re-record specific scenarios

## Summary Checklist

- [ ] Review prompt changes in `domain/extraction/services.py`
- [ ] Configure API credentials in `config.json`
- [ ] Run dry-run: `python scripts/record_default_cassettes.py`
- [ ] Run dry-run: `python scripts/record_grounded_cassettes.py`
- [ ] Record cassettes: `python scripts/record_default_cassettes.py --record`
- [ ] Record cassettes: `python scripts/record_grounded_cassettes.py --record`
- [ ] Verify cassette files exist
- [ ] Run tournament: `python scripts/quality_tournament.py --pipeline individual`
- [ ] Verify metrics don't regress (strict-F1 ≥ 0.917, soft-F1 ≥ 0.928)
- [ ] Commit cassettes and tournament results
- [ ] Run backend tests: `pytest tests/` (to verify no regressions)
- [ ] Verify domain purity: `python scripts/check_domain_imports.py`
