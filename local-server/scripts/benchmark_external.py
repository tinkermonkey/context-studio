"""
Head-to-head on the extraction benchmark: the app's pipeline against one call.

Arms (scored by tests/integration/pipelines/_harness/benchmark.py, unchanged):

- A: the app's `find_then_type` implementation with its configuration
  `extraction-find-then-type` (Claude Haiku 5.5), through the real pipeline
  (scripts/benchmark_replay.py). Take 1 is the committed recording; further
  takes are recorded live into a cassette folder given with --cassettes, never
  over the committed ones.
- B, B-sonnet, B-haiku: ONE call per document to Claude Opus 5.5, Sonnet 5.5 or
  Haiku 5.5. The whole source plus the DR class catalog (full definitions, by
  layer) and predicate catalog, as a cached system block; structured output;
  adaptive thinking at effort high. Same system text for all three.

Every take is saved to
tests/integration/fixtures/pipelines/extraction_benchmark_external/<arm>/<document>/take<N>.json
({individuals, relationships, usage, cost, latency, raw response}), so
`replay` re-scores everything without calls. Every paid call is appended to a
ledger (--ledger, JSON lines); a call that could take the ledger past
BUDGET_USD is not made.

Usage (from local-server/):
    python scripts/benchmark_external.py selftest            # offline adapter checks
    python scripts/benchmark_external.py export-a-take1      # committed recording -> A take 1
    python scripts/benchmark_external.py run-b --arm B --document edit_check --take 1 --spend
    python scripts/benchmark_external.py record-a --take 2 --spend --cassettes <dir>
    python scripts/benchmark_external.py replay [--json]
"""

import argparse
import asyncio
import hashlib
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.integration.pipelines._harness.benchmark import (  # noqa: E402
    BENCHMARK_DIR,
    Passage,
    Predicted,
    PredictedRelationship,
    SchemaSnapshot,
    benchmark_documents,
    class_reference,
    load_gold,
    load_schema_bundle,
    match_individuals,
    name_key,
    score,
)

EXTERNAL_DIR = BENCHMARK_DIR.with_name("extraction_benchmark_external")
MODELS = {"B": "claude-opus-5-5", "B-sonnet": "claude-sonnet-5-5", "B-haiku": "claude-haiku-5-5"}
A_MODEL = "claude-haiku-5-5"
MAX_TOKENS = 64000
EFFORT = "high"
BUDGET_USD = 30.0
# USD per million tokens (claude-api reference, 2026-11-15): input, 5-minute cache
# write, cache read, output. Haiku 5.5 has a second card for prompts over 100K tokens.
PRICES = {
    "claude-opus-5-5": (4.00, 5.00, 0.20, 20.00),
    "claude-sonnet-5-5": (2.00, 2.50, 0.10, 10.00),
    "claude-haiku-5-5": (0.10, 0.125, 0.01, 0.50),
    "claude-haiku-5-5>100k": (0.50, 0.625, 0.05, 2.50),
}
LAYER_ORDER = (
    "motivation business product security application technology api data-model data-store ux"
    " navigation apm testing"
).split()


# ---------------------------------------------------------------- cost and ledger


def usage_of(usage: Any) -> dict[str, int]:
    """The four meters of an API usage object."""
    return {
        "input": usage.input_tokens or 0,
        "cache_write": getattr(usage, "cache_creation_input_tokens", None) or 0,
        "cache_read": getattr(usage, "cache_read_input_tokens", None) or 0,
        "output": usage.output_tokens or 0,
    }


def price_card(model: str, prompt_tokens: int) -> tuple[float, ...]:
    if model == "claude-haiku-5-5" and prompt_tokens > 100_000:
        return PRICES["claude-haiku-5-5>100k"]
    return PRICES[model]


def cost_usd(model: str, u: dict[str, int]) -> float:
    rate_in, rate_write, rate_read, rate_out = price_card(
        model, u["input"] + u["cache_write"] + u["cache_read"]
    )
    return (
        u["input"] * rate_in
        + u["cache_write"] * rate_write
        + u["cache_read"] * rate_read
        + u["output"] * rate_out
    ) / 1e6


