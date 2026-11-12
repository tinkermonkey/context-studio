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


_SOURCE = (
    "Python coroutines run on the event loop.\n"
    "A GUI toolkit runs its own Event Loop to dispatch clicks.\n"
    "Wrap a coroutine in a Task to schedule it. Each Task on the sprint board is a unit of work.\n"
    "An asyncio Future holds a result; a concurrent.futures Future wraps a thread.\n"
    "Have a contractor check the cooling system each spring. A clean filter helps the "
    "cooling system run efficiently."
)


def _state_with(*labels: str) -> SchemaExtractionState:
    from domain.pipelines.schema_extraction.orchestrator import CandidateClass

    return SchemaExtractionState(
        run_id="run",
        pipeline_type=PipelineType.SCHEMA_EXTRACTION,
        input_data={},
        source_text=_SOURCE,
        normalized_text=" ".join(_SOURCE.split()),
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


def _reply(term: str, *senses: dict) -> str:
    return json.dumps(
        {"ambiguous_terms": [{"term": term, "rationale": "two uses", "senses": list(senses)}]}
    )


class TestDisambiguation:
    """A term is split into senses only when each sense quotes a different passage."""

    @pytest.mark.asyncio
    async def test_senses_with_distinct_found_quotes_split(self):
        reply = _reply(
            "event loop",
            {
                "qualifier": "asyncio",
                "definition": "The asyncio scheduler that runs coroutines",
                "quote": "coroutines run on the event loop",
            },
            {
                # Case and whitespace differ from the source; the quote is still found
                "qualifier": "GUI",
                "definition": "A UI framework loop dispatching events",
                "quote": "runs its own  event loop to dispatch clicks",
            },
            {"qualifier": "snake", "definition": "Off topic", "quote": "a large snake"},
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
        # Each sense's provenance is the passage its quote matched in the source
        first, second = classes[1].provenance, classes[2].provenance
        assert [(s.quote, _SOURCE[s.start : s.end]) for s in first] == [
            ("coroutines run on the event loop", "coroutines run on the event loop")
        ]
        assert [s.quote for s in second] == ["runs its own Event Loop to dispatch clicks"]
        assert _SOURCE[second[0].start : second[0].end] == second[0].quote

    @pytest.mark.asyncio
    async def test_over_reported_senses_without_findable_quotes_collapse(self):
        # The ENERGY STAR failure: categories the text never uses the term in
        reply = _reply(
            "Cooling System",
            {"qualifier": "Functional Category", "definition": "A class of systems"},
            {
                "qualifier": "Physical Equipment",
                "definition": "The installed unit",
                "quote": "The cooling system is the equipment that cools the home",
            },
            {
                "qualifier": "Maintenance Target",
                "definition": "What gets serviced",
                "quote": "check the cooling system each spring",
            },
        )
        classes = await _disambiguate(reply, "Cooling System")

        assert [c.label for c in classes] == ["Cooling System"]
        assert classes[0].disambiguation_rationale is None

    @pytest.mark.asyncio
    async def test_senses_citing_the_same_passage_collapse(self):
        reply = _reply(
            "Cooling System",
            {
                "qualifier": "equipment",
                "definition": "The installed unit",
                "quote": "check the cooling system each spring",
            },
            {
                "qualifier": "maintenance target",
                "definition": "What gets serviced",
                "quote": "contractor check the cooling system",
            },
            {
                "qualifier": "category",
                "definition": "A class of systems",
                "quote": "check the cooling system each spring",
            },
        )
        classes = await _disambiguate(reply, "Cooling System")

        assert [c.label for c in classes] == ["Cooling System"]

    @pytest.mark.asyncio
    async def test_a_quote_that_does_not_name_the_term_is_no_evidence(self):
        reply = _reply(
            "Cooling System",
            {"qualifier": "equipment", "quote": "check the cooling system each spring"},
            {"qualifier": "efficiency", "quote": "A clean filter helps"},
        )
        classes = await _disambiguate(reply, "Cooling System")

        assert [c.label for c in classes] == ["Cooling System"]

    @pytest.mark.asyncio
    async def test_plain_string_senses_have_no_quote_and_collapse(self):
        reply = '{"ambiguous_terms": [{"term": "Python", "senses": ["language", "snake"]}]}'
        classes = await _disambiguate(reply, "Python", "Coroutine")

        assert [c.label for c in classes] == ["Python", "Coroutine"]
        assert classes[0].proposed_definition == "Python definition"

    @pytest.mark.asyncio
    async def test_long_qualifier_never_becomes_a_label(self):
        reply = _reply(
            "Task",
            {
                "qualifier": "An asyncio Task object that wraps a coroutine",
                "definition": "Wraps a coroutine",
                "quote": "Wrap a coroutine in a Task",
            },
            {
                "qualifier": "unit of work",
                "definition": "Work to do",
                "quote": "Each Task on the sprint board",
            },
        )
        classes = await _disambiguate(reply, "Task")

        assert [c.label for c in classes] == ["Task", "Task (sense 1)", "Task (unit of work)"]
        assert classes[1].proposed_definition == "Wraps a coroutine"

    @pytest.mark.asyncio
    async def test_fallback_qualifier_counts_kept_senses(self):
        reply = _reply(
            "Future",
            {"qualifier": "dictionary meaning", "quote": "the time to come"},
            {"qualifier": "", "definition": "An asyncio Future", "quote": "asyncio Future"},
            {"qualifier": "concurrent.futures object", "quote": "concurrent.futures Future"},
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
