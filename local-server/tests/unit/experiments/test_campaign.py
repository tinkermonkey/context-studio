"""
Unit tests for the record of a refinement-loop campaign (experiments/campaign.py).

Every test works on a copy of documentation/extraction/ and a temporary ledger,
so nothing touches the real pages or the tracked `experiments/ledger.jsonl`.
"""

import io
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from experiments.campaign import (
    SECTIONS,
    CampaignRecordError,
    page_name,
    record,
    replace_block,
)
from experiments.campaign import _main as campaign_cli
from experiments.ledger import (
    accepted_hypotheses,
    append_baseline_reset,
    read_entries,
    rejected_hypotheses,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
DOCS = REPO_ROOT / "documentation" / "extraction"
PAGE = "documentation/extraction/experiments/2026-11-16-loop-find_then_type.md"
PAGE_FILE = "2026-11-16-loop-find_then_type.md"


def _entry(iteration, hypothesis, decision, dev_typed=0.4712, **overrides):
    entry = {
        "experiment_id": f"{iteration}-find_then_type-{hypothesis}",
        "iteration": iteration,
        "implementation": "find_then_type",
        "configuration": "extraction-find-then-type",
        "model": "claude-haiku-5-5",
        "incumbent_model": "claude-haiku-5-5",
        "hypothesis": hypothesis,
        "variant": f"find_then_type+{hypothesis}",
        "diff_stat": "1 file changed",
        "base_commit": "73bf76c4abcdef",
        "dev": {"typed_f1": dev_typed, "f1": 0.54},
        "holdout": {"typed_f1": 0.47},
        "incumbent": {"dev": {"typed_f1": 0.4648, "f1": 0.5343}, "holdout": {"typed_f1": 0.4811}},
        "guard": {"applies": False, "reason": "no recordings"},
        "margins": {"epsilon": 0.03, "provisional": True},
        "other_targets": [],
        "other_guards": [],
        "decision": decision,
        "reason": "why",
        "cost_usd": 0.3,
        "agent": "wt-1",
    }
    entry.update(overrides)
    return entry


def _request(iteration, entries, page=None, accepted=None, stop=None, model="claude-haiku-5-5"):
    return {
        "implementation": "find_then_type",
        "configuration": "extraction-find-then-type",
        "model": model,
        "page": page,
        "page_suffix": "loop-find_then_type",
        "iteration": iteration,
        "entries": entries,
        "accepted_hypothesis": accepted,
        "margins": {
            "epsilon": 0.03,
            "holdout_slack": 0.06,
            "coverage_slack": 0.05,
            "guard_slack": None,
            "provisional": True,
            "basis": "typing noise only",
            "missing": "full re-recording noise",
        },
        "budget_usd": 20,
        "stop": stop,
    }


@pytest.fixture
def docs(tmp_path):
    """A copy of the current state and the experiments index."""
    root = tmp_path / "extraction"
    (root / "experiments").mkdir(parents=True)
    shutil.copy(DOCS / "README.md", root / "README.md")
    shutil.copy(DOCS / "experiments" / "README.md", root / "experiments" / "README.md")
    return root


@pytest.fixture
def ledger(tmp_path):
    return tmp_path / "ledger.jsonl"


def _page(docs, name=PAGE_FILE):
    return (docs / "experiments" / name).read_text()


def _index_rows(docs, name=PAGE_FILE):
    index = (docs / "experiments" / "README.md").read_text()
    return [line for line in index.split("\n") if f"]({name})" in line]


def _numbers_section(text):
    return text.split("## Best current numbers")[1].split("\n## ")[0]


def _leads(text):
    inside = text.split("<!-- loop:leads:start -->")[1].split("<!-- loop:leads:end -->")[0]
    return [line for line in inside.split("\n") if line.strip()]


class TestRecord:
    def test_first_iteration_creates_the_page_with_the_template_sections(self, docs, ledger):
        outcome = record(_request(1, [_entry(1, "a", "rejected")]), "2026-11-16", docs, ledger)

        assert outcome == {
            "page": PAGE,
            "created": True,
            "appended": 1,
            "skipped": 0,
            "index_row": "added",
            "lead_recorded": False,
        }
        page = _page(docs)
        template = (DOCS / "experiments" / "_template.md").read_text()
        headings = [line for line in page.split("\n") if line.startswith("## ")]
        assert headings == [f"## {section}" for section in SECTIONS]
        assert headings == [line for line in template.split("\n") if line.startswith("## ")]
        assert "**provisional**" in page and "ε = 0.03" in page
        assert "a lead, not a result" in page
        assert "| 1 | `a` | rejected |" in page
        assert "Running: no change accepted yet." in page
        [entry] = read_entries(ledger)
        assert entry["campaign"] == "2026-11-16-loop-find_then_type"
        assert entry["date"] == "2026-11-16"

    def test_later_iterations_regenerate_the_table_and_keep_what_is_outside_the_markers(
        self, docs, ledger
    ):
        record(_request(1, [_entry(1, "a", "rejected")]), "2026-11-16", docs, ledger)
        page_path = docs / "experiments" / PAGE_FILE
        page_path.write_text(page_path.read_text() + "\nA hand-written line.\n")

        outcome = record(
            _request(2, [_entry(2, "b", "unmeasured")], page=PAGE), "2026-11-17", docs, ledger
        )

        assert outcome["created"] is False
        assert outcome["index_row"] == "updated"
        page = _page(docs)
        assert "A hand-written line." in page
        assert page.count("<!-- loop:results:start -->") == 1
        assert page.count("| iteration | hypothesis |") == 1
        assert "| 1 | `a` |" in page and "| 2 | `b` |" in page
        assert len(_index_rows(docs)) == 1
        assert (
            "2 iteration(s): 0 accepted (leads), 1 rejected, 1 unmeasured" in _index_rows(docs)[0]
        )

    def test_a_campaign_shows_only_its_own_entries(self, docs, ledger):
        record(_request(1, [_entry(1, "a", "rejected")]), "2026-11-10", docs, ledger)
        record(_request(1, [_entry(1, "b", "rejected")]), "2026-11-16", docs, ledger)
        assert "`b`" in _page(docs) and "`a`" not in _page(docs)

    def test_a_second_campaign_on_the_same_day_gets_its_own_page(self, docs, ledger):
        first = record(
            _request(1, [_entry(1, "a", "rejected")], stop="plateau"), "2026-11-16", docs, ledger
        )
        second = record(_request(1, [_entry(1, "b", "rejected")]), "2026-11-16", docs, ledger)
        third = record(_request(1, [_entry(1, "c", "rejected")]), "2026-11-16", docs, ledger)

        assert first["page"] == PAGE
        assert second["page"] == PAGE.replace(".md", "-2.md")
        assert third["page"] == PAGE.replace(".md", "-3.md")
        assert second["created"] is True and second["appended"] == 1
        assert "`b`" not in _page(docs) and "Stopped: plateau." in _page(docs)
        assert "`b`" in _page(docs, "2026-11-16-loop-find_then_type-2.md")
        stems = [entry["campaign"] for entry in read_entries(ledger)]
        assert stems == [
            "2026-11-16-loop-find_then_type",
            "2026-11-16-loop-find_then_type-2",
            "2026-11-16-loop-find_then_type-3",
        ]
        assert len(_index_rows(docs, "2026-11-16-loop-find_then_type-2.md")) == 1

    def test_recording_the_same_request_twice_is_a_no_op(self, docs, ledger):
        request = _request(1, [_entry(1, "a", "rejected"), _entry(1, "b", "unmeasured")])
        record(json.loads(json.dumps(request)), "2026-11-16", docs, ledger)
        page_before = _page(docs)
        index_before = (docs / "experiments" / "README.md").read_text()

        again = dict(request, page=PAGE)
        outcome = record(again, "2026-11-16", docs, ledger)

        assert outcome["appended"] == 0 and outcome["skipped"] == 2
        assert len(read_entries(ledger)) == 2
        assert ledger.read_text().count("\n") == 2
        assert _page(docs) == page_before
        assert (docs / "experiments" / "README.md").read_text() == index_before

    def test_a_first_iteration_re_run_with_no_page_is_the_same_campaign(self, docs, ledger):
        """A first iteration's request names no page; its re-run is no second campaign."""
        request = _request(1, [_entry(1, "a", "rejected")])
        record(json.loads(json.dumps(request)), "2026-11-16", docs, ledger)
        outcome = record(json.loads(json.dumps(request)), "2026-11-16", docs, ledger)
        assert outcome["page"] == PAGE
        assert outcome["created"] is False and outcome["appended"] == 0
        assert outcome["skipped"] == 1
        assert not (docs / "experiments" / PAGE_FILE.replace(".md", "-2.md")).exists()
        assert len(read_entries(ledger)) == 1

    def test_an_entry_the_other_ledger_holds_is_not_appended_again(self, docs, ledger, tmp_path):
        """On the integration branch, the main checkout's ledger is read with it."""
        main_ledger = tmp_path / "main.jsonl"
        record(_request(1, [_entry(1, "a", "rejected")]), "2026-11-16", docs, main_ledger)
        outcome = record(
            _request(1, [_entry(1, "a", "rejected")], page=PAGE),
            "2026-11-16",
            docs,
            ledger,
            also_ledger=main_ledger,
        )
        assert outcome["skipped"] == 1 and not ledger.exists()

    def test_a_baseline_reset_mid_campaign_keeps_its_rows_and_verdict(self, docs, ledger):
        record(
            _request(1, [_entry(1, "a", "accepted", dev_typed=0.5)], accepted="a", stop="accepted"),
            "2026-11-16",
            docs,
            ledger,
        )
        append_baseline_reset(
            "re-measured margins",
            "extraction_benchmark",
            ledger_path=ledger,
            implementation="find_then_type",
            configuration="extraction-find-then-type",
            today="2026-11-17",
        )
        record(_request(2, [_entry(2, "b", "rejected")], page=PAGE), "2026-11-18", docs, ledger)

        page = _page(docs)
        assert "| 1 | `a` | accepted |" in page and "| 2 | `b` | rejected |" in page
        assert "Lead (one take): `a` (iteration 1)" in page
        assert "Lead (one take): `a`" in _index_rows(docs)[0]
        # The loop's own decisions still read through the reset.
        assert accepted_hypotheses(ledger, "find_then_type") == []
        assert rejected_hypotheses(ledger, "find_then_type", "extraction-find-then-type") == ["b"]

    def test_an_accept_is_a_lead_and_no_number_on_the_current_state_moves(self, docs, ledger):
        before = (docs / "README.md").read_text()
        record(_request(1, [_entry(1, "a", "rejected")]), "2026-11-16", docs, ledger)
        assert (docs / "README.md").read_text() == before

        outcome = record(
            _request(
                2,
                [_entry(2, "b", "accepted", dev_typed=0.5123)],
                page=PAGE,
                accepted="b",
                stop="accepted: promote",
            ),
            "2026-11-18",
            docs,
            ledger,
        )

        assert outcome["lead_recorded"] is True
        after = (docs / "README.md").read_text()
        assert _numbers_section(after) == _numbers_section(before)
        assert "**As of 2026-11-18.**" in after
        [lead] = _leads(after)
        assert lead.startswith("- `find_then_type` with `extraction-find-then-type`: `b`")
        assert "dev typed F1 0.4648 → 0.5123" in lead and "holdout typed F1 0.4811 → 0.4700" in lead
        assert "one take" in lead and f"(experiments/{PAGE_FILE})" in lead
        assert "To confirm with three takes." in lead
        page = _page(docs)
        assert (
            "Lead (one take): `b` (iteration 2), merged to the integration branch; confirm with"
            " three takes before it counts." in page
        )
        assert "Adopted" not in page and "Adopted" not in _index_rows(docs)[0]
        assert "Lead (one take): `b`; confirm with three takes" in _index_rows(docs)[0]

        # Everything outside the leads block and the date is byte-identical.
        def strip(text):
            text = (
                text.split("<!-- loop:leads:start -->")[0]
                + text.split("<!-- loop:leads:end -->")[1]
            )
            return text.replace("**As of 2026-11-18.**", "**As of 2026-11-16.**")

        assert strip(after) == strip(before)

    def test_the_same_lead_accepted_again_replaces_its_line(self, docs, ledger):
        record(
            _request(1, [_entry(1, "b", "accepted", dev_typed=0.5)], accepted="b"),
            "2026-11-16",
            docs,
            ledger,
        )
        record(
            _request(2, [_entry(2, "b", "accepted", dev_typed=0.52)], page=PAGE, accepted="b"),
            "2026-11-17",
            docs,
            ledger,
        )
        [lead] = _leads((docs / "README.md").read_text())
        assert "0.5200" in lead and "iteration 2" in lead

    def test_an_accept_that_was_not_merged_is_no_lead(self, docs, ledger):
        before = (docs / "README.md").read_text()
        outcome = record(
            _request(1, [_entry(1, "b", "accept_unmerged")], stop="could not be merged"),
            "2026-11-16",
            docs,
            ledger,
        )
        assert outcome["lead_recorded"] is False
        assert (docs / "README.md").read_text() == before
        assert "Passed the accept gate but not merged, so not a lead: `b`" in _page(docs)
        assert "Not merged: `b`; no lead" in _index_rows(docs)[0]
        assert "| 1 | `b` | accept_unmerged |" in _page(docs)
        assert accepted_hypotheses(ledger, "find_then_type") == []
        assert rejected_hypotheses(ledger, "find_then_type") == []
        with pytest.raises(CampaignRecordError, match="no accepted entry"):
            record(
                _request(2, [_entry(2, "c", "accept_unmerged")], page=PAGE, accepted="c"),
                "2026-11-16",
                docs,
                ledger,
            )

    def test_a_stop_with_no_entries_updates_the_verdict_and_the_index_row(self, docs, ledger):
        record(_request(1, [_entry(1, "a", "rejected")]), "2026-11-16", docs, ledger)
        assert "Running" in _index_rows(docs)[0]

        outcome = record(
            _request(2, [], page=PAGE, stop="budget exhausted", model=None),
            "2026-11-17",
            docs,
            ledger,
        )

        assert outcome["appended"] == 0 and outcome["created"] is False
        assert "Rejected: no change passed the accept gate. Stopped: budget exhausted." in _page(
            docs
        )
        row = _index_rows(docs)[0]
        assert "Running" not in row and "(stopped)" in row
        assert "(claude-haiku-5-5)" in row, "the model is the campaign's when the request has none"
        with pytest.raises(CampaignRecordError, match="nothing to record"):
            record(_request(1, [], stop="plateau"), "2026-11-20", docs, ledger)

    def test_two_index_rows_for_one_campaign_are_refused(self, docs, ledger):
        record(_request(1, [_entry(1, "a", "rejected")]), "2026-11-16", docs, ledger)
        index = docs / "experiments" / "README.md"
        [row] = _index_rows(docs)
        index.write_text(index.read_text().replace(row, f"{row}\n{row}"))
        with pytest.raises(CampaignRecordError, match="2 rows"):
            record(_request(2, [_entry(2, "b", "rejected")], page=PAGE), "2026-11-17", docs, ledger)
        assert len(read_entries(ledger)) == 1

    @pytest.mark.parametrize(
        "change",
        [
            lambda r: r.update(page="documentation/extraction/README.md"),
            lambda r: r.update(page_suffix="find_then_type"),
            lambda r: r.update(implementation="bad name"),
            lambda r: r.update(accepted_hypothesis="not-in-entries"),
            lambda r: r.update(model="a|b"),
            lambda r: r.update(model="line\nbreak"),
            lambda r: r.update(entries=[1]),
            lambda r: r.update(entries="x"),
            lambda r: r.update(stop=["not", "text"]),
            lambda r: r["entries"][0].pop("decision"),
            lambda r: r["entries"][0].update(decision="deferred"),
            lambda r: r["entries"][0].update(decision="baseline_reset"),
            lambda r: r["entries"][0].update(hypothesis=None),
            lambda r: r["entries"][0].update(configuration="extraction-default"),
        ],
    )
    def test_a_bad_request_writes_nothing(self, docs, ledger, change):
        request = _request(1, [_entry(1, "a", "rejected")])
        change(request)
        with pytest.raises(ValueError):
            record(request, "2026-11-16", docs, ledger)
        assert not ledger.exists()
        assert not (docs / "experiments" / PAGE_FILE).exists()

    def test_a_page_without_its_markers_is_refused_before_the_ledger_is_appended(
        self, docs, ledger
    ):
        record(_request(1, [_entry(1, "a", "rejected")]), "2026-11-16", docs, ledger)
        page_path = docs / "experiments" / PAGE_FILE
        page_path.write_text(page_path.read_text().replace("<!-- loop:verdict:end -->", ""))
        with pytest.raises(CampaignRecordError, match="verdict"):
            record(_request(2, [_entry(2, "b", "rejected")], page=PAGE), "2026-11-17", docs, ledger)
        assert len(read_entries(ledger)) == 1

    def test_a_stop_reason_cannot_break_the_page(self, docs, ledger):
        stop = "line one\nline | two <!-- loop:verdict:end -->"
        record(_request(1, [_entry(1, "a", "rejected")], stop=stop), "2026-11-16", docs, ledger)
        page = _page(docs)
        assert page.count("<!-- loop:verdict:end -->") == 1
        record(_request(2, [_entry(2, "b", "rejected")], page=PAGE), "2026-11-17", docs, ledger)


class TestHelpers:
    def test_page_name(self, tmp_path):
        assert page_name(_request(1, []), "2026-11-16", tmp_path) == PAGE_FILE
        assert page_name(_request(1, [], page=PAGE), "2026-12-01", tmp_path) == PAGE_FILE
        (tmp_path / PAGE_FILE).write_text("")
        assert page_name(_request(1, []), "2026-11-16", tmp_path) == PAGE_FILE.replace(
            ".md", "-2.md"
        )

    def test_replace_block_keeps_everything_else(self):
        text = "a\n<!-- loop:x:start -->\nold\n<!-- loop:x:end -->\nb"
        assert replace_block(text, "x", "new") == (
            "a\n<!-- loop:x:start -->\nnew\n<!-- loop:x:end -->\nb"
        )
        with pytest.raises(CampaignRecordError):
            replace_block(text + text, "x", "new")


class TestCli:
    def test_reads_the_request_from_stdin_and_prints_what_it_did(
        self, docs, ledger, monkeypatch, capsys
    ):
        request = _request(1, [_entry(1, "a", "rejected")])
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(request)))
        exit_code = campaign_cli(
            ["--docs-root", str(docs), "--ledger-path", str(ledger), "--today", "2026-11-16"]
        )
        assert exit_code == 0
        assert json.loads(capsys.readouterr().out)["page"] == PAGE

    @pytest.mark.parametrize("stdin", ["not json", "[1, 2]", '{"entries": [1]}'])
    def test_a_bad_request_exits_1_with_a_clean_error(
        self, docs, ledger, monkeypatch, capsys, stdin
    ):
        monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
        assert campaign_cli(["--docs-root", str(docs), "--ledger-path", str(ledger)]) == 1
        err = capsys.readouterr().err
        assert err.startswith("ERROR:") and "Traceback" not in err
