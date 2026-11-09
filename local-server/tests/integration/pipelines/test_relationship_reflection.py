"""
Integration tests for the schema relationship reflection pipeline (#1410), run
through the background executor on real SQLite with the pinned DR spec (0.8.4)
imported: the run asks every relationship type in scope its sorting questions
(a scripted decision model, no network), records progress, cost and latency,
and links the one change proposal it makes; the DR relationship identity of a
proposed rename is completed so the operation applies.
"""

import json
import re
import shutil
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import sessionmaker

from adapters.events.in_process import InProcessEventPublisher
from adapters.interchange.dr_relationships import (
    DR_TAXONOMY_IDENTIFIER,
    DrRelationshipRules,
    dr_relationship_id,
)
from adapters.persistence.sqlite.batch_repo import BatchRepository
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.connection import create_local_db_engine
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.pipeline_run_repo import PipelineRepository
from adapters.persistence.sqlite.proposal_repo import SQLiteChangeProposalRepository
from adapters.pipelines.run_executor import BackgroundRunExecutor
from domain.decision.value_objects import ChoiceAnswer
from domain.ontology.services import OntologyService
from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from domain.pipelines.schema_relationship_reflection import (
    register_schema_relationship_reflection,
)
from domain.versioning.proposal_service import ProposalService
from domain.versioning.proposals import OperationStatus, OperationType, ProposalSource
from domain.versioning.revert_service import RevertService
from scripts.dr_ontology_loader import import_dr_ontology
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_llm_provider import FakeLLMProvider
from tests.integration.pipelines._harness.dr_spec import pinned_dr_spec_dir
from tests.utils.change_recording import wire_change_recorder

RENAMED = "api.operation.delivers.api.response"
KEPT = "api.operation.aggregates.api.parameter"
_TRIPLE = re.compile(r"The catalog says '(\S+) (\S+) (\S+)'")


class RenamingModel:
    """
    Keeps every relationship type except `rename` (a 'source predicate target'
    string), whose best predicate is the first other forward predicate offered.
    """

    name = "scripted"
    is_configured = True

    def __init__(self, rename):
        self.rename = rename
        self.calls = 0

    def decide(self, state, questions):
        self.calls += 1
        source, predicate, target = _TRIPLE.search(questions["source_for"].instructions).groups()
        current = {"source_for": source, "target_for": target, "predicate_for": predicate}
        if f"{source} {predicate} {target}" == self.rename:
            current["predicate_for"] = next(
                o
                for o in questions["predicate_for"].criteria
                if o not in (predicate, "none") and not o.startswith("reverse:")
            )
        out = {}
        for name, question in questions.items():
            options = list(question.options())
            choice = current[name]
            out[name] = ChoiceAnswer(
                choice=choice,
                probabilities={o: 0.9 if o == choice else 0.1 / len(options) for o in options},
                model=self.name,
                latency_ms=25.0,
                cost_usd=0.0001,
            )
        return out

    async def decide_async(self, state, questions):
        return self.decide(state, questions)


class Models:
    def __init__(self, model):
        self.model = model

    def get(self, name=None):
        return self.model

    def describe(self):
        return []


def spec_with_catalog(spec):
    """The pinned spec with its predicate catalog as dist/base.json (as test_dr_reflection_plan)."""
    shutil.copytree(pinned_dr_spec_dir(), spec)
    catalog = json.loads((spec / "schemas" / "base" / "predicates.json").read_text())
    (spec / "dist" / "base.json").write_text(
        json.dumps({"specVersion": "0.8.4", "predicates": catalog["predicates"]})
    )
    return spec


@pytest.fixture(scope="module")
def spec_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "spec.db"
        engine = create_local_db_engine(f"sqlite:///{path}")
        Base.metadata.create_all(engine)
        repo = SQLiteOntologyRepository(session_factory=sessionmaker(bind=engine))
        service = OntologyService(repo, FakeEmbeddingService(), InProcessEventPublisher())
        import_dr_ontology(service, repo, spec_with_catalog(Path(tmpdir) / "spec"))
        engine.dispose()
        yield path


