# Knowledge Graph Extraction Iteration Log

Append-only log documenting each iteration of the knowledge graph extraction pipeline. Each entry captures hypothesis, configuration changes, and measured outcomes to guide optimization decisions.

---

## 2026-05-08 — Baseline establishment (zero-state)

- Config change: None — baseline measurement against specification stub
- Hypothesis: Establish zero-state baseline with extraction endpoint as specification stub; validate benchmarking infrastructure readiness
- TekGen F1: baseline → 0.000 (50 samples, 10 ontologies)
- WebNLG F1: baseline → 0.000 (95 samples, 19 ontologies)
- Cost (TekGen): $0.00 | Cost (WebNLG): $0.00
- Hallucination rate: 0.0 (no triples predicted)
- Decision: promote to default — baseline infrastructure validated; ready for extraction implementation

---

## 2026-05-08 — Infrastructure validation (no-op configuration)

- Config change: None — verify baseline reproducibility and log structure correctness
- Hypothesis: Validate that iteration log structure and benchmarking workflow are correct before moving to extraction implementation
- TekGen F1: 0.000 → 0.000 (50 samples, 10 ontologies)
- WebNLG F1: 0.000 → 0.000 (95 samples, 19 ontologies)
- Cost (TekGen): $0.00 | Cost (WebNLG): $0.00
- Hallucination rate: 0.0 (no triples predicted)
- Decision: promote to default — log structure validated; ready for active iteration

---

## 2026-05-08 — Iteration tooling validation

This entry documents the first iteration using the agent-driven iteration tooling (issue #696).

- Config change: None — validate iteration tooling infrastructure
- Hypothesis: Iteration loop (Makefile, caching, seed support, diffing) is ready for productive use
- TekGen F1: 0.000 → 0.000 (50 samples, 10 ontologies)
- WebNLG F1: 0.000 → 0.000 (95 samples, 19 ontologies)
- Cost (TekGen): $0.00 | Cost (WebNLG): $0.00
- Hallucination rate: 0.0 (no triples predicted)
- Decision: promote to default — iteration tooling validated; ready for active extraction improvements

**Workflow used:**
```bash
cd local-server
# Edit configs/extraction-experimental.json with hypothesis changes
make benchmark-experiment PIPELINE=configs/extraction-experimental.json
# Tool automatically:
#  - Runs benchmarks on both TekGen and WebNLG
#  - Saves to reports/{date}-{config-slug}.json
#  - Diffs against baseline-comparison.json
#  - Prints human + agent-readable summary
#  - Caches LLM responses by prompt hash (invalidates on config change)
#  - Wires seed parameter through to model calls for reproducibility
# Human reviews diff output and updates this log with results
```

---

## Iteration Template

Use this template for future iterations:

```
## YYYY-MM-DD — <short description of change>

- Config change: <what changed in extraction config or pipeline>
- Hypothesis: <why this should improve things>
- TekGen F1: <before> → <after>
- WebNLG F1: <before> → <after>
- Cost (TekGen): $X | Cost (WebNLG): $Y
- Hallucination rate: <value or N/A>
- Decision: promote to default / revert / investigate further
```

---

## Phase 4 Absolute F1 Threshold

**Target Threshold:** 0.75

**Definition:** Phase 4 extraction quality is considered complete when both TekGen and WebNLG datasets achieve F1 ≥ 0.75.

**Rationale:**
1. Production-quality structured extraction with Claude Opus 4.7
2. Implies Precision ≥ 0.72 and Recall ≥ 0.78
3. Grounded in NLP extraction benchmarks (basic: 0.4-0.6, well-implemented: 0.7-0.85, SOTA: 0.85-0.95)
4. Concrete and defensible — avoids gaming by using absolute metric

**Baseline:** Current F1 is 0.000 (placeholder extraction, 2026-05-08). Progress tracked in subsequent entries.
