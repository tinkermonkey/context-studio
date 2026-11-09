"""
Integration tests for the schema_node_definition_refinement pipeline.

The pipeline reads a class node from the ontology repo, traverses its
neighborhood (parent, siblings, children, properties), asks an LLM to generate
up to 3 candidate refined definitions, and returns them on state.result.

Focused tests:
  - Bootstrap registration produces orchestrator + config
  - execute() against a canon class yields candidates with the expected schema
  - Missing node_id raises PipelineInputError
  - Confidence values are clamped to [0, 1]
  - Candidates are capped at 3 even if the LLM returns more
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
from domain.ontology.entities import Class, ConceptScheme, PropertyDefinition, Taxonomy
from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.pipelines.exceptions import PipelineInputError
from domain.pipelines.refinement.neighborhood import SchemaNeighborhoodTraversal
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from domain.pipelines.schema_node_definition_refinement.bootstrap import (
    register_schema_node_definition_refinement,
)
from domain.pipelines.schema_node_definition_refinement.orchestrator import (
    DefinitionRefinementOrchestrator,
    DefinitionRefinementState,
)
from tests.fakes.fake_llm_provider import FakeLLMProvider
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
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
def ontology_with_rest_class(session_factory):
    """Repo seeded with a canon REST class that has an intentionally thin description."""
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
    rest_cls = Class(
        id=str(uuid4()),
        identifier="rest",
        concept_scheme_id=scheme.id,
        taxonomy_id=tax.id,
        title="REST",
        description="A web style.",  # intentionally thin — to be refined
    )
    repo.save_class(rest_cls)
    return repo, rest_cls


@pytest.fixture
def traversal(ontology_with_rest_class):
    repo, _ = ontology_with_rest_class
    return SchemaNeighborhoodTraversal(ontology_repo=repo)


def _refinement_response(definitions: list[dict]) -> str:
    """Build a JSON array string the orchestrator's parser will accept."""
    return json.dumps(definitions)


# ---------------------------------------------------------------------------- #
# Registration                                                                 #
# ---------------------------------------------------------------------------- #


class TestDefinitionRefinementRegistration:
    def test_orchestrator_registered_with_implementation_registry(self):
        impl_registry = PipelineImplementationRegistry()
        register_schema_node_definition_refinement(impl_registry, None)
        impl_class = impl_registry.get(PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT, "default")
        assert impl_class is DefinitionRefinementOrchestrator

    def test_default_configuration_registered(self):
        config_registry = PipelineConfigurationRegistry()
        register_schema_node_definition_refinement(None, config_registry)
        config = config_registry.get_latest(
            PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            "default",
            "definition-refinement-default",
        )
        assert config is not None
        assert "model" in config.config


# ---------------------------------------------------------------------------- #
# Execution                                                                    #
# ---------------------------------------------------------------------------- #


