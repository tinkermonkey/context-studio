"""
Unit tests for SchemaExtractionOrchestrator warning emissions.

Tests that warnings are properly emitted when candidates, connections, or
properties lack concrete provenance in the source text.
"""

import json
import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)


import pytest

from domain.extraction.value_objects import SourceSpan
from domain.ontology.entities import Class, ConceptScheme, Taxonomy
from domain.pipelines.entities import PipelineType
from domain.pipelines.exceptions import PipelineInputError
from domain.pipelines.ports import LLMResponse
from domain.pipelines.schema_extraction.orchestrator import (
    CandidateClass,
    CandidateConnection,
    SchemaExtractionOrchestrator,
    SchemaExtractionState,
    join_documents,
)
from tests.fakes.fake_ontology_repository import FakeOntologyRepository


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
            content = '{"Microservice": "A small service", "UnknownTerm": "An unknown concept"}'
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
        assert len(conn_warnings) > 0, (
            "Expected at least one connection_proposal warning for unknown terms"
        )
        assert any(
            "UnknownA" in w.get("error", "") or "UnknownB" in w.get("error", "")
            for w in conn_warnings
        ), "Expected warning to mention unknown relationship"
        assert any("UnknownProperty" in w.get("error", "") for w in conn_warnings), (
            "Expected warning to mention unknown property"
        )

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

        # The original term stays (connections proposed earlier refer to it).
        assert [c.label for c in classes] == [
            "Event Loop",
            "Event Loop (asyncio)",
            "Event Loop (GUI)",
        ]
        assert [c.proposed_definition for c in classes] == [
            "Event Loop definition",
            "The asyncio scheduler that runs coroutines",
            "A UI framework loop dispatching events",
        ]
        assert classes[0].disambiguation_rationale is None
        assert all(c.disambiguation_rationale.endswith("two uses") for c in classes[1:])

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

        assert [c.label for c in classes] == ["Task", "Task (sense 1)", "Task (unit of work)"]
        assert classes[1].proposed_definition == "Wraps a coroutine"

    @pytest.mark.asyncio
    async def test_string_false_drops_a_sense_and_fallback_counts_kept_senses(self):
        reply = (
            '{"ambiguous_terms": [{"term": "Future", "rationale": "r", "senses": ['
            '{"qualifier": "dictionary meaning", "used_in_text": "false"},'
            '{"qualifier": "", "definition": "An asyncio Future", "used_in_text": true},'
            '{"qualifier": "concurrent.futures object", "used_in_text": "yes"}'
            "]}]}"
        )
        classes = await _disambiguate(reply, "Future")

        assert [c.label for c in classes] == [
            "Future",
            "Future (sense 1)",
            "Future (concurrent.futures object)",
        ]

    @pytest.mark.asyncio
    async def test_null_term_matches_nothing(self):
        reply = '{"ambiguous_terms": [{"term": null, "senses": ["a", "b"]}]}'
        classes = await _disambiguate(reply, "None", "Coroutine")

        assert [c.label for c in classes] == ["None", "Coroutine"]

    @pytest.mark.asyncio
    async def test_no_ambiguous_terms_leaves_candidates_unchanged(self):
        classes = await _disambiguate('{"ambiguous_terms": []}', "Coroutine", "Task")

        assert [c.label for c in classes] == ["Coroutine", "Task"]


class TestJoinDocuments:
    """join_documents builds the text that schema provenance offsets index into."""

    def test_joins_documents_with_a_space(self):
        assert join_documents(["First.", "Second."]) == "First. Second."

    def test_skips_non_string_documents(self):
        assert join_documents(["Only.", 3, None]) == "Only."

    def test_non_list_input_is_empty(self):
        assert join_documents("not a list") == ""


class TestChunkText:
    """Schema extraction chunks normalized text with the shared chunker."""

    def test_short_text_is_one_chunk(self, orchestrator):
        assert orchestrator._chunk_text("Short text.") == ["Short text."]

    def test_empty_text_is_one_empty_chunk(self, orchestrator):
        assert orchestrator._chunk_text("") == [""]

    def test_long_text_splits_on_sentences_and_rejoins_to_the_text(self, orchestrator):
        text = " ".join(f"Sentence {i} is about a gateway." for i in range(600))
        chunks = orchestrator._chunk_text(text)
        assert len(chunks) > 1
        assert all(len(chunk) <= 8000 and chunk.endswith(".") for chunk in chunks)
        assert " ".join(chunks) == text


