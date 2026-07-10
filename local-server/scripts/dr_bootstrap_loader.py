"""
Discovery and filtering logic for the Wave 1 DR bootstrap corpus
(`documentation/karpathy_loop_dr_ontology_design.md` §5).

Reads `documentation_robotics_viewer`'s dogfooded model (its own
`documentation-robotics/model/` directory of YAML element and relationship
files -- a real, independently-produced DR model, treated as an external,
read-only dependency and never vendored into this repo) and builds one
`BootstrapScenario` per qualifying prose source file:

- A source file "qualifies" if any element's `source_reference.locations[].file`
  matches one of `--prose-extensions` (default `.md`) -- discovered from the
  element data itself, not a hardcoded file list (Must-Fix 5).
- An individual belongs to a scenario if its `source_reference.provenance` is
  `extracted` and at least one of its locations names that scenario's file.
  `inferred`-provenance individuals never qualify, for any file.
- A relationship belongs to a scenario only if its own
  `properties.source_provenance` is `extracted` AND both its `source` and
  `target` are individuals that qualify for that *same* file. Relationship
  endpoints are not pooled across files: a scenario's `expected.json` is
  graded against a single pinned document, so a fact spanning two source
  files could never be recovered from that document's text alone.

This module only reads YAML under `{viewer_dir}/documentation-robotics/model/`.
It never reads the prose files themselves -- pinning their real content is
the generator script's job (`generate_dr_bootstrap_corpus.py`), which needs
to handle a prose file being discoverable from the model data but absent from
the checked-out working tree (upstream drift; see that script's docstring).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

MODEL_SUBDIR = Path("documentation-robotics") / "model"
_EXCLUDED_MODEL_FILES = {"manifest.yaml", "relationships.yaml"}


@dataclass(frozen=True)
class BootstrapScenario:
    """One qualifying source file's extracted-provenance slice of the model."""

    source_file: str
    individuals: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)


def _model_dir(viewer_dir: Path) -> Path:
    return viewer_dir / MODEL_SUBDIR


def _require_model_dir(viewer_dir: Path) -> Path:
    model_dir = _model_dir(viewer_dir)
    if not model_dir.is_dir():
        raise FileNotFoundError(
            f"Viewer model directory not found: {model_dir} — check --viewer-dir points at a "
            "documentation_robotics_viewer checkout with a documentation-robotics/model/ "
            "directory"
        )
    return model_dir


def _load_yaml(path: Path) -> Any:
    """Read and parse a YAML file, raising ValueError with the file path on malformed YAML."""
    try:
        return yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise ValueError(f"Malformed YAML in {path}: {exc}") from exc


def iter_elements(viewer_dir: Path) -> list[dict[str, Any]]:
    """
    Load every element from every layer YAML file under the viewer's model
    directory (excluding `manifest.yaml` and `relationships.yaml`).
    """
    model_dir = _require_model_dir(viewer_dir)
    elements: list[dict[str, Any]] = []
    for yaml_path in sorted(model_dir.rglob("*.yaml")):
        if yaml_path.name in _EXCLUDED_MODEL_FILES:
            continue
        data = _load_yaml(yaml_path) or {}
        for element in data.values():
            elements.append(element)
    return elements


def load_relationships(viewer_dir: Path) -> list[dict[str, Any]]:
    """
    Load the flat relationship list from `relationships.yaml`.

    A missing `documentation-robotics/model/` directory means `viewer_dir` is
    misconfigured and raises. A missing `relationships.yaml` file within an
    otherwise-present model directory is treated as a legitimate model with
    no relationships and returns an empty list.
    """
    relationships_path = _require_model_dir(viewer_dir) / "relationships.yaml"
    if not relationships_path.is_file():
        return []
    return _load_yaml(relationships_path) or []


def _location_files(element: dict[str, Any]) -> list[str]:
    locations = element.get("source_reference", {}).get("locations", [])
    return [loc["file"] for loc in locations if loc.get("file")]


def discover_prose_files(
    elements: Sequence[dict[str, Any]], prose_extensions: Sequence[str]
) -> list[str]:
    """
    Return the sorted, deduplicated set of source files referenced by any
    element's `source_reference.locations[].file` whose name ends with one
    of `prose_extensions` (case-insensitive).
    """
    extensions = tuple(ext.lower() for ext in prose_extensions)
    files: set[str] = set()
    for element in elements:
        for file in _location_files(element):
            if file.lower().endswith(extensions):
                files.add(file)
    return sorted(files)


