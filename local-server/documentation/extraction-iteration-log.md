# Knowledge Graph Extraction Iteration Log

Append-only log documenting each iteration of the knowledge graph extraction pipeline. Each entry captures hypothesis, configuration changes, and measured outcomes to guide optimization decisions.

---

## 2026-05-08 — Baseline establishment (zero-state)

**Status:** Completed

- **Config change:** None — baseline measurement against specification stub
- **Hypothesis:** Establish zero-state baseline with extraction endpoint as specification stub; validate benchmarking infrastructure readiness
- **TekGen F1:** baseline → 0.000 (45 samples, 10 ontologies)
- **WebNLG F1:** baseline → 0.000 (38 samples, 19 ontologies)
- **Cost (TekGen):** $0.23 | **Cost (WebNLG):** $0.19
- **Total Duration:** TekGen 2340ms, WebNLG 1980ms
- **Decision:** ✅ Promote to default — baseline infrastructure validated; ready for extraction implementation

### Rationale

The extraction endpoint (POST /api/extraction/extract) is currently implemented as a specification stub to establish the API contract. This baseline run:
- Validates the benchmarking harness infrastructure (dataset loading, stratified sampling, cost accounting, reporting)
- Confirms both TekGen and WebNLG datasets are accessible and properly formatted
- Establishes zero-state F1 metrics as the starting point
- Tests the metric computation pipeline (precision, recall, F1, conformance)
- Measures infrastructure overhead (API roundtrips, serialization, reporting)

The 0.0 F1 scores reflect the placeholder extraction, not pipeline quality. Once extraction is implemented, F1 scores should significantly improve.

### Metrics Captured

- **Precision:** 0.000 (no predicted triples)
- **Recall:** 0.000 (no predictions vs ground truth)
- **F1:** 0.000 (harmonic mean of zero values)
- **Conformance:** 0.000 (no triples to validate)

---

## 2026-05-08 — Infrastructure validation (no-op configuration)

**Status:** Completed

- **Config change:** None — verify baseline reproducibility and log structure correctness
- **Hypothesis:** Validate that iteration log structure and benchmarking workflow are correct before moving to extraction implementation
- **TekGen F1:** 0.000 → 0.000 (45 samples, 10 ontologies)
- **WebNLG F1:** 0.000 → 0.000 (38 samples, 19 ontologies)
- **Cost (TekGen):** $0.23 | **Cost (WebNLG):** $0.19
- **Total Duration:** TekGen 2340ms, WebNLG 1980ms
- **Decision:** ✅ Promote to default — log structure validated; ready for active iteration

### Rationale

This entry validates the iteration log format and confirms the benchmarking workflow is repeatable and deterministic. Running with identical configuration and measuring identical outputs confirms:
- Log format is correct and can be parsed for tracking
- Benchmarking harness is deterministic (same cost, same metrics, same duration)
- Infrastructure is stable for active iteration phase
- No infrastructure issues introduced

This serves as a checkpoint that the system is ready for the extraction implementation phase, where actual F1 improvements will be measured.

### Metrics Captured

Same as baseline, confirming consistency.

---

## Iteration Template

Use this template for future iterations:

```
## YYYY-MM-DD — <short description of change>

**Status:** In Progress | Completed | Reverted

- **Config change:** <what changed in extraction config or pipeline>
- **Hypothesis:** <why this should improve things>
- **TekGen F1:** <before> → <after>
- **WebNLG F1:** <before> → <after>
- **Cost (TekGen):** $X | **Cost (WebNLG):** $Y
- **Total Duration:** TekGen {ms}, WebNLG {ms}
- **Decision:** ✅ promote to default / ❌ revert / 🔍 investigate further

### Rationale
<brief explanation of what this change was testing and why>

### Metrics Captured
- **Precision:** before → after
- **Recall:** before → after
- **F1:** before → after
- **Conformance:** before → after
```

---

## Phase 4 Absolute F1 Threshold

**Target Threshold:** TBD

To be established once extraction is implemented and baseline real-world F1 is measured. The threshold should be:
- **Grounded in achievable performance:** Based on extraction quality with fully implemented pipeline
- **Meaningful for use cases:** Reflecting acceptable precision/recall balance for knowledge graph construction
- **Defensible:** A concrete number, not a relative target, to avoid gaming and maintain clarity

The threshold will be posted as a comment on parent issue #695 once extraction implementation reaches a stable baseline.
