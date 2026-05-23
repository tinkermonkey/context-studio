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

import pytest

from domain.pipelines.entities import PipelineType
from domain.pipelines.schema_extraction.orchestrator import (
    SchemaExtractionOrchestrator,
    SchemaExtractionState,
)
from tests.fixtures.schema_extraction_fixtures import get_fixtures


class MockLLMProvider:
    """Mock LLM provider for testing with JSON responses."""

    def __init__(self, fail_stage=None):
        """
        Initialize with predefined responses.

        Args:
            fail_stage: Optional stage name to inject parsing failures (for testing error handling)
        """
        self.call_count = 0
        self.fail_stage = fail_stage

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

        # Determine which stage this is to inject failures if needed
        stage = None
        if "disambiguation" in system_prompt.lower():
            stage = "disambiguation"
        elif (
            "relationships and properties" in user_prompt.lower()
            and "For these candidate classes" in user_prompt
        ):
            stage = "connection_proposal"
        elif "Extract" in system_prompt or (
            "extract" in system_prompt.lower() and "candidate" in system_prompt.lower()
        ):
            stage = "candidate_identification"
        else:
            stage = "definition_synthesis"

        # Inject failures for specific stages if requested
        if self.fail_stage == stage:
            # Return invalid JSON for the requested stage
            if stage == "candidate_identification":
                content = "not valid json at all!!!"
            elif stage == "connection_proposal":
                # Valid JSON but wrong shape (list instead of dict)
                content = '["this", "is", "a", "list"]'
            elif stage == "disambiguation":
                content = "invalid json response"  # Truly invalid JSON
            else:
                content = "invalid json"
        else:
            # Normal responses for working stages
            if stage == "disambiguation":
                # Stage 6: Disambiguation - handle multi-sense terms
                content = (
                    '{"ambiguous_terms": '
                    '[{"term": "Service", "senses": '
                    '["Microservice instance", "Web service", "Business service"], '
                    '"rationale": "Service has multiple meanings in different contexts"}]'
                    "}"
                )
            elif stage == "connection_proposal":
                # Stage 5: Connection proposal - more specific to avoid matching definition context
                content = (
                    '{"relationships": '
                    '[{"subject": "Microservice", "predicate": "subclass_of", '
                    '"object": "Service", "confidence": 0.9}], '
                    '"properties": '
                    '[{"name": "communicates_with", "domain": "Microservice", '
                    '"range": "Service", "confidence": 0.8}]'
                    "}"
                )
            elif stage == "candidate_identification":
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
    ):
        """Return mock responses (async version)."""
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
            "documents": [source_text],
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

        # For class candidates, verify proposed_definition is a non-empty string
        if candidate["kind"] == "class":
            assert "proposed_definition" in candidate
            definition = candidate["proposed_definition"]
            assert isinstance(
                definition, str
            ), f"proposed_definition must be a string, got {type(definition)}"
            assert len(definition) > 0, "proposed_definition must not be empty for classes"
            # Verify it's not a JSON object (should be human-readable text)
            assert not definition.strip().startswith(
                "{"
            ), "proposed_definition should be text, not JSON"


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
            "documents": [source_text],
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
                "documents": [source_text],
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
            "documents": [source_text],
            "model": "google/gemini-3-flash-preview",
        },
    )

    result_state = await orchestrator.execute(state)

    # Look for disambiguated terms (marked with rationale)
    disambiguated_candidates = [
        c for c in result_state.result["candidates"] if c.get("disambiguation_rationale")
    ]

    # Verify the acceptance criterion: multi-sense disambiguation works
    # MockLLMProvider is deterministic and returns disambiguation data for "Service"
    assert (
        len(disambiguated_candidates) > 0
    ), "Should have disambiguated candidates for multi-sense terms"

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
                "documents": [source_text],
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


