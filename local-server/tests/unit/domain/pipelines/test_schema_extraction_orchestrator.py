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


import pytest

from domain.extraction.value_objects import SourceSpan
from domain.pipelines.entities import PipelineType
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
            content = '{"Microservice": "A small service", ' '"UnknownTerm": "An unknown concept"}'
        elif "disambiguation" in system_prompt.lower():
            content = '{"ambiguous_terms": []}'
        elif "relationships and properties" in user_prompt.lower():
            content = '{"relationships": [], "properties": []}'
        else:
            content = "[]"

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
            w
            for w in result_state.parse_warnings
            if w.get("stage") == "definition_synthesis" and "provenance" in w.get("error", "")
        ]

        # UnknownTerm should generate a warning (no provenance in text)
        assert any("UnknownTerm" in w.get("error", "") for w in def_syn_warnings)

    @pytest.mark.asyncio
    async def test_connection_proposal_warns_on_missing_provenance(self):
        """Connection without concrete provenance emits a connection_proposal warning."""
        from domain.pipelines.schema_extraction.orchestrator import CandidateClass

        # Custom mock that returns a relationship and property with unknown
        # terms not in source text
        class _MockLLMWithUnknownConnection(_MockLLM):
            def complete(
                self,
                system_prompt,
                user_prompt,
                model,
                temperature=0.0,
                max_tokens=2000,
                response_format=None,
                timeout=None,
                seed=None,
            ):
                if "relationships and properties" in user_prompt.lower():
                    # Return a relationship with both unknown terms and a
                    # property with unknown name. Both won't be found in
                    # source text: "Microservice interacts with Gateway."
                    content = (
                        '{"relationships": ['
                        '{"subject": "UnknownA", "predicate": "calls", '
                        '"object": "UnknownB", "confidence": 0.8}'
                        "], "
                        '"properties": ['
                        '{"name": "UnknownProperty", "domain": "Unknown", '
                        '"range": "Unknown", "confidence": 0.7}'
                        "]}"
                    )
                else:
                    return super().complete(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        model=model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        response_format=response_format,
                        timeout=timeout,
                        seed=seed,
                    )

                return LLMResponse(
                    content=content,
                    tokens_in=10,
                    tokens_out=30,
                    duration_ms=5,
                    finish_reason="stop",
                    model=model,
                )

        mock_llm = _MockLLMWithUnknownConnection()
        orchestrator = SchemaExtractionOrchestrator(
            llm_provider=mock_llm,
            ontology_repo=None,
            run_id="test-run",
            status_writer=None,
        )

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
                CandidateClass(label="Gateway", confidence=0.7),
            ],
            parse_warnings=[],
        )

        result_state = await orchestrator._stage_connection_proposal(state)

        # Filter warnings for connection_proposal stage
        conn_warnings = [
            w for w in result_state.parse_warnings if w.get("stage") == "connection_proposal"
        ]

        # Both the unknown relationship and unknown property should
        # generate warnings (no provenance in text)
        assert (
            len(conn_warnings) > 0
        ), "Expected at least one connection_proposal warning for unknown terms"
        assert any(
            "UnknownA" in w.get("error", "") or "UnknownB" in w.get("error", "")
            for w in conn_warnings
        ), "Expected warning to mention unknown relationship"
        assert any(
            "UnknownProperty" in w.get("error", "") for w in conn_warnings
        ), "Expected warning to mention unknown property"

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
        confidence = orchestrator._compute_confidence("Microservice", source_text, provenance)

        # Confidence should be boosted by provenance presence and term frequency
        assert 0.2 <= confidence <= 1.0

    def test_compute_confidence_without_precomputed_provenance(self, orchestrator):
        """_compute_confidence can compute provenance internally."""
        source_text = "Microservice is an architecture pattern."

        # Call without provenance - should compute it internally
        confidence = orchestrator._compute_confidence("Microservice", source_text)

        assert 0.2 <= confidence <= 1.0


class _FencedJsonLLM(_MockLLM):
    """Mock LLM that wraps every JSON reply in a Markdown code fence (as Gemini does)."""

    def __init__(self):
        self.response_formats: list = []

    def complete(
        self,
        system_prompt,
        user_prompt,
        model,
        temperature=0.0,
        max_tokens=2000,
        response_format=None,
        timeout=None,
        seed=None,
    ):
        self.response_formats.append(response_format)
        if "relationships and properties" in user_prompt.lower():
            body = (
                '{"relationships": [{"subject": "Microservice", "predicate": "calls", '
                '"object": "Gateway", "confidence": 0.8}], '
                '"properties": [{"name": "endpoint", "domain": "Microservice", '
                '"range": "Gateway", "confidence": 0.7}]}'
            )
        else:
            body = '["Microservice", "Gateway"]'
        return LLMResponse(
            content=f"```json\n{body}\n```",
            tokens_in=10,
            tokens_out=30,
            duration_ms=5,
            finish_reason="stop",
            model=model,
        )


