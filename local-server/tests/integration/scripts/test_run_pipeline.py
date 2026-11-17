"""
scripts/run_pipeline.py builds a run of every registered pipeline type and
implementation: the services each draws on are wired as in the app.

Construction only, over a real SQLite workspace and fakes for the model ports:
no orchestrator is executed and no LLM call is made.
"""

import pytest

from adapters.persistence.sqlite.connection import create_local_db_engine, create_session_factory
from adapters.persistence.sqlite.models import Base
from adapters.reference.proxy import ReferenceProxy
from config import Settings
from domain.pipelines.bootstrap import register_pipelines
from domain.pipelines.entities import PipelineType
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from scripts.run_pipeline import build_app_state, instantiate_run
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_llm_provider import FakeLLMProvider
from tests.fakes.fake_nlp_processor import FakeNLPProcessor

RESOLVER = register_pipelines(PipelineImplementationRegistry(), PipelineConfigurationRegistry())

EVERY_IMPLEMENTATION = [
    (pipeline_type, implementation_id)
    for pipeline_type in RESOLVER.runnable_types()
    for implementation_id in sorted(RESOLVER.implementations(pipeline_type))
]


@pytest.fixture()
def llm():
    return FakeLLMProvider()


@pytest.fixture()
def app_state(tmp_path, llm):
    engine = create_local_db_engine(f"sqlite:///{tmp_path / 'local.db'}")
    Base.metadata.create_all(engine)
    settings = Settings()
    return build_app_state(
        local_session_factory=create_session_factory(engine),
        settings=settings,
        llm_provider=llm,
        embedding_service=FakeEmbeddingService(),
        nlp_processor=FakeNLPProcessor(),
        # Not started: reference sources address their own APIs and are not called
        reference_proxy=ReferenceProxy(settings.reference.proxy),
    )


def test_every_pipeline_type_is_covered():
    covered = {pipeline_type for pipeline_type, _ in EVERY_IMPLEMENTATION}

    assert covered == set(PipelineType) - {PipelineType.NO_OP}
    # The ones the script could not run before it was given their services
    assert (PipelineType.INDIVIDUAL_EXTRACTION, "open_v1") in EVERY_IMPLEMENTATION
    assert (PipelineType.SCHEMA_RELATIONSHIP_REFLECTION, "default") in EVERY_IMPLEMENTATION
    assert (PipelineType.CLAIM_TRIAGE, "default") in EVERY_IMPLEMENTATION
    assert (PipelineType.NOTES_TO_CLAIMS, "default") in EVERY_IMPLEMENTATION


@pytest.mark.parametrize(
    ("pipeline_type", "implementation_id"),
    EVERY_IMPLEMENTATION,
    ids=[f"{t.value}:{i}" for t, i in EVERY_IMPLEMENTATION],
)
def test_the_script_builds_a_run_of_it(app_state, llm, pipeline_type, implementation_id):
    selection = RESOLVER.resolve(pipeline_type, implementation_id)

    orchestrator, state = instantiate_run(selection, app_state, llm, {"text": "t"})

    assert type(orchestrator) is selection.implementation
    assert state.pipeline_type is pipeline_type
    assert llm.call_count == 0
