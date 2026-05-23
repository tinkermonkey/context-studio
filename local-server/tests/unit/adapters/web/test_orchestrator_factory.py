"""
Unit tests for orchestrator factory composition root.

Tests the complete branching logic for all 6 orchestrator types,
dependency injection, and error handling for missing services.
"""

from unittest.mock import Mock

import pytest

from adapters.web.orchestrator_factory import create_orchestrator, create_pipeline_state
from domain.pipeline.ports import LLMProvider
from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.pipelines.individual_extraction.orchestrator import (
    IndividualExtractionOrchestrator,
    IndividualExtractionState,
)
from domain.pipelines.orchestration.noop import NoOpPipelineOrchestrator, NoOpPipelineState
from domain.pipelines.schema_extraction.orchestrator import (
    SchemaExtractionOrchestrator,
    SchemaExtractionState,
)
from domain.pipelines.schema_node_connection_refinement.orchestrator import (
    ConnectionRefinementOrchestrator,
    ConnectionRefinementState,
)
from domain.pipelines.schema_node_definition_refinement.orchestrator import (
    DefinitionRefinementOrchestrator,
    DefinitionRefinementState,
)
from domain.pipelines.schema_node_grounding.orchestrator import (
    SchemaGroundingOrchestrator,
    SchemaGroundingState,
)


@pytest.fixture
def mock_llm_provider() -> Mock:
    """Create a mock LLM provider."""
    return Mock(spec=LLMProvider)


@pytest.fixture
def mock_extraction_service() -> Mock:
    """Create a mock extraction service."""
    return Mock()


@pytest.fixture
def mock_ontology_repo() -> Mock:
    """Create a mock ontology repository."""
    return Mock()


@pytest.fixture
def mock_extraction_repo() -> Mock:
    """Create a mock extraction repository."""
    return Mock()


@pytest.fixture
def mock_grounding_adapter() -> Mock:
    """Create a mock grounding adapter."""
    return Mock()


@pytest.fixture
def mock_scorer() -> Mock:
    """Create a mock scorer."""
    return Mock()


class TestCreateOrchestratorNoOp:
    """Test create_orchestrator for NoOpPipelineOrchestrator."""

    def test_creates_noop_orchestrator_with_llm_provider(self, mock_llm_provider):
        """Test that NoOpPipelineOrchestrator is created with just llm_provider."""
        orchestrator = create_orchestrator(
            NoOpPipelineOrchestrator,
            llm_provider=mock_llm_provider,
        )

        assert isinstance(orchestrator, NoOpPipelineOrchestrator)
        assert orchestrator._llm_provider is mock_llm_provider

    def test_creates_noop_orchestrator_ignores_services(
        self, mock_llm_provider, mock_extraction_service
    ):
        """Test that NoOpPipelineOrchestrator ignores extra services."""
        services = {"extraction_service": mock_extraction_service}

        orchestrator = create_orchestrator(
            NoOpPipelineOrchestrator,
            llm_provider=mock_llm_provider,
            services=services,
        )

        assert isinstance(orchestrator, NoOpPipelineOrchestrator)
        assert orchestrator._llm_provider is mock_llm_provider


class TestCreateOrchestratorIndividualExtraction:
    """Test create_orchestrator for IndividualExtractionOrchestrator."""

    def test_creates_with_extraction_service(
        self,
        mock_llm_provider,
        mock_extraction_service,
    ):
        """Test that IndividualExtractionOrchestrator is created with extraction_service."""
        services = {"extraction_service": mock_extraction_service}

        orchestrator = create_orchestrator(
            IndividualExtractionOrchestrator,
            llm_provider=mock_llm_provider,
            services=services,
        )

        assert isinstance(orchestrator, IndividualExtractionOrchestrator)
        assert orchestrator._llm_provider is mock_llm_provider
        assert orchestrator._extraction_service is mock_extraction_service

    def test_raises_value_error_when_extraction_service_missing(self, mock_llm_provider):
        """Test that ValueError is raised when extraction_service is missing."""
        with pytest.raises(ValueError) as exc_info:
            create_orchestrator(
                IndividualExtractionOrchestrator,
                llm_provider=mock_llm_provider,
                services={},
            )

        assert "extraction_service is required" in str(exc_info.value)

    def test_raises_value_error_when_extraction_service_none(self, mock_llm_provider):
        """Test that ValueError is raised when extraction_service is None."""
        services = {"extraction_service": None}

        with pytest.raises(ValueError) as exc_info:
            create_orchestrator(
                IndividualExtractionOrchestrator,
                llm_provider=mock_llm_provider,
                services=services,
            )

        assert "extraction_service is required" in str(exc_info.value)

    def test_raises_value_error_when_extraction_service_empty_string(self, mock_llm_provider):
        """Test that ValueError is raised when extraction_service is empty string."""
        services = {"extraction_service": ""}

        with pytest.raises(ValueError) as exc_info:
            create_orchestrator(
                IndividualExtractionOrchestrator,
                llm_provider=mock_llm_provider,
                services=services,
            )

        assert "extraction_service is required" in str(exc_info.value)


