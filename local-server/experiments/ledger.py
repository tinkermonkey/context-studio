"""
Append-only experiment ledger for the Karpathy loop (Loop C).

Read/write helpers for `local-server/experiments/ledger.jsonl` — one JSON
line per experiment (accepted and rejected), in the exact shape specified by
`documentation/karpathy_loop_design.md` §8:

    {"experiment_id": "...", "iteration": 12, "hypothesis": "copular handling",
     "variant": "open_v1+copular", "diff_stat": "...", "base_commit": "...",
     "dev": {"strict_f1": 0.31, "soft_f1": 0.52, "candidate_recall": 0.71},
     "holdout": {"strict_f1": 0.28, "soft_f1": 0.47},
     "decision": "accepted", "reason": "", "cost_usd": 0.11, "agent": "worktree-2"}

The ledger is the loop's negative-result memory (design doc §6 guardrails):
`rejected_hypotheses()` is consulted by target selection (§4.3 step 2) so a
hypothesis that already failed is not retried without a materially changed
codebase. The ledger is also one of the accept-gate's integrity checks
(§6 item 4: "no edits to ... ledger history") — this module only ever opens
the file in append mode, never rewrites or truncates it.

Usage as a library (from Python):

    from experiments.ledger import append_entry, read_entries, rejected_hypotheses

Usage as a CLI (from a Loop C experimenter/verifier/decider sub-agent, which
has shell access but no in-process import of this package — see
`.claude/workflows/karpathy-loop.js`):

    python experiments/ledger.py append '<json entry>'
    python experiments/ledger.py append --stdin <<'EOF'
    <json entry>
    EOF
    python experiments/ledger.py rejected-hypotheses

`append --stdin` exists because ledger entries routinely embed free-form LLM
text (verifier/reject reasons) that may contain apostrophes, backticks, or
`$` — unsafe to interpolate into a single-quoted shell argument. Callers with
free-form text should always prefer `--stdin` with a quoted heredoc
(`<<'EOF'`), which takes the body literally with no shell expansion.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional, Union

LEDGER_PATH = Path(__file__).parent / "ledger.jsonl"

REQUIRED_FIELDS = (
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
)

VALID_DECISIONS = ("accepted", "rejected")


class LedgerEntryError(ValueError):
    """Raised when a ledger entry is missing required fields or has an invalid decision."""


def validate_entry(entry: dict[str, Any]) -> None:
    """
    Validate `entry` against the ledger shape in karpathy_loop_design.md §8.

    Raises:
        LedgerEntryError: If a required field is missing, or `decision` is
            not one of "accepted"/"rejected".
    """
    missing = [field for field in REQUIRED_FIELDS if field not in entry]
    if missing:
        raise LedgerEntryError(f"ledger entry missing required field(s): {missing}")
    if entry["decision"] not in VALID_DECISIONS:
        raise LedgerEntryError(
            f"ledger entry 'decision' must be one of {VALID_DECISIONS}, got {entry['decision']!r}"
        )


def append_entry(entry: dict[str, Any], ledger_path: Optional[Union[Path, str]] = None) -> None:
    """
    Validate and append one experiment record to the ledger.

    Args:
        entry: The experiment record (see module docstring for the required shape).
        ledger_path: Defaults to `LEDGER_PATH`. Override for testing.
    """
    validate_entry(entry)
    path = Path(ledger_path) if ledger_path is not None else LEDGER_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def read_entries(ledger_path: Optional[Union[Path, str]] = None) -> list[dict[str, Any]]:
    """Read every entry in the ledger, in file order. Returns [] if the ledger doesn't exist yet."""
    path = Path(ledger_path) if ledger_path is not None else LEDGER_PATH
    if not path.exists():
        return []
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def rejected_hypotheses(ledger_path: Optional[Union[Path, str]] = None) -> list[str]:
    """
    Return the distinct `hypothesis` strings of every rejected experiment, in first-seen order.

    Target selection (§4.3 step 2) excludes these unless the codebase has
    materially changed in the relevant area — that judgment call is made by
    the humans/agents driving the loop, not automated here.
    """
    seen: list[str] = []
    for entry in read_entries(ledger_path):
        hypothesis = entry.get("hypothesis")
        if entry.get("decision") == "rejected" and hypothesis is not None and hypothesis not in seen:
            seen.append(hypothesis)
    return seen


def _main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point — see module docstring for usage."""
    parser = argparse.ArgumentParser(description="Read/write the Karpathy-loop experiment ledger.")
    parser.add_argument(
        "--ledger-path",
        default=None,
        help="Override the ledger file path (defaults to experiments/ledger.jsonl next to this script).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    append_parser = subparsers.add_parser("append", help="Append one JSON ledger entry")
    append_parser.add_argument(
        "entry_json",
        nargs="?",
        default=None,
        help="The entry as a JSON object string. Omit this and pass --stdin instead when the entry"
        " contains free-form text that cannot survive shell quoting.",
    )
    append_parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read the JSON entry from standard input instead of the entry_json argument"
        " (use with a quoted heredoc: `<<'EOF' ... EOF`).",
    )

    subparsers.add_parser("rejected-hypotheses", help="Print rejected hypotheses, one per line")

    args = parser.parse_args(argv)

    if args.command == "append":
        if args.stdin and args.entry_json is not None:
            print("ERROR: pass either entry_json or --stdin, not both", file=sys.stderr)
            return 1
        if not args.stdin and args.entry_json is None:
            print("ERROR: provide entry_json or --stdin", file=sys.stderr)
            return 1
        raw_json = sys.stdin.read() if args.stdin else args.entry_json
        try:
            entry = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            print(f"ERROR: entry_json is not valid JSON: {exc}", file=sys.stderr)
            return 1
        try:
            append_entry(entry, ledger_path=args.ledger_path)
        except LedgerEntryError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        path = args.ledger_path or LEDGER_PATH
        print(f"appended experiment '{entry['experiment_id']}' ({entry['decision']}) to {path}")
        return 0

    if args.command == "rejected-hypotheses":
        for hypothesis in rejected_hypotheses(ledger_path=args.ledger_path):
            print(hypothesis)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(_main())