class BudgetExceeded(RuntimeError):
    """The next call could take the ledger past the budget."""


class Ledger:
    """Paid calls, one JSON line each; calls reserve their worst case before they are made."""

    def __init__(self, path: Path, budget_usd: float = BUDGET_USD) -> None:
        self.path = path
        self.budget_usd = budget_usd
        self.lock = threading.Lock()
        self.reserved = 0.0

    def spent(self) -> float:
        if not self.path.exists():
            return 0.0
        return sum(json.loads(line)["usd"] for line in self.path.read_text().splitlines() if line)

    def reserve(self, usd: float) -> None:
        with self.lock:
            if self.spent() + self.reserved + usd > self.budget_usd:
                raise BudgetExceeded(
                    f"spent {self.spent():.2f} + in flight {self.reserved:.2f} + this call's worst"
                    f" case {usd:.2f} would pass ${self.budget_usd:.2f}"
                )
            self.reserved += usd

    def record(self, entry: dict[str, Any], reserved: float) -> None:
        with self.lock:
            self.reserved -= reserved
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a") as f:
                f.write(json.dumps({**entry, "at": time.time()}) + "\n")

    def release(self, reserved: float) -> None:
        with self.lock:
            self.reserved -= reserved


def anthropic_key() -> str:
    """The Anthropic key from config (CONFIG_PATH / .env); never printed."""
    from config import get_config_manager

    key = get_config_manager().get_settings().llm.anthropic_api_key
    if not key:
        raise SystemExit("No Anthropic API key is configured")
    return key


# ---------------------------------------------------------------- arm B: one call


def catalog() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """The DR classes (reference, title, layer, definition) and the predicates in use."""
    bundle = load_schema_bundle()
    schemes = {s["identifier"]: s["title"] for s in bundle["schemes"]}
    classes = [
        {
            "ref": class_reference(c),
            "title": c["title"],
            "layer": class_reference(c).split(".", 1)[0],
            "layer_title": schemes.get(c["scheme"], c["scheme"]),
            "definition": " ".join((c.get("description") or "").split()),
        }
        for c in bundle["classes"]
        if not c.get("derived")
    ]
    classes.sort(key=lambda c: (LAYER_ORDER.index(c["layer"]), c["ref"]))
    used = {p["predicate"] for p in bundle["properties"] if not p.get("derived")}
    predicates = sorted(
        (
            {"identifier": p["identifier"], "definition": p.get("description") or ""}
            for p in bundle["predicates"]
            if p["identifier"] in used
        ),
        key=lambda p: p["identifier"],
    )
    return classes, predicates


SYSTEM_HEAD = """You are an expert knowledge graph extraction assistant. Your task is to read one
document and extract from it, for a model of its subject in the {ontology} ontology, every
individual the document states and every relationship between those individuals that the
document states.

An individual is an instance of exactly one class of the ontology. The classes are listed
below by layer, each as: class reference (title): definition.

# Classes
"""

SYSTEM_TAIL = """
# Predicates
Each relationship uses one predicate, read as: source <predicate> target.
{predicates}

# What to extract

Individuals. List two kinds:
- things the document names: use the name the document gives them;
- statements the document asserts about its subject or the people behind it: a goal, a
  requirement, a principle, a constraint, a reason, a finding or an outcome. Title a
  statement with a paraphrase of at most ten words.
Be exhaustive: include what is named only once, in a table, a list or a diagram.
Leave out what the document only refers to and does not describe as part of its subject:
other works it cites or compares itself with, press coverage, link lists, navigation,
passing examples, generic terms, and repeats of headings.
List each individual once. For each give:
- title: as above;
- class: the one class reference from the list above that best fits what the individual
  is, as the document describes it. Judge by the class definitions, not by the class
  names;
- quote: the exact words of the document, at most 300 characters, that say what the
  individual is or that state it. Copy the quote verbatim; never paraphrase it.

Relationships. List each relationship the document states between two of your
individuals; never one you only infer. For each give:
- source and target: the titles of two of your individuals, copied exactly;
- predicate: one predicate from the list above, so that "source predicate target" is
  what the document says;
- quote: the exact words of the document that state the relationship, verbatim.

Answer with the JSON object the response format asks for."""

