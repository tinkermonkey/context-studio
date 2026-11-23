"""
The pre-review stage's assessment harness
(documentation/extraction/experiments/2026-11-22-pre-review-stage.md).

Phase 0 only, free, no model calls:

    python scripts/benchmark_pre_review.py witness          # where the split question applies
    python scripts/benchmark_pre_review.py seeded --fake keep     # the seeds, scored with a stage that keeps all
    python scripts/benchmark_pre_review.py seeded --fake oracle   # ... with one that knows every seed

Phase 1, the real stage on the planted errors (an arm is opus or haiku):

    python scripts/benchmark_pre_review.py seeded --arm haiku --spend  # record the missing takes (costs)
    python scripts/benchmark_pre_review.py seeded --arm haiku          # replay the recorded takes, free

`witness` reports the split witness on Gate D's four splits (it must mark all
four), on each benchmark document's gold titles, and on single_call's recorded
titles. `seeded` builds the planted errors of the dev documents for takes 1-3
and scores a stage on them: a fake one, or the real pre_review call (`--arm`).
Each real take is recorded as a cassette under
tests/integration/fixtures/cassettes/pre_review_seeded/<arm>/take<n>/<document>.json,
and every paid call is metered in
tests/integration/fixtures/pipelines/extraction_benchmark_pre_review/ledger.jsonl
against the experiment's cap; a call whose worst case would pass it is not made.

Phase 2, the stage inside single_call on the benchmark, paired with the
incumbent's takes (take 1 is single_call's committed recording; takes 2 and 3
are recorded here):

    python scripts/benchmark_pre_review.py benchmark --arm off --spend    # record the incumbent's takes 2-3 (costs)
    python scripts/benchmark_pre_review.py benchmark --arm haiku --spend  # each arm over each incumbent take (costs)
    python scripts/benchmark_pre_review.py benchmark                      # replay every arm, score, apply the rule (free)

An arm's take reads the incumbent take's recording first, so its
find_individuals call and every relate call the review left unchanged cost
nothing; only the review and the relate calls it changed are new.

Run from local-server/ with the venv active. Add --json for machine-readable output.
"""

import argparse
import json
import os
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.extraction.entities import (  # noqa: E402
    FoundIndividual,
    Mention,
    PreReviewAnswer,
    PreReviewPart,
    PreReviewQuestion,
    PreReviewVerdict,
)
from domain.extraction.find_then_type import CatalogClass  # noqa: E402
from domain.extraction.pre_review import (  # noqa: E402
    PreReviewResult,
    review_individuals,
    split_witness,
)
from domain.extraction.prompts import PRE_REVIEW_STAGE  # noqa: E402
from domain.extraction.single_call import build_catalog, parse_individuals  # noqa: E402
from tests.integration.pipelines._harness.benchmark import (  # noqa: E402
    BENCHMARK_DIR,
    DEV_DOCUMENTS,
    HOLDOUT_DOCUMENTS,
    class_reference,
    load_gold,
    load_schema_bundle,
)
from tests.integration.pipelines._harness.pre_review_seeded import (  # noqa: E402
    MERGE,
    RETYPE_REALISTIC,
    RETYPE_SAME_LAYER,
    ClassCatalog,
    SeededDocument,
    SeededScore,
    build_seeded,
    gate,
    recorded_mistypes,
    score_seeded,
)

RECORDINGS = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "integration"
    / "fixtures"
    / "cassettes"
    / "extraction_benchmark_single_call"
)
TAKES = (1, 2, 3)
# The arms, as the decision rule names them: model and effort
ARMS = {"opus": ("claude-opus-5-5", "medium"), "haiku": ("claude-haiku-5-5", None)}
CASSETTES = RECORDINGS.parent / "pre_review_seeded"
RESULTS = BENCHMARK_DIR.with_name("extraction_benchmark_pre_review")
# The experiment's cap, every phase together (the user's, 2026-11-23)
BUDGET_USD = 40.0

