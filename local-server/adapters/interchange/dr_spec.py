"""
Reading a Documentation Robotics (DR) spec checkout: the manifest, design
charter, layer descriptions, predicate catalog, node schemas (with their
attributes and DR fields) and relationship schemas, and the spec's revision.

Shared by the DR importer (`scripts/dr_ontology_loader.py`) and the drift
planner (`dr_drift.py`), so both read the spec the same way.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from adapters.interchange.dr_relationships import DR_ATTRIBUTE_SCHEMA, RelationshipSchemaRecord
from domain.ontology.value_objects import DataType, SourceRevision, normalize_evidence_signals

CHARTER_FILE = "DESIGN_CHARTER.md"
_SUMMARY_HEADING = "## In one paragraph"


@dataclass(frozen=True)
class AttributeSchemaRecord:
    """
    One attribute of a node schema (`properties.attributes.properties.<name>`).

    `schema` is the attribute's JSON Schema without the keywords the
    attribute definition holds itself (type, description, and enum or const
    when its values are strings), kept on its DR reference as metadata
    `{"schema": ...}` so a round trip loses nothing: `{"minimum": 0}`,
    `{"items": {...}}`, `{}`. An untyped attribute is a string whose schema
    has `"type": null`, so it goes back without a type. The attribute
    definition's own fields are the truth; the schema only adds to them.
    """

    name: str
    datatype: str
    description: str | None
    is_required: bool
    allowed_values: tuple[str, ...] | None
    schema: dict[str, Any] = field(default_factory=dict, hash=False)

    @property
    def metadata(self) -> dict[str, Any]:
        """Its DR reference's metadata."""
        return {DR_ATTRIBUTE_SCHEMA: self.schema}


@dataclass(frozen=True)
class NodeSchemaRecord:
    """
    One `schemas/nodes/**/*.node.schema.json` file.

    Its DR fields are the class's operational definition (#1513): `standard`
    (x-dr-standard), `evidence` (x-dr-evidence) and `distinguish`
    (x-dr-distinguish: other node id -> when to use that type instead, in the
    schema's order).
    """

    spec_node_id: str
    layer_id: str
    title: str
    description: str | None
    attributes: tuple[AttributeSchemaRecord, ...] = ()
    standard: str | None = None
    evidence: tuple[str, ...] = ()
    distinguish: tuple[tuple[str, str], ...] = ()


def _load_json(path: Path) -> Any:
    """Read and parse a JSON file, raising ValueError with the file path on malformed JSON."""
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed JSON in {path}: {exc}") from exc


def read_manifest(spec_dir: Path) -> tuple[str, list[dict[str, Any]]]:
    """Read spec_version and per-layer metadata from spec/dist/manifest.json."""
    manifest_path = spec_dir / "dist" / "manifest.json"
    manifest = _load_json(manifest_path)
    try:
        return manifest["specVersion"], manifest["layers"]
    except KeyError as exc:
        raise ValueError(f"Manifest {manifest_path} is missing required key {exc}") from exc


def read_source_revision(spec_dir: Path, spec_version: str) -> SourceRevision:
    """
    The spec's revision: its repository's origin URL and HEAD commit (each None
    when git can't tell, e.g. a spec outside a git checkout) and its version.
    """
    return SourceRevision(
        repo=_git(spec_dir, "remote", "get-url", "origin"),
        commit=_git(spec_dir, "rev-parse", "HEAD"),
        spec_version=spec_version,
    )


