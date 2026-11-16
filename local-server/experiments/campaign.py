"""
The record of a refinement-loop campaign, written from the ledger.

A campaign is consecutive Loop C iterations against one implementation and
configuration, from one driver (`.claude/workflows/karpathy-loop.js`). Its
record has three levels, each written from the one before it:

1. the ledger (`experiments/ledger.jsonl`): one entry per decided hypothesis,
   for machines;
2. the campaign's experiment page
   (`documentation/extraction/experiments/YYYY-MM-DD-loop-<implementation>[-<configuration>][-N].md`)
   and its row in the experiments index, for people;
3. the current-state page (`documentation/extraction/README.md`): only a lead
   line and the "As of" date, on an accept.

A loop accept is one take judged by a margin below the noise threshold: a
lead, not a result. It never moves a number on the current-state page; it is
listed under "Leads from the refinement loop" until a three-take experiment
confirms it.

The workflow's record step runs this script once per iteration (and once more,
with no entries, when the loop stops before deciding anything), inside a
worktree of the loop's integration branch, and commits what it wrote together
with the ledger append, so all three reach `main` when that branch is promoted.
It does the mechanical parts, so they cannot drift from the ledger:

- appends the iteration's ledger entries, stamped with the campaign's name and
  the date, skipping any the ledger already holds (a re-run is a no-op);
- creates the campaign's page on its first iteration (the sections of
  `experiments/_template.md`, filled from the request); a second campaign on
  the same day gets the next free name (`-2`, `-3`);
- regenerates the page's results table and verdict between their markers
  (`<!-- loop:results:start -->` ... `<!-- loop:results:end -->`, and the same
  for `verdict`) from every entry of the campaign, whatever baseline reset came
  between, so whatever is written outside them survives;
- adds or updates the campaign's one row in the experiments index;
- on an accept that was merged, adds or updates its line between the
  `<!-- loop:leads:... -->` markers of the current-state page and its "As of"
  date.

The short narrative lines (one note per iteration, and "What we know" when an
accept changes it) are left to the record step's agent.

Usage (from local-server/; the request is JSON on standard input):

    python experiments/campaign.py [--also-ledger <the main checkout's ledger>] <<'RECORD_EOF'
    {"implementation": "find_then_type", "configuration": "extraction-find-then-type",
     "model": "claude-haiku-5-5", "page": null, "page_suffix": "loop-find_then_type",
     "iteration": 1, "entries": [...], "accepted_hypothesis": null,
     "margins": {...}, "budget_usd": 20, "stop": null}
    RECORD_EOF

It prints what it did as JSON: the page (a path from the repository root), whether
it was created, how many entries it appended and skipped, the index row and
whether a lead was recorded. It writes nothing when the request or a page it
would edit is not as expected, and exits 1 saying why.
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Callable, Optional, Union

# Run as a script (`python experiments/campaign.py` from local-server/), the
# script's own directory is on the path, not local-server/.
sys.path.append(str(Path(__file__).resolve().parents[1]))

from experiments.ledger import (
    ACCEPT_UNMERGED_DECISION,
    LEDGER_PATH,
    UNMEASURED_DECISION,
    append_entry,
    entry_identity,
    read_entries,
    render_table,
    table_cell,
    target_entries,
    validate_entry,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_RELATIVE = Path("documentation") / "extraction"
DOCS_ROOT = REPO_ROOT / DOCS_RELATIVE
EXPERIMENTS_DIR = "experiments"
INDEX_NAME = "README.md"
CURRENT_STATE_NAME = "README.md"

PAGE_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}-loop-[A-Za-z0-9][A-Za-z0-9_.+-]*\.md$")
PAGE_SUFFIX = re.compile(r"^loop-[A-Za-z0-9][A-Za-z0-9_.+-]*$")
TARGET_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+-]*$")
AS_OF = re.compile(r"\*\*As of \d{4}-\d{2}-\d{2}\.\*\*")
INDEX_HEADER = "| date | page |"
NO_LEADS = "None yet."

# What a loop iteration can record (a baseline reset is not the loop's to write).
RECORDED_DECISIONS = ("accepted", "rejected", UNMEASURED_DECISION, ACCEPT_UNMERGED_DECISION)

# The sections every experiment page has, in order (experiments/_template.md).
SECTIONS = (
    "Question",
    "Decision rule (set in advance)",
    "Method",
    "Results",
    "Limits",
    "Verdict",
    "Reproduce",
    "Links",
)

NOTES_HEADING = "Notes, one line per iteration (written by the loop):"


class CampaignRecordError(ValueError):
    """Raised when a request, or a page the record would edit, is not as expected."""


def _start(name: str) -> str:
    return f"<!-- loop:{name}:start -->"


def _end(name: str) -> str:
    return f"<!-- loop:{name}:end -->"


def _block(text: str, name: str) -> tuple[str, str, str]:
    """A generated block's text before its start marker, inside, and after its end marker."""
    start, end = _start(name), _end(name)
    if text.count(start) != 1 or text.count(end) != 1 or text.index(start) > text.index(end):
        raise CampaignRecordError(f"the page does not hold exactly one `{start}` ... `{end}` block")
    before, rest = text.split(start, 1)
    inside, after = rest.split(end, 1)
    return before, inside, after


