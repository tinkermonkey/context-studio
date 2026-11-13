"""
Find-then-type individual extraction: the two calls that replace pass 1.

The two-pass shape asks one call to find a text's individuals and type them,
against a shortlist of class names. This shape splits that:

- **find** lists what a text mentions, each with its passage, typing nothing;
- **type** asks, for one mention at a time, which one class of the ontology it
  is an instance of, offering the whole class catalog with definitions, or
  none when it is not something to record.

The catalog is the system prompt of every typing call of a run, byte for byte,
so a provider that caches system prompts reads it once. Each function here
makes one LLM call under the rules of llm_calls.complete_parsed and reports a
failure on its result: a text that could not be read is never "mentions
nothing", and a mention that could not be typed is never "not something to
record".
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Callable, NamedTuple, Sequence

from domain.pipelines.ports import LLMProvider
from domain.pipelines.stage_prompts import StagePrompt, render

from .entities import Mention, MentionsResult, TypingPrompt, TypingResult
from .exceptions import IncompleteLLMResponseError
from .llm_calls import TokenTally, complete_parsed, failure_fields
from .prompts import FIND_MENTIONS, TYPE_MENTION
from .span_resolution import resolve_span

_logger = logging.getLogger(__name__)

# Characters of text sent on each side of a mention's passage when it is typed
CONTEXT_WINDOW_CHARS = 1200

# Characters of a class definition (and of a kind's description) put in a prompt
_DEFINITION_CHARS = 260

# The find answer lists every mention of a chunk with a quote each; models that
# think before answering spend output tokens on that first
_FIND_MAX_TOKENS = 16000
_TYPE_MAX_TOKENS = 4000

NONE_ANSWER = "none"
_KINDS = ("thing", "statement")
_DEFAULT_CONFIDENCE = 0.5


class CatalogClass(NamedTuple):
    """A class as the typing prompt lists it."""

    reference: str
    title: str
    kind: str
    definition: str


def kinds_grounding(ontology_title: str, kinds: Sequence[tuple[str, str]]) -> str:
    """
    What the find prompt is told of the ontology: its title and the kinds of
    element it records (its concept schemes, each with its scope).
    """
    lines = [f"Ontology: {ontology_title}"]
    if kinds:
        lines += ["", "It records elements of these kinds:"]
        lines += [
            f"- {title}: {_brief(description)}" if description else f"- {title}"
            for title, description in kinds
        ]
    return "\n".join(lines)


def build_typing_prompt(
    ontology_title: str, classes: Sequence[CatalogClass], prompt: StagePrompt
) -> TypingPrompt:
    """
    The typing prompt of a run: the stage's system prompt with the catalog in
    it. Classes are listed in order of their reference, so the same ontology
    gives the same prompt whatever order its classes were read in.
    """
    listed = sorted(classes, key=lambda cls: cls.reference)
    lines = [f"Ontology: {ontology_title}", "", "Classes (reference: title (kind): definition):"]
    lines += [
        f"- {cls.reference}: {cls.title} ({cls.kind}): {_brief(cls.definition)}" for cls in listed
    ]
    return TypingPrompt(
        system=render(prompt.system, {"catalog": "\n".join(lines)}),
        user=prompt.user,
        class_refs={cls.reference.lower(): cls.reference for cls in listed},
    )


def find_mentions(
    llm: LLMProvider,
    sleep: Callable[[float], None],
    text: str,
    grounding: str,
    model: str,
    temperature: float,
    prompt: StagePrompt,
) -> MentionsResult:
    """
    List what a text mentions (the find stage): one LLM call.

    Args:
        text: The text (a chunk of a source, or a pasted text)
        grounding: What the prompt is told of the ontology (kinds_grounding)
        prompt: The stage's prompts

    Returns:
        The mentions, each with its passage placed in the text where it could
        be; on failure no mentions and a failure_reason
    """
    request = {
        "system_prompt": prompt.system,
        "user_prompt": render(prompt.user, {"text": text, "grounding": grounding}),
        "model": model,
        "temperature": temperature,
        "max_tokens": _FIND_MAX_TOKENS,
        "response_format": "json",
    }
    spent = TokenTally()
    started = time.time()
    mentions: list[Mention] = []
    warnings: list[str] = []
    failed: dict[str, Any] = {}
    try:
        mentions, warnings = complete_parsed(
            llm, sleep, FIND_MENTIONS, request, lambda content: parse_mentions(content, text), spent
        )
    except Exception as exc:
        _logger.error("Finding mentions failed: %s", exc, exc_info=exc)
        failed = failure_fields(exc)
        warnings = [f"Extraction failed: {failed['failure_reason']}"]
    return MentionsResult(
        mentions=mentions,
        warnings=warnings,
        metadata=_spent(model, spent, started),
        **failed,
    )


def type_mention(
    llm: LLMProvider,
    sleep: Callable[[float], None],
    prompt: TypingPrompt,
    context: str,
    mention: Mention,
    model: str,
    temperature: float,
) -> TypingResult:
    """
    Type one mention against the run's class catalog (the type stage): one LLM
    call. It reads nothing but its arguments, so calls can be made side by side.

    Args:
        prompt: The run's typing prompt (build_typing_prompt)
        context: The text around the mention (mention_context)

    Returns:
        The class reference, or None with no failure_reason when the mention
        is not something to record; on failure None and a failure_reason
    """
    request = {
        "system_prompt": prompt.system,
        "user_prompt": render(
            prompt.user,
            {
                "context": context,
                "name": mention.name,
                "quote": f'"{mention.quote}"' if mention.quote else "(no passage)",
            },
        ),
        "model": model,
        "temperature": temperature,
        "max_tokens": _TYPE_MAX_TOKENS,
        "response_format": "json",
    }
    spent = TokenTally()
    started = time.time()
    class_ref: str | None = None
    confidence = 0.0
    failed: dict[str, Any] = {}
    try:
        class_ref, confidence = complete_parsed(
            llm,
            sleep,
            TYPE_MENTION,
            request,
            lambda content: parse_typing(content, prompt.class_refs),
            spent,
        )
    except Exception as exc:
        _logger.error("Typing %r failed: %s", mention.name, exc, exc_info=exc)
        failed = failure_fields(exc)
    return TypingResult(
        class_ref=class_ref,
        confidence=confidence,
        metadata=_spent(model, spent, started),
        **failed,
    )


def mention_context(text: str, mention: Mention) -> str:
    """
    The text a mention is typed in: its passage with CONTEXT_WINDOW_CHARS on
    each side; around the first place its name appears when the passage was
    not placed; the start of the text when the name is not there either.
    """
    start, end = mention.start, mention.end
    if start is None or end is None:
        at = text.find(mention.name)
        start = max(at, 0)
        end = start + (len(mention.name) if at >= 0 else 0)
    return text[max(0, start - CONTEXT_WINDOW_CHARS) : end + CONTEXT_WINDOW_CHARS]


def typing_triple(mention: Mention, class_ref: str, confidence: float) -> dict[str, Any]:
    """
    A typed mention as the typing triple the two-pass shape would have given:
    the individual ``is_a`` the class, with the mention's passage as provenance.
    """
    return {
        "subject": {"kind": "individual", "id": "", "label": mention.name, "class_ids": []},
        "predicate": {"property_definition_id": "", "label": "is_a"},
        "object": {"kind": "class", "id": "", "label": class_ref},
        "confidence": confidence,
        "provenance": {"quote": mention.quote, "start": mention.start, "end": mention.end},
    }


def parse_mentions(content: str, text: str) -> tuple[list[Mention], list[str]]:
    """
    Read a find answer: a JSON object with a ``mentions`` list.

    A mention without a name is skipped. Each quote is placed in the text
    (span_resolution.resolve_span); one that is not there leaves its mention
    without a passage, and a warning says how many were.

    Raises:
        IncompleteLLMResponseError: If the answer is not such an object
    """
    listed = _json_object(content).get("mentions")
    if not isinstance(listed, list):
        raise IncompleteLLMResponseError("its JSON has no mentions list")
    mentions: list[Mention] = []
    unplaced = 0
    for item in listed:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        quote = item.get("quote")
        span = resolve_span(
            quote if isinstance(quote, str) and quote.strip() else None, None, None, text
        )
        unplaced += span.quote is None
        mentions.append(
            Mention(
                name=name,
                kind=item.get("kind") if item.get("kind") in _KINDS else _KINDS[0],
                quote=span.quote,
                start=span.start,
                end=span.end,
            )
        )
    warnings = (
        [f"The passage of {unplaced} of {len(mentions)} mentions was not found in the text"]
        if unplaced
        else []
    )
    return mentions, warnings


def parse_typing(content: str, class_refs: Any) -> tuple[str | None, float]:
    """
    Read a typing answer: a JSON object whose ``class`` is one of the catalog's
    class references, or "none".

    Returns:
        (the class reference as the catalog writes it, or None for "none";
        the answer's confidence, 0..1)

    Raises:
        IncompleteLLMResponseError: If the answer is not such an object, or
            names a class the catalog does not list: that is not an answer,
            and never read as "none"
    """
    answer = _json_object(content)
    named = answer.get("class")
    if not isinstance(named, str) or not named.strip():
        raise IncompleteLLMResponseError("its JSON names no class")
    key = named.strip().lower()
    if key != NONE_ANSWER and key not in class_refs:
        raise IncompleteLLMResponseError(f"it names a class the ontology does not list ({named})")
    try:
        confidence = float(answer.get("confidence", _DEFAULT_CONFIDENCE))
    except (TypeError, ValueError):
        confidence = _DEFAULT_CONFIDENCE
    return (None if key == NONE_ANSWER else class_refs[key]), max(0.0, min(1.0, confidence))


def _json_object(content: str) -> dict[str, Any]:
    """The JSON object in a response, which may wrap it in prose or a code fence."""
    match = re.search(r"\{.*\}", content or "", re.DOTALL)
    if not match:
        raise IncompleteLLMResponseError("it holds no complete JSON object")
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError as error:
        raise IncompleteLLMResponseError(f"its JSON does not parse ({error})") from error
    if not isinstance(data, dict):
        raise IncompleteLLMResponseError("its JSON is not an object")
    return data


def _brief(text: str | None) -> str:
    """A definition on one line, cut to the length a prompt lists it at."""
    return " ".join((text or "").split())[:_DEFINITION_CHARS]


def _spent(model: str, spent: TokenTally, started: float) -> dict[str, int | str]:
    return {
        "model": model,
        "tokens_used": spent.total,
        "duration_ms": int((time.time() - started) * 1000),
    }
