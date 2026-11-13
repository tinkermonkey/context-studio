"""
The individual-extraction benchmark: hand-made extractions of prose documents
against the Documentation Robotics schema, and how a pipeline run compares.

The gold extractions live in tests/integration/fixtures/pipelines/extraction_benchmark/
(see its README). This script works against a running Context Studio server:

    validate   Check every gold file against its source and the schema snapshot (no server).
    load       Put a gold extraction into the workspace as a dataset of the DR taxonomy:
               the source document, then one proposal of individual and relationship
               creates, each with its passages, applied.
    score      Score a proposal an extraction run produced against the gold extraction.
    run        Extract a benchmark document with a pipeline configuration, in a fresh
               dataset, and score the proposal. This calls the configured LLM (it costs
               money) and needs --spend.

Usage (from local-server/, venv active; the server on http://127.0.0.1:8000):
    python scripts/extraction_benchmark.py validate
    python scripts/extraction_benchmark.py load [--document ID] [--replace]
    python scripts/extraction_benchmark.py score --document ID --proposal PROPOSAL_ID
    python scripts/extraction_benchmark.py run --document ID [--configuration REF] --spend
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.integration.pipelines._harness.benchmark import (
    BENCHMARK_DIR,
    BenchmarkScore,
    Passage,
    Predicted,
    PredictedRelationship,
    benchmark_documents,
    load_gold,
    score,
    validate_gold,
)

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
REPORTS_DIR = Path(__file__).resolve().parents[1] / "experiments" / "reports"
FINISHED = {"completed", "failed", "cancelled"}
POLL_SECONDS = 5
# Operations sent per proposal; a gold extraction is split so each proposal validates quickly.
LIST_LIMIT = 5000


class ApiError(RuntimeError):
    """The server refused a request."""


class Api:
    """A minimal JSON client for the Context Studio API."""

    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")

    def get(self, path: str, **query: Any) -> Any:
        params = {k: v for k, v in query.items() if v is not None}
        url = f"{self._base}{path}" + (f"?{urllib.parse.urlencode(params)}" if params else "")
        return self._send(urllib.request.Request(url))

    def post(self, path: str, body: Any, **query: Any) -> Any:
        url = f"{self._base}{path}" + (f"?{urllib.parse.urlencode(query)}" if query else "")
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return self._send(request)

    def delete(self, path: str) -> Any:
        return self._send(urllib.request.Request(f"{self._base}{path}", method="DELETE"))

    def upload(self, path: str, fields: dict[str, str], file_name: str, data: bytes) -> Any:
        """A multipart/form-data upload of one file with text fields."""
        boundary = uuid.uuid4().hex
        parts = []
        for name, value in fields.items():
            parts.append(
                (
                    f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"'
                    f"\r\n\r\n{value}\r\n"
                ).encode()
            )
        parts.append(
            (
                f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
                f'filename="{file_name}"\r\nContent-Type: text/markdown\r\n\r\n'
            ).encode()
            + data
            + b"\r\n"
        )
        parts.append(f"--{boundary}--\r\n".encode())
        request = urllib.request.Request(
            f"{self._base}{path}",
            data=b"".join(parts),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        return self._send(request)

    @staticmethod
    def _send(request: urllib.request.Request) -> Any:
        try:
            with urllib.request.urlopen(request, timeout=600) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ApiError(
                f"{request.get_method()} {request.full_url}: {exc.code} {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise ApiError(f"Cannot reach {request.full_url}: {exc.reason}") from exc
        return json.loads(body) if body else None


def _items(payload: Any) -> list[dict[str, Any]]:
    return payload["items"] if isinstance(payload, dict) else payload


class Schema:
    """The workspace's DR taxonomy: ids for the classes and relationship types gold uses."""

    def __init__(self, api: Api, identifier: str) -> None:
        taxonomy = next(
            (t for t in _items(api.get("/api/taxonomies")) if t["identifier"] == identifier), None
        )
        if taxonomy is None:
            raise ApiError(f"The workspace has no taxonomy {identifier!r}")
        self.taxonomy_id: str = taxonomy["id"]
        self.spec_version = (taxonomy.get("source_revision") or {}).get("spec_version")
        classes = [
            c
            for c in _items(api.get("/api/classes", taxonomy_id=self.taxonomy_id, limit=LIST_LIMIT))
            if c["taxonomy_id"] == self.taxonomy_id
        ]
        self.class_id = {self._ref(c): c["id"] for c in classes}
        self.class_ref = {c["id"]: self._ref(c) for c in classes}
        predicates = {
            p["id"]: p["identifier"]
            for p in api.get(f"/api/taxonomies/{self.taxonomy_id}/predicates")
        }
        self.property_id: dict[tuple[str, str, str], str] = {}
        self.property_triple: dict[str, tuple[str, str, str]] = {}
        for prop in _items(api.get("/api/properties", limit=LIST_LIMIT)):
            domain, range_ = prop.get("domain_class_id"), prop.get("range_class_id")
            if domain in self.class_ref and range_ in self.class_ref:
                predicate = predicates.get(prop.get("predicate_id")) or prop["canonical_predicate"]
                triple = (self.class_ref[domain], predicate, self.class_ref[range_])
                self.property_id[triple] = prop["id"]
                self.property_triple[prop["id"]] = triple

    @staticmethod
    def _ref(cls: dict[str, Any]) -> str:
        references = cls.get("external_references") or []
        return references[0]["identifier"] if references else cls["identifier"]


