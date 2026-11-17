"""
Relationship extraction on the extraction benchmark, measured (2026-11-17).

Every arm relates individuals with the relationship types the schema allows
between their classes (a (domain, predicate, range) triple of the DR spec),
and is scored by tests/integration/pipelines/_harness/benchmark.py on what it
keeps. The page is documentation/extraction/experiments/2026-11-17-relationships.md.

- R0: `find_then_type`'s relate stage (per chunk, offered the predicates each
  subject class allows, configuration `extraction-find-then-type`, Claude
  Haiku 5.5) through the real pipeline (chunking, relate, recognition, merge,
  planning) over the individuals of arm B's take of the same index (one Opus
  5.5 call). The find and type stages are answered from that take, not called
  (GivenIndividualsService): an individual is mentioned in each chunk its
  quote overlaps, and in each chunk its title appears in. This is what the
  planned default (`single_call`) does.
- R1: arm B's one Opus 5.5 call, with the allowed relationship types (all 987,
  by source class) added to its system text.
- R2-haiku, R2-opus: one call over the whole document, given the individuals
  of arm B's take of the same index with their classes and the relationship
  types allowed among those classes.
- Diagnostics, one take each, labelled `-gold`: R0 and R2 given the gold
  individuals, to separate relationship errors from individual errors.

R1 and R2 takes are marked `relationships_validated`: a relationship that is
not an allowed type for the classes of its ends is dropped when scored, and
counted (benchmark_external.predictions). R0's planning drops such
relationships itself.

Takes are saved beside the head-to-head's, in
tests/integration/fixtures/pipelines/extraction_benchmark_external/<arm>/<document>/take<N>.json,
so `python scripts/benchmark_external.py replay` and `report` here re-score
them without calls. Paid calls go to their own ledger with their own budget.

Usage (from local-server/):
    python scripts/benchmark_relationships.py selftest          # offline checks
    python scripts/benchmark_relationships.py prompt --arm R2-opus --document edit_check
    python scripts/benchmark_relationships.py run --arm R1 --take 1 --spend
    python scripts/benchmark_relationships.py record-r0 --take 1 --spend --cassettes <dir>
    python scripts/benchmark_relationships.py report [--json]
"""

import argparse
import asyncio
import functools
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import mean
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.extraction.entities import (  # noqa: E402
    Mention,
    MentionsResult,
    TypingPrompt,
    TypingResult,
)
from domain.extraction.services import ExtractionService  # noqa: E402
from scripts.benchmark_external import (  # noqa: E402
    A_MODEL,
    BENCHMARK_DIR,
    EXTERNAL_DIR,
    LAYER_ORDER,
    SYSTEM_TAIL,
    CallPrompt,
    Ledger,
    _normalized,
    _schema_types,
    a_take_record,
    anthropic_key,
    catalog,
    cost_usd,
    locate,
    run_take,
    score_take,
    system_prompt,
    take_path,
    usage_of,
)
from tests.integration.pipelines._harness.benchmark import (  # noqa: E402
    benchmark_documents,
    load_gold,
)

OPUS, HAIKU = "claude-opus-5-5", "claude-haiku-5-5"
CALL_ARMS = {
    "R1": OPUS,
    "R2-haiku": HAIKU,
    "R2-opus": OPUS,
    "R2-haiku-gold": HAIKU,
    "R2-opus-gold": OPUS,
}
PIPELINE_ARMS = ("R0", "R0-gold")
LEDGER = EXTERNAL_DIR / "ledger-relationships.jsonl"
BUDGET_USD = 20.0
# Requests in flight at once (the organisation's concurrent-request limit is shared)
CONCURRENCY = 2
DEV = ("edit_check", "gitlab_architecture")
HOLDOUT = ("wikimedia_enterprise",)

# ---------------------------------------------------------------- the allowed types


def types_block(classes: set[str] | None = None) -> str:
    """
    The schema's relationship types by source class, as "- source: predicate ->
    targets; ...", all of them or those whose two classes are among `classes`.
    """
    by_source: dict[str, dict[str, list[str]]] = {}
    for domain, predicate, target in sorted(_schema_types()):
        if classes is None or (domain in classes and target in classes):
            by_source.setdefault(domain, {}).setdefault(predicate, []).append(target)
    order = sorted(by_source, key=lambda ref: (LAYER_ORDER.index(ref.split(".")[0]), ref))
    return "\n".join(
        f"- {domain}: "
        + "; ".join(f"{p} -> {', '.join(targets)}" for p, targets in by_source[domain].items())
        for domain in order
    )


