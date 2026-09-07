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

Entries may also carry an optional `bootstrap` field — the Wave 1 DR
bootstrap-scenario diagnostics (`karpathy_loop_dr_ontology_design.md` §5,
`dataset_split.py`'s `DR_BOOTSTRAP_SCENARIOS`), logged for visibility only.
It is not in `REQUIRED_FIELDS` and nothing that reads the ledger
(`rejected_hypotheses`, the §6 accept gate) ever consults it — see
`acceptGate` in `.claude/workflows/karpathy-loop.js`, which takes only `dev`
and `holdout` as arguments.

The ledger is the loop's negative-result memory (design doc §6 guardrails):
`rejected_hypotheses()` is consulted by target selection (§4.3 step 2) so a
hypothesis that already failed is not retried without a materially changed
codebase. The ledger is also one of the accept-gate's integrity checks
(§6 item 4: "no edits to ... ledger history") — this module only ever opens
the file in append mode, never rewrites or truncates it.

A `decision: "baseline_reset"` entry (written via `append_baseline_reset`,
never hand-authored) marks a measurement-layer or ontology/corpus swap —
e.g. the DR ontology import replacing the placeholder 3-class ontology
(`documentation/karpathy_loop_dr_ontology_design.md` §9). Every ledger read
that feeds a loop decision is scoped through `entries_since_last_baseline_reset`
so entries recorded before the most recent reset are excluded automatically;
`rejected_hypotheses` already does this. This is a mechanism, not a
documented convention: a pre-reset rejection cannot silently suppress
retrying the same hypothesis after the baseline it was rejected under no
longer exists. Any future spec-version upgrade (DR or otherwise) is expected
to append a new `baseline_reset` entry rather than mutate ontology data
in place silently — see `scripts/import_dr_ontology.py`, which does this
automatically on a spec-version change.

Usage as a library (from Python):

    from experiments.ledger import (
        accepted_hypotheses,
        append_baseline_reset,
        append_entry,
        entries_since_last_baseline_reset,
        read_entries,
        rejected_hypotheses,
    )

Usage as a CLI (from a Loop C experimenter/verifier/decider sub-agent, which
has shell access but no in-process import of this package — see
`.claude/workflows/karpathy-loop.js`):

    python experiments/ledger.py append '<json entry>'
    python experiments/ledger.py append --stdin <<'EOF'
    <json entry>
    EOF
    python experiments/ledger.py rejected-hypotheses
    python experiments/ledger.py accepted-hypotheses
    python experiments/ledger.py baseline-reset --ontology-context dr_spec --spec-version 0.8.4 \
        --base-commit "$(git rev-parse HEAD)" 'Replaced the placeholder ontology with the DR spec.'

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

from utils.logger import get_logger

LEDGER_PATH = Path(__file__).parent / "ledger.jsonl"

logger = get_logger(__name__)

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

BASELINE_RESET_DECISION = "baseline_reset"

VALID_DECISIONS = ("accepted", "rejected", BASELINE_RESET_DECISION)


class LedgerEntryError(ValueError):
    """Raised when a ledger entry is missing required fields or has an invalid decision."""


def validate_entry(entry: dict[str, Any]) -> None:
    """
    Validate `entry` against the ledger shape in karpathy_loop_design.md §8.

    Raises:
        LedgerEntryError: If a required field is missing, or `decision` is
            not one of "accepted"/"rejected"/"baseline_reset".
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


def read_entries(
    ledger_path: Optional[Union[Path, str]] = None,
) -> list[dict[str, Any]]:
    """
    Read every entry in the ledger, in file order. Returns [] if the ledger doesn't exist yet.

    The ledger is an append-only audit log, so a single corrupted line
    (partial write, disk full, concurrent access) must not prevent reading
    every other valid entry. A line that fails to parse as JSON is skipped
    with a warning rather than raised.
    """
    path = Path(ledger_path) if ledger_path is not None else LEDGER_PATH
    if not path.exists():
        return []
    entries = []
    with open(path) as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError as exc:
                logger.warning(
                    "skipping corrupted ledger line %d in %s: %s",
                    line_number,
                    path,
                    exc,
                )
    return entries


def append_baseline_reset(
    reason: str,
    ontology_context: str,
    spec_version: Optional[str] = None,
    base_commit: str = "unknown",
    iteration: int = 0,
    agent: str = "system",
    ledger_path: Optional[Union[Path, str]] = None,
) -> dict[str, Any]:
    """
    Append a baseline-reset checkpoint entry to the ledger.

    A baseline reset marks a measurement-layer or ontology/corpus swap
    (karpathy_loop_design.md §6 "metric-gaming defense";
    karpathy_loop_dr_ontology_design.md §9) — e.g. importing a new ontology
    that existing scenarios were not graded against. Every entry recorded
    before a baseline reset is excluded from `entries_since_last_baseline_reset`
    (and therefore from `rejected_hypotheses`): this is the mechanism, not
    just a documented convention, by which pre-reset dev/holdout scores stop
    being used to judge post-reset experiments.

    Args:
        reason: Human-readable explanation of what changed and why.
        ontology_context: Identifier for the new baseline (e.g. "dr_spec",
            "placeholder").
        spec_version: The external spec version pinned by this baseline, if
            the baseline is tied to one (e.g. the DR spec's own
            `specVersion`). None for resets not tied to a versioned spec.
        base_commit: The repository commit this reset was recorded against.

    Returns:
        The entry that was appended.
    """
    entry: dict[str, Any] = {
        "experiment_id": f"baseline-reset-{ontology_context}-{spec_version or 'n/a'}",
        "iteration": iteration,
        "hypothesis": "__baseline_reset__",
        "variant": f"{ontology_context}@{spec_version}" if spec_version else ontology_context,
        "diff_stat": "n/a (ontology/corpus baseline reset, not a code diff)",
        "base_commit": base_commit,
        "dev": {},
        "holdout": {},
        "decision": BASELINE_RESET_DECISION,
        "reason": reason,
        "cost_usd": 0,
        "agent": agent,
        "ontology_context": ontology_context,
        "spec_version": spec_version,
    }
    append_entry(entry, ledger_path=ledger_path)
    return entry


def entries_since_last_baseline_reset(
    ledger_path: Optional[Union[Path, str]] = None,
) -> list[dict[str, Any]]:
    """
    Return every ledger entry recorded after the most recent baseline-reset
    checkpoint (the checkpoint entry itself is excluded), or every entry if
    no checkpoint has been recorded yet.

    Every ledger read that feeds a loop decision should be scoped through
    this function instead of `read_entries` directly, so pre-reset entries
    never silently influence a post-reset decision.
    """
    entries = read_entries(ledger_path)
    last_reset_index = None
    for index, entry in enumerate(entries):
        if entry.get("decision") == BASELINE_RESET_DECISION:
            last_reset_index = index
    if last_reset_index is None:
        return entries
    return entries[last_reset_index + 1 :]


def latest_baseline_reset(
    ontology_context: Optional[str] = None,
    ledger_path: Optional[Union[Path, str]] = None,
) -> Optional[dict[str, Any]]:
    """
    Return the most recently recorded baseline-reset entry, optionally
    filtered to a specific `ontology_context`, or None if none exists.

    Used to make baseline resets themselves idempotent per spec version: a
    caller (e.g. the DR ontology import script) can check whether the current
    spec version already has a recorded checkpoint before appending another.
    """
    matches = [
        entry
        for entry in read_entries(ledger_path)
        if entry.get("decision") == BASELINE_RESET_DECISION
        and (ontology_context is None or entry.get("ontology_context") == ontology_context)
    ]
    return matches[-1] if matches else None


def rejected_hypotheses(ledger_path: Optional[Union[Path, str]] = None) -> list[str]:
    """
    Return the distinct `hypothesis` strings of every rejected experiment
    recorded since the last baseline reset, in first-seen order.

    Target selection (§4.3 step 2) excludes these unless the codebase has
    materially changed in the relevant area — that judgment call is made by
    the humans/agents driving the loop, not automated here. Rejections
    recorded before a baseline reset (e.g. against the retired placeholder
    ontology) are scoped out entirely: see `entries_since_last_baseline_reset`.
    """
    seen: list[str] = []
    for entry in entries_since_last_baseline_reset(ledger_path):
        hypothesis = entry.get("hypothesis")
        if (
            entry.get("decision") == "rejected"
            and hypothesis is not None
            and hypothesis not in seen
        ):
            seen.append(hypothesis)
    return seen


def accepted_hypotheses(ledger_path: Optional[Union[Path, str]] = None) -> list[str]:
    """
    Return the distinct `hypothesis` strings of every accepted experiment
    recorded since the last baseline reset, in first-seen order.

    Target selection (§4.3 step 2) excludes these: an accepted hypothesis is
    already merged into the incumbent, so re-drafting it produces a candidate
    the accept gate can only reject (it cannot beat an incumbent that already
    contains it) — a wasted iteration. Acceptances recorded before a baseline
    reset are scoped out (see `entries_since_last_baseline_reset`), so an
    ontology/corpus swap makes a previously-merged hypothesis retryable again,
    since the incumbent it was merged into no longer exists.
    """
    seen: list[str] = []
    for entry in entries_since_last_baseline_reset(ledger_path):
        hypothesis = entry.get("hypothesis")
        if (
            entry.get("decision") == "accepted"
            and hypothesis is not None
            and hypothesis not in seen
        ):
            seen.append(hypothesis)
    return seen


def _main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point — see module docstring for usage."""
    parser = argparse.ArgumentParser(description="Read/write the Karpathy-loop experiment ledger.")
    parser.add_argument(
        "--ledger-path",
        default=None,
        help="Override the ledger file path (defaults to experiments/ledger.jsonl next to"
        " this script).",
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

    subparsers.add_parser("accepted-hypotheses", help="Print accepted hypotheses, one per line")

    baseline_reset_parser = subparsers.add_parser(
        "baseline-reset", help="Append a baseline-reset checkpoint entry"
    )
    baseline_reset_parser.add_argument(
        "--ontology-context",
        required=True,
        help="Identifier for the new baseline, e.g. 'dr_spec'",
    )
    baseline_reset_parser.add_argument(
        "--spec-version",
        default=None,
        help="External spec version pinned by this baseline, if any",
    )
    baseline_reset_parser.add_argument(
        "--base-commit",
        default="unknown",
        help="Repository commit this reset was recorded against",
    )
    baseline_reset_parser.add_argument("--iteration", type=int, default=0)
    baseline_reset_parser.add_argument("--agent", default="system")
    baseline_reset_parser.add_argument(
        "reason",
        nargs="?",
        default=None,
        help="Human-readable explanation of what changed and why. Omit this and pass --stdin"
        " instead when the reason contains text that cannot survive shell quoting.",
    )
    baseline_reset_parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read the reason from standard input instead of the reason argument"
        " (use with a quoted heredoc: `<<'EOF' ... EOF`).",
    )

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

    if args.command == "accepted-hypotheses":
        for hypothesis in accepted_hypotheses(ledger_path=args.ledger_path):
            print(hypothesis)
        return 0

    if args.command == "baseline-reset":
        if args.stdin and args.reason is not None:
            print("ERROR: pass either reason or --stdin, not both", file=sys.stderr)
            return 1
        if not args.stdin and args.reason is None:
            print("ERROR: provide reason or --stdin", file=sys.stderr)
            return 1
        reason = sys.stdin.read() if args.stdin else args.reason
        entry = append_baseline_reset(
            reason=reason,
            ontology_context=args.ontology_context,
            spec_version=args.spec_version,
            base_commit=args.base_commit,
            iteration=args.iteration,
            agent=args.agent,
            ledger_path=args.ledger_path,
        )
        path = args.ledger_path or LEDGER_PATH
        print(f"appended baseline-reset checkpoint '{entry['experiment_id']}' to {path}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(_main())
