"""Unit tests for anchored text edits (#1630)."""

import pytest

from domain.versioning.text_edits import (
    ANCHOR_NOT_FOUND,
    ANCHOR_NOT_UNIQUE,
    TextEditError,
    apply_text_edits,
    parse_text_edits,
)

VISION = "- **Knowing who the house deals with:** contacts.\n- **Fixing things:** repairs.\n"


def test_insert_after_an_anchor():
    edits = [{"after": "contacts.\n", "insert": "- **Buying where it's in stock:** stores.\n"}]
    assert apply_text_edits(VISION, edits) == (
        "- **Knowing who the house deals with:** contacts.\n"
        "- **Buying where it's in stock:** stores.\n"
        "- **Fixing things:** repairs.\n"
    )


def test_replace_and_delete():
    edits = [{"replace": "repairs", "with": "repairs and upkeep"}, {"delete": "contacts."}]
    assert apply_text_edits(VISION, edits) == (
        "- **Knowing who the house deals with:** \n- **Fixing things:** repairs and upkeep.\n"
    )


def test_edits_apply_in_order_each_to_what_the_last_left():
    edits = [{"replace": "Fixing", "with": "Mending"}, {"after": "Mending", "insert": " and fixing"}]
    assert "Mending and fixing things" in apply_text_edits(VISION, edits)


def test_a_missing_anchor_names_the_edit():
    with pytest.raises(TextEditError) as raised:
        apply_text_edits(VISION, [{"delete": "repairs"}, {"delete": "gardening"}])
    assert raised.value.index == 1
    assert raised.value.code == ANCHOR_NOT_FOUND
    assert str(raised.value).startswith("edit 2: anchor 'gardening' is not in the text")


def test_an_anchor_that_appears_twice_is_refused():
    with pytest.raises(TextEditError) as raised:
        apply_text_edits(VISION, [{"after": "- **", "insert": "x"}])
    assert raised.value.code == ANCHOR_NOT_UNIQUE
    assert "appears 2 times" in str(raised.value)


def test_no_text_has_no_anchors():
    with pytest.raises(TextEditError) as raised:
        apply_text_edits(None, [{"delete": "x"}])
    assert raised.value.code == ANCHOR_NOT_FOUND


@pytest.mark.parametrize(
    "value",
    [
        "a whole value",
        {"edits": []},
        {"edits": [{"after": "x"}]},
        {"edits": [{"replace": "x", "insert": "y"}]},
        {"edits": [{"delete": ""}]},
        {"edits": [{"delete": 3}]},
        {"edits": [{"delete": "x"}], "extra": 1},
    ],
)
def test_malformed_edits_are_refused(value):
    with pytest.raises(TextEditError) as raised:
        parse_text_edits(value)
    assert raised.value.code is None


def test_parse_returns_the_edits():
    edits = [{"after": "a", "insert": "b"}, {"replace": "c", "with": ""}, {"delete": "d"}]
    assert parse_text_edits({"edits": edits}) == edits