TYPES_HEAD = """# Allowed relationship types
A relationship is allowed only when the class of its source, its predicate and the class of
its target form one of the types below. They are listed by the class of the source, as:
predicate -> the classes its target may have.
{types}
"""

# ---------------------------------------------------------------- R1: arm B plus the types

_RULE_START = '- predicate: one predicate from the list above, so that "source predicate target" is'
B_PREDICATE_RULE = _RULE_START + "\n  what the document says;"
R1_PREDICATE_RULE = (
    _RULE_START
    + """
  what the document says and the relationship is one of the allowed relationship types
  for the classes you gave its source and its target. When no allowed type fits what the
  document says about two individuals, leave that relationship out;"""
)


def r1_system() -> str:
    """Arm B's system text with the allowed relationship types and a rule to keep to them."""
    system = system_prompt()
    marker = "\n# What to extract"
    assert system.count(marker) == 1 and system.count(B_PREDICATE_RULE) == 1
    system = system.replace(marker, "\n" + TYPES_HEAD.format(types=types_block()) + marker)
    return system.replace(B_PREDICATE_RULE, R1_PREDICATE_RULE)


def r1_prompt(document_id: str) -> CallPrompt:
    from scripts.benchmark_external import USER_PROMPT, output_schema

    source = (BENCHMARK_DIR / document_id / "source.md").read_text()
    return CallPrompt(r1_system(), USER_PROMPT.format(source=source), output_schema())


# ---------------------------------------------------------------- R2: a relationship stage

R2_SYSTEM = """You are an expert knowledge graph extraction assistant. You are given one document
and the individuals already extracted from it for a model of its subject in the {ontology}
ontology, each with its class. Your task is to list every relationship the document states
between two of these individuals.

{predicates}

{types}
# What to list
List each relationship the document states between two of the given individuals; never one
you only infer. For each give:
- source and target: the titles of two of the given individuals, copied exactly;
- predicate: one predicate from the list above, so that "source predicate target" is what
  the document says and the relationship is one of the allowed relationship types for the
  classes of its source and its target. When no allowed type fits what the document says
  about two individuals, leave that relationship out;
- quote: the exact words of the document that state the relationship, verbatim.
List each relationship once.

Answer with the JSON object the response format asks for."""

R2_USER = """The individuals, each as: title [class reference]
{individuals}

<document>
{source}
</document>"""


def given_individuals(document_id: str, take: int, gold: bool) -> list[dict[str, str]]:
    """What an arm relates: arm B's take of the same index, or the gold individuals."""
    if gold:
        return [
            {"title": g.title, "class": g.class_ref, "quote": g.evidence[0].quote}
            for g in load_gold(document_id).individuals
        ]
    record = json.loads(take_path("B", document_id, take).read_text())
    return [
        {"title": i["title"], "class": i["class"], "quote": i["quote"]}
        for i in record["individuals"]
    ]


