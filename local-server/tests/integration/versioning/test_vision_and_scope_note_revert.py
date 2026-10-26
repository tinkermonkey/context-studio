"""
Integration tests (#1334): taxonomy vision, scheme scope-note edits and scheme moves
are stored, recorded as change events with old and new values, and restored by a revert.

Real SQLite with the ChangeEventRecorder wired to an in-process publisher and the
RevertService wired as in app.py.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.events.change_recorder import ChangeEventRecorder
from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.pipeline_run_repo import PipelineRepository
from domain.interchange.services import set_batch_run_context
from domain.ontology.events import SchemeUpdated, TaxonomyUpdated
from domain.ontology.services import OntologyService
from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.versioning.revert_service import RevertService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.utils.parent_rows import create_batch_row

VISION = "# House\n\nThe graph is memory and vocabulary; Claude does the reasoning."


@pytest.fixture()
def session_factory():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_engine(f"sqlite:///{Path(tmpdir) / 'local.db'}")
        Base.metadata.create_all(engine)
        yield sessionmaker(bind=engine)
        engine.dispose()


@pytest.fixture()
def ontology_repo(session_factory):
    return SQLiteOntologyRepository(session_factory=session_factory)


@pytest.fixture()
def change_repo(session_factory):
    return SQLiteChangeRepository(session_factory=session_factory)


@pytest.fixture()
def pipeline_repo(session_factory):
    return PipelineRepository(session_factory=session_factory)


@pytest.fixture()
def ontology_service(ontology_repo, change_repo):
    publisher = InProcessEventPublisher()
    recorder = ChangeEventRecorder(change_repo)
    publisher.subscribe(TaxonomyUpdated, recorder.on_taxonomy_updated)
    publisher.subscribe(SchemeUpdated, recorder.on_scheme_updated)
    return OntologyService(
        repository=ontology_repo,
        embedding_service=FakeEmbeddingService(),
        event_publisher=publisher,
    )


@pytest.fixture()
def revert_service(change_repo, ontology_repo):
    return RevertService(change_repo=change_repo, ontology_repo=ontology_repo)


def _new_run(pipeline_repo):
    run = pipeline_repo.create(
        batch_run_id=create_batch_row(pipeline_repo._session_factory),
        pipeline_type=PipelineType.SCHEMA_EXTRACTION,
        implementation_id="default",
        configuration_ref="schema-default",
        configuration_slug="schema-default",
        configuration_version=1,
        specific_data={},
    )
    pipeline_repo.update_status(run.id, PipelineRunStatus.COMPLETED)
    return run


def _in_run(run_id, write):
    """Perform a write with its change events tagged with the run, as the apply route does."""
    set_batch_run_context(run_id)
    try:
        return write()
    finally:
        set_batch_run_context(None)


def test_vision_is_stored_and_read_back(ontology_service, ontology_repo):
    """A vision given at creation survives the round trip through SQLite."""
    taxonomy = ontology_service.create_taxonomy(
        title="House", description="Household tasks by place and activity.", vision=VISION
    )

    stored = ontology_repo.get_taxonomy(taxonomy.id)

    assert stored.vision == VISION
    assert stored.description == "Household tasks by place and activity."


def test_vision_edit_is_recorded_with_old_and_new_values(ontology_service, change_repo):
    """Updating the vision writes one change event carrying both versions."""
    taxonomy = ontology_service.create_taxonomy(title="House", vision="First draft")

    ontology_service.update_taxonomy(taxonomy.id, vision=VISION)

    changes = change_repo.get_changes(entity_id=taxonomy.id).events
    assert len(changes) == 1
    assert changes[0].previous_state == {"vision": "First draft"}
    assert changes[0].new_state == {"vision": VISION}


def test_reverting_a_run_restores_vision_and_scope_note(
    ontology_service, ontology_repo, pipeline_repo, revert_service
):
    """Vision and scope-note edits made in a run are undone by reverting that run."""
    taxonomy = ontology_service.create_taxonomy(title="House", vision="Original vision")
    scheme = ontology_service.create_scheme(
        taxonomy_id=taxonomy.id, title="Places", description="Rooms and areas."
    )
    run = _new_run(pipeline_repo)

    _in_run(run.id, lambda: ontology_service.update_taxonomy(taxonomy.id, vision=VISION))
    _in_run(
        run.id,
        lambda: ontology_service.update_concept_scheme(
            scheme.id, description="Rooms, areas and storage, nested by containment."
        ),
    )
    assert ontology_repo.get_taxonomy(taxonomy.id).vision == VISION

    revert_service.revert_with_summary(run.id)

    assert ontology_repo.get_taxonomy(taxonomy.id).vision == "Original vision"
    assert ontology_repo.get_concept_scheme(scheme.id).description == "Rooms and areas."


def test_scheme_history_matches_what_was_stored(ontology_service, ontology_repo, change_repo):
    """A move is stored and recorded once, with the old and new taxonomy."""
    source = ontology_service.create_taxonomy(title="House")
    target = ontology_service.create_taxonomy(title="Garden")
    scheme = ontology_service.create_scheme(taxonomy_id=source.id, title="Places")

    ontology_service.update_concept_scheme(scheme.id, taxonomy_id=target.id)

    assert ontology_repo.get_concept_scheme(scheme.id).taxonomy_id == target.id
    moves = [
        c
        for c in change_repo.get_changes(entity_id=scheme.id).events
        if "taxonomy_id" in (c.new_state or {})
    ]
    assert [(m.previous_state, m.new_state) for m in moves] == [
        ({"taxonomy_id": source.id}, {"taxonomy_id": target.id})
    ]


def test_reverting_a_run_moves_the_scheme_and_its_classes_back(
    ontology_service, ontology_repo, pipeline_repo, revert_service
):
    """A scheme moved in a run returns, with its classes and counts, when the run is reverted."""
    house = ontology_service.create_taxonomy(title="House")
    garden = ontology_service.create_taxonomy(title="Garden")
    scheme = ontology_service.create_scheme(taxonomy_id=house.id, title="Places")
    room = ontology_service.create_class(concept_scheme_id=scheme.id, title="Room")
    ontology_service.create_individual(title="Main kitchen", class_ids=[room.id])
    run = _new_run(pipeline_repo)

    _in_run(
        run.id, lambda: ontology_service.update_concept_scheme(scheme.id, taxonomy_id=garden.id)
    )
    assert ontology_repo.get_class(room.id).taxonomy_id == garden.id

    result = revert_service.revert_with_summary(run.id)

    assert result.events_reverted == 1
    assert ontology_repo.get_concept_scheme(scheme.id).taxonomy_id == house.id
    assert ontology_repo.get_class(room.id).taxonomy_id == house.id
    [counts] = ontology_repo.count_by_scheme(house.id)
    assert (counts.class_count, counts.individual_count) == (1, 1)
    assert ontology_repo.count_by_scheme(garden.id) == []