def replace_block(text: str, name: str, body: str) -> str:
    """Replace what is between a generated block's markers; everything else is kept."""
    before, _, after = _block(text, name)
    return f"{before}{_start(name)}\n{body}\n{_end(name)}{after}"


def _prose(value: Any) -> str:
    """Free text placed in a page: one line, and no marker of a generated block."""
    return table_cell(value).replace("<!--", "&lt;!--")


def _row(cells: list[str]) -> str:
    return "| " + " | ".join(table_cell(cell) for cell in cells) + " |"


def _decided(entries: list[dict[str, Any]], decision: str) -> list[dict[str, Any]]:
    return [entry for entry in entries if entry.get("decision") == decision]


def _counts(entries: list[dict[str, Any]]) -> str:
    counts = (
        f"{len(_decided(entries, 'accepted'))} accepted (leads), "
        f"{len(_decided(entries, 'rejected'))} rejected, "
        f"{len(_decided(entries, UNMEASURED_DECISION))} unmeasured"
    )
    unmerged = len(_decided(entries, ACCEPT_UNMERGED_DECISION))
    return counts + (f", {unmerged} accepted but not merged" if unmerged else "")


def _iterations(entries: list[dict[str, Any]]) -> int:
    return len({entry.get("iteration") for entry in entries})


def _typed(entry: dict[str, Any], group: str, side: Optional[str] = None) -> Optional[float]:
    """Typed F1 of the candidate, or of the incumbent it was compared with."""
    measured = (entry.get("incumbent") or {}) if side == "incumbent" else entry
    measures = measured.get(group)
    value = measures.get("typed_f1") if isinstance(measures, dict) else None
    return value if isinstance(value, (int, float)) else None


