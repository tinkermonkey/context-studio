"""
Unit tests for the Karpathy-loop experiment ledger (experiments/ledger.py).

Covers the read/write helpers plus the CLI entry point, using a temporary
ledger file for every test so nothing touches the real, tracked
`experiments/ledger.jsonl`.
"""

import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from experiments.ledger import (
    LedgerEntryError,
    append_entry,
    read_entries,
    rejected_hypotheses,
    validate_entry,
)
from experiments.ledger import _main as ledger_cli


def _entry(**overrides):
    """A minimally valid ledger entry (karpathy_loop_design.md §8 shape), with overrides applied."""
    base = {
        "experiment_id": "1-copular_appositive_handling",
        "iteration": 1,
        "hypothesis": "copular_appositive_handling",
        "variant": "open_v1+copular",
        "diff_stat": "1 file changed, 20 insertions(+)",
        "base_commit": "abc123",
        "dev": {"strict_f1": 0.31, "soft_f1": 0.52, "candidate_recall": 0.71},
        "holdout": {"strict_f1": 0.28, "soft_f1": 0.47},
        "decision": "accepted",
        "reason": "",
        "cost_usd": 0.11,
        "agent": "worktree-2",
    }
    base.update(overrides)
    return base


class TestValidateEntry:
    def test_valid_entry_passes(self):
        validate_entry(_entry())

    @pytest.mark.parametrize("missing_field", [
        "experiment_id", "iteration", "hypothesis", "variant", "diff_stat",
        "base_commit", "dev", "holdout", "decision", "reason", "cost_usd", "agent",
    ])
    def test_missing_required_field_raises(self, missing_field):
        entry = _entry()
        del entry[missing_field]
        with pytest.raises(LedgerEntryError, match=missing_field):
            validate_entry(entry)

    def test_invalid_decision_raises(self):
        entry = _entry(decision="maybe")
        with pytest.raises(LedgerEntryError, match="decision"):
            validate_entry(entry)

    def test_rejected_decision_is_valid(self):
        validate_entry(_entry(decision="rejected"))


class TestAppendAndReadEntries:
    def test_read_entries_missing_file_returns_empty_list(self, tmp_path):
        assert read_entries(tmp_path / "does_not_exist.jsonl") == []

    def test_append_then_read_round_trips(self, tmp_path):
        ledger_path = tmp_path / "ledger.jsonl"
        entry = _entry()

        append_entry(entry, ledger_path=ledger_path)

        entries = read_entries(ledger_path)
        assert entries == [entry]

    def test_append_is_append_only_and_preserves_order(self, tmp_path):
        ledger_path = tmp_path / "ledger.jsonl"
        first = _entry(experiment_id="1-a", hypothesis="a", decision="rejected")
        second = _entry(experiment_id="1-b", hypothesis="b", decision="accepted")

        append_entry(first, ledger_path=ledger_path)
        append_entry(second, ledger_path=ledger_path)

        entries = read_entries(ledger_path)
        assert [e["experiment_id"] for e in entries] == ["1-a", "1-b"]

    def test_append_writes_one_json_line_per_entry(self, tmp_path):
        ledger_path = tmp_path / "ledger.jsonl"
        append_entry(_entry(experiment_id="1-a"), ledger_path=ledger_path)
        append_entry(_entry(experiment_id="1-b"), ledger_path=ledger_path)

        lines = ledger_path.read_text().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["experiment_id"] == "1-a"
        assert json.loads(lines[1])["experiment_id"] == "1-b"

    def test_append_creates_parent_directories(self, tmp_path):
        ledger_path = tmp_path / "nested" / "dir" / "ledger.jsonl"
        append_entry(_entry(), ledger_path=ledger_path)
        assert ledger_path.exists()

    def test_append_rejects_invalid_entry_without_writing(self, tmp_path):
        ledger_path = tmp_path / "ledger.jsonl"
        entry = _entry()
        del entry["decision"]

        with pytest.raises(LedgerEntryError):
            append_entry(entry, ledger_path=ledger_path)

        assert not ledger_path.exists()


