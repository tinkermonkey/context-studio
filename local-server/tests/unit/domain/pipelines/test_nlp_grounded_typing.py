"""
Unit tests for NLP-grounded typing in the open individual-extraction orchestrator.

Tests the noun-chunk → vector-retrieve → LLM-confirm pipeline.
"""

from unittest.mock import Mock

import pytest

from domain.extraction.ports import NounChunkSpan, OpenExtractionResult, OpenToken
from domain.pipelines.individual_extraction.configurations.open_v1 import (
    IndividualOpenV1Config,
)
from domain.pipelines.individual_extraction.open_orchestrator import (
    OpenIndividualExtractionOrchestrator,
)


class FakeLLMProvider:
    """Fake LLM provider for testing."""

    def __init__(self, responses=None):
        self.responses = responses or []
        self.call_count = 0

    async def complete_async(self, system_prompt, user_prompt, model=None, **kwargs):
        """Return a pre-canned response."""
        from domain.pipelines.ports import LLMResponse

        if self.call_count < len(self.responses):
            content = self.responses[self.call_count]
        else:
            content = '{"class": "none"}'
        self.call_count += 1
        return LLMResponse(
            content=content,
            tokens_in=10,
            tokens_out=20,
            duration_ms=100.0,
            finish_reason="stop",
            model=model or "test-model",
        )


class TestNLPGroundedTypingConfig:
    """Test configuration validation for NLP-grounded typing."""

    def test_config_with_nlp_grounded_typing_enabled(self):
        """NLP-grounded typing config flags are accepted."""
        config = {
            "nlp_grounded_typing": True,
            "nlp_typing_top_k": 10,
            "nlp_typing_threshold": 0.3,
            "nlp_typing_matching_mode": "max",
        }
        cfg = IndividualOpenV1Config.from_dict(config)
        assert cfg.nlp_grounded_typing is True
        assert cfg.nlp_typing_top_k == 10
        assert cfg.nlp_typing_threshold == 0.3
        assert cfg.nlp_typing_matching_mode == "max"

    def test_config_nlp_grounded_typing_mutually_exclusive_with_ground_to_schema(self):
        """nlp_grounded_typing and ground_to_schema are mutually exclusive."""
        config = {
            "nlp_grounded_typing": True,
            "ground_to_schema": True,
        }
        with pytest.raises(Exception) as exc_info:
            IndividualOpenV1Config.from_dict(config)
        assert "mutually exclusive" in str(exc_info.value)

    def test_config_nlp_grounded_typing_mutually_exclusive_with_require_schema_match(
        self,
    ):
        """nlp_grounded_typing and require_schema_match are mutually exclusive."""
        config = {
            "nlp_grounded_typing": True,
            "require_schema_match": True,
        }
        with pytest.raises(Exception) as exc_info:
            IndividualOpenV1Config.from_dict(config)
        assert "mutually exclusive" in str(exc_info.value)

    def test_config_nlp_typing_top_k_validation(self):
        """nlp_typing_top_k must be >= 1."""
        config = {
            "nlp_grounded_typing": True,
            "nlp_typing_top_k": 0,
        }
        with pytest.raises(Exception) as exc_info:
            IndividualOpenV1Config.from_dict(config)
        assert "nlp_typing_top_k" in str(exc_info.value)

    def test_config_nlp_typing_threshold_validation(self):
        """nlp_typing_threshold must be in [0, 1]."""
        config = {
            "nlp_grounded_typing": True,
            "nlp_typing_threshold": 1.5,
        }
        with pytest.raises(Exception) as exc_info:
            IndividualOpenV1Config.from_dict(config)
        assert "nlp_typing_threshold" in str(exc_info.value)

    def test_config_nlp_typing_matching_mode_validation(self):
        """nlp_typing_matching_mode must be 'max' or 'definition_preferred'."""
        config = {
            "nlp_grounded_typing": True,
            "nlp_typing_matching_mode": "invalid",
        }
        with pytest.raises(Exception) as exc_info:
            IndividualOpenV1Config.from_dict(config)
        assert "nlp_typing_matching_mode" in str(exc_info.value)


