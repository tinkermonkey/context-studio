# Phase 3: Verbatim-Quote Prompt Enhancement - Summary

## Objective
Strengthen extraction prompts to explicitly direct the LLM to return verbatim source quotes (not paraphrases) with best-effort character offsets, and validate quality shows no regression against baseline (strict-F1 ≥ 0.917, soft-F1 ≥ 0.928).

## Work Completed

### 1. Prompt Enhancements ✓

**Pass-1 Prompt (Individual Extraction)**
- Location: `domain/extraction/services.py:1618-1620`
- Addition: "For each extracted triple, set provenance.raw to an exact, verbatim substring from the source text (not a paraphrase), and set text_offset_start/text_offset_end to the best-effort character positions of that substring."
- Impact: Minimal, non-structural change (~4 lines)
- Existing instructions preserved: class grounding, predicate clamping, individual completeness rules

**Pass-2 Prompt (Relationship Extraction)**
- Location: `domain/extraction/services.py:1737-1740`
- Addition: "For each relationship triple, set provenance.raw to an exact, verbatim substring that evidences the relationship (typically spanning both entities and the connecting clause, not just a single entity mention), and set text_offset_start/text_offset_end to the best-effort character positions of that substring."
- Impact: Minimal, non-structural change (~5 lines)
- Clarification: Relationship quotes must span both entities and connecting clause, not single mentions
- Existing instructions preserved: individual and object roles, concept-object handling

### 2. Code Validation ✓

- **Domain Purity**: Verified `scripts/check_domain_imports.py` passes
- **Import Structure**: ExtractionService and all dependencies import successfully
- **Method Signatures**: No breaking changes to `_build_individual_extraction_prompt` or `_build_relationship_extraction_prompt`
- **Syntax**: No Python errors in updated code

### 3. Cassette Re-recording Infrastructure ✓

Since prompt changes invalidate cassette keys (hash = SHA256(system|user|model|temperature|seed)), cassettes must be re-recorded with live LLM calls.

**Created Supporting Documentation:**
- `CASSETTE_RECORDING_GUIDE.md`: Comprehensive guide covering:
  - Background and why cassettes must be re-recorded
  - Prerequisites (API credentials)
  - Step-by-step recording instructions for both pipelines
  - Quality acceptance criteria (0.917/0.928)
  - Troubleshooting and cost estimates

**Created Preparation Helper:**
- `scripts/prepare_cassette_recording.py`: Interactive helper that:
  - Validates API configuration
  - Displays cassette recording plan (scenarios, models, call count)
  - Provides step-by-step instructions
  - Includes troubleshooting tips
  - No API calls required (dry-run only)

### 4. Git Commits ✓

**Commit 1: Prompt Changes**
```
3449bf07 Phase 3: Add verbatim-quote instructions to extraction prompts
  - Pass-1: exact verbatim substring instruction
  - Pass-2: relationship-spanning guidance
  - Minimal changes to existing instructions
```

**Commit 2: Documentation & Tooling**
```
7441d94e Phase 3: Add cassette re-recording guide and preparation helper
  - CASSETTE_RECORDING_GUIDE.md (424 lines)
  - scripts/prepare_cassette_recording.py (interactive helper)
```

## What Still Needs to Happen

### Cassette Re-recording (Requires API Credentials)

The following scripts must be run with actual LLM API calls:

```bash
# 1. Verify setup
python scripts/prepare_cassette_recording.py

# 2. Dry-run (no costs)
python scripts/record_default_cassettes.py
python scripts/record_grounded_cassettes.py

# 3. Record cassettes (incurs costs)
python scripts/record_default_cassettes.py --record     # ~14 cheap calls
python scripts/record_grounded_cassettes.py --record    # ~50-100 expensive calls

# 4. Verify cassettes
ls tests/integration/fixtures/cassettes/individual_extraction_default/ | wc -l
ls tests/integration/fixtures/cassettes/individual_grounded_typing/ | wc -l
```

### Quality Tournament Validation

```bash
# Run tournament (requires cassettes from previous step)
python scripts/quality_tournament.py --pipeline individual

# Check results in:
# - experiments/reports/quality_tournament_*.json
# - experiments/reports/quality_tournament_*.md

# Acceptance criteria:
# - dev strict-F1 ≥ 0.917 (baseline from previous phase)
# - dev soft-F1 ≥ 0.928 (baseline from previous phase)
# - No regression from these numbers
```

### Test Execution

```bash
# Full backend test suite (after cassettes are ready)
pytest tests/ -v

# Quality-specific tests
pytest tests/integration/pipelines/test_quality_individual_extraction.py
```

## Design Alignment

This work implements the "Prompt Changes" section of the extraction pipeline architecture:
- ✓ Targeted, minimal prompt enhancements for verbatim quotes
- ✓ No structural changes to extraction logic
- ✓ Clear reasoning documented in prompts
- ✓ Cassette re-recording capability established
- ✓ Quality validation workflow understood

## Baseline Metrics (for reference)

From commit 909fd416 (previous cassette re-recording):
- **Dev Split**: strict-F1 0.917 / soft-F1 0.928
- **Holdout Split**: strict-F1 0.829 / soft-F1 0.960

These are the acceptance thresholds that the updated prompts must maintain.

## Risk Assessment

**Low Risk**: The prompt changes are:
- Minimal additions (~9 lines across both prompts)
- Clarifications of existing expected behavior (verbatim quotes from text)
- Non-structural (no change to JSON format, individual/relationship structure)
- Preservation of existing quality constraints

**Quality Regression Risk**: Mitigated by:
- Clear documentation of baseline metrics
- Cassette re-recording captures new LLM behavior before commitment
- Quality tournament validates no regression
- Iterative approach: if metrics regress, prompts can be refined before merge

## Next Steps (for whoever has API credentials)

1. Set up API credentials in `config.json`
2. Run `python scripts/prepare_cassette_recording.py` to validate setup
3. Follow step-by-step instructions from the guide
4. Re-record cassettes with `--record` flag
5. Run quality tournament to validate metrics
6. Commit cassettes and tournament results
7. Run full test suite to confirm no regressions

The infrastructure and documentation are ready; execution requires LLM API access.