def _number(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def _provisional(entries: list[dict[str, Any]]) -> bool:
    return any((entry.get("margins") or {}).get("provisional") for entry in entries)


def _hypotheses(entries: list[dict[str, Any]], with_iteration: bool = True) -> str:
    return ", ".join(
        f"`{entry['hypothesis']}`"
        + (f" (iteration {entry.get('iteration')})" if with_iteration else "")
        for entry in entries
    )


def summary_line(entries: list[dict[str, Any]]) -> str:
    """How many iterations and decisions the campaign has, and what its recordings cost."""
    cost = sum(e["cost_usd"] for e in entries if isinstance(e.get("cost_usd"), (int, float)))
    return (
        f"{_iterations(entries)} iteration(s) recorded: {_counts(entries)}. Recording cost "
        f"${cost:.2f}, as the experimenters estimated it (agent tokens are not counted)."
    )


def results_block(entries: list[dict[str, Any]]) -> str:
    """The generated part of Results: the summary and one row per ledger entry."""
    return (
        f"{summary_line(entries)} Each candidate is one take against one take of the incumbent "
        "(dev typed F1 and holdout typed F1 as `incumbent → candidate`).\n\n"
        f"{render_table(entries)}"
    )


def verdict_text(entries: list[dict[str, Any]], stop: Optional[str]) -> str:
    """
    The campaign's verdict. An accept is a lead (one take), never "adopted": it
    counts once a three-take experiment confirms it. A candidate that passed the
    gate but was not merged is neither.
    """
    leads = _decided(entries, "accepted")
    unmerged = _decided(entries, ACCEPT_UNMERGED_DECISION)
    parts = []
    if leads:
        parts.append(
            f"Lead (one take): {_hypotheses(leads)}, merged to the integration branch; confirm"
            " with three takes before it counts."
        )
    if unmerged:
        parts.append(
            f"Passed the accept gate but not merged, so not a lead: {_hypotheses(unmerged)}."
        )
    if not parts:
        if not stop:
            parts.append("Running: no change accepted yet.")
        elif entries and all(e.get("decision") == UNMEASURED_DECISION for e in entries):
            parts.append("Inconclusive: no candidate could be measured.")
        elif entries:
            parts.append("Rejected: no change passed the accept gate.")
        else:
            parts.append("Inconclusive: nothing was decided.")
    if stop:
        parts.append(f"Stopped: {_prose(stop)}.")
    if _provisional(entries):
        parts.append("Judged under provisional margins.")
    return " ".join(parts)


def index_cells(
    request: dict[str, Any],
    name: str,
    model: str,
    entries: list[dict[str, Any]],
    stop: Optional[str],
) -> list[str]:
    """The campaign's row in the experiments index: date, page, question, result, verdict."""
    implementation, configuration = request["implementation"], request["configuration"]
    named = f"`{implementation}`"
    if request["page_suffix"] != f"loop-{implementation}":
        named = f"{named} with `{configuration}`"
    result = f"{_iterations(entries)} iteration(s): {_counts(entries)}"
    leads = _decided(entries, "accepted")
    if leads:
        first, last = leads[0], leads[-1]
        result += (
            f"; lead dev typed F1 {_number(_typed(first, 'dev', 'incumbent'))} → "
            f"{_number(_typed(last, 'dev'))} (one take)"
        )
    unmerged = _decided(entries, ACCEPT_UNMERGED_DECISION)
    if leads:
        verdict = f"Lead (one take): {_hypotheses(leads, False)}; confirm with three takes"
    elif unmerged:
        verdict = f"Not merged: {_hypotheses(unmerged, False)}; no lead"
    elif not stop:
        verdict = "Running"
    elif entries and all(e.get("decision") == UNMEASURED_DECISION for e in entries):
        verdict = "Inconclusive: nothing could be measured"
    elif entries:
        verdict = "Rejected: no change passed the accept gate"
    else:
        verdict = "Inconclusive: nothing was decided"
    if stop:
        verdict += " (stopped)"
    if _provisional(entries):
        verdict += " (provisional margins)"
    return [
        name[:10],
        f"[Loop: {named}]({name})",
        f"Can the refinement loop improve {named} ({model}) on the benchmark?",
        result,
        verdict,
    ]


def upsert_index_row(text: str, name: str, cells: list[str]) -> tuple[str, str]:
    """Put the campaign's row in the index table: replace its row, or add it at the end."""
    lines = text.split("\n")
    header = next((i for i, line in enumerate(lines) if line.startswith(INDEX_HEADER)), None)
    if header is None:
        raise CampaignRecordError(f"the experiments index has no table starting `{INDEX_HEADER}`")
    last = header
    while last + 1 < len(lines) and lines[last + 1].startswith("|"):
        last += 1
    link = f"]({name})"
    rows = [i for i in range(header + 2, last + 1) if link in lines[i]]
    if len(rows) > 1:
        raise CampaignRecordError(f"the experiments index has {len(rows)} rows for {name}")
    if rows:
        lines[rows[0]] = _row(cells)
        return "\n".join(lines), "updated"
    lines.insert(last + 1, _row(cells))
    return "\n".join(lines), "added"


def add_lead(
    text: str, request: dict[str, Any], entry: dict[str, Any], name: str, model: str, today: str
) -> str:
    """
    After an accept that was merged: its line among the leads of the current-state
    page (one per implementation, configuration and hypothesis; added, or
    replaced when the same hypothesis is accepted again) and the "As of" date.
    No number elsewhere on the page changes: a lead is one take.
    """
    if len(AS_OF.findall(text)) != 1:
        raise CampaignRecordError("the current-state page has no single `**As of YYYY-MM-DD.**`")
    before, inside, after = _block(text, "leads")
    implementation, configuration = request["implementation"], request["configuration"]
    key = f"- `{implementation}` with `{configuration}`: `{entry['hypothesis']}`"
    line = (
        f"{key} (iteration {entry.get('iteration')}, {today}): dev typed F1"
        f" {_number(_typed(entry, 'dev', 'incumbent'))} → {_number(_typed(entry, 'dev'))},"
        f" holdout typed F1 {_number(_typed(entry, 'holdout', 'incumbent'))} →"
        f" {_number(_typed(entry, 'holdout'))}, one take with {model};"
        f" [campaign]({EXPERIMENTS_DIR}/{name}). To confirm with three takes."
    )
    lines = [kept for kept in inside.strip("\n").split("\n") if kept.strip() not in ("", NO_LEADS)]
    replaced = [line if kept.startswith(f"{key} ") else kept for kept in lines]
    if replaced == lines:
        replaced.append(line)
    text = f"{before}{_start('leads')}\n" + "\n".join(replaced) + f"\n{_end('leads')}{after}"
    return AS_OF.sub(f"**As of {today}.**", text)


def _decision_rule(margins: dict[str, Any], base_commit: str) -> str:
    guard = margins.get("guard_slack")
    guard_line = (
        f"the triple-corpus guard: its dev strict-F1 down by at most {guard};"
        if isinstance(guard, (int, float))
        else "the triple-corpus guard: not applicable to this target (no recordings of it);"
    )
    if margins.get("provisional"):
        status = (
            f"These margins are **provisional**: set from {margins.get('basis')}. Still to "
            f"measure: {margins.get('missing')}. An accept or a reject under them is not yet a "
            "trusted verdict."
        )
    else:
        status = f"These margins are measured: {margins.get('basis')}."
    return "\n".join(
        [
            "The loop's accept gate (`acceptGate` and `GATE_MARGINS` in",
            "`.claude/workflows/karpathy-loop.js`), fixed in code before the campaign started"
            f" (first iteration's base commit `{base_commit[:8]}`). A candidate is compared with"
            " the incumbent on `main`:",
            "",
            f"- dev documents: found F1 up by more than ε = {margins.get('epsilon')} with typed F1"
            " not down, or typed F1 up by more than ε with found F1 down by at most"
            f" {margins.get('coverage_slack')};",
            f"- the holdout document's typed F1 down by at most {margins.get('holdout_slack')}"
            " (a veto only; it never chooses);",
            f"- {guard_line}",
            "- every other recorded benchmark target's dev typed F1 down by no more than its own ε;"
            " a candidate measured with another model is not judged;",
            "- of the candidates that pass, the one with the highest dev typed F1 is accepted, one"
            " per iteration. Scores are compared in whole ten-thousandths.",
            "",
            "An accept is one take judged by a margin below the noise threshold: a lead, not a"
            " result. It is listed among the leads of the current state and counts only when a"
            " three-take experiment confirms it.",
            "",
            status,
        ]
    )


def new_page(request: dict[str, Any], name: str, model: str, base_commit: str) -> str:
    """A campaign's page, with the sections of experiments/_template.md, on its first iteration."""
    implementation, configuration = request["implementation"], request["configuration"]
    flags = f"--implementation {implementation} --configuration {configuration}"
    stem = name[: -len(".md")]
    budget = request.get("budget_usd")
    budget_line = (
        f"${budget} for the campaign (checked before each iteration, so the last can overrun it)"
        if isinstance(budget, (int, float))
        else "no cap set"
    )
    provisional = (request.get("margins") or {}).get("provisional")
    sections = {
        "Question": (
            f"Can changes from the loop's backlog for `{implementation}` (`BACKLOGS` in the"
            f" workflow) improve it, run with `{configuration}` ({model}), on the extraction"
            " benchmark?"
        ),
        "Decision rule (set in advance)": _decision_rule(request.get("margins") or {}, base_commit),
        "Method": "\n".join(
            [
                f"- Implementation `{implementation}`, configuration `{configuration}`, model"
                f" {model}.",
                "- Documents: the extraction benchmark, `edit_check` and `gitlab_architecture`"
                " (dev), `wikimedia_enterprise` (holdout).",
                "- Takes: one recording per candidate, against the incumbent's committed recording"
                " on `main`: a single take each.",
                f"- Budget: {budget_line}. Actual cost: the summary under Results.",
            ]
        ),
        "Results": "\n".join(
            [_start("results"), results_block([]), _end("results"), "", NOTES_HEADING, ""]
        ),
        "Limits": "\n".join(
            [
                "- Every candidate is one take. An accept is a lead until three takes confirm it"
                " against the noise threshold stated in the"
                " [current state](../README.md#how-quality-is-measured).",
                "- The gold is model-made and the benchmark has three documents.",
            ]
            + (
                ["- The gate margins are provisional (see the decision rule)."]
                if provisional
                else []
            )
        ),
        "Verdict": "\n".join([_start("verdict"), verdict_text([], None), _end("verdict")]),
        "Reproduce": "\n".join(
            [
                "From `local-server/`, free and offline:",
                "",
                "```bash",
                f"python scripts/benchmark_replay.py {flags}",
                f"python experiments/ledger.py render {flags} --campaign {stem}",
                "```",
                "",
                "The first replays the incumbent, and an accepted change once it is on `main`."
                " Rejected and unmeasured candidates' branches and recordings are deleted: scratch;"
                " not reproducible from the repository.",
            ]
        ),
        "Links": "\n".join(
            [
                "- Ledger: `local-server/experiments/ledger.jsonl`, the entries with"
                f' `"campaign": "{stem}"`.',
                "- Pull requests: the promotion of the loop's integration branch that carries this"
                " page.",
            ]
        ),
    }
    title = f"# Refinement loop: `{implementation}`"
    if request["page_suffix"] != f"loop-{implementation}":
        title += f" with `{configuration}`"
    intro = (
        f"{title} ({name[:10]})\n\n"
        "A campaign of the refinement loop (Loop C): consecutive iterations against one"
        " implementation and configuration. The loop writes this page at every iteration with"
        " `local-server/experiments/campaign.py`: the results table and the verdict are generated"
        " from the ledger between their `loop:` markers, and the notes are the loop's own words."
        " Edit outside the markers only."
    )
    body = "\n\n".join(f"## {section}\n\n{sections[section]}" for section in SECTIONS)
    return f"{intro}\n\n{body}\n"


def _clean_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value) and not any(c in value for c in "|\r\n")


