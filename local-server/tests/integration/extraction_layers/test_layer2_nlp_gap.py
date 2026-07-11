"""
Layer 2 (NLP Gap-fill) isolation tests.

Exercises `domain.extraction.layers.nlp_gap.execute`. Layer 2:
  - raises `NLPProcessorNotReadyError` if `nlp.is_ready()` is False
  - calls `nlp.extract_entities(text)`
  - filters duplicates by case-insensitive label match against existing_entities
  - emits ExtractedEntity rows with `source_layer == 2`
"""

from __future__ import annotations

import pytest

from domain.extraction.entities import ExtractedEntity
from domain.extraction.exceptions import NLPProcessorNotReadyError
from domain.extraction.layers import nlp_gap
from domain.extraction.ports import NLPEntity, NLPResult
from domain.extraction.value_objects import LayerInput
from tests.fakes.fake_nlp_processor import FakeNLPProcessor


def _input(text: str = "Some text.", prior=()) -> LayerInput:
    return LayerInput(text=text, existing_entities=tuple(prior))


class _NotReadyNLPProcessor:
    """An NLPProcessor that reports it is not ready."""

    def __init__(self) -> None:
        self.process_calls = 0
        self.extract_calls = 0

    def process(self, text: str) -> NLPResult:
        self.process_calls += 1
        return NLPResult(tokens=(), entities=[], noun_chunks=[], language="en")

    def extract_entities(self, text: str) -> list[NLPEntity]:
        self.extract_calls += 1
        return []

    def is_ready(self) -> bool:
        return False


class _PaperNLPProcessor:
    """An NLPProcessor that returns canon-flavoured entities."""

    def __init__(self, entities: list[NLPEntity]) -> None:
        self._entities = entities

    def process(self, text: str) -> NLPResult:
        return NLPResult(
            tokens=tuple(text.split()),
            entities=self._entities,
            noun_chunks=[],
            language="en",
        )

    def extract_entities(self, text: str) -> list[NLPEntity]:
        return list(self._entities)

    def is_ready(self) -> bool:
        return True


def test_empty_text_returns_no_entities():
    out = nlp_gap.execute(_input(text=""), FakeNLPProcessor())
    assert out.entities == ()
    assert out.metadata is not None and out.metadata.get("reason") == "empty_text"


def test_processor_not_ready_raises_nlp_processor_not_ready_error():
    processor = _NotReadyNLPProcessor()
    with pytest.raises(NLPProcessorNotReadyError):
        nlp_gap.execute(_input(), processor)
    # Layer must NOT have called extract_entities after the readiness check.
    assert processor.extract_calls == 0


def test_nlp_entities_emit_layer_2_extracted_entities():
    paper = "Conflict-free Replicated Data Types (CRDTs) converge without coordination."
    processor = _PaperNLPProcessor(
        entities=[
            NLPEntity(
                text="CRDT",
                label="DataStructure",
                start=20,
                end=24,
                confidence=0.92,
                linked_uri=None,
            ),
            NLPEntity(
                text="anti-entropy",
                label="Algorithm",
                start=60,
                end=72,
                confidence=0.85,
                linked_uri="http://dbpedia.org/resource/Anti-entropy",
            ),
        ]
    )
    out = nlp_gap.execute(_input(text=paper), processor)
    assert len(out.entities) == 2
    for entity in out.entities:
        assert entity.source_layer == 2
        assert entity.confidence > 0.0
    crdt = next(e for e in out.entities if e.label == "CRDT")
    assert crdt.entity_type == "DataStructure"
    assert "char_offset_start" in crdt.properties
    assert "char_offset_end" in crdt.properties


def test_duplicate_against_prior_entity_is_filtered():
    """Layer 2 must dedupe (case-insensitively) against existing_entities."""
    prior = (
        ExtractedEntity(label="CRDT", entity_type="DataStructure", source_layer=1, confidence=0.9),
    )
    processor = _PaperNLPProcessor(
        entities=[
            NLPEntity(
                text="crdt",
                label="DataStructure",
                start=0,
                end=4,
                confidence=0.9,
                linked_uri=None,
            ),
            NLPEntity(
                text="anti-entropy",
                label="Algorithm",
                start=10,
                end=22,
                confidence=0.85,
                linked_uri=None,
            ),
        ]
    )
    out = nlp_gap.execute(_input(text="text with crdt and anti-entropy", prior=prior), processor)
    labels = {e.label for e in out.entities}
    assert "anti-entropy" in labels
    # 'crdt' must be filtered because prior had 'CRDT' (case-insensitive match)
    assert "crdt" not in labels and "CRDT" not in labels


def test_metadata_reports_skipped_duplicates():
    prior = (
        ExtractedEntity(label="CRDT", entity_type="DataStructure", source_layer=1, confidence=0.9),
    )
    processor = _PaperNLPProcessor(
        entities=[
            NLPEntity(
                text="CRDT",
                label="DataStructure",
                start=0,
                end=4,
                confidence=0.9,
                linked_uri=None,
            ),
        ]
    )
    out = nlp_gap.execute(_input(prior=prior), processor)
    assert out.metadata is not None
    assert out.metadata.get("nlp_entities_found") == 1
    assert out.metadata.get("duplicates_skipped") == 1
    assert out.metadata.get("processor_ready") is True


def test_default_fake_processor_yields_layer_2_entity():
    """Sanity: FakeNLPProcessor always emits a single ORG entity for non-empty text."""
    out = nlp_gap.execute(_input(text="anything"), FakeNLPProcessor())
    assert len(out.entities) == 1
    assert out.entities[0].source_layer == 2
    assert out.entities[0].entity_type == "ORG"