def _git(directory: Path, *args: str) -> str | None:
    """A git command's output in `directory`, or None if it fails."""
    try:
        result = subprocess.run(
            ["git", "-C", str(directory), *args], capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def read_predicate_catalog(spec_dir: Path) -> dict[str, dict[str, Any]] | None:
    """
    The spec's predicate catalog from spec/dist/base.json, by predicate id: each
    predicate's inverse, category and description, plus its archimate_alignment
    and semantics when the spec gives them. None when the spec has no
    dist/base.json (older specs).
    """
    path = spec_dir / "dist" / "base.json"
    if not path.is_file():
        return None
    predicates = _load_json(path).get("predicates")
    if not isinstance(predicates, dict) or not predicates:
        raise ValueError(f"{path} has no predicates object")
    try:
        return {
            predicate_id: {
                "inverse": entry.get("inverse"),
                "category": entry.get("category"),
                "description": entry.get("description"),
                **{key: entry[key] for key in ("archimate_alignment", "semantics") if key in entry},
            }
            for predicate_id, entry in sorted(predicates.items())
        }
    except AttributeError as exc:
        raise ValueError(f"{path}: a predicate entry is not an object") from exc


def read_charter(spec_dir: Path) -> tuple[str | None, str | None]:
    """
    The spec's design charter as (vision, summary).

    The vision is the whole file; the summary is the text under "## In one
    paragraph", unwrapped into one line. Both are None when the spec has no
    charter (older spec versions); the summary is None if the file has no such
    section.
    """
    path = spec_dir / CHARTER_FILE
    if not path.is_file():
        return None, None
    vision = path.read_text()
    lines = vision.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == _SUMMARY_HEADING)
    except StopIteration:
        return vision, None
    body: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        if line.strip():
            body.append(line.strip())
    return vision, " ".join(body) or None


def read_layer_descriptions(spec_dir: Path) -> dict[str, str]:
    """Each layer's description from spec/layers/*.layer.json, by layer id."""
    descriptions: dict[str, str] = {}
    for path in sorted((spec_dir / "layers").glob("*.layer.json")):
        data = _load_json(path)
        if data.get("id") and data.get("description"):
            descriptions[data["id"]] = data["description"]
    return descriptions


def iter_node_schemas(spec_dir: Path) -> Iterator[NodeSchemaRecord]:
    """Yield one record per node schema in schemas/nodes/ (base schemas excluded)."""
    nodes_dir = spec_dir / "schemas" / "nodes"
    if not nodes_dir.is_dir():
        raise FileNotFoundError(
            f"DR node schema directory not found: {nodes_dir} — check --spec-dir points at a "
            "documentation_robotics spec checkout with a schemas/nodes/ directory"
        )
    for path in sorted(nodes_dir.glob("*/*.node.schema.json")):
        data = _load_json(path)
        try:
            props = data["properties"]
            yield NodeSchemaRecord(
                spec_node_id=props["spec_node_id"]["const"],
                layer_id=props["layer_id"]["const"],
                title=data["title"],
                description=data.get("description"),
                attributes=_attribute_records(path, props.get("attributes") or {}),
                **_node_fields(path, data),
            )
        except KeyError as exc:
            raise ValueError(f"Node schema {path} is missing required key {exc}") from exc


