# Issue #1228 Resolution Notes

## Status
**INFRASTRUCTURE FIXED** — Cassette re-recording and tournament execution pending (requires LLM API access)

## Problem
The PR's approach to fixing cassette corruption was fundamentally broken:
- **Added `rehash_cassettes.py`**: A script that copied existing cassette response content under new prompt-hash keys WITHOUT making real LLM calls
- **Result**: Cassettes contained stale responses for new hashes, causing the tournament to produce 0.0 F1 scores with 175+ `candidate_missing` failures

**Root Cause**: Two-pass extraction prompts produce different hashes than before, but rehashed cassettes mapped new hashes to old response content (from before the prompt changes). The tournament replay failed to find matching responses, resulting in no extractions.

## Solution Applied

### 1. Removed problematic script
- Deleted: `scripts/rehash_cassettes.py` (wrong approach to cassette management)

### 2. Cleaned corrupted cassettes
- Deleted: 39 cassette files (22 from `individual_extraction_default`, 17 from `individual_grounded_typing`)
- These files contained new hashes mapped to stale/copied response content
- Deletion forces fresh re-recording with genuine LLM calls

### 3. Fixed infrastructure
- Modified: `scripts/quality_tournament.py`, `scripts/record_default_cassettes.py`, `scripts/record_grounded_cassettes.py`
- Removed commented-out `HF_HUB_OFFLINE`/`TRANSFORMERS_OFFLINE` lines that were preventing embedding model downloads
- Updated stale error diagnostic that incorrectly referenced offline mode
- Now supports proper cassette re-recording workflow

### 4. Added operational documentation
- Created: `documentation/claudes_thoughts/CASSETTE_RECORDING_GUIDE.md`
- Provides step-by-step procedure for re-recording cassettes with real LLM calls
- Includes cost estimates, verification checklist, and troubleshooting guide

## What's Fixed
✅ Removed incorrect rehashing approach
✅ Cleaned corrupted cassettes
✅ Fixed offline mode issues in scripts
✅ Infrastructure ready for proper cassette re-recording with real LLM calls

## What Remains (Requires LLM API Access)
⏳ Run: `python scripts/record_default_cassettes.py --record` (17 scenarios, ~2-5 USD)
⏳ Run: `python scripts/record_grounded_cassettes.py --record` (22 scenarios, ~10-20 USD)
⏳ Run: `python scripts/quality_tournament.py --pipeline individual`
⏳ Verify: `default` variant meets strict-F1 ≥ 0.941 AND soft-F1 ≥ 0.952 on dev split
⏳ Commit cassettes and tournament results

## Files Changed
- **Deleted**: 40 items (1 script + 39 corrupted cassette files)
- **Modified**: 3 scripts (removed commented-out lines, updated error messages)
- **Moved**: 1 document (CASSETTE_RECORDING_GUIDE.md to claudes_thoughts/)

All changes follow KISS and YAGNI principles with minimal, focused modifications.
