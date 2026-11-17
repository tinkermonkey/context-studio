"""
Single-call individual extraction: one call finds and types a text's individuals.

The find-then-type shape finds mentions chunk by chunk and types each one in a
call of its own. This shape asks one call to read a whole text (a document, or
a section of one too long for one call) and list every individual in it with
its class, offering every class of the ontology with its whole definition, by
kind. It is the head-to-head's arm B
(documentation/extraction/experiments/2026-11-15-head-to-head.md) without its
relationships, which pass 2 states as for find-then-type.

The catalog is in the system prompt, the same byte for byte for every call
against the ontology, so a provider that caches system prompts reads it once.
The call is made under the rules of llm_calls.complete_parsed and reports a
failure on its result: a text that could not be read never "holds nothing".
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Callable, Mapping, Sequence

from domain.pipelines.ports import LLMProvider
from domain.pipelines.stage_prompts import StagePrompt, render

from .entities import FoundIndividual, FoundIndividualsResult, Mention
from .exceptions import IncompleteLLMResponseError
from .find_then_type import CatalogClass, _json_object
from .llm_calls import TokenTally, complete_parsed, failure_fields
from .prompts import FIND_INDIVIDUALS
from .span_resolution import resolve_span

_logger = logging.getLogger(__name__)

# The most output tokens the call may produce when the caller names no limit.
# The call thinks before it answers and lists every individual of a document
# with a quote each: the head-to-head's one call used up to 28,700 on a
# 46,000-character document (relationships included)
FIND_INDIVIDUALS_MAX_TOKENS = 64000


def build_catalog(
    ontology_title: str, classes: Sequence[CatalogClass]
) -> tuple[str, dict[str, str]]:
    """
    The catalog the call is offered, and the class references an answer may name.

    Classes are listed in order of their reference, under a heading for each
    kind (concept scheme) as it first comes, each as "reference (title):
    definition" with the whole definition on one line. The same ontology so
    gives the same catalog whatever order its classes were read in.

    Returns:
        (the catalog text, each class reference under its lowercased form)
    """
    lines = [f"Ontology: {ontology_title}", "", "# Classes"]
    kind = None
    for cls in sorted(classes, key=lambda c: c.reference):
        if cls.kind != kind:
            kind = cls.kind
            lines += ["", f"## {_one_line(kind)}"]
        definition = _one_line(cls.definition)
        lines.append(
            f"- {cls.reference} ({_one_line(cls.title)})"
            + (f": {definition}" if definition else "")
        )
    return "\n".join(lines), {cls.reference.lower(): cls.reference for cls in classes}


def find_individuals(
    llm: LLMProvider,
    sleep: Callable[[float], None],
    text: str,
    catalog: str,
    class_refs: Mapping[str, str],
    model: str,
    temperature: float,
    prompt: StagePrompt,
    max_tokens: int | None = None,
    effort: str | None = None,
) -> FoundIndividualsResult:
    """
    Find and type every individual of a text (the find_individuals stage): one LLM call.

    Args:
        text: The text (a source, a section of one, or a pasted text)
        catalog: The ontology's class catalog (build_catalog)
        class_refs: The class references an answer may name, under their lowercased form
        prompt: The stage's prompts
        max_tokens: The most output tokens the call may produce;
            FIND_INDIVIDUALS_MAX_TOKENS when None
        effort: How much the model thinks; its default when None

    Returns:
        The individuals, each with its passage placed in the text where it
        could be; on failure none and a failure_reason
    """
    request: dict[str, Any] = {
        "system_prompt": render(prompt.system, {"catalog": catalog}),
        "user_prompt": render(prompt.user, {"text": text}),
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens or FIND_INDIVIDUALS_MAX_TOKENS,
        "response_format": "json",
    }
    if effort is not None:
        request["effort"] = effort
    spent = TokenTally()
    started = time.time()
    individuals: list[FoundIndividual] = []
    warnings: list[str] = []
    failed: dict[str, Any] = {}
    try:
        individuals, warnings = complete_parsed(
            llm,
            sleep,
            FIND_INDIVIDUALS,
            request,
            lambda content: parse_individuals(content, text, class_refs),
            spent,
            # An answer cut off at the output limit would be cut off again, at
            # up to 64,000 Opus output tokens a time: the section fails at once
            stop_when_cut_off=True,
        )
    except Exception as exc:
        _logger.error("Finding individuals failed: %s", exc, exc_info=exc)
        failed = failure_fields(exc)
        warnings = [f"Extraction failed: {failed['failure_reason']}"]
    return FoundIndividualsResult(
        individuals=individuals,
        warnings=warnings,
        metadata={
            "model": model,
            "tokens_used": spent.total,
            "duration_ms": int((time.time() - started) * 1000),
        },
        **failed,
    )


def parse_individuals(
    content: str, text: str, class_refs: Mapping[str, str]
) -> tuple[list[FoundIndividual], list[str]]:
    """
    Read an answer: a JSON object with an ``individuals`` list of
    ``{title, class, quote}``.

    An item without a title is skipped. One that names a class the catalog
    does not list is left out, and a warning says how many were: the rest of
    the answer stands. Each quote is placed in the text
    (span_resolution.resolve_span); one that is not there leaves its
    individual without a passage, and a warning says how many were.

    Raises:
        IncompleteLLMResponseError: If the answer is not such an object, or
            lists items of which none is an individual with a title and a
            listed class: that is not an answer, and never read as "holds nothing"
    """
    listed = _json_object(content).get("individuals")
    if not isinstance(listed, list):
        raise IncompleteLLMResponseError("its JSON has no individuals list")
    found: list[FoundIndividual] = []
    unknown: list[str] = []
    unplaced = 0
    for item in listed:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        named = str(item.get("class") or "").strip()
        class_ref = class_refs.get(named.lower())
        if class_ref is None:
            unknown.append(named)
            continue
        quote = item.get("quote")
        span = resolve_span(
            quote if isinstance(quote, str) and quote.strip() else None, None, None, text
        )
        unplaced += span.quote is None
        found.append(
            FoundIndividual(
                Mention(name=title, kind="thing", quote=span.quote, start=span.start, end=span.end),
                class_ref,
            )
        )
    if listed and not found:
        raise IncompleteLLMResponseError(
            f"none of the {len(listed)} individuals it lists has a title and a listed class"
        )
    warnings = []
    if unknown:
        warnings.append(
            f"{len(unknown)} individuals named a class the ontology does not list and were"
            f" left out ({', '.join(sorted(set(unknown))[:5])})"
        )
    if unplaced:
        warnings.append(
            f"The passage of {unplaced} of {len(found)} individuals was not found in the text"
        )
    return found, warnings


def name_spans(name: str, text: str) -> list[tuple[int, int]]:
    """
    Where a name appears in a text as written: whole words, case and all.
    """
    if not name.strip():
        return []
    pattern = re.compile(r"(?<!\w)" + re.escape(name) + r"(?!\w)")
    return [(match.start(), match.end()) for match in pattern.finditer(text)]


def _one_line(text: str | None) -> str:
    return " ".join((text or "").split())
