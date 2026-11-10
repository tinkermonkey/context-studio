"""
Integration test for the claim triage pipeline (#1520): a background run over
real SQLite, through the orchestrator factory, saves each claim's triage.
"""

import time
from types import SimpleNamespace

import pytest

from adapters.persistence.sqlite.batch_repo import BatchRepository
from adapters.persistence.sqlite.claim_repo import SQLiteClaimRepository
from adapters.persistence.sqlite.connection import create_local_db_engine, create_session_factory
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.pipeline_run_repo import PipelineRepository
from adapters.pipelines.run_executor import BackgroundRunExecutor
from domain.ontology.entities import Class, ConceptScheme, Taxonomy
from domain.pipelines.claim_triage import register_claim_triage
from domain.pipelines.entities import ClaimTriageRun, PipelineRunStatus, PipelineType
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from domain.versioning.claims import Claim, ClaimFilter, ClaimService, NoteSource, Validity
from tests.fakes.fake_decision_model import FakeDecisionModel
from tests.fakes.fake_llm_provider import FakeLLMProvider

T = "tax-1"


class Models:
    def __init__(self, model):
        self.model = model

    def get(self, name=None):
        return self.model


@pytest.fixture()
def world(tmp_path):
    engine = create_local_db_engine(f"sqlite:///{tmp_path / 'local.db'}")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    repo = SQLiteOntologyRepository(session_factory)
    repo.save_taxonomy(Taxonomy(id=T, identifier="house", title="House", description="A home"))
    repo.save_concept_scheme(ConceptScheme(id="s1", taxonomy_id=T, title="Rooms"))
    repo.save_class(
        Class(id="c1", taxonomy_id=T, concept_scheme_id="s1", title="Room", description="A space")
    )
    claims = ClaimService(SQLiteClaimRepository(session_factory), repo)
    claims.submit(
        T,
        [
            Claim(
                taxonomy_id=T,
                key=f"room#{n}",
                text=f"Room claim {n}",
                note_ref="room",
                note_source=NoteSource.REVIEWER,
                subject_id="c1",
                affected_ids=["c1"],
            )
            for n in (1, 2)
        ],
    )
    yield SimpleNamespace(session_factory=session_factory, repo=repo, claims=claims)
    engine.dispose()


def make_executor(world, model):
    implementations = PipelineImplementationRegistry()
    configurations = PipelineConfigurationRegistry()
    register_claim_triage(implementations, configurations)
    return BackgroundRunExecutor(
        runs=PipelineRepository(world.session_factory),
        batches=BatchRepository(world.session_factory),
        implementations=implementations,
        configurations=configurations,
        llm_provider=FakeLLMProvider(),
        app_state=SimpleNamespace(
            ontology_repo=world.repo,
            decision_models=Models(model),
            claim_service=world.claims,
        ),
        poll_seconds=0.05,
    )


def wait_for_end(runs, run_id, timeout=30.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = runs.get(run_id)
        if run.status not in (PipelineRunStatus.PENDING, PipelineRunStatus.RUNNING):
            return run
        time.sleep(0.05)
    raise AssertionError("run did not finish")


def test_a_background_triage_run_saves_each_claims_answers(world):
    model = FakeDecisionModel(
        "clef",
        choices={"validity": "works_as_designed", "category": "other"},
        scores={"severity": 1},
        cost_usd=0.0002,
    )
    executor = make_executor(world, model)
    run = executor.submit(
        PipelineType.CLAIM_TRIAGE, "default", "default", {"taxonomy_id": T, "scope": None}
    )
    executor.start()
    try:
        done = wait_for_end(PipelineRepository(world.session_factory), run.id)
    finally:
        executor.stop()

    assert isinstance(done, ClaimTriageRun)
    assert done.status == PipelineRunStatus.COMPLETED, done.failure_reason
    assert (done.items_done, done.items_total) == (2, 2)
    assert done.llm_metadata["decision_model"] == "clef"
    assert done.llm_metadata["cost_usd"] == pytest.approx(0.0016)
    assert done.output_summary["validity"] == {"works_as_designed": 2}
    assert done.proposal_id is None
    triaged = world.claims.list_claims(ClaimFilter(taxonomy_id=T, triaged=True))
    assert [c.key for c in triaged] == ["room#1", "room#2"]
    assert {c.triage.validity for c in triaged} == {Validity.WORKS_AS_DESIGNED}
    assert {c.triage.run_id for c in triaged} == {run.id}
    assert "A space" in model.calls[0][0]  # the subject's definition reached the state