class TestClassification:
    """Classification marks candidates whose title a class in the run's taxonomy has (#1571)."""

    @pytest.fixture
    def repo(self):
        repo = FakeOntologyRepository()
        for n, title in ((1, "Data Object"), (2, "Gateway")):
            repo.save_taxonomy(Taxonomy(id=f"tx-{n}", identifier=f"tax_{n}", title=f"T{n}"))
            repo.save_concept_scheme(
                ConceptScheme(
                    id=f"cs-{n}", taxonomy_id=f"tx-{n}", identifier=f"scheme_{n}", title="S"
                )
            )
            repo.save_class(
                Class(
                    id=f"cls-{n}",
                    concept_scheme_id=f"cs-{n}",
                    taxonomy_id=f"tx-{n}",
                    identifier=f"class_{n}",
                    title=title,
                )
            )
        return repo

    @staticmethod
    def _classify(mock_llm, repo, input_data):
        orchestrator = SchemaExtractionOrchestrator(
            llm_provider=mock_llm, ontology_repo=repo, run_id="test-run", status_writer=None
        )
        state = SchemaExtractionState(
            run_id="test-run",
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            input_data=input_data,
            candidate_concepts=["dataobject", "Gateway", "Microservice"],
        )
        return orchestrator._stage_classification(state)

    @pytest.mark.asyncio
    async def test_titles_of_the_run_taxonomys_classes_only(self, mock_llm, repo):
        state = await self._classify(mock_llm, repo, {"ontology_id": "tx-1"})
        # "dataobject" is "Data Object" by title key; Gateway is in another taxonomy
        assert state.classified_concepts == {
            "dataobject": True,
            "Gateway": False,
            "Microservice": False,
        }
        assert state.steps_completed[-1] == "classification"

    @pytest.mark.asyncio
    async def test_without_a_taxonomy_every_candidate_is_new(self, mock_llm, repo):
        state = await self._classify(mock_llm, repo, {})
        assert not any(state.classified_concepts.values())

    @pytest.mark.asyncio
    async def test_scope_names_the_taxonomy_as_source_runs_pass_it(self, mock_llm, repo):
        state = await self._classify(mock_llm, repo, {"scope": "tx-2"})
        assert state.classified_concepts["Gateway"] is True


class _PlacementLLM:
    """Replies to the placement stage with a scripted reply and records its prompt."""

    def __init__(self, reply):
        self.reply = reply
        self.user_prompts = []

    async def complete_async(self, system_prompt, user_prompt, model, **kwargs):
        self.user_prompts.append(user_prompt)
        content = self.reply if isinstance(self.reply, str) else json.dumps(self.reply)
        return LLMResponse(
            content=content,
            tokens_in=1,
            tokens_out=1,
            duration_ms=1,
            finish_reason="stop",
            model=model,
        )


