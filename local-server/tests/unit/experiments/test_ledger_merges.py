"""
The ledger across git branches: the loop commits its entries on its integration
branch, `main` gets them by a promotion (merged or squashed), and the record
step merges `main` into the branch with `merge=union` on the ledger
(`/.gitattributes`). These tests replay those histories in a scratch git
repository and check what `read_entries` makes of the result.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from experiments.ledger import read_entries, rejected_hypotheses

REPO_ROOT = Path(__file__).resolve().parents[4]
LEDGER = "ledger.jsonl"

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")


def _entry(hypothesis, decision="rejected", date="2026-11-16", campaign="c1", **extra):
    entry = {
        "experiment_id": f"1-find_then_type-{hypothesis}",
        "iteration": 1,
        "implementation": "find_then_type",
        "configuration": "extraction-find-then-type",
        "hypothesis": hypothesis,
        "variant": "v",
        "diff_stat": "",
        "base_commit": "abc",
        "dev": {},
        "holdout": {},
        "decision": decision,
        "reason": "",
        "cost_usd": 0,
        "agent": "wt",
        "date": date,
    }
    if campaign:
        entry["campaign"] = campaign
    entry.update(extra)
    return entry


def _reset(date):
    return {
        "experiment_id": "baseline-reset-extraction_benchmark-n/a",
        "iteration": 0,
        "hypothesis": "__baseline_reset__",
        "variant": "extraction_benchmark",
        "diff_stat": "",
        "base_commit": "abc",
        "dev": {},
        "holdout": {},
        "decision": "baseline_reset",
        "reason": "re-recorded",
        "cost_usd": 0,
        "agent": "system",
        "implementation": "find_then_type",
        "configuration": "extraction-find-then-type",
        "date": date,
    }


class Repo:
    """A scratch repository with one ledger file, on `main`."""

    def __init__(self, root: Path, union: bool = True):
        self.root = root
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "loop@example.invalid")
        self.git("config", "user.name", "loop")
        if union:
            (root / ".gitattributes").write_text(f"{LEDGER} merge=union\n")
        self.append(_entry("base", campaign=None, date=None))
        self.commit("base")

    def git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args], cwd=self.root, capture_output=True, text=True, check=check
        )

    def append(self, *entries: dict) -> None:
        with open(self.root / LEDGER, "a") as f:
            for entry in entries:
                f.write(json.dumps({k: v for k, v in entry.items() if v is not None}) + "\n")

    def commit(self, message: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def show(self, branch: str, into: Path) -> Path:
        into.write_text(self.git("show", f"{branch}:{LEDGER}").stdout)
        return into


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    return Repo(root)


def test_the_repository_merges_the_ledger_as_a_union():
    attributes = (REPO_ROOT / ".gitattributes").read_text().split("\n")
    assert "local-server/experiments/ledger.jsonl merge=union" in attributes


def test_both_sides_appending_merge_cleanly_and_read_whole(repo):
    """union1: the branch and `main` each append; merging `main` keeps both."""
    repo.git("checkout", "-q", "-b", "exp")
    repo.append(_entry("e1"), _entry("e2"))
    repo.commit("exp")
    repo.git("checkout", "-q", "main")
    repo.append(_entry("m1", campaign="c0", date="2026-11-15"))
    repo.commit("main")
    repo.git("checkout", "-q", "exp")
    assert repo.git("merge", "--no-edit", "main", check=False).returncode == 0
    ids = [e["hypothesis"] for e in read_entries(repo.root / LEDGER)]
    assert sorted(ids) == ["base", "e1", "e2", "m1"]


def test_without_the_union_attribute_both_sides_appending_conflict(tmp_path):
    """union2: why `/.gitattributes` holds the line."""
    root = tmp_path / "plain"
    root.mkdir()
    repo = Repo(root, union=False)
    repo.git("checkout", "-q", "-b", "exp")
    repo.append(_entry("e1"))
    repo.commit("exp")
    repo.git("checkout", "-q", "main")
    repo.append(_entry("m1"))
    repo.commit("main")
    repo.git("checkout", "-q", "exp")
    assert repo.git("merge", "--no-edit", "main", check=False).returncode != 0


def test_after_a_squash_promotion_and_a_reset_both_ledgers_read_as_one(repo, tmp_path):
    """
    union3: the branch is squash-promoted (it is never an ancestor of `main`
    again), `main` then records a reset, and the branch goes on. Reading the
    checkout's ledger and the branch's together gives every entry once, in date
    order: the reset covers what came before it and not what came after.
    """
    repo.git("checkout", "-q", "-b", "exp")
    repo.append(_entry("before", date="2026-11-16"))
    repo.commit("e1")
    repo.git("checkout", "-q", "main")
    repo.git("merge", "-q", "--squash", "exp")
    repo.commit("squash")
    repo.append(_reset("2026-11-17"))
    repo.commit("reset")
    repo.git("checkout", "-q", "exp")
    repo.append(_entry("after", date="2026-11-18"))
    repo.commit("e2")

    main_ledger = repo.show("main", tmp_path / "main.jsonl")
    branch_ledger = repo.show("exp", tmp_path / "exp.jsonl")
    both = [main_ledger, branch_ledger]
    assert [e["hypothesis"] for e in read_entries(both)] == [
        "base",
        "before",
        "__baseline_reset__",
        "after",
    ]
    assert rejected_hypotheses(both, "find_then_type", "extraction-find-then-type") == ["after"]
    # The branch alone misses the reset; `main` alone misses the newest rejection.
    assert rejected_hypotheses(branch_ledger, "find_then_type") == ["base", "before", "after"]
    assert rejected_hypotheses(main_ledger, "find_then_type") == []

    # Merging `main` back puts the reset after the branch's newer line in the
    # file; reading by date still puts it where it happened.
    assert repo.git("merge", "--no-edit", "main", check=False).returncode == 0
    lines = (repo.root / LEDGER).read_text().strip().split("\n")
    assert json.loads(lines[-1])["decision"] == "baseline_reset"
    merged = repo.root / LEDGER
    assert rejected_hypotheses(merged, "find_then_type", "extraction-find-then-type") == ["after"]


def test_a_line_both_sides_hold_is_counted_once(repo):
    """union4: a union merge keeps both copies of a line both sides added."""
    repo.git("checkout", "-q", "-b", "exp")
    repo.append(_entry("x", campaign="c2"), _entry("same"))
    repo.commit("exp")
    repo.git("checkout", "-q", "main")
    repo.append(_entry("same"), _entry("y", campaign="c3"))
    repo.commit("main")
    repo.git("checkout", "-q", "exp")
    assert repo.git("merge", "--no-edit", "main", check=False).returncode == 0
    text = (repo.root / LEDGER).read_text()
    assert text.count('"hypothesis": "same"') == 2, "the union kept both copies"
    ids = [e["hypothesis"] for e in read_entries(repo.root / LEDGER)]
    assert ids.count("same") == 1
    assert rejected_hypotheses(repo.root / LEDGER, "find_then_type").count("same") == 1