def build_scenarios(
    viewer_dir: Path,
    prose_extensions: Sequence[str] = (".md",),
    include_files: Sequence[str] | None = None,
) -> list[BootstrapScenario]:
    """
    Build one `BootstrapScenario` per qualifying source file.

    Args:
        viewer_dir: Path to the `documentation_robotics_viewer` checkout.
        prose_extensions: Extensions a source file must match to qualify.
        include_files: If given, use this exact file list instead of
            discovering it from the element data -- an explicit override for
            regenerating a subset of scenarios.
    """
    elements = iter_elements(viewer_dir)
    relationships = load_relationships(viewer_dir)

    qualifying_files = (
        list(include_files) if include_files else discover_prose_files(elements, prose_extensions)
    )

    scenarios = []
    for source_file in sorted(qualifying_files):
        file_individuals = [
            element
            for element in elements
            if element.get("source_reference", {}).get("provenance") == "extracted"
            and source_file in _location_files(element)
        ]
        try:
            individual_paths = {element["path"] for element in file_individuals}
        except KeyError as exc:
            raise ValueError(
                f"Element for source file {source_file!r} is missing required key {exc}"
            ) from exc
        file_relationships = [
            relationship
            for relationship in relationships
            if relationship.get("properties", {}).get("source_provenance") == "extracted"
            and relationship.get("source") in individual_paths
            and relationship.get("target") in individual_paths
        ]
        scenarios.append(
            BootstrapScenario(
                source_file=source_file,
                individuals=file_individuals,
                relationships=file_relationships,
            )
        )
    return scenarios


def _individual_triple(element: dict[str, Any]) -> dict[str, Any]:
    element_id = element.get("path", element.get("id", "<unknown>"))
    try:
        return {
            "subject": {"label": element["name"], "kind": "individual"},
            "predicate": {"label": "is_a", "kind": "property"},
            "object": {"label": element["spec_node_id"], "kind": "individual"},
            "confidence": 1.0,
        }
    except KeyError as exc:
        raise ValueError(f"Element {element_id!r} is missing required key {exc}") from exc


def _relationship_triple(
    relationship: dict[str, Any], individuals_by_path: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    try:
        source_path = relationship["source"]
        target_path = relationship["target"]
    except KeyError as exc:
        raise ValueError(
            f"Relationship {relationship} is missing required key {exc}"
        ) from exc
    try:
        source = individuals_by_path[source_path]
    except KeyError as exc:
        raise ValueError(
            f"Relationship source {source_path!r} does not match any qualifying individual"
        ) from exc
    try:
        target = individuals_by_path[target_path]
    except KeyError as exc:
        raise ValueError(
            f"Relationship target {target_path!r} does not match any qualifying individual"
        ) from exc
    try:
        return {
            "subject": {"label": source["name"], "kind": "individual"},
            "predicate": {"label": relationship["predicate"], "kind": "property"},
            "object": {"label": target["name"], "kind": "individual"},
            "confidence": 1.0,
        }
    except KeyError as exc:
        raise ValueError(
            f"Relationship {source_path!r} -> {target_path!r} is missing required key {exc}"
        ) from exc


def scenario_triples(scenario: BootstrapScenario) -> list[dict[str, Any]]:
    """
    Ground-truth triples for `scenario`: one `is_a` triple per qualifying
    individual (subject = element name, object = its DR `spec_node_id`),
    followed by one triple per qualifying relationship (subject/object =
    the endpoint element names, predicate = the relationship's own
    predicate).
    """
    try:
        individuals_by_path = {element["path"]: element for element in scenario.individuals}
    except KeyError as exc:
        raise ValueError(
            f"Element in scenario {scenario.source_file!r} is missing required key {exc}"
        ) from exc
    try:
        triples = [_individual_triple(element) for element in scenario.individuals]
        triples.extend(
            _relationship_triple(relationship, individuals_by_path)
            for relationship in scenario.relationships
        )
    except ValueError as exc:
        raise ValueError(f"In scenario {scenario.source_file!r}: {exc}") from exc
    return triples