class TestPlacement:
    """Placement puts candidates under existing classes or each other, and makes
    measurements attributes of a class (#1570)."""

    @pytest.fixture
    def repo(self):
        repo = FakeOntologyRepository()
        repo.save_taxonomy(Taxonomy(id="tx-h", identifier="house", title="House"))
        repo.save_concept_scheme(
            ConceptScheme(id="cs-h", taxonomy_id="tx-h", identifier="resources", title="R")
        )
        for n, (title, description) in enumerate(
            (("Appliance", "A machine\n that does a household task."), ("Task", None)), start=1
        ):
            repo.save_class(
                Class(
                    id=f"cls-{n}",
                    concept_scheme_id="cs-h",
                    taxonomy_id="tx-h",
                    identifier=f"class_{n}",
                    title=title,
                    description=description,
                )
            )
        return repo

    @staticmethod
    async def _place(reply, repo=None, input_data=None, labels=None):
        llm = _PlacementLLM(reply)
        orchestrator = SchemaExtractionOrchestrator(
            llm_provider=llm, ontology_repo=repo, run_id="test-run", status_writer=None
        )
        labels = labels or ["Heat Pump", "Air Filter", "Voltage", "Indoor Humidity"]
        state = SchemaExtractionState(
            run_id="test-run",
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            input_data=input_data if input_data is not None else {"scope": "tx-h"},
            candidate_classes=[
                CandidateClass(label=label, proposed_definition=f"{label} defined.")
                for label in labels
            ],
        )
        return llm, await orchestrator._stage_placement(state)

    @pytest.mark.asyncio
    async def test_classes_get_parents_and_measurements_become_attributes(self, repo):
        reply = {
            "placements": [
                {"label": "heat pump", "role": "class", "parent": "appliance"},
                {"label": "Air Filter", "role": "class", "parent": "Heat Pump"},
                {
                    "label": "Voltage",
                    "role": "attribute",
                    "of": "Heat Pump",
                    "value_type": "float",
                    "unit": "V",
                },
                {
                    "label": "Indoor Humidity",
                    "role": "attribute",
                    "of": "appliance",
                    "unit": "null",
                },
            ]
        }
        llm, state = await self._place(reply, repo)

        assert [(c.label, c.proposed_parent) for c in state.candidate_classes] == [
            ("Heat Pump", "Appliance"),
            ("Air Filter", "Heat Pump"),
        ]
        assert [
            (a.label, a.of_class, a.value_type, a.unit, a.proposed_definition)
            for a in state.candidate_attributes
        ] == [
            ("Voltage", "Heat Pump", "number", "V", "Voltage defined."),
            ("Indoor Humidity", "Appliance", "string", None, "Indoor Humidity defined."),
        ]
        assert state.steps_completed[-1] == "placement"
        assert state.parse_warnings == []
        prompt = llm.user_prompts[0]
        assert "- Appliance: A machine that does a household task.\n- Task\n" in prompt
        assert "- Heat Pump: Heat Pump defined." in prompt
        assert "string, integer, number, date, boolean" in prompt

    @pytest.mark.asyncio
    async def test_unknown_names_and_self_parents_are_dropped_with_warnings(self, repo):
        reply = {
            "placements": [
                {"label": "Heat Pump", "role": "class", "parent": "Machine"},
                {"label": "Air Filter", "role": "class", "parent": "Air Filter"},
                # An attribute can't belong to another attribute
                {"label": "Voltage", "role": "attribute", "of": "Indoor Humidity"},
                {"label": "Indoor Humidity", "role": "attribute", "of": "Dishwasher"},
                {"label": "Not A Candidate", "role": "class", "parent": "Task"},
            ]
        }
        _, state = await self._place(reply, repo)

        assert [c.proposed_parent for c in state.candidate_classes] == [None, None]
        assert [a.of_class for a in state.candidate_attributes] == [None, None]
        errors = [w["error"] for w in state.parse_warnings]
        assert len(errors) == 4  # one per name that resolves to no other class
        assert any("Machine" in e for e in errors)
        assert any("Dishwasher" in e for e in errors)

    @pytest.mark.asyncio
    async def test_a_cycle_among_candidates_is_cut(self, repo):
        reply = {
            "placements": [
                {"label": "A", "role": "class", "parent": "B"},
                {"label": "B", "role": "class", "parent": "C"},
                {"label": "C", "role": "class", "parent": "A"},
                {"label": "D", "role": "class", "parent": "Appliance"},
            ]
        }
        _, state = await self._place(reply, repo, labels=["A", "B", "C", "D"])

        assert [(c.label, c.proposed_parent) for c in state.candidate_classes] == [
            ("A", "B"),
            ("B", "C"),
            ("C", None),
            ("D", "Appliance"),
        ]
        assert any("cycle" in w["error"] for w in state.parse_warnings)

    @pytest.mark.asyncio
    async def test_without_a_taxonomy_it_places_among_the_candidates(self):
        reply = {
            "placements": [
                {"label": "Air Filter", "role": "class", "parent": "Heat Pump"},
                {"label": "Heat Pump", "role": "class", "parent": "Appliance"},
            ]
        }
        llm, state = await self._place(reply, input_data={}, labels=["Heat Pump", "Air Filter"])

        assert "Existing classes:\n(none)" in llm.user_prompts[0]
        assert [(c.label, c.proposed_parent) for c in state.candidate_classes] == [
            ("Heat Pump", None),
            ("Air Filter", "Heat Pump"),
        ]

    @pytest.mark.asyncio
    async def test_an_unreadable_reply_leaves_every_candidate_a_top_level_class(self, repo):
        _, state = await self._place("[]", repo)

        assert len(state.candidate_classes) == 4
        assert state.candidate_attributes == []
        assert state.parse_warnings[0]["stage"] == "placement"

    @pytest.mark.asyncio
    async def test_subclass_of_connections_fill_missing_parents(self, repo):
        _, state = await self._place(
            {"placements": [{"label": "Heat Pump", "role": "class", "parent": "Appliance"}]},
            repo,
            labels=["Heat Pump", "Air Filter", "Filter Media"],
        )
        orchestrator = SchemaExtractionOrchestrator(
            llm_provider=_PlacementLLM("{}"), ontology_repo=repo, run_id="test-run"
        )
        state.proposed_connections = [
            CandidateConnection("Heat Pump", "subclass_of", "Task"),  # already placed
            CandidateConnection("Air Filter", "is a", "Heat Pump"),
            CandidateConnection("Filter Media", "subclass_of", "Unknown"),
            CandidateConnection("Filter Media", "part_of", "Air Filter"),
        ]

        state = orchestrator._parents_from_connections(state)

        assert [(c.label, c.proposed_parent) for c in state.candidate_classes] == [
            ("Heat Pump", "Appliance"),
            ("Air Filter", "Heat Pump"),
            ("Filter Media", None),
        ]

    @pytest.mark.asyncio
    async def test_attributes_are_serialized_with_the_candidates(self, repo):
        reply = {
            "placements": [
                {"label": "Heat Pump", "role": "class", "parent": "Appliance"},
                {"label": "Voltage", "role": "attribute", "of": "Heat Pump", "unit": "V"},
            ]
        }
        _, state = await self._place(reply, repo, labels=["Heat Pump", "Voltage"])
        orchestrator = SchemaExtractionOrchestrator(llm_provider=_PlacementLLM("{}"))

        state = await orchestrator._stage_finalize(state)

        heat_pump, voltage = state.result["candidates"]
        assert heat_pump["kind"] == "class"
        assert heat_pump["proposed_parent"] == "Appliance"
        assert {k: voltage[k] for k in ("kind", "label", "of", "value_type", "unit")} == {
            "kind": "attribute",
            "label": "Voltage",
            "of": "Heat Pump",
            "value_type": "string",
            "unit": "V",
        }
        assert state.result["attribute_count"] == 1
        assert state.result["candidate_count"] == 1


