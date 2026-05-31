"""
Layer 3 (Reference Enrich) isolation tests.

Exercises `domain.extraction.layers.reference.execute`. Layer 3:
  - returns empty when text is empty
  - returns empty (with metadata reason) when there are no prior entities
  - returns empty when no reference source is available
  - emits enriched COPIES of prior entities with the SAME id and source_layer == 3
  - records source-name failures in metadata.failed_source_names
"""

from __future__ import annotations

from unittest.mock import MagicMock

from domain.extraction.entities import ExtractedEntity
from domain.extraction.layers import reference as layer3
from domain.extraction.services import ExtractionService
from domain.extraction.value_objects import LayerInput
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_llm_provider import FakeLLMProvider
from tests.fakes.fake_nlp_processor import FakeNLPProcessor
from tests.fakes.fake_reference_source import FakeReferenceSource


def _input(
    text: str = "REST is an architectural style.",
    prior=(),
) -> LayerInput:
    return LayerInput(text=text, existing_entities=tuple(prior))


def _prior(label: str = "REST", entity_type: str = "ArchitecturalStyle") -> ExtractedEntity:
    return ExtractedEntity(
        label=label,
        entity_type=entity_type,
        source_layer=1,
        confidence=0.9,
    )


class _UnavailableSource:
    """A reference source that reports itself unavailable."""

    source_name = "unavailable"

    def search(self, term, limit=10):
        raise AssertionError("Layer 3 must not call an unavailable source")

    def get_relations(self, uri, limit=10):
        return []

    def is_available(self) -> bool:
        return False


class _ExplodingSource:
    """An available source whose search() raises."""

    source_name = "exploding"

    def search(self, term, limit=10):
        raise RuntimeError("simulated upstream failure")

    def get_relations(self, uri, limit=10):
        return []

    def is_available(self) -> bool:
        return True


def test_empty_text_returns_no_entities():
    out = layer3.execute(_input(text=""), [FakeReferenceSource()])
    assert out.entities == ()
    assert out.metadata is not None and out.metadata.get("reason") == "empty_text"


def test_no_prior_entities_returns_no_enrichment():
    out = layer3.execute(_input(prior=()), [FakeReferenceSource()])
    assert out.entities == ()
    assert out.metadata is not None
    assert out.metadata.get("reason") == "no_prior_entities"
    assert out.metadata.get("enriched_count") == 0


def test_no_available_sources_returns_empty():
    prior = (_prior(),)
    out = layer3.execute(_input(prior=prior), [_UnavailableSource()])
    assert out.entities == ()
    assert out.metadata is not None
    assert out.metadata.get("reason") == "no_available_reference_sources"
    assert out.metadata.get("prior_entities") == 1


def test_enrichment_preserves_prior_entity_id_and_marks_source_layer_3():
    """Enriched copies must share the prior entity's id so dedup can merge them."""
    prior = (_prior(label="REST"),)
    fake_source = FakeReferenceSource(name="dbpedia")
    out = layer3.execute(_input(prior=prior), [fake_source])

    assert len(out.entities) == 1
    enriched = out.entities[0]
    assert enriched.id == prior[0].id, "Enriched copy must share the prior entity id"
    assert enriched.source_layer == 3
    assert enriched.label == "REST"
    assert enriched.uri == "fake://REST"
    assert enriched.description == "Fake result for REST"
    assert enriched.properties.get("reference_source") == "dbpedia"
    assert enriched.properties.get("reference_label") == "REST"


def test_multiple_prior_entities_each_get_enriched_once():
    prior = (
        _prior(label="REST"),
        _prior(label="CRDT", entity_type="DataStructure"),
        _prior(label="Microservices", entity_type="ArchitecturalStyle"),
    )
    out = layer3.execute(_input(prior=prior), [FakeReferenceSource()])

    assert len(out.entities) == 3
    enriched_ids = {e.id for e in out.entities}
    prior_ids = {p.id for p in prior}
    assert enriched_ids == prior_ids
    assert all(e.source_layer == 3 for e in out.entities)


def test_layer_stops_at_first_matching_source_per_entity():
    """Per the contract, the first matching source wins and the second is skipped."""
    prior = (_prior(label="REST"),)
    primary = FakeReferenceSource(name="primary")
    secondary = FakeReferenceSource(name="secondary")
    out = layer3.execute(_input(prior=prior), [primary, secondary])

    assert len(out.entities) == 1
    assert out.entities[0].properties.get("reference_source") == "primary"
    assert primary.call_count == 1
    assert secondary.call_count == 0, (
        "Secondary source must not be queried after the primary match"
    )