class TestCreateOrchestratorSchemaExtraction:
    """Test create_orchestrator for SchemaExtractionOrchestrator."""

    def test_creates_schema_extraction_orchestrator(self, mock_llm_provider):
        """Test that SchemaExtractionOrchestrator is created with just llm_provider."""
        orchestrator = create_orchestrator(
            SchemaExtractionOrchestrator,
            llm_provider=mock_llm_provider,
        )

        assert isinstance(orchestrator, SchemaExtractionOrchestrator)
        assert orchestrator._llm_provider is mock_llm_provider

    def test_creates_schema_extraction_ignores_services(
        self,
        mock_llm_provider,
        mock_extraction_service,
    ):
        """Test that SchemaExtractionOrchestrator ignores extra services."""
        services = {"extraction_service": mock_extraction_service}

        orchestrator = create_orchestrator(
            SchemaExtractionOrchestrator,
            llm_provider=mock_llm_provider,
            services=services,
        )

        assert isinstance(orchestrator, SchemaExtractionOrchestrator)
        assert orchestrator._llm_provider is mock_llm_provider


class TestCreateOrchestratorSchemaGrounding:
    """Test create_orchestrator for SchemaGroundingOrchestrator."""

    def test_creates_with_grounding_adapter_and_scorer(
        self,
        mock_llm_provider,
        mock_grounding_adapter,
        mock_scorer,
    ):
        """Test that SchemaGroundingOrchestrator is created with adapter and scorer."""
        services = {
            "grounding_adapter": mock_grounding_adapter,
            "scorer": mock_scorer,
        }

        orchestrator = create_orchestrator(
            SchemaGroundingOrchestrator,
            llm_provider=mock_llm_provider,
            services=services,
        )

        assert isinstance(orchestrator, SchemaGroundingOrchestrator)
        assert orchestrator._llm_provider is mock_llm_provider
        assert orchestrator._grounding_adapter is mock_grounding_adapter
        assert orchestrator._scorer is mock_scorer
        assert orchestrator._config == {}

    def test_creates_with_optional_grounding_config(
        self,
        mock_llm_provider,
        mock_grounding_adapter,
        mock_scorer,
    ):
        """Test that SchemaGroundingOrchestrator accepts optional grounding_config."""
        config = {"threshold": 0.8}
        services = {
            "grounding_adapter": mock_grounding_adapter,
            "scorer": mock_scorer,
            "grounding_config": config,
        }

        orchestrator = create_orchestrator(
            SchemaGroundingOrchestrator,
            llm_provider=mock_llm_provider,
            services=services,
        )

        assert isinstance(orchestrator, SchemaGroundingOrchestrator)
        assert orchestrator._llm_provider is mock_llm_provider
        assert orchestrator._grounding_adapter is mock_grounding_adapter
        assert orchestrator._scorer is mock_scorer
        assert orchestrator._config == config

    def test_creates_with_empty_grounding_config_default(
        self,
        mock_llm_provider,
        mock_grounding_adapter,
        mock_scorer,
    ):
        """Test that SchemaGroundingOrchestrator uses empty dict when config not provided."""
        services = {
            "grounding_adapter": mock_grounding_adapter,
            "scorer": mock_scorer,
        }

        orchestrator = create_orchestrator(
            SchemaGroundingOrchestrator,
            llm_provider=mock_llm_provider,
            services=services,
        )

        assert isinstance(orchestrator, SchemaGroundingOrchestrator)
        assert orchestrator._config == {}

    def test_raises_value_error_when_grounding_adapter_missing(
        self,
        mock_llm_provider,
        mock_scorer,
    ):
        """Test that ValueError is raised when grounding_adapter is missing."""
        services = {"scorer": mock_scorer}

        with pytest.raises(ValueError) as exc_info:
            create_orchestrator(
                SchemaGroundingOrchestrator,
                llm_provider=mock_llm_provider,
                services=services,
            )

        assert "grounding_adapter is required" in str(exc_info.value)

    def test_raises_value_error_when_grounding_adapter_none(
        self,
        mock_llm_provider,
        mock_scorer,
    ):
        """Test that ValueError is raised when grounding_adapter is None."""
        services = {
            "grounding_adapter": None,
            "scorer": mock_scorer,
        }

        with pytest.raises(ValueError) as exc_info:
            create_orchestrator(
                SchemaGroundingOrchestrator,
                llm_provider=mock_llm_provider,
                services=services,
            )

        assert "grounding_adapter is required" in str(exc_info.value)

    def test_raises_value_error_when_scorer_missing(
        self,
        mock_llm_provider,
        mock_grounding_adapter,
    ):
        """Test that ValueError is raised when scorer is missing."""
        services = {"grounding_adapter": mock_grounding_adapter}

        with pytest.raises(ValueError) as exc_info:
            create_orchestrator(
                SchemaGroundingOrchestrator,
                llm_provider=mock_llm_provider,
                services=services,
            )

        assert "scorer is required" in str(exc_info.value)

    def test_raises_value_error_when_scorer_none(
        self,
        mock_llm_provider,
        mock_grounding_adapter,
    ):
        """Test that ValueError is raised when scorer is None."""
        services = {
            "grounding_adapter": mock_grounding_adapter,
            "scorer": None,
        }

        with pytest.raises(ValueError) as exc_info:
            create_orchestrator(
                SchemaGroundingOrchestrator,
                llm_provider=mock_llm_provider,
                services=services,
            )

        assert "scorer is required" in str(exc_info.value)