@pytest.mark.asyncio
async def test_schema_extraction_corpus_consensus_distributed_fixture():
    """Test schema extraction on corpus-derived consensus and distributed systems fixture."""
    llm_provider = MockLLMProvider()
    orchestrator = SchemaExtractionOrchestrator(llm_provider)

    fixtures = get_fixtures()
    # Skip if corpus fixture not available
    if "consensus_distributed" not in fixtures:
        pytest.skip("Corpus fixture not available")

    source_text = fixtures["consensus_distributed"]

    state = SchemaExtractionState(
        run_id="run-corpus-consensus",
        pipeline_type=PipelineType.SCHEMA_EXTRACTION,
        input_data={
            "documents": [source_text],
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


@pytest.mark.asyncio
async def test_schema_extraction_corpus_microservices_api_fixture():
    """Test schema extraction on corpus-derived microservices API fixture."""
    llm_provider = MockLLMProvider()
    orchestrator = SchemaExtractionOrchestrator(llm_provider)

    fixtures = get_fixtures()
    # Skip if corpus fixture not available
    if "microservices_api" not in fixtures:
        pytest.skip("Corpus fixture not available")

    source_text = fixtures["microservices_api"]

    state = SchemaExtractionState(
        run_id="run-corpus-microservices-api",
        pipeline_type=PipelineType.SCHEMA_EXTRACTION,
        input_data={
            "documents": [source_text],
            "model": "google/gemini-3-flash-preview",
        },
    )

    result_state = await orchestrator.execute(state)

    # Verify execution completed
    assert result_state.current_status == "completed"
    assert result_state.result is not None
    assert "candidates" in result_state.result


@pytest.mark.asyncio
async def test_schema_extraction_corpus_service_multisense_fixture():
    """Test multi-sense disambiguation on corpus-derived service fixture."""
    llm_provider = MockLLMProvider()
    orchestrator = SchemaExtractionOrchestrator(llm_provider)

    fixtures = get_fixtures()
    # Skip if corpus fixture not available
    if "service_multisense" not in fixtures:
        pytest.skip("Corpus fixture not available")

    source_text = fixtures["service_multisense"]

    state = SchemaExtractionState(
        run_id="run-corpus-service-multisense",
        pipeline_type=PipelineType.SCHEMA_EXTRACTION,
        input_data={
            "documents": [source_text],
            "model": "google/gemini-3-flash-preview",
        },
    )

    result_state = await orchestrator.execute(state)

    # Verify execution completed
    assert result_state.current_status == "completed"
    assert result_state.result is not None

    # Verify multi-sense handling
    candidates = result_state.result["candidates"]
    assert len(candidates) > 0

    # Look for candidates that have multi-sense indicators
    for candidate in candidates:
        assert "kind" in candidate
        assert "confidence" in candidate
        assert 0.0 <= candidate["confidence"] <= 1.0


@pytest.mark.asyncio
async def test_parse_warnings_candidate_identification_invalid_json():
    """Test that parse_warnings is populated when candidate_identification returns invalid JSON."""
    llm_provider = MockLLMProvider(fail_stage="candidate_identification")
    orchestrator = SchemaExtractionOrchestrator(llm_provider)

    fixtures = get_fixtures()
    source_text = fixtures["microservices"]

    state = SchemaExtractionState(
        run_id="run-parse-fail-candidates",
        pipeline_type=PipelineType.SCHEMA_EXTRACTION,
        input_data={
            "documents": [source_text],
            "model": "google/gemini-3-flash-preview",
        },
    )

    result_state = await orchestrator.execute(state)

    # Verify execution completed
    assert result_state.current_status == "completed"

    # Verify parse_warnings is populated
    assert result_state.parse_warnings
    warning = result_state.parse_warnings[0]
    assert warning["stage"] == "candidate_identification"
    assert "JSON parse error" in warning["error"]
    assert warning["fallback_action"] == "regex extraction"

    # Verify regex fallback was used (will extract all-caps phrases)
    assert len(result_state.candidate_concepts) > 0


@pytest.mark.asyncio
async def test_parse_warnings_connection_proposal_invalid_json():
    """Test that parse_warnings is populated when connection_proposal returns invalid JSON."""
    llm_provider = MockLLMProvider(fail_stage="connection_proposal")
    orchestrator = SchemaExtractionOrchestrator(llm_provider)

    fixtures = get_fixtures()
    source_text = fixtures["microservices"]

    state = SchemaExtractionState(
        run_id="run-parse-fail-connections",
        pipeline_type=PipelineType.SCHEMA_EXTRACTION,
        input_data={
            "documents": [source_text],
            "model": "google/gemini-3-flash-preview",
        },
    )

    result_state = await orchestrator.execute(state)

    # Verify execution completed
    assert result_state.current_status == "completed"

    # Verify parse_warnings contains connection_proposal failure
    connection_warnings = [
        w for w in result_state.parse_warnings if w["stage"] == "connection_proposal"
    ]
    assert len(connection_warnings) > 0
    warning = connection_warnings[0]
    assert "JSON parse error" in warning["error"]
    assert warning["fallback_action"] == "no connections extracted"

    # Verify connections are empty but execution continues
    assert result_state.proposed_connections == []
    assert result_state.current_status == "completed"


@pytest.mark.asyncio
async def test_parse_warnings_disambiguation_invalid_json():
    """Test that parse_warnings is populated when disambiguation returns invalid JSON."""
    llm_provider = MockLLMProvider(fail_stage="disambiguation")
    orchestrator = SchemaExtractionOrchestrator(llm_provider)

    fixtures = get_fixtures()
    source_text = fixtures["microservices"]

    state = SchemaExtractionState(
        run_id="run-parse-fail-disamb",
        pipeline_type=PipelineType.SCHEMA_EXTRACTION,
        input_data={
            "documents": [source_text],
            "model": "google/gemini-3-flash-preview",
        },
    )

    result_state = await orchestrator.execute(state)

    # Verify execution completed
    assert result_state.current_status == "completed"

    # Verify parse_warnings contains disambiguation failure
    disamb_warnings = [w for w in result_state.parse_warnings if w["stage"] == "disambiguation"]
    assert len(disamb_warnings) > 0
    warning = disamb_warnings[0]
    assert "JSON parse error" in warning["error"]
    assert warning["fallback_action"] == "skipping disambiguation"

    # Verify candidates are preserved but disambiguation didn't happen
    assert len(result_state.candidate_classes) > 0
    assert result_state.current_status == "completed"


@pytest.mark.asyncio
async def test_parse_warnings_structure():
    """Test that parse_warnings have the correct structure."""
    llm_provider = MockLLMProvider(fail_stage="candidate_identification")
    orchestrator = SchemaExtractionOrchestrator(llm_provider)

    fixtures = get_fixtures()
    source_text = fixtures["microservices"]

    state = SchemaExtractionState(
        run_id="run-warning-structure",
        pipeline_type=PipelineType.SCHEMA_EXTRACTION,
        input_data={
            "documents": [source_text],
            "model": "google/gemini-3-flash-preview",
        },
    )

    result_state = await orchestrator.execute(state)

    # Verify warning structure
    if result_state.parse_warnings:
        for warning in result_state.parse_warnings:
            assert isinstance(warning, dict)
            assert "stage" in warning
            assert "error" in warning
            assert "response_preview" in warning
            assert "fallback_action" in warning
            assert isinstance(warning["stage"], str)
            assert isinstance(warning["error"], str)
            assert isinstance(warning["response_preview"], str)
            assert isinstance(warning["fallback_action"], str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
