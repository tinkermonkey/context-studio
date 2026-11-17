"""
Unit tests for the single call that finds and types a text's individuals.

The call is offered the ontology's whole catalog with full definitions by
kind, asks for the effort it is given, and reads an answer that lists
individuals with a class and a quote. A class the catalog does not list costs
that individual only; an answer with no individual it can use is not an
answer, so it is asked again and never read as "holds nothing".
"""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

import json

import pytest

from domain.extraction.exceptions import IncompleteLLMResponseError
from domain.extraction.find_then_type import CatalogClass
from domain.extraction.prompts import FIND_INDIVIDUALS, SINGLE_CALL_STAGES
from domain.extraction.single_call import (
    FIND_INDIVIDUALS_MAX_TOKENS,
    build_catalog,
    find_individuals,
    name_spans,
    parse_individuals,
)
from domain.pipelines.ports import LLMResponse
from domain.pipelines.stage_prompts import resolve_stage_prompts

PROMPT = resolve_stage_prompts(SINGLE_CALL_STAGES, None)[FIND_INDIVIDUALS]
CLASSES = [
    CatalogClass("motivation.goal", "Goal", "Motivation", "A high-level  aim.\nOf the subject."),
    CatalogClass("application.component", "Application Component", "Application", "A part."),
    CatalogClass("application.service", "Application Service", "Application", ""),
]
TEXT = "The Gateway serves requests. Our goal is to keep latency low."


class _LLM:
    """Answers each call with the next of ``answers``, recording the requests."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.requests: list[dict] = []
        self.forgotten = 0

    def complete(self, **request):
        self.requests.append(request)
        return LLMResponse(self.answers.pop(0), 100, 50, 1.0, "end_turn", request["model"])

    def forget(self, **request):
        self.forgotten += 1


def _answer(*individuals):
    return json.dumps(
        {"individuals": [dict(zip(("title", "class", "quote"), i)) for i in individuals]}
    )


def _call(llm, **kwargs):
    catalog, refs = build_catalog("DR", CLASSES)
    return find_individuals(
        llm, lambda _: None, TEXT, catalog, refs, "claude-opus-5-5", 0.0, PROMPT, **kwargs
    )


class TestCatalog:
    def test_classes_are_listed_by_reference_under_their_kind_with_whole_definitions(self):
        catalog, refs = build_catalog("DR", CLASSES)

        assert catalog == (
            "Ontology: DR\n\n# Classes\n\n## Application\n"
            "- application.component (Application Component): A part.\n"
            "- application.service (Application Service)\n\n## Motivation\n"
            "- motivation.goal (Goal): A high-level aim. Of the subject."
        )
        assert refs == {
            "motivation.goal": "motivation.goal",
            "application.component": "application.component",
            "application.service": "application.service",
        }

    def test_the_same_classes_in_another_order_give_the_same_catalog(self):
        assert build_catalog("DR", CLASSES) == build_catalog("DR", list(reversed(CLASSES)))


class TestTheCall:
    def test_it_sends_the_catalog_the_text_and_the_effort(self):
        llm = _LLM(_answer(("Gateway", "application.component", "The Gateway serves requests.")))

        result = _call(llm, effort="high", max_tokens=64000)

        request = llm.requests[0]
        assert (
            "## Motivation\n- motivation.goal (Goal): A high-level aim." in request["system_prompt"]
        )
        assert "<document>\n" + TEXT + "\n</document>" in request["user_prompt"]
        assert request["effort"] == "high"
        assert request["max_tokens"] == 64000
        assert result.failure_reason is None
        assert [(i.mention.name, i.class_ref) for i in result.individuals] == [
            ("Gateway", "application.component")
        ]
        assert result.metadata["tokens_used"] == 150

    def test_with_no_effort_or_limit_it_names_no_effort_and_its_own_limit(self):
        llm = _LLM(_answer())

        _call(llm)

        assert "effort" not in llm.requests[0]
        assert llm.requests[0]["max_tokens"] == FIND_INDIVIDUALS_MAX_TOKENS

    def test_an_answer_that_does_not_parse_is_asked_again(self):
        llm = _LLM("no json here", _answer(("Gateway", "application.component", "Gateway")))

        result = _call(llm, effort="high")

        assert len(llm.requests) == 2 and llm.forgotten == 1
        assert llm.requests[1]["effort"] == "high"
        assert [i.mention.name for i in result.individuals] == ["Gateway"]

    def test_a_text_never_answered_fails_and_lists_nothing(self):
        llm = _LLM("x", "x", "x")

        result = _call(llm)

        assert result.individuals == []
        assert result.incomplete_response
        assert "find_individuals" in result.failure_reason


class TestReadingTheAnswer:
    REFS = build_catalog("DR", CLASSES)[1]

    def test_quotes_are_placed_in_the_text(self):
        found, warnings = parse_individuals(
            _answer(("Keep latency low", "motivation.goal", "keep latency low")), TEXT, self.REFS
        )

        mention = found[0].mention
        assert (mention.quote, TEXT[mention.start : mention.end]) == (
            "keep latency low",
            "keep latency low",
        )
        assert warnings == []

    def test_a_class_is_read_whatever_its_case(self):
        found, _ = parse_individuals(
            _answer(("Gateway", "Application.Component", "")), TEXT, self.REFS
        )

        assert found[0].class_ref == "application.component"

    def test_an_unlisted_class_costs_that_individual_only(self):
        found, warnings = parse_individuals(
            _answer(("Gateway", "application.component", "Gateway"), ("X", "made.up", "")),
            TEXT,
            self.REFS,
        )

        assert [i.mention.name for i in found] == ["Gateway"]
        assert warnings == [
            "1 individuals named a class the ontology does not list and were left out (made.up)"
        ]

    def test_a_quote_that_is_not_in_the_text_leaves_no_passage(self):
        found, warnings = parse_individuals(
            _answer(("Gateway", "application.component", "nothing like this")), TEXT, self.REFS
        )

        assert found[0].mention.start is None
        assert warnings == ["The passage of 1 of 1 individuals was not found in the text"]

    def test_an_empty_list_is_an_answer(self):
        assert parse_individuals(_answer(), TEXT, self.REFS) == ([], [])

    @pytest.mark.parametrize(
        "content",
        [
            '{"items": []}',
            "not json",
            _answer(("X", "made.up", "")),
            _answer(("", "motivation.goal", "")),
        ],
    )
    def test_an_answer_with_nothing_usable_is_not_an_answer(self, content):
        with pytest.raises(IncompleteLLMResponseError):
            parse_individuals(content, TEXT, self.REFS)


class TestNameSpans:
    def test_a_name_is_found_as_a_whole_word_as_written(self):
        assert name_spans("Gate", "Gateway Gate gate (Gate).") == [(8, 12), (19, 23)]

    def test_a_blank_name_is_nowhere(self):
        assert name_spans("  ", "text") == []
