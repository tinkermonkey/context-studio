"""
Integration tests for NLP-grounded typing in the open extraction orchestrator.

Tests the complete flow from input text to is_a typing triples.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from domain.extraction.ports import NounChunkSpan, OpenExtractionResult, OpenToken
from domain.pipelines.entities import PipelineRunStatus
from domain.pipelines.individual_extraction.configurations.open_v1 import (
    IndividualOpenV1Config,
)
from domain.pipelines.individual_extraction.open_orchestrator import (
    OpenIndividualExtractionOrchestrator,
)
from domain.pipelines.orchestration.base import PipelineState


class TestNLPGroundedTypingIntegration:
    """Integration tests for NLP-grounded typing orchestrator."""

    @pytest.mark.asyncio
    async def test_execute_with_nlp_grounded_typing_enabled(self):
        """Full orchestrator execution with NLP-grounded typing produces is_a triples."""
        ontology = Mock(id="ontology_id")
        ontology_repo = Mock()
        ontology_repo.get_by_identifier.return_value = ontology

        schema_index = Mock()
        schema_index.search.return_value = [
            Mock(
                external_id="technology.concept",
                identifier="tech_concept",
                label="Technology",
                entity_id="tech_id",
                score=0.85,
            )
        ]

        embedding_service = Mock()
        embedding_service.embed.return_value = [0.1, 0.2, 0.3]

        nlp_processor = Mock()
        nlp_processor.process_open.return_value = OpenExtractionResult(
            tokens=(
                OpenToken(
                    index=0, text="Technology", lemma="technology", pos="NOUN", tag="NN",
                    dep="nsubj", head_index=2, start=0, end=10, sentence_index=0,
                    is_stop=False, is_alpha=True,
                ),
                OpenToken(
                    index=1, text="is", lemma="be", pos="AUX", tag="VBZ",
                    dep="cop", head_index=2, start=11, end=13, sentence_index=0,
                    is_stop=False, is_alpha=True,
                ),
                OpenToken(
                    index=2, text="important", lemma="important", pos="ADJ", tag="JJ",
                    dep="ROOT", head_index=2, start=14, end=23, sentence_index=0,
                    is_stop=False, is_alpha=True,
                ),
            ),
            noun_chunks=(
                NounChunkSpan(
                    text="Technology", start_token=0, end_token=1, root_index=0,
                    start=0, end=10, sentence_index=0,
                ),
            ),
            sentence_count=1,
            language="en",
        )

        llm_provider = Mock()
        llm_provider.complete_async = AsyncMock(
            return_value=Mock(
                content='{"class": "technology.concept"}',
                tokens_in=10,
                tokens_out=20,
            )
        )

        config = {
            "nlp_grounded_typing": True,
            "nlp_typing_top_k": 8,
            "nlp_typing_threshold": 0.2,
        }

        orchestrator = OpenIndividualExtractionOrchestrator(
            llm_provider=llm_provider,
            nlp_processor=nlp_processor,
            embedding_service=embedding_service,
            schema_index=schema_index,
            ontology_repo=ontology_repo,
            config=config,
            run_id="run_123",
        )

        state = PipelineState(
            run_id="run_123",
            pipeline_type="individual_extraction",
            input_data={"text": "Technology is important.", "ontology_id": "ontology_id"},
            current_status=PipelineRunStatus.RUNNING,
        )

        result = await orchestrator.execute(state)

        assert result.current_status == PipelineRunStatus.COMPLETED
        assert result.extracted_triples is not None

        typing_triples = [
            t for t in result.extracted_triples
            if t["predicate"]["label"] == "is_a"
        ]
        assert len(typing_triples) > 0
        assert typing_triples[0]["subject"]["label"] == "Technology"
        assert typing_triples[0]["object"]["label"] == "technology.concept"

    @pytest.mark.asyncio
    async def test_execute_skips_typing_when_flag_disabled(self):
        """NLP-grounded typing is skipped when flag is False."""
        ontology = Mock(id="ontology_id")
        ontology_repo = Mock()
        ontology_repo.get_by_identifier.return_value = ontology

        schema_index = Mock()
        nlp_processor = Mock()
        nlp_processor.process_open.return_value = OpenExtractionResult(
            tokens=(
                OpenToken(
                    index=0, text="Test", lemma="test", pos="NOUN", tag="NN",
                    dep="nsubj", head_index=0, start=0, end=4, sentence_index=0,
                    is_stop=False, is_alpha=True,
                ),
            ),
            noun_chunks=(),
            sentence_count=1,
            language="en",
        )

        embedding_service = Mock()
        llm_provider = Mock()

        config = {
            "nlp_grounded_typing": False,
            "ground_to_schema": False,
        }

        orchestrator = OpenIndividualExtractionOrchestrator(
            llm_provider=llm_provider,
            nlp_processor=nlp_processor,
            embedding_service=embedding_service,
            schema_index=schema_index,
            ontology_repo=ontology_repo,
            config=config,
            run_id="run_123",
        )

        state = PipelineState(
            run_id="run_123",
            pipeline_type="individual_extraction",
            input_data={"text": "Test text.", "ontology_id": "ontology_id"},
            current_status=PipelineRunStatus.RUNNING,
        )

        result = await orchestrator.execute(state)

        assert result.current_status == PipelineRunStatus.COMPLETED
        llm_provider.complete_async.assert_not_called()

    @pytest.mark.asyncio
    async def test_config_validation_prevents_conflicting_flags(self):
        """Configuration validation prevents nlp_grounded_typing + ground_to_schema."""
        with pytest.raises(Exception) as exc_info:
            config = {
                "nlp_grounded_typing": True,
                "ground_to_schema": True,
            }
            IndividualOpenV1Config.from_dict(config)

        assert "mutually exclusive" in str(exc_info.value)
