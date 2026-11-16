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
    RunParameterError,
    UnknownConfigurationError,
    UnknownImplementationError,
)
from domain.pipelines.individual_extraction.find_then_type import FindThenTypeOrchestrator
from domain.pipelines.individual_extraction.orchestrator import IndividualExtractionOrchestrator
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from domain.pipelines.selection import MAX_OUTPUT_TOKENS, PipelineResolver

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

    def test_leaving_the_configuration_out_is_no_way_around_a_disabled_default(
        self, resolver, registries
    ):
        _, configurations = registries
        configurations.register(
            EXTRACTION,
            "default",
            "two-pass-haiku",
            {"model": "haiku", "enabled": False},
            default=True,
        )

        with pytest.raises(ConfigurationDisabledError) as error:
            resolver.resolve(EXTRACTION)

        assert str(error.value) == (
            "No configuration was named and the default one, 'two-pass-haiku', of the 'default'"
            " implementation of individual_extraction is disabled (enabled: two-pass-gemini)"
        )

    def test_an_implementation_with_no_enabled_configuration_says_so(self, resolver, registries):
        _, configurations = registries
        configurations.register(
            EXTRACTION,
            "find_then_type",
            "find-then-type",
            {"model": "haiku", "enabled": False},
            default=True,
        )

        with pytest.raises(ConfigurationDisabledError) as error:
            resolver.resolve(EXTRACTION, "find_then_type")

        assert str(error.value).endswith(
            "is disabled (the implementation has no enabled configuration)"
        )

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

    def test_a_parameter_no_configuration_of_the_implementation_sets_is_left_out(self, resolver):
        # find-then-type's default configuration sets a model only
        run_input = resolver.resolve(EXTRACTION, "find_then_type").run_input({"text": "t"})

        assert run_input == {"text": "t", "model": "haiku"}

    def test_the_input_given_is_not_changed(self, resolver):
        given = {"text": "t"}

        resolver.resolve(EXTRACTION).run_input(given)

        assert given == {"text": "t"}


class TestInheritedParameters:
    """A configuration need not set a temperature or an output limit of its own."""

    def test_what_a_configuration_leaves_unset_is_the_implementations_default(
        self, resolver, registries
    ):
        _, configurations = registries
        configurations.register(EXTRACTION, "default", "mine", {"model": "my-model"})

        selection = resolver.resolve(EXTRACTION, None, "mine")

        assert selection.parameters == {
            "model": "my-model",
            "temperature": 0.0,
            "max_tokens": 20000,
        }
        assert selection.run_input({"text": "t"}) == {
            "text": "t",
            "model": "my-model",
            "temperature": 0.0,
            "max_tokens": 20000,
        }

    def test_what_it_sets_is_its_own(self, resolver, registries):
        _, configurations = registries
        configurations.register(
            EXTRACTION, "default", "mine", {"model": "m", "temperature": 0.7, "max_tokens": 900}
        )

        assert resolver.resolve(EXTRACTION, None, "mine").parameters == {
            "model": "m",
            "temperature": 0.7,
            "max_tokens": 900,
        }

    def test_a_parameter_no_configuration_sets_is_absent(self, resolver):
        # find-then-type's default sets a model only
        assert resolver.resolve(EXTRACTION, "find_then_type").parameters == {"model": "haiku"}

    def test_a_pinned_run_gets_them_the_same_way(self, resolver, registries):
        _, configurations = registries
        configurations.register(EXTRACTION, "default", "mine", {"model": "my-model"})

        pinned = resolver.pinned(EXTRACTION, "default", "mine", 1)

        assert pinned.parameters["max_tokens"] == 20000


