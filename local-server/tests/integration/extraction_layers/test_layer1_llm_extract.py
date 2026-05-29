"""
Layer 1 (LLM Extract) isolation tests.

Exercises `domain.extraction.layers.llm_extract.execute` with controlled fake
LLM responses. Layer 1 builds a prompt embedding any prior entities, calls the
LLM, and parses a JSON ARRAY of `[{label, type, confidence, uri, description}]`.

Notes:
  - The Layer-1 response format is a JSON array, *not* the orchestrator's
    `{"triples": [...]}` object. So the test fakes here construct array JSON
    directly via FakeLLMProvider.response_content.
"""

from __future__ import annotations

import json
from typing import Literal

import pytest

from domain.extraction.entities import ExtractedEntity
from domain.extraction.layers import llm_extract
from domain.extraction.value_objects import LayerInput
from domain.pipelines.ports import LLMResponse
from tests.fakes.fake_llm_provider import FakeLLMProvider


def _input(text: str = "REST is an architectural style.", prior=()) -> LayerInput:
    return LayerInput(text=text, existing_entities=tuple(prior))


def _array_response(entities: list[dict]) -> str:
    return json.dumps(entities)


def test_empty_text_returns_no_entities():
    fake = FakeLLMProvider(response_content=_array_response([]))
    out = llm_extract.execute(_input(text=""), fake)
    assert out.entities == ()
    assert out.metadata is not None and out.metadata.get("reason") == "empty_text"
    # LLM must not be called for empty input.
    assert fake.call_count == 0


def test_no_available_models_returns_empty_with_metadata():
    """A provider that lists zero models should short-circuit cleanly."""

    class _NoModelsProvider(FakeLLMProvider):
        def list_available_models(self) -> list[str]:
            return []

    fake = _NoModelsProvider(response_content="[]")
    out = llm_extract.execute(_input(), fake)
    assert out.entities == ()
    assert out.metadata is not None
    assert out.metadata.get("reason") == "no_models_available"


def test_valid_array_response_produces_layer_1_entities():
    payload = _array_response(
        [
            {
                "label": "REST",
                "type": "ArchitecturalStyle",
                "confidence": 0.92,
                "uri": "http://dbpedia.org/resource/REST",
                "description": "Representational State Transfer",
            },
            {
                "label": "uniform interface",
                "type": "ArchitecturalConstraint",
                "confidence": 0.88,
            },
        ]
    )
    fake = FakeLLMProvider(response_content=payload)
    out = llm_extract.execute(_input(), fake)

    assert len(out.entities) == 2
    labels = {e.label for e in out.entities}
    assert labels == {"REST", "uniform interface"}
    for entity in out.entities:
        assert entity.source_layer == 1
        assert 0.0 <= entity.confidence <= 1.0
    rest_entity = next(e for e in out.entities if e.label == "REST")
    assert rest_entity.uri == "http://dbpedia.org/resource/REST"
    assert rest_entity.description == "Representational State Transfer"


def test_array_wrapped_in_prose_is_still_extracted():
    """The parser fishes the JSON array out of a prose-wrapped response."""
    payload = (
        "Here are the entities I found:\n"
        + _array_response([{"label": "Paxos", "type": "ConsensusProtocol", "confidence": 0.9}])
        + "\nLet me know if you need more."
    )
    fake = FakeLLMProvider(response_content=payload)
    out = llm_extract.execute(_input(text="Paxos is a consensus protocol."), fake)
    assert len(out.entities) == 1
    assert out.entities[0].label == "Paxos"
    assert out.entities[0].source_layer == 1


def test_malformed_response_records_parse_error():
    fake = FakeLLMProvider(response_content="not even close to JSON")
    out = llm_extract.execute(_input(), fake)
    assert out.entities == ()
    assert out.metadata is not None
    assert out.metadata.get("parse_error"), (
        f"Expected parse_error in metadata; got {dict(out.metadata)}"
    )


def test_prior_entities_propagate_into_user_prompt():
    """Layer 1 must include the labels of existing_entities as LLM context."""
    fake = FakeLLMProvider(response_content="[]")
    prior = (
        ExtractedEntity(label="REST", entity_type="ArchitecturalStyle", source_layer=0, confidence=0.9),
        ExtractedEntity(label="HATEOAS", entity_type="Concept", source_layer=0, confidence=0.85),
    )
    llm_extract.execute(_input(prior=prior), fake)

    assert fake.last_call_args is not None
    prompt = fake.last_call_args["user_prompt"]
    assert "Already extracted" in prompt
    assert "REST" in prompt and "HATEOAS" in prompt


def test_entries_without_label_are_dropped():
    payload = _array_response(
        [
            {"label": "REST", "type": "ArchitecturalStyle", "confidence": 0.9},
            {"type": "MISSING_LABEL", "confidence": 0.7},  # silently dropped
            {"label": "  ", "type": "BLANK", "confidence": 0.5},  # blank → dropped
        ]
    )
    fake = FakeLLMProvider(response_content=payload)
    out = llm_extract.execute(_input(), fake)
    assert len(out.entities) == 1
    assert out.entities[0].label == "REST"


def test_metadata_carries_token_counts_and_model():
    fake = FakeLLMProvider(
        response_content=_array_response([]),
        tokens_in=42,
        tokens_out=7,
    )
    out = llm_extract.execute(_input(), fake)
    assert out.metadata is not None
    assert out.metadata.get("tokens_in") == 42
    assert out.metadata.get("tokens_out") == 7
    assert out.metadata.get("model") in fake.available_models
