"""
Unit tests for experiment page metadata headers (experiments/page_metadata.py),
and a check that every page in documentation/extraction/experiments/ has one.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from experiments.page_metadata import (
    FIELDS,
    MetadataError,
    check,
    pages,
    render,
    split,
    validate,
    with_header,
)
from experiments.page_metadata import _main as metadata_cli

HEADER = {
    "date": "2026-11-15",
    "kind": "experiment",
    "implementations": ["find_then_type"],
    "models": ["claude-haiku-5-5", "claude-opus-5-5"],
    "takes": 3,
    "cost_usd": 6.01,
    "verdict": "open",
    "reproducible": "yes",
}


def test_every_experiment_page_in_the_repository_has_a_valid_header():
    assert pages(), "no experiment pages found"
    assert check() == []


def test_a_header_reads_back_as_written():
    header, body = split(render(HEADER) + "# Title\n\nText.\n")

    assert header == HEADER
    assert body == "# Title\n\nText.\n"


def test_with_header_replaces_an_existing_header_and_keeps_the_body():
    page = with_header("# Title\n", HEADER)
    changed = with_header(page, {**HEADER, "verdict": "adopted", "cost_usd": None})

    header, body = split(changed)
    assert header["verdict"] == "adopted" and header["cost_usd"] is None
    assert body == "# Title\n"
    assert changed.count("---\n") == 2


def test_a_page_without_a_header_has_none():
    assert split("# Title\n") == (None, "# Title\n")


@pytest.mark.parametrize(
    "change, problem",
    [
        ({"date": "15 Nov 2026"}, "YYYY-MM-DD"),
        ({"kind": "probe"}, "kind"),
        ({"verdict": "great"}, "verdict"),
        ({"reproducible": "maybe"}, "reproducible"),
        ({"models": "claude-haiku-5-5"}, "models"),
        ({"implementations": ["two words"]}, "implementations"),
        ({"takes": 0}, "takes"),
        ({"cost_usd": -1}, "cost_usd"),
    ],
)
def test_a_field_out_of_its_values_is_refused(change, problem):
    with pytest.raises(MetadataError, match=problem):
        validate({**HEADER, **change})


def test_a_missing_or_unknown_field_is_refused():
    with pytest.raises(MetadataError, match="missing"):
        validate({k: v for k, v in HEADER.items() if k != "verdict"})
    with pytest.raises(MetadataError, match="unknown"):
        validate({**HEADER, "owner": "someone"})


def test_check_names_each_page_with_a_problem(tmp_path):
    (tmp_path / "README.md").write_text("# Index\n")
    (tmp_path / "2026-11-15-good.md").write_text(with_header("# Good\n", HEADER))
    (tmp_path / "2026-11-15-bare.md").write_text("# Bare\n")
    (tmp_path / "2026-11-14-misdated.md").write_text(with_header("# Misdated\n", HEADER))

    problems = check(tmp_path)

    assert len(problems) == 2
    assert problems[0].startswith("2026-11-14-misdated.md: `date`")
    assert problems[1] == "2026-11-15-bare.md: the page has no metadata header"


def test_a_history_page_is_named_by_its_month(tmp_path):
    header = {**HEADER, "kind": "history", "date": "2026-05-08"}
    (tmp_path / "2026-05-to-09-history.md").write_text(with_header("# History\n", header))

    assert check(tmp_path) == []


def test_the_header_lists_fields_in_a_fixed_order():
    lines = render(HEADER).strip().split("\n")[1:-1]

    assert [line.split(":")[0] for line in lines] == list(FIELDS)


def test_cli_check_exits_1_on_a_bad_page(tmp_path, capsys):
    (tmp_path / "2026-11-15-bare.md").write_text("# Bare\n")

    assert metadata_cli(["check", "--dir", str(tmp_path)]) == 1
    assert "no metadata header" in capsys.readouterr().err
