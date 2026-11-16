"""
The open_v1 canonicalization recorder (scripts/record_individual_canonicalization_cassettes.py)
records only when told to twice: with no flags it is a dry run that calls no
LLM, builds no ontology and writes nothing.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from scripts import record_individual_canonicalization_cassettes as recorder


@pytest.fixture
def recordings(monkeypatch):
    """Replace the recording itself: a test must never reach the live LLM."""
    started: list[bool] = []

    async def record() -> int:
        started.append(True)
        return 0

    monkeypatch.setattr(recorder, "_record", record)
    return started


@pytest.mark.parametrize("argv", [[], ["--dry-run"]])
def test_without_record_it_only_prints_the_plan(recordings, capsys, argv):
    assert recorder.main(argv) == 0
    out = capsys.readouterr().out

    assert recordings == []
    assert "DRY RUN" in out
    assert "--record --spend" in out
    assert "individual_canon_" in out
    # The model is the open_v1 configuration's, never a fixture's pinned one
    model = recorder._selection().parameters["model"]
    assert f"Model: {model}" in out
    assert "claude-opus-4-7" not in out


def test_record_without_spend_is_refused(recordings):
    with pytest.raises(SystemExit) as refused:
        recorder.main(["--record"])
    assert "--spend" in str(refused.value)
    assert recordings == []


def test_record_and_dry_run_together_are_refused(recordings):
    with pytest.raises(SystemExit):
        recorder.main(["--record", "--spend", "--dry-run"])
    assert recordings == []


def test_record_with_spend_records(recordings):
    assert recorder.main(["--record", "--spend"]) == 0
    assert recordings == [True]


def test_help_records_nothing(recordings):
    with pytest.raises(SystemExit) as shown:
        recorder.main(["--help"])
    assert shown.value.code == 0
    assert recordings == []
