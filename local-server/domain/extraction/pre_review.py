"""
Pre-review: a stage that reviews extracted individuals before a person does.

Designed in the DR changeset ``extraction-pre-review-stage`` and assessed by
documentation/extraction/experiments/2026-11-22-pre-review-stage.md. One call
reads a text and the individuals extracted from it (numbered: title, class,
quote) against the ontology's whole class catalog, and asks two questions of
each:

- **split**: is it one item or several? Asked only where the split witness
  marks its title as a list;
- **retype**: is its class the best fit, compared with the class it could
  most plausibly be?

The answer lists only the individuals it changes or is unsure about; every
other one is kept. An answer about an individual that is not listed, a retype
to a class the catalog does not list (or to its own class), a split of an
individual the witness did not mark, or a split into fewer than two usable
parts is left out with a warning, and that individual is kept as extracted. A
part whose quote is not found in the text keeps no passage, as an extracted
individual's does (single_call.parse_individuals). The call is made under the
rules of llm_calls.complete_parsed and reports a failure on its result: a
failed review changes nothing and is never read as "everything is right".

This module does not wire the stage into an orchestrator or a proposal; the
experiment decides whether it is.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from domain.pipelines.ports import LLMProvider
from domain.pipelines.stage_prompts import StagePrompt, render

from .entities import (
    FoundIndividual,
    PreReviewAnswer,
    PreReviewPart,
    PreReviewQuestion,
    PreReviewVerdict,
)
from .exceptions import IncompleteLLMResponseError
from .find_then_type import _json_object
from .llm_calls import TokenTally, complete_parsed, failure_fields
from .prompts import PRE_REVIEW
from .span_resolution import resolve_span

_logger = logging.getLogger(__name__)

# A list inside a title: a comma, "and", "&" or "+" between words, or a slash
# joining two words ("Torx T20, T25", "Compression nut and ferrule",
# "Straight and Phillips blade screwdriver"). It marks where the split question
# applies; it never decides the answer: most DR titles it marks are one item
# ("Newcomers and Junior Contributors", "GNU/Linux").
_LIST_MARK = re.compile(r"\w,\s+\w|\s(?:and|&|\+)\s|[A-Za-z]/[A-Za-z]", re.IGNORECASE)

# The most output tokens the call may produce when the caller names no limit.
# The answer lists only what changes, with a short reason each; the limit stays
# under the provider's unstreamed ceiling (20,000).
PRE_REVIEW_MAX_TOKENS = 16000
# The longest quote shown per individual in the list
_QUOTE_CHARS = 300
LIST_MARK = "[list?]"
ALL_QUESTIONS = frozenset(q.value for q in PreReviewQuestion)


def split_witness(title: str) -> bool:
    """Whether a title looks like a list of several things, so the split question applies."""
    return bool(_LIST_MARK.search(title or ""))


@dataclass
class PreReviewResult:
    """
    What one pre-review call made of a text's individuals.

    ``verdicts`` holds an entry for each individual the stage split, retyped or
    was unsure about, by its index in the list it was given; any other was
    kept. ``metadata`` and the failure fields read as on FoundIndividualsResult:
    a failure_reason means nothing was reviewed.
    """

    verdicts: dict[int, PreReviewVerdict] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, int | str] = field(default_factory=dict)
    failure_reason: str | None = None
    incomplete_response: bool = False
    provider_failed: bool = False
    provider_refused: bool = False


def render_items(individuals: Sequence[FoundIndividual], questions: Collection[str]) -> str:
    """The numbered list the call is given: ``n. title | class | "quote"``, marked where asked to split."""
    lines = []
    for index, individual in enumerate(individuals, start=1):
        quote = " ".join((individual.mention.quote or "").split())[:_QUOTE_CHARS]
        mark = (
            f" {LIST_MARK}"
            if PreReviewQuestion.SPLIT.value in questions and split_witness(individual.mention.name)
            else ""
        )
        lines.append(
            f'{index}. {individual.mention.name} | {individual.class_ref} | "{quote}"{mark}'
        )
    return "\n".join(lines)


def review_individuals(
    llm: LLMProvider,
    sleep: Callable[[float], None],
    text: str,
    individuals: Sequence[FoundIndividual],
    catalog: str,
    class_refs: Mapping[str, str],
    model: str,
    temperature: float,
    prompt: StagePrompt,
    max_tokens: int | None = None,
    effort: str | None = None,
    questions: Collection[str] = ALL_QUESTIONS,
) -> PreReviewResult:
    """
    Review a text's extracted individuals (the pre_review stage): one LLM call.

    Args:
        text: The text the individuals were found in
        individuals: The individuals, in the order they are numbered
        catalog: The ontology's class catalog (single_call.build_catalog)
        class_refs: The class references an answer may name, under their lowercased form
        prompt: The stage's prompts
        max_tokens: The most output tokens the call may produce;
            PRE_REVIEW_MAX_TOKENS when None
        effort: How much the model thinks; its default when None
        questions: The questions whose answers are used ("split", "retype");
            an answer to any other is left out

    Returns:
        The verdicts by index (0-based) of the individuals the stage changed or
        was unsure about; on failure none and a failure_reason
    """
    if not individuals:
        return PreReviewResult(metadata={"model": model, "tokens_used": 0, "duration_ms": 0})
    request: dict[str, Any] = {
        "system_prompt": render(prompt.system, {"catalog": catalog}),
        "user_prompt": render(
            prompt.user, {"text": text, "items": render_items(individuals, questions)}
        ),
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens or PRE_REVIEW_MAX_TOKENS,
        "response_format": "json",
    }
    if effort is not None:
        request["effort"] = effort
    spent = TokenTally()
    started = time.time()
    result = PreReviewResult()
    try:
        result.verdicts, result.warnings = complete_parsed(
            llm,
            sleep,
            PRE_REVIEW,
            request,
            lambda content: parse_reviews(content, text, individuals, class_refs, model, questions),
            spent,
            stop_when_cut_off=True,
        )
    except Exception as exc:
        _logger.error("Pre-review failed: %s", exc, exc_info=exc)
        failed = failure_fields(exc)
        for name, value in failed.items():
            setattr(result, name, value)
        result.warnings = [f"Pre-review failed: {failed['failure_reason']}"]
    result.metadata = {
        "model": model,
        "tokens_used": spent.total,
        "duration_ms": int((time.time() - started) * 1000),
    }
    return result


def parse_reviews(
    content: str,
    text: str,
    individuals: Sequence[FoundIndividual],
    class_refs: Mapping[str, str],
    model: str = "",
    questions: Collection[str] = ALL_QUESTIONS,
) -> tuple[dict[int, PreReviewVerdict], list[str]]:
    """
    Read an answer: a JSON object with a ``reviews`` list of
    ``{item, answer, reasoning, compared, class, parts}``.

    See the module docstring for what is left out. The first answer about an
    individual is used; a later one is left out.

    Raises:
        IncompleteLLMResponseError: If the answer is not such an object: that
            is not an answer, and never read as "every individual is right"
    """
    listed = _json_object(content).get("reviews")
    if not isinstance(listed, list):
        raise IncompleteLLMResponseError("its JSON has no reviews list")
    verdicts: dict[int, PreReviewVerdict] = {}
    left_out: list[str] = []
    for review in listed:
        if not isinstance(review, dict):
            continue
        reason = _verdict(review, text, individuals, class_refs, model, questions, verdicts)
        if reason is None:
            continue
        if isinstance(reason, str):
            left_out.append(reason)
        else:
            index, verdict = reason
            verdicts[index] = verdict
    warnings = []
    if left_out:
        shown = "; ".join(left_out[:5])
        warnings.append(f"{len(left_out)} pre-review answers were left out ({shown})")
    unplaced = sum(1 for v in verdicts.values() for part in v.parts if part.quote is None)
    if unplaced:
        warnings.append(f"The quote of {unplaced} split parts was not found in the text")
    return verdicts, warnings


def _verdict(
    review: Mapping[str, Any],
    text: str,
    individuals: Sequence[FoundIndividual],
    class_refs: Mapping[str, str],
    model: str,
    questions: Collection[str],
    done: Mapping[int, PreReviewVerdict],
) -> tuple[int, PreReviewVerdict] | str | None:
    """One review read as a verdict, or why it is left out; None for a keep (nothing to do)."""
    try:
        number = int(review.get("item"))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return f"item {review.get('item')!r} is not a number"
    index = number - 1
    if not 0 <= index < len(individuals):
        return f"item {number} is not listed"
    if index in done:
        return f"item {number} is answered twice"
    individual = individuals[index]
    try:
        answer = PreReviewAnswer(str(review.get("answer") or "").strip().lower())
    except ValueError:
        return f"item {number}: {review.get('answer')!r} is not an answer"
    reasoning = " ".join(str(review.get("reasoning") or "").split())
    compared = tuple(
        class_refs[str(ref).strip().lower()]
        for ref in review.get("compared") or ()
        if str(ref).strip().lower() in class_refs
    )
    common = {
        "reasoning": reasoning,
        "original_title": individual.mention.name,
        "original_class_ref": individual.class_ref,
        "compared": compared,
        "model": model,
    }
    if answer is PreReviewAnswer.KEEP:
        return None
    if answer is PreReviewAnswer.UNSURE:
        return index, PreReviewVerdict(answer, None, **common)
    question = PreReviewQuestion(answer.value)
    if question.value not in questions:
        return f"item {number}: {question.value} is not asked"
    if answer is PreReviewAnswer.RETYPE:
        class_ref = class_refs.get(str(review.get("class") or "").strip().lower())
        if class_ref is None:
            return f"item {number}: {review.get('class')!r} is not a listed class"
        if class_ref == individual.class_ref:
            return f"item {number}: retyped to its own class"
        return index, PreReviewVerdict(answer, question, class_ref=class_ref, **common)
    if not split_witness(individual.mention.name):
        return f"item {number}: not marked as a list"
    parts = []
    for part in review.get("parts") or ():
        if not isinstance(part, dict):
            continue
        title = str(part.get("title") or "").strip()
        class_ref = class_refs.get(str(part.get("class") or "").strip().lower())
        if not title or class_ref is None:
            continue
        quote = part.get("quote")
        span = resolve_span(
            quote if isinstance(quote, str) and quote.strip() else None, None, None, text
        )
        parts.append(PreReviewPart(title, class_ref, span.quote))
    if len(parts) < 2:
        return f"item {number}: a split needs two parts with a title and a listed class"
    return index, PreReviewVerdict(answer, question, parts=tuple(parts), **common)
