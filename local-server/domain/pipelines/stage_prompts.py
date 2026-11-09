"""
Stage prompts: the LLM prompts a pipeline sends at each stage, as configuration.

A pipeline declares its stages with default prompts in code. A configuration
can override any stage's system prompt or user prompt template; a stage or
field it leaves out (or blank) keeps the default.

User prompt templates name their inputs as ``{placeholder}``. Only the
placeholders a stage declares are substituted; every other brace is kept as
written, so JSON examples in a template need no escaping.
"""

import re
from dataclasses import dataclass
from typing import Any, Mapping

# A {name} token in a template; JSON braces such as {"a": 1} never match.
_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


@dataclass(frozen=True)
class StagePrompt:
    """
    The prompts for one LLM stage.

    Attributes:
        system: The system prompt
        user: The user prompt template; ``{placeholder}`` names are filled per call
    """

    system: str
    user: str


@dataclass(frozen=True)
class StageDefinition:
    """
    A stage a pipeline sends to the LLM, with its default prompts.

    Attributes:
        key: Stable stage name used in configuration (e.g. "candidate_identification")
        label: Short human-readable name
        description: What the stage does
        placeholders: Names a template may use, each with what it is filled with
        default: The prompts used when a configuration does not override them
    """

    key: str
    label: str
    description: str
    placeholders: Mapping[str, str]
    default: StagePrompt


def render(template: str, values: Mapping[str, Any]) -> str:
    """
    Fill a template's ``{name}`` placeholders from values.

    Only names present in values are replaced; any other braces stay literal.

    Args:
        template: The template text
        values: Placeholder name -> value (converted with str())

    Returns:
        The rendered text
    """
    if not values:
        return template
    pattern = re.compile(r"\{(" + "|".join(re.escape(name) for name in values) + r")\}")
    return pattern.sub(lambda m: str(values[m.group(1)]), template)


def resolve_stage_prompts(
    stages: tuple[StageDefinition, ...],
    overrides: Mapping[str, Any] | None,
) -> dict[str, StagePrompt]:
    """
    The prompts to use for each stage: overrides where set, defaults otherwise.

    Args:
        stages: The pipeline's stage definitions
        overrides: A configuration's ``stage_prompts``: stage key ->
            {"system": str, "user": str}; unknown stages are ignored

    Returns:
        Stage key -> StagePrompt for every stage
    """
    overrides = overrides or {}
    resolved: dict[str, StagePrompt] = {}
    for stage in stages:
        override = overrides.get(stage.key)
        if not isinstance(override, Mapping):
            override = {}
        system = override.get("system")
        user = override.get("user")
        resolved[stage.key] = StagePrompt(
            system=system if isinstance(system, str) and system.strip() else stage.default.system,
            user=user if isinstance(user, str) and user.strip() else stage.default.user,
        )
    return resolved


def strip_defaults(
    stages: tuple[StageDefinition, ...],
    overrides: Mapping[str, Any] | None,
) -> dict[str, dict[str, str]]:
    """
    Only the parts of overrides that differ from the defaults.

    A configuration stores just what it changes, so editing one stage does not
    pin the others to today's default text. Blank fields, fields equal to the
    default and stages left with nothing are dropped.

    Args:
        stages: The pipeline's stage definitions
        overrides: Stage key -> {"system"?: str, "user"?: str} (None for a stage
            means "use the default")

    Returns:
        Stage key -> the fields that differ from the default

    Raises:
        ValueError: If overrides name a stage the pipeline does not have, or a
            template uses a ``{placeholder}`` its stage does not provide
    """
    by_key = {s.key: s for s in stages}
    unknown = sorted(set(overrides or {}) - set(by_key))
    if unknown:
        raise ValueError(f"Unknown stage(s): {', '.join(unknown)}")
    kept: dict[str, dict[str, str]] = {}
    for key, override in (overrides or {}).items():
        if not isinstance(override, Mapping):
            continue
        stage = by_key[key]
        default = stage.default
        fields = {
            name: value
            for name, value in (("system", override.get("system")), ("user", override.get("user")))
            if isinstance(value, str) and value.strip() and value != getattr(default, name)
        }
        for text in fields.values():
            unknown_names = sorted(set(_PLACEHOLDER.findall(text)) - set(stage.placeholders))
            if unknown_names:
                names = ", ".join("{" + name + "}" for name in unknown_names)
                raise ValueError(f"Stage {key} has no placeholder(s) {names}")
        if fields:
            kept[key] = fields
    return kept