# The four items the person split by hand in Gate D
# (documentation/extraction/experiments/2026-11-21-gate-d-real-documents.md)
GATE_D_SPLITS = (
    "Torx T20, T25",
    "Copper water supply kits WX8X2, WX8X3, WX8X4",
    "Straight and Phillips blade screwdriver",
    "Compression nut and ferrule",
)


def recorded_titles(document_id: str) -> list[tuple[str, str]]:
    """single_call's recorded (title, class) answers for a document; empty when not recorded."""
    path = RECORDINGS / f"{document_id}.json"
    if not path.exists():
        return []
    found: list[tuple[str, str]] = []
    for response in json.loads(path.read_text(encoding="utf-8")).values():
        content = str(response.get("content") or "")
        if '"individuals"' not in content:
            continue
        # Every class is accepted here: the answer is read as recorded, not checked
        individuals, _ = parse_individuals(content, "", _AnyClass())
        found.extend((i.mention.name, i.class_ref) for i in individuals)
    return found


class _AnyClass(Mapping[str, str]):
    """A class-reference lookup that accepts every reference as written."""

    def __getitem__(self, key: str) -> str:
        return key

    def __iter__(self):  # pragma: no cover - never iterated
        return iter(())

    def __len__(self) -> int:  # pragma: no cover
        return 0

    def get(self, key: str, default: Any = None) -> str:  # type: ignore[override]
        return key


def witness_report() -> dict[str, Any]:
    gate_d = {title: split_witness(title) for title in GATE_D_SPLITS}
    documents = {}
    for document_id in (*DEV_DOCUMENTS, *HOLDOUT_DOCUMENTS):
        gold = load_gold(document_id)
        marked = [g.title for g in gold.individuals if split_witness(g.title)]
        recorded = [title for title, _ in recorded_titles(document_id)]
        documents[document_id] = {
            "gold_titles": len(gold.individuals),
            "gold_marked": len(marked),
            "gold_marked_examples": marked[:6],
            "recorded_titles": len(recorded),
            "recorded_marked": sum(1 for t in recorded if split_witness(t)),
        }
    return {
        "gate_d_splits": gate_d,
        "gate_d_all_marked": all(gate_d.values()),
        "documents": documents,
    }


def oracle_stage(
    document: SeededDocument, gold_titles: Mapping[str, Any]
) -> dict[int, PreReviewVerdict]:
    """A fake stage that knows every seed: it puts each one right and leaves the rest alone."""
    verdicts: dict[int, PreReviewVerdict] = {}
    for item in document.items:
        seed = document.seeds[item.index]
        if seed.stratum == MERGE:
            parts = tuple(
                PreReviewPart(gold_titles[key].title, gold_titles[key].class_ref)
                for key in seed.gold_keys
            )
            verdicts[item.index] = PreReviewVerdict(
                PreReviewAnswer.SPLIT,
                PreReviewQuestion.SPLIT,
                "oracle",
                item.title,
                item.class_ref,
                parts=parts,
            )
        elif seed.stratum in (RETYPE_REALISTIC, RETYPE_SAME_LAYER):
            verdicts[item.index] = PreReviewVerdict(
                PreReviewAnswer.RETYPE,
                PreReviewQuestion.RETYPE,
                "oracle",
                item.title,
                item.class_ref,
                class_ref=gold_titles[seed.gold_keys[0]].class_ref,
            )
    return verdicts


def seeded_report(fake: str) -> dict[str, Any]:
    catalog = ClassCatalog.from_bundle(load_schema_bundle())
    total = SeededScore()
    takes = []
    for document_id in DEV_DOCUMENTS:
        gold = load_gold(document_id)
        mistypes = recorded_mistypes(gold, recorded_titles(document_id))
        by_key = {g.key: g for g in gold.individuals}
        for take in TAKES:
            document = build_seeded(gold, catalog, take, mistypes)
            verdicts = oracle_stage(document, by_key) if fake == "oracle" else {}
            score = score_seeded(document, gold, verdicts)
            total.add(score)
            takes.append(
                {
                    "document": document_id,
                    "take": take,
                    "items": len(document.items),
                    "strata": document.stratum_counts(),
                    "merge_examples": [
                        document.items[i].title
                        for i, s in document.seeds.items()
                        if s.stratum == MERGE
                    ][:3],
                    "realistic_examples": [
                        f"{document.items[i].title}: {s.planted_class} (gold {by_key[s.gold_keys[0]].class_ref})"
                        for i, s in document.seeds.items()
                        if s.stratum == RETYPE_REALISTIC
                    ][:3],
                }
            )
    return {
        "fake_stage": fake,
        "takes": takes,
        "score": total.to_json(),
        "precision": total.precision(),
        "gate": [vars(g) for g in gate(total)],
    }


