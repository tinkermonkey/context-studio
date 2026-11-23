"""
Unit tests for the pre-review stage's free parts: the split witness, and the
verdict's rules.

The witness marks a title that reads as a list, so the split question is
asked of it; it must mark all four items the person split by hand in Gate D.
A verdict changes an individual only by a split into two or more parts or a
retype to another class, and says what it changed from.
"""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
)

import pytest

from domain.extraction.entities import (
    PreReviewAnswer,
    PreReviewPart,
    PreReviewQuestion,
    PreReviewVerdict,
)
from domain.extraction.pre_review import split_witness

GATE_D_SPLITS = [
    "Torx T20, T25",
    "Copper water supply kits WX8X2, WX8X3, WX8X4",
    "Straight and Phillips blade screwdriver",
    "Compression nut and ferrule",
]


@pytest.mark.parametrize("title", GATE_D_SPLITS)
def test_the_witness_marks_every_split_from_gate_d(title):
    assert split_witness(title)


@pytest.mark.parametrize(
    "title",
    [
        "Ice maker & water filter",
        "Bolts + washers",
        "GNU/Linux",
        "Newcomers and Junior Contributors",
    ],
)
def test_the_witness_marks_any_list_shaped_title(title):
    # It decides where to ask, not the answer: "GNU/Linux" is one item
    assert split_witness(title)


@pytest.mark.parametrize(
    "title",
    ["Edit Check", "Reference Check", "Sandy Brand", "GitLab Workhorse", "1,000 edits", "", "Q&A"],
)
def test_the_witness_leaves_a_single_name_alone(title):
    assert not split_witness(title)


def _verdict(answer, **fields):
    defaults = {
        "question": PreReviewQuestion.RETYPE,
        "reasoning": "because",
        "original_title": "Torx T20, T25",
        "original_class_ref": "house.supply",
    }
    return PreReviewVerdict(answer, **{**defaults, **fields})


def test_a_retype_names_another_class_and_is_a_change():
    verdict = _verdict(PreReviewAnswer.RETYPE, class_ref="house.tool")
    assert verdict.changes
    assert verdict.class_ref == "house.tool"


@pytest.mark.parametrize("class_ref", [None, "house.supply"])
def test_a_retype_without_another_class_is_refused(class_ref):
    with pytest.raises(ValueError, match="other than the original"):
        _verdict(PreReviewAnswer.RETYPE, class_ref=class_ref)


def test_a_split_has_at_least_two_parts():
    parts = (PreReviewPart("Torx T20", "house.tool"), PreReviewPart("Torx T25", "house.tool"))
    verdict = _verdict(PreReviewAnswer.SPLIT, question=PreReviewQuestion.SPLIT, parts=parts)
    assert verdict.changes
    with pytest.raises(ValueError, match="at least two parts"):
        _verdict(PreReviewAnswer.SPLIT, question=PreReviewQuestion.SPLIT, parts=parts[:1])


@pytest.mark.parametrize("answer", [PreReviewAnswer.KEEP, PreReviewAnswer.UNSURE])
def test_keep_and_unsure_change_nothing(answer):
    verdict = _verdict(answer, question=None)
    assert not verdict.changes
    with pytest.raises(ValueError, match="Only a split has parts"):
        _verdict(answer, parts=(PreReviewPart("a", "x"), PreReviewPart("b", "x")))
    with pytest.raises(ValueError, match="Only a retype names a class"):
        _verdict(answer, class_ref="house.tool")


# ---------------------------------------------------------------- the stage's call

import json  # noqa: E402

from domain.extraction.entities import FoundIndividual, Mention  # noqa: E402
from domain.extraction.find_then_type import CatalogClass  # noqa: E402
from domain.extraction.pre_review import (  # noqa: E402
    LIST_MARK,
    PRE_REVIEW_MAX_TOKENS,
    parse_reviews,
    render_items,
    review_individuals,
)
from domain.extraction.prompts import PRE_REVIEW_STAGE  # noqa: E402
from domain.extraction.single_call import build_catalog  # noqa: E402
from domain.pipelines.ports import LLMResponse  # noqa: E402

CLASSES = [
    CatalogClass(
        "tech.tool", "Tool", "Technology", "A hand tool. Use Supply instead when used up."
    ),
    CatalogClass("tech.supply", "Supply", "Technology", "Something used up."),
    CatalogClass("biz.role", "Role", "Business", "A role people play."),
]
TEXT = "Remove the panel with a Torx T20 and a Torx T25. Junior Contributors join first."
INDIVIDUALS = [
    FoundIndividual(Mention("Torx T20, T25", "thing", "Torx T20 and a Torx T25"), "tech.supply"),
    FoundIndividual(Mention("Junior Contributors", "thing", "Junior Contributors"), "biz.role"),
]


