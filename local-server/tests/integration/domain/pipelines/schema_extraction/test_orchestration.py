"""
Integration tests for Schema Extraction orchestrator.

Tests verify:
- Full pipeline execution end-to-end
- Candidate class and property definition extraction
- Provenance tracking with correct text offsets
- Confidence scores in [0, 1]
- Multi-sense term disambiguation
- Connection proposal between candidates
"""

import os
import sys

# Add local-server directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

import pytest

from domain.pipelines.entities import PipelineType
from domain.pipelines.schema_extraction.orchestrator import SchemaExtractionOrchestrator, SchemaExtractionState
from tests.fixtures.schema_extraction_fixtures import get_fixtures


class MockLLMProvider:
    """Mock LLM provider for testing with JSON responses."""

    def __init__(self):
        """Initialize with predefined responses."""
        self.call_count = 0

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format=None,
        timeout=None,
        seed=None,
    ):
        """Return mock responses based on the stage."""
        from domain.pipeline.ports import LLMResponse

        self.call_count += 1

        # Dispatch based on system prompt first, then specific user_prompt patterns
        if "disambiguation" in system_prompt.lower():
            # Stage 6: Disambiguation - handle multi-sense terms
            content = (
                '{"ambiguous_terms": '
                '[{"term": "Service", "senses": ["Microservice instance", "Web service", "Business service"], '
                '"rationale": "Service has multiple meanings in different contexts"}]'
                "}"
            )
        elif "relationships and properties" in user_prompt.lower() and "For these candidate classes" in user_prompt:
            # Stage 5: Connection proposal - more specific to avoid matching definition context
            content = (
                '{"relationships": '
                '[{"subject": "Microservice", "predicate": "subclass_of", "object": "Service", "confidence": 0.9}], '
                '"properties": '
                '[{"name": "communicates_with", "domain": "Microservice", "range": "Service", "confidence": 0.8}]'
                "}"
            )
        elif "Extract" in system_prompt or "extract" in system_prompt.lower() and "candidate" in system_prompt.lower():
            # Stage 2: Candidate identification
            content = '["Microservice", "API Gateway", "Service", "Message Queue"]'
        else:
            # Stage 4: Definition synthesis (default - all other stages get definition string)
            content = "A definition of the requested term in the context."

        return LLMResponse(
            content=content,
            tokens_in=10,
            tokens_out=20,
            duration_ms=100,
            finish_reason="stop",
            model=model,
        )

    def is_model_available(self, model: str) -> bool:
        return True

    def list_available_models(self) -> list[str]:
        return ["google/gemini-3-flash-preview"]


@pytest.mark.asyncio
async def test_schema_extraction_microservices_fixture():
    """Test schema extraction on microservices fixture."""
    llm_provider = MockLLMProvider()
    orchestrator = SchemaExtractionOrchestrator(llm_provider)

    fixtures = get_fixtures()
    source_text = fixtures["microservices"]

    state = SchemaExtractionState(
        run_id="run-001",
        pipeline_type=PipelineType.SCHEMA_EXTRACTION,
        input_data={
            "text": source_text,
            "model": "google/gemini-3-flash-preview",
        },
    )

    result_state = await orchestrator.execute(state)

    # Verify execution completed
    assert result_state.current_status == "completed"
    assert result_state.result is not None

    # Verify candidates were extracted
    assert "candidates" in result_state.result
    assert len(result_state.result["candidates"]) > 0

    # Verify candidate structure
    for candidate in result_state.result["candidates"]:
        assert "kind" in candidate
        assert candidate["kind"] in ["class", "property_definition"]
        assert "label" in candidate
        assert "confidence" in candidate
        assert 0.0 <= candidate["confidence"] <= 1.0
        assert "provenance" in candidate

        # For class candidates, verify proposed_definition is a non-empty string (not JSON)
        if candidate["kind"] == "class":
            assert "proposed_definition" in candidate
            definition = candidate["proposed_definition"]
            assert isinstance(definition, str), f"proposed_definition must be a string, got {type(definition)}"
            assert len(definition) > 0, "proposed_definition must not be empty for classes"
            # Verify it's not a JSON object (should be human-readable text)
            assert not definition.strip().startswith("{"), "proposed_definition should be text, not JSON"