class TestCreateOrchestratorDefinitionRefinement:
    """Test create_orchestrator for DefinitionRefinementOrchestrator."""

    def test_creates_with_ontology_repo(
        self,
        mock_llm_provider,
        mock_ontology_repo,
    ):
        """Test that DefinitionRefinementOrchestrator is created with ontology_repo."""
        services = {"ontology_repo": mock_ontology_repo}

        orchestrator = create_orchestrator(
            DefinitionRefinementOrchestrator,
            llm_provider=mock_llm_provider,
            services=services,
        )

        assert isinstance(orchestrator, DefinitionRefinementOrchestrator)
        assert orchestrator._llm_provider is mock_llm_provider
        assert orchestrator._traversal._ontology is mock_ontology_repo
        assert orchestrator._traversal._extraction is None
        assert orchestrator._config == {}

    def test_creates_with_optional_extraction_repo(
        self,
        mock_llm_provider,
        mock_ontology_repo,
        mock_extraction_repo,
    ):
        """Test that DefinitionRefinementOrchestrator accepts optional extraction_repo."""
        services = {
            "ontology_repo": mock_ontology_repo,
            "extraction_repo": mock_extraction_repo,
        }

        orchestrator = create_orchestrator(
            DefinitionRefinementOrchestrator,
            llm_provider=mock_llm_provider,
            services=services,
        )

        assert isinstance(orchestrator, DefinitionRefinementOrchestrator)
        assert orchestrator._traversal._ontology is mock_ontology_repo
        assert orchestrator._traversal._extraction is mock_extraction_repo

    def test_creates_with_optional_refinement_config(
        self,
        mock_llm_provider,
        mock_ontology_repo,
    ):
        """Test that DefinitionRefinementOrchestrator accepts optional refinement_config."""
        config = {"depth": 2}
        services = {
            "ontology_repo": mock_ontology_repo,
            "refinement_config": config,
        }

        orchestrator = create_orchestrator(
            DefinitionRefinementOrchestrator,
            llm_provider=mock_llm_provider,
            services=services,
        )

        assert isinstance(orchestrator, DefinitionRefinementOrchestrator)
        assert orchestrator._config == config

    def test_creates_with_empty_refinement_config_default(
        self,
        mock_llm_provider,
        mock_ontology_repo,
    ):
        """Test that DefinitionRefinementOrchestrator uses empty dict when config not provided."""
        services = {"ontology_repo": mock_ontology_repo}

        orchestrator = create_orchestrator(
            DefinitionRefinementOrchestrator,
            llm_provider=mock_llm_provider,
            services=services,
        )

        assert isinstance(orchestrator, DefinitionRefinementOrchestrator)
        assert orchestrator._config == {}

    def test_raises_value_error_when_ontology_repo_missing(self, mock_llm_provider):
        """Test that ValueError is raised when ontology_repo is missing."""
        with pytest.raises(ValueError) as exc_info:
            create_orchestrator(
                DefinitionRefinementOrchestrator,
                llm_provider=mock_llm_provider,
                services={},
            )

        assert "ontology_repo is required" in str(exc_info.value)

    def test_raises_value_error_when_ontology_repo_none(self, mock_llm_provider):
        """Test that ValueError is raised when ontology_repo is None."""
        services = {"ontology_repo": None}

        with pytest.raises(ValueError) as exc_info:
            create_orchestrator(
                DefinitionRefinementOrchestrator,
                llm_provider=mock_llm_provider,
                services=services,
            )

        assert "ontology_repo is required" in str(exc_info.value)


