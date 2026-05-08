# Graph Extraction Benchmarks

This document tracks the performance of the knowledge graph extraction pipeline across different dataset tracks, configurations, and iterations.

## Baseline (Phase 4.5) — 2026-05-08

**Note:** The triple extraction endpoint (POST /api/extraction/extract) is currently implemented as a specification stub returning empty triples. This baseline establishes the zero-state measurement point. Since the stub returns empty predictions and all API calls incur near-zero processing time, all metrics, costs, and durations reflect zero actual extraction work. Full extraction implementation will follow in subsequent iterations.

### Results Summary

| Dataset | Ontologies | Samples | Precision | Recall | F1 | Conformance | Cost (USD) | Duration (ms) |
|---------|-----------|---------|-----------|--------|-----|-------------|-----------|---------------|
| TekGen | 10 | 50 | 0.000 | 0.000 | 0.000 | 0.000 | $0.00 | 0 |
| WebNLG | 19 | 95 | 0.000 | 0.000 | 0.000 | 0.000 | $0.00 | 0 |

### Per-Ontology Results

#### TekGen (text2kg-bench/wikidata-tekgen)

| Ontology | Precision | Recall | F1 | Samples | Cost |
|----------|-----------|--------|-----|---------|------|
| organisation | 0.000 | 0.000 | 0.000 | 5 | $0.00 |
| university | 0.000 | 0.000 | 0.000 | 5 | $0.00 |
| company | 0.000 | 0.000 | 0.000 | 5 | $0.00 |
| person | 0.000 | 0.000 | 0.000 | 5 | $0.00 |
| building | 0.000 | 0.000 | 0.000 | 5 | $0.00 |
| city | 0.000 | 0.000 | 0.000 | 5 | $0.00 |
| sports | 0.000 | 0.000 | 0.000 | 5 | $0.00 |
| medical | 0.000 | 0.000 | 0.000 | 5 | $0.00 |
| film | 0.000 | 0.000 | 0.000 | 5 | $0.00 |
| music | 0.000 | 0.000 | 0.000 | 5 | $0.00 |

#### WebNLG (text2kg-bench/dbpedia-webnlg)

| Ontology | Precision | Recall | F1 | Samples | Cost |
|----------|-----------|--------|-----|---------|------|
| athlete | 0.000 | 0.000 | 0.000 | 5 | $0.00 |
| basket | 0.000 | 0.000 | 0.000 | 5 | $0.00 |
| buildingstructure | 0.000 | 0.000 | 0.000 | 5 | $0.00 |
| city | 0.000 | 0.000 | 0.000 | 5 | $0.00 |
| company | 0.000 | 0.000 | 0.000 | 5 | $0.00 |
| creator | 0.000 | 0.000 | 0.000 | 5 | $0.00 |
| dishes | 0.000 | 0.000 | 0.000 | 5 | $0.00 |
| hacker | 0.000 | 0.000 | 0.000 | 5 | $0.00 |
| military | 0.000 | 0.000 | 0.000 | 5 | $0.00 |
| music | 0.000 | 0.000 | 0.000 | 5 | $0.00 |
| royalty | 0.000 | 0.000 | 0.000 | 5 | $0.00 |
| scientist | 0.000 | 0.000 | 0.000 | 5 | $0.00 |
| software | 0.000 | 0.000 | 0.000 | 5 | $0.00 |
| sportsteam | 0.000 | 0.000 | 0.000 | 5 | $0.00 |
| university | 0.000 | 0.000 | 0.000 | 5 | $0.00 |
| vehicle | 0.000 | 0.000 | 0.000 | 5 | $0.00 |
| writerartist | 0.000 | 0.000 | 0.000 | 5 | $0.00 |
| writer | 0.000 | 0.000 | 0.000 | 5 | $0.00 |
| explorer | 0.000 | 0.000 | 0.000 | 5 | $0.00 |

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
- **Hallucination Rate:** Percentage of predicted triples with no text support in provenance (0.0 — no triples predicted)

### Cost Analysis

- **TekGen Total Cost:** $0.00
- **WebNLG Total Cost:** $0.00
- **Combined Total:** $0.00
- **Budget Ceiling:** $50.00 (100% headroom)
- **Cost per Sample (avg):** $0.00 (no extraction processed by stub)

Pricing model based on Claude Opus 4.7 rates (as of May 2026):
- Input: $0.003 per 1K tokens
- Output: $0.015 per 1K tokens
- Note: Current stub incurs no cost as no actual API calls to LLM occur

### Infrastructure Notes

- **Extraction Endpoint Status:** Specification stub returning empty triples (no actual extraction processing)
- **Dataset Status:** HuggingFace datasets (text2kg-bench/wikidata-tekgen, text2kg-bench/dbpedia-webnlg) unavailable in test environment; zero-state baseline uses projected sample allocation
- **Sample Allocation:** Stratified with equal allocation per ontology (5 samples each) to demonstrate benchmarking infrastructure
- **Timestamp:** 2026-05-08T00:00:00Z (projected baseline, not measured runtime)

### Next Iteration Expectations

Once triple extraction is implemented:
1. F1 scores should significantly improve from baseline zeros
2. Precision/recall balance will indicate extraction quality
3. Conformance metrics will validate triple format compliance
4. Hallucination rates will measure grounding in source text
5. Cost per extraction will stabilize after implementation optimizations