class TestDefinitionRefinementExecution:
    def test_missing_node_id_raises_pipeline_input_error(self, traversal):
        orchestrator = DefinitionRefinementOrchestrator(
            llm_provider=FakeLLMProvider(response_content="[]"),
            traversal=traversal,
        )
        state = DefinitionRefinementState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            input_data={"node_id": "", "current_definition": "anything"},
        )
        with pytest.raises(PipelineInputError, match="node_id"):
            asyncio.run(orchestrator.execute(state))

    def test_missing_node_raises_pipeline_input_error(self, traversal):
        """Test that missing node raises PipelineInputError, not PipelineExecutionError."""
        orchestrator = DefinitionRefinementOrchestrator(
            llm_provider=FakeLLMProvider(response_content="[]"),
            traversal=traversal,
        )
        state = DefinitionRefinementState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            input_data={
                "node_id": str(uuid4()),  # Use a UUID that doesn't exist
                "current_definition": "anything",
            },
        )
        with pytest.raises(PipelineInputError, match="No class or property definition"):
            asyncio.run(orchestrator.execute(state))

    def test_refinement_against_canon_rest_class_emits_candidates(
        self, traversal, ontology_with_rest_class
    ):
        _, rest_cls = ontology_with_rest_class
        canon_definitions = [
            {
                "definition": (
                    "An architectural style for distributed hypermedia systems "
                    "derived from six constraints (client-server, stateless, "
                    "cacheable, uniform interface, layered system, code-on-demand)."
                ),
                "rationale": "Aligned with the Fielding dissertation phrasing.",
                "sources_used": ["parent_class", "groundings"],
                "confidence": 0.92,
            },
            {
                "definition": (
                    "A network-based architectural style emphasising uniform "
                    "interfaces between resources identified by URIs."
                ),
                "rationale": "Captures the hypermedia / resource framing.",
                "sources_used": ["groundings"],
                "confidence": 0.85,
            },
        ]
        orchestrator = DefinitionRefinementOrchestrator(
            llm_provider=FakeLLMProvider(response_content=_refinement_response(canon_definitions)),
            traversal=traversal,
        )
        state = DefinitionRefinementState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            input_data={
                "node_id": rest_cls.id,
                "current_definition": rest_cls.description,
                "groundings": [{"label": "Representational State Transfer", "description": "..."}],
                "extraction_usages": [],
            },
        )
        result_state = asyncio.run(orchestrator.execute(state))

        assert result_state.current_status == PipelineRunStatus.COMPLETED
        assert result_state.result is not None
        candidates = result_state.result.get("candidates", [])
        assert len(candidates) == 2
        for cand in candidates:
            assert set(cand.keys()) >= {
                "definition",
                "rationale",
                "sources_used",
                "confidence",
            }
            assert cand["definition"]
            assert 0.0 <= cand["confidence"] <= 1.0
        assert result_state.result.get("total_candidates") == 2
        assert result_state.result.get("node_label") == "REST"

    def test_candidates_capped_at_three(self, traversal, ontology_with_rest_class):
        """The orchestrator limits output to 3 candidates regardless of LLM output."""
        _, rest_cls = ontology_with_rest_class
        too_many = [
            {
                "definition": f"Definition variant {i}",
                "rationale": "test",
                "sources_used": ["test"],
                "confidence": 0.8,
            }
            for i in range(7)
        ]
        orchestrator = DefinitionRefinementOrchestrator(
            llm_provider=FakeLLMProvider(response_content=_refinement_response(too_many)),
            traversal=traversal,
        )
        state = DefinitionRefinementState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            input_data={
                "node_id": rest_cls.id,
                "current_definition": rest_cls.description,
            },
        )
        result_state = asyncio.run(orchestrator.execute(state))
        candidates = result_state.result.get("candidates", [])
        assert len(candidates) <= 3

    def test_wrapped_definitions_object_is_also_parsed(self, traversal, ontology_with_rest_class):
        """The orchestrator accepts both bare arrays and `{"definitions": [...]}` wrapping."""
        _, rest_cls = ontology_with_rest_class
        wrapped = {
            "definitions": [
                {
                    "definition": "REST as resource-oriented architecture.",
                    "rationale": "Captures the resource abstraction.",
                    "sources_used": ["parent_class"],
                    "confidence": 0.9,
                }
            ]
        }
        orchestrator = DefinitionRefinementOrchestrator(
            llm_provider=FakeLLMProvider(response_content=json.dumps(wrapped)),
            traversal=traversal,
        )
        state = DefinitionRefinementState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            input_data={
                "node_id": rest_cls.id,
                "current_definition": rest_cls.description,
            },
        )
        result_state = asyncio.run(orchestrator.execute(state))
        assert result_state.current_status == PipelineRunStatus.COMPLETED
        assert len(result_state.result.get("candidates", [])) == 1


class TestDefinitionRefinementViaHarness:
    """Harness-based integration tests using shared fixture infrastructure."""

    @pytest.mark.asyncio
    async def test_harness_loads_and_runs_basic_refinement(self):
        """Harness successfully loads fixture and runs definition refinement orchestrator."""
        from domain.pipelines.schema_node_definition_refinement.orchestrator import (
            DefinitionRefinementOrchestrator,
        )

        llm_response = (
            '{"definitions": ' '[{"label": "Microservice", ' '"definition": "A small service"}]}'
        )
        llm_provider = FakeLLMProvider(response_content=llm_response)
        orchestrator = DefinitionRefinementOrchestrator(llm_provider=llm_provider, traversal=None)

        actual, expected = await run_pipeline_against_fixture(
            orchestrator,
            "schema_node_definition_refinement",
            "basic",
        )

        # Verify outputs were loaded and execution succeeded
        assert actual is not None
        assert expected is not None
        assert actual["status"] == "completed"
        assert "result" in actual


