# Phase 4: Grounded_v1 Integration Tests, Tournament Evaluation, and Tuning

## Summary

This document records the Phase 4 implementation for validating the `grounded_v1` NLP-grounded typing variant against the `default` LLM pipeline. Phase 4 consists of integration testing, definition-coverage verification, tournament evaluation, and coordinate-ascent tuning to determine whether `grounded_v1` should be promoted to `default` status.

## Completed Work

### 1. Integration Test Implementation

**File**: `tests/integration/pipelines/test_grounded_v1_integration.py`

**Tests Created**:
- `test_grounded_v1_produces_typing_triples_with_expected_shape`: Verifies end-to-end grounded_v1 execution with `FakeSchemaVectorIndex` and `FakeLLMProvider`, confirming is_a triples are produced with required fields (subject/predicate/object/confidence)
- `test_grounded_v1_config_validation`: Validates that mutually-exclusive config flags (nlp_grounded_typing + ground_to_schema) raise PipelineInputError
- `test_grounded_v1_skips_typing_when_no_schema_index`: Confirms graceful degradation when schema index is unavailable
- `test_grounded_v1_definition_preferred_matching_mode`: Verifies the key risk mitigation (definition_preferred matching mode) for candidate ranking

**Status**: ✅ All 4 tests passing

**Key Findings**:
- Grounded_v1 successfully produces is_a typing triples with confidence scores
- Config validation correctly prevents invalid configurations
- Definition-preferred matching mode is available and functional for disambiguation

### 2. Class Definition Coverage Verification

**File**: `scripts/eval_ontology_definition_coverage.py`

**Purpose**: Check whether classes in the evaluation ontology have definitions distinctive enough for embedding similarity to separate instances.

**Status**: Script created; execution requires embedding models (offline models in sandbox environment)

**Next Step**: Run in production environment with online access:
```bash
python scripts/eval_ontology_definition_coverage.py
```

**Expected Results**:
- Coverage target: ≥80% of classes should have definitions
- Average definition length: >100 characters for meaningful similarity separation
- Acceptance criterion: Coverage ≥60% to proceed with tournament

### 3. Cassette Recording Setup

**File**: `scripts/record_grounded_cassettes.py` (already exists from Phase 3)

**Current Status**: Dry-run confirmed; cassettes not yet recorded (requires live LLM calls)

**Cassette Path**: `/workspace/local-server/tests/integration/fixtures/cassettes/individual_grounded_typing/`

**Scenarios to Record**: 17 scenarios across dev/holdout, Wave 1 bootstrap, Wave 4 informal, and relabeled arxiv splits

**Recording Command** (requires LLM API keys):
```bash
python scripts/record_grounded_cassettes.py --record
```

## Next Steps for Tournament Evaluation

### Step 1: Record Cassettes
Once cassettes exist for all required scenarios, `grounded_v1` will automatically register in the variant registry (see `scripts/quality_tournament.py::build_registry()`).

### Step 2: Run Quality Tournament
```bash
python scripts/quality_tournament.py --pipeline individual
```

This will:
1. Run Loop A (coordinate ascent) to tune grounded_v1 on dev split
2. Evaluate tuned config across full corpus (dev + holdout)
3. Report metrics: strict-F1, soft-F1, candidate_recall, predicate_recall, label_accuracy

### Step 3: Analyze Tuning Results

The tuning space (`_GROUNDED_SPACE` in `quality_loop.py`) includes:
- `nlp_typing_matching_mode`: [None, "max", "definition_preferred"] ← **PRIMARY MITIGATION**
- `nlp_typing_top_k`: [5, 8, 10]
- `nlp_typing_threshold`: [0.1, 0.2, 0.3]
- Shared downstream knobs (predicate form, confidence thresholds, etc.)

**Key Signal**: Evaluate whether `definition_preferred` mode improves disambiguation over `max` mode (the highest-signal untested mitigation for the retrieval-recall risk).

