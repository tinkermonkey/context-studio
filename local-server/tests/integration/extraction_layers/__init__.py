"""Per-layer isolation tests for the 4-layer extraction pipeline.

Each test module exercises one layer (`domain.extraction.layers.{kg_context,
llm_extract, nlp_gap, reference}`) in isolation against the software-
architecture canon, so a regression in one layer is localised rather than
masked by the orchestrator returning *something*.
"""
