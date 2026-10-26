"""
Integration tests (#1352): attribute-definition creates and updates are recorded
as change events and undone by reverting their run.

Real SQLite with the ChangeEventRecorder wired as in app.py.
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
from domain.ontology.events import AttributeDefinitionCreated, AttributeDefinitionUpdated
from domain.ontology.services import OntologyService
from domain.ontology.value_objects import DataType
from domain.pipelines.entities import PipelineRunStatus, PipelineType
from domain.versioning.revert_service import RevertService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.utils.parent_rows import create_batch_row


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
def service(ontology_repo, change_repo):
    publisher = InProcessEventPublisher()
    recorder = ChangeEventRecorder(change_repo)
    publisher.subscribe(AttributeDefinitionCreated, recorder.on_attribute_definition_created)
    publisher.subscribe(AttributeDefinitionUpdated, recorder.on_attribute_definition_updated)
    return OntologyService(
        repository=ontology_repo,
        embedding_service=FakeEmbeddingService(),
        event_publisher=publisher,
    )


@pytest.fixture()
def revert_service(change_repo, ontology_repo):
    return RevertService(change_repo=change_repo, ontology_repo=ontology_repo)


@pytest.fixture()
def activity(service):
    taxonomy = service.create_taxonomy(title="House")
    scheme = service.create_scheme(taxonomy_id=taxonomy.id, title="Vocabulary")
    return service.create_class(concept_scheme_id=scheme.id, title="Activity")


@pytest.fixture()
def run_id(session_factory):
    repo = PipelineRepository(session_factory=session_factory)
    run = repo.create(
        batch_run_id=create_batch_row(session_factory),
        pipeline_type=PipelineType.SCHEMA_EXTRACTION,
        implementation_id="default",
        configuration_ref="schema-default",
        configuration_slug="schema-default",
        configuration_version=1,
        specific_data={},
    )
    repo.update_status(run.id, PipelineRunStatus.COMPLETED)
    return run.id


def _in_run(run_id, write):
    """Perform a write with its change events tagged with the run, as the apply route does."""
    set_batch_run_context(run_id)
    try:
        return write()
    finally:
        set_batch_run_context(None)


def test_attribute_created_in_a_run_is_deleted_by_reverting_it(
    service, ontology_repo, activity, run_id, revert_service
):
    attribute = _in_run(
        run_id,
        lambda: service.create_attribute_definition(
            class_id=activity.id,
            identifier="estimate_minutes",
            title="Estimate (minutes)",
            datatype="integer",
        ),
    )

    result = revert_service.revert_with_summary(run_id)

    assert ontology_repo.get_attribute_definition(attribute.id) is None
    assert result.events_reverted == 1


def test_attribute_update_in_a_run_is_restored_by_reverting_it(
    service, ontology_repo, activity, run_id, revert_service
):
    attribute = service.create_attribute_definition(
        class_id=activity.id,
        identifier="unit",
        title="Unit",
        datatype="string",
        description="Base unit.",
    )
    _in_run(
        run_id,
        lambda: service.update_attribute_definition(
            attribute.id,
            title="Base unit",
            datatype="integer",
            allowed_values=["each", "pair"],
            description="The resource's base unit.",
        ),
    )
    changed = ontology_repo.get_attribute_definition(attribute.id)
    assert changed.datatype == DataType.INTEGER and changed.allowed_values == ["each", "pair"]

    revert_service.revert_with_summary(run_id)

    restored = ontology_repo.get_attribute_definition(attribute.id)
    assert restored.title == "Unit"
    assert restored.datatype == DataType.STRING
    assert restored.allowed_values is None
    assert restored.description == "Base unit."