def r2_prompt(document_id: str, individuals: list[dict[str, str]]) -> CallPrompt:
    """The whole-document relationship call over the given individuals."""
    classes = {i["class"] for i in individuals}
    allowed = {(d, p, r) for d, p, r in _schema_types() if d in classes and r in classes}
    used = {p for _, p, _ in allowed}
    _, predicates = catalog()
    predicate_lines = "\n".join(
        f"- {p['identifier']}: {p['definition']}" for p in predicates if p["identifier"] in used
    )
    predicates_head = SYSTEM_TAIL.split("\n# What to extract")[0].strip()
    system = R2_SYSTEM.format(
        ontology="Documentation Robotics (DR)",
        predicates=predicates_head.format(predicates=predicate_lines),
        types=TYPES_HEAD.format(types=types_block(classes)),
    )
    titles = list(dict.fromkeys(i["title"] for i in individuals))
    source = (BENCHMARK_DIR / document_id / "source.md").read_text()
    user = R2_USER.format(
        individuals="\n".join(f"- {i['title']} [{i['class']}]" for i in individuals),
        source=source,
    )
    text = {"type": "string"}
    schema = {
        "type": "object",
        "properties": {
            "relationships": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string", "enum": titles},
                        "predicate": {"type": "string", "enum": sorted(used)},
                        "target": {"type": "string", "enum": titles},
                        "quote": text,
                    },
                    "required": ["source", "predicate", "target", "quote"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["relationships"],
        "additionalProperties": False,
    }
    return CallPrompt(system, user, schema)


# ---------------------------------------------------------------- running the call arms


def call_job(
    client: Any, ledger: Ledger, arm: str, document_id: str, take: int, started: threading.Event
) -> None:
    gold = arm.endswith("-gold")
    if arm == "R1":
        prompt, lists = r1_prompt(document_id), ("individuals", "relationships")
        extra = {"relationships_validated": True}
    else:
        individuals = given_individuals(document_id, take, gold)
        prompt, lists = r2_prompt(document_id, individuals), ("relationships",)
        extra = {
            "relationships_validated": True,
            "individuals_from": "gold" if gold else f"B take{take}",
            "individuals": individuals,
        }
    try:
        run_take(
            client,
            ledger,
            arm,
            document_id,
            take,
            started,
            model=CALL_ARMS[arm],
            prompt=prompt,
            lists=lists,
            extra=extra,
        )
    except Exception as exc:  # reported, and the other jobs go on
        started.set()
        print(f"{arm} {document_id} take{take}: ERROR {type(exc).__name__}: {exc}", flush=True)


def run_calls(
    arm: str, jobs: list[tuple[str, int]], ledger: Ledger, concurrency: int = CONCURRENCY
) -> None:
    """
    The jobs not yet saved, `concurrency` at a time; the first alone until its
    prompt is read, so the others read R1's system text from the cache.
    """
    import anthropic

    client = anthropic.Anthropic(api_key=anthropic_key(), max_retries=6, timeout=1800)
    jobs = [j for j in jobs if not take_path(arm, *j).exists()]
    if not jobs:
        return
    first = threading.Event()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(call_job, client, ledger, arm, *jobs[0], first)]
        first.wait()
        futures += [
            pool.submit(call_job, client, ledger, arm, *job, threading.Event()) for job in jobs[1:]
        ]
        for future in futures:
            future.result()


# ---------------------------------------------------------------- R0: the pipeline's relate stage

_WORD = r"(?<![\w-]){}(?![\w-])"


class Placement:
    """
    Where given individuals (title, class, quote) are mentioned in a source's
    chunks: a chunk mentions an individual when the individual's quote, placed
    in the source, overlaps the chunk (the mention's passage is the overlap),
    or else when the chunk holds the individual's title as words of its own.
    """

    def __init__(self, given: list[dict[str, str]], source: str) -> None:
        self.given = given
        self.source = source
        normalized = _normalized(source)
        self.spans = [locate(item["quote"], source, normalized) for item in given]
        self.class_of: dict[str, str] = {}
        for item in given:
            self.class_of.setdefault(item["title"], item["class"])
        self.placed: set[str] = set()

    def mentions(self, text: str) -> list[Mention]:
        """The given individuals a chunk of the source mentions, with passages in the chunk."""
        offset = self.source.find(text)
        assert offset >= 0, "a chunk is a slice of the source"
        mentions = []
        for item, span in zip(self.given, self.spans):
            kind = "statement" if item["class"].startswith("motivation.") else "thing"
            start = end = None
            if span is not None and span.start < offset + len(text) and span.end > offset:
                start = max(span.start, offset) - offset
                end = min(span.end, offset + len(text)) - offset
            else:
                found = re.search(_WORD.format(re.escape(item["title"])), text, re.IGNORECASE)
                if found:
                    start, end = found.span()
            if start is not None and end is not None:
                mentions.append(Mention(item["title"], kind, text[start:end], start, end))
                self.placed.add(item["title"])
        return mentions