def _validate(request: dict[str, Any]) -> None:
    if not isinstance(request, dict):
        raise CampaignRecordError("the request is not a JSON object")
    for field in ("implementation", "configuration"):
        value = request.get(field)
        if not isinstance(value, str) or not TARGET_NAME.match(value):
            raise CampaignRecordError(f"`{field}` is not a registry name: {value!r}")
    if not PAGE_SUFFIX.match(str(request.get("page_suffix") or "")):
        raise CampaignRecordError(
            f"`page_suffix` is not `loop-<name>`: {request.get('page_suffix')!r}"
        )
    if request.get("model") is not None and not _clean_text(request["model"]):
        raise CampaignRecordError(f"`model` must be one line without `|`: {request['model']!r}")
    if request.get("stop") is not None and not isinstance(request["stop"], str):
        raise CampaignRecordError("`stop` must be a string or null")
    entries = request.get("entries")
    if not isinstance(entries, list):
        raise CampaignRecordError("the request has no `entries` list")
    for position, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise CampaignRecordError(f"entries[{position}] is not a JSON object")
        validate_entry(entry)
        if entry["decision"] not in RECORDED_DECISIONS:
            raise CampaignRecordError(
                f"entries[{position}]: an iteration does not record {entry['decision']!r}"
            )
        if not isinstance(entry.get("hypothesis"), str) or not entry["hypothesis"]:
            raise CampaignRecordError(f"entries[{position}] has no hypothesis id")
        target = (entry.get("implementation"), entry.get("configuration"))
        if target != (request["implementation"], request["configuration"]):
            raise CampaignRecordError(
                f"entry {entry.get('experiment_id')!r} is not of the campaign's target"
            )
    accepted = request.get("accepted_hypothesis")
    if accepted is not None and not any(
        e.get("hypothesis") == accepted and e.get("decision") == "accepted" for e in entries
    ):
        raise CampaignRecordError(f"no accepted entry for `{accepted}` in this request")


