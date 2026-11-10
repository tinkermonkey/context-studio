"""
Integration test for the notes-to-claims pipeline (#1519): a background run over
real SQLite, through the orchestrator factory, stores each note's claims, and a
re-run keeps the verdicts of the claims it keeps.
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
from domain.ontology.entities import AttributeDefinition, Class, ConceptScheme, Taxonomy
from domain.pipelines.entities import NotesToClaimsRun, PipelineRunStatus, PipelineType
from domain.pipelines.notes_to_claims import register_notes_to_claims
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from domain.versioning.claims import ClaimFilter, ClaimService, ClaimVerdict
from tests.fakes.fake_note_splitter import FakeNoteSplitter

T = "tax-1"
NOTE = "A room's floor area has no unit. Rooms and spaces overlap."


@pytest.fixture()
def world(tmp_path):
    engine = create_local_db_engine(f"sqlite:///{tmp_path / 'local.db'}")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    repo = SQLiteOntologyRepository(session_factory)
    repo.save_taxonomy(Taxonomy(id=T, identifier="house", title="House", description="A home"))
    repo.save_concept_scheme(
        ConceptScheme(id="s1", taxonomy_id=T, title="Rooms", identifier="rooms")
    )
    for class_id, identifier in (("c1", "room"), ("c2", "space")):
        repo.save_class(
            Class(
                id=class_id,
                taxonomy_id=T,
                concept_scheme_id="s1",
                title=identifier.title(),
                identifier=identifier,
                description=f"A {identifier}",
            )
        )
    repo.save_attribute_definition(
        AttributeDefinition(
            id="a1", class_id="c1", identifier="floor_area", title="Floor area", datatype="number"
        )
    )
    claims = ClaimService(SQLiteClaimRepository(session_factory), repo)
    yield SimpleNamespace(session_factory=session_factory, repo=repo, claims=claims)
    engine.dispose()


def make_executor(world, llm):
    implementations = PipelineImplementationRegistry()
    configurations = PipelineConfigurationRegistry()
    register_notes_to_claims(implementations, configurations)
    return BackgroundRunExecutor(
        runs=PipelineRepository(world.session_factory),
        batches=BatchRepository(world.session_factory),
        implementations=implementations,
        configurations=configurations,
        llm_provider=llm,
        app_state=SimpleNamespace(ontology_repo=world.repo, claim_service=world.claims),
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


def split_in_background(world, llm, **scope):
    executor = make_executor(world, llm)
    notes = [{"ref": "n1", "subject": "room", "text": NOTE}]
    run = executor.submit(
        PipelineType.NOTES_TO_CLAIMS,
        "default",
        "default",
        {"taxonomy_id": T, "scope": {"notes": notes, **scope}},
    )
    executor.start()
    try:
        return wait_for_end(PipelineRepository(world.session_factory), run.id)
    finally:
        executor.stop()


def claim_split(text, *affected):
    return {
        "text": text,
        "category": "missing_attribute",
        "affected_ids": list(affected),
        "proposed_change": "none stated",
    }


def test_a_background_run_stores_each_notes_claims_and_a_rerun_keeps_verdicts(world):
    first = FakeNoteSplitter(
        {
            "floor area": [
                claim_split("room.floor_area has no unit.", "room.floor_area"),
                claim_split("room and space overlap.", "room", "space", "hall"),
            ]
        }
    )
    done = split_in_background(world, first)

    assert isinstance(done, NotesToClaimsRun)
    assert done.status == PipelineRunStatus.COMPLETED, done.failure_reason
    assert (done.items_done, done.items_total) == (1, 1)
    assert done.llm_metadata["tokens_in"] == 100
    assert done.output_summary["claims"] == 2
    assert done.proposal_id is None
    stored = world.claims.list_claims(ClaimFilter(taxonomy_id=T))
    assert [c.key for c in stored] == ["n1#1", "n1#2"]
    assert stored[0].affected_ids == ["a1"]
    assert (stored[1].affected_ids, stored[1].unresolved_refs) == (["c1", "c2"], ["hall"])
    assert {c.subject_id for c in stored} == {"c1"}
    assert {c.source_run_id for c in stored} == {done.id}
    assert "floor_area: number" in first.calls[0]["user"]
    world.claims.set_verdict(
        stored[0].id, ClaimVerdict(validity="real_defect", adjudicated_by="user")
    )

    resplit = FakeNoteSplitter(
        {"floor area": [claim_split("room.floor_area has no unit.", "room.floor_area")]}
    )
    skipped = split_in_background(world, resplit)

    # Split already: left as it is
    assert skipped.status == PipelineRunStatus.COMPLETED, skipped.failure_reason
    assert (skipped.output_summary["skipped"], resplit.calls) == (1, [])
    assert len(world.claims.list_claims(ClaimFilter(taxonomy_id=T))) == 2

    again = split_in_background(world, resplit, force=True)

    assert again.status == PipelineRunStatus.COMPLETED, again.failure_reason
    assert again.output_summary["claims_removed"] == 1
    kept = world.claims.list_claims(ClaimFilter(taxonomy_id=T))
    assert [c.key for c in kept] == ["n1#1"]
    assert kept[0].id == stored[0].id and kept[0].verdict is not None