# ---------------------------------------------------------------- the real stage


def stage_catalog() -> tuple[str, dict[str, str]]:
    """The class catalog the stage is offered, as single_call's: every non-derived class by kind."""
    bundle = load_schema_bundle()
    kinds = {s["identifier"]: s["title"] for s in bundle["schemes"]}
    classes = [
        CatalogClass(
            class_reference(c),
            c["title"],
            kinds.get(c["scheme"], c["scheme"]),
            c.get("description") or "",
        )
        for c in bundle["classes"]
        if not c.get("derived")
    ]
    return build_catalog(bundle["taxonomy"]["title"], classes)


def stage_input(document: SeededDocument) -> list[FoundIndividual]:
    return [
        FoundIndividual(Mention(item.title, "thing", item.quote), item.class_ref)
        for item in document.items
    ]


def run_stage(document: SeededDocument, arm: str, provider: Any) -> PreReviewResult:
    model, effort = ARMS[arm]
    catalog, refs = stage_catalog()
    return review_individuals(
        provider,
        time.sleep,
        document.text,
        stage_input(document),
        catalog,
        refs,
        model,
        0.0,
        PRE_REVIEW_STAGE.default,
        effort=effort,
    )


def cassette_path(arm: str, document_id: str, take: int) -> Path:
    return CASSETTES / arm / f"take{take}" / f"{document_id}.json"


def seeded_documents() -> list[tuple[Any, SeededDocument]]:
    """The dev documents' planted errors for every take, with their gold."""
    catalog = ClassCatalog.from_bundle(load_schema_bundle())
    documents = []
    for document_id in DEV_DOCUMENTS:
        gold = load_gold(document_id)
        mistypes = recorded_mistypes(gold, recorded_titles(document_id))
        for take in TAKES:
            documents.append((gold, build_seeded(gold, catalog, take, mistypes)))
    return documents


def record_seeded(arm: str) -> None:
    """Record every missing take of an arm with the live model, each call metered."""
    from adapters.llm.provider_router import LLMProviderRouter
    from scripts.benchmark_external import Ledger, anthropic_key, cost_usd, usage_of
    from tests.integration.pipelines._harness.cassettes import RecordingLLMProvider

    model, _ = ARMS[arm]
    ledger = Ledger(RESULTS / "ledger.jsonl", BUDGET_USD)
    router = LLMProviderRouter(anthropic_api_key=anthropic_key())  # Anthropic only
    client = router._providers["anthropic"]._client
    create = client.messages.create
    where = {"document": "", "take": 0}

    def metered_create(**kwargs: Any) -> Any:
        prompt_chars = len(json.dumps(kwargs.get("system", ""))) + len(
            json.dumps(kwargs.get("messages", ""))
        )
        worst = cost_usd(
            model,
            {
                "input": 0,
                "cache_write": prompt_chars // 3,
                "cache_read": 0,
                "output": kwargs.get("max_tokens", 16000),
            },
        )
        ledger.reserve(worst)
        try:
            response = create(**kwargs)
        except BaseException:
            ledger.release(worst)
            raise
        usage = usage_of(response.usage)
        ledger.record(
            {
                "phase": 1,
                "arm": arm,
                "model": model,
                **where,
                "usage": usage,
                "usd": cost_usd(model, usage),
            },
            worst,
        )
        return response

    client.messages.create = metered_create
    for _, document in seeded_documents():
        path = cassette_path(arm, document.document_id, document.take)
        if path.exists():
            continue
        where.update(document=document.document_id, take=document.take)
        recorder = RecordingLLMProvider(router, path)
        began = time.perf_counter()
        result = run_stage(document, arm, recorder)
        if result.failure_reason:
            # Nothing usable was recorded: leave no cassette, so the take is recorded again
            print(
                f"{arm} {document.document_id} take{document.take}: FAILED: {result.failure_reason}"
            )
            raise SystemExit(1)
        recorder.flush()
        print(
            f"{arm} {document.document_id} take{document.take}: {len(result.verdicts)} verdicts,"
            f" {time.perf_counter() - began:.0f}s, spent so far ${ledger.spent():.2f}"
            + (f", FAILED: {result.failure_reason}" if result.failure_reason else ""),
            flush=True,
        )