def _node_fields(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    """A node schema's DR fields (x-dr-standard, -evidence, -distinguish), checked."""
    standard = data.get("x-dr-standard")
    evidence = data.get("x-dr-evidence", [])
    distinguish = data.get("x-dr-distinguish", {})
    if standard is not None and not isinstance(standard, str):
        raise ValueError(f"Node schema {path}: x-dr-standard is not a string")
    if not isinstance(evidence, list) or not all(isinstance(e, str) for e in evidence):
        raise ValueError(f"Node schema {path}: x-dr-evidence is not a string list")
    if not isinstance(distinguish, dict) or not all(
        isinstance(text, str) for text in distinguish.values()
    ):
        raise ValueError(f"Node schema {path}: x-dr-distinguish is not a map of node id to text")
    blank = [key for key, text in distinguish.items() if not text.strip()]
    if blank:
        raise ValueError(f"Node schema {path}: x-dr-distinguish has no text for {blank[0]}")
    # As the class stores them, so an unchanged spec drifts nothing
    return {
        "standard": (standard or "").strip() or None,
        "evidence": tuple(normalize_evidence_signals(evidence)),
        "distinguish": tuple((key.strip(), text.strip()) for key, text in distinguish.items()),
    }


def _attribute_records(path: Path, attributes: dict[str, Any]) -> tuple[AttributeSchemaRecord, ...]:
    """
    A node schema's attributes, in schema order. The datatype is the JSON
    Schema type, or a const's type; an untyped attribute is a string, and a
    string with format date is a date.
    """
    properties = attributes.get("properties") or {}
    required = set(attributes.get("required") or [])
    records = []
    for name, schema in properties.items():
        if not isinstance(schema, dict):
            raise ValueError(f"Node schema {path}: attribute {name!r} is not an object")
        json_type = schema.get("type")
        const = schema.get("const")
        if json_type is None and isinstance(const, str):
            json_type = "string"
        datatype = json_type or DataType.STRING.value
        is_date = json_type == "string" and schema.get("format") == "date"
        if is_date:
            datatype = DataType.DATE.value
        try:
            DataType(datatype)
        except ValueError as exc:
            raise ValueError(
                f"Node schema {path}: attribute {name!r} has type {json_type!r}, which an "
                "attribute definition can't hold"
            ) from exc
        enum = schema.get("enum")
        strings = isinstance(enum, list) and all(isinstance(v, str) for v in enum)
        allowed = tuple(enum) if strings else (const,) if isinstance(const, str) else None
        held = {
            "type",
            "description",
            "enum" if strings else "",
            "const" if allowed else "",
            "format" if is_date else "",
        }
        rest = {key: value for key, value in schema.items() if key not in held}
        if "type" not in schema and not isinstance(const, str):
            rest["type"] = None
        records.append(
            AttributeSchemaRecord(
                name=name,
                datatype=datatype,
                description=schema.get("description"),
                is_required=name in required,
                allowed_values=allowed,
                schema=rest,
            )
        )
    return tuple(records)


def iter_relationship_schemas(spec_dir: Path) -> Iterator[RelationshipSchemaRecord]:
    """Yield one record per relationship schema in schemas/relationships/ (base excluded)."""
    relationships_dir = spec_dir / "schemas" / "relationships"
    if not relationships_dir.is_dir():
        raise FileNotFoundError(
            f"DR relationship schema directory not found: {relationships_dir} — check "
            "--spec-dir points at a documentation_robotics spec checkout with a "
            "schemas/relationships/ directory"
        )
    for path in sorted(relationships_dir.glob("*/*.relationship.schema.json")):
        data = _load_json(path)
        try:
            props = data["properties"]
            evidence = data.get("x-dr-evidence") or []
            if not isinstance(evidence, list) or not all(isinstance(e, str) for e in evidence):
                raise ValueError(f"Relationship schema {path}: x-dr-evidence is not a string list")
            yield RelationshipSchemaRecord(
                source_spec_node_id=props["source_spec_node_id"]["const"],
                source_layer=props["source_layer"]["const"],
                destination_spec_node_id=props["destination_spec_node_id"]["const"],
                destination_layer=props["destination_layer"]["const"],
                predicate=props["predicate"]["const"],
                title=data["title"],
                description=data.get("description"),
                cardinality=(props.get("cardinality") or {}).get("const"),
                strength=(props.get("strength") or {}).get("const"),
                evidence=tuple(evidence),
            )
        except KeyError as exc:
            raise ValueError(f"Relationship schema {path} is missing required key {exc}") from exc


def slugify_spec_node_id(spec_node_id: str) -> str:
    """'motivation.goal' -> 'motivation_goal' (Class identifier slug)."""
    return spec_node_id.replace(".", "_").replace("-", "_")


def attribute_identifier(name: str) -> str:
    """A DR attribute name as an identifier: 'operationId' -> 'operation_id'."""
    snake = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    snake = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", snake)
    return re.sub(r"[^A-Za-z0-9]+", "_", snake).strip("_").lower()