class TestStoredVersions:
    """A stored configuration is registered under the version its record holds."""

    def test_it_registers_as_the_version_given(self, registries):
        _, configurations = registries

        registered = configurations.register(
            EXTRACTION, "default", "mine", {"model": "m"}, version=3
        )

        assert registered.version == 3
        assert configurations.get_latest(EXTRACTION, "default", "mine").version == 3
        # Earlier versions, whose content is not kept, are not registered at all
        assert configurations.get_version(EXTRACTION, "default", "mine", 1) is None

    def test_an_edit_leaves_only_the_edited_version(self, registries):
        # A stored configuration keeps its latest content alone, so a run pinned
        # to the earlier version finds nothing, before a restart as after one
        _, configurations = registries
        configurations.register(EXTRACTION, "default", "mine", {"model": "m"}, version=1)

        configurations.register(EXTRACTION, "default", "mine", {"model": "edited"}, version=2)

        assert configurations.get_version(EXTRACTION, "default", "mine", 1) is None
        assert configurations.get_latest(EXTRACTION, "default", "mine").config == {
            "model": "edited"
        }

    def test_the_next_version_follows_it(self, registries):
        _, configurations = registries
        configurations.register(EXTRACTION, "default", "mine", {"model": "m"}, version=3)

        assert configurations.register(EXTRACTION, "default", "mine", {"model": "n"}).version == 4

    def test_a_version_not_above_the_latest_is_refused(self, registries):
        _, configurations = registries
        configurations.register(EXTRACTION, "default", "mine", {"model": "m"}, version=3)

        with pytest.raises(ValueError, match="already registered at version 3"):
            configurations.register(EXTRACTION, "default", "mine", {"model": "n"}, version=3)


class TestRemovedConfiguration:
    """A deleted configuration starts no run and is not offered as one that can."""

    def test_it_is_refused_and_not_listed(self, resolver, registries):
        _, configurations = registries

        assert configurations.remove(EXTRACTION, "default", "two-pass-gemini") is True

        with pytest.raises(UnknownConfigurationError) as error:
            resolver.resolve(EXTRACTION, None, "two-pass-gemini")
        assert str(error.value) == (
            "'two-pass-gemini' is not a configuration of the 'default' implementation of"
            " individual_extraction (one of: two-pass-haiku)"
        )
        assert [ref for ref, _ in configurations.list_configs(EXTRACTION, "default")] == [
            "two-pass-haiku"
        ]

    def test_a_run_still_pinned_to_it_finds_nothing(self, resolver, registries):
        # As after a restart, which does not load a deleted configuration
        _, configurations = registries
        configurations.remove(EXTRACTION, "default", "two-pass-gemini")

        assert resolver.pinned(EXTRACTION, "default", "two-pass-gemini", 1) is None

    def test_the_default_configuration_cannot_be_removed(self, registries):
        _, configurations = registries

        with pytest.raises(ValueError, match="cannot be removed"):
            configurations.remove(EXTRACTION, "default", "two-pass-haiku")

    def test_one_that_is_not_registered_is_not_removed(self, registries):
        _, configurations = registries

        assert configurations.remove(EXTRACTION, "default", "no-such") is False


class TestOutputLimit:
    """The output-token limit a run executes with is one a provider can be asked for."""

    def test_a_limit_the_input_names_above_the_bound_is_refused(self, resolver):
        with pytest.raises(RunParameterError) as error:
            resolver.resolve(EXTRACTION).run_input({"max_tokens": MAX_OUTPUT_TOKENS + 1})

        assert str(error.value) == (
            "The run's input names max_tokens 20001: the output-token limit of a run is a"
            " whole number from 1 to 20000, the most every provider can be asked for in one"
            " request"
        )

    @pytest.mark.parametrize("limit", [0, -5, "many", 1.5, True])
    def test_a_limit_that_is_not_a_positive_whole_number_is_refused(self, resolver, limit):
        with pytest.raises(RunParameterError, match="whole number from 1 to 20000"):
            resolver.resolve(EXTRACTION).run_input({"max_tokens": limit})

    def test_the_bound_itself_is_accepted(self, resolver):
        run_input = resolver.resolve(EXTRACTION).run_input({"max_tokens": MAX_OUTPUT_TOKENS})

        assert run_input["max_tokens"] == MAX_OUTPUT_TOKENS

    def test_a_configuration_that_sets_one_above_the_bound_cannot_run(self, resolver, registries):
        _, configurations = registries
        configurations.register(
            EXTRACTION, "default", "too-much", {"model": "m", "max_tokens": 64000}
        )
        selection = resolver.resolve(EXTRACTION, None, "too-much")

        with pytest.raises(RunParameterError, match="The 'too-much' configuration sets max_tokens"):
            selection.run_input({"text": "t"})
        # A limit named in the input is the run's, and lets it run
        assert selection.run_input({"max_tokens": 9000})["max_tokens"] == 9000

    def test_a_run_given_no_limit_at_all_has_none(self, resolver):
        assert "max_tokens" not in resolver.resolve(EXTRACTION, "find_then_type").run_input({})