class TestCreateOrchestratorConnectionRefinement:
    """Test create_orchestrator for ConnectionRefinementOrchestrator."""

    def test_creates_with_ontology_repo(
        self,
        mock_llm_provider,
        mock_ontology_repo,
    ):
        """Test that ConnectionRefinementOrchestrator is created with ontology_repo."""
        services = {"ontology_repo": mock_ontology_repo}

        orchestrator = create_orchestrator(
            ConnectionRefinementOrchestrator,
            llm_provider=mock_llm_provider,
            services=services,
        )

        assert isinstance(orchestrator, ConnectionRefinementOrchestrator)
        assert orchestrator._llm_provider is mock_llm_provider
        assert orchestrator._traversal._ontology is mock_ontology_repo
        assert orchestrator._traversal._extraction is None
        assert orchestrator._config == {}

    def test_creates_with_optional_extraction_repo(
        self,
        mock_llm_provider,
        mock_ontology_repo,
        mock_extraction_repo,
    ):
        """Test that ConnectionRefinementOrchestrator accepts optional extraction_repo."""
        services = {
            "ontology_repo": mock_ontology_repo,
            "extraction_repo": mock_extraction_repo,
        }

        orchestrator = create_orchestrator(
            ConnectionRefinementOrchestrator,
            llm_provider=mock_llm_provider,
            services=services,
        )

        assert isinstance(orchestrator, ConnectionRefinementOrchestrator)
        assert orchestrator._traversal._ontology is mock_ontology_repo
        assert orchestrator._traversal._extraction is mock_extraction_repo

    def test_creates_with_optional_refinement_config(
        self,
        mock_llm_provider,
        mock_ontology_repo,
    ):
        """Test that ConnectionRefinementOrchestrator accepts optional refinement_config."""
        config = {"breadth": 3}
        services = {
            "ontology_repo": mock_ontology_repo,
            "refinement_config": config,
        }

        orchestrator = create_orchestrator(
            ConnectionRefinementOrchestrator,
            llm_provider=mock_llm_provider,
            services=services,
        )

        assert isinstance(orchestrator, ConnectionRefinementOrchestrator)
        assert orchestrator._config == config

    def test_creates_with_empty_refinement_config_default(
        self,
        mock_llm_provider,
        mock_ontology_repo,
    ):
        """Test that ConnectionRefinementOrchestrator uses empty dict when config not provided."""
        services = {"ontology_repo": mock_ontology_repo}

        orchestrator = create_orchestrator(
            ConnectionRefinementOrchestrator,
            llm_provider=mock_llm_provider,
            services=services,
        )

        assert isinstance(orchestrator, ConnectionRefinementOrchestrator)
        assert orchestrator._config == {}

    def test_raises_value_error_when_ontology_repo_missing(self, mock_llm_provider):
        """Test that ValueError is raised when ontology_repo is missing."""
        with pytest.raises(ValueError) as exc_info:
            create_orchestrator(
                ConnectionRefinementOrchestrator,
                llm_provider=mock_llm_provider,
                services={},
            )

        assert "ontology_repo is required" in str(exc_info.value)

    def test_raises_value_error_when_ontology_repo_none(self, mock_llm_provider):
        """Test that ValueError is raised when ontology_repo is None."""
        services = {"ontology_repo": None}

        with pytest.raises(ValueError) as exc_info:
            create_orchestrator(
                ConnectionRefinementOrchestrator,
                llm_provider=mock_llm_provider,
                services=services,
            )

        assert "ontology_repo is required" in str(exc_info.value)


