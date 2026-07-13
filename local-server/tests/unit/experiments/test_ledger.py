"""
Unit tests for the Karpathy-loop experiment ledger (experiments/ledger.py).

Covers the read/write helpers plus the CLI entry point, using a temporary
ledger file for every test so nothing touches the real, tracked
`experiments/ledger.jsonl`.
"""

import json
import logging
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from experiments.ledger import (
    BASELINE_RESET_DECISION,
    LedgerEntryError,
    accepted_hypotheses,
    append_baseline_reset,
    append_entry,
    entries_since_last_baseline_reset,
    latest_baseline_reset,
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

    @pytest.mark.parametrize(
        "missing_field",
        [
            "experiment_id",
            "iteration",
            "hypothesis",
            "variant",
            "diff_stat",
            "base_commit",
            "dev",
            "holdout",
            "decision",
            "reason",
            "cost_usd",
            "agent",
        ],
    )
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

    def test_entry_with_optional_bootstrap_diagnostics_is_valid(self):
        # bootstrap (karpathy_loop_dr_ontology_design.md §5) is logged for
        # visibility only -- not in REQUIRED_FIELDS, so its presence or
        # content never affects validation.
        validate_entry(_entry(bootstrap={"strict_f1": 0.0, "soft_f1": 0.0}))


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

    def test_corrupted_line_is_skipped_with_warning(self, tmp_path, caplog):
        ledger_path = tmp_path / "ledger.jsonl"
        append_entry(_entry(experiment_id="1-a"), ledger_path=ledger_path)
        with open(ledger_path, "a") as f:
            f.write('{"experiment_id": "1-b", "decision": "rejected"\n')  # truncated/corrupted line
        append_entry(_entry(experiment_id="1-c"), ledger_path=ledger_path)

        # Scope the level to the ledger logger, not just root: get_logger()
        # raises that logger's own level to its file handler's once a handler is
        # attached (which other tests trigger in a full-suite run), which would
        # otherwise drop the WARNING before it reaches caplog.
        with caplog.at_level(logging.WARNING, logger="experiments.ledger"):
            entries = read_entries(ledger_path)

        assert "corrupted ledger line" in caplog.text
        assert [e["experiment_id"] for e in entries] == ["1-a", "1-c"]

    def test_all_corrupted_lines_returns_empty_list(self, tmp_path, caplog):
        ledger_path = tmp_path / "ledger.jsonl"
        ledger_path.write_text('{"not": "closed"\n{"also": "broken"\n')

        with caplog.at_level(logging.WARNING, logger="experiments.ledger"):
            assert read_entries(ledger_path) == []
        assert "corrupted ledger line" in caplog.text

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
        append_entry(
            _entry(experiment_id="1-a", hypothesis="a", decision="rejected"),
            ledger_path=ledger_path,
        )
        append_entry(
            _entry(experiment_id="1-b", hypothesis="b", decision="accepted"),
            ledger_path=ledger_path,
        )
        append_entry(
            _entry(experiment_id="1-c", hypothesis="c", decision="rejected"),
            ledger_path=ledger_path,
        )

        assert rejected_hypotheses(ledger_path) == ["a", "c"]

    def test_duplicate_rejected_hypothesis_appears_once_in_first_seen_order(self, tmp_path):
        ledger_path = tmp_path / "ledger.jsonl"
        append_entry(
            _entry(experiment_id="1-a", hypothesis="a", decision="rejected"),
            ledger_path=ledger_path,
        )
        append_entry(
            _entry(experiment_id="2-a", hypothesis="a", decision="rejected"),
            ledger_path=ledger_path,
        )
        append_entry(
            _entry(experiment_id="1-b", hypothesis="b", decision="rejected"),
            ledger_path=ledger_path,
        )

        assert rejected_hypotheses(ledger_path) == ["a", "b"]

    def test_hypothesis_accepted_after_earlier_rejection_still_counts_as_rejected(self, tmp_path):
        # The ledger is a record of every experiment, not a per-hypothesis
        # final verdict — a hypothesis rejected once still shows up here even
        # if a later, materially different experiment on it was accepted.
        # Target selection deciding whether to retry it is a judgment call
        # made by the loop's driver, not this module.
        ledger_path = tmp_path / "ledger.jsonl"
        append_entry(
            _entry(experiment_id="1-a", hypothesis="a", decision="rejected"),
            ledger_path=ledger_path,
        )
        append_entry(
            _entry(experiment_id="2-a", hypothesis="a", decision="accepted"),
            ledger_path=ledger_path,
        )

        assert rejected_hypotheses(ledger_path) == ["a"]


class TestAcceptedHypotheses:
    def test_empty_ledger_returns_empty_list(self, tmp_path):
        assert accepted_hypotheses(tmp_path / "ledger.jsonl") == []

    def test_only_accepted_entries_are_returned(self, tmp_path):
        ledger_path = tmp_path / "ledger.jsonl"
        append_entry(
            _entry(experiment_id="1-a", hypothesis="a", decision="accepted"),
            ledger_path=ledger_path,
        )
        append_entry(
            _entry(experiment_id="1-b", hypothesis="b", decision="rejected"),
            ledger_path=ledger_path,
        )
        append_entry(
            _entry(experiment_id="1-c", hypothesis="c", decision="accepted"),
            ledger_path=ledger_path,
        )

        assert accepted_hypotheses(ledger_path) == ["a", "c"]

    def test_duplicate_accepted_hypothesis_appears_once_in_first_seen_order(self, tmp_path):
        ledger_path = tmp_path / "ledger.jsonl"
        append_entry(
            _entry(experiment_id="1-a", hypothesis="a", decision="accepted"),
            ledger_path=ledger_path,
        )
        append_entry(
            _entry(experiment_id="2-a", hypothesis="a", decision="accepted"),
            ledger_path=ledger_path,
        )
        append_entry(
            _entry(experiment_id="1-b", hypothesis="b", decision="accepted"),
            ledger_path=ledger_path,
        )

        assert accepted_hypotheses(ledger_path) == ["a", "b"]

    def test_acceptance_before_reset_is_excluded(self, tmp_path):
        # An accepted hypothesis merged into an incumbent that a baseline
        # reset has since retired is retryable again, so it must not linger
        # in the accepted set past the reset.
        ledger_path = tmp_path / "ledger.jsonl"
        append_entry(
            _entry(experiment_id="1-a", hypothesis="a", decision="accepted"),
            ledger_path=ledger_path,
        )
        append_baseline_reset(
            reason="ontology swap",
            ontology_context="dr_spec",
            ledger_path=ledger_path,
        )

        assert accepted_hypotheses(ledger_path) == []


class TestAppendBaselineReset:
    def test_appends_entry_with_baseline_reset_decision(self, tmp_path):
        ledger_path = tmp_path / "ledger.jsonl"

        entry = append_baseline_reset(
            reason="DR ontology import replaces the placeholder ontology.",
            ontology_context="dr_spec",
            spec_version="0.8.4",
            base_commit="abc123",
            ledger_path=ledger_path,
        )

        assert entry["decision"] == BASELINE_RESET_DECISION
        assert entry["ontology_context"] == "dr_spec"
        assert entry["spec_version"] == "0.8.4"
        assert entry["base_commit"] == "abc123"
        assert read_entries(ledger_path) == [entry]

    def test_appended_entry_satisfies_validate_entry(self, tmp_path):
        ledger_path = tmp_path / "ledger.jsonl"
        append_baseline_reset(reason="reset", ontology_context="dr_spec", ledger_path=ledger_path)
        # append_entry (called internally) already validates; re-reading and
        # re-validating guards against the shape drifting out of sync.
        [entry] = read_entries(ledger_path)
        validate_entry(entry)

    def test_spec_version_defaults_to_none(self, tmp_path):
        ledger_path = tmp_path / "ledger.jsonl"
        entry = append_baseline_reset(
            reason="reset", ontology_context="placeholder", ledger_path=ledger_path
        )
        assert entry["spec_version"] is None


class TestEntriesSinceLastBaselineReset:
    def test_no_reset_returns_all_entries(self, tmp_path):
        ledger_path = tmp_path / "ledger.jsonl"
        append_entry(_entry(experiment_id="1-a"), ledger_path=ledger_path)
        append_entry(_entry(experiment_id="1-b"), ledger_path=ledger_path)

        entries = entries_since_last_baseline_reset(ledger_path)

        assert [e["experiment_id"] for e in entries] == ["1-a", "1-b"]

    def test_excludes_entries_before_the_reset(self, tmp_path):
        ledger_path = tmp_path / "ledger.jsonl"
        append_entry(_entry(experiment_id="1-a", hypothesis="a"), ledger_path=ledger_path)
        append_baseline_reset(reason="reset", ontology_context="dr_spec", ledger_path=ledger_path)
        append_entry(_entry(experiment_id="2-a", hypothesis="a"), ledger_path=ledger_path)

        entries = entries_since_last_baseline_reset(ledger_path)

        assert [e.get("experiment_id") for e in entries] == ["2-a"]

    def test_uses_only_the_most_recent_reset(self, tmp_path):
        ledger_path = tmp_path / "ledger.jsonl"
        append_entry(_entry(experiment_id="1-a"), ledger_path=ledger_path)
        append_baseline_reset(
            reason="first reset", ontology_context="dr_spec", ledger_path=ledger_path
        )
        append_entry(_entry(experiment_id="2-a"), ledger_path=ledger_path)
        append_baseline_reset(
            reason="second reset", ontology_context="dr_spec_v2", ledger_path=ledger_path
        )
        append_entry(_entry(experiment_id="3-a"), ledger_path=ledger_path)

        entries = entries_since_last_baseline_reset(ledger_path)

        assert [e.get("experiment_id") for e in entries] == ["3-a"]

    def test_empty_ledger_returns_empty_list(self, tmp_path):
        assert entries_since_last_baseline_reset(tmp_path / "ledger.jsonl") == []


class TestLatestBaselineReset:
    def test_no_reset_returns_none(self, tmp_path):
        ledger_path = tmp_path / "ledger.jsonl"
        append_entry(_entry(), ledger_path=ledger_path)
        assert latest_baseline_reset(ledger_path=ledger_path) is None

    def test_returns_the_most_recent_reset(self, tmp_path):
        ledger_path = tmp_path / "ledger.jsonl"
        append_baseline_reset(
            reason="first",
            ontology_context="dr_spec",
            spec_version="0.8.4",
            ledger_path=ledger_path,
        )
        append_baseline_reset(
            reason="second",
            ontology_context="dr_spec",
            spec_version="0.9.0",
            ledger_path=ledger_path,
        )

        latest = latest_baseline_reset(ledger_path=ledger_path)

        assert latest["spec_version"] == "0.9.0"

    def test_filters_by_ontology_context(self, tmp_path):
        ledger_path = tmp_path / "ledger.jsonl"
        append_baseline_reset(
            reason="placeholder reset", ontology_context="placeholder", ledger_path=ledger_path
        )
        append_baseline_reset(
            reason="dr reset",
            ontology_context="dr_spec",
            spec_version="0.8.4",
            ledger_path=ledger_path,
        )

        assert (
            latest_baseline_reset(ontology_context="placeholder", ledger_path=ledger_path)[
                "ontology_context"
            ]
            == "placeholder"
        )
        assert (
            latest_baseline_reset(ontology_context="dr_spec", ledger_path=ledger_path)[
                "spec_version"
            ]
            == "0.8.4"
        )
        assert (
            latest_baseline_reset(ontology_context="nonexistent", ledger_path=ledger_path) is None
        )


class TestRejectedHypothesesScopedToBaselineReset:
    def test_rejection_before_reset_is_excluded(self, tmp_path):
        ledger_path = tmp_path / "ledger.jsonl"
        append_entry(
            _entry(experiment_id="1-a", hypothesis="a", decision="rejected"),
            ledger_path=ledger_path,
        )
        append_baseline_reset(reason="reset", ontology_context="dr_spec", ledger_path=ledger_path)

        assert rejected_hypotheses(ledger_path) == []

    def test_rejection_after_reset_is_included(self, tmp_path):
        ledger_path = tmp_path / "ledger.jsonl"
        append_entry(
            _entry(experiment_id="1-a", hypothesis="a", decision="rejected"),
            ledger_path=ledger_path,
        )
        append_baseline_reset(reason="reset", ontology_context="dr_spec", ledger_path=ledger_path)
        append_entry(
            _entry(experiment_id="2-b", hypothesis="b", decision="rejected"),
            ledger_path=ledger_path,
        )

        assert rejected_hypotheses(ledger_path) == ["b"]

    def test_same_hypothesis_rejected_before_and_after_reset_is_retryable_once(self, tmp_path):
        # "a" was rejected pre-reset (against the retired ontology) and again
        # post-reset -- only the post-reset rejection should count.
        ledger_path = tmp_path / "ledger.jsonl"
        append_entry(
            _entry(experiment_id="1-a", hypothesis="a", decision="rejected"),
            ledger_path=ledger_path,
        )
        append_baseline_reset(reason="reset", ontology_context="dr_spec", ledger_path=ledger_path)

        assert rejected_hypotheses(ledger_path) == []

        append_entry(
            _entry(experiment_id="2-a", hypothesis="a", decision="rejected"),
            ledger_path=ledger_path,
        )
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
        append_entry(
            _entry(experiment_id="1-a", hypothesis="a", decision="rejected"),
            ledger_path=ledger_path,
        )
        append_entry(
            _entry(experiment_id="1-b", hypothesis="b", decision="accepted"),
            ledger_path=ledger_path,
        )

        exit_code = ledger_cli(["--ledger-path", str(ledger_path), "rejected-hypotheses"])

        assert exit_code == 0
        assert capsys.readouterr().out.splitlines() == ["a"]

    def test_rejected_hypotheses_command_empty_ledger_prints_nothing(self, tmp_path, capsys):
        ledger_path = tmp_path / "ledger.jsonl"

        exit_code = ledger_cli(["--ledger-path", str(ledger_path), "rejected-hypotheses"])

        assert exit_code == 0
        assert capsys.readouterr().out == ""

    def test_accepted_hypotheses_command_prints_one_per_line(self, tmp_path, capsys):
        ledger_path = tmp_path / "ledger.jsonl"
        append_entry(
            _entry(experiment_id="1-a", hypothesis="a", decision="accepted"),
            ledger_path=ledger_path,
        )
        append_entry(
            _entry(experiment_id="1-b", hypothesis="b", decision="rejected"),
            ledger_path=ledger_path,
        )

        exit_code = ledger_cli(["--ledger-path", str(ledger_path), "accepted-hypotheses"])

        assert exit_code == 0
        assert capsys.readouterr().out.splitlines() == ["a"]

    def test_accepted_hypotheses_command_empty_ledger_prints_nothing(self, tmp_path, capsys):
        ledger_path = tmp_path / "ledger.jsonl"

        exit_code = ledger_cli(["--ledger-path", str(ledger_path), "accepted-hypotheses"])

        assert exit_code == 0
        assert capsys.readouterr().out == ""

    def test_baseline_reset_command_writes_entry(self, tmp_path, capsys):
        ledger_path = tmp_path / "ledger.jsonl"

        exit_code = ledger_cli(
            [
                "--ledger-path",
                str(ledger_path),
                "baseline-reset",
                "--ontology-context",
                "dr_spec",
                "--spec-version",
                "0.8.4",
                "--base-commit",
                "abc123",
                "Replaced the placeholder ontology with the DR spec.",
            ]
        )

        assert exit_code == 0
        [entry] = read_entries(ledger_path)
        assert entry["decision"] == BASELINE_RESET_DECISION
        assert entry["ontology_context"] == "dr_spec"
        assert entry["spec_version"] == "0.8.4"
        assert entry["base_commit"] == "abc123"
        assert "appended baseline-reset checkpoint" in capsys.readouterr().out

    def test_baseline_reset_command_reads_reason_from_stdin(self, tmp_path, capsys, monkeypatch):
        import io

        ledger_path = tmp_path / "ledger.jsonl"
        monkeypatch.setattr(sys, "stdin", io.StringIO("free-form reason with a $var and 'quotes'"))

        exit_code = ledger_cli(
            [
                "--ledger-path",
                str(ledger_path),
                "baseline-reset",
                "--ontology-context",
                "dr_spec",
                "--stdin",
            ]
        )

        assert exit_code == 0
        [entry] = read_entries(ledger_path)
        assert entry["reason"] == "free-form reason with a $var and 'quotes'"

    def test_baseline_reset_command_rejects_both_reason_and_stdin(self, tmp_path, capsys):
        ledger_path = tmp_path / "ledger.jsonl"

        exit_code = ledger_cli(
            [
                "--ledger-path",
                str(ledger_path),
                "baseline-reset",
                "--ontology-context",
                "dr_spec",
                "--stdin",
                "reason",
            ]
        )

        assert exit_code == 1
        assert not ledger_path.exists()
        assert "ERROR" in capsys.readouterr().err

    def test_baseline_reset_command_requires_reason_or_stdin(self, tmp_path, capsys):
        ledger_path = tmp_path / "ledger.jsonl"

        exit_code = ledger_cli(
            ["--ledger-path", str(ledger_path), "baseline-reset", "--ontology-context", "dr_spec"]
        )

        assert exit_code == 1
        assert not ledger_path.exists()
        assert "ERROR" in capsys.readouterr().err