def test_exception_in_source_recorded_in_metadata_and_falls_through():
    """A source that raises must be caught and recorded; a fallback source should still enrich."""
    prior = (_prior(label="REST"),)
    out = layer3.execute(
        _input(prior=prior),
        [_ExplodingSource(), FakeReferenceSource(name="fallback")],
    )

    assert len(out.entities) == 1
    assert out.entities[0].properties.get("reference_source") == "fallback"
    assert out.metadata is not None
    assert "exploding" in (out.metadata.get("failed_source_names") or [])
    assert out.metadata.get("sources_failed") >= 1


def test_metadata_reports_enrichment_counts():
    prior = (_prior(label="REST"),)
    out = layer3.execute(_input(prior=prior), [FakeReferenceSource()])
    assert out.metadata is not None
    assert out.metadata.get("prior_entities") == 1
    assert out.metadata.get("enriched_count") == 1
    assert out.metadata.get("sources_checked") == 1


# ---------------------------------------------------------------------------- #
# Dedup verification — the canonical Layer-3 → ExtractionService contract       #
# ---------------------------------------------------------------------------- #


def _build_extraction_service() -> ExtractionService:
    """Minimal ExtractionService with all-fake ports; only `_deduplicate` is exercised."""
    return ExtractionService(
        ontology_repo=MagicMock(),
        embedding_service=FakeEmbeddingService(),
        llm=FakeLLMProvider(response_content='{"triples": []}'),
        nlp=FakeNLPProcessor(),
        reference_sources=[FakeReferenceSource()],
        event_publisher=MagicMock(),
        extraction_repo=MagicMock(),
        extraction_run_repo=MagicMock(),
    )


def test_dedup_merges_layer_3_enriched_copy_with_layer_1_prior():
    """
    Contract: a Layer-3 enriched copy with the same id as a Layer-1 prior
    must be merged into one entity post-dedup, preserving:
      - the Layer-1 entity's label / entity_type / confidence (higher priority)
      - the Layer-3 entity's uri / description / external-source properties

    This is the entire reason Layer 3 emits `id=prior_entity.id` rather than
    a fresh UUID. Without this dedup contract, enrichment would create
    duplicate entities — every reference grounding would double-count.
    """
    prior_id = "shared-entity-id"
    prior_layer1 = ExtractedEntity(
        id=prior_id,
        label="REST",
        entity_type="ArchitecturalStyle",
        source_layer=1,
        confidence=0.95,
        # Layer 1 has no URI / description on its own.
    )
    enriched_layer3 = ExtractedEntity(
        id=prior_id,  # same id is the contract
        label="REST",
        entity_type="ArchitecturalStyle",
        source_layer=3,
        confidence=0.95,
        uri="http://dbpedia.org/resource/Representational_state_transfer",
        description="Architectural style for distributed hypermedia systems.",
        properties={"reference_source": "dbpedia", "reference_label": "REST"},
    )

    service = _build_extraction_service()
    merged = service._deduplicate([prior_layer1, enriched_layer3])

    assert len(merged) == 1, (
        f"Expected dedup to merge Layer-3 enriched copy into the Layer-1 prior "
        f"by shared id; got {len(merged)} entities post-dedup"
    )
    entity = merged[0]
    # Identity preserved
    assert entity.id == prior_id
    assert entity.label == "REST"
    assert entity.entity_type == "ArchitecturalStyle"
    # Enrichment merged in
    assert entity.uri == enriched_layer3.uri, (
        "URI from Layer-3 enrichment was lost during dedup"
    )
    assert entity.description == enriched_layer3.description, (
        "Description from Layer-3 enrichment was lost during dedup"
    )
    assert entity.properties.get("reference_source") == "dbpedia"


def test_dedup_does_not_merge_distinct_ids():
    """Sanity: two entities with different ids must NOT be merged."""
    a = ExtractedEntity(
        id="id-a",
        label="REST",
        entity_type="ArchitecturalStyle",
        source_layer=1,
        confidence=0.9,
    )
    b = ExtractedEntity(
        id="id-b",
        label="CRDT",
        entity_type="DataStructure",
        source_layer=3,
        confidence=0.9,
        uri="http://example/CRDT",
    )
    service = _build_extraction_service()
    merged = service._deduplicate([a, b])
    assert len(merged) == 2
    ids = {e.id for e in merged}
    assert ids == {"id-a", "id-b"}
