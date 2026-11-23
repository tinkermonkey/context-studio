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