def replay_seeded(arm: str) -> dict[str, Any]:
    """Score an arm's recorded takes, free: every call is answered from its cassette."""
    from tests.integration.pipelines._harness.cassettes import CassetteLLMProvider

    total = SeededScore()
    takes = []
    for gold, document in seeded_documents():
        path = cassette_path(arm, document.document_id, document.take)
        if not path.exists():
            takes.append(
                {"document": document.document_id, "take": document.take, "status": "not recorded"}
            )
            continue
        provider = CassetteLLMProvider(path)
        result = run_stage(document, arm, provider)
        if provider.misses or result.failure_reason:
            takes.append(
                {
                    "document": document.document_id,
                    "take": document.take,
                    "status": "stale" if provider.misses else "failed",
                    "failure": result.failure_reason,
                }
            )
            continue
        score = score_seeded(document, gold, result.verdicts)
        total.add(score)
        takes.append(
            {
                "document": document.document_id,
                "take": document.take,
                "status": "scored",
                "score": score.to_json(),
                "precision": score.precision(),
                "warnings": result.warnings,
                "verdicts": {
                    str(i): {
                        "item": document.items[i].title,
                        "stratum": document.seeds[i].stratum,
                        "answer": v.answer.value,
                        "class": v.class_ref,
                        "parts": [p.title for p in v.parts],
                        "reasoning": v.reasoning,
                    }
                    for i, v in sorted(result.verdicts.items())
                },
            }
        )
    return {
        "arm": arm,
        "model": ARMS[arm][0],
        "takes": takes,
        "score": total.to_json(),
        "precision": total.precision(),
        "gate": [vars(g) for g in gate(total)],
    }


def spend_report() -> dict[str, Any]:
    path = RESULTS / "ledger.jsonl"
    rows = (
        [json.loads(line) for line in path.read_text().splitlines() if line]
        if path.exists()
        else []
    )
    by_arm: dict[str, float] = {}
    for row in rows:
        by_arm[row.get("arm", "?")] = by_arm.get(row.get("arm", "?"), 0.0) + row["usd"]
    return {
        "calls": len(rows),
        "usd": round(sum(by_arm.values()), 4),
        "by_arm": {k: round(v, 4) for k, v in by_arm.items()},
    }


# ---------------------------------------------------------------- Phase 2: the benchmark

DOCUMENTS = (*DEV_DOCUMENTS, *HOLDOUT_DOCUMENTS)
PHASE2_CASSETTES = RECORDINGS.parent / "pre_review_benchmark"
# The stage's setting per arm, as the configuration carries it
REVIEW_SETTINGS = {
    "haiku": {"model": "claude-haiku-5-5"},
    "opus": {"model": "claude-opus-5-5", "effort": "medium"},
}


class _ArmTarget:
    """single_call's target with the arm's pre_review setting in its configuration."""

    def __init__(self, base: Any, setting: Mapping[str, Any] | None) -> None:
        self._base = base
        self.config = {**base.config, **({"pre_review": dict(setting)} if setting else {})}

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base, name)


class _Chain:
    """
    Answers from the first recording that has the prompt; with none, from the
    live recorder when there is one, else counts a miss and raises.
    """

    def __init__(self, replays: list[Any], live: Any = None) -> None:
        self.replays, self.live, self.misses = replays, live, 0

    def complete(self, **request: Any) -> Any:
        from tests.integration.pipelines._harness.cassettes import CassetteStaleError

        for replay in self.replays:
            try:
                return replay.complete(**request)
            except CassetteStaleError:
                continue
        if self.live is None:
            self.misses += 1
            raise CassetteStaleError("no recording answers this prompt")
        return self.live.complete(**request)

    def forget(self, **request: Any) -> None:
        if self.live is not None:
            self.live.forget(**request)

    def is_model_available(self, model: str) -> bool:
        return True