# ---------------------------------------------------------------------------- #
# Property definitions                                                         #
# ---------------------------------------------------------------------------- #


@pytest.fixture
def exposes_property(ontology_with_rest_class):
    """A property declared from REST (domain) to HTTP API (range), with no relationships."""
    repo, rest_cls = ontology_with_rest_class
    api_cls = Class(
        id=str(uuid4()),
        identifier="http_api",
        concept_scheme_id=rest_cls.concept_scheme_id,
        taxonomy_id=rest_cls.taxonomy_id,
        title="HTTP API",
        description="An interface reached over HTTP.",
    )
    repo.save_class(api_cls)
    prop = PropertyDefinition(
        id=str(uuid4()),
        identifier="exposes",
        title="exposes",
        description="Links things.",
        domain_class_id=rest_cls.id,
        range_class_id=api_cls.id,
    )
    repo.save_property_definition(prop)
    return prop


def _run_refinement(traversal, node_id: str) -> tuple[DefinitionRefinementState, FakeLLMProvider]:
    llm = FakeLLMProvider(
        response_content=_refinement_response(
            [{"definition": "Refined.", "rationale": "r", "sources_used": [], "confidence": 0.8}]
        )
    )
    orchestrator = DefinitionRefinementOrchestrator(llm_provider=llm, traversal=traversal)
    state = DefinitionRefinementState(
        run_id=str(uuid4()),
        pipeline_type=PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
        input_data={"node_id": node_id, "current_definition": "Links things."},
    )
    return asyncio.run(orchestrator.execute(state)), llm


class TestPropertyDefinitionRefinement:
    def test_property_is_refined_with_its_domain_and_range(self, traversal, exposes_property):
        state, llm = _run_refinement(traversal, exposes_property.id)

        assert state.result["node_type"] == "PropertyDefinition"
        assert state.result["node_label"] == "exposes"
        assert state.result["total_candidates"] == 1
        prompt = llm.last_call_args["user_prompt"]
        assert prompt.startswith("Refine this property definition:")
        assert "Property label: exposes" in prompt
        assert "Domain class (subject): REST (definition: A web style.)" in prompt
        assert (
            "Range class (object): HTTP API (definition: An interface reached over HTTP.)"
            in prompt
        )
        system_prompt = llm.last_call_args["system_prompt"]
        assert "property (a relationship type between classes)" in system_prompt

    def test_class_prompt_is_unchanged(self, traversal, ontology_with_rest_class):
        _, rest_cls = ontology_with_rest_class

        state, llm = _run_refinement(traversal, rest_cls.id)

        assert state.result["node_type"] == "Class"
        prompt = llm.last_call_args["user_prompt"]
        assert prompt.startswith("Refine this class definition:")
        assert "Class label: REST" in prompt
        assert "definitions for a schema class." in llm.last_call_args["system_prompt"]

    def test_declared_domain_that_cannot_be_found_is_left_out(self):
        # SQLite's foreign keys prevent a dangling domain, so this uses the fake repository.
        repo = FakeOntologyRepository()
        api_cls = Class(
            id=str(uuid4()),
            identifier="http_api",
            concept_scheme_id=str(uuid4()),
            taxonomy_id=str(uuid4()),
            title="HTTP API",
        )
        repo.save_class(api_cls)
        prop = PropertyDefinition(
            id=str(uuid4()),
            identifier="hosts",
            title="hosts",
            domain_class_id=str(uuid4()),
            range_class_id=api_cls.id,
        )
        repo.save_property_definition(prop)

        neighborhood = SchemaNeighborhoodTraversal(ontology_repo=repo).get_property_neighborhood(
            prop.id
        )

        assert neighborhood.domain_neighborhood is None
        assert neighborhood.range_neighborhood.class_label == "HTTP API"
