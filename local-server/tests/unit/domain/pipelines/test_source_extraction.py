"""
Unit tests: the individual-extraction implementation a source is extracted
with. `default` reads it unless another is named; the run uses the named
implementation's own configuration for sources unless one of its
configurations is named too; an implementation that is not registered, or
that cannot extract a source, and a configuration of another implementation
are input errors that start no run.
"""

from types import SimpleNamespace

import pytest

from domain.extraction.sources import Source, SourceKind
from domain.ontology.services import OntologyService
from domain.pipelines.entities import PipelineType
from domain.pipelines.individual_extraction.bootstrap import register_individual_extraction
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from domain.pipelines.source_extraction import SourceExtractionService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_proposal_repository import FakeChangeProposalRepository
from tests.fakes.fake_source_repository import FakeSourceRepository

TEXT = "The WRF555SDFZ is a refrigerator. It is made by Acme."


class RecordingSubmitter:
    """Records the runs it is asked to start instead of starting them."""

    def __init__(self) -> None:
        self.submitted: list[SimpleNamespace] = []

    def submit(self, pipeline_type, implementation_id, configuration_ref, input_data):
        run = SimpleNamespace(
            id=f"run-{len(self.submitted) + 1}",
            pipeline_type=pipeline_type,
            implementation_id=implementation_id,
            configuration_ref=configuration_ref,
            input_data=input_data,
        )
        self.submitted.append(run)
        return run


@pytest.fixture()
def repo():
    return FakeOntologyRepository()


@pytest.fixture()
def ontology(repo):
    return OntologyService(repo, FakeEmbeddingService(), FakeEventPublisher())


@pytest.fixture()
def registries():
    implementations = PipelineImplementationRegistry()
    configurations = PipelineConfigurationRegistry()
    register_individual_extraction(implementations, configurations)
    return implementations, configurations


@pytest.fixture()
def submitter():
    return RecordingSubmitter()


@pytest.fixture()
def source(ontology, repo):
    taxonomy = ontology.create_taxonomy(title="House")
    home = ontology.create_dataset(taxonomy.id, "home", "Home")
    return Source(
        taxonomy_id=taxonomy.id,
        dataset_id=home.id,
        kind=SourceKind.TEXT,
        title="Use and care guide",
        pages=1,
        chars=len(TEXT),
        text=TEXT,
        page_starts=[0],
    )


@pytest.fixture()
def service(registries, submitter, source, repo):
    implementations, configurations = registries
    sources = FakeSourceRepository()
    sources.save(source)
    return SourceExtractionService(
        sources=sources,
        ontology_repo=repo,
        implementations=implementations,
        configurations=configurations,
        submitter=submitter,
        runs=SimpleNamespace(list_source_runs=lambda source_ids: []),
        proposals=FakeChangeProposalRepository(),
    )


class TestImplementationChoice:
    def test_default_reads_a_source_when_none_is_named(self, service, submitter, source):
        service.extract(source.id, "home")

        [run] = submitter.submitted
        assert run.pipeline_type is PipelineType.INDIVIDUAL_EXTRACTION
        assert run.implementation_id == "default"
        assert run.configuration_ref == "extraction-default"

    def test_a_named_implementation_runs_with_its_own_configuration(
        self, service, submitter, source, registries
    ):
        runs = service.extract(source.id, "home", implementation_id="find_then_type")

        [run] = submitter.submitted
        assert runs == [run]
        assert run.implementation_id == "find_then_type"
        assert run.configuration_ref == "extraction-find-then-type"
        # The run's model is its configuration's, not the default implementation's
        _, configurations = registries
        expected = configurations.get_latest(
            PipelineType.INDIVIDUAL_EXTRACTION, "find_then_type", "extraction-find-then-type"
        )
        assert run.input_data["model"] == expected.config["model"]
        assert run.input_data["source_id"] == source.id

    def test_a_named_configuration_of_the_implementation_is_used(
        self, service, submitter, source, registries
    ):
        _, configurations = registries
        configurations.register(
            PipelineType.INDIVIDUAL_EXTRACTION,
            "find_then_type",
            "find-then-type-other-model",
            {"provider": "anthropic", "model": "another-model"},
        )

        service.extract(
            source.id,
            "home",
            configuration_ref="find-then-type-other-model",
            implementation_id="find_then_type",
        )

        [run] = submitter.submitted
        assert run.implementation_id == "find_then_type"
        assert run.configuration_ref == "find-then-type-other-model"
        assert run.input_data["model"] == "another-model"

    def test_a_configuration_of_the_default_implementation_still_works(
        self, service, submitter, source
    ):
        service.extract(source.id, "home", configuration_ref="extraction-openrouter-default")

        [run] = submitter.submitted
        assert run.implementation_id == "default"
        assert run.configuration_ref == "extraction-openrouter-default"

    def test_an_unknown_implementation_is_an_input_error(self, service, submitter, source):
        with pytest.raises(ValueError, match="'no_such'.*default, find_then_type"):
            service.extract(source.id, "home", implementation_id="no_such")

        assert submitter.submitted == []

    def test_an_implementation_that_cannot_extract_a_source_is_an_input_error(
        self, service, submitter, source
    ):
        # open_v1 is registered for individual extraction but reads pasted text only
        with pytest.raises(ValueError, match="'open_v1'.*can extract a source"):
            service.extract(source.id, "home", implementation_id="open_v1")

        assert submitter.submitted == []

    @pytest.mark.parametrize(
        "implementation_id, configuration_ref",
        [
            ("find_then_type", "extraction-default"),
            ("default", "extraction-find-then-type"),
            (None, "extraction-find-then-type"),
            ("find_then_type", "no-such-configuration"),
        ],
    )
    def test_a_configuration_of_another_implementation_is_an_input_error(
        self, service, submitter, source, implementation_id, configuration_ref
    ):
        with pytest.raises(ValueError, match=f"'{configuration_ref}' is not a configuration"):
            service.extract(
                source.id,
                "home",
                configuration_ref=configuration_ref,
                implementation_id=implementation_id,
            )

        assert submitter.submitted == []

    def test_schema_extraction_is_not_the_named_implementations(
        self, service, submitter, source, registries
    ):
        _, configurations = registries
        configurations.register(
            PipelineType.SCHEMA_EXTRACTION, "default", "schema-extraction-default", {"model": "m"}
        )

        service.extract(source.id, "home", schema=True, implementation_id="find_then_type")

        individual, schema = submitter.submitted
        assert individual.implementation_id == "find_then_type"
        assert schema.pipeline_type is PipelineType.SCHEMA_EXTRACTION
        assert schema.implementation_id == "default"
        assert schema.configuration_ref == "schema-extraction-default"
        assert individual.input_data["extraction_id"] == schema.input_data["extraction_id"]


def test_each_implementations_source_configuration_is_registered(registries):
    implementations, configurations = registries
    able = {
        impl_id: impl.SOURCE_CONFIGURATION
        for impl_id, impl in implementations.list_by_type(
            PipelineType.INDIVIDUAL_EXTRACTION
        ).items()
        if impl.SOURCE_CONFIGURATION
    }

    assert set(able) == {"default", "find_then_type"}
    for impl_id, configuration in able.items():
        assert configurations.get_latest(
            PipelineType.INDIVIDUAL_EXTRACTION, impl_id, configuration
        ), f"{impl_id}: {configuration} is not registered"
