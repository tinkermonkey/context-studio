"""
The metadata header of an experiment page (documentation/extraction/experiments/).

Each page opens with a small header between `---` lines, one `key: value` per
line, so the catalogue can be listed and checked by a script:

    ---
    date: 2026-11-15
    kind: experiment
    implementations: [find_then_type]
    models: [claude-haiku-5-5, claude-opus-5-5]
    takes: 3
    cost_usd: 6.01
    verdict: open
    reproducible: yes
    ---

Values are a word or date, a number, `null`, or a list in brackets. The fields,
and what each may hold, are FIELDS below; the rules are in the experiments
README ("Recording an experiment").

Usage (from local-server/):

    python experiments/page_metadata.py check     # every page has a valid header
    python experiments/page_metadata.py list      # one line per page
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Optional, Union

EXPERIMENTS_DIR = (
    Path(__file__).resolve().parents[2] / "documentation" / "extraction" / "experiments"
)
NOT_PAGES = ("README.md", "_template.md")

KINDS = ("experiment", "loop-campaign", "review", "history")
VERDICTS = ("adopted", "rejected", "inconclusive", "lead", "open", "running", "n/a")
REPRODUCIBLE = ("yes", "partly", "no", "n/a")

# Field -> what it holds, in the order a header lists them.
FIELDS = {
    "date": "the day the experiment started, YYYY-MM-DD",
    "kind": " | ".join(KINDS),
    "implementations": (
        "the implementations it ran, a list (empty for a prototype outside the registry)"
    ),
    "models": "the models it called, a list",
    "takes": "takes per arm, a number, or null when it does not apply",
    "cost_usd": "what it spent in dollars, a number, or null when not recorded",
    "verdict": " | ".join(VERDICTS),
    "reproducible": " | ".join(REPRODUCIBLE)
    + " (yes: replays from the repository; partly: some of it; no: scratch)",
}

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WORD = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/+-]*$")


class MetadataError(ValueError):
    """Raised when a page's header is missing or not as FIELDS describes."""


def _value(text: str) -> Any:
    text = text.strip()
    if text == "null":
        return None
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        return [item.strip() for item in inner.split(",")] if inner else []
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def _format(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, list):
        return "[" + ", ".join(str(item) for item in value) + "]"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def split(text: str) -> tuple[Optional[dict[str, Any]], str]:
    """A page's header (None when it has none) and the text after it."""
    lines = text.split("\n")
    if not lines or lines[0] != "---":
        return None, text
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise MetadataError("the header has no closing `---`") from exc
    header: dict[str, Any] = {}
    for line in lines[1:end]:
        key, sep, value = line.partition(":")
        if not sep:
            raise MetadataError(f"not a `key: value` line in the header: {line!r}")
        header[key.strip()] = _value(value)
    body = "\n".join(lines[end + 1 :])
    return header, body.lstrip("\n")


def render(header: dict[str, Any]) -> str:
    """A header as the page holds it, fields in FIELDS order."""
    lines = ["---"] + [f"{key}: {_format(header[key])}" for key in FIELDS] + ["---"]
    return "\n".join(lines) + "\n\n"


def with_header(text: str, header: dict[str, Any]) -> str:
    """A page's text with its header replaced (or added)."""
    validate(header)
    _, body = split(text)
    return render(header) + body


def validate(header: Optional[dict[str, Any]]) -> None:
    """Raise MetadataError unless the header holds exactly FIELDS, each as described."""
    if header is None:
        raise MetadataError("the page has no metadata header")
    missing = [key for key in FIELDS if key not in header]
    extra = [key for key in header if key not in FIELDS]
    if missing or extra:
        raise MetadataError(f"header fields: missing {missing}, unknown {extra}")
    if not isinstance(header["date"], str) or not DATE.match(header["date"]):
        raise MetadataError(f"`date` is not YYYY-MM-DD: {header['date']!r}")
    for key, allowed in (("kind", KINDS), ("verdict", VERDICTS), ("reproducible", REPRODUCIBLE)):
        if header[key] not in allowed:
            raise MetadataError(f"`{key}` is {header[key]!r}, not one of {', '.join(allowed)}")
    for key in ("implementations", "models"):
        value = header[key]
        if not isinstance(value, list) or not all(
            isinstance(v, str) and WORD.match(v) for v in value
        ):
            raise MetadataError(f"`{key}` is not a list of names: {value!r}")
    takes = header["takes"]
    if takes is not None and (not isinstance(takes, int) or takes < 1):
        raise MetadataError(f"`takes` is not a whole number of at least 1, or null: {takes!r}")
    cost = header["cost_usd"]
    if cost is not None and (not isinstance(cost, (int, float)) or cost < 0):
        raise MetadataError(f"`cost_usd` is not a number of dollars, or null: {cost!r}")


def pages(directory: Optional[Union[Path, str]] = None) -> list[Path]:
    """The experiment pages: every markdown file but the README and the template."""
    folder = Path(directory) if directory is not None else EXPERIMENTS_DIR
    return sorted(p for p in folder.glob("*.md") if p.name not in NOT_PAGES)


def check(directory: Optional[Union[Path, str]] = None) -> list[str]:
    """One problem per page whose header is missing or invalid; empty when all are valid."""
    problems = []
    for page in pages(directory):
        try:
            header, _ = split(page.read_text())
            validate(header)
            # A page is named after its date; a history page spans months, so only its month
            prefix = header["date"][:7] if header["kind"] == "history" else header["date"]
            if not page.name.startswith(prefix):
                raise MetadataError(f"`date` {header['date']} does not match the file name")
        except MetadataError as exc:
            problems.append(f"{page.name}: {exc}")
    return problems


def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Experiment page metadata headers.")
    parser.add_argument("command", choices=("check", "list"))
    parser.add_argument(
        "--dir", default=None, help="Experiments folder (default: the repository's)"
    )
    args = parser.parse_args(argv)
    if args.command == "check":
        problems = check(args.dir)
        for problem in problems:
            print(f"ERROR: {problem}", file=sys.stderr)
        if not problems:
            print(f"{len(pages(args.dir))} pages, every header valid")
        return 1 if problems else 0
    for page in pages(args.dir):
        header, _ = split(page.read_text())
        if header is None:
            print(f"{page.name}  (no header)")
            continue
        print(
            f"{page.name}  {header.get('kind')}  {_format(header.get('implementations'))}"
            f"  takes {_format(header.get('takes'))}  ${_format(header.get('cost_usd'))}"
            f"  {header.get('verdict')}  reproducible {header.get('reproducible')}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(_main())
