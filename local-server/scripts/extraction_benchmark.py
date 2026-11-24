"""
The individual-extraction benchmark: hand-made extractions of prose documents
against the Documentation Robotics schema, and how a pipeline run compares.

The gold extractions live in tests/integration/fixtures/pipelines/extraction_benchmark/
(see its README). This script works against a running Context Studio server:

    validate   Check every gold file against its source and the schema snapshot (no server).
    load       Put a gold extraction into the workspace as a dataset of the DR taxonomy:
               the source document, then one proposal of individual and relationship
               creates, each with its passages, applied.
    check      Load a gold extraction for a person to check: one unapplied proposal of
               its individuals and relationships, in a new dataset gold-check-<document>,
               to review on its proposal page (gold mode).
    write-gold Write the decisions taken on a gold check's proposal back to gold.json.
    score      Score a proposal an extraction run produced against the gold extraction.
    run        Extract a benchmark document with a pipeline configuration, in a fresh
               dataset, and score the proposal. This calls the configured LLM (it costs
               money) and needs --spend.

Usage (from local-server/, venv active; the server on http://127.0.0.1:8000):
    python scripts/extraction_benchmark.py validate
    python scripts/extraction_benchmark.py load [--document ID] [--replace]
    python scripts/extraction_benchmark.py check --document ID
    python scripts/extraction_benchmark.py write-gold --document ID --proposal PROPOSAL_ID
    python scripts/extraction_benchmark.py score --document ID --proposal PROPOSAL_ID
    python scripts/extraction_benchmark.py run --document ID [--configuration REF] --spend
"""

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.integration.pipelines._harness.benchmark import (
    BENCHMARK_DIR,
    HOLDOUT_DOCUMENTS,
    BenchmarkScore,
    Passage,
    Predicted,
    PredictedRelationship,
    SchemaSnapshot,
    benchmark_documents,
    load_gold,
    name_key,
    score,
    validate_gold,
)

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
# The external reference that names a class's DR type (a bundle import adds one of its own)
DR_REFERENCE_SOURCE = "documentation_robotics"
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
        """The class's DR reference: its documentation_robotics one, else its first."""
        references = cls.get("external_references") or []
        dr = [r for r in references if r.get("source") == DR_REFERENCE_SOURCE]
        return (dr or references)[0]["identifier"] if references else cls["identifier"]


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


# ---------------------------------------------------------------- check / write-gold

# The implementation a gold check's proposal names in its origin, and the client_metadata
# key that holds what write-gold needs to map its decisions back to the gold file
GOLD_CHECK_IMPLEMENTATION = "gold_check"
GOLD_CHECK_KEY = "gold_check"
# How a gold file is formatted: one-space indent, non-ASCII kept, no final newline
GOLD_INDENT = 1
# The tier of an element a reviewer added without giving one
ADDED_TIER = "supporting"
# What a rejection's reason code says in `excluded`, when the reviewer left no note
REASON_LABELS = {
    "not_in_text": "Not in the text.",
    "too_generic": "Too generic to be an element.",
    "mentioned_only": "Only mentioned in passing.",
    "out_of_scope": "Out of the document's scope.",
    "duplicate": "A duplicate of another element.",
    "other": "Rejected in review.",
}


def gold_text(gold: dict[str, Any]) -> str:
    """A gold file's text, formatted as the files are."""
    return json.dumps(gold, indent=GOLD_INDENT, ensure_ascii=False)


def gold_digest(document_id: str) -> str:
    """A short hash of a document's gold file: the version a gold check reviews."""
    return hashlib.sha256((BENCHMARK_DIR / document_id / "gold.json").read_bytes()).hexdigest()[:12]


def split_of(document_id: str) -> str:
    """Whether a document is in the dev set or the holdout."""
    return "holdout" if document_id in HOLDOUT_DOCUMENTS else "dev"