class TestRejectedHypotheses:
    def test_empty_ledger_returns_empty_list(self, tmp_path):
        assert rejected_hypotheses(tmp_path / "ledger.jsonl") == []

    def test_only_rejected_entries_are_returned(self, tmp_path):
        ledger_path = tmp_path / "ledger.jsonl"
        append_entry(_entry(experiment_id="1-a", hypothesis="a", decision="rejected"), ledger_path=ledger_path)
        append_entry(_entry(experiment_id="1-b", hypothesis="b", decision="accepted"), ledger_path=ledger_path)
        append_entry(_entry(experiment_id="1-c", hypothesis="c", decision="rejected"), ledger_path=ledger_path)

        assert rejected_hypotheses(ledger_path) == ["a", "c"]

    def test_duplicate_rejected_hypothesis_appears_once_in_first_seen_order(self, tmp_path):
        ledger_path = tmp_path / "ledger.jsonl"
        append_entry(_entry(experiment_id="1-a", hypothesis="a", decision="rejected"), ledger_path=ledger_path)
        append_entry(_entry(experiment_id="2-a", hypothesis="a", decision="rejected"), ledger_path=ledger_path)
        append_entry(_entry(experiment_id="1-b", hypothesis="b", decision="rejected"), ledger_path=ledger_path)

        assert rejected_hypotheses(ledger_path) == ["a", "b"]

    def test_hypothesis_accepted_after_earlier_rejection_still_counts_as_rejected(self, tmp_path):
        # The ledger is a record of every experiment, not a per-hypothesis
        # final verdict — a hypothesis rejected once still shows up here even
        # if a later, materially different experiment on it was accepted.
        # Target selection deciding whether to retry it is a judgment call
        # made by the loop's driver, not this module.
        ledger_path = tmp_path / "ledger.jsonl"
        append_entry(_entry(experiment_id="1-a", hypothesis="a", decision="rejected"), ledger_path=ledger_path)
        append_entry(_entry(experiment_id="2-a", hypothesis="a", decision="accepted"), ledger_path=ledger_path)

        assert rejected_hypotheses(ledger_path) == ["a"]


class TestCli:
    def test_append_command_writes_entry(self, tmp_path, capsys):
        ledger_path = tmp_path / "ledger.jsonl"
        entry = _entry()

        exit_code = ledger_cli(["--ledger-path", str(ledger_path), "append", json.dumps(entry)])

        assert exit_code == 0
        assert read_entries(ledger_path) == [entry]
        assert "appended" in capsys.readouterr().out

    def test_append_command_rejects_invalid_json(self, tmp_path, capsys):
        ledger_path = tmp_path / "ledger.jsonl"

        exit_code = ledger_cli(["--ledger-path", str(ledger_path), "append", "{not json"])

        assert exit_code == 1
        assert not ledger_path.exists()
        assert "ERROR" in capsys.readouterr().err

    def test_append_command_rejects_invalid_entry(self, tmp_path, capsys):
        ledger_path = tmp_path / "ledger.jsonl"
        entry = _entry()
        del entry["decision"]

        exit_code = ledger_cli(["--ledger-path", str(ledger_path), "append", json.dumps(entry)])

        assert exit_code == 1
        assert not ledger_path.exists()
        assert "ERROR" in capsys.readouterr().err

    def test_rejected_hypotheses_command_prints_one_per_line(self, tmp_path, capsys):
        ledger_path = tmp_path / "ledger.jsonl"
        append_entry(_entry(experiment_id="1-a", hypothesis="a", decision="rejected"), ledger_path=ledger_path)
        append_entry(_entry(experiment_id="1-b", hypothesis="b", decision="accepted"), ledger_path=ledger_path)

        exit_code = ledger_cli(["--ledger-path", str(ledger_path), "rejected-hypotheses"])

        assert exit_code == 0
        assert capsys.readouterr().out.splitlines() == ["a"]

    def test_rejected_hypotheses_command_empty_ledger_prints_nothing(self, tmp_path, capsys):
        ledger_path = tmp_path / "ledger.jsonl"

        exit_code = ledger_cli(["--ledger-path", str(ledger_path), "rejected-hypotheses"])

        assert exit_code == 0
        assert capsys.readouterr().out == ""
