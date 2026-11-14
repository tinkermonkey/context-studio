"""
Append-only experiment ledger for the Karpathy loop (Loop C).

Read/write helpers for `local-server/experiments/ledger.jsonl` — one JSON
line per experiment (accepted and rejected), in the exact shape specified by
`documentation/karpathy_loop_design.md` §8:

    {"experiment_id": "12-default-full_class_catalog", "iteration": 12,
     "implementation": "default", "configuration": "extraction-openrouter-default",
     "hypothesis": "full_class_catalog",
     "variant": "default+full_class_catalog", "diff_stat": "...", "base_commit": "...",
     "dev": {"typed_f1": 0.41, "f1": 0.58}, "holdout": {"typed_f1": 0.37, "f1": 0.55},
     "guard": {"applies": true, "strict_f1": 0.92, "soft_f1": 0.93},
     "decision": "accepted", "reason": "", "cost_usd": 0.11, "agent": "worktree-2"}

`implementation` and `configuration` say what the experiment refined and
measured: the pipeline implementation and the configuration it ran with, the
pair every run is selected by. An experiment entry must carry both.

`dev` and `holdout` are the extraction benchmark's measures and `guard` the
triple corpus's (entries before the 2026-11 baseline reset carry triple-corpus
metrics in `dev`/`holdout`). The guard applies only to an implementation the
triple corpus has recordings of; for any other the entry records
`"guard": {"applies": false, "reason": "..."}`, never another implementation's
number. A `decision: "unmeasured"` entry has all three null when the candidate
could not be measured, and its claimed numbers when it was measured but the
verifier returned nothing.

**Hypothesis ids are scoped by what was refined: the implementation and the
configuration.** A hypothesis is a change to one implementation, judged by
measurements made with one configuration (its model decides what a change is
worth), so `rejected_hypotheses` and `accepted_hypotheses` take both and return
only that pair's entries: `cross_chunk_relationships` rejected for `default` is
still open for `find_then_type`, and a hypothesis rejected for `default` with
`extraction-openrouter-default` is still open for `default` with
`extraction-default`. An entry written before the fields existed has neither
and counts for every pair (all such entries predate the 2026-11 baseline
reset, so none is read today).

Entries may also carry an optional `bootstrap` field — the Wave 1 DR
bootstrap-scenario diagnostics (`karpathy_loop_dr_ontology_design.md` §5,
`dataset_split.py`'s `DR_BOOTSTRAP_SCENARIOS`), logged for visibility only.
It is not in `REQUIRED_FIELDS` and nothing that reads the ledger
(`rejected_hypotheses`, the §6 accept gate) ever consults it — see
`acceptGate` in `.claude/workflows/karpathy-loop.js`, which reads only `dev`,
`holdout` and `guard`.

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
`rejected_hypotheses` already does this. A reset that names an
`implementation` (and, with it, a `configuration`) resets that history only
(its recordings were made again, its margins re-measured); one that names none
resets every history (the gold files, the scorer or the ontology changed).
This is a mechanism, not a
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
    python experiments/ledger.py rejected-hypotheses --implementation find_then_type \
        --configuration extraction-find-then-type
    python experiments/ledger.py accepted-hypotheses --implementation find_then_type \
        --configuration extraction-find-then-type
    python experiments/ledger.py baseline-reset --ontology-context dr_spec --spec-version 0.8.4 \
        --base-commit "$(git rev-parse HEAD)" 'Replaced the placeholder ontology with the DR spec.'
    python experiments/ledger.py baseline-reset --ontology-context extraction_benchmark \
        --implementation find_then_type --configuration extraction-find-then-type \
        --base-commit "$(git rev-parse HEAD)" 'Recorded find_then_type again; margins re-measured.'

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

# Run as a script (`python experiments/ledger.py ...` from local-server/), the
# script's own directory is on the path, not local-server/.
sys.path.append(str(Path(__file__).resolve().parents[1]))

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

# What an experiment refined and measured. Required of an experiment entry; a
# baseline reset carries them only when it is one implementation's.
TARGET_FIELDS = ("implementation", "configuration")

BASELINE_RESET_DECISION = "baseline_reset"

# An experiment that ran but could not be measured or verified (a failed
# recording, a stale cassette, a verifier that returned nothing). It is recorded
# with its cost, and says nothing about the hypothesis: only "rejected" entries
# keep a hypothesis from being selected again.
UNMEASURED_DECISION = "unmeasured"

VALID_DECISIONS = ("accepted", "rejected", UNMEASURED_DECISION, BASELINE_RESET_DECISION)


class LedgerEntryError(ValueError):
    """Raised when a ledger entry is missing required fields or has an invalid decision."""


def validate_entry(entry: dict[str, Any]) -> None:
    """
    Validate `entry` against the ledger shape in karpathy_loop_design.md §8.

    Raises:
        LedgerEntryError: If a required field is missing, `decision` is not
            one of "accepted"/"rejected"/"unmeasured"/"baseline_reset", or an
            experiment entry does not name its implementation and configuration.
    """
    missing = [field for field in REQUIRED_FIELDS if field not in entry]
    if missing:
        raise LedgerEntryError(f"ledger entry missing required field(s): {missing}")
    if entry["decision"] not in VALID_DECISIONS:
        raise LedgerEntryError(
            f"ledger entry 'decision' must be one of {VALID_DECISIONS}, got {entry['decision']!r}"
        )
    if entry["decision"] != BASELINE_RESET_DECISION:
        unnamed = [field for field in TARGET_FIELDS if not entry.get(field)]
        if unnamed:
            raise LedgerEntryError(
                f"an experiment entry must say what it refined; missing or empty: {unnamed}"
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
    implementation: Optional[str] = None,
    configuration: Optional[str] = None,
    baseline: Optional[dict[str, Any]] = None,
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
        implementation: The one implementation whose history this resets
            (with the configuration it is measured with); None resets every
            implementation's.
        configuration: That implementation's configuration.
        baseline: The incumbent scores at this reset, for the record (dev,
            holdout, guard, failure counts; per implementation when the reset
            is every implementation's).

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
    if implementation:
        entry["implementation"] = implementation
        if configuration:
            entry["configuration"] = configuration
    if baseline is not None:
        entry["baseline"] = baseline
    append_entry(entry, ledger_path=ledger_path)
    return entry


def _within(entry: dict[str, Any], field: str, wanted: Optional[str]) -> bool:
    """Whether an entry is in scope for a field: unscoped reads and unnamed entries always are."""
    return wanted is None or entry.get(field) in (None, wanted)


def _resets(reset: dict[str, Any], entry: dict[str, Any]) -> bool:
    """Whether a baseline reset covers an entry: what the reset names is what the entry refined."""
    return all(reset.get(field) in (None, entry.get(field)) for field in TARGET_FIELDS)


def entries_since_last_baseline_reset(
    ledger_path: Optional[Union[Path, str]] = None,
    implementation: Optional[str] = None,
    configuration: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Return the experiment entries no later baseline-reset checkpoint covers
    (checkpoints themselves are excluded), in file order.

    A checkpoint that names nothing covers every entry before it. One that
    names an implementation, or an implementation and a configuration, covers
    only the earlier entries that refined that: one implementation's reset
    leaves another's history standing, and one configuration's leaves the same
    implementation's other configurations standing.

    With an `implementation` (and a `configuration`), only the entries of that
    implementation (with that configuration) are returned, plus those written
    before entries named either.

    Every ledger read that feeds a loop decision should be scoped through
    this function instead of `read_entries` directly, so pre-reset entries
    never silently influence a post-reset decision.
    """
    entries = read_entries(ledger_path)
    live: list[dict[str, Any]] = []
    # Walk backwards, so each entry meets only the resets recorded after it
    later_resets: list[dict[str, Any]] = []
    for entry in reversed(entries):
        if entry.get("decision") == BASELINE_RESET_DECISION:
            later_resets.append(entry)
            continue
        if not _within(entry, "implementation", implementation):
            continue
        if not _within(entry, "configuration", configuration):
            continue
        if any(_resets(reset, entry) for reset in later_resets):
            continue
        live.append(entry)
    live.reverse()
    return live


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