def base_target() -> Any:
    from scripts.benchmark_replay import resolve_target

    return resolve_target("single_call", "extraction-single-call")


def off_cassette(document_id: str, take: int) -> Path:
    if take == 1:
        return RECORDINGS / f"{document_id}.json"
    return PHASE2_CASSETTES / "off" / f"take{take}" / f"{document_id}.json"


def arm_cassette(arm: str, document_id: str, take: int) -> Path:
    return PHASE2_CASSETTES / arm / f"take{take}" / f"{document_id}.json"


def _metered_router(ledger: Any, where: dict[str, Any], phase: int) -> Any:
    """The Anthropic router with every call, streamed or not, metered on the ledger."""
    from adapters.llm.provider_router import LLMProviderRouter
    from scripts.benchmark_external import anthropic_key, cost_usd, usage_of

    router = LLMProviderRouter(anthropic_api_key=anthropic_key())  # Anthropic only
    client = router._providers["anthropic"]._client
    create, stream = client.messages.create, client.messages.stream

    def worst(kwargs: Mapping[str, Any]) -> float:
        chars = len(json.dumps(kwargs.get("system", ""))) + len(
            json.dumps(kwargs.get("messages", ""))
        )
        return cost_usd(
            kwargs["model"],
            {
                "input": 0,
                "cache_write": chars // 3,
                "cache_read": 0,
                "output": kwargs.get("max_tokens", 16000),
            },
        )

    def record(kwargs: Mapping[str, Any], message: Any, reserved: float) -> None:
        usage = usage_of(message.usage)
        ledger.record(
            {
                "phase": phase,
                **where,
                "model": kwargs["model"],
                "usage": usage,
                "usd": cost_usd(kwargs["model"], usage),
            },
            reserved,
        )

    def metered_create(**kwargs: Any) -> Any:
        reserved = worst(kwargs)
        ledger.reserve(reserved)
        try:
            message = create(**kwargs)
        except BaseException:
            ledger.release(reserved)
            raise
        record(kwargs, message, reserved)
        return message

    class _MeteredStream:
        def __init__(self, kwargs: Mapping[str, Any]) -> None:
            self.kwargs, self.reserved = kwargs, worst(kwargs)
            ledger.reserve(self.reserved)
            try:
                self.manager = stream(**kwargs)
            except BaseException:
                ledger.release(self.reserved)
                raise

        def __enter__(self) -> Any:
            self.inner = self.manager.__enter__()
            return self.inner

        def __exit__(self, *exc: Any) -> Any:
            if exc[0] is not None:
                ledger.release(self.reserved)
                return self.manager.__exit__(*exc)
            try:
                message = self.inner.get_final_message()
            except BaseException:
                ledger.release(self.reserved)
                raise
            record(self.kwargs, message, self.reserved)
            return self.manager.__exit__(*exc)

    client.messages.create = metered_create
    client.messages.stream = lambda **kwargs: _MeteredStream(kwargs)
    return router


