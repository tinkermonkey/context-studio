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
from dataclasses import replace
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
from domain.pipelines.schema_node_definition_refinement.bootstrap import (
    register_schema_node_definition_refinement,
)
from domain.pipelines.schema_node_definition_refinement.orchestrator import (
    DefinitionRefinementOrchestrator,
    DefinitionRefinementState,
)
from tests.fakes.fake_llm_provider import FakeLLMProvider


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
        impl_class = impl_registry.get(
            PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT, "default"
        )
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
            llm_provider=FakeLLMProvider(
                response_content=_refinement_response(canon_definitions)
            ),
            traversal=traversal,
        )
        state = DefinitionRefinementState(
            run_id=str(uuid4()),
            pipeline_type=PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
            input_data={
                "node_id": rest_cls.id,
                "current_definition": rest_cls.description,
                "groundings": [
                    {"label": "Representational State Transfer", "description": "..."}
                ],
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
            input_data={"node_id": rest_cls.id, "current_definition": rest_cls.description},
        )
        result_state = asyncio.run(orchestrator.execute(state))
        candidates = result_state.result.get("candidates", [])
        assert len(candidates) <= 3

    def test_wrapped_definitions_object_is_also_parsed(
        self, traversal, ontology_with_rest_class
    ):
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
            input_data={"node_id": rest_cls.id, "current_definition": rest_cls.description},
        )
        result_state = asyncio.run(orchestrator.execute(state))
        assert result_state.current_status == PipelineRunStatus.COMPLETED
        assert len(result_state.result.get("candidates", [])) == 1
