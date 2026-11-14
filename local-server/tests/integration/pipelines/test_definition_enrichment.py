"""
Integration test for definition enrichment (#1517): a background run of the
definition refinement pipeline's scoped mode over real SQLite, through the
orchestrator factory, proposes each class's operational definition, and the
proposal applies.
"""

import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.batch_repo import BatchRepository
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.connection import create_local_db_engine, create_session_factory
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.pipeline_run_repo import PipelineRepository
from adapters.persistence.sqlite.proposal_repo import SQLiteChangeProposalRepository
from adapters.pipelines.run_executor import BackgroundRunExecutor
from domain.ontology.services import OntologyService
from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.pipelines.ports import LLMResponse
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from domain.pipelines.schema_node_definition_refinement import (
    register_schema_node_definition_refinement,
)
from domain.versioning.proposal_service import ProposalService
from domain.versioning.proposals import OperationStatus
from domain.versioning.revert_service import RevertService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.utils.change_recording import wire_change_recorder

ANSWER = {
    "definition": "A room where food is prepared.",
    "distinguish_from": [{"type": "house_den", "when": "people relax there"}],
    "standard_reference": None,
    "evidence_signals": ["a stove", "a sink", "a fridge"],
    "notes": "",
    "confidence": 0.7,
}


class OneAnswerLLM:
    async def complete_async(self, system_prompt, user_prompt, model, **kwargs):
        return LLMResponse(json.dumps(ANSWER), 10, 5, 1.0, "stop", model)


@pytest.fixture()
def world(tmp_path: Path):
    engine = create_local_db_engine(f"sqlite:///{tmp_path / 'local.db'}")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    repo = SQLiteOntologyRepository(session_factory)
    change_repo = SQLiteChangeRepository(session_factory)
    publisher = InProcessEventPublisher()
    wire_change_recorder(publisher, change_repo)
    ontology = OntologyService(repo, FakeEmbeddingService(), publisher)
    proposals = ProposalService(
        SQLiteChangeProposalRepository(session_factory),
        ontology,
        repo,
        RevertService(change_repo=change_repo, ontology_repo=repo),
    )
    taxonomy = ontology.create_taxonomy(title="House", identifier="house")
    rooms = ontology.create_scheme(taxonomy.id, "Rooms", identifier="rooms")
    kitchen = ontology.create_class(rooms.id, "Kitchen", identifier="house_kitchen")
    den = ontology.create_class(rooms.id, "Den", identifier="house_den")
    yield SimpleNamespace(
        session_factory=session_factory,
        repo=repo,
        proposals=proposals,
        taxonomy=taxonomy,
        kitchen=kitchen,
        den=den,
    )
    engine.dispose()


def wait_for_end(runs, run_id, timeout=30.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = runs.get(run_id)
        if run.status not in (PipelineRunStatus.PENDING, PipelineRunStatus.RUNNING):
            return run
        time.sleep(0.05)
    raise AssertionError("run did not finish")


def test_a_background_enrichment_run_proposes_definitions_that_apply(world):
    implementations = PipelineImplementationRegistry()
    configurations = PipelineConfigurationRegistry()
    register_schema_node_definition_refinement(implementations, configurations)
    executor = BackgroundRunExecutor(
        runs=PipelineRepository(world.session_factory),
        batches=BatchRepository(world.session_factory),
        implementations=implementations,
        configurations=configurations,
        llm_provider=OneAnswerLLM(),
        app_state=SimpleNamespace(ontology_repo=world.repo, proposal_service=world.proposals),
        poll_seconds=0.05,
    )
    run = executor.submit(
        PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT,
        None,
        None,
        {"taxonomy_id": world.taxonomy.id, "scope": ["house_kitchen"]},
    )
    executor.start()
    try:
        done = wait_for_end(PipelineRepository(world.session_factory), run.id)
    finally:
        executor.stop()

    assert done.status == PipelineRunStatus.COMPLETED, done.failure_reason
    assert done.proposal_id == done.output_summary["proposal_id"]
    proposal = world.proposals.get(done.proposal_id)
    applied = world.proposals.apply(proposal.id, [o.id for o in proposal.operations])
    assert [o.status for o in applied.operations] == [OperationStatus.APPLIED]
    kitchen = world.repo.get_class(world.kitchen.id)
    assert kitchen.description == "A room where food is prepared."
    assert kitchen.distinguish_from == [{"class_id": world.den.id, "when": "people relax there"}]
    assert kitchen.evidence_signals == ["a stove", "a sink", "a fridge"]
