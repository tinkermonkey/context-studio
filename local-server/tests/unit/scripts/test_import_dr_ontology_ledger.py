"""
Unit tests for scripts/import_dr_ontology.py's ledger-recording behavior.

Covers `record_baseline_reset_if_new` only — the pure DR-spec-transform logic
(`scripts.dr_ontology_loader.import_dr_ontology`) is exercised separately in
tests/integration/scripts/test_import_dr_ontology.py and tests/unit/scripts/
test_dr_ontology_loader.py. This module never touches the real
experiments/ledger.jsonl: every test passes an explicit tmp_path ledger.
"""

import os
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from experiments.ledger import read_entries
from scripts.dr_ontology_loader import ImportSummary
from scripts.import_dr_ontology import DR_ONTOLOGY_CONTEXT, record_baseline_reset_if_new


def _summary(spec_version="0.8.4"):
    return ImportSummary(
        spec_version=spec_version,
        taxonomies_created=1,
        concept_schemes_created=12,
        classes_created=186,
        property_definitions_created=1566,
    )


class TestRecordBaselineResetIfNew:
    def test_first_import_appends_checkpoint(self, tmp_path):
        ledger_path = tmp_path / "ledger.jsonl"

        appended = record_baseline_reset_if_new(
            _summary(), Path("/some/spec/dir"), ledger_path=ledger_path
        )

        assert appended is True
        [entry] = read_entries(ledger_path)
        assert entry["decision"] == "baseline_reset"
        assert entry["ontology_context"] == DR_ONTOLOGY_CONTEXT
        assert entry["spec_version"] == "0.8.4"
        assert "0.8.4" in entry["reason"]

    def test_reimport_of_same_spec_version_is_a_noop(self, tmp_path):
        ledger_path = tmp_path / "ledger.jsonl"
        record_baseline_reset_if_new(
            _summary("0.8.4"), Path("/some/spec/dir"), ledger_path=ledger_path
        )

        appended_again = record_baseline_reset_if_new(
            _summary("0.8.4"), Path("/some/spec/dir"), ledger_path=ledger_path
        )

        assert appended_again is False
        assert len(read_entries(ledger_path)) == 1

    def test_spec_version_bump_appends_a_new_checkpoint(self, tmp_path):
        ledger_path = tmp_path / "ledger.jsonl"
        record_baseline_reset_if_new(
            _summary("0.8.4"), Path("/some/spec/dir"), ledger_path=ledger_path
        )

        appended = record_baseline_reset_if_new(
            _summary("0.9.0"), Path("/some/spec/dir"), ledger_path=ledger_path
        )

        assert appended is True
        entries = read_entries(ledger_path)
        assert len(entries) == 2
        assert entries[-1]["spec_version"] == "0.9.0"

    def test_unrelated_ontology_context_does_not_suppress_the_checkpoint(self, tmp_path):
        from experiments.ledger import append_baseline_reset

        ledger_path = tmp_path / "ledger.jsonl"
        append_baseline_reset(
            reason="unrelated placeholder reset",
            ontology_context="placeholder",
            ledger_path=ledger_path,
        )

        appended = record_baseline_reset_if_new(
            _summary("0.8.4"), Path("/some/spec/dir"), ledger_path=ledger_path
        )

        assert appended is True
        entries = read_entries(ledger_path)
        assert len(entries) == 2
