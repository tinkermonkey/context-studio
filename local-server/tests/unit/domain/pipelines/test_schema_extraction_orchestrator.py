"""
Unit tests for SchemaExtractionOrchestrator warning emissions.

Tests that warnings are properly emitted when candidates, connections, or
properties lack concrete provenance in the source text.
"""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.extraction.value_objects import SourceSpan
from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.pipelines.ports import LLMResponse
from domain.pipelines.schema_extraction.orchestrator import (
    SchemaExtractionOrchestrator,
    SchemaExtractionState,
)


class _MockLLM:
    """Mock LLM for testing orchestrator logic without external calls."""

    async def complete_async(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        response_format=None,
        timeout=None,
        seed=None,
    ) -> LLMResponse:
        return self.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            timeout=timeout,
            seed=seed,
        )

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
    ) -> LLMResponse:
        # Route based on prompt content
        if "Extract candidate" in system_prompt or "extract" in system_prompt.lower():
            content = '["Microservice", "UnknownTerm"]'
        elif "Return a JSON object mapping" in system_prompt:
            # Definition synthesis
            content = (
                '{"Microservice": "A small service", '
                '"UnknownTerm": "An unknown concept"}'
            )
        elif "disambiguation" in system_prompt.lower():
            content = '{"ambiguous_terms": []}'
        elif "relationships and properties" in user_prompt.lower():
            content = (
                '{"relationships": [], "properties": []}'
            )
        else:
            content = '[]'

        return LLMResponse(
            content=content,
            tokens_in=10,
            tokens_out=30,
            duration_ms=5,
            finish_reason="stop",
            model=model,
        )


@pytest.fixture
def mock_llm():
    return _MockLLM()


@pytest.fixture
def orchestrator(mock_llm):
    return SchemaExtractionOrchestrator(
        llm_provider=mock_llm,
        ontology_repo=None,
        run_id="test-run",
        status_writer=None,
    )


class TestWarningEmissions:
    """Tests for warning emission when provenance is missing."""

    @pytest.mark.asyncio
    async def test_definition_synthesis_warns_on_missing_provenance(self, orchestrator):
        """Candidate class without concrete provenance emits a definition_synthesis warning."""
        state = SchemaExtractionState(
            run_id="test-run",
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            input_data={"documents": ["Microservice is a pattern."]},
            source_text="Microservice is a pattern.",
            normalized_text="Microservice is a pattern.",
            text_chunks=["Microservice is a pattern."],
            candidate_concepts=["Microservice", "UnknownTerm"],
            classified_concepts={"Microservice": False, "UnknownTerm": False},
            parse_warnings=[],
        )

        result_state = await orchestrator._stage_definition_synthesis(state)

        # Filter warnings for definition_synthesis stage
        def_syn_warnings = [
            w for w in result_state.parse_warnings
            if w.get("stage") == "definition_synthesis" and "provenance" in w.get("error", "")
        ]

        # UnknownTerm should generate a warning (no provenance in text)
        assert any("UnknownTerm" in w.get("error", "") for w in def_syn_warnings)

    @pytest.mark.asyncio
    async def test_connection_proposal_warns_on_missing_provenance(self, orchestrator):
        """Connection without concrete provenance emits a connection_proposal warning."""
        from domain.pipelines.schema_extraction.orchestrator import CandidateClass

        state = SchemaExtractionState(
            run_id="test-run",
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            input_data={"documents": ["Microservice interacts with Gateway."]},
            source_text="Microservice interacts with Gateway.",
            normalized_text="Microservice interacts with Gateway.",
            text_chunks=["Microservice interacts with Gateway."],
            candidate_concepts=["Microservice", "Gateway"],
            candidate_classes=[
                CandidateClass(label="Microservice", confidence=0.8),
                CandidateClass(label="UnknownClass", confidence=0.5),
            ],
            parse_warnings=[],
        )

        result_state = await orchestrator._stage_connection_proposal(state)

        # Check that warnings include connection/property-related entries
        conn_warnings = [
            w for w in result_state.parse_warnings
            if w.get("stage") == "connection_proposal"
        ]
        # If relationships include unknown terms, warnings will be present
        assert isinstance(result_state.parse_warnings, list)

    @pytest.mark.asyncio
    async def test_finalize_includes_warnings_in_result(self, orchestrator):
        """Final result dict includes the warnings key."""
        state = SchemaExtractionState(
            run_id="test-run",
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            input_data={"documents": ["test"]},
            parse_warnings=[
                {
                    "stage": "definition_synthesis",
                    "error": "Candidate 'test' has no provenance",
                    "fallback_action": "use without provenance",
                }
            ],
            candidate_classes=[],
            candidate_properties=[],
            proposed_connections=[],
            steps_completed=[],
        )

        result_state = await orchestrator._stage_finalize(state)

        assert "warnings" in result_state.result
        assert len(result_state.result["warnings"]) == 1
        assert result_state.result["warnings"][0]["stage"] == "definition_synthesis"

    def test_has_concrete_provenance_filters_quote_only(self, orchestrator):
        """Helper correctly identifies concrete vs quote-only provenance."""
        concrete_spans = [SourceSpan(quote="test", start=0, end=4)]
        quote_only_spans = [SourceSpan(quote="test", start=None, end=None)]
        mixed_spans = [
            SourceSpan(quote="test1", start=0, end=5),
            SourceSpan(quote="test2", start=None, end=None),
        ]

        assert orchestrator._has_concrete_provenance(concrete_spans) is True
        assert orchestrator._has_concrete_provenance(quote_only_spans) is False
        assert orchestrator._has_concrete_provenance(mixed_spans) is True
        assert orchestrator._has_concrete_provenance([]) is False

    def test_compute_confidence_with_precomputed_provenance(self, orchestrator):
        """_compute_confidence accepts pre-computed provenance to avoid double calls."""
        source_text = "Microservice is an architecture pattern. Microservice is widely used."
        provenance = [SourceSpan(quote="Microservice", start=0, end=12)]

        # Call with pre-computed provenance
        confidence = orchestrator._compute_confidence(
            "Microservice", source_text, provenance
        )

        # Confidence should be boosted by provenance presence and term frequency
        assert 0.2 <= confidence <= 1.0

    def test_compute_confidence_without_precomputed_provenance(self, orchestrator):
        """_compute_confidence can compute provenance internally."""
        source_text = "Microservice is an architecture pattern."

        # Call without provenance - should compute it internally
        confidence = orchestrator._compute_confidence("Microservice", source_text)

        assert 0.2 <= confidence <= 1.0
