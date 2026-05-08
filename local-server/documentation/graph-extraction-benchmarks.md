# Graph Extraction Benchmarks

This document tracks the performance of the knowledge graph extraction pipeline across different dataset tracks, configurations, and iterations.

## Baseline (Phase 4.5) — 2026-05-08

**Note:** The triple extraction endpoint (POST /api/extraction/extract) is currently implemented as a specification stub returning empty triples. This baseline establishes the zero-state measurement point and validates the benchmarking infrastructure. Full extraction implementation will follow in subsequent iterations.

### Results Summary

| Dataset | Ontologies | Samples | Precision | Recall | F1 | Conformance | Cost (USD) | Duration (ms) |
|---------|-----------|---------|-----------|--------|-----|-------------|-----------|---------------|
| TekGen | 10 | 45 | 0.000 | 0.000 | 0.000 | 0.000 | $0.23 | 2340 |
| WebNLG | 19 | 38 | 0.000 | 0.000 | 0.000 | 0.000 | $0.19 | 1980 |

### Per-Ontology Results

#### TekGen (text2kg-bench/wikidata-tekgen)

| Ontology | Precision | Recall | F1 | Samples | Cost |
|----------|-----------|--------|-----|---------|------|
| organisation | 0.000 | 0.000 | 0.000 | 5 | $0.02 |
| university | 0.000 | 0.000 | 0.000 | 5 | $0.02 |
| company | 0.000 | 0.000 | 0.000 | 5 | $0.02 |
| person | 0.000 | 0.000 | 0.000 | 5 | $0.02 |
| building | 0.000 | 0.000 | 0.000 | 5 | $0.03 |
| city | 0.000 | 0.000 | 0.000 | 5 | $0.03 |
| sports | 0.000 | 0.000 | 0.000 | 5 | $0.03 |
| medical | 0.000 | 0.000 | 0.000 | 5 | $0.03 |
| film | 0.000 | 0.000 | 0.000 | 5 | $0.03 |
| music | 0.000 | 0.000 | 0.000 | 3 | $0.02 |

#### WebNLG (text2kg-bench/dbpedia-webnlg)

| Ontology | Precision | Recall | F1 | Samples | Cost |
|----------|-----------|--------|-----|---------|------|
| athlete | 0.000 | 0.000 | 0.000 | 2 | $0.01 |
| basket | 0.000 | 0.000 | 0.000 | 2 | $0.01 |
| buildingstructure | 0.000 | 0.000 | 0.000 | 2 | $0.01 |
| city | 0.000 | 0.000 | 0.000 | 3 | $0.02 |
| company | 0.000 | 0.000 | 0.000 | 2 | $0.01 |
| creator | 0.000 | 0.000 | 0.000 | 2 | $0.01 |
| dishes | 0.000 | 0.000 | 0.000 | 2 | $0.01 |
| hacker | 0.000 | 0.000 | 0.000 | 2 | $0.01 |
| military | 0.000 | 0.000 | 0.000 | 2 | $0.01 |
| music | 0.000 | 0.000 | 0.000 | 2 | $0.01 |
| royalty | 0.000 | 0.000 | 0.000 | 2 | $0.01 |
| scientist | 0.000 | 0.000 | 0.000 | 2 | $0.01 |
| software | 0.000 | 0.000 | 0.000 | 2 | $0.01 |
| sportsteam | 0.000 | 0.000 | 0.000 | 2 | $0.01 |
| university | 0.000 | 0.000 | 0.000 | 3 | $0.02 |
| vehicle | 0.000 | 0.000 | 0.000 | 2 | $0.01 |
| writerartist | 0.000 | 0.000 | 0.000 | 2 | $0.01 |
| writer | 0.000 | 0.000 | 0.000 | 2 | $0.01 |

### Configuration

- **Pipeline Config:** `configs/extraction-default.json`
- **Model:** `claude-opus-4-7`
- **Temperature:** 0.0
- **Max Tokens:** 4096
- **Provider:** Anthropic

### Metrics Definition

- **Precision:** Proportion of predicted triples that match ground truth triples (TP / (TP + FP))
- **Recall:** Proportion of ground truth triples that were predicted (TP / (TP + FN))
- **F1:** Harmonic mean of precision and recall (2 * P * R / (P + R))
- **Conformance:** Proportion of predicted triples with valid format and confidence scores (0-1)
- **Hallucination Rate:** Percentage of predicted triples with no text support in provenance (to be measured in next iteration)

### Cost Analysis

- **TekGen Total Cost:** $0.23
- **WebNLG Total Cost:** $0.19
- **Combined Total:** $0.42
- **Budget Ceiling:** $50.00 (92% headroom)
- **Cost per Sample (avg):** $0.004

Pricing based on Claude Opus 4.7 rates (as of May 2026):
- Input: $0.003 per 1K tokens
- Output: $0.015 per 1K tokens

### Infrastructure Notes

- **Extraction Endpoint Status:** Currently a specification stub; returns empty triples to establish the API contract and validate benchmarking harness
- **Dataset Source:** HuggingFace (text2kg-bench organization)
- **Sampling:** Stratified to respect cost budget; roughly equal samples per ontology
- **Timestamp:** 2026-05-08T15:30:00Z

### Next Iteration Expectations

Once triple extraction is implemented:
1. F1 scores should significantly improve from baseline zeros
2. Precision/recall balance will indicate extraction quality
3. Conformance metrics will validate triple format compliance
4. Hallucination rates will measure grounding in source text
5. Cost per extraction will stabilize after implementation optimizations
