"""
Integration test: an extraction run can be reverted.

A real ExtractionService.extract_triples run against SQLite records one
change event, an ``extraction_result`` CREATE tagged with the run id, through
the real ChangeEventRecorder. Reverting the run must succeed, leave that event
and the extraction run record in place, and not touch the graph caches.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.events.change_recorder import ChangeEventRecorder
from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.extraction_repo import SQLiteExtractionRepository
from adapters.persistence.sqlite.extraction_run_repo import SQLiteExtractionRunRepository
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.extraction.events import ExtractionCompleted
from domain.extraction.services import ExtractionService
from domain.ontology.entities import Class, ConceptScheme, Taxonomy
from domain.ontology.events import GraphInvalidated
from domain.versioning.revert_service import RevertService
from domain.versioning.value_objects import ChangeOperation
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_llm_provider import FakeLLMProvider
from tests.fakes.fake_nlp_processor import FakeNLPProcessor
from tests.fakes.fake_reference_source import FakeReferenceSource

TAXONOMY_ID = "tx-extract"


@pytest.fixture()
def session_factory():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_engine(f"sqlite:///{Path(tmpdir) / 'local.db'}")
        Base.metadata.create_all(engine)
        yield sessionmaker(bind=engine)
        engine.dispose()


@pytest.fixture()
def ontology_repo(session_factory):
    repo = SQLiteOntologyRepository(session_factory=session_factory)
    repo.save_taxonomy(Taxonomy(id=TAXONOMY_ID, identifier="extract_tax", title="Extract"))
    repo.save_concept_scheme(
        ConceptScheme(id="cs-extract", taxonomy_id=TAXONOMY_ID, identifier="cs", title="CS")
    )
    repo.save_class(
        Class(
            id="cls-person",
            concept_scheme_id="cs-extract",
            taxonomy_id=TAXONOMY_ID,
            identifier="person",
            title="Person",
        )
    )
    return repo


@pytest.fixture()
def change_repo(session_factory):
    return SQLiteChangeRepository(session_factory=session_factory)


@pytest.fixture()
def extraction_run_repo(session_factory):
    return SQLiteExtractionRunRepository(session_factory)


@pytest.fixture()
def extraction_service(session_factory, ontology_repo, change_repo, extraction_run_repo):
    publisher = InProcessEventPublisher()
    recorder = ChangeEventRecorder(change_repo)
    publisher.subscribe(ExtractionCompleted, recorder.on_extraction_completed)
    return ExtractionService(
        ontology_repo=ontology_repo,
        embedding_service=FakeEmbeddingService(),
        llm=FakeLLMProvider(response_content=json.dumps({"individuals": [], "triples": []})),
        nlp=FakeNLPProcessor(),
        reference_sources=[FakeReferenceSource()],
        event_publisher=publisher,
        extraction_repo=SQLiteExtractionRepository(session_factory),
        extraction_run_repo=extraction_run_repo,
    )


def test_revert_extraction_run(extraction_service, change_repo, ontology_repo, extraction_run_repo):
    """Reverting a completed extraction run succeeds and changes nothing."""
    extraction_service.extract_triples(
        text="Ada Lovelace wrote the first program.",
        ontology_id=TAXONOMY_ID,
        model="test-model",
        temperature=0.0,
    )
    events = change_repo.get_changes(limit=None).events
    assert len(events) == 1
    run_id = events[0].batch_run_id
    assert run_id == events[0].entity_id
    assert events[0].operation == ChangeOperation.CREATE

    publisher = FakeEventPublisher()
    revert_service = RevertService(change_repo, ontology_repo, event_publisher=publisher)
    result = revert_service.revert_with_summary(run_id)

    assert result.events_reverted == 0
    run_events = change_repo.get_changes(batch_run_id=run_id, limit=None).events
    assert [e.id for e in run_events] == [events[0].id]
    assert extraction_run_repo.get_extraction_run(run_id) is not None
    assert ontology_repo.get_class("cls-person") is not None
    assert publisher.get_events_of_type(GraphInvalidated) == []