def record_benchmark(arm: str) -> None:
    """Record every missing take of an arm (off: the incumbent's takes 2-3), each call metered."""
    import asyncio

    from scripts.benchmark_external import Ledger
    from scripts.benchmark_replay import benchmark_ontology, extract_document
    from tests.integration.pipelines._harness.cassettes import (
        CassetteLLMProvider,
        RecordingLLMProvider,
    )

    ledger = Ledger(RESULTS / "ledger.jsonl", BUDGET_USD)
    where: dict[str, Any] = {"phase": 2, "arm": arm}
    router = _metered_router(ledger, where, 2)
    target = _ArmTarget(base_target(), REVIEW_SETTINGS.get(arm))
    for take in TAKES:
        for document_id in DOCUMENTS:
            if arm == "off":
                path = off_cassette(document_id, take)
                replays: list[Any] = []
            else:
                path = arm_cassette(arm, document_id, take)
                incumbent = off_cassette(document_id, take)
                if not incumbent.exists():
                    print(f"{arm} {document_id} take{take}: no incumbent take yet, skipped")
                    continue
                replays = [CassetteLLMProvider(incumbent)]
            if path.exists():
                continue
            where.update(document=document_id, take=take)
            recorder = RecordingLLMProvider(router, path)
            began = time.perf_counter()
            try:
                asyncio.run(
                    extract_document(
                        benchmark_ontology(), _Chain(replays, recorder), document_id, target
                    )
                )
            except Exception as exc:  # a failed take records nothing, so it is recorded again
                print(f"{arm} {document_id} take{take}: FAILED: {exc}", flush=True)
                raise SystemExit(1)
            recorder.flush()
            print(
                f"{arm} {document_id} take{take}: {time.perf_counter() - began:.0f}s,"
                f" spent so far ${ledger.spent():.2f}",
                flush=True,
            )


def _merged_predictions(gold: Any, individuals: list[Any]) -> int:
    """
    Predictions that are several gold individuals in one, so a person would
    split them: not a statement, the title is no gold name, and cut at its list separators it
    gives two or more pieces that are each a different gold individual's name.
    """
    import re as _re

    from tests.integration.pipelines._harness.benchmark import name_key

    owner = {name: g.key for g in gold.individuals for name in g.names}
    count = 0
    for prediction in individuals:
        # A statement (a goal, requirement...) names several things and is still one item
        statement = any(ref.startswith("motivation.") for ref in prediction.class_refs)
        if statement or name_key(prediction.title) in owner:
            continue
        pieces = _re.split(r",\s+|\s+(?:and|&|\+)\s+|/", prediction.title)
        named = {owner[name_key(piece)] for piece in pieces if name_key(piece) in owner}
        count += len(named) >= 2
    return count


def score_benchmark_take(arm: str, document_id: str, take: int) -> dict[str, Any] | None:
    """Replay one take of an arm and score it; None when it is not recorded or stale."""
    import asyncio

    from scripts.benchmark_replay import benchmark_ontology, extract_document
    from tests.integration.pipelines._harness.benchmark import score
    from tests.integration.pipelines._harness.cassettes import CassetteLLMProvider

    incumbent = off_cassette(document_id, take)
    paths = [incumbent] if arm == "off" else [arm_cassette(arm, document_id, take), incumbent]
    if not all(p.exists() for p in paths):
        return None
    chain = _Chain([CassetteLLMProvider(p) for p in paths])
    target = _ArmTarget(base_target(), REVIEW_SETTINGS.get(arm))
    try:
        individuals, relationships = asyncio.run(
            extract_document(benchmark_ontology(), chain, document_id, target)
        )
    except Exception as exc:
        return {"status": "stale" if chain.misses else "failed", "detail": str(exc)[:200]}
    gold = load_gold(document_id)
    result = score(gold, individuals, relationships)
    missed = {m["key"] for m in result.missed}
    mistyped = {m["key"] for m in result.mistyped}
    found = {g.key for g in gold.individuals} - missed
    merged = _merged_predictions(gold, individuals)
    return {
        "status": "scored",
        "metrics": {
            k: result.metrics[k]
            for k in (
                "typed_f1",
                "f1",
                "type_accuracy",
                "relationship_recall",
                "relationship_precision",
            )
        },
        "mistyped": sorted(mistyped),
        "typed": sorted(found - mistyped),
        "merged": merged,
        "edits_needed": len(mistyped) + merged,
        "predicted": len(individuals),
    }