class TestSentenceTexts:
    """Test the sentence-text extraction helper."""

    def test_sentence_texts_single_sentence(self):
        """Extract text for a single-sentence document."""
        text = "The quick brown fox jumps."
        tokens = [
            Mock(index=0, sentence_index=0, start=0, end=3, text="The"),
            Mock(index=1, sentence_index=0, start=4, end=9, text="quick"),
            Mock(index=2, sentence_index=0, start=10, end=15, text="brown"),
            Mock(index=3, sentence_index=0, start=16, end=19, text="fox"),
            Mock(index=4, sentence_index=0, start=20, end=25, text="jumps"),
        ]

        result = OpenIndividualExtractionOrchestrator._sentence_texts(text, tokens)

        assert 0 in result
        assert result[0] == "The quick brown fox jumps"

    def test_sentence_texts_multiple_sentences(self):
        """Extract text for a multi-sentence document."""
        text = "First sentence. Second sentence."
        tokens = [
            Mock(index=0, sentence_index=0, start=0, end=5, text="First"),
            Mock(index=1, sentence_index=0, start=6, end=14, text="sentence"),
            Mock(index=2, sentence_index=1, start=16, end=22, text="Second"),
            Mock(index=3, sentence_index=1, start=23, end=31, text="sentence"),
        ]

        result = OpenIndividualExtractionOrchestrator._sentence_texts(text, tokens)

        assert result[0] == "First sentence"
        assert result[1] == "Second sentence"


class TestMakeTypingTriple:
    """Test the typing-triple builder."""

    def test_make_typing_triple_with_external_id(self):
        """Create typing triple using external_id."""
        match = Mock(
            external_id="technology.node",
            identifier="tech_node",
            label="Technology Node",
            score=0.85,
        )
        triple = OpenIndividualExtractionOrchestrator._make_typing_triple("my_label", match)

        assert triple["subject"]["label"] == "my_label"
        assert triple["subject"]["kind"] == "individual"
        assert triple["predicate"]["label"] == "is_a"
        assert triple["predicate"]["kind"] == "property"
        assert triple["object"]["label"] == "technology.node"
        assert triple["object"]["kind"] == "class"
        assert triple["confidence"] == 0.85

    def test_make_typing_triple_fallback_to_identifier(self):
        """Create typing triple falling back to identifier when no external_id."""
        match = Mock(
            external_id=None,
            identifier="tech_node",
            label="Technology Node",
            score=0.75,
        )
        triple = OpenIndividualExtractionOrchestrator._make_typing_triple("example", match)

        assert triple["object"]["label"] == "tech_node"

    def test_make_typing_triple_fallback_to_label(self):
        """Create typing triple falling back to label when no external_id/identifier."""
        match = Mock(
            external_id=None,
            identifier=None,
            label="Technology",
            score=0.65,
        )
        triple = OpenIndividualExtractionOrchestrator._make_typing_triple("test", match)

        assert triple["object"]["label"] == "Technology"
        assert triple["confidence"] == 0.65

    def test_make_typing_triple_label_is_verbatim(self):
        """Subject label is character-identical to source text (no transformation)."""
        match = Mock(
            external_id="class_ref",
            identifier=None,
            label="ClassName",
            score=0.90,
        )
        label = "My Exact Label With Capitals"
        triple = OpenIndividualExtractionOrchestrator._make_typing_triple(label, match)

        assert triple["subject"]["label"] == "My Exact Label With Capitals"