USER_PROMPT = """Extract every individual and every relationship the following document states.

<document>
{source}
</document>"""


def system_prompt() -> str:
    classes, predicates = catalog()
    lines, layer = [], None
    for c in classes:
        if c["layer"] != layer:
            layer = c["layer"]
            lines.append(f"\n## {c['layer_title']}")
        lines.append(f"- {c['ref']} ({c['title']}): {c['definition']}")
    predicate_lines = "\n".join(f"- {p['identifier']}: {p['definition']}" for p in predicates)
    return (
        SYSTEM_HEAD.format(ontology="Documentation Robotics (DR)")
        + "\n".join(lines).lstrip("\n")
        + "\n"
        + SYSTEM_TAIL.format(predicates=predicate_lines)
    )


def output_schema() -> dict[str, Any]:
    classes, predicates = catalog()

    def obj(properties: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        }

    text = {"type": "string"}
    return obj(
        {
            "individuals": {
                "type": "array",
                "items": obj(
                    {
                        "title": text,
                        "class": {"type": "string", "enum": [c["ref"] for c in classes]},
                        "quote": text,
                    }
                ),
            },
            "relationships": {
                "type": "array",
                "items": obj(
                    {
                        "source": text,
                        "predicate": {
                            "type": "string",
                            "enum": [p["identifier"] for p in predicates],
                        },
                        "target": text,
                        "quote": text,
                    }
                ),
            },
        }
    )


def take_path(arm: str, document_id: str, take: int) -> Path:
    return EXTERNAL_DIR / arm / document_id / f"take{take}.json"


@dataclass(frozen=True)
class CallPrompt:
    """What one call is sent: a system text (cached), a user text, the JSON schema it answers."""

    system: str
    user: str
    schema: dict[str, Any]

    @property
    def sha256(self) -> str:
        return hashlib.sha256((self.system + self.user).encode()).hexdigest()


def b_prompt(document_id: str) -> CallPrompt:
    """Arm B's call for a document."""
    source = (BENCHMARK_DIR / document_id / "source.md").read_text()
    return CallPrompt(system_prompt(), USER_PROMPT.format(source=source), output_schema())


def one_call(
    client: Any,
    ledger: Ledger,
    model: str,
    document_id: str,
    started: threading.Event,
    prompt: CallPrompt | None = None,
    take: tuple[str, int] | None = None,
) -> dict[str, Any]:
    """
    One streamed call for a document; `started` is set once the prompt is read
    (cached). `take` (arm, take number) is recorded on the call's ledger row.
    """
    prompt = prompt or b_prompt(document_id)
    prompt_tokens = (len(prompt.system) + len(prompt.user)) // 3  # generous: 4 chars a token
    worst = cost_usd(
        model, {"input": 0, "cache_write": prompt_tokens, "cache_read": 0, "output": MAX_TOKENS}
    )
    ledger.reserve(worst)
    began = time.perf_counter()
    try:
        with client.messages.stream(
            model=model,
            max_tokens=MAX_TOKENS,
            system=[
                {"type": "text", "text": prompt.system, "cache_control": {"type": "ephemeral"}}
            ],
            messages=[{"role": "user", "content": prompt.user}],
            thinking={"type": "adaptive"},
            output_config={
                "effort": EFFORT,
                "format": {"type": "json_schema", "schema": prompt.schema},
            },
        ) as stream:
            for _ in stream:
                started.set()
            message = stream.get_final_message()
    except BaseException:
        ledger.release(worst)
        started.set()
        raise
    latency = time.perf_counter() - began
    usage = usage_of(message.usage)
    usd = cost_usd(model, usage)
    where = {"arm": take[0], "take": take[1]} if take else {}
    ledger.record(
        {"arm_model": model, **where, "document": document_id, "usage": usage, "usd": usd}, worst
    )
    raw = message.model_dump(mode="json")
    for block in raw.get("content", []):
        block.pop("signature", None)  # thinking signatures: opaque and large
    text = "".join(b.text for b in message.content if b.type == "text")
    return {
        "raw": raw,
        "text": text,
        "usage": usage,
        "usd": usd,
        "latency_s": round(latency, 1),
        "stop_reason": message.stop_reason,
    }