def _decided_hypotheses(
    decision: str,
    ledger_path: Optional[Union[Path, str]],
    implementation: Optional[str],
    configuration: Optional[str],
) -> list[str]:
    """Distinct hypotheses with that decision since the last reset, in first-seen order."""
    seen: list[str] = []
    for entry in entries_since_last_baseline_reset(ledger_path, implementation, configuration):
        hypothesis = entry.get("hypothesis")
        if entry.get("decision") == decision and hypothesis is not None and hypothesis not in seen:
            seen.append(hypothesis)
    return seen


def rejected_hypotheses(
    ledger_path: Optional[Union[Path, str]] = None,
    implementation: Optional[str] = None,
    configuration: Optional[str] = None,
) -> list[str]:
    """
    Return the distinct `hypothesis` strings of every rejected experiment
    recorded since the last baseline reset, in first-seen order.

    Hypothesis ids are scoped by implementation and configuration: pass what
    is being refined to get its rejections only. Without either, everyone's
    are returned.

    Target selection (§4.3 step 2) excludes these until the next baseline
    reset. Rejections recorded before a baseline reset (e.g. against the
    retired placeholder ontology) are scoped out entirely: see
    `entries_since_last_baseline_reset`. An "unmeasured" entry is not a
    rejection and is not returned.
    """
    return _decided_hypotheses("rejected", ledger_path, implementation, configuration)