def _documents(selected: list[str] | None) -> list[str]:
    available = benchmark_documents()
    unknown = [d for d in selected or [] if d not in available]
    if unknown:
        raise SystemExit(f"No benchmark document {unknown}; there are: {', '.join(available)}")
    return selected or available


def _gold_json(document_id: str) -> dict[str, Any]:
    return json.loads((BENCHMARK_DIR / document_id / "gold.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- validate


def cmd_validate(args: argparse.Namespace) -> int:
    failed = False
    for document_id in _documents(args.document):
        problems = validate_gold(document_id)
        gold = load_gold(document_id)
        core = sum(1 for g in gold.individuals if g.tier == "core")
        print(
            f"{document_id}: {len(gold.individuals)} individuals ({core} core), "
            f"{len(gold.relationships)} relationships, {len(problems)} problems"
        )
        for problem in problems:
            print(f"  ! {problem}")
        failed = failed or bool(problems)
    return 1 if failed else 0


# ---------------------------------------------------------------- load


def _dataset(api: Api, taxonomy_id: str, identifier: str) -> dict[str, Any] | None:
    datasets = api.get("/api/datasets", taxonomy_id=taxonomy_id)
    return next((d for d in datasets if d["identifier"] == identifier), None)


def _add_source(
    api: Api, schema: Schema, dataset: str, document_id: str, title: str
) -> dict[str, Any]:
    data = (BENCHMARK_DIR / document_id / "source.md").read_bytes()
    source = api.upload(
        "/api/sources",
        {"taxonomy_id": schema.taxonomy_id, "dataset": dataset, "title": title},
        f"{document_id}.md",
        data,
    )
    if source["status"] != "ready":
        raise ApiError(
            f"The source was not read: {source.get('failure')} {source.get('failure_detail')}"
        )
    text = api.get(f"/api/sources/{source['id']}/text")
    stored = text["text"] if isinstance(text, dict) else text
    expected = data.decode("utf-8")
    if stored != expected:
        raise ApiError(
            "The stored source text differs from source.md, so the gold offsets would not line up"
        )
    return source


def _evidence(passages: list[dict[str, Any]], source_id: str) -> list[dict[str, Any]]:
    return [
        {
            "source_id": source_id,
            "page": None,
            "start": p["start"],
            "end": p["end"],
            "quote": p["quote"],
        }
        for p in passages
    ]


def _operations(gold: dict[str, Any], schema: Schema, source_id: str) -> list[dict[str, Any]]:
    """A gold extraction as proposal operations: individual creates, then relationship creates."""
    operations: list[dict[str, Any]] = []
    class_of = {}
    for item in gold["individuals"]:
        class_of[item["key"]] = item["class"]
        fields: dict[str, Any] = {
            "title": item["title"],
            "class_ids": [schema.class_id[item["class"]]],
            "description": item["description"],
        }
        if item.get("data"):
            fields["data_properties"] = item["data"]
        operations.append(
            {
                "seq": len(operations) + 1,
                "op": "create",
                "kind": "individual",
                "ref": item["key"],
                "fields": fields,
                "notes": f"benchmark tier: {item['tier']}",
                "evidence": _evidence(item["evidence"], source_id),
                "probability": 1.0,
            }
        )
    for rel in gold["relationships"]:
        triple = (class_of[rel["source"]], rel["predicate"], class_of[rel["target"]])
        operations.append(
            {
                "seq": len(operations) + 1,
                "op": "create",
                "kind": "relationship",
                "fields": {
                    "source_id": f"${rel['source']}",
                    "target_id": f"${rel['target']}",
                    "property_definition_id": schema.property_id[triple],
                },
                "evidence": _evidence(rel["evidence"], source_id),
                "probability": 1.0,
            }
        )
    return operations


def load_document(api: Api, schema: Schema, document_id: str, replace: bool) -> None:
    gold = _gold_json(document_id)
    document = gold["document"]
    identifier, title = document["dataset"]["identifier"], document["dataset"]["title"]
    gold_version = gold["taxonomy"].get("spec_version")
    if gold_version != schema.spec_version:
        print(
            f"  note: gold was made against DR spec {gold_version}; "
            f"the workspace has {schema.spec_version}"
        )
    missing = sorted({i["class"] for i in gold["individuals"]} - set(schema.class_id))
    if missing:
        raise ApiError(f"The workspace schema lacks classes gold uses: {missing}")

    existing = _dataset(api, schema.taxonomy_id, identifier)
    if existing is not None:
        if existing["individual_count"] and not replace:
            print(
                f"{document_id}: dataset {identifier!r} already holds "
                f"{existing['individual_count']} "
                "individuals; pass --replace to load it again"
            )
            return
        if existing["individual_count"]:
            raise ApiError(
                f"Dataset {identifier!r} holds individuals. Revert the proposal that loaded it "
                "(Review queue, or POST /api/proposals/<id>/revert), then run load again"
            )
    else:
        existing = api.post(
            "/api/datasets",
            {"taxonomy_id": schema.taxonomy_id, "identifier": identifier, "title": title},
        )
    source = _add_source(api, schema, identifier, document_id, document["title"])
    proposal_body = {
        "taxonomy_id": schema.taxonomy_id,
        "title": f"Benchmark extraction: {document['title']}",
        "rationale": (
            f"Hand-made extraction of {document['source_url']} ({document['license']}), the "
            "baseline individual-extraction pipelines are scored against. Loaded by "
            "scripts/extraction_benchmark.py from "
            f"tests/integration/fixtures/pipelines/extraction_benchmark/{document_id}/gold.json."
        ),
        "source": "user",
        "source_detail": f"extraction-benchmark:{document_id}",
        "dataset_id": existing["id"],
        "operations": _operations(gold, schema, source["id"]),
    }
    api.post("/api/proposals", proposal_body, dry_run="true")
    proposal = api.post("/api/proposals", proposal_body)
    pending = [o["id"] for o in proposal["operations"] if o["status"] == "pending"]
    if pending:
        proposal = api.post(f"/api/proposals/{proposal['id']}/apply", {"operation_ids": pending})
    failed = [o for o in proposal["operations"] if o["status"] not in ("applied", "auto_applied")]
    after = _dataset(api, schema.taxonomy_id, identifier) or {}
    print(
        f"{document_id}: dataset {identifier!r} now holds "
        f"{after.get('individual_count')} individuals "
        f"and {after.get('relationship_count')} relationships (proposal {proposal['id']}, "
        f"source {source['id']})"
    )
    for operation in failed:
        print(f"  ! op {operation['seq']} {operation['status']}: {operation.get('reason')}")
    if failed:
        raise ApiError(f"{len(failed)} operations did not apply")


def cmd_load(args: argparse.Namespace) -> int:
    api = Api(args.base_url)
    schema = Schema(api, args.taxonomy)
    for document_id in _documents(args.document):
        problems = validate_gold(document_id)
        if problems:
            raise SystemExit(f"{document_id}: gold file has problems; run validate")
        load_document(api, schema, document_id, args.replace)
    return 0


# ---------------------------------------------------------------- score


def predictions_from_proposal(
    proposal: dict[str, Any], schema: Schema, api: Api
) -> tuple[list[Predicted], list[PredictedRelationship]]:
    """A proposal's individual and relationship creates as predictions (rejected ones left out)."""
    titles: dict[str, str] = {}
    individuals: list[Predicted] = []
    relationships: list[PredictedRelationship] = []
    operations = [
        o for o in proposal["operations"] if o["op"] == "create" and o["status"] != "rejected"
    ]
    for operation in operations:
        if operation["kind"] != "individual":
            continue
        fields = operation["fields"]
        title = str(fields.get("title") or "").strip()
        if not title:
            continue
        for handle in (f"${operation.get('ref')}", operation.get("result_entity_id")):
            if handle:
                titles[handle] = title
        individuals.append(
            Predicted(
                title=title,
                class_refs=tuple(
                    schema.class_ref[c]
                    for c in fields.get("class_ids", ())
                    if c in schema.class_ref
                ),
                evidence=tuple(
                    Passage(e["start"], e["end"], str(e.get("quote") or ""))
                    for e in operation.get("evidence", ())
                    if isinstance(e.get("start"), int) and isinstance(e.get("end"), int)
                ),
            )
        )
    for operation in operations:
        if operation["kind"] != "relationship":
            continue
        fields = operation["fields"]
        triple = schema.property_triple.get(fields.get("property_definition_id"))
        ends = [_end_title(fields.get(name), titles, api) for name in ("source_id", "target_id")]
        if triple and all(ends):
            relationships.append(PredictedRelationship(ends[0], triple[1], ends[1]))
    return individuals, relationships


def _end_title(handle: Any, titles: dict[str, str], api: Api) -> str:
    """The title of a relationship end: a "$ref" of this proposal, or an existing individual."""
    if not handle:
        return ""
    if handle not in titles and not str(handle).startswith("$"):
        try:
            titles[handle] = api.get(f"/api/individuals/{handle}")["title"]
        except ApiError:
            titles[handle] = ""
    return titles.get(handle, "")


def write_report(result: BenchmarkScore, label: str, details: dict[str, Any]) -> Path:
    """Write a score as JSON and a short markdown digest under experiments/reports/."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = REPORTS_DIR / f"benchmark_{result.document_id}_{label}_{stamp}"
    stem.with_suffix(".json").write_text(
        json.dumps({**details, **result.to_json()}, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    stem.with_suffix(".md").write_text(report_markdown(result, details), encoding="utf-8")
    return stem.with_suffix(".md")


def report_markdown(result: BenchmarkScore, details: dict[str, Any]) -> str:
    m, c = result.metrics, result.counts
    lines = [
        f"# Benchmark: {result.document_id}",
        "",
        *(f"- {name}: {value}" for name, value in details.items()),
        "",
        f"Found {c['matched']} of {c['gold']} gold individuals "
        f"({c['typed']} with an acceptable type) "
        f"from {c['predicted']} predictions; {c['spurious']} match nothing, "
        f"{c['excluded_hits']} are known distractors, {c['duplicates']} repeat one already found.",
        "",
        "| measure | value |",
        "|---|---|",
        *(f"| {name} | {value:.3f} |" for name, value in m.items()),
        "",
        "| layer | gold | recall | typed recall |",
        "|---|---|---|---|",
        *(
            f"| {layer} | {int(row['gold'])} | {row['recall']:.2f} | {row['typed_recall']:.2f} |"
            for layer, row in result.by_layer.items()
        ),
        "",
        "## Missed (core first)",
        *(
            f"- {item['title']} [{item['class']}] ({item['tier']})"
            for item in sorted(result.missed, key=lambda i: i["tier"])
        ),
        "",
        "## Found with the wrong type",
        *(
            f"- {item['title']}: gold {item['gold']}, "
            f"predicted {', '.join(item['predicted']) or 'none'}"
            for item in result.mistyped
        ),
        "",
        "## Predictions that match nothing in gold (check: an error, or something gold lacks)",
        *(f"- {item['title']} [{', '.join(item['predicted'])}]" for item in result.spurious),
        "",
        "## Known distractors extracted",
        *(f"- {title}" for title in result.excluded_hits),
        "",
    ]
    return "\n".join(lines)


def print_summary(result: BenchmarkScore) -> None:
    m = result.metrics
    print(
        f"{result.document_id}: recall {m['recall']:.3f} (core {m['recall_core']:.3f}), "
        f"precision {m['precision']:.3f}, type accuracy {m['type_accuracy']:.3f}, "
        f"typed F1 {m['typed_f1']:.3f}, relationship recall {m['relationship_recall']:.3f}"
    )


def cmd_score(args: argparse.Namespace) -> int:
    api = Api(args.base_url)
    schema = Schema(api, args.taxonomy)
    proposal = api.get(f"/api/proposals/{args.proposal}")
    individuals, relationships = predictions_from_proposal(proposal, schema, api)
    result = score(load_gold(args.document), individuals, relationships)
    report = write_report(result, args.label, {"proposal": args.proposal})
    print_summary(result)
    print(f"report: {report}")
    return 0


# ---------------------------------------------------------------- run


def cmd_run(args: argparse.Namespace) -> int:
    if not args.spend:
        raise SystemExit(
            "run extracts the document with the configured LLM, which costs money; "
            "pass --spend to go ahead"
        )
    api = Api(args.base_url)
    schema = Schema(api, args.taxonomy)
    gold = _gold_json(args.document)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    identifier = f"bench-run-{args.document.replace('_', '-')}-{stamp}"[:64]
    api.post(
        "/api/datasets",
        {
            "taxonomy_id": schema.taxonomy_id,
            "identifier": identifier,
            "title": f"Benchmark run: {gold['document']['title']} ({stamp})",
        },
    )
    source = _add_source(api, schema, identifier, args.document, gold["document"]["title"])
    body: dict[str, Any] = {"dataset": identifier, "skip_boilerplate": not args.keep_boilerplate}
    if args.configuration:
        body["configuration_ref"] = args.configuration
    started = api.post(f"/api/sources/{source['id']}/extract", body)
    run_id = started["runs"][0]["run_id"]
    print(f"{args.document}: run {run_id} started in dataset {identifier!r}")
    while True:
        last = api.get(f"/api/sources/{source['id']}").get("last_extraction") or {}
        run = next((r for r in last.get("runs", []) if r["run_id"] == run_id), None)
        if run and run["status"] in FINISHED:
            break
        if run and run.get("items_total"):
            print(f"  {run.get('items_done') or 0}/{run['items_total']} chunks", flush=True)
        time.sleep(POLL_SECONDS)
    if run["status"] != "completed" or not run.get("proposal_id"):
        raise ApiError(f"Run {run_id} ended {run['status']} with proposal {run.get('proposal_id')}")
    proposal = api.get(f"/api/proposals/{run['proposal_id']}")
    individuals, relationships = predictions_from_proposal(proposal, schema, api)
    result = score(load_gold(args.document), individuals, relationships)
    details = {
        "run": run_id,
        "proposal": run["proposal_id"],
        "dataset": identifier,
        "configuration": args.configuration or "extraction-default",
    }
    report = write_report(result, args.label, details)
    print_summary(result)
    print(f"report: {report}")
    print(f"The proposal is left pending in the review queue (dataset {identifier!r}).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)

    def common(sub: argparse.ArgumentParser, server: bool = True) -> None:
        if server:
            sub.add_argument("--base-url", default=DEFAULT_BASE_URL)
            sub.add_argument("--taxonomy", default="dr_spec", help="Identifier of the DR taxonomy")

    validate = commands.add_parser("validate", help="Check the gold files")
    validate.add_argument(
        "--document", action="append", help="A document id (repeatable); all by default"
    )
    validate.set_defaults(func=cmd_validate)

    load = commands.add_parser("load", help="Load gold extractions into the workspace as datasets")
    common(load)
    load.add_argument(
        "--document", action="append", help="A document id (repeatable); all by default"
    )
    load.add_argument(
        "--replace", action="store_true", help="Load again into a dataset emptied by a revert"
    )
    load.set_defaults(func=cmd_load)

    score_cmd = commands.add_parser("score", help="Score a proposal against a gold extraction")
    common(score_cmd)
    score_cmd.add_argument("--document", required=True)
    score_cmd.add_argument(
        "--proposal", required=True, help="The proposal an extraction run produced"
    )
    score_cmd.add_argument("--label", default="proposal", help="A short name for the report file")
    score_cmd.set_defaults(func=cmd_score)

    run = commands.add_parser(
        "run", help="Extract a benchmark document and score it (calls the LLM)"
    )
    common(run)
    run.add_argument("--document", required=True)
    run.add_argument(
        "--configuration",
        help="An individual-extraction configuration; extraction-default if omitted",
    )
    run.add_argument(
        "--keep-boilerplate", action="store_true", help="Do not skip boilerplate sections"
    )
    run.add_argument("--label", default="run", help="A short name for the report file")
    run.add_argument("--spend", action="store_true", help="Confirm the run may call the LLM")
    run.set_defaults(func=cmd_run)

    args = parser.parse_args()
    try:
        return args.func(args)
    except ApiError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
