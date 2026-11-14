"""
Unit tests: how a pipeline run is selected (domain/pipelines/selection.py).

A run is selected by (pipeline type, implementation, configuration). An
implementation left out is the type's default and a configuration left out is
the implementation's default, both declared at registration. What cannot be
selected is refused with a message naming what can. The configuration's model,
temperature and output-token limit become the run's unless its input names
its own.
"""

import pytest

from domain.pipelines.bootstrap import register_pipelines
from domain.pipelines.entities import PipelineType
from domain.pipelines.exceptions import (
    ConfigurationDisabledError,
    PipelineSelectionError,
    UnknownConfigurationError,
    UnknownImplementationError,
)
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from domain.pipelines.selection import PipelineResolver

EXTRACTION = PipelineType.INDIVIDUAL_EXTRACTION


class TwoPass:
    """Stands in for an orchestrator class."""


class FindThenType:
    """Stands in for another orchestrator class."""


@pytest.fixture()
def registries():
    implementations = PipelineImplementationRegistry()
    configurations = PipelineConfigurationRegistry()
    implementations.register_impl(EXTRACTION, "default", TwoPass, default=True)
    implementations.register_impl(EXTRACTION, "find_then_type", FindThenType)
    configurations.register(
        EXTRACTION,
        "default",
        "two-pass-haiku",
        {"model": "haiku", "temperature": 0.0, "max_tokens": 20000},
        default=True,
    )
    configurations.register(EXTRACTION, "default", "two-pass-gemini", {"model": "gemini"})
    configurations.register(
        EXTRACTION, "find_then_type", "find-then-type", {"model": "haiku"}, default=True
    )
    return implementations, configurations


@pytest.fixture()
def resolver(registries):
    return PipelineResolver(*registries)


class TestDefaultsAreDeclaredAtRegistration:
    def test_a_type_has_one_default_implementation(self, registries):
        implementations, _ = registries

        assert implementations.default_implementation(EXTRACTION) == "default"
        with pytest.raises(ValueError, match="already has a default implementation: default"):
            implementations.register_impl(EXTRACTION, "other", TwoPass, default=True)
        # The refused registration registered nothing
        assert implementations.get(EXTRACTION, "other") is None

    def test_an_implementation_has_one_default_configuration(self, registries):
        _, configurations = registries

        assert configurations.default_configuration(EXTRACTION, "default") == "two-pass-haiku"
        with pytest.raises(ValueError, match="already has a default configuration"):
            configurations.register(EXTRACTION, "default", "two-pass-gemini", {}, default=True)

    def test_a_new_version_of_the_default_configuration_stays_the_default(self, registries):
        _, configurations = registries

        updated = configurations.register(
            EXTRACTION, "default", "two-pass-haiku", {"model": "haiku-next"}, default=True
        )

        assert updated.version == 2
        assert configurations.default_configuration(EXTRACTION, "default") == "two-pass-haiku"

    def test_a_type_without_a_default_implementation_is_reported(self):
        implementations = PipelineImplementationRegistry()
        configurations = PipelineConfigurationRegistry()
        implementations.register_impl(EXTRACTION, "default", TwoPass)
        configurations.register(EXTRACTION, "default", "c", {})

        with pytest.raises(ValueError) as error:
            PipelineResolver(implementations, configurations).check_defaults()

        assert "individual_extraction has no default implementation" in str(error.value)
        assert "individual_extraction:default has no default configuration" in str(error.value)


