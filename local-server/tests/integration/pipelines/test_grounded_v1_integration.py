"""
Integration test for grounded_v1 NLP-grounded typing variant.

Verifies end-to-end grounded_v1 stage execution with fakes and asserts the
expected triple shape (subject/predicate/object/confidence) without
requiring real LLM calls or cassettes.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json
from unittest.mock import Mock
from uuid import uuid4

import pytest

from domain.ontology.ports import SchemaMatch
from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.pipelines.individual_extraction.configurations.open_v1 import (
    get_open_v1_config,
)
from domain.pipelines.individual_extraction.open_orchestrator import (
    OpenIndividualExtractionOrchestrator,
)
from domain.pipelines.individual_extraction.orchestrator import IndividualExtractionState
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_llm_provider import FakeLLMProvider
from tests.fakes.fake_nlp_processor import FakeNLPProcessor
from tests.fakes.fake_schema_vector_index import FakeSchemaVectorIndex


class TestGroundedV1Integration:
    """
    Integration tests for grounded_v1 variant using project fakes.

    These tests focus on grounded_v1 variant-specific behavior and configuration
    using better fake implementations (FakeLLMProvider, FakeSchemaVectorIndex).
    Generic orchestrator behavior tests are in test_nlp_grounded_typing_orchestrator.py.
    """

    @pytest.mark.asyncio
    async def test_grounded_v1_produces_typing_triples_with_expected_shape(self):
        """
        Verify grounded_v1 end-to-end execution produces is_a triples with
        subject/predicate/object/confidence fields.
        """
        # Build fake ontology (mock is sufficient for test)
        ontology_repo = Mock()
        ontology_id = str(uuid4())
        ontology = Mock(id=ontology_id)
        ontology_repo.get_by_identifier.return_value = ontology

        # Classes will be returned by schema index searches, not queried from repo
        # Set repo to return ontology when requested
        ontology_repo.get_taxonomy.return_value = ontology

        # Define class IDs
        class_1_id = str(uuid4())
        class_2_id = str(uuid4())

        # Set up schema vector index with matching classes
        schema_index = FakeSchemaVectorIndex()
        schema_index.set_search_results(
            [
                SchemaMatch(
                    external_id="class1.concept",
                    identifier="class_1_id",
                    label="Technology System",
                    entity_id=class_1_id,
                    kind="class",
                    score=0.92,
                    matched_field="title",
                ),
                SchemaMatch(
                    external_id="class2.concept",
                    identifier="class_2_id",
                    label="Software Architecture",
                    entity_id=class_2_id,
                    kind="class",
                    score=0.85,
                    matched_field="title",
                ),
            ],
            taxonomies={class_1_id: ontology_id, class_2_id: ontology_id},
        )

        # Set up fake LLM provider for typing confirmation
        # Returns JSON with confirmed class
        typing_confirm_response = json.dumps({"class": "class1.concept"})
        llm_provider = FakeLLMProvider(response_content=typing_confirm_response)

        # Set up fake NLP processor with a noun chunk
        nlp_processor = FakeNLPProcessor()

        # Set up embedding service
        embedding = FakeEmbeddingService()

        # Build grounded_v1 config
        config = dict(get_open_v1_config())
        config.update(
            {
                "nlp_grounded_typing": True,
                "ground_to_schema": False,
                "require_schema_match": False,
                "nlp_typing_top_k": 5,
                "nlp_typing_threshold": 0.2,
                "nlp_typing_matching_mode": "max",
                "llm_canonicalization": True,
            }
        )

        # Create orchestrator
        orch = OpenIndividualExtractionOrchestrator(
            llm_provider=llm_provider,
            nlp_processor=nlp_processor,
            embedding_service=embedding,
            schema_index=schema_index,
            ontology_repo=ontology_repo,
            config=config,
        )

        # Create input state
        input_data = {
            "text": "Technology System is the foundation. Software Architecture defines structure.",
            "ontology_id": ontology_id,
        }
        state = IndividualExtractionState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            input_data=input_data,
        )

        # Execute
        result_state = await orch.execute(state)

        # Verify completion status
        assert result_state.current_status == PipelineRunStatus.COMPLETED
        assert result_state.result is not None

        # Extract triples
        triples = result_state.result.get("triples", [])

        # Verify typing triples are produced
        typing_triples = [t for t in triples if t.get("predicate", {}).get("label") == "is_a"]
        assert len(typing_triples) > 0, "Expected at least one typing triple (is_a predicate)"

        # Verify triple shape for each typing triple
        for triple in typing_triples:
            # Check required fields
            assert "subject" in triple, "Triple missing subject field"
            assert "predicate" in triple, "Triple missing predicate field"
            assert "object" in triple, "Triple missing object field"
            assert "confidence" in triple, "Triple missing confidence field"

            # Verify subject structure
            subject = triple["subject"]
            assert "label" in subject, "Subject missing label"
            assert isinstance(subject["label"], str), "Subject label must be a string"

            # Verify predicate structure
            predicate = triple["predicate"]
            assert predicate["label"] == "is_a", "Expected is_a predicate"

            # Verify object structure (should be a schema class)
            obj = triple["object"]
            assert "label" in obj, "Object missing label"
            assert isinstance(obj["label"], str), "Object label must be a string"

            # Verify confidence value
            confidence = triple["confidence"]
            assert isinstance(confidence, (int, float)), "Confidence must be numeric"
            assert 0.0 <= confidence <= 1.0, f"Confidence must be in [0, 1], got {confidence}"

    @pytest.mark.skip(
        reason=(
            "Config validation tested in "
            "test_nlp_grounded_typing_orchestrator.py::"
            "test_config_validation_prevents_conflicting_flags"
        )
    )
    def test_grounded_v1_config_validation(self):
        """Config validation is tested elsewhere."""
        pass

    @pytest.mark.asyncio
    async def test_grounded_v1_skips_typing_when_no_schema_index(self):
        """Typing stage skips gracefully when schema index is not available."""
        config = dict(get_open_v1_config())
        config.update(
            {
                "nlp_grounded_typing": True,
                "ground_to_schema": False,
                "require_schema_match": False,
            }
        )

        orch = OpenIndividualExtractionOrchestrator(
            llm_provider=FakeLLMProvider(),
            nlp_processor=FakeNLPProcessor(),
            embedding_service=FakeEmbeddingService(),
            schema_index=None,  # No schema index
            ontology_repo=Mock(),
            config=config,
        )

        input_data = {
            "text": "Test text with noun chunks.",
            "ontology_id": str(uuid4()),
        }
        state = IndividualExtractionState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            input_data=input_data,
        )

        result_state = await orch.execute(state)

        # Should complete without error
        assert result_state.current_status == PipelineRunStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_grounded_v1_accepts_definition_preferred_config(self):
        """
        Smoke test: grounded_v1 accepts and processes definition_preferred matching mode.

        Note: This test verifies the config is accepted and execution completes.
        Behavioral verification of definition-preferred ranking would require
        observable differences in selected candidates, which the fake cannot verify.
        """
        # Build ontology with classes that have definitions
        ontology_repo = Mock()
        ontology_id = str(uuid4())
        ontology = Mock(id=ontology_id)
        ontology_repo.get_by_identifier.return_value = ontology
        ontology_repo.get_taxonomy.return_value = ontology

        class_with_def_id = str(uuid4())
        class_without_def_id = str(uuid4())

        # Schema index returns both classes
        schema_index = FakeSchemaVectorIndex()
        schema_index.set_search_results(
            [
                SchemaMatch(
                    external_id="tech.system",
                    identifier="tech_system_id",
                    label="Technology System",
                    entity_id=class_with_def_id,
                    kind="class",
                    score=0.80,
                    matched_field="title",
                ),
                SchemaMatch(
                    external_id="tech.component",
                    identifier="tech_component_id",
                    label="Technology Component",
                    entity_id=class_without_def_id,
                    kind="class",
                    score=0.82,  # Slightly higher vector score but no definition
                    matched_field="title",
                ),
            ],
            taxonomies={
                class_with_def_id: ontology_id,
                class_without_def_id: ontology_id,
            },
        )

        llm_provider = FakeLLMProvider(
            response_content=json.dumps({"class": "tech.system"})
        )
        nlp_processor = FakeNLPProcessor()
        embedding = FakeEmbeddingService()

        # Use definition_preferred mode
        config = dict(get_open_v1_config())
        config.update(
            {
                "nlp_grounded_typing": True,
                "ground_to_schema": False,
                "require_schema_match": False,
                "nlp_typing_top_k": 5,
                "nlp_typing_threshold": 0.2,
                "nlp_typing_matching_mode": "definition_preferred",
            }
        )

        orch = OpenIndividualExtractionOrchestrator(
            llm_provider=llm_provider,
            nlp_processor=nlp_processor,
            embedding_service=embedding,
            schema_index=schema_index,
            ontology_repo=ontology_repo,
            config=config,
        )

        input_data = {
            "text": "Technology is important.",
            "ontology_id": ontology_id,
        }
        state = IndividualExtractionState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            input_data=input_data,
        )

        result_state = await orch.execute(state)

        # Verify completion
        assert result_state.current_status == PipelineRunStatus.COMPLETED
        assert result_state.result is not None