class TestFencedJsonReplies:
    """Regression: fenced JSON replies must parse instead of triggering fallbacks."""

    _TEXT = "The Microservice calls the Gateway. It exposes an endpoint."

    def _state(self, **overrides):
        fields = dict(
            run_id="test-run",
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            input_data={"documents": [self._TEXT]},
            source_text=self._TEXT,
            normalized_text=self._TEXT,
            text_chunks=[self._TEXT],
            parse_warnings=[],
        )
        fields.update(overrides)
        return SchemaExtractionState(**fields)

    @pytest.mark.asyncio
    async def test_candidate_identification_parses_fenced_array(self):
        orchestrator = SchemaExtractionOrchestrator(
            llm_provider=_FencedJsonLLM(),
            ontology_repo=None,
            run_id="test-run",
            status_writer=None,
        )

        result = await orchestrator._stage_candidate_identification(self._state())

        assert result.candidate_concepts == ["Microservice", "Gateway"]
        assert not any(
            w.get("fallback_action") == "regex extraction" for w in result.parse_warnings
        )

    @pytest.mark.asyncio
    async def test_connection_proposal_parses_fenced_object(self):
        from domain.pipelines.schema_extraction.orchestrator import CandidateClass

        llm = _FencedJsonLLM()
        orchestrator = SchemaExtractionOrchestrator(
            llm_provider=llm, ontology_repo=None, run_id="test-run", status_writer=None
        )
        state = self._state(
            candidate_concepts=["Microservice", "Gateway"],
            candidate_classes=[
                CandidateClass(label="Microservice", confidence=0.8),
                CandidateClass(label="Gateway", confidence=0.7),
            ],
        )

        result = await orchestrator._stage_connection_proposal(state)

        assert [
            (c.subject_ref, c.predicate, c.object_ref) for c in result.proposed_connections
        ] == [("Microservice", "calls", "Gateway")]
        assert [p.label for p in result.candidate_properties] == ["endpoint"]
        assert not any("JSON parse error" in w.get("error", "") for w in result.parse_warnings)
        assert llm.response_formats == ["json"]


class _DisambiguationLLM:
    """Returns a fixed disambiguation reply; only the disambiguation stage is called."""

    def __init__(self, content: str):
        self.content = content

    async def complete_async(self, system_prompt, user_prompt, model, **kwargs) -> LLMResponse:
        return LLMResponse(
            content=self.content,
            tokens_in=1,
            tokens_out=1,
            duration_ms=1,
            finish_reason="stop",
            model=model,
        )


def _state_with(*labels: str) -> SchemaExtractionState:
    from domain.pipelines.schema_extraction.orchestrator import CandidateClass

    return SchemaExtractionState(
        run_id="run",
        pipeline_type=PipelineType.SCHEMA_EXTRACTION,
        input_data={},
        normalized_text="Python coroutines run on the event loop.",
        candidate_classes=[
            CandidateClass(label=label, proposed_definition=f"{label} definition", confidence=0.9)
            for label in labels
        ],
    )


async def _disambiguate(content: str, *labels: str):
    orchestrator = SchemaExtractionOrchestrator(
        llm_provider=_DisambiguationLLM(content), ontology_repo=None
    )
    result = await orchestrator._stage_disambiguation(_state_with(*labels))
    return result.candidate_classes


class TestDisambiguation:
    """Disambiguation splits only on in-text senses and never puts definitions in labels."""

    @pytest.mark.asyncio
    async def test_off_domain_senses_are_dropped_and_term_left_unsplit(self):
        reply = (
            '```json\n{"ambiguous_terms": [{"term": "Python", "rationale": "r", "senses": ['
            '{"qualifier": "language", "definition": "The programming language", '
            '"used_in_text": true},'
            '{"qualifier": "snake", "definition": "A large snake", "used_in_text": false}'
            "]}]}\n```"
        )
        classes = await _disambiguate(reply, "Python", "Coroutine")

        assert [c.label for c in classes] == ["Python", "Coroutine"]
        assert classes[0].proposed_definition == "Python definition"
        assert classes[0].disambiguation_rationale is None

    @pytest.mark.asyncio
    async def test_in_text_senses_split_with_short_labels_and_sense_definitions(self):
        reply = (
            '{"ambiguous_terms": [{"term": "event loop", "rationale": "two uses", "senses": ['
            '{"qualifier": "asyncio", "definition": "The asyncio scheduler that runs '
            'coroutines", "used_in_text": true},'
            '{"qualifier": "GUI", "definition": "A UI framework loop dispatching events", '
            '"used_in_text": true},'
            '{"qualifier": "snake", "definition": "Off topic", "used_in_text": false}'
            "]}]}"
        )
        classes = await _disambiguate(reply, "Event Loop")

        assert [c.label for c in classes] == ["Event Loop (asyncio)", "Event Loop (GUI)"]
        assert [c.proposed_definition for c in classes] == [
            "The asyncio scheduler that runs coroutines",
            "A UI framework loop dispatching events",
        ]
        assert all(c.disambiguation_rationale.endswith("two uses") for c in classes)

    @pytest.mark.asyncio
    async def test_long_qualifier_never_becomes_a_label(self):
        reply = (
            '{"ambiguous_terms": [{"term": "Task", "rationale": "r", "senses": ['
            '{"qualifier": "An asyncio Task object that wraps a coroutine", '
            '"definition": "Wraps a coroutine", "used_in_text": true},'
            '{"qualifier": "unit of work", "definition": "Work to do", "used_in_text": true}'
            "]}]}"
        )
        classes = await _disambiguate(reply, "Task")

        assert [c.label for c in classes] == ["Task (sense 1)", "Task (unit of work)"]
        assert classes[0].proposed_definition == "Wraps a coroutine"

    @pytest.mark.asyncio
    async def test_no_ambiguous_terms_leaves_candidates_unchanged(self):
        classes = await _disambiguate('{"ambiguous_terms": []}', "Coroutine", "Task")

        assert [c.label for c in classes] == ["Coroutine", "Task"]