class TestResolve:
    def test_nothing_named_is_the_default_implementation_and_its_default_configuration(
        self, resolver
    ):
        selection = resolver.resolve(EXTRACTION)

        assert selection.implementation_id == "default"
        assert selection.implementation is TwoPass
        assert selection.configuration_ref == "two-pass-haiku"
        assert selection.configuration.version == 1

    def test_a_named_implementation_runs_with_its_own_default_configuration(self, resolver):
        selection = resolver.resolve(EXTRACTION, "find_then_type")

        assert selection.implementation is FindThenType
        assert selection.configuration_ref == "find-then-type"

    def test_a_named_configuration_of_the_implementation_is_used(self, resolver):
        selection = resolver.resolve(EXTRACTION, None, "two-pass-gemini")

        assert selection.implementation_id == "default"
        assert selection.config["model"] == "gemini"

    def test_the_latest_version_of_the_configuration_is_pinned(self, resolver, registries):
        _, configurations = registries
        configurations.register(EXTRACTION, "default", "two-pass-gemini", {"model": "gemini-2"})

        selection = resolver.resolve(EXTRACTION, "default", "two-pass-gemini")

        assert selection.configuration.version == 2
        assert selection.config["model"] == "gemini-2"

    def test_an_unknown_implementation_names_the_registered_ones(self, resolver):
        with pytest.raises(UnknownImplementationError) as error:
            resolver.resolve(EXTRACTION, "no_such")

        assert str(error.value) == (
            "'no_such' is not an implementation of individual_extraction"
            " (one of: default, find_then_type)"
        )

    def test_a_type_with_nothing_registered_has_nothing_to_run(self, resolver):
        with pytest.raises(UnknownImplementationError, match="no_op has no default"):
            resolver.resolve(PipelineType.NO_OP)

    def test_a_configuration_of_another_implementation_says_whose_it_is(self, resolver):
        with pytest.raises(UnknownConfigurationError) as error:
            resolver.resolve(EXTRACTION, "find_then_type", "two-pass-haiku")

        assert str(error.value) == (
            "'two-pass-haiku' is a configuration of the default implementation, not of the"
            " 'find_then_type' implementation of individual_extraction (one of: find-then-type)"
        )

    def test_an_unknown_configuration_names_the_implementations_own(self, resolver):
        with pytest.raises(UnknownConfigurationError) as error:
            resolver.resolve(EXTRACTION, None, "no-such")

        assert str(error.value) == (
            "'no-such' is not a configuration of the 'default' implementation of"
            " individual_extraction (one of: two-pass-gemini, two-pass-haiku)"
        )

    def test_a_disabled_configuration_is_refused_and_not_offered(self, resolver, registries):
        _, configurations = registries
        configurations.register(
            EXTRACTION, "default", "two-pass-gemini", {"model": "gemini", "enabled": False}
        )

        with pytest.raises(ConfigurationDisabledError) as disabled:
            resolver.resolve(EXTRACTION, "default", "two-pass-gemini")
        with pytest.raises(UnknownConfigurationError) as unknown:
            resolver.resolve(EXTRACTION, "default", "no-such")

        assert str(disabled.value) == (
            "The 'two-pass-gemini' configuration of the 'default' implementation of"
            " individual_extraction is disabled (enabled: two-pass-haiku)"
        )
        assert "(one of: two-pass-haiku)" in str(unknown.value)

    def test_selection_errors_are_input_errors_of_the_caller(self):
        # Entry points that answer a ValueError as bad input answer these too
        assert issubclass(PipelineSelectionError, ValueError)


class TestPinned:
    def test_a_stored_run_executes_the_version_it_was_pinned_to(self, resolver, registries):
        _, configurations = registries
        configurations.register(EXTRACTION, "default", "two-pass-gemini", {"model": "gemini-2"})

        selection = resolver.pinned(EXTRACTION, "default", "two-pass-gemini", 1)

        assert selection is not None
        assert selection.config["model"] == "gemini"

    def test_a_configuration_disabled_since_the_run_was_accepted_still_runs_it(
        self, resolver, registries
    ):
        _, configurations = registries
        configurations.register(
            EXTRACTION, "default", "two-pass-gemini", {"model": "gemini", "enabled": False}
        )

        assert resolver.pinned(EXTRACTION, "default", "two-pass-gemini", 2) is not None

    def test_what_is_no_longer_registered_is_none(self, resolver):
        assert resolver.pinned(EXTRACTION, "default", "two-pass-gemini", 7) is None
        assert resolver.pinned(EXTRACTION, "gone", "two-pass-gemini", 1) is None