class TestCreateOrchestratorUnknownClass:
    """Test create_orchestrator error handling for unknown classes."""

    def test_raises_value_error_for_unknown_orchestrator_class(self, mock_llm_provider):
        """Test that ValueError is raised for unknown orchestrator class."""

        class UnknownOrchestrator:
            pass

        with pytest.raises(ValueError) as exc_info:
            create_orchestrator(
                UnknownOrchestrator,  # type: ignore
                llm_provider=mock_llm_provider,
            )

        assert "Unknown orchestrator class" in str(exc_info.value)
        assert "UnknownOrchestrator" in str(exc_info.value)


class TestCreateOrchestratorWithNoneServices:
    """Test create_orchestrator with None services dict."""

    def test_handles_none_services_dict(self, mock_llm_provider):
        """Test that None services dict is handled gracefully."""
        orchestrator = create_orchestrator(
            NoOpPipelineOrchestrator,
            llm_provider=mock_llm_provider,
            services=None,
        )

        assert isinstance(orchestrator, NoOpPipelineOrchestrator)


class TestCreatePipelineStateNoOp:
    """Test create_pipeline_state for NO_OP pipeline type."""

    def test_creates_noop_state(self, mock_llm_provider):
        """Test that NO_OP pipeline state is created correctly."""
        input_data = {"text": "test"}

        state = create_pipeline_state(
            run_id="run-123",
            pipeline_type=PipelineType.NO_OP,
            input_data=input_data,
            llm_provider=mock_llm_provider,
        )

        assert isinstance(state, NoOpPipelineState)
        assert state.run_id == "run-123"
        assert state.pipeline_type == PipelineType.NO_OP
        assert state.input_data == input_data
        assert state.current_status == PipelineRunStatus.PENDING
        assert state.llm_provider is mock_llm_provider
        assert state.result is None


class TestCreatePipelineStateSchemaExtraction:
    """Test create_pipeline_state for SCHEMA_EXTRACTION pipeline type."""

    def test_creates_schema_extraction_state(self, mock_llm_provider):
        """Test that SCHEMA_EXTRACTION pipeline state is created correctly."""
        input_data = {"schema": "test"}

        state = create_pipeline_state(
            run_id="run-456",
            pipeline_type=PipelineType.SCHEMA_EXTRACTION,
            input_data=input_data,
            llm_provider=mock_llm_provider,
        )

        assert isinstance(state, SchemaExtractionState)
        assert state.run_id == "run-456"
        assert state.pipeline_type == PipelineType.SCHEMA_EXTRACTION
        assert state.input_data == input_data
        assert state.current_status == PipelineRunStatus.PENDING
        assert state.llm_provider is mock_llm_provider
        assert state.result is None


class TestCreatePipelineStateSchemaNodeGrounding:
    """Test create_pipeline_state for SCHEMA_NODE_GROUNDING pipeline type."""

    def test_creates_grounding_state(self, mock_llm_provider):
        """Test that SCHEMA_NODE_GROUNDING pipeline state is created correctly."""
        input_data = {"node_id": "node-123"}

        state = create_pipeline_state(
            run_id="run-789",
            pipeline_type=PipelineType.SCHEMA_NODE_GROUNDING,
            input_data=input_data,
            llm_provider=mock_llm_provider,
        )

        assert isinstance(state, SchemaGroundingState)
        assert state.run_id == "run-789"
        assert state.pipeline_type == PipelineType.SCHEMA_NODE_GROUNDING
        assert state.input_data == input_data
        assert state.current_status == PipelineRunStatus.PENDING
        assert state.llm_provider is mock_llm_provider
        assert state.result is None