class TestRegisteredPipelines:
    """What the app and the scripts register (domain/pipelines/bootstrap.py)."""

    def test_registration_fails_when_a_default_is_missing(self, monkeypatch):
        # register_pipelines checks what registration promises (check_defaults)
        def register_without_defaults(impl_registry, config_registry):
            impl_registry.register_impl(PipelineType.NOTES_TO_CLAIMS, "default", TwoPass)
            config_registry.register(PipelineType.NOTES_TO_CLAIMS, "default", "default", {})

        monkeypatch.setattr(
            "domain.pipelines.bootstrap.register_notes_to_claims", register_without_defaults
        )

        with pytest.raises(ValueError) as error:
            register_pipelines(PipelineImplementationRegistry(), PipelineConfigurationRegistry())

        assert "notes_to_claims has no default implementation" in str(error.value)
        assert "notes_to_claims:default has no default configuration" in str(error.value)

    def test_no_configuration_sets_a_limit_a_provider_cannot_send(self, registered):
        implementations, configurations, _ = registered

        limits = [
            latest.config["max_tokens"]
            for pipeline_type, implementation_id in implementations.list_all()
            for _, latest in configurations.list_configs(pipeline_type, implementation_id)
            if latest.config.get("max_tokens") is not None
        ]

        assert limits and max(limits) <= MAX_OUTPUT_TOKENS == 20000

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
            assert selection.config.get("enabled") is not False

    def test_individual_extraction_defaults_to_find_then_type(self, registered):
        implementations, _, resolver = registered

        selection = resolver.resolve(EXTRACTION)

        assert implementations.default_implementation(EXTRACTION) == "find_then_type"
        assert selection.implementation is FindThenTypeOrchestrator
        assert selection.configuration_ref == "extraction-find-then-type"
        assert selection.parameters == {
            "model": "claude-haiku-5-5",
            "temperature": 0.0,
            "max_tokens": 16000,
        }

    def test_the_implementation_named_default_is_two_pass_not_the_default(self, registered):
        # The id is a name only: two-pass runs when a run names it
        implementations, _, resolver = registered

        selection = resolver.resolve(EXTRACTION, "default")

        assert selection.implementation is IndividualExtractionOrchestrator
        assert selection.configuration_ref == "extraction-default"
        assert implementations.default_implementation(EXTRACTION) != "default"

    def test_every_other_type_still_defaults_to_its_default_implementation(self, registered):
        implementations, _, resolver = registered

        others = [t for t in resolver.runnable_types() if t is not EXTRACTION]

        assert {implementations.default_implementation(t) for t in others} == {"default"}

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

    @pytest.mark.parametrize("implementation_id", ["find_then_type", "default"])
    def test_individual_extraction_runs_on_haiku_with_room_to_think(
        self, registered, implementation_id
    ):
        _, _, resolver = registered

        config = resolver.resolve(EXTRACTION, implementation_id).config

        assert config["provider"] == "anthropic"
        assert config["model"] == "claude-haiku-5-5"
        # Claude 5.5 models think before answering; 8000 output tokens ran out on real chunks
        assert config["max_tokens"] >= 16000

    def test_definition_refinements_default_name_still_resolves_without_being_the_default(
        self, registered
    ):
        # Runs were started and pinned under the name "default"; it stays a
        # registered name of the same configuration, not the implementation's default
        _, configurations, resolver = registered
        refinement = PipelineType.SCHEMA_NODE_DEFINITION_REFINEMENT

        named = resolver.resolve(refinement, None, "default")
        unnamed = resolver.resolve(refinement)

        assert named.configuration_ref == "default"
        assert unnamed.configuration_ref == "definition-refinement-default"
        assert named.config == unnamed.config
        assert resolver.pinned(refinement, "default", "default", 1) is not None
        assert configurations.default_configuration(refinement, "default") == (
            "definition-refinement-default"
        )

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