class TestRunInput:
    def test_the_configurations_parameters_are_the_runs(self, resolver):
        run_input = resolver.resolve(EXTRACTION).run_input({"text": "t", "ontology_id": "o"})

        assert run_input == {
            "text": "t",
            "ontology_id": "o",
            "model": "haiku",
            "temperature": 0.0,
            "max_tokens": 20000,
        }

    def test_a_parameter_the_input_names_wins(self, resolver):
        run_input = resolver.resolve(EXTRACTION).run_input(
            {"model": "opus", "temperature": 0.7, "max_tokens": 500}
        )

        assert run_input == {"model": "opus", "temperature": 0.7, "max_tokens": 500}

    def test_an_empty_or_null_parameter_names_nothing(self, resolver):
        run_input = resolver.resolve(EXTRACTION).run_input({"model": "", "temperature": None})

        assert run_input["model"] == "haiku"
        assert run_input["temperature"] == 0.0

    def test_a_parameter_the_configuration_lacks_is_left_out(self, resolver):
        run_input = resolver.resolve(EXTRACTION, None, "two-pass-gemini").run_input({"text": "t"})

        assert run_input == {"text": "t", "model": "gemini"}

    def test_the_input_given_is_not_changed(self, resolver):
        given = {"text": "t"}

        resolver.resolve(EXTRACTION).run_input(given)

        assert given == {"text": "t"}


class TestRegisteredPipelines:
    """What the app and the scripts register (domain/pipelines/bootstrap.py)."""

    @pytest.fixture(scope="class")
    def registered(self):
        implementations = PipelineImplementationRegistry()
        configurations = PipelineConfigurationRegistry()
        resolver = register_pipelines(implementations, configurations)
        return implementations, configurations, resolver

    def test_every_registered_type_runs_with_nothing_named(self, registered):
        _, _, resolver = registered

        runnable = resolver.runnable_types()

        assert set(runnable) == set(PipelineType) - {PipelineType.NO_OP}
        for pipeline_type in runnable:
            selection = resolver.resolve(pipeline_type)
            assert selection.implementation_id == "default"
            assert selection.config.get("enabled") is not False

    def test_every_implementation_has_a_default_configuration_of_its_own(self, registered):
        implementations, configurations, resolver = registered

        for pipeline_type, implementation_id in implementations.list_all():
            selection = resolver.resolve(pipeline_type, implementation_id)
            assert selection.configuration_ref == configurations.default_configuration(
                pipeline_type, implementation_id
            )

    def test_the_default_configurations_of_individual_extraction(self, registered):
        _, configurations, resolver = registered

        defaults = {
            implementation_id: configurations.default_configuration(EXTRACTION, implementation_id)
            for implementation_id in resolver.implementations(EXTRACTION)
        }

        assert defaults == {
            "default": "extraction-default",
            "open_v1": "extraction-open-v1",
            "find_then_type": "extraction-find-then-type",
        }

    def test_individual_extraction_defaults_to_haiku_with_room_to_think(self, registered):
        _, _, resolver = registered

        config = resolver.resolve(EXTRACTION).config

        assert config["provider"] == "anthropic"
        assert config["model"] == "claude-haiku-5-5"
        # Claude 5.5 models think before answering; 8000 output tokens ran out on real chunks
        assert config["max_tokens"] >= 16000

    def test_no_configuration_is_registered_twice_under_another_name(self, registered):
        _, configurations, _ = registered

        refs = [
            ref
            for ref, _ in configurations.list_configs(
                PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT, "default"
            )
        ]

        assert refs == ["definition-refinement-default"]

    def test_implementations_that_can_extract_a_source(self, registered):
        _, _, resolver = registered

        able = {
            (pipeline_type.value, implementation_id)
            for pipeline_type in resolver.runnable_types()
            for implementation_id, implementation in resolver.implementations(pipeline_type).items()
            if getattr(implementation, "EXTRACTS_SOURCES", False)
        }

        assert able == {
            ("individual_extraction", "default"),
            ("individual_extraction", "find_then_type"),
            ("schema_extraction", "default"),
        }