class _LLM:
    """Answers each call with the next of ``answers``, recording the requests."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.requests: list[dict] = []

    def complete(self, **request):
        self.requests.append(request)
        return LLMResponse(self.answers.pop(0), 100, 50, 1.0, "end_turn", request["model"])

    def forget(self, **request):
        pass


def _review(llm, **kwargs):
    catalog, refs = build_catalog("Toy", CLASSES)
    return review_individuals(
        llm,
        lambda _: None,
        TEXT,
        INDIVIDUALS,
        catalog,
        refs,
        "claude-haiku-5-5",
        0.0,
        PRE_REVIEW_STAGE.default,
        **kwargs,
    )


def _refs():
    return build_catalog("Toy", CLASSES)[1]


def test_the_list_numbers_each_individual_and_marks_where_split_is_asked():
    lines = render_items(INDIVIDUALS, {"split", "retype"}).splitlines()
    assert lines[0] == f'1. Torx T20, T25 | tech.supply | "Torx T20 and a Torx T25" {LIST_MARK}'
    assert lines[1] == '2. Junior Contributors | biz.role | "Junior Contributors"'
    assert LIST_MARK not in render_items(INDIVIDUALS, {"retype"})


def test_the_call_carries_the_catalog_text_and_list():
    llm = _LLM('{"reviews": []}')
    result = _review(llm, effort="medium")
    request = llm.requests[0]
    assert "tech.tool (Tool): A hand tool." in request["system_prompt"]
    assert TEXT in request["user_prompt"] and "1. Torx T20, T25" in request["user_prompt"]
    assert request["max_tokens"] == PRE_REVIEW_MAX_TOKENS and request["effort"] == "medium"
    assert result.verdicts == {} and result.failure_reason is None
    assert result.metadata["tokens_used"] == 150


def test_a_split_and_a_retype_are_read_with_their_reasoning():
    answer = {
        "reviews": [
            {
                "item": 1,
                "answer": "split",
                "reasoning": "Two drivers.",
                "parts": [
                    {"title": "Torx T20", "class": "tech.tool", "quote": "Torx T20"},
                    {"title": "Torx T25", "class": "TECH.TOOL", "quote": "not in the text"},
                ],
            },
            {
                "item": 2,
                "answer": "retype",
                "reasoning": "x",
                "class": "tech.tool",
                "compared": ["biz.role", "tech.tool", "nope"],
            },
        ]
    }
    result = _review(_LLM(json.dumps(answer)))
    split, retype = result.verdicts[0], result.verdicts[1]
    assert split.answer is PreReviewAnswer.SPLIT and split.reasoning == "Two drivers."
    assert [(p.title, p.class_ref) for p in split.parts] == [
        ("Torx T20", "tech.tool"),
        ("Torx T25", "tech.tool"),
    ]
    assert split.parts[0].quote == "Torx T20" and split.parts[1].quote is None
    assert split.original_class_ref == "tech.supply"
    assert retype.class_ref == "tech.tool" and retype.compared == ("biz.role", "tech.tool")
    assert result.warnings == ["The quote of 1 split parts was not found in the text"]


@pytest.mark.parametrize(
    "review, why",
    [
        ({"item": 9, "answer": "retype", "class": "tech.tool"}, "not listed"),
        ({"item": 2, "answer": "retype", "class": "tech.drill"}, "not a listed class"),
        ({"item": 2, "answer": "retype", "class": "biz.role"}, "its own class"),
        ({"item": 2, "answer": "maybe"}, "not an answer"),
        (
            {"item": 2, "answer": "split", "parts": [{"title": "a", "class": "biz.role"}] * 2},
            "not marked as a list",
        ),
        (
            {"item": 1, "answer": "split", "parts": [{"title": "a", "class": "tech.tool"}]},
            "two parts",
        ),
    ],
)
def test_an_unusable_answer_is_left_out_and_its_individual_kept(review, why):
    verdicts, warnings = parse_reviews(
        json.dumps({"reviews": [review]}), TEXT, INDIVIDUALS, _refs()
    )
    assert verdicts == {}
    assert why in warnings[0]


def test_keep_needs_no_entry_and_unsure_asks_the_reviewer():
    answer = {
        "reviews": [
            {"item": 1, "answer": "keep"},
            {"item": 2, "answer": "unsure", "reasoning": "A role or a group?"},
        ]
    }
    verdicts, warnings = parse_reviews(json.dumps(answer), TEXT, INDIVIDUALS, _refs())
    assert list(verdicts) == [1] and verdicts[1].answer is PreReviewAnswer.UNSURE
    assert verdicts[1].reasoning == "A role or a group?" and warnings == []


def test_an_answer_to_a_question_not_asked_is_left_out():
    answer = {"reviews": [{"item": 2, "answer": "retype", "class": "tech.tool"}]}
    verdicts, warnings = parse_reviews(
        json.dumps(answer), TEXT, INDIVIDUALS, _refs(), questions={"split"}
    )
    assert verdicts == {} and "retype is not asked" in warnings[0]


def test_an_answer_with_no_reviews_list_is_asked_again_then_fails_without_changing_anything():
    result = _review(_LLM("{}", "not json", '{"answers": []}'))
    assert result.verdicts == {}
    assert result.incomplete_response and "no reviews list" in result.failure_reason


def test_no_individuals_means_no_call():
    llm = _LLM()
    catalog, refs = build_catalog("Toy", CLASSES)
    result = review_individuals(
        llm, lambda _: None, TEXT, [], catalog, refs, "m", 0.0, PRE_REVIEW_STAGE.default
    )
    assert result.verdicts == {} and llm.requests == []