### Step 4: Promotion Decision

**Baseline Metrics** (current `default` variant):
- Strict-F1: 0.941
- Soft-F1: 0.952

**Promotion Criteria**:
- `grounded_v1` MUST exceed baseline on both strict-F1 AND soft-F1 to promote
- If strict-F1 ≥ 0.941 AND soft-F1 ≥ 0.952 → **PROMOTE to `default` status**
- Otherwise → **STAY with current `default`, log findings for future iteration**

**Non-Promotion Scenarios**:
1. Definition coverage < 60% → insufficient signal for definition_preferred matching
2. Tuning finds definition_preferred mode provides < 1% improvement
3. Grounded_v1 scores < baseline on either metric
4. Retrieval-recall gap persists despite grounding

## Architecture Decisions

### Why Integration Tests Use Fakes
The integration test suite uses `FakeSchemaVectorIndex` and `FakeLLMProvider` rather than cassettes because:
1. Cassette recording requires live LLM calls (cost + latency)
2. Fake-based tests verify orchestrator logic deterministically, offline
3. Cassette-based tournament evaluation validates end-to-end quality

### Why definition_preferred is First Mitigation
Per the architecture design's risk analysis:
- Retrieval-recall risk: Top-k candidates may miss the true class
- Mitigation ranking: definition_preferred (highest signal) → max → None
- Rationale: Classes with rich definitions provide better semantic grounding
- Expected effect: Disambiguation accuracy improvement of 5-15% on retrieval-miss scenarios

### Config Mutual Exclusivity
`nlp_grounded_typing` is mutually exclusive with schema-grounding knobs because:
- NLP-grounded typing uses spaCy chunk → vector retrieval → LLM confirm
- Schema grounding uses schema-entity matching and similarity thresholding
- Both operating simultaneously creates conflicting type signals
- Enforced at config validation (IndividualOpenV1Config.from_dict)

## Testing Strategy Summary

| Layer | Scope | Status |
|-------|-------|--------|
| **Unit** | Config validation, typing logic | Passing (test_nlp_grounded_typing.py) |
| **Integration** | Orchestrator + fakes | ✅ Passing (test_grounded_v1_integration.py) |
| **System** | Cassette replay + tournament | Blocked: cassettes pending |
| **Decision** | Promotion gate | Blocked: tournament pending |

## Known Unknowns

1. **Definition Coverage**: Unknown until eval ontology is scored
2. **Definition-Preferred Effect Size**: Expected 5-15% improvement; actual gain TBD
3. **Holdout Performance**: Train-only optimization may not generalize
4. **External Scenario Performance**: Bootstrap/Wave4/arxiv scores may diverge from core

## Files Changed/Created

### New Files
- `tests/integration/pipelines/test_grounded_v1_integration.py` (integration tests)
- `scripts/eval_ontology_definition_coverage.py` (coverage verification)
- `documentation/claudes_thoughts/phase_4_grounded_v1_implementation.md` (this document)

### Modified Files
- None (grounded_v1 variant infrastructure already in place from Phase 3)

## Dependencies

**Phase 3 Work (Required for Phase 4)**:
- ✅ `grounded_v1` variant registration (quality_tournament.py::_make_grounded_v1_variant)
- ✅ Cassette path setup (scripts/record_grounded_cassettes.py)
- ✅ Orchestrator implementation (open_orchestrator.py::nlp_grounded_typing=True)

## Appendix: Coordinate Ascent Parameters

Loop A will sweep grounded_v1 with:
- Passes per restart: 2-4 (TBD based on available budget)
- Random restarts: 3-5 (for knob-space diversity)
- Primary metric: soft_f1 (tuning objective)
- Floor gate: strict_f1 ≥ baseline (regression protection)
- Seed: Fixed for reproducibility

Result will be emitted to `_metrics/quality_tournament_loopA_grounded_v1.jsonl` for provenance.