def benchmark_report() -> dict[str, Any]:
    """Every arm's takes against the incumbent's, paired by take, and the decision rule applied."""
    from statistics import mean

    rows: dict[str, dict[tuple[str, int], Any]] = {}
    for arm in ("off", *REVIEW_SETTINGS):
        rows[arm] = {(d, t): score_benchmark_take(arm, d, t) for d in DOCUMENTS for t in TAKES}
    report: dict[str, Any] = {"takes": {}, "arms": {}}
    for arm, cells in rows.items():
        report["takes"][arm] = {f"{d} take{t}": cell for (d, t), cell in cells.items()}
    for arm in REVIEW_SETTINGS:
        paired = {}
        for (d, t), cell in rows[arm].items():
            off = rows["off"][(d, t)]
            if not (cell and off and cell.get("status") == off.get("status") == "scored"):
                continue
            fixes = len(set(cell["typed"]) - set(off["typed"]) & set(off["mistyped"]))
            harms = len(set(off["typed"]) & set(cell["mistyped"]))
            paired[(d, t)] = {
                "typed_f1": cell["metrics"]["typed_f1"] - off["metrics"]["typed_f1"],
                "relationship_recall": (
                    cell["metrics"]["relationship_recall"] - off["metrics"]["relationship_recall"]
                ),
                "edits_off": off["edits_needed"],
                "edits_arm": cell["edits_needed"],
                "fixes": fixes,
                "harms": harms,
            }
        if not paired:
            report["arms"][arm] = {"status": "no paired takes"}
            continue

        def split(docs: tuple[str, ...], key: str) -> list[float]:
            per_take = []
            for t in TAKES:
                values = [paired[(d, t)][key] for d in docs if (d, t) in paired]
                if values:
                    per_take.append(mean(values))
            return per_take

        edit_takes = [
            (paired[("edit_check", t)]["edits_off"], paired[("edit_check", t)]["edits_arm"])
            for t in TAKES
            if ("edit_check", t) in paired
        ]
        gitlab_takes = [
            (
                paired[("gitlab_architecture", t)]["edits_off"],
                paired[("gitlab_architecture", t)]["edits_arm"],
            )
            for t in TAKES
            if ("gitlab_architecture", t) in paired
        ]
        cut = (
            (1 - sum(a for _, a in edit_takes) / sum(o for o, _ in edit_takes))
            if edit_takes and sum(o for o, _ in edit_takes)
            else 0.0
        )
        dev_f1, hold_f1 = split(DEV_DOCUMENTS, "typed_f1"), split(HOLDOUT_DOCUMENTS, "typed_f1")
        dev_rel = split(DEV_DOCUMENTS, "relationship_recall")
        dev_cells = [v for (d, _), v in paired.items() if d in DEV_DOCUMENTS]
        fixes, harms = sum(v["fixes"] for v in dev_cells), sum(v["harms"] for v in dev_cells)
        precision = fixes / (fixes + harms) if fixes + harms else None
        complete = len(paired) == len(DOCUMENTS) * len(TAKES)
        checks = {
            "a_edits_cut_30pct_every_take": (
                bool(edit_takes) and cut >= 0.30 and all(a < o for o, a in edit_takes)
            ),
            "a_gitlab_not_the_other_way": (
                sum(a for _, a in gitlab_takes) <= sum(o for o, _ in gitlab_takes)
            ),
            "b_typed_f1_mean_drop_le_0.02": (
                bool(dev_f1 and hold_f1) and mean(dev_f1) >= -0.02 and mean(hold_f1) >= -0.02
            ),
            "b_no_take_below_-0.04": all(v >= -0.04 for v in dev_f1 + hold_f1),
            "c_relationship_recall_drop_le_0.03": bool(dev_rel) and mean(dev_rel) >= -0.03,
            "d_stage_precision_ge_0.7": precision is not None and precision >= 0.7,
        }
        rejected = (precision is not None and precision < 0.5) or bool(
            dev_f1 and mean(dev_f1) < -0.04
        )
        report["arms"][arm] = {
            "complete": complete,
            "edit_check_edits_off_vs_arm": edit_takes,
            "gitlab_edits_off_vs_arm": gitlab_takes,
            "edit_cut": round(cut, 3),
            "typed_f1_delta_dev_by_take": [round(v, 4) for v in dev_f1],
            "typed_f1_delta_holdout_by_take": [round(v, 4) for v in hold_f1],
            "relationship_recall_delta_dev_by_take": [round(v, 4) for v in dev_rel],
            "dev_fixes": fixes,
            "dev_harms": harms,
            "stage_precision": precision,
            "checks": checks,
            "verdict_phase2": (
                "incomplete"
                if not complete
                else (
                    "reject"
                    if rejected
                    else "adopt (pending Phase 3 veto)" if all(checks.values()) else "inconclusive"
                )
            ),
        }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    witness = commands.add_parser("witness", help="Where the split witness fires (free)")
    witness.add_argument("--json", action="store_true")
    seeded = commands.add_parser("seeded", help="Planted errors, scored with a fake stage (free)")
    stage = seeded.add_mutually_exclusive_group(required=True)
    stage.add_argument("--fake", choices=("keep", "oracle"))
    stage.add_argument("--arm", choices=sorted(ARMS))
    seeded.add_argument("--spend", action="store_true", help="Record missing takes (costs)")
    seeded.add_argument("--json", action="store_true")
    bench = commands.add_parser("benchmark", help="Phase 2: the stage in single_call, paired takes")
    bench.add_argument("--arm", choices=("off", *sorted(REVIEW_SETTINGS)))
    bench.add_argument(
        "--spend", action="store_true", help="Record the arm's missing takes (costs)"
    )
    args = parser.parse_args()

    if args.command == "benchmark":
        if args.spend:
            if not args.arm:
                raise SystemExit("--spend needs --arm")
            record_benchmark(args.arm)
        report = benchmark_report()
        report["spend"] = spend_report()
        out = RESULTS / "benchmark.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, default=list) + "\n", encoding="utf-8")
        for arm, summary in report["arms"].items():
            print(f"{arm}: {json.dumps(summary, default=list)}")
        print(f"spent: {report['spend']}; report in {out}")
        return

    if args.command == "seeded" and args.arm:
        if args.spend:
            record_seeded(args.arm)
        report = replay_seeded(args.arm)
        report["spend"] = spend_report()
        out = RESULTS / "seeded" / f"{args.arm}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        if args.json:
            print(json.dumps(report, indent=2))
            return
        print(f"Arm {args.arm} ({report['model']}), report in {out}")
        for take in report["takes"]:
            print(
                f"  {take['document']} take {take['take']}: {take['status']}"
                + (f", precision {take['precision']}" if take.get("status") == "scored" else "")
            )
        _print_score(report)
        print(f"spent: {report['spend']}")
        return
    report = witness_report() if args.command == "witness" else seeded_report(args.fake)
    if args.json:
        print(json.dumps(report, indent=2))
        return
    if args.command == "witness":
        print(
            f"Gate D splits marked: {sum(report['gate_d_splits'].values())} of {len(GATE_D_SPLITS)}"
        )
        for title, marked in report["gate_d_splits"].items():
            print(f"  {'yes' if marked else 'NO '}  {title}")
        print("\ndocument                gold marked   recorded marked")
        for document_id, row in report["documents"].items():
            print(
                f"{document_id:22}  {row['gold_marked']:>3} of {row['gold_titles']:<4}"
                f"  {row['recorded_marked']:>3} of {row['recorded_titles']}"
            )
        return
    print(f"Fake stage: {report['fake_stage']}")
    for take in report["takes"]:
        strata = ", ".join(f"{k} {v}" for k, v in take["strata"].items())
        print(f"  {take['document']} take {take['take']}: {take['items']} items ({strata})")
    _print_score(report)


def _print_score(report: dict[str, Any]) -> None:
    for stratum, cell in report["score"].items():
        print(
            f"  {stratum:18} items {cell['items']:>3}  fixed {cell['fixed']:>3}  harmed {cell['harmed']:>2}"
            f"  neutral {cell['neutral']:>2}  missed {cell['missed']:>3}"
            f"  changed wrongly {cell['changed_wrongly']:>2}  unsure {cell['unsure']:>2}"
        )
    print(f"precision: {report['precision']}")
    for g in report["gate"]:
        print(
            f"  {g['question']}: recovery {g['recovery']:.2f} (needs {g['needed']}),"
            f" harms {g['harms']}/{g['controls']} (upper {g['harm_upper']:.3f})"
            f" -> {'pass' if g['passed'] else 'fail'}"
        )


if __name__ == "__main__":
    main()