class GivenIndividualsService(ExtractionService):
    """
    The extraction service with its find and type stages answered from given
    individuals (Placement) instead of LLM calls; the relate stage, recognition
    and everything else are the service's own.
    """

    def __init__(self, *args: Any, placement: Placement, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.placement = placement

    def find_mentions(
        self,
        text: str,
        ontology_id: str,
        model: str,
        temperature: float,
        stage_prompts: Any = None,
        max_tokens: int | None = None,
    ) -> MentionsResult:
        return MentionsResult(
            self.placement.mentions(text), [], {"model": model, "tokens_used": 0, "duration_ms": 0}
        )

    def typing_prompt(self, ontology_id: str, stage_prompts: Any = None) -> TypingPrompt:
        return TypingPrompt(system="", user="", class_refs={})

    def type_mention(
        self,
        prompt: TypingPrompt,
        context: str,
        mention: Mention,
        model: str,
        temperature: float,
        max_tokens: int | None = None,
    ) -> TypingResult:
        return TypingResult(
            class_ref=self.placement.class_of[mention.name],
            confidence=1.0,
            metadata={"model": model, "tokens_used": 0, "duration_ms": 0},
        )


def record_r0(take: int, documents: list[str], gold: bool, cassettes: Path, ledger: Ledger):
    """A take of R0 (or R0-gold) through the real pipeline, every relate call metered."""
    from adapters.llm.provider_router import LLMProviderRouter
    from scripts.benchmark_replay import benchmark_ontology, extract_document, resolve_target
    from tests.integration.pipelines._harness.cassettes import RecordingLLMProvider

    arm = "R0-gold" if gold else "R0"
    target = resolve_target("find_then_type", "extraction-find-then-type")
    router = LLMProviderRouter(anthropic_api_key=anthropic_key())  # Anthropic only
    client = router._providers["anthropic"]._client
    create = client.messages.create
    calls: list[dict[str, Any]] = []
    current = [""]
    worst = cost_usd(
        A_MODEL, {"input": 0, "cache_write": 30_000, "cache_read": 0, "output": 16_000}
    )

    def metered_create(**kwargs: Any) -> Any:
        ledger.reserve(worst)
        try:
            response = create(**kwargs)
        except BaseException:
            ledger.release(worst)
            raise
        usage = usage_of(response.usage)
        usd = cost_usd(A_MODEL, usage)
        ledger.record(
            {
                "arm_model": f"{arm}:{A_MODEL}",
                "arm": arm,
                "take": take,
                "document": current[0],
                "usage": usage,
                "usd": usd,
            },
            worst,
        )
        with ledger.lock:
            calls.append({"usage": usage, "usd": usd})
        return response

    client.messages.create = metered_create
    for document_id in documents:
        if take_path(arm, document_id, take).exists():
            continue
        current[0], calls[:] = document_id, []
        path = cassettes / arm / f"take{take}" / f"{document_id}.json"
        if path.exists():
            raise SystemExit(f"{path} exists; not overwriting a recording")
        given = given_individuals(document_id, take, gold)
        source = (BENCHMARK_DIR / document_id / "source.md").read_text()
        placement = Placement(given, source)
        recorder = RecordingLLMProvider(router, path)
        began = time.perf_counter()
        individuals, relationships = asyncio.run(
            extract_document(
                benchmark_ontology(),
                recorder,
                document_id,
                target,
                functools.partial(GivenIndividualsService, placement=placement),
            )
        )
        latency = time.perf_counter() - began
        failed = recorder.incomplete_count
        recorder.flush()
        placed = placement.placed
        a_take_record(
            document_id,
            take,
            individuals,
            relationships,
            arm=arm,
            individuals_from="gold" if gold else f"B take{take}",
            individuals_given=len({i["title"] for i in given}),
            individuals_placed=len(placed),
            calls=len(calls),
            usage={
                k: sum(c["usage"][k] for c in calls)
                for k in ("input", "cache_write", "cache_read", "output")
            },
            usd=sum(c["usd"] for c in calls),
            latency_s=round(latency, 1),
            incomplete_responses=failed,
            cassette=f"{arm}/take{take}/{document_id}.json (--cassettes folder; not committed)",
        )
        print(
            f"{arm} {document_id} take{take}: {len(individuals)} individuals"
            f" ({len(placed)} of {len({i['title'] for i in given})} placed),"
            f" {len(relationships)} relationships, {len(calls)} calls,"
            f" ${sum(c['usd'] for c in calls):.3f}, {latency:.0f}s"
            + (f", {failed} incomplete responses" if failed else ""),
            flush=True,
        )


# ---------------------------------------------------------------- report

REPORT_ARMS = ("A", "B", "B+validation", "R0", "R1", "R2-haiku", "R2-opus")
DIAGNOSTIC_ARMS = ("R0-gold", "R2-haiku-gold", "R2-opus-gold")
COLUMNS = (
    "relationship_recall",
    "relationship_precision",
    "relationship_precision_resolved",
    "relationship_pair_recall",
    "typed_f1",
)


def scored(arm: str, document_id: str, take: int) -> dict[str, Any] | None:
    """One saved take, scored; `B+validation` is arm B's take with invalid types dropped."""
    path = take_path("B" if arm == "B+validation" else arm, document_id, take)
    if not path.exists():
        return None
    record = json.loads(path.read_text())
    if arm == "B+validation":
        record["relationships_validated"] = True
    result = score_take(record)
    diag = result["diagnostics"]
    listed = diag.get("relationships_listed") or len(record.get("relationships", []))
    return {
        **result["metrics"],
        "relationship_pair_recall": diag["relationship_pair_recall"],
        "relationships_listed": listed,
        "relationships_kept": diag["relationships_scored"],
        "schema_invalid_listed": diag.get(
            "schema_invalid_listed", diag["schema_invalid_relationships"]
        ),
        "invalid_dropped": diag.get("invalid_dropped", 0),
        "usd": record.get("usd"),
        "latency_s": record.get("latency_s"),
        "failed": record.get("failed", False),
    }


def split_values(arm: str, documents: tuple[str, ...], takes: range) -> dict[int, dict[str, float]]:
    """
    Per take, the mean over the split's documents of each number (takes with
    every document); a number some document lacks (arm A take 1's cost) is left out.
    """
    values: dict[int, dict[str, float]] = {}
    for take in takes:
        rows = [scored(arm, d, take) for d in documents]
        if all(rows):
            values[take] = {
                k: mean(float(r[k]) for r in rows)  # type: ignore[index]
                for k in rows[0]  # type: ignore[union-attr]
                if k != "failed" and all(r[k] is not None for r in rows)  # type: ignore[index]
            }
    return values


def report() -> dict[str, Any]:
    """Every arm's numbers per split, and paired deltas against R0 (and R1's against B)."""
    takes = range(1, 4)
    out: dict[str, Any] = {"arms": {}, "deltas": {}, "per_document": {}}
    for arm in REPORT_ARMS + DIAGNOSTIC_ARMS:
        for split, documents in (("dev", DEV), ("holdout", HOLDOUT)):
            values = split_values(arm, documents, takes)
            if not values:
                continue
            keys = set.intersection(*(set(v) for v in values.values()))
            out["arms"].setdefault(arm, {})[split] = {
                "takes": sorted(values),
                **{
                    k: {
                        "mean": round(mean(v[k] for v in values.values()), 4),
                        "min": round(min(v[k] for v in values.values()), 4),
                        "max": round(max(v[k] for v in values.values()), 4),
                    }
                    for k in sorted(keys)
                },
            }
        for document_id in DEV + HOLDOUT:
            rows = {t: scored(arm, document_id, t) for t in takes}
            out["per_document"].setdefault(arm, {})[document_id] = {
                t: r for t, r in rows.items() if r
            }
    pairs = [(arm, "R0") for arm in ("R1", "R2-haiku", "R2-opus")] + [
        ("R1", "B"),
        ("R2-opus", "R2-haiku"),
    ]
    for arm, base in pairs:
        for split, documents in (("dev", DEV), ("holdout", HOLDOUT)):
            mine, theirs = split_values(arm, documents, takes), split_values(base, documents, takes)
            common = sorted(set(mine) & set(theirs))
            if not common:
                continue
            out["deltas"].setdefault(f"{arm} - {base}", {})[split] = {
                k: {
                    "mean": round(mean(mine[t][k] - theirs[t][k] for t in common), 4),
                    "by_take": [round(mine[t][k] - theirs[t][k], 4) for t in common],
                }
                for k in COLUMNS + ("relationships_kept",)
            }
    return out


def print_report(result: dict[str, Any]) -> None:
    def cell(stats: dict[str, float], digits: int = 3) -> str:
        return f"{stats['mean']:.{digits}f} [{stats['min']:.{digits}f}-{stats['max']:.{digits}f}]"

    print(
        "| arm | split | takes | rel. recall | rel. precision | precision (resolved) |"
        " pair recall | typed F1 | kept | invalid listed | $ per doc |"
    )
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for arm, splits in result["arms"].items():
        for split, s in splits.items():
            invalid = s["schema_invalid_listed"]["mean"]
            listed = s["relationships_listed"]["mean"]
            usd = s.get("usd", {}).get("mean", float("nan"))
            print(
                f"| {arm} | {split} | {len(s['takes'])} | {cell(s['relationship_recall'])} |"
                f" {cell(s['relationship_precision'])} |"
                f" {cell(s['relationship_precision_resolved'])} |"
                f" {cell(s['relationship_pair_recall'])} | {cell(s['typed_f1'])} |"
                f" {s['relationships_kept']['mean']:.0f} |"
                f" {invalid:.0f} of {listed:.0f} ({(invalid / listed if listed else 0):.0%}) |"
                f" {usd:.3f} |"
            )
    print()
    print("| pair | split | Δ rel. recall [by take] | Δ rel. precision [by take] | Δ typed F1 |")
    print("|---|---|---|---|---|")
    for pair, splits in result["deltas"].items():
        for split, d in splits.items():

            def fmt(k: str) -> str:
                return (
                    f"{d[k]['mean']:+.3f} [" + ", ".join(f"{x:+.3f}" for x in d[k]["by_take"]) + "]"
                )

            print(
                f"| {pair} | {split} | {fmt('relationship_recall')} |"
                f" {fmt('relationship_precision')} | {fmt('typed_f1')} |"
            )


# ---------------------------------------------------------------- checks


def selftest() -> None:
    """Offline: gold relationships over gold individuals as an R2 take score 1.0, none dropped;
    prompt sizes; where R0 would place arm B's individuals."""
    for document_id in benchmark_documents():
        gold = load_gold(document_id)
        titles = {g.key: g.title for g in gold.individuals}
        take = {
            "document": document_id,
            "relationships_validated": True,
            "individuals": given_individuals(document_id, 1, gold=True),
            "relationships": [
                {"source": titles[r.source], "predicate": r.predicate, "target": titles[r.target]}
                for r in gold.relationships
            ],
        }
        m = score_take(take)
        print(
            f"gold as R2 {document_id:<22} rel recall {m['metrics']['relationship_recall']:.4f}"
            f" precision {m['metrics']['relationship_precision']:.4f}"
            f" dropped {m['diagnostics']['invalid_dropped']}"
        )
        r2 = r2_prompt(document_id, given_individuals(document_id, 1, gold=False))
        titles = r2.schema["properties"]["relationships"]["items"]["properties"]["source"]["enum"]
        print(
            f"R2 prompt {document_id:<22} system {len(r2.system)} chars, user {len(r2.user)} chars,"
            f" {len(titles)} titles"
        )
        source = (BENCHMARK_DIR / document_id / "source.md").read_text()
        given = given_individuals(document_id, 1, gold=False)
        placement = Placement(given, source)
        placement.mentions(source)
        print(f"R0 placement {document_id:<22} {len(placement.placed)} of {len(given)} placed")
    print(f"R1 system {len(r1_system())} chars; B system {len(system_prompt())} chars")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("command", choices=["selftest", "prompt", "run", "record-r0", "report"])
    parser.add_argument("--arm", choices=sorted(CALL_ARMS))
    parser.add_argument("--document", action="append")
    parser.add_argument("--take", type=int, action="append")
    parser.add_argument("--gold", action="store_true", help="record-r0: R0-gold")
    parser.add_argument("--spend", action="store_true", help="Confirm paid calls")
    parser.add_argument("--cassettes", type=Path, help="Folder for R0's recordings")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--concurrency", type=int, choices=[1, 2], default=CONCURRENCY)
    args = parser.parse_args()
    documents = args.document or benchmark_documents()
    if args.command in ("run", "record-r0") and not args.spend:
        raise SystemExit("this command makes paid calls; pass --spend")
    ledger = Ledger(LEDGER, BUDGET_USD)
    if args.command == "selftest":
        selftest()
    elif args.command == "prompt":
        take = (args.take or [1])[0]
        document_id = documents[0]
        if args.arm == "R1":
            prompt = r1_prompt(document_id)
        else:
            prompt = r2_prompt(
                document_id, given_individuals(document_id, take, args.arm.endswith("-gold"))
            )
        print(prompt.system)
        print("=" * 40)
        print(prompt.user[:3000])
    elif args.command == "run":
        if not args.arm:
            raise SystemExit("--arm is required")
        jobs = [(d, t) for t in args.take or [1] for d in documents]
        run_calls(args.arm, jobs, ledger, args.concurrency)
        print(f"ledger: ${ledger.spent():.2f} of ${BUDGET_USD:.2f}")
    elif args.command == "record-r0":
        if not args.cassettes:
            raise SystemExit("--cassettes is required")
        for take in args.take or [1]:
            record_r0(take, documents, args.gold, args.cassettes, ledger)
        print(f"ledger: ${ledger.spent():.2f} of ${BUDGET_USD:.2f}")
    else:
        result = report()
        if args.json:
            print(json.dumps(result, indent=1))
        else:
            print_report(result)
            print(f"\nledger: ${ledger.spent():.2f} of ${BUDGET_USD:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
