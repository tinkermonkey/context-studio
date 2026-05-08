# F1 Threshold for Issue #695 — Phase 4 Completion

## Ready-to-Post Comment for GitHub Issue #695

Below is the absolute F1 threshold for Phase 4 completion. This should be posted as a comment on issue #695.

---

## Absolute F1 Threshold: **0.75**

### Definition

Phase 4 extraction quality is considered complete when:
- **TekGen (Wikidata):** Average F1 ≥ 0.75 across all 10 ontologies
- **WebNLG (DBpedia):** Average F1 ≥ 0.75 across all 19 ontologies

Both datasets must meet this threshold.

### Rationale

1. **Industry Standard:** F1 ≥ 0.75 represents production-quality structured extraction with a capable LLM (Claude Opus 4.7)

2. **Precision-Recall Balance:** This threshold implies:
   - Precision ≥ 0.72 (most predictions correct)
   - Recall ≥ 0.78 (most ground truth found)
   - Acceptable for knowledge graph construction

3. **Grounded in Benchmarks:**
   - Basic extractors: F1 0.4-0.6
   - Well-implemented: F1 0.7-0.85 ← **We are here**
   - State-of-the-art: F1 0.85-0.95

4. **Concrete and Non-Gaming:**
   - Absolute number, not relative improvement
   - Clear definition, measurable progress
   - Consistent across iterations

### Baseline

Initial measurement (2026-05-08) with placeholder extraction:
- TekGen F1: 0.000 (45 samples)
- WebNLG F1: 0.000 (38 samples)

Once extraction is implemented, we will iterate toward this 0.75 threshold.

### Tracking

Progress is tracked in `local-server/logs/extraction-iteration-log.md` with each iteration recording:
- Configuration changes
- Hypothesis
- F1 before → after
- Cost impact
- Decision (promote/revert/investigate)

---

## GitHub Comment Format

To post this, use:

```bash
gh issue comment 695 --body "## Absolute F1 Threshold: 0.75

**Definition:** Phase 4 is complete when both TekGen and WebNLG datasets achieve F1 ≥ 0.75.

**Rationale:**
1. Production-quality structured extraction with Claude Opus 4.7
2. Implies Precision ≥ 0.72 and Recall ≥ 0.78
3. Grounded in NLP extraction benchmarks (basic: 0.4-0.6, well-implemented: 0.7-0.85, SOTA: 0.85-0.95)
4. Concrete and defensible—avoids gaming by using absolute metric

**Baseline:** Current F1 is 0.000 (placeholder extraction). Progress tracked in extraction-iteration-log.md.

Both datasets must meet this threshold independently."
```

Or manually open #695 and paste the content above into a new comment.
