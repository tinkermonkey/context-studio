"""
Unit tests for the open_v1 LLM label-canonicalization stage.

Cover the pure, LLM-free parts of the stage: the label-mapping rewrite/dedup
and the anti-hallucination acceptance guard on the model's returned mapping.
The end-to-end grounded behavior is exercised by the tournament and the open
quality suite; these tests pin the deterministic logic in isolation.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import pytest

from domain.pipelines.individual_extraction.configurations.open_v1 import (
    get_open_v1_config,
)
from domain.pipelines.individual_extraction.open_orchestrator import (
    OpenIndividualExtractionOrchestrator,
)


def _triple(subj, pred, obj):
    return {
        "subject": {"label": subj, "kind": "individual"},
        "predicate": {"label": pred, "kind": "property"},
        "object": {"label": obj, "kind": "individual"},
        "confidence": 0.7,
    }


def test_apply_label_mapping_rewrites_subject_and_object():
    """Mapped labels replace both roles; unmapped labels are left untouched."""
    triples = [_triple("technician_route", "navigate", "job_detail_route")]
    mapping = {
        "technician_route": "Technician Route",
        "job_detail_route": "Job Detail Route",
    }
    out = OpenIndividualExtractionOrchestrator._apply_label_mapping(triples, mapping)
    assert out[0]["subject"]["label"] == "Technician Route"
    assert out[0]["object"]["label"] == "Job Detail Route"
    # Predicate and confidence pass through unchanged.
    assert out[0]["predicate"]["label"] == "navigate"
    assert out[0]["confidence"] == 0.7


def test_apply_label_mapping_dedupes_collisions():
    """Two triples that collapse to the same key after rewriting yield one triple."""
    triples = [
        _triple("gpt4", "is_a", "model"),
        _triple("gpt_4", "is_a", "model"),
    ]
    mapping = {"gpt4": "GPT-4", "gpt_4": "GPT-4"}
    out = OpenIndividualExtractionOrchestrator._apply_label_mapping(triples, mapping)
    assert len(out) == 1
    assert out[0]["subject"]["label"] == "GPT-4"


class _CannedProvider:
    """LLM provider returning a fixed JSON body for the single canonicalization call."""

    def __init__(self, body: str):
        self._body = body

    async def complete_async(self, **_kwargs):
        from domain.pipelines.ports import LLMResponse

        return LLMResponse(
            content=self._body,
            tokens_in=0,
            tokens_out=0,
            duration_ms=0.0,
            finish_reason="stop",
            model="test",
        )


def _orchestrator(provider):
    return OpenIndividualExtractionOrchestrator(
        llm_provider=provider,
        nlp_processor=None,
        embedding_service=None,
        schema_index=None,
        config={**get_open_v1_config(), "llm_canonicalization": True},
    )


@pytest.mark.asyncio
async def test_request_canonical_labels_accepts_only_text_present_names():
    """A returned name is kept only when it occurs in the source text or equals the mention."""
    body = (
        '{"technician_route": "Technician Route", '
        '"job_detail_route": "Fabricated Name", '
        '"flow_step": "flow_step"}'
    )
    orch = _orchestrator(_CannedProvider(body))
    text = "The Technician Route lets a technician move between flow steps."
    type_hints = {
        "technician_route": "Route",
        "job_detail_route": "Route",
        "flow_step": "FlowStep",
    }
    mapping = await orch._request_canonical_labels(type_hints, text)
    # Present in text -> accepted.
    assert mapping["technician_route"] == "Technician Route"
    # Mention returned unchanged -> accepted.
    assert mapping["flow_step"] == "flow_step"
    # Not present in text and not the mention -> rejected (guards hallucination).
    assert "job_detail_route" not in mapping


@pytest.mark.asyncio
async def test_request_canonical_labels_ignores_unknown_mentions():
    """Keys the model returns that were never offered are dropped."""
    orch = _orchestrator(_CannedProvider('{"unrequested": "Something"}'))
    mapping = await orch._request_canonical_labels({"foo": "Bar"}, "Something Something")
    assert mapping == {}


@pytest.mark.asyncio
async def test_request_canonical_labels_swallows_bad_json():
    """A non-JSON model response yields an empty mapping instead of raising."""
    orch = _orchestrator(_CannedProvider("not json at all"))
    mapping = await orch._request_canonical_labels({"foo": "Bar"}, "text")
    assert mapping == {}
