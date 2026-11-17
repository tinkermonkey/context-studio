"""
Selecting what a pipeline run executes.

A run is selected by (pipeline type, implementation, configuration). The
configuration carries everything else that varies: provider, model,
temperature, output-token limit, stage prompts and the implementation's own
settings. An implementation left unnamed is the type's default; a
configuration left unnamed is the implementation's default. Both defaults are
declared at registration (domain/pipelines/registry.py and each pipeline's
bootstrap.py) and read here, so no caller spells one.

Every entry point that starts a run (the run API, the batch route, source
extraction, the chat and MCP tools, scripts) selects through PipelineResolver
and gives the run PipelineSelection.run_input(): its input with the
configuration's model, temperature and output-token limit filled in wherever
the input names none. A run that waits to execute is stored with that input,
so it executes with the parameters it was accepted with whatever happens to
the configuration meanwhile.

Every proposal a run makes records the run's origin (PipelineSelection.origin):
the pipeline type, implementation, configuration and configuration version,
with a digest of what that version made the run do. create_selected_run gives
the run a proposal service that records it, so no implementation does.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from domain.pipelines.entities import PipelineType
from domain.pipelines.exceptions import (
    ConfigurationDisabledError,
    RunParameterError,
    UnknownConfigurationError,
    UnknownImplementationError,
)
from domain.pipelines.registry import (
    ConfigurationVersion,
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)
from domain.pipelines.stage_prompts import resolve_stage_prompts
from domain.versioning.proposals import ProposalOrigin

# What a configuration sets for every model call of a run, under the same keys
# in the configuration and in the run's input. `max_tokens` is the most output
# tokens one call may produce.
RUN_PARAMETERS = ("model", "temperature", "max_tokens")

# The model that settles a recognition tie: when an extracted individual is
# about as close to several existing individuals as to one, it is asked which
# (if any) is the same. A setting of an individual extraction configuration,
# not a run parameter: recognition asks it when the run's results are
# previewed or applied, not while the run executes, so it is never filled into
# a run's input. A configuration that leaves it unset takes its
# implementation's default configuration's.
RECOGNITION_MODEL = "recognition_model"

# The largest output-token limit a run may ask one call for. It was 20,000
# while the Anthropic provider sent every request without streaming, which its
# client refuses above about 21,000; the provider now streams a request asking
# for more. 64,000 is what one call that reads a whole document with thinking
# may need (single_call), and within what the current Claude models (128,000)
# and Gemini 3 Flash (65,536) produce. A model that produces less refuses a
# larger limit, and the call fails saying so.
MAX_OUTPUT_TOKENS = 64000

# Configuration entries that name or describe it without changing what a run does
_NOT_BEHAVIOUR = ("name", "description", "enabled")
DIGEST_CHARS = 12


@dataclass(frozen=True)
class PipelineSelection:
    """
    What a run executes: an implementation and one version of a configuration.

    Attributes:
        pipeline_type: The pipeline type
        implementation_id: The implementation
        implementation: Its orchestrator class
        configuration: The configuration version the run is pinned to
        parameters: The model, temperature and output-token limit the
            configuration gives a run (RUN_PARAMETERS). One the configuration
            leaves unset is the implementation's default configuration's; one
            neither sets is absent.
        recognition_model: The model that settles the recognition ties of the
            run's results (RECOGNITION_MODEL), inherited the same way; None
            when neither configuration names one
    """

    pipeline_type: PipelineType
    implementation_id: str
    implementation: type[Any]
    configuration: ConfigurationVersion
    parameters: Mapping[str, Any] = field(default_factory=dict)
    recognition_model: str | None = None

    @property
    def configuration_ref(self) -> str:
        """The configuration's reference."""
        return self.configuration.config_ref

    @property
    def config(self) -> dict[str, Any]:
        """The configuration's settings."""
        return self.configuration.config

    def run_input(self, input_data: Mapping[str, Any]) -> dict[str, Any]:
        """
        The input the orchestrator executes with: `input_data`, with the
        configuration's model, temperature and output-token limit
        (`parameters`) filled in. A parameter the input gives wins, so a
        caller can still run a configuration with another model.

        Raises:
            RunParameterError: If the output-token limit the run would execute
                with, named in its input or set by its configuration, is not a
                whole number from 1 to MAX_OUTPUT_TOKENS
        """
        filled = dict(input_data)
        named = filled.get("max_tokens") is not None
        for key, configured in self.parameters.items():
            given = filled.get(key)
            if given is None or given == "":
                filled[key] = configured
        limit = filled.get("max_tokens")
        if limit is not None and not _is_output_limit(limit):
            whose = (
                "The run's input names"
                if named
                else f"The {self.configuration_ref!r} configuration sets"
            )
            raise RunParameterError(
                f"{whose} max_tokens {limit!r}: the output-token limit of a run is a whole"
                f" number from 1 to {MAX_OUTPUT_TOKENS}, the most a run may ask one call for"
                + ("" if named else "; edit the configuration, or name a limit in the run's input")
            )
        return filled

    def origin(self, run_input: Mapping[str, Any]) -> ProposalOrigin:
        """
        What a run of this selection records on every proposal it makes: the
        pipeline type, implementation, configuration and its version, and a
        digest of what they make the run do (see ProposalOrigin.digest).

        Args:
            run_input: The input the run executes with (run_input()), whose
                model, temperature and output-token limit may be its own
        """
        settings = {k: v for k, v in self.config.items() if k not in _NOT_BEHAVIOUR}
        stages = getattr(self.implementation, "STAGE_PROMPTS", ())
        prompts = resolve_stage_prompts(stages, self.config.get("stage_prompts"))
        executed = {
            "settings": settings,
            "stage_prompts": {key: [p.system, p.user] for key, p in prompts.items()},
            "parameters": _executed_parameters(run_input),
        }
        text = json.dumps(executed, sort_keys=True, default=str)
        return ProposalOrigin(
            pipeline_type=self.pipeline_type.value,
            implementation_id=self.implementation_id,
            configuration_ref=self.configuration_ref,
            configuration_version=self.configuration.version,
            digest=hashlib.sha256(text.encode()).hexdigest()[:DIGEST_CHARS],
        )