@pytest.mark.asyncio
async def test_schema_extraction_provenance_tracking():
    """Test that provenance offsets match source text."""
    llm_provider = MockLLMProvider()
    orchestrator = SchemaExtractionOrchestrator(llm_provider)

    fixtures = get_fixtures()
    source_text = fixtures["microservices"]

    state = SchemaExtractionState(
        run_id="run-002",
        pipeline_type=PipelineType.SCHEMA_EXTRACTION,
        input_data={
            "text": source_text,
            "model": "google/gemini-3-flash-preview",
        },
    )

    result_state = await orchestrator.execute(state)

    # Verify candidates have provenance
    for candidate in result_state.result["candidates"]:
        if candidate["provenance"]:
            for prov in candidate["provenance"]:
                # Verify provenance structure
                assert "text_offset_start" in prov
                assert "text_offset_end" in prov
                assert "raw" in prov

                # Verify offsets are valid
                start = prov["text_offset_start"]
                end = prov["text_offset_end"]
                assert 0 <= start < len(source_text)
                assert start <= end <= len(source_text)

                # Verify raw text matches source
                extracted = source_text[start:end]
                assert extracted.lower() == prov["raw"].lower()


@pytest.mark.asyncio
async def test_schema_extraction_confidence_bounds():
    """Test that all confidence scores are in [0, 1]."""
    llm_provider = MockLLMProvider()
    orchestrator = SchemaExtractionOrchestrator(llm_provider)

    fixtures = get_fixtures()

    for fixture_name, source_text in fixtures.items():
        state = SchemaExtractionState(
            run_id=f"run-conf-{fixture_name}",
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            input_data={
                "text": source_text,
                "model": "google/gemini-3-flash-preview",
            },
        )

        result_state = await orchestrator.execute(state)

        # All candidates must have confidence in [0, 1]
        for candidate in result_state.result["candidates"]:
            confidence = candidate["confidence"]
            assert isinstance(confidence, float)
            assert 0.0 <= confidence <= 1.0

        # All connections must have confidence in [0, 1]
        for connection in result_state.result["connections"]:
            confidence = connection["confidence"]
            assert isinstance(confidence, float)
            assert 0.0 <= confidence <= 1.0


@pytest.mark.asyncio
async def test_schema_extraction_disambiguation():
    """Test multi-sense disambiguation produces separate candidates."""
    llm_provider = MockLLMProvider()
    orchestrator = SchemaExtractionOrchestrator(llm_provider)

    fixtures = get_fixtures()
    source_text = fixtures["microservices"]

    state = SchemaExtractionState(
        run_id="run-disamb",
        pipeline_type=PipelineType.SCHEMA_EXTRACTION,
        input_data={
            "text": source_text,
            "model": "google/gemini-3-flash-preview",
        },
    )

    result_state = await orchestrator.execute(state)

    # Look for disambiguated terms (marked with rationale)
    disambiguated_candidates = [
        c
        for c in result_state.result["candidates"]
        if c.get("disambiguation_rationale")
    ]

    # Verify the acceptance criterion: multi-sense disambiguation works
    # MockLLMProvider is deterministic and returns disambiguation data for "Service"
    assert len(disambiguated_candidates) > 0, "Should have disambiguated candidates for multi-sense terms"

    for candidate in disambiguated_candidates:
        assert "disambiguation_rationale" in candidate
        assert isinstance(candidate["disambiguation_rationale"], str)


@pytest.mark.asyncio
async def test_schema_extraction_all_fixtures():
    """Test extraction on all fixtures."""
    llm_provider = MockLLMProvider()
    orchestrator = SchemaExtractionOrchestrator(llm_provider)

    fixtures = get_fixtures()

    for fixture_name, source_text in fixtures.items():
        state = SchemaExtractionState(
            run_id=f"run-{fixture_name}",
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            input_data={
                "text": source_text,
                "model": "google/gemini-3-flash-preview",
            },
        )

        result_state = await orchestrator.execute(state)

        # Basic sanity checks
        assert result_state.current_status == "completed"
        assert result_state.result is not None
        assert "candidates" in result_state.result
        assert "connections" in result_state.result

        # Verify counts are non-negative
        assert result_state.result["candidate_count"] >= 0
        assert result_state.result["property_count"] >= 0
        assert result_state.result["connection_count"] >= 0

        # Verify all steps completed
        expected_steps = [
            "text_ingestion",
            "candidate_identification",
            "classification",
            "definition_synthesis",
            "connection_proposal",
            "disambiguation",
            "confidence_scoring",
            "finalize",
        ]
        for step in expected_steps:
            assert step in result_state.steps_completed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
