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
extraction, the chat and MCP tools, scripts) selects through PipelineResolver,
and everything that executes one gives its orchestrator
PipelineSelection.run_input(): the run's input with the configuration's model,
temperature and output-token limit filled in wherever the input names none.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from domain.pipelines.entities import PipelineType
from domain.pipelines.exceptions import (
    ConfigurationDisabledError,
    UnknownConfigurationError,
    UnknownImplementationError,
)
from domain.pipelines.registry import (
    ConfigurationVersion,
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
)

# What a configuration sets for every model call of a run, under the same keys
# in the configuration and in the run's input. `max_tokens` is the most output
# tokens one call may produce.
RUN_PARAMETERS = ("model", "temperature", "max_tokens")


@dataclass(frozen=True)
class PipelineSelection:
    """
    What a run executes: an implementation and one version of a configuration.

    Attributes:
        pipeline_type: The pipeline type
        implementation_id: The implementation
        implementation: Its orchestrator class
        configuration: The configuration version the run is pinned to
    """

    pipeline_type: PipelineType
    implementation_id: str
    implementation: type[Any]
    configuration: ConfigurationVersion

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
        (RUN_PARAMETERS) filled in. A parameter the input gives wins, so a
        caller can still run a configuration with another model.
        """
        filled = dict(input_data)
        for key in RUN_PARAMETERS:
            given = filled.get(key)
            configured = self.config.get(key)
            if (given is None or given == "") and configured is not None:
                filled[key] = configured
        return filled


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
        return PipelineSelection(pipeline_type, implementation_id, implementation, configuration)

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
        return PipelineSelection(pipeline_type, implementation_id, implementation, configuration)

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


def _listed(names: Any) -> str:
    return ", ".join(sorted(names))