class PipelineResolver:
    """Turns (type, implementation or none, configuration or none) into what a run executes."""

    def __init__(
        self,
        implementations: PipelineImplementationRegistry,
        configurations: PipelineConfigurationRegistry,
    ) -> None:
        self._implementations = implementations
        self._configurations = configurations

    def resolve(
        self,
        pipeline_type: PipelineType,
        implementation_id: str | None = None,
        configuration_ref: str | None = None,
    ) -> PipelineSelection:
        """
        Select what a new run executes.

        Args:
            pipeline_type: The pipeline type
            implementation_id: The implementation; the type's default when omitted
            configuration_ref: One of the implementation's configurations; its
                default when omitted. The run is pinned to its latest version.

        Raises:
            UnknownImplementationError: If the type has no such implementation,
                or none is named and it has no default
            UnknownConfigurationError: If the implementation has no such
                configuration (the message says whose it is, when it is
                another implementation's), or none is named and it has no default
            ConfigurationDisabledError: If the configuration is disabled, also
                when it is the default one of a run that named none
        """
        implementation_id, implementation = self.implementation(pipeline_type, implementation_id)
        registered = self._implementations.list_by_type(pipeline_type)

        # What a run may be started with: the implementation's enabled configurations
        own = [
            ref
            for ref, latest in self._configurations.list_configs(pipeline_type, implementation_id)
            if latest.config.get("enabled") is not False
        ]
        named = bool(configuration_ref)
        if not named:
            configuration_ref = self._configurations.default_configuration(
                pipeline_type, implementation_id
            )
            if configuration_ref is None:
                raise UnknownConfigurationError(
                    f"The {implementation_id!r} implementation of {pipeline_type.value} has no"
                    " default configuration"
                    + (f"; name one of: {_listed(own)}" if own else " and none to run with")
                )
        configuration = self._configurations.get_latest(
            pipeline_type, implementation_id, configuration_ref
        )
        if configuration is None:
            owners = [
                other
                for other in registered
                if other != implementation_id
                and self._configurations.get_latest(pipeline_type, other, configuration_ref)
            ]
            whose = (
                f"is a configuration of the {_listed(owners)} implementation, not of"
                if owners
                else "is not a configuration of"
            )
            raise UnknownConfigurationError(
                f"{configuration_ref!r} {whose} the {implementation_id!r} implementation of"
                f" {pipeline_type.value}"
                + (f" (one of: {_listed(own)})" if own else " (it has none)")
            )
        if configuration.config.get("enabled") is False:
            # The default is refused as a named one is: leaving the
            # configuration out is no way around its being disabled
            which = (
                f"The {configuration_ref!r} configuration"
                if named
                else f"No configuration was named and the default one, {configuration_ref!r},"
            )
            raise ConfigurationDisabledError(
                f"{which} of the {implementation_id!r} implementation of"
                f" {pipeline_type.value} is disabled"
                + (
                    f" (enabled: {_listed(own)})"
                    if own
                    else " (the implementation has no enabled configuration)"
                )
            )
        return self._selection(pipeline_type, implementation_id, implementation, configuration)

    def parameters(
        self, pipeline_type: PipelineType, implementation_id: str, config: Mapping[str, Any]
    ) -> dict[str, Any]:
        """
        The run parameters (RUN_PARAMETERS) a configuration of the
        implementation gives a run: its own, and for one it leaves unset (a
        user-created configuration need not set a temperature or an output
        limit) the implementation's default configuration's.
        """
        return self._inherited(pipeline_type, implementation_id, config, RUN_PARAMETERS)

    def _inherited(
        self,
        pipeline_type: PipelineType,
        implementation_id: str,
        config: Mapping[str, Any],
        keys: tuple[str, ...],
    ) -> dict[str, Any]:
        """
        The configuration's values of `keys`, each it leaves unset taken from
        the implementation's default configuration; a key neither sets is absent.
        """
        default_ref = self._configurations.default_configuration(pipeline_type, implementation_id)
        default = (
            self._configurations.get_latest(pipeline_type, implementation_id, default_ref)
            if default_ref
            else None
        )
        inherited = default.config if default else {}
        resolved = {}
        for key in keys:
            value = config.get(key)
            if value is None:
                value = inherited.get(key)
            if value is not None:
                resolved[key] = value
        return resolved

    def _selection(
        self,
        pipeline_type: PipelineType,
        implementation_id: str,
        implementation: type[Any],
        configuration: ConfigurationVersion,
    ) -> PipelineSelection:
        recognition_model = self._inherited(
            pipeline_type, implementation_id, configuration.config, (RECOGNITION_MODEL,)
        ).get(RECOGNITION_MODEL)
        return PipelineSelection(
            pipeline_type,
            implementation_id,
            implementation,
            configuration,
            self.parameters(pipeline_type, implementation_id, configuration.config),
            recognition_model if isinstance(recognition_model, str) and recognition_model else None,
        )

    def implementation(
        self, pipeline_type: PipelineType, implementation_id: str | None = None
    ) -> tuple[str, type[Any]]:
        """
        An implementation of the type and its orchestrator class: the one
        named, or the type's default.

        Raises:
            UnknownImplementationError: If the type has no such implementation,
                or none is named and it has no default
        """
        implementation_id = implementation_id or self._implementations.default_implementation(
            pipeline_type
        )
        registered = self._implementations.list_by_type(pipeline_type)
        if implementation_id is None:
            raise UnknownImplementationError(
                f"{pipeline_type.value} has no default implementation"
                + (f"; name one of: {_listed(registered)}" if registered else " and none to run")
            )
        implementation = registered.get(implementation_id)
        if implementation is None:
            raise UnknownImplementationError(
                f"{implementation_id!r} is not an implementation of {pipeline_type.value}"
                + (f" (one of: {_listed(registered)})" if registered else " (it has none)")
            )
        return implementation_id, implementation

    def implementations(self, pipeline_type: PipelineType) -> dict[str, type[Any]]:
        """The type's implementations: id -> orchestrator class."""
        return self._implementations.list_by_type(pipeline_type)

    def runnable_types(self) -> list[PipelineType]:
        """The pipeline types that have an implementation to run, in PipelineType's order."""
        registered = {pipeline_type for pipeline_type, _ in self._implementations.list_all()}
        return [pipeline_type for pipeline_type in PipelineType if pipeline_type in registered]

    def pinned(
        self,
        pipeline_type: PipelineType,
        implementation_id: str,
        configuration_ref: str,
        version: int,
    ) -> PipelineSelection | None:
        """
        What a stored run executes: its implementation and the configuration
        version it was pinned to when it was accepted (a configuration disabled
        since then still runs it). None when either is no longer registered.
        """
        implementation = self._implementations.get(pipeline_type, implementation_id)
        configuration = self._configurations.get_version(
            pipeline_type, implementation_id, configuration_ref, version
        )
        if implementation is None or configuration is None:
            return None
        return self._selection(pipeline_type, implementation_id, implementation, configuration)

    def check_defaults(self) -> None:
        """
        Check what registration promises: every pipeline type with an
        implementation has a default one, and every implementation a default
        configuration that is registered.

        Raises:
            ValueError: Naming each type or implementation that lacks its default
        """
        missing: list[str] = []
        by_type: dict[PipelineType, list[str]] = {}
        for pipeline_type, implementation_id in self._implementations.list_all():
            by_type.setdefault(pipeline_type, []).append(implementation_id)
        for pipeline_type, implementation_ids in by_type.items():
            if self._implementations.default_implementation(pipeline_type) is None:
                missing.append(f"{pipeline_type.value} has no default implementation")
            for implementation_id in implementation_ids:
                ref = self._configurations.default_configuration(pipeline_type, implementation_id)
                if ref is None:
                    missing.append(
                        f"{pipeline_type.value}:{implementation_id} has no default configuration"
                    )
        if missing:
            raise ValueError("Pipeline registration is incomplete: " + "; ".join(missing))


def _executed_parameters(run_input: Mapping[str, Any]) -> dict[str, Any]:
    """
    The model, temperature and output-token limit a run executes with, each
    written one way however its input spelled it (a temperature of 0 is 0.0, a
    limit of 8000.0 is 8000), so equal runs hash alike.
    """
    parameters = {key: run_input.get(key) for key in RUN_PARAMETERS}
    temperature, limit = parameters["temperature"], parameters["max_tokens"]
    if isinstance(temperature, (int, float)) and not isinstance(temperature, bool):
        parameters["temperature"] = float(temperature)
    if isinstance(limit, float) and limit.is_integer():
        parameters["max_tokens"] = int(limit)
    return parameters


def _is_output_limit(value: Any) -> bool:
    return (
        isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= MAX_OUTPUT_TOKENS
    )


def _listed(names: Any) -> str:
    return ", ".join(sorted(names))