def accepted_hypotheses(
    ledger_path: Optional[Union[Path, str]] = None,
    implementation: Optional[str] = None,
    configuration: Optional[str] = None,
) -> list[str]:
    """
    Return the distinct `hypothesis` strings of every accepted experiment
    recorded since the last baseline reset, in first-seen order, scoped by
    implementation and configuration as `rejected_hypotheses` is.

    Target selection (§4.3 step 2) excludes these: an accepted hypothesis is
    already merged into the incumbent, so re-drafting it produces a candidate
    the accept gate can only reject (it cannot beat an incumbent that already
    contains it) — a wasted iteration. Acceptances recorded before a baseline
    reset are scoped out (see `entries_since_last_baseline_reset`), so an
    ontology/corpus swap makes a previously-merged hypothesis retryable again,
    since the incumbent it was merged into no longer exists.
    """
    return _decided_hypotheses("accepted", ledger_path, implementation, configuration)


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

    for command, decided in (
        ("rejected-hypotheses", "rejected"),
        ("accepted-hypotheses", "accepted"),
    ):
        decided_parser = subparsers.add_parser(
            command, help=f"Print {decided} hypotheses, one per line"
        )
        decided_parser.add_argument(
            "--implementation",
            default=None,
            help="The implementation being refined: hypothesis ids are scoped by it."
            " Omit for every implementation's",
        )
        decided_parser.add_argument(
            "--configuration",
            default=None,
            help="The configuration it is measured with: ids are scoped by it too."
            " Omit for every configuration's",
        )

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
    baseline_reset_parser.add_argument(
        "--implementation",
        default=None,
        help="Reset this implementation's history only; omit to reset every implementation's",
    )
    baseline_reset_parser.add_argument(
        "--configuration",
        default=None,
        help="The configuration that implementation is measured with",
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
        for hypothesis in rejected_hypotheses(
            args.ledger_path, args.implementation, args.configuration
        ):
            print(hypothesis)
        return 0

    if args.command == "accepted-hypotheses":
        for hypothesis in accepted_hypotheses(
            args.ledger_path, args.implementation, args.configuration
        ):
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
            implementation=args.implementation,
            configuration=args.configuration,
        )
        path = args.ledger_path or LEDGER_PATH
        print(f"appended baseline-reset checkpoint '{entry['experiment_id']}' to {path}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(_main())