class TestCreatePipelineStateDefinitionRefinement:
    """Test create_pipeline_state for SCHEMA_NODE_DEFINITION_REFINEMENT pipeline type."""

    def test_creates_definition_refinement_state(self, mock_llm_provider):
        """Test that SCHEMA_NODE_DEFINITION_REFINEMENT pipeline state is created correctly."""
        input_data = {"definition": "test"}

        state = create_pipeline_state(
            run_id="run-101",
            pipeline_type=PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            input_data=input_data,
            llm_provider=mock_llm_provider,
        )

        assert isinstance(state, DefinitionRefinementState)
        assert state.run_id == "run-101"
        assert state.pipeline_type == PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT
        assert state.input_data == input_data
        assert state.current_status == PipelineRunStatus.PENDING
        assert state.llm_provider is mock_llm_provider
        assert state.result is None


class TestCreatePipelineStateConnectionRefinement:
    """Test create_pipeline_state for SCHEMA_NODE_CONNECTION_REFINEMENT pipeline type."""

    def test_creates_connection_refinement_state(self, mock_llm_provider):
        """Test that SCHEMA_NODE_CONNECTION_REFINEMENT pipeline state is created correctly."""
        input_data = {"connection": "test"}

        state = create_pipeline_state(
            run_id="run-202",
            pipeline_type=PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT,
            input_data=input_data,
            llm_provider=mock_llm_provider,
        )

        assert isinstance(state, ConnectionRefinementState)
        assert state.run_id == "run-202"
        assert state.pipeline_type == PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT
        assert state.input_data == input_data
        assert state.current_status == PipelineRunStatus.PENDING
        assert state.llm_provider is mock_llm_provider
        assert state.result is None


class TestCreatePipelineStateIndividualExtraction:
    """Test create_pipeline_state for INDIVIDUAL_EXTRACTION pipeline type."""

    def test_creates_individual_extraction_state(self, mock_llm_provider):
        """Test that INDIVIDUAL_EXTRACTION pipeline state is created correctly."""
        input_data = {"text": "extraction test"}

        state = create_pipeline_state(
            run_id="run-303",
            pipeline_type=PipelineType.INDIVIDUAL_EXTRACTION,
            input_data=input_data,
            llm_provider=mock_llm_provider,
        )

        assert isinstance(state, IndividualExtractionState)
        assert state.run_id == "run-303"
        assert state.pipeline_type == PipelineType.INDIVIDUAL_EXTRACTION
        assert state.input_data == input_data
        assert state.current_status == PipelineRunStatus.PENDING
        assert state.llm_provider is mock_llm_provider
        assert state.result is None


class TestCreatePipelineStateUnknownType:
    """Test create_pipeline_state with unknown pipeline type."""

    def test_returns_none_for_unknown_pipeline_type(self, mock_llm_provider):
        """Test that unknown pipeline type returns None (implicit behavior)."""

        class UnknownPipelineType:
            pass

        result = create_pipeline_state(
            run_id="run-test",
            pipeline_type=UnknownPipelineType(),  # type: ignore
            input_data={},
            llm_provider=mock_llm_provider,
        )

        assert result is None


class TestCreatePipelineStateCommonBehavior:
    """Test create_pipeline_state common behavior across all types."""

    def test_all_states_have_empty_parse_warnings_by_default(self, mock_llm_provider):
        """Test that all pipeline states start with empty parse_warnings."""
        for pipeline_type in [
            PipelineType.NO_OP,
            PipelineType.SCHEMA_EXTRACTION,
            PipelineType.SCHEMA_NODE_GROUNDING,
            PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT,
            PipelineType.INDIVIDUAL_EXTRACTION,
        ]:
            state = create_pipeline_state(
                run_id="run-test",
                pipeline_type=pipeline_type,
                input_data={},
                llm_provider=mock_llm_provider,
            )

            assert state.parse_warnings == []

    def test_state_preserves_input_data_identity(self, mock_llm_provider):
        """Test that input_data is stored as-is in state."""
        input_data = {"key": "value", "nested": {"data": 123}}

        state = create_pipeline_state(
            run_id="run-test",
            pipeline_type=PipelineType.NO_OP,
            input_data=input_data,
            llm_provider=mock_llm_provider,
        )

        assert state.input_data is input_data
        assert state.input_data == {"key": "value", "nested": {"data": 123}}