_ENGLISH = (
    "A microservice exposes its API through the gateway. The gateway routes each request"
    " to the service that owns it, and it checks the caller's token first."
)
_FRENCH = (
    "Un microservice expose son API par la passerelle. La passerelle envoie chaque requête"
    " au service qui la possède, et elle vérifie le jeton de l'appelant."
)
_WARRANTY = (
    "LIMITED WARRANTY\nThe vendor warrants to the original purchaser that the product is"
    " free from defects in workmanship, and is not liable for incidental damages."
)


class TestSkipBoilerplate:
    """A source's boilerplate and other-language copies are left unread (#1570)."""

    def _input(self, **extra):
        text = "\n\n".join([_ENGLISH, _FRENCH, _WARRANTY])
        starts = [0, len(_ENGLISH) + 2, len(_ENGLISH) + len(_FRENCH) + 4]
        return {"documents": [text], "page_starts": starts, "model": "m", **extra}

    def _state(self, **extra):
        return SchemaExtractionState(
            run_id="test-run",
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            input_data=self._input(**extra),
        )

    async def test_skipped_sections_are_blanked_and_reported(self, orchestrator):
        state = await orchestrator.execute(self._state(source_id="src-1"))

        text = self._input()["documents"][0]
        assert len(state.source_text) == len(text)
        assert state.source_text.startswith(_ENGLISH)
        assert state.source_text[len(_ENGLISH) :].strip() == ""
        assert state.normalized_text == _ENGLISH
        assert [s["reason"] for s in state.result["skipped_sections"]] == [
            "other_language",
            "warranty",
        ]
        assert state.result["skipped_sections_by_reason"] == {
            "other_language": 1,
            "warranty": 1,
        }
        assert state.result["warnings"][0]["stage"] == "text_ingestion"

    async def test_skip_boilerplate_false_reads_everything(self, orchestrator):
        state = await orchestrator.execute(self._state(source_id="src-1", skip_boilerplate=False))

        assert state.source_text == self._input()["documents"][0]
        assert "skipped_sections" not in state.result

    async def test_documents_that_are_no_source_are_read_whole(self, orchestrator):
        state = await orchestrator.execute(
            SchemaExtractionState(
                run_id="test-run",
                pipeline_type=PipelineType.SCHEMA_EXTRACTION,
                input_data={"documents": [_FRENCH], "model": "m"},
            )
        )

        assert state.source_text == _FRENCH

    async def test_nothing_left_is_an_input_error(self, orchestrator):
        with pytest.raises(PipelineInputError, match="skip_boilerplate"):
            await orchestrator.execute(
                SchemaExtractionState(
                    run_id="test-run",
                    pipeline_type=PipelineType.SCHEMA_EXTRACTION,
                    input_data={"documents": [_FRENCH], "source_id": "src-1", "model": "m"},
                )
            )