def check_operations(
    gold: dict[str, Any],
    class_id: dict[str, str],
    property_id: dict[tuple[str, str, str], str],
    source_id: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    A gold extraction as the operations of a proposal to review, and what
    write-gold needs to map the decisions on them back: each individual create
    is named (ref) by its gold key, and each relationship create's seq names
    its gold relationship.

    Returns:
        The operations, and {elements: {ref: {key, tier, acceptable_classes,
        aliases}}, relationships: {seq: {source, predicate, target, tier}}}
    """
    operations: list[dict[str, Any]] = []
    elements: dict[str, Any] = {}
    relationships: dict[str, Any] = {}
    class_of: dict[str, str] = {}
    for item in gold["individuals"]:
        class_of[item["key"]] = item["class"]
        elements[item["key"]] = {
            "key": item["key"],
            "tier": item["tier"],
            "acceptable_classes": list(item.get("acceptable_classes", ())),
            "aliases": list(item.get("aliases", ())),
        }
        operations.append(
            {
                "seq": len(operations) + 1,
                "op": "create",
                "kind": "individual",
                "ref": item["key"],
                "fields": {"title": item["title"], "class_ids": [class_id[item["class"]]]},
                "notes": f"benchmark tier: {item['tier']}",
                "evidence": _evidence(item["evidence"], source_id),
            }
        )
    for rel in gold["relationships"]:
        triple = (class_of[rel["source"]], rel["predicate"], class_of[rel["target"]])
        seq = len(operations) + 1
        relationships[str(seq)] = {
            "source": rel["source"],
            "predicate": rel["predicate"],
            "target": rel["target"],
            "tier": rel.get("tier", "core"),
        }
        operations.append(
            {
                "seq": seq,
                "op": "create",
                "kind": "relationship",
                "fields": {
                    "source_id": f"${rel['source']}",
                    "target_id": f"${rel['target']}",
                    "property_definition_id": property_id[triple],
                },
                "evidence": _evidence(rel["evidence"], source_id),
            }
        )
    return operations, {"elements": elements, "relationships": relationships}


# Who decides on behalf of nobody: a policy, a bundle import, or decisions backfilled
# from before they were recorded. Only a person's decision is a verdict on gold.
NOT_A_REVIEWER = frozenset({"policy", "bundle", "unknown"})


@dataclass
class GoldRewrite:
    """
    A gold file with a gold check's review written back.

    Attributes:
        gold: The rewritten gold file
        notes: What the rewrite did that the reviewer should know (data dropped
            by a class edit, a second class not written, an addition already
            in the file)
        origins: Gold individual key or relationship label ("source predicate
            target") -> the operation whose decision changed it ("seq N 'title'"),
            to name what to reject when the result does not validate
    """

    gold: dict[str, Any]
    notes: list[str] = field(default_factory=list)
    origins: dict[str, str] = field(default_factory=dict)


def _by_reviewer(decision: dict[str, Any] | None) -> bool:
    return decision is not None and decision.get("decided_by") not in NOT_A_REVIEWER


def _checked(decision: dict[str, Any], proposal_id: str) -> dict[str, str]:
    """Who checked an element and when, and in which gold check's proposal."""
    return {"by": decision["decided_by"], "at": decision["decided_at"], "proposal": proposal_id}


def _slug(title: str, taken: set[str]) -> str:
    """A key for a new gold individual: its title as a slug, unique among the file's keys."""
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "element"
    key, n = base, 2
    while key in taken:
        key, n = f"{base}-{n}", n + 1
    return key


def _excluded_reason(operation: dict[str, Any], decision: dict[str, Any]) -> str:
    note = decision.get("reason") or operation.get("reason")
    if note:
        return str(note)
    code = decision.get("reason_code") or operation.get("reason_code")
    return REASON_LABELS.get(str(code), REASON_LABELS["other"])


def _extend(item: dict[str, Any], name: str, values: list[str], leave_out: set[str]) -> None:
    """Append values to a list field of a gold individual, once each; only if any are new."""
    current = list(item.get(name, ()))
    new = [v for v in dict.fromkeys(values) if v not in current and v not in leave_out]
    if new:
        item[name] = current + new


def _origin(operation: dict[str, Any]) -> str:
    title = (operation.get("applied_fields") or operation.get("fields") or {}).get("title")
    return f"seq {operation['seq']}" + (f" {title!r}" if title else "")


def _classes(
    fields: dict[str, Any], class_ref: dict[str, str], operation: dict[str, Any], notes: list[str]
) -> list[str]:
    """The class refs of an edit or addition; a second class is noted, never written."""
    classes = [class_ref[c] for c in fields.get("class_ids") or () if c in class_ref]
    if len(classes) > 1:
        notes.append(
            f"{_origin(operation)}: has {len(classes)} classes; only the first, {classes[0]}, "
            "is written (gold gives each element one class)"
        )
    return classes


def _apply_verdict(
    item: dict[str, Any],
    operation: dict[str, Any],
    decision: dict[str, Any],
    class_ref: dict[str, str],
    class_attributes: Mapping[str, Collection[str]] | None,
    proposal_id: str,
    notes: list[str],
) -> None:
    """What an applied decision writes to its gold individual."""
    annotations = decision.get("annotations") or {}
    defensible = [class_ref[c] for c in annotations.get("also_defensible") or () if c in class_ref]
    if decision["decision"] == "applied_with_edits":
        applied = decision.get("applied_fields") or {}
        classes = _classes(applied, class_ref, operation, notes)
        if classes and classes[0] != item["class"]:
            item["class"] = classes[0]
            if classes[0] in item.get("acceptable_classes", ()):
                item["acceptable_classes"] = [
                    c for c in item["acceptable_classes"] if c != classes[0]
                ]
            _drop_undefined_data(item, class_attributes, operation, notes)
        title = applied.get("title")
        if isinstance(title, str) and title and title != item["title"]:
            old = item["title"]
            item["title"] = title
            if title in item.get("aliases", ()):
                item["aliases"] = [a for a in item["aliases"] if a != title]
            _extend(item, "aliases", [old], set())
    # The old class (an edit's) goes to acceptable_classes only when marked defensible.
    _extend(item, "acceptable_classes", defensible, {item["class"]})
    if annotations.get("tier"):
        item["tier"] = annotations["tier"]
    item["checked"] = _checked(decision, proposal_id)


def _drop_undefined_data(
    item: dict[str, Any],
    class_attributes: Mapping[str, Collection[str]] | None,
    operation: dict[str, Any],
    notes: list[str],
) -> None:
    """Drop the attribute values a new class does not define, noting each."""
    if class_attributes is None or not item.get("data"):
        return
    defined = class_attributes.get(item["class"], ())
    dropped = [name for name in item["data"] if name not in defined]
    for name in dropped:
        notes.append(
            f"{_origin(operation)}: dropped data {name}={item['data'][name]!r}; "
            f"{item['class']} has no attribute {name}"
        )
    if dropped:
        item["data"] = {k: v for k, v in item["data"].items() if k not in dropped}
        if not item["data"]:
            del item["data"]


def _added_individual(
    operation: dict[str, Any],
    decision: dict[str, Any],
    class_ref: dict[str, str],
    taken: set[str],
    proposal_id: str,
    notes: list[str],
) -> dict[str, Any]:
    """A gold individual for an element a reviewer added from the text."""
    fields = operation.get("applied_fields") or operation["fields"]
    title = fields["title"]
    classes = _classes(fields, class_ref, operation, notes)
    if not classes:
        raise ValueError(f"{_origin(operation)}: its class is not in the schema")
    annotations = decision.get("annotations") or {}
    item: dict[str, Any] = {
        "key": _slug(title, taken),
        "title": title,
        "class": classes[0],
        "tier": annotations.get("tier") or ADDED_TIER,
        "description": "",
    }
    defensible = [class_ref[c] for c in annotations.get("also_defensible") or () if c in class_ref]
    _extend(item, "acceptable_classes", defensible, {item["class"]})
    item["evidence"] = [
        {"quote": e["quote"], "start": e["start"], "end": e["end"]}
        for e in operation.get("evidence", ())
        if isinstance(e.get("start"), int) and isinstance(e.get("end"), int)
    ]
    item["checked"] = _checked(decision, proposal_id)
    return item


def _already_there(added: dict[str, Any], individuals: list[dict[str, Any]]) -> bool:
    """An added element a previous write-gold wrote: same name, same first passage."""
    first = (added["evidence"] or [{}])[0]
    for item in individuals:
        evidence = (item.get("evidence") or [{}])[0]
        if name_key(item["title"]) == name_key(added["title"]) and (
            evidence.get("start"),
            evidence.get("end"),
        ) == (first.get("start"), first.get("end")):
            return True
    return False


def rewrite_gold(
    gold: dict[str, Any],
    proposal: dict[str, Any],
    decisions: list[dict[str, Any]],
    class_ref: dict[str, str],
    class_attributes: Mapping[str, Collection[str]] | None = None,
    property_predicate: Mapping[str, str] | None = None,
) -> GoldRewrite:
    """
    A gold file with a gold check's review written back; the input is left as it is.

    Only a person's standing decision is a verdict: an operation closed without
    one (a revert rejects what was undecided) or by a policy changes nothing.

    Individuals: applied as proposed is marked checked (by, at, proposal);
    applied with a class edit takes the new class, the old one going to
    acceptable_classes only if the decision marks it also defensible, and the
    `data` values the new class does not define are dropped (noted); a title
    edit replaces the title, the old one becoming an alias; a tier annotation
    sets the tier, also defensible classes join acceptable_classes. Rejected
    ones move to `excluded` with the note (else the reason code's label), with
    every relationship touching them. Ones the reviewer added become new
    individuals (tier from the annotation, else "supporting"). Relationships:
    applied are marked checked (and take a tier annotation), rejected removed;
    applied with an edited type or ends replace the gold relationship with the
    edited one (its evidence kept), marked checked, when each edited end is an
    individual of the gold check and the type's predicate is known (else it is
    left as it is, noted).
    Pending and failed operations change nothing, so a proposal nobody reviewed
    gives the gold back unchanged; and writing the same review again changes
    nothing more.

    Args:
        gold: The gold file, as parsed
        proposal: The gold check's proposal, as GET /api/proposals/{id} returns it
        decisions: Its standing decisions, as GET /api/taxonomies/{id}/gold lists them
        class_ref: Class id -> the class's reference in gold ("product.feature")
        class_attributes: Class reference -> the attributes it defines; without
            it a class edit keeps every `data` value
        property_predicate: Relationship type id -> its predicate in gold
            ("realizes"); without it an edited relationship is left as it is
    """
    result = copy.deepcopy(gold)
    rewrite = GoldRewrite(result)
    notes, origins = rewrite.notes, rewrite.origins
    proposal_id = proposal["id"]
    meta = (proposal.get("client_metadata") or {}).get(GOLD_CHECK_KEY) or {}
    elements, gold_relationships = meta.get("elements", {}), meta.get("relationships", {})
    by_operation = {d["operation_id"]: d for d in decisions if not d.get("superseded_at")}
    items = {item["key"]: item for item in result["individuals"]}
    taken = set(items)
    removed: set[str] = set()
    removed_relationships: set[tuple[str, str, str]] = set()
    checked_relationships: dict[tuple[str, str, str], tuple[dict[str, Any], str]] = {}
    excluded_labels = {str(e.get("label")) for e in result.get("excluded", ())}
    added: list[dict[str, Any]] = []
    # Entity id -> its gold key, for the ends of edited relationships.
    key_of: dict[str, str] = {}
    edited: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    for operation in sorted(proposal["operations"], key=lambda o: o["seq"]):
        decision = by_operation.get(operation["id"])
        if operation["op"] != "create" or not _by_reviewer(decision):
            continue
        status = operation["status"]
        if operation["kind"] == "individual":
            if operation.get("added_by_reviewer"):
                if status == "applied":
                    item = _added_individual(
                        operation, decision, class_ref, taken, proposal_id, notes
                    )
                    if _already_there(item, result["individuals"] + added):
                        continue
                    taken.add(item["key"])
                    origins[item["key"]] = _origin(operation)
                    added.append(item)
                    if operation.get("result_entity_id"):
                        key_of[operation["result_entity_id"]] = item["key"]
                continue
            element = elements.get(operation.get("ref"))
            item = items.get(element["key"]) if element else None
            if item is None:
                continue
            origins[item["key"]] = _origin(operation)
            if status == "applied" and operation.get("result_entity_id"):
                key_of[operation["result_entity_id"]] = item["key"]
            if status == "rejected":
                removed.add(item["key"])
                if item["title"] not in excluded_labels:
                    excluded_labels.add(item["title"])
                    result.setdefault("excluded", []).append(
                        {"label": item["title"], "reason": _excluded_reason(operation, decision)}
                    )
            elif status == "applied":
                _apply_verdict(
                    item, operation, decision, class_ref, class_attributes, proposal_id, notes
                )
        elif operation["kind"] == "relationship":
            rel = gold_relationships.get(str(operation["seq"]))
            if rel is None:
                continue
            triple = (rel["source"], rel["predicate"], rel["target"])
            origins[" ".join(triple)] = f"seq {operation['seq']} ({' '.join(triple)})"
            if status == "rejected":
                removed_relationships.add(triple)
            elif status == "applied" and operation.get("applied_fields"):
                edited.append((rel, operation, decision))
            elif status == "applied":
                checked_relationships[triple] = (decision, proposal_id)
    def end_key(value: Any) -> str | None:
        """An end's gold key: the "$ref" of a gold element, or the entity an element made."""
        if isinstance(value, str) and value.startswith("$"):
            element = elements.get(value[1:])
            return element["key"] if element else None
        return key_of.get(value) if isinstance(value, str) else None

    replacements: dict[tuple[str, str, str], tuple[str, str, str]] = {}
    for rel, operation, decision in edited:
        triple = (rel["source"], rel["predicate"], rel["target"])
        fields = operation["applied_fields"]
        source = end_key(fields.get("source_id"))
        target = end_key(fields.get("target_id"))
        predicate = (property_predicate or {}).get(fields.get("property_definition_id", ""))
        if source is None or target is None or predicate is None:
            notes.append(
                f"seq {operation['seq']} ({' '.join(triple)}) was accepted with another type"
                " or end that isn't an individual of this gold check; left as it is"
            )
            continue
        new_triple = (source, predicate, target)
        removed_relationships.add(triple)
        replacements[triple] = new_triple
        checked_relationships[new_triple] = (decision, proposal_id)
        origins[" ".join(new_triple)] = f"seq {operation['seq']} ({' '.join(new_triple)})"
    result["individuals"] = [i for i in result["individuals"] if i["key"] not in removed] + added
    relationships = []
    present = {(r["source"], r["predicate"], r["target"]) for r in result["relationships"]}
    for rel in list(result["relationships"]):
        new_triple = replacements.get((rel["source"], rel["predicate"], rel["target"]))
        if new_triple is not None and new_triple not in present:
            present.add(new_triple)
            source, predicate, target = new_triple
            result["relationships"].append(
                {**rel, "source": source, "predicate": predicate, "target": target}
            )
    for rel in result["relationships"]:
        triple = (rel["source"], rel["predicate"], rel["target"])
        if rel["source"] in removed or rel["target"] in removed or triple in removed_relationships:
            continue
        if triple in checked_relationships:
            decision, _ = checked_relationships[triple]
            tier = (decision.get("annotations") or {}).get("tier")
            if tier:
                rel["tier"] = tier
            rel["checked"] = _checked(decision, proposal_id)
        relationships.append(rel)
    result["relationships"] = relationships
    return rewrite


def _created(proposal: dict[str, Any], check: dict[str, Any]) -> str | None:
    """
    Why a gold check's new proposal is not ready to review, if it isn't: all
    must be pending. A safety net: the proposal is review_only (#1628), so no
    approval policy should have applied any of it.
    """
    decided = [o for o in proposal["operations"] if o["status"] != "pending"]
    if not decided:
        return None
    listed = ", ".join(f"seq {o['seq']} {o['status']}" for o in decided[:5])
    return (
        f"{len(decided)} of the gold check's {len(proposal['operations'])} operations are not "
        f"pending ({listed}{', ...' if len(decided) > 5 else ''}): the taxonomy's approval policy "
        f"applied them as soon as they were proposed, so they are not a person's verdicts. "
        f"Revert proposal {proposal['id']} (Review queue, or POST "
        f"/api/proposals/{proposal['id']}/revert), delete dataset {check['dataset']!r}, change the "
        "approval policy so it does not apply individual or relationship creates, and run check "
        "again"
    )


def check_document(api: Any, schema: Any, document_id: str) -> dict[str, Any]:
    """
    Load a gold file as an unapplied proposal to review.

    Returns:
        The proposal, as the API returned it

    Raises:
        SystemExit: If the check's dataset already exists, or the proposal came
            back with operations already applied (an approval policy); what was
            created is left for the user to revert
    """
    gold = _gold_json(document_id)
    missing = sorted({i["class"] for i in gold["individuals"]} - set(schema.class_id))
    if missing:
        raise ApiError(f"The workspace schema lacks classes gold uses: {missing}")
    identifier = f"gold-check-{document_id}"
    if _dataset(api, schema.taxonomy_id, identifier) is not None:
        raise SystemExit(
            f"Dataset {identifier!r} already exists: a gold check of {document_id} is loaded. "
            "Finish it (write-gold), or delete the dataset to start again"
        )
    dataset = api.post(
        "/api/datasets",
        {
            "taxonomy_id": schema.taxonomy_id,
            "identifier": identifier,
            "title": f"Gold check: {gold['document']['title']}",
        },
    )
    source = _add_source(api, schema, identifier, document_id, gold["document"]["title"])
    operations, mapping = check_operations(gold, schema.class_id, schema.property_id, source["id"])
    body = {
        "taxonomy_id": schema.taxonomy_id,
        "title": f"Gold check: {gold['document']['title']}",
        "rationale": (
            f"The gold extraction of {document_id} "
            f"(tests/integration/fixtures/pipelines/extraction_benchmark/{document_id}/gold.json), "
            "loaded for a person to check. Nothing is applied until it is reviewed; "
            "scripts/extraction_benchmark.py write-gold writes the verdicts back."
        ),
        "source": "pipeline",
        "source_detail": f"extraction-benchmark:{document_id}",
        "dataset_id": dataset["id"],
        # A person checks every element: no approval policy applies any of it (#1628)
        "review_only": True,
        "operations": operations,
        "client_metadata": {
            "source_id": source["id"],
            "origin": {
                "pipeline_type": "individual_extraction",
                "implementation_id": GOLD_CHECK_IMPLEMENTATION,
                "configuration_ref": "gold",
                "configuration_version": 1,
                "digest": gold_digest(document_id),
            },
            GOLD_CHECK_KEY: {"document": document_id, "split": split_of(document_id), **mapping},
        },
    }
    api.post("/api/proposals", body, dry_run="true")
    proposal = api.post("/api/proposals", body)
    problem = _created(proposal, {"dataset": identifier})
    if problem is not None:
        raise SystemExit(f"{document_id}: {problem}")
    return proposal


def cmd_check(args: argparse.Namespace) -> int:
    document_id = _documents([args.document])[0]
    if validate_gold(document_id):
        raise SystemExit(f"{document_id}: gold file has problems; run validate")
    api = Api(args.base_url)
    proposal = check_document(api, Schema(api, args.taxonomy), document_id)
    print(
        f"{document_id}: gold check proposal {proposal['id']} with "
        f"{len(proposal['operations'])} operations in dataset 'gold-check-{document_id}'"
    )
    print(f"Review it at /app/proposals/{proposal['id']}")
    return 0


def _decisions(api: Api, taxonomy_id: str, proposal_id: str) -> list[dict[str, Any]]:
    """A proposal's standing decisions, every page."""
    found: list[dict[str, Any]] = []
    while True:
        page = api.get(
            f"/api/taxonomies/{taxonomy_id}/gold",
            proposal_id=proposal_id,
            limit=500,
            offset=len(found),
        )
        found += page["items"]
        if not page["items"] or len(found) >= page["total"]:
            return found


def gold_check_problem(proposal: dict[str, Any], document_id: str, taxonomy_id: str) -> str | None:
    """Why write-gold can't write this proposal into this document's gold file, if it can't."""
    origin = (proposal.get("client_metadata") or {}).get("origin") or {}
    meta = (proposal.get("client_metadata") or {}).get(GOLD_CHECK_KEY) or {}
    if origin.get("implementation_id") != GOLD_CHECK_IMPLEMENTATION or not meta:
        return f"Proposal {proposal['id']} is not a gold check (see the check command)"
    if meta.get("document") != document_id:
        return (
            f"Proposal {proposal['id']} is a gold check of {meta.get('document')},"
            f" not {document_id}"
        )
    if proposal["taxonomy_id"] != taxonomy_id:
        return f"Proposal {proposal['id']} is in another taxonomy than --taxonomy"
    if proposal["status"] == "reverted":
        return (
            f"Proposal {proposal['id']} was reverted: none of its decisions stand. "
            "Run check again to review the gold file"
        )
    return None


def written_by(gold: dict[str, Any], proposal_id: str) -> bool:
    """Whether a previous write-gold of this proposal wrote this gold file."""
    entries = [*gold["individuals"], *gold["relationships"]]
    return any((e.get("checked") or {}).get("proposal") == proposal_id for e in entries)


def _with_origins(problems: list[str], origins: dict[str, str]) -> list[str]:
    """
    Each validation problem, with the operations behind it: the element or
    relationship it is about, and for a relationship the elements at its ends.
    """
    named = []
    for problem in problems:
        owner = problem.split(":", 1)[0]
        parts = owner.split(" ")
        candidates = [owner, *([parts[0], parts[2]] if len(parts) == 3 else [])]
        behind = list(dict.fromkeys(origins[c] for c in candidates if c in origins))
        named.append(f"{problem} (from {'; '.join(behind)})" if behind else problem)
    return named


def cmd_write_gold(args: argparse.Namespace) -> int:
    document_id = _documents([args.document])[0]
    api = Api(args.base_url)
    proposal = api.get(f"/api/proposals/{args.proposal}")
    schema = Schema(api, args.taxonomy)
    problem = gold_check_problem(proposal, document_id, schema.taxonomy_id)
    if problem is not None:
        raise SystemExit(problem)
    decisions = _decisions(api, proposal["taxonomy_id"], proposal["id"])
    path = BENCHMARK_DIR / document_id / "gold.json"
    original = path.read_text(encoding="utf-8")
    gold = json.loads(original)
    digest = proposal["client_metadata"]["origin"].get("digest")
    if digest != gold_digest(document_id) and not written_by(gold, proposal["id"]):
        print(
            f"warning: {path} changed since proposal {proposal['id']} loaded it (digest "
            f"{gold_digest(document_id)}, not {digest}); its decisions are written onto the "
            "file as it is now"
        )
    rewrite = rewrite_gold(
        gold,
        proposal,
        decisions,
        schema.class_ref,
        SchemaSnapshot.load().attributes,
        {property_id: triple[1] for property_id, triple in schema.property_triple.items()},
    )
    for note in rewrite.notes:
        print(f"  note: {note}")
    if rewrite.gold == gold:
        print(f"{document_id}: nothing new to write")
        return 0
    path.write_text(gold_text(rewrite.gold), encoding="utf-8")
    problems = validate_gold(document_id)
    if problems:
        path.write_text(original, encoding="utf-8")
        listed = "\n".join(f"  ! {p}" for p in _with_origins(problems, rewrite.origins))
        raise SystemExit(
            f"{document_id}: the rewritten gold file is invalid, so it was left as it was. "
            f"Reject or change the decisions named:\n{listed}"
        )
    pending = sum(1 for o in proposal["operations"] if o["status"] in ("pending", "failed"))
    print(
        f"{document_id}: wrote {len(decisions)} decisions to {path} "
        f"({pending} operations still unchecked)"
    )
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
    # What is left out is the registered default (domain/pipelines/selection.py)
    if args.implementation:
        body["implementation_id"] = args.implementation
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
    # What the run executed with, as the run records it
    stored = api.get(f"/api/pipelines/runs/{run_id}")
    details = {
        "run": run_id,
        "proposal": run["proposal_id"],
        "dataset": identifier,
        "implementation": stored["implementation_id"],
        "configuration": stored["configuration_ref"],
        "model": (stored.get("llm_metadata") or {}).get("model"),
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

    check = commands.add_parser(
        "check", help="Load a gold extraction as an unapplied proposal for a person to check"
    )
    common(check)
    check.add_argument("--document", required=True)
    check.set_defaults(func=cmd_check)

    write_gold = commands.add_parser(
        "write-gold", help="Write a gold check's decisions back to the gold file"
    )
    common(write_gold)
    write_gold.add_argument("--document", required=True)
    write_gold.add_argument("--proposal", required=True, help="The gold check's proposal")
    write_gold.set_defaults(func=cmd_write_gold)

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
        "--implementation",
        help=(
            "An individual-extraction implementation that can extract a source; the"
            " pipeline's default implementation if omitted"
        ),
    )
    run.add_argument(
        "--configuration",
        help=("One of that implementation's configurations; its default configuration if omitted"),
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