def run_take(
    client: Any,
    ledger: Ledger,
    arm: str,
    document_id: str,
    take: int,
    started: threading.Event,
    model: str | None = None,
    prompt: CallPrompt | None = None,
    lists: tuple[str, ...] = ("individuals", "relationships"),
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    One take: a call, retried once when it is cut off, refused or not valid JSON.
    By default arm B's call with the arm's model; another arm gives its model,
    its prompt, the lists its answer must hold, and what else its take records
    (`extra`, which may give the individuals of an answer that lists none).
    """
    model, attempts = model or MODELS[arm], []
    prompt = prompt or b_prompt(document_id)
    for attempt in (1, 2):
        result = one_call(
            client,
            ledger,
            model,
            document_id,
            started if attempt == 1 else threading.Event(),
            prompt,
            (arm, take),
        )
        problem = (
            None if result["stop_reason"] == "end_turn" else f"stop_reason {result['stop_reason']}"
        )
        parsed = None
        if problem is None:
            try:
                parsed = json.loads(result["text"])
                if not all(isinstance(parsed.get(name), list) for name in lists):
                    problem = f"JSON without {' and '.join(lists)} lists"
            except (ValueError, AttributeError) as exc:
                problem = f"invalid JSON: {exc}"
        attempts.append(
            {
                "attempt": attempt,
                "problem": problem,
                "usage": result["usage"],
                "usd": result["usd"],
                "latency_s": result["latency_s"],
            }
        )
        if problem is None:
            break
    record = {
        "arm": arm,
        "model": model,
        "document": document_id,
        "take": take,
        "effort": EFFORT,
        "max_tokens": MAX_TOKENS,
        "prompt_sha256": (
            hashlib.sha256((system_prompt() + USER_PROMPT).encode()).hexdigest()
            if arm in MODELS
            else prompt.sha256
        ),
        "failed": problem is not None,
        "attempts": attempts,
        **(extra or {}),
        **{name: (parsed or {}).get(name, []) for name in lists},
        "usage": {k: sum(a["usage"][k] for a in attempts) for k in attempts[0]["usage"]},
        "usd": sum(a["usd"] for a in attempts),
        "latency_s": result["latency_s"],
        "raw_response": result["raw"],
    }
    path = take_path(arm, document_id, take)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=1))
    print(
        f"{arm} {document_id} take{take}: {len(record['individuals'])} individuals, "
        f"{len(record['relationships'])} relationships, ${record['usd']:.3f},"
        f" {record['latency_s']}s"
        + (f", FAILED {problem}" if problem else "")
        + (", retried" if len(attempts) > 1 else ""),
        flush=True,
    )
    return record


def run_b(arm: str, jobs: list[tuple[str, int]], ledger: Ledger) -> None:
    """The first job alone until its prompt is read (cached), then the rest side by side."""
    import anthropic

    client = anthropic.Anthropic(api_key=anthropic_key(), max_retries=4, timeout=1800)
    jobs = [j for j in jobs if not take_path(arm, *j).exists()]
    if not jobs:
        return
    first = threading.Event()
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = [pool.submit(run_take, client, ledger, arm, *jobs[0], first)]
        first.wait()
        futures += [
            pool.submit(run_take, client, ledger, arm, *job, threading.Event()) for job in jobs[1:]
        ]
        for future in futures:
            future.result()


# ---------------------------------------------------------------- arm A: the pipeline


def a_take_record(
    document_id: str,
    take: int,
    individuals: list[Predicted],
    relationships: list[PredictedRelationship],
    arm: str = "A",
    **extra: Any,
) -> dict[str, Any]:
    """A take of the pipeline (arm A, or another arm run through it), saved."""
    record = {
        "arm": arm,
        "model": A_MODEL,
        "document": document_id,
        "take": take,
        "individuals": [
            {
                "title": p.title,
                "classes": list(p.class_refs),
                "passages": [
                    {"start": e.start, "end": e.end, "quote": e.quote} for e in p.evidence
                ],
            }
            for p in individuals
        ],
        "relationships": [
            {"source": r.source, "predicate": r.predicate, "target": r.target}
            for r in relationships
        ],
        **extra,
    }
    path = take_path(arm, document_id, take)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=1))
    return record


def a_predictions_from_cassette(
    document_id: str, cassette: Path
) -> tuple[list[Predicted], list[PredictedRelationship]]:
    from scripts.benchmark_replay import benchmark_ontology, extract_document, resolve_target
    from tests.integration.pipelines._harness.cassettes import CassetteLLMProvider

    provider = CassetteLLMProvider(cassette)
    result = asyncio.run(
        extract_document(
            benchmark_ontology(),
            provider,
            document_id,
            resolve_target("find_then_type", "extraction-find-then-type"),
        )
    )
    if provider.misses:
        raise SystemExit(f"{cassette}: {provider.misses} prompts have no recording")
    return result


def export_a_take1() -> None:
    """The committed recording, replayed free, as A take 1 (tokens as recorded: no cache split)."""
    from scripts.benchmark_replay import cassette_path, resolve_target

    target = resolve_target("find_then_type", "extraction-find-then-type")
    for document_id in benchmark_documents():
        path = cassette_path(document_id, target)
        individuals, relationships = a_predictions_from_cassette(document_id, path)
        entries = list(json.loads(path.read_text()).values())
        a_take_record(
            document_id,
            1,
            individuals,
            relationships,
            calls=len(entries),
            recorded_tokens={
                "input_all": sum(e["tokens_in"] for e in entries),
                "output": sum(e["tokens_out"] for e in entries),
            },
            usd=None,
            latency_s=None,
            source=str(path.relative_to(BENCHMARK_DIR.parents[4])),
        )
        print(f"A {document_id} take1 exported", flush=True)


def record_a(take: int, documents: list[str], cassettes: Path, ledger: Ledger) -> None:
    """Record a new take of arm A through the real pipeline, every call metered."""
    from adapters.llm.provider_router import LLMProviderRouter
    from scripts.benchmark_replay import benchmark_ontology, extract_document, resolve_target
    from tests.integration.pipelines._harness.cassettes import RecordingLLMProvider

    target = resolve_target("find_then_type", "extraction-find-then-type")
    router = LLMProviderRouter(anthropic_api_key=anthropic_key())  # Anthropic only
    client = router._providers["anthropic"]._client
    create = client.messages.create
    calls: list[dict[str, Any]] = []
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
            {"arm_model": f"A:{A_MODEL}", "document": current[0], "usage": usage, "usd": usd}, worst
        )
        with ledger.lock:
            calls.append({"usage": usage, "usd": usd})
        return response

    client.messages.create = metered_create
    current = [""]
    for document_id in documents:
        if take_path("A", document_id, take).exists():
            continue
        current[0], calls[:] = document_id, []
        path = cassettes / f"take{take}" / f"{document_id}.json"
        if path.exists():
            raise SystemExit(f"{path} exists; not overwriting a recording")
        recorder = RecordingLLMProvider(router, path)
        began = time.perf_counter()
        individuals, relationships = asyncio.run(
            extract_document(benchmark_ontology(), recorder, document_id, target)
        )
        latency = time.perf_counter() - began
        failed = recorder.incomplete_count
        recorder.flush()
        usage = {
            k: sum(c["usage"][k] for c in calls)
            for k in ("input", "cache_write", "cache_read", "output")
        }
        a_take_record(
            document_id,
            take,
            individuals,
            relationships,
            calls=len(calls),
            usage=usage,
            usd=sum(c["usd"] for c in calls),
            latency_s=round(latency, 1),
            incomplete_responses=failed,
            cassette=f"take{take}/{document_id}.json (in the --cassettes folder; not committed)",
        )
        print(
            f"A {document_id} take{take}: {len(individuals)} individuals,"
            f" {len(relationships)} relationships, "
            f"{len(calls)} calls, ${sum(c['usd'] for c in calls):.3f}, {latency:.0f}s"
            + (f", {failed} incomplete responses" if failed else ""),
            flush=True,
        )


# ---------------------------------------------------------------- the adapter


def _normalized(text: str) -> tuple[str, list[int]]:
    """Text without markdown marks, quotes straight, spaces collapsed, lowercased; and offsets."""
    swap = {"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-"}
    chars, offsets, space = [], [], True
    for i, ch in enumerate(text):
        if ch in "`*_#>|\\[]":
            continue
        if ch.isspace():
            if not space:
                chars.append(" ")
                offsets.append(i)
            space = True
            continue
        chars.append(swap.get(ch, ch).lower())
        offsets.append(i)
        space = False
    return "".join(chars), offsets


def locate(quote: str, source: str, normalized: tuple[str, list[int]]) -> Passage | None:
    """Where a quote is in the source: exactly, else ignoring markdown, case and spacing."""
    quote = (quote or "").strip()
    if not quote:
        return None
    at = source.find(quote)
    if at >= 0:
        return Passage(at, at + len(quote), quote)
    text, offsets = normalized
    needle = _normalized(quote)[0].strip()
    at = text.find(needle) if needle else -1
    if at < 0:
        return None
    start, end = offsets[at], offsets[at + len(needle) - 1] + 1
    return Passage(start, end, source[start:end])


def predictions(
    take: dict[str, Any], source: str, classes: set[str], predicates: set[str]
) -> tuple[list[Predicted], list[PredictedRelationship], dict[str, int]]:
    """
    A saved take as the scorer's predictions. Individuals that share a name
    (the scorer's name key) and a class are one prediction, as the pipeline's
    merge makes them; references outside the catalog are kept as given (so they
    score as errors) and counted. A relationship end is the individual whose
    name key it has; a relationship with an end that names none is dropped and
    counted. A relationship that is not a relationship type of the schema for
    the classes of its ends is counted; a take marked `relationships_validated`
    (an arm restricted to the allowed types by validation) has such
    relationships dropped, as the pipeline's planning drops them.
    """
    normalized = _normalized(source)
    diag = {
        "individuals_listed": 0,
        "invalid_class": 0,
        "merged": 0,
        "unlocated_quotes": 0,
        "relationships_listed": 0,
        "invalid_predicate": 0,
        "dangling_relationships": 0,
        "schema_invalid_listed": 0,
        "invalid_dropped": 0,
    }
    groups: dict[tuple[str, tuple[str, ...]], dict[str, Any]] = {}
    for item in take["individuals"]:
        diag["individuals_listed"] += 1
        refs = tuple(item["classes"]) if "classes" in item else (item["class"],)
        diag["invalid_class"] += sum(1 for r in refs if r not in classes)
        if "passages" in item:
            passages = [Passage(p["start"], p["end"], p.get("quote", "")) for p in item["passages"]]
        else:
            found = locate(item.get("quote", ""), source, normalized)
            diag["unlocated_quotes"] += found is None
            passages = [found] if found else []
        key = (name_key(item["title"]), refs)
        if key in groups:
            diag["merged"] += 1
            groups[key]["evidence"] += passages
        else:
            groups[key] = {"title": item["title"], "refs": refs, "evidence": passages}
    individuals = [Predicted(g["title"], g["refs"], tuple(g["evidence"])) for g in groups.values()]
    title_of: dict[str, str] = {}
    classes_of: dict[str, set[str]] = {}
    for p in individuals:
        title_of.setdefault(name_key(p.title), p.title)
        classes_of.setdefault(name_key(p.title), set()).update(p.class_refs)
    validated = bool(take.get("relationships_validated"))
    relationships = []
    for item in take["relationships"]:
        diag["relationships_listed"] += 1
        diag["invalid_predicate"] += item["predicate"] not in predicates
        source_title, target_title = (
            title_of.get(name_key(item["source"])),
            title_of.get(name_key(item["target"])),
        )
        if source_title is None or target_title is None:
            diag["dangling_relationships"] += 1
            continue
        relationship = PredictedRelationship(source_title, item["predicate"], target_title)
        if not schema_valid(relationship, classes_of):
            diag["schema_invalid_listed"] += 1
            if validated:
                diag["invalid_dropped"] += 1
                continue
        relationships.append(relationship)
    return individuals, relationships, diag


def schema_valid(relationship: PredictedRelationship, classes_of: dict[str, set[str]]) -> bool:
    """Whether a relationship is a relationship type of the schema for some classes of its ends."""
    types = _schema_types()
    return any(
        (s, relationship.predicate, t) in types
        for s in classes_of.get(name_key(relationship.source), ())
        for t in classes_of.get(name_key(relationship.target), ())
    )


def score_take(take: dict[str, Any]) -> dict[str, Any]:
    classes, predicates = catalog()
    gold = load_gold(take["document"])
    individuals, relationships, diag = predictions(
        take, gold.source_text, {c["ref"] for c in classes}, {p["identifier"] for p in predicates}
    )
    result = score(gold, individuals, relationships)
    diag.update(relationship_diagnostics(gold, individuals, relationships))
    return {"metrics": result.metrics, "counts": result.counts, "diagnostics": diag}


def relationship_diagnostics(
    gold: Any, individuals: list[Predicted], relationships: list[PredictedRelationship]
) -> dict[str, Any]:
    """
    Diagnostics beside the scorer's relationship recall (which needs the gold
    predicate and direction): the share of gold relationships whose two ends a
    run related at all, either way round, with ends resolved as score() resolves
    them; and how many of the run's relationships are not a relationship type of
    the schema for the classes it gave their ends.
    """
    matches = match_individuals(gold, individuals)
    found = {g.key for g in matches.values()}
    ends: dict[str, set[str]] = {}
    for g in gold.individuals:
        if g.key in found:
            for name in g.names:
                ends.setdefault(name, set()).add(g.key)
    for i, g in matches.items():
        ends.setdefault(name_key(individuals[i].title), set()).add(g.key)
    end_key = {name: next(iter(keys)) for name, keys in ends.items() if len(keys) == 1}
    pairs = {
        frozenset((end_key[name_key(r.source)], end_key[name_key(r.target)]))
        for r in relationships
        if name_key(r.source) in end_key and name_key(r.target) in end_key
    }
    gold_pairs = [frozenset((r.source, r.target)) for r in gold.relationships]
    classes_of: dict[str, set[str]] = {}
    for p in individuals:
        classes_of.setdefault(name_key(p.title), set()).update(p.class_refs)
    invalid = sum(1 for r in relationships if not schema_valid(r, classes_of))
    return {
        "relationship_pair_recall": round(sum(p in pairs for p in gold_pairs) / len(gold_pairs), 4)
        if gold_pairs
        else 0.0,
        "schema_invalid_relationships": invalid,
        "relationships_scored": len(relationships),
    }


_TYPES: list[frozenset] = []


def _schema_types() -> frozenset:
    if not _TYPES:
        _TYPES.append(SchemaSnapshot.load().relationship_types)
    return _TYPES[0]


# ---------------------------------------------------------------- checks and replay


def selftest() -> None:
    """Gold as predictions scores 1.0 (offsets or quotes alone); A take 1 matches the replay."""
    from scripts.benchmark_replay import replay_document, resolve_target

    for document_id in benchmark_documents():
        gold = load_gold(document_id)
        titles = {g.key: g.title for g in gold.individuals}
        for mode in ("quotes", "passages"):
            take = {
                "document": document_id,
                "individuals": [
                    {"title": g.title, "class": g.class_ref, "quote": g.evidence[0].quote}
                    if mode == "quotes"
                    else {
                        "title": g.title,
                        "classes": [g.class_ref],
                        "passages": [
                            {"start": e.start, "end": e.end, "quote": e.quote} for e in g.evidence
                        ],
                    }
                    for g in gold.individuals
                ],
                "relationships": [
                    {
                        "source": titles[r.source],
                        "predicate": r.predicate,
                        "target": titles[r.target],
                    }
                    for r in gold.relationships
                ],
            }
            m = score_take(take)
            print(
                f"gold->{mode:<8} {document_id:<22} typed F1 {m['metrics']['typed_f1']:.4f} "
                f"F1 {m['metrics']['f1']:.4f} rel recall {m['metrics']['relationship_recall']:.4f} "
                f"evidence {m['metrics']['evidence_agreement']:.4f} {m['diagnostics']}"
            )
        replayed = asyncio.run(replay_document(document_id, resolve_target("find_then_type")))
        saved = json.loads(take_path("A", document_id, 1).read_text())
        mine = score_take(saved)["metrics"]
        theirs = replayed.score.metrics
        differ = {k: (theirs[k], mine[k]) for k in theirs if abs(theirs[k] - mine[k]) > 1e-9}
        print(
            f"A take1 vs replay {document_id:<22} typed F1 {mine['typed_f1']:.4f}"
            f" / {theirs['typed_f1']:.4f}; "
            f"differences: {differ or 'none'}"
        )
        quotes_only = {
            **saved,
            "individuals": [
                {
                    "title": i["title"],
                    "classes": i["classes"],
                    "quote": (i["passages"] or [{}])[0].get("quote", ""),
                }
                for i in saved["individuals"]
            ],
        }
        m = score_take(quotes_only)["metrics"]
        print(
            f"A take1 quotes only {document_id:<20} typed F1 {m['typed_f1']:.4f} F1 {m['f1']:.4f} "
            f"evidence {m['evidence_agreement']:.4f}"
        )


METRICS = (
    "f1",
    "typed_f1",
    "recall",
    "recall_core",
    "precision",
    "type_accuracy",
    "relationship_recall",
    "relationship_precision",
    "relationship_precision_resolved",
)


def replay() -> dict[str, Any]:
    """Every saved take, scored."""
    rows = []
    for path in sorted(EXTERNAL_DIR.glob("*/*/take*.json")):
        take = json.loads(path.read_text())
        scored = score_take(take)
        rows.append(
            {
                "arm": take["arm"],
                "document": take["document"],
                "take": take["take"],
                "failed": take.get("failed", False),
                "retried": len(take.get("attempts", [])) > 1,
                **{k: scored["metrics"][k] for k in METRICS},
                "diagnostics": scored["diagnostics"],
                "counts": scored["counts"],
                "usage": take.get("usage") or take.get("recorded_tokens"),
                "usd": take.get("usd"),
                "latency_s": take.get("latency_s"),
                "calls": take.get("calls", 1),
            }
        )
    return {"takes": rows}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "command", choices=["selftest", "export-a-take1", "run-b", "record-a", "replay", "prompt"]
    )
    parser.add_argument("--arm", choices=sorted(MODELS))
    parser.add_argument("--document", action="append")
    parser.add_argument("--take", type=int, action="append")
    parser.add_argument(
        "--spend", action="store_true", help="Confirm the command may make paid calls"
    )
    parser.add_argument("--ledger", type=Path, default=EXTERNAL_DIR / "ledger.jsonl")
    parser.add_argument("--cassettes", type=Path, help="Folder for arm A's new recordings")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    documents = args.document or benchmark_documents()
    if args.command in ("run-b", "record-a") and not args.spend:
        raise SystemExit("this command makes paid calls; pass --spend")
    if args.command == "selftest":
        selftest()
    elif args.command == "export-a-take1":
        export_a_take1()
    elif args.command == "prompt":
        print(system_prompt())
    elif args.command == "run-b":
        run_b(args.arm, [(d, t) for t in args.take or [1] for d in documents], Ledger(args.ledger))
    elif args.command == "record-a":
        if not args.cassettes:
            raise SystemExit("--cassettes is required: never record over the committed cassettes")
        for take in args.take or [2]:
            record_a(take, documents, args.cassettes, Ledger(args.ledger))
    else:
        result = replay()
        if args.json:
            print(json.dumps(result, indent=1))
        else:
            for r in result["takes"]:
                print(
                    f"{r['arm']:<9} {r['document']:<22} take{r['take']} "
                    + " ".join(f"{k} {r[k]:.3f}" for k in METRICS)
                    + f" ${r['usd'] or 0:.3f}"
                )
    return 0


if __name__ == "__main__":
    sys.exit(main())
