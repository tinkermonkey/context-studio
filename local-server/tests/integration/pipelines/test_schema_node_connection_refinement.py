"""
Integration tests for the schema_node_connection_refinement pipeline.

The pipeline reads a class node (the "scope"), traverses its neighborhood,
asks an LLM to propose connection deltas (add/modify/remove relationships)
backed by groundings and extraction usages, and returns them on state.result.

Focused tests:
  - Bootstrap registration produces orchestrator + config
  - execute() against a canon class yields deltas with the expected schema
  - Missing scope_id raises PipelineInputError
  - Confidence values are in [0, 1] and deltas declare their operation
  - Deltas are capped at 5 even if the LLM returns more
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.ontology.entities import Class, ConceptScheme, Taxonomy
from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.pipelines.exceptions import PipelineInputError
from domain.pipelines.refinement.neighborhood import SchemaNeighborhoodTraversal
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from domain.pipelines.schema_node_connection_refinement.bootstrap import (
    register_schema_node_connection_refinement,
)
from domain.pipelines.schema_node_connection_refinement.orchestrator import (
    ConnectionRefinementOrchestrator,
    ConnectionRefinementState,
)
from tests.fakes.fake_llm_provider import FakeLLMProvider
from tests.integration.fixtures.pipelines.harness import (
    run_pipeline_against_fixture,
)

# ---------------------------------------------------------------------------- #
# Fixtures                                                                     #
# ---------------------------------------------------------------------------- #


@pytest.fixture
def session_factory():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_url = f"sqlite:///{Path(tmpdir) / 'test.db'}"
        engine = create_engine(db_url)
        Base.metadata.create_all(engine)
        yield sessionmaker(bind=engine)


@pytest.fixture
def ontology_with_microservice_class(session_factory):
    """Repo seeded with a canon-aligned Microservices class to refine connections for."""
    repo = SQLiteOntologyRepository(session_factory)
    tax = Taxonomy(
        id=str(uuid4()),
        identifier="software_architecture",
        title="Software Architecture",
    )
    repo.save_taxonomy(tax)
    scheme = ConceptScheme(
        id=str(uuid4()),
        identifier="architectural_styles",
        taxonomy_id=tax.id,
        title="Architectural Styles",
    )
    repo.save_concept_scheme(scheme)
    ms_cls = Class(
        id=str(uuid4()),
        identifier="microservices_architecture",
        concept_scheme_id=scheme.id,
        taxonomy_id=tax.id,
        title="Microservices Architecture",
        description=(
            "An architectural style that structures an application as a suite of "
            "small, independently deployable services."
        ),
    )
    repo.save_class(ms_cls)
    return repo, ms_cls


@pytest.fixture
def traversal(ontology_with_microservice_class):
    repo, _ = ontology_with_microservice_class
    return SchemaNeighborhoodTraversal(ontology_repo=repo)


def _deltas_response(deltas: list[dict]) -> str:
    return json.dumps(deltas)


# ---------------------------------------------------------------------------- #
# Registration                                                                 #
# ---------------------------------------------------------------------------- #


class TestConnectionRefinementRegistration:
    def test_orchestrator_registered_with_implementation_registry(self):
        impl_registry = PipelineImplementationRegistry()
        register_schema_node_connection_refinement(impl_registry, None)
        impl_class = impl_registry.get(PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT, "default")
        assert impl_class is ConnectionRefinementOrchestrator

    def test_default_configuration_registered(self):
        config_registry = PipelineConfigurationRegistry()
        register_schema_node_connection_refinement(None, config_registry)
        config = config_registry.get_latest(
            PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT,
            "default",
            "connection-refinement-default",
        )
        assert config is not None
        assert "model" in config.config


# ---------------------------------------------------------------------------- #
# Execution                                                                    #
# ---------------------------------------------------------------------------- #


class TestConnectionRefinementExecution:
    def test_missing_scope_id_raises_pipeline_input_error(self, traversal):
        orchestrator = ConnectionRefinementOrchestrator(
            llm_provider=FakeLLMProvider(response_content="[]"),
            traversal=traversal,
        )
        state = ConnectionRefinementState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT,
            input_data={"scope_id": "", "current_connections": []},
        )
        with pytest.raises(PipelineInputError, match="scope_id"):
            asyncio.run(orchestrator.execute(state))

    def test_missing_scope_raises_pipeline_input_error(self, traversal):
        """Verify missing scope raises PipelineInputError.

        Not PipelineExecutionError.
        """
        orchestrator = ConnectionRefinementOrchestrator(
            llm_provider=FakeLLMProvider(response_content="[]"),
            traversal=traversal,
        )
        state = ConnectionRefinementState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT,
            input_data={
                "scope_id": str(uuid4()),  # Use a UUID that doesn't exist
                "current_connections": [],
            },
        )
        with pytest.raises(PipelineInputError, match="Scope with id"):
            asyncio.run(orchestrator.execute(state))

    def test_refinement_against_canon_microservices_class_emits_deltas(
        self, traversal, ontology_with_microservice_class
    ):
        _, ms_cls = ontology_with_microservice_class
        canon_deltas = [
            {
                "operation": "add",
                "subject": "Microservices Architecture",
                "predicate": "communicates_via",
                "object": "API Gateway",
                "rationale": "Extraction usage cites HTTP API Gateway pattern.",
                "sources_cited": ["extraction_usages"],
                "confidence": 0.9,
            },
            {
                "operation": "add",
                "subject": "Microservices Architecture",
                "predicate": "satisfies_principle",
                "object": "Independent Deployability",
                "rationale": "Core principle in Fowler microservices article.",
                "sources_cited": ["groundings"],
                "confidence": 0.88,
            },
        ]
        orchestrator = ConnectionRefinementOrchestrator(
            llm_provider=FakeLLMProvider(response_content=_deltas_response(canon_deltas)),
            traversal=traversal,
        )
        state = ConnectionRefinementState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT,
            input_data={
                "scope_id": ms_cls.id,
                "current_connections": [],
                "groundings": [{"label": "Microservice"}],
                "extraction_usages": [
                    {"extracted_text": "Microservices communicate via API Gateway"}
                ],
            },
        )
        result_state = asyncio.run(orchestrator.execute(state))

        assert result_state.current_status == PipelineRunStatus.COMPLETED
        deltas = (result_state.result or {}).get("deltas", [])
        assert len(deltas) == 2
        for delta in deltas:
            assert set(delta.keys()) >= {
                "operation",
                "subject",
                "predicate",
                "object",
                "rationale",
                "sources_cited",
                "confidence",
            }
            assert delta["operation"] in ("add", "remove", "modify")
            assert 0.0 <= delta["confidence"] <= 1.0
        assert result_state.result.get("total_deltas") == 2
        assert result_state.result.get("scope_label") == "Microservices Architecture"

    def test_deltas_capped_at_five(self, traversal, ontology_with_microservice_class):
        """The orchestrator limits output to 5 deltas regardless of LLM output."""
        _, ms_cls = ontology_with_microservice_class
        too_many = [
            {
                "operation": "add",
                "subject": "Microservices Architecture",
                "predicate": f"relates_to_{i}",
                "object": f"Concept_{i}",
                "rationale": "test",
                "sources_cited": ["test"],
                "confidence": 0.7,
            }
            for i in range(12)
        ]
        orchestrator = ConnectionRefinementOrchestrator(
            llm_provider=FakeLLMProvider(response_content=_deltas_response(too_many)),
            traversal=traversal,
        )
        state = ConnectionRefinementState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT,
            input_data={"scope_id": ms_cls.id, "current_connections": []},
        )
        result_state = asyncio.run(orchestrator.execute(state))
        deltas = (result_state.result or {}).get("deltas", [])
        assert len(deltas) <= 5

    def test_wrapped_deltas_object_is_also_parsed(
        self, traversal, ontology_with_microservice_class
    ):
        """The orchestrator accepts both bare arrays and `{"deltas": [...]}` wrapping."""
        _, ms_cls = ontology_with_microservice_class
        wrapped = {
            "deltas": [
                {
                    "operation": "add",
                    "subject": "Microservices Architecture",
                    "predicate": "composed_of",
                    "object": "Microservice",
                    "rationale": "Definitional containment relationship.",
                    "sources_cited": ["parent_class"],
                    "confidence": 0.95,
                }
            ]
        }
        orchestrator = ConnectionRefinementOrchestrator(
            llm_provider=FakeLLMProvider(response_content=json.dumps(wrapped)),
            traversal=traversal,
        )
        state = ConnectionRefinementState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_CONNECTION_REFINEMENT,
            input_data={"scope_id": ms_cls.id, "current_connections": []},
        )
        result_state = asyncio.run(orchestrator.execute(state))
        assert result_state.current_status == PipelineRunStatus.COMPLETED
        assert len((result_state.result or {}).get("deltas", [])) == 1


class TestConnectionRefinementViaHarness:
    """Harness-based integration tests using shared fixture infrastructure."""

    @pytest.mark.asyncio
    async def test_harness_loads_and_runs_basic_connection_refinement(self):
        """Harness successfully loads fixture and runs connection refinement orchestrator."""
        from domain.pipelines.schema_node_connection_refinement.orchestrator import (
            ConnectionRefinementOrchestrator,
        )

        llm_response = (
            '{"relationships": '
            '[{"subject": "Microservice", '
            '"predicate": "depends_on", '
            '"object": "Database"}]}'
        )
        llm_provider = FakeLLMProvider(response_content=llm_response)
        orchestrator = ConnectionRefinementOrchestrator(llm_provider=llm_provider, traversal=None)

        actual, expected = await run_pipeline_against_fixture(
            orchestrator,
            "schema_node_connection_refinement",
            "basic",
        )

        # Verify outputs were loaded and execution succeeded
        assert actual is not None
        assert expected is not None
        assert actual["status"] == "completed"
        assert "result" in actual