class TestConfirmClassForChunk:
    """Test the LLM-based class confirmation."""

    @pytest.mark.asyncio
    async def test_confirm_class_picks_valid_candidate(self):
        """LLM picks the best-fitting candidate from the retrieved set."""
        orchestrator = OpenIndividualExtractionOrchestrator(
            llm_provider=FakeLLMProvider(['{"class": "technology.node"}']),
            nlp_processor=Mock(),
            embedding_service=Mock(),
            schema_index=Mock(),
            ontology_repo=Mock(),
        )

        matches = [
            Mock(
                external_id="technology.node",
                identifier="tech_node",
                label="Technology",
                entity_id="id1",
                score=0.85,
            ),
            Mock(
                external_id="methodology.node",
                identifier="method_node",
                label="Methodology",
                entity_id="id2",
                score=0.60,
            ),
        ]

        result = await orchestrator._confirm_class_for_chunk(
            "technology", "Technology drives innovation.", matches
        )

        assert result is not None
        assert result.external_id == "technology.node"

    @pytest.mark.asyncio
    async def test_confirm_class_returns_none_for_none_choice(self):
        """LLM choosing 'none' returns None."""
        orchestrator = OpenIndividualExtractionOrchestrator(
            llm_provider=FakeLLMProvider(['{"class": "none"}']),
            nlp_processor=Mock(),
            embedding_service=Mock(),
            schema_index=Mock(),
            ontology_repo=Mock(),
        )

        matches = [
            Mock(
                external_id="technology.node",
                identifier="tech_node",
                label="Technology",
                entity_id="id1",
                score=0.85,
            ),
        ]

        result = await orchestrator._confirm_class_for_chunk(
            "random", "This is a random word.", matches
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_confirm_class_returns_none_for_empty_candidates(self):
        """No candidates yields None (LLM never called)."""
        orchestrator = OpenIndividualExtractionOrchestrator(
            llm_provider=FakeLLMProvider(),
            nlp_processor=Mock(),
            embedding_service=Mock(),
            schema_index=Mock(),
            ontology_repo=Mock(),
        )

        matches = [
            Mock(
                external_id=None,
                identifier=None,
                label=None,
                entity_id="id1",
                score=0.85,
            ),
        ]

        result = await orchestrator._confirm_class_for_chunk("test", "Test sentence.", matches)

        assert result is None

    @pytest.mark.asyncio
    async def test_confirm_class_handles_llm_failure_gracefully(self):
        """LLM failure returns None (doesn't crash)."""

        class FailingLLM:
            async def complete_async(self, **kwargs):
                raise RuntimeError("LLM service unavailable")

        orchestrator = OpenIndividualExtractionOrchestrator(
            llm_provider=FailingLLM(),
            nlp_processor=Mock(),
            embedding_service=Mock(),
            schema_index=Mock(),
            ontology_repo=Mock(),
        )

        matches = [
            Mock(
                external_id="technology.node",
                identifier="tech_node",
                label="Technology",
                entity_id="id1",
                score=0.85,
            ),
        ]

        result = await orchestrator._confirm_class_for_chunk("technology", "Test.", matches)

        assert result is None

    @pytest.mark.asyncio
    async def test_confirm_class_rejects_fabricated_class_reference(self):
        """LLM choosing a fabricated class reference returns None (safety guarantee)."""
        orchestrator = OpenIndividualExtractionOrchestrator(
            llm_provider=FakeLLMProvider(['{"class": "invented.fabricated_class"}']),
            nlp_processor=Mock(),
            embedding_service=Mock(),
            schema_index=Mock(),
            ontology_repo=Mock(),
        )

        matches = [
            Mock(
                external_id="technology.node",
                identifier="tech_node",
                label="Technology",
                entity_id="id1",
                score=0.85,
            ),
            Mock(
                external_id="methodology.node",
                identifier="method_node",
                label="Methodology",
                entity_id="id2",
                score=0.60,
            ),
        ]

        result = await orchestrator._confirm_class_for_chunk(
            "unknown", "The unknown fabricated class.", matches
        )

        assert result is None


class TestNLPGroundedTyping:
    """Test the full NLP-grounded typing pipeline."""

    @pytest.mark.asyncio
    async def test_skip_when_no_schema_index(self):
        """No-op when schema_index is None."""
        orchestrator = OpenIndividualExtractionOrchestrator(
            llm_provider=Mock(),
            nlp_processor=Mock(),
            embedding_service=Mock(),
            schema_index=None,
            ontology_repo=Mock(),
        )

        triples = [{"subject": {"label": "test"}, "predicate": {"label": "test"}}]
        open_result = OpenExtractionResult(
            tokens=(),
            noun_chunks=(),
            sentence_count=0,
            language="en",
        )
        result = await orchestrator._type_individuals_nlp_grounded(
            triples, "Test text.", None, open_result
        )

        assert result == triples

    @pytest.mark.asyncio
    async def test_skip_when_no_ontology_repo(self):
        """No-op when ontology_repo is None."""
        orchestrator = OpenIndividualExtractionOrchestrator(
            llm_provider=Mock(),
            nlp_processor=Mock(),
            embedding_service=Mock(),
            schema_index=Mock(),
            ontology_repo=None,
        )

        triples = [{"subject": {"label": "test"}, "predicate": {"label": "test"}}]
        open_result = OpenExtractionResult(
            tokens=(),
            noun_chunks=(),
            sentence_count=0,
            language="en",
        )
        result = await orchestrator._type_individuals_nlp_grounded(
            triples, "Test text.", None, open_result
        )

        assert result == triples

    @pytest.mark.asyncio
    async def test_skip_when_no_ontology_id(self):
        """No-op when ontology_id is None."""
        orchestrator = OpenIndividualExtractionOrchestrator(
            llm_provider=Mock(),
            nlp_processor=Mock(),
            embedding_service=Mock(),
            schema_index=Mock(),
            ontology_repo=Mock(),
        )

        triples = [{"subject": {"label": "test"}, "predicate": {"label": "test"}}]
        open_result = OpenExtractionResult(
            tokens=(),
            noun_chunks=(),
            sentence_count=0,
            language="en",
        )
        result = await orchestrator._type_individuals_nlp_grounded(
            triples, "Test text.", None, open_result
        )

        assert result == triples

    @pytest.mark.asyncio
    async def test_skip_when_ontology_not_found(self):
        """No-op when ontology cannot be resolved."""
        ontology_repo = Mock()
        ontology_repo.get_by_identifier.return_value = None

        orchestrator = OpenIndividualExtractionOrchestrator(
            llm_provider=Mock(),
            nlp_processor=Mock(),
            embedding_service=Mock(),
            schema_index=Mock(),
            ontology_repo=ontology_repo,
        )

        triples = [{"subject": {"label": "test"}, "predicate": {"label": "test"}}]
        open_result = OpenExtractionResult(
            tokens=(),
            noun_chunks=(),
            sentence_count=0,
            language="en",
        )
        result = await orchestrator._type_individuals_nlp_grounded(
            triples, "Test text.", "unknown_ontology", open_result
        )

        assert result == triples
        ontology_repo.get_by_identifier.assert_called_once_with("unknown_ontology")

    @pytest.mark.asyncio
    async def test_deduplicates_case_insensitive_chunk_text(self):
        """Case-insensitive duplicate chunk text produces only one typing triple."""
        ontology = Mock(id="ontology_id")
        ontology_repo = Mock()
        ontology_repo.get_by_identifier.return_value = ontology
        ontology_repo.get_class.return_value = None

        schema_index = Mock()
        schema_index.search.return_value = [
            Mock(
                external_id="class_ref",
                identifier="class_id",
                label="Class",
                entity_id="class_entity_id",
                score=0.85,
            )
        ]

        embedding_service = Mock()
        embedding_service.embed.return_value = [0.1, 0.2, 0.3]

        nlp_processor = Mock()
        nlp_processor.process_open.return_value = OpenExtractionResult(
            tokens=(
                OpenToken(
                    index=0,
                    text="Technology",
                    lemma="technology",
                    pos="NOUN",
                    tag="NN",
                    dep="nsubj",
                    head_index=0,
                    start=0,
                    end=10,
                    sentence_index=0,
                    is_stop=False,
                    is_alpha=True,
                ),
                OpenToken(
                    index=1,
                    text="drives",
                    lemma="drive",
                    pos="VERB",
                    tag="VBZ",
                    dep="ROOT",
                    head_index=1,
                    start=11,
                    end=17,
                    sentence_index=0,
                    is_stop=False,
                    is_alpha=True,
                ),
            ),
            noun_chunks=(
                NounChunkSpan(
                    text="Technology",
                    start_token=0,
                    end_token=1,
                    root_index=0,
                    start=0,
                    end=10,
                    sentence_index=0,
                ),
                NounChunkSpan(
                    text="technology",
                    start_token=0,
                    end_token=1,
                    root_index=0,
                    start=0,
                    end=10,
                    sentence_index=0,
                ),
            ),
            sentence_count=1,
            language="en",
        )

        llm_provider = FakeLLMProvider(['{"class": "class_ref"}', '{"class": "class_ref"}'])

        orchestrator = OpenIndividualExtractionOrchestrator(
            llm_provider=llm_provider,
            nlp_processor=nlp_processor,
            embedding_service=embedding_service,
            schema_index=schema_index,
            ontology_repo=ontology_repo,
        )

        open_result = nlp_processor.process_open.return_value

        triples = []
        result = await orchestrator._type_individuals_nlp_grounded(
            triples,
            "Technology drives innovation. technology is important.",
            "ontology_id",
            open_result,
        )

        typing_triples = [t for t in result if t["predicate"]["label"] == "is_a"]
        assert len(typing_triples) == 1
        assert typing_triples[0]["subject"]["label"] == "Technology"

    @pytest.mark.asyncio
    async def test_filters_chunk_not_rooted_in_noun_propn(self):
        """Chunks not rooted in NOUN/PROPN are skipped."""
        ontology = Mock(id="ontology_id")
        ontology_repo = Mock()
        ontology_repo.get_by_identifier.return_value = ontology

        embedding_service = Mock()
        embedding_service.embed.return_value = [0.1, 0.2, 0.3]

        nlp_processor = Mock()
        nlp_processor.process_open.return_value = OpenExtractionResult(
            tokens=(
                OpenToken(
                    index=0,
                    text="Very",
                    lemma="very",
                    pos="ADV",
                    tag="RB",
                    dep="advmod",
                    head_index=1,
                    start=0,
                    end=4,
                    sentence_index=0,
                    is_stop=False,
                    is_alpha=True,
                ),
                OpenToken(
                    index=1,
                    text="quickly",
                    lemma="quickly",
                    pos="ADV",
                    tag="RB",
                    dep="ROOT",
                    head_index=1,
                    start=5,
                    end=12,
                    sentence_index=0,
                    is_stop=False,
                    is_alpha=True,
                ),
            ),
            noun_chunks=(
                NounChunkSpan(
                    text="Very quickly",
                    start_token=0,
                    end_token=2,
                    root_index=1,
                    start=0,
                    end=12,
                    sentence_index=0,
                ),
            ),
            sentence_count=1,
            language="en",
        )

        orchestrator = OpenIndividualExtractionOrchestrator(
            llm_provider=Mock(),
            nlp_processor=nlp_processor,
            embedding_service=embedding_service,
            schema_index=Mock(),
            ontology_repo=ontology_repo,
        )

        open_result = nlp_processor.process_open.return_value

        triples = []
        result = await orchestrator._type_individuals_nlp_grounded(
            triples, "Very quickly.", "ontology_id", open_result
        )

        typing_triples = [t for t in result if t["predicate"]["label"] == "is_a"]
        assert len(typing_triples) == 0

    @pytest.mark.asyncio
    async def test_filters_stopword_roots(self):
        """Chunks rooted in stopwords are skipped."""
        ontology = Mock(id="ontology_id")
        ontology_repo = Mock()
        ontology_repo.get_by_identifier.return_value = ontology

        embedding_service = Mock()
        embedding_service.embed.return_value = [0.1, 0.2, 0.3]

        nlp_processor = Mock()
        nlp_processor.process_open.return_value = OpenExtractionResult(
            tokens=(
                OpenToken(
                    index=0,
                    text="the",
                    lemma="the",
                    pos="DET",
                    tag="DT",
                    dep="det",
                    head_index=1,
                    start=0,
                    end=3,
                    sentence_index=0,
                    is_stop=True,
                    is_alpha=True,
                ),
                OpenToken(
                    index=1,
                    text="dog",
                    lemma="dog",
                    pos="NOUN",
                    tag="NN",
                    dep="nsubj",
                    head_index=1,
                    start=4,
                    end=7,
                    sentence_index=0,
                    is_stop=False,
                    is_alpha=True,
                ),
            ),
            noun_chunks=(
                NounChunkSpan(
                    text="the",
                    start_token=0,
                    end_token=1,
                    root_index=0,
                    start=0,
                    end=3,
                    sentence_index=0,
                ),
            ),
            sentence_count=1,
            language="en",
        )

        orchestrator = OpenIndividualExtractionOrchestrator(
            llm_provider=Mock(),
            nlp_processor=nlp_processor,
            embedding_service=embedding_service,
            schema_index=Mock(),
            ontology_repo=ontology_repo,
        )

        open_result = nlp_processor.process_open.return_value

        triples = []
        result = await orchestrator._type_individuals_nlp_grounded(
            triples, "the dog", "ontology_id", open_result
        )

        typing_triples = [t for t in result if t["predicate"]["label"] == "is_a"]
        assert len(typing_triples) == 0
