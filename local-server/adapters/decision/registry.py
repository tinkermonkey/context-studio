"""
Decision-model instances built from config.json's decision_models section.

Each named instance names an adapter ('workers_ai' or 'llm') and its model.
Callers ask for an instance by name or take the default, so changing the
default (or pointing an instance at another model) is a config change only.

An instance may name a fallback instance, used when it is unconfigured or
unavailable (transport errors, 429, 5xx). Requests the service rejects (other
4xx) and unusable responses are raised instead: a fallback would hide a
revoked token or a bad question and pay for every call.
"""

from __future__ import annotations

from typing import Callable, Mapping, Optional

from adapters.decision.llm import LLMDecisionModel
from adapters.decision.workers_ai import WorkersAIDecisionModel, WorkersAIOptions
from config import DecisionModelInstanceConfig, DecisionModelsConfig
from domain.decision.exceptions import (
    DecisionModelError,
    DecisionModelNotConfiguredError,
    DecisionModelUnavailableError,
    UnknownDecisionModelError,
)
from domain.decision.ports import DecisionModel
from domain.decision.value_objects import Answer, DecisionModelInfo, Question
from domain.pipelines.ports import LLMProvider
from utils.logger import get_logger

logger = get_logger(__name__)


class UnavailableDecisionModel:
    """An instance that cannot be built (e.g. an unknown adapter); every call raises."""

    def __init__(self, name: str, reason: str) -> None:
        self._name = name
        self._reason = reason

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_configured(self) -> bool:
        return False

    def decide(self, state: str, questions: Mapping[str, Question]) -> dict[str, Answer]:
        raise DecisionModelNotConfiguredError(f"Decision model '{self._name}': {self._reason}")

    async def decide_async(
        self, state: str, questions: Mapping[str, Question]
    ) -> dict[str, Answer]:
        raise DecisionModelNotConfiguredError(f"Decision model '{self._name}': {self._reason}")


class FallbackDecisionModel:
    """
    An instance with a fallback: the fallback answers when the primary is
    unconfigured or raises DecisionModelUnavailableError. Other errors are
    raised. Answers report the instance that actually answered.
    """

    def __init__(self, primary: DecisionModel, fallback: DecisionModel) -> None:
        self._primary = primary
        self._fallback = fallback

    @property
    def name(self) -> str:
        return self._primary.name

    @property
    def is_configured(self) -> bool:
        return self._primary.is_configured or self._fallback.is_configured

    def _log_fallback(self, error: DecisionModelError) -> None:
        logger.warning(
            "Decision model %s failed (%s); falling back to %s",
            self._primary.name,
            error,
            self._fallback.name,
        )

    def decide(self, state: str, questions: Mapping[str, Question]) -> dict[str, Answer]:
        if self._primary.is_configured:
            try:
                return self._primary.decide(state, questions)
            except (DecisionModelNotConfiguredError, DecisionModelUnavailableError) as e:
                self._log_fallback(e)
        return self._fallback.decide(state, questions)

    async def decide_async(
        self, state: str, questions: Mapping[str, Question]
    ) -> dict[str, Answer]:
        if self._primary.is_configured:
            try:
                return await self._primary.decide_async(state, questions)
            except (DecisionModelNotConfiguredError, DecisionModelUnavailableError) as e:
                self._log_fallback(e)
        return await self._fallback.decide_async(state, questions)


class DecisionModelRegistry:
    """The configured decision-model instances, by name (implements DecisionModels)."""

    def __init__(
        self,
        config: DecisionModelsConfig,
        instances: Mapping[str, DecisionModel],
        unwrapped: Mapping[str, DecisionModel],
    ) -> None:
        self._config = config
        self._instances = dict(instances)
        # Instances without their fallback, for the per-instance configured flag
        self._unwrapped = dict(unwrapped)
        self._default = config.default

    @property
    def default_name(self) -> Optional[str]:
        return self._default

    def get(self, name: Optional[str] = None) -> DecisionModel:
        key = name if name is not None else self._default
        if key is None:
            raise UnknownDecisionModelError("No default decision model is configured")
        instance = self._instances.get(key)
        if instance is None:
            raise UnknownDecisionModelError(f"No decision model named '{key}'")
        return instance

    def describe(self) -> list[DecisionModelInfo]:
        return [
            DecisionModelInfo(
                name=name,
                adapter=cfg.adapter,
                model=cfg.model,
                configured=self._unwrapped[name].is_configured,
                is_default=name == self._default,
                fallback=cfg.fallback,
            )
            for name, cfg in self._config.models.items()
        ]


AdapterBuilder = Callable[[str, DecisionModelInstanceConfig], DecisionModel]


def _adapter_builders(llm: Optional[LLMProvider]) -> dict[str, AdapterBuilder]:
    def workers_ai(name: str, cfg: DecisionModelInstanceConfig) -> DecisionModel:
        return WorkersAIDecisionModel(
            name,
            model=cfg.model,
            options=WorkersAIOptions(**cfg.options),
            price_per_mtok_in=cfg.price_per_mtok_in,
            price_per_mtok_out=cfg.price_per_mtok_out,
            concurrency=cfg.concurrency,
            timeout_seconds=cfg.timeout_seconds,
        )

    def llm_adapter(name: str, cfg: DecisionModelInstanceConfig) -> DecisionModel:
        return LLMDecisionModel(
            name,
            llm=llm,
            model=cfg.model,
            price_per_mtok_in=cfg.price_per_mtok_in,
            price_per_mtok_out=cfg.price_per_mtok_out,
            concurrency=cfg.concurrency,
            timeout_seconds=cfg.timeout_seconds,
        )

    return {"workers_ai": workers_ai, "llm": llm_adapter}


def build_decision_models(
    config: DecisionModelsConfig,
    llm: Optional[LLMProvider] = None,
    builders: Optional[Mapping[str, AdapterBuilder]] = None,
) -> DecisionModelRegistry:
    """
    Build every configured instance, wrapping those that name a fallback.

    An unknown adapter, invalid adapter options, or a fallback that names a
    missing instance (or loops back) is logged rather than stopping the server.
    """
    builders = builders if builders is not None else _adapter_builders(llm)
    base: dict[str, DecisionModel] = {}
    for name, cfg in config.models.items():
        builder = builders.get(cfg.adapter)
        if builder is None:
            logger.warning("Decision model %s: unknown adapter %r", name, cfg.adapter)
            base[name] = UnavailableDecisionModel(name, f"unknown adapter '{cfg.adapter}'")
        else:
            try:
                base[name] = builder(name, cfg)
            except (ValueError, TypeError) as e:
                # Invalid adapter options (pydantic's ValidationError is a ValueError)
                logger.warning("Decision model %s: invalid options (%s)", name, e)
                base[name] = UnavailableDecisionModel(name, f"invalid options: {e}")

    def with_fallbacks(name: str, seen: tuple[str, ...]) -> DecisionModel:
        fallback = config.models[name].fallback
        if fallback is None:
            return base[name]
        if fallback not in base:
            logger.warning("Decision model %s: fallback %r is not configured", name, fallback)
            return base[name]
        if fallback in seen:
            logger.warning("Decision model %s: fallback %r loops back", name, fallback)
            return base[name]
        return FallbackDecisionModel(base[name], with_fallbacks(fallback, (*seen, fallback)))

    instances = {name: with_fallbacks(name, (name,)) for name in base}
    if config.default is not None and config.default not in instances:
        logger.warning("Default decision model %r is not configured", config.default)
    return DecisionModelRegistry(config, instances, base)