@pytest.fixture()
def world(spec_db, tmp_path):
    db = tmp_path / "local.db"
    db.write_bytes(spec_db.read_bytes())
    engine = create_local_db_engine(f"sqlite:///{db}")
    session_factory = sessionmaker(bind=engine)
    repo = SQLiteOntologyRepository(session_factory=session_factory)
    change_repo = SQLiteChangeRepository(session_factory=session_factory)
    publisher = InProcessEventPublisher()
    wire_change_recorder(publisher, change_repo)
    ontology = OntologyService(repo, FakeEmbeddingService(), publisher)
    proposals = ProposalService(
        SQLiteChangeProposalRepository(session_factory),
        ontology,
        repo,
        RevertService(change_repo=change_repo, ontology_repo=repo),
        apply_rules=[DrRelationshipRules(repo)],
    )
    yield SimpleNamespace(
        session_factory=session_factory, repo=repo, proposals=proposals, engine=engine
    )
    engine.dispose()


def by_dr_id(repo):
    return {
        dr_relationship_id(p.external_references): p
        for p in repo.list_property_definitions(limit=None)
        if dr_relationship_id(p.external_references)
    }


def make_executor(world, model):
    implementations = PipelineImplementationRegistry()
    configurations = PipelineConfigurationRegistry()
    register_schema_relationship_reflection(implementations, configurations)
    return BackgroundRunExecutor(
        runs=PipelineRepository(world.session_factory),
        batches=BatchRepository(world.session_factory),
        implementations=implementations,
        configurations=configurations,
        llm_provider=FakeLLMProvider(),
        app_state=SimpleNamespace(
            ontology_repo=world.repo,
            decision_models=Models(model),
            proposal_service=world.proposals,
        ),
        poll_seconds=0.05,
    )


def wait_for_end(runs, run_id, timeout=60.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = runs.get(run_id)
        if run.status not in (PipelineRunStatus.PENDING, PipelineRunStatus.RUNNING):
            return run
        time.sleep(0.05)
    raise AssertionError("run did not finish")


def test_background_run_proposes_a_dr_rename_that_applies(world):
    props = by_dr_id(world.repo)
    renamed, kept = props[RENAMED], props[KEPT]
    taxonomy = world.repo.get_by_identifier(DR_TAXONOMY_IDENTIFIER)
    # The import marks the DR taxonomy mirrored, which refuses reflection runs;
    # this test is about the pipeline itself, so it lifts the flag.
    taxonomy.mirrored = False
    world.repo.save_taxonomy(taxonomy)
    model = RenamingModel(rename="api_operation delivers api_response")
    executor = make_executor(world, model)
    run = executor.submit(
        PipelineType.SCHEMA_RELATIONSHIP_REFLECTION,
        "default",
        "default",
        {"taxonomy_id": taxonomy.id, "scope": [renamed.id, kept.id]},
    )
    executor.start()
    try:
        done = wait_for_end(PipelineRepository(world.session_factory), run.id)
    finally:
        executor.stop()

    assert done.status == PipelineRunStatus.COMPLETED, done.failure_reason
    assert (done.items_done, done.items_total) == (2, 2)
    assert done.llm_metadata["decision_model"] == "scripted"
    assert done.llm_metadata["requests"] == 2
    assert done.llm_metadata["cost_usd"] == pytest.approx(0.0006)
    assert done.llm_metadata["latency_ms_total"] == pytest.approx(50.0)
    assert done.output_summary["outcomes"] == {"reproduced": 1, "no_better": 0, "alternative": 1}
    assert done.proposal_id == done.output_summary["proposal_id"]

    proposal = world.proposals.get(done.proposal_id)
    assert proposal.source is ProposalSource.PIPELINE
    assert proposal.taxonomy_id == taxonomy.id
    (op,) = proposal.operations
    assert op.op is OperationType.UPDATE and op.target_id == renamed.id
    new_predicate = op.fields["canonical_predicate"]
    new_id = f"api.operation.{new_predicate}.api.response"
    # The DR identity of the new triple is completed, so the DR rules let it apply
    assert dr_relationship_id(op.fields["external_references"]) == new_id
    assert op.fields["identifier"] != renamed.identifier

    applied = world.proposals.apply(proposal.id, [op.id])
    assert applied.operations[0].status is OperationStatus.APPLIED, applied.operations[0].reason
    after = world.repo.get_property_definition(renamed.id)
    assert after.canonical_predicate == new_predicate
    assert dr_relationship_id(after.external_references) == new_id