def page_name(
    request: dict[str, Any],
    today: str,
    experiments: Path,
    recorded: Callable[[str], bool] = lambda stem: False,
) -> str:
    """
    The campaign's page: the one threaded through the workflow, else today's,
    with the next free number when today's is taken by another campaign. A page
    whose campaign already holds this request's entries (`recorded(stem)`) is
    this campaign's: the request is a re-run, not a new campaign.
    """
    page = request.get("page")
    if page:
        name = Path(page).name
        if Path(page) != DOCS_RELATIVE / EXPERIMENTS_DIR / name or not PAGE_NAME.match(name):
            raise CampaignRecordError(f"not a campaign page: {page}")
        return name
    base = f"{today}-{request['page_suffix']}"
    name, number = f"{base}.md", 2
    while (experiments / name).exists() and not recorded(name[: -len(".md")]):
        name, number = f"{base}-{number}.md", number + 1
    if not PAGE_NAME.match(name):
        raise CampaignRecordError(f"not a campaign page name: {name!r}")
    return name


def record(
    request: dict[str, Any],
    today: Optional[str] = None,
    docs_root: Optional[Union[Path, str]] = None,
    ledger_path: Optional[Union[Path, str]] = None,
    also_ledger: Optional[Union[Path, str]] = None,
) -> dict[str, Any]:
    """
    Record one iteration of a campaign: append its entries, then write the
    campaign's page, its index row and, on an accept that was merged, its lead
    on the current-state page.

    `ledger_path` is the ledger written to; `also_ledger` another read with it
    (the main checkout's, when this runs on the integration branch), so an
    entry either already holds is not appended again. With no entries the
    request only records a stop: the page must exist.

    Every text is built before anything is written, so a request or a page that
    is not as expected leaves the ledger and the pages as they were.
    """
    today = today or date.today().isoformat()
    root = Path(docs_root) if docs_root is not None else DOCS_ROOT
    primary = Path(ledger_path) if ledger_path is not None else LEDGER_PATH
    reads = [primary, Path(also_ledger)] if also_ledger is not None else primary
    _validate(request)
    experiments = root / EXPERIMENTS_DIR
    held = {(e.get("campaign"), e.get("experiment_id")) for e in read_entries(reads)}
    name = page_name(
        request,
        today,
        experiments,
        lambda stem: any((stem, e["experiment_id"]) in held for e in request["entries"]),
    )
    stem = name[: -len(".md")]
    page_path = experiments / name
    created = not page_path.exists()
    if created and not request["entries"]:
        raise CampaignRecordError(f"nothing to record: no entries, and no page {name} yet")

    implementation, configuration = request["implementation"], request["configuration"]
    recorded = target_entries(implementation, configuration, reads, campaign=stem)
    known = {entry_identity(entry) for entry in recorded}
    fresh, skipped = [], 0
    for entry in request["entries"]:
        stamped = {**entry, "campaign": stem, "date": today}
        if entry_identity(stamped) in known:
            skipped += 1
            continue
        known.add(entry_identity(stamped))
        fresh.append(stamped)
    entries = recorded + fresh
    model = request.get("model") or next(
        (e.get("incumbent_model") or e.get("model") for e in reversed(entries) if e.get("model")),
        None,
    )
    if not _clean_text(model):
        raise CampaignRecordError("no `model` in the request, and none in the campaign's entries")
    stop = request.get("stop") or None

    if created:
        base_commit = str(entries[0].get("base_commit") or "unknown")
        page = new_page(request, name, model, base_commit)
    else:
        page = page_path.read_text()
    page = replace_block(page, "results", results_block(entries))
    page = replace_block(page, "verdict", verdict_text(entries, stop))

    index_path = experiments / INDEX_NAME
    index, index_row = upsert_index_row(
        index_path.read_text(), name, index_cells(request, name, model, entries, stop)
    )

    current_state = None
    accepted = request.get("accepted_hypothesis")
    # The latest accept of that hypothesis: this iteration's, or on a re-run the one recorded.
    lead = next(
        (
            e
            for e in reversed(entries)
            if e["hypothesis"] == accepted and e["decision"] == "accepted"
        ),
        None,
    )
    if accepted and lead is not None:
        current_state_path = root / CURRENT_STATE_NAME
        current_state = add_lead(current_state_path.read_text(), request, lead, name, model, today)

    for entry in fresh:
        append_entry(entry, ledger_path=primary)
    page_path.write_text(page)
    index_path.write_text(index)
    if current_state is not None:
        (root / CURRENT_STATE_NAME).write_text(current_state)
    return {
        "page": str(DOCS_RELATIVE / EXPERIMENTS_DIR / name),
        "created": created,
        "appended": len(fresh),
        "skipped": skipped,
        "index_row": index_row,
        "lead_recorded": current_state is not None,
    }


def _main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point: see the module docstring."""
    parser = argparse.ArgumentParser(
        description="Record one refinement-loop iteration: ledger, campaign page, index, leads."
    )
    parser.add_argument("--docs-root", default=None, help="Override documentation/extraction/")
    parser.add_argument("--ledger-path", default=None, help="Override experiments/ledger.jsonl")
    parser.add_argument(
        "--also-ledger",
        default=None,
        help="Another ledger read with it (the main checkout's): entries it holds are skipped",
    )
    parser.add_argument("--today", default=None, help="Override today's date (YYYY-MM-DD)")
    args = parser.parse_args(argv)
    try:
        request = json.loads(sys.stdin.read())
    except json.JSONDecodeError as exc:
        print(f"ERROR: the request is not valid JSON: {exc}", file=sys.stderr)
        return 1
    try:
        outcome = record(request, args.today, args.docs_root, args.ledger_path, args.also_ledger)
    except (ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(outcome))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
