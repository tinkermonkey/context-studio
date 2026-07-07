#!/usr/bin/env python
"""
Generate the Wave 1 DR bootstrap corpus: one individual_extraction quality
fixture scenario per qualifying prose source file discovered in
`documentation_robotics_viewer`'s dogfooded model
(`documentation/karpathy_loop_dr_ontology_design.md` §5).

For each source file discovered by `dr_bootstrap_loader.discover_prose_files`
(data-first: scanned from `source_reference.locations[].file` across every
element, not a hardcoded list), writes a
`tests/integration/fixtures/pipelines/individual_extraction/dr_bootstrap_<slug>/`
directory containing:

- `input.json`: the real, pinned content of the source file, read from the
  viewer checkout at generation time.
- `expected.json`: that file's extracted-provenance individuals/relationships
  (see `dr_bootstrap_loader.build_scenarios` for the exact filter).
- `distractors.json`: always `[]` -- Wave 1 has no near-miss data in the
  viewer model to derive distractors from (design doc §5 / Must-Fix 3).
- `README.md`: explains the scenario's provenance and the empty-distractors
  disposition.

A source file discoverable from the model data can still be absent from the
checked-out working tree -- e.g. renamed or deleted upstream since the model
was captured. `documentation_robotics_viewer` is an external, independently
maintained checkout (never vendored into this repo), so this drift is
expected, not a bug. Real, pinned content cannot be fabricated for a file
that doesn't exist: such a scenario is skipped with a warning rather than
written with fake or stale content. Re-running this script later will pick
the file back up automatically if/when it reappears upstream.

Usage (from local-server/, venv active):
    python scripts/generate_dr_bootstrap_corpus.py [--viewer-dir PATH]
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.dr_bootstrap_loader import BootstrapScenario, build_scenarios, scenario_triples

DR_ONTOLOGY_ID = "dr_spec"
FIXTURE_MODEL = "claude-opus-4-7"
FIXTURE_TEMPERATURE = 0.0

# local-server/scripts/../.. == the context-studio repo root; parents[3] is
# that repo root's parent, where the viewer is checked out as a sibling repo
# (not vendored into this one) -- same convention as import_dr_ontology.py's
# DEFAULT_SPEC_DIR.
DEFAULT_VIEWER_DIR = Path(__file__).resolve().parents[3] / "documentation_robotics_viewer"
DEFAULT_OUTPUT_DIR = (
    Path(__file__).resolve().parent.parent
    / "tests"
    / "integration"
    / "fixtures"
    / "pipelines"
    / "individual_extraction"
)


def scenario_name(source_file: str) -> str:
    """Derive a filesystem-safe, collision-resistant scenario slug from a source file path."""
    stem = source_file.rsplit(".", 1)[0]
    slug = re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_")
    return f"dr_bootstrap_{slug}"


def _readme_content(
    scenario: BootstrapScenario, individual_count: int, relationship_count: int
) -> str:
    return f"""# DR Bootstrap Fixture: {scenario.source_file}

**Source:** `documentation_robotics_viewer`'s own dogfooded DR model
(`documentation-robotics/model/`), a real, independently-produced model.
**Wave:** 1 -- bootstrap corpus
(`documentation/karpathy_loop_dr_ontology_design.md` §5)
**Ontology:** Wave 0 DR spec import (`ontology_id: "{DR_ONTOLOGY_ID}"`), not
the placeholder.

## Overview

`input.json` pins the real content of `{scenario.source_file}` as it existed
in the viewer checkout at generation time. `expected.json` contains this
file's `provenance: extracted` individuals ({individual_count}) and the
`extracted`-provenance relationships whose endpoints are both individuals
from this same file ({relationship_count}). `inferred`-provenance elements,
and any relationship touching one, are excluded entirely -- they were not
literally stated in the text, so crediting or penalizing extraction against
them would measure DR's inference step, not this pipeline's extraction.

## Distractors

`distractors.json` is intentionally empty. Wave 1's source is a real,
already-curated architecture model, not authored fixture prose -- there is
no near-miss / plausible-but-wrong data in the viewer model to derive
distractors from (design doc §5, Must-Fix 3). A future wave that authors
prose directly (Wave 2+) can add distractors deliberately; fabricating them
here would not reflect anything actually present in the source data.
"""


def _write_scenario(scenario: BootstrapScenario, text: str, output_dir: Path) -> str:
    name = scenario_name(scenario.source_file)
    scenario_dir = output_dir / name
    scenario_dir.mkdir(parents=True, exist_ok=True)

    input_payload = {
        "text": text,
        "ontology_id": DR_ONTOLOGY_ID,
        "model": FIXTURE_MODEL,
        "temperature": FIXTURE_TEMPERATURE,
    }
    (scenario_dir / "input.json").write_text(json.dumps(input_payload, indent=2) + "\n")

    triples = scenario_triples(scenario)
    expected_payload = {
        "status": "completed",
        "result": {"triples": triples, "excluded": []},
        "created_individual_ids": [],
        "created_relationship_ids": [],
    }
    (scenario_dir / "expected.json").write_text(json.dumps(expected_payload, indent=2) + "\n")

    (scenario_dir / "distractors.json").write_text(json.dumps({"triples": []}, indent=2) + "\n")

    (scenario_dir / "README.md").write_text(
        _readme_content(scenario, len(scenario.individuals), len(scenario.relationships))
    )

    return name


def generate_corpus(
    viewer_dir: Path, output_dir: Path, prose_extensions: list[str], include_files: list[str] | None
) -> tuple[list[str], list[str]]:
    """
    Build and write all qualifying scenarios.

    Returns:
        (written_scenario_names, skipped_source_files) -- skipped files are
        ones discovered in the model data whose real content could not be
        found on disk in `viewer_dir`.
    """
    scenarios = build_scenarios(
        viewer_dir, prose_extensions=prose_extensions, include_files=include_files
    )

    written = []
    skipped = []
    for scenario in scenarios:
        source_path = viewer_dir / scenario.source_file
        if not source_path.is_file():
            print(
                f"WARNING: skipping '{scenario.source_file}' -- discovered in the model data but "
                f"not found at {source_path} (upstream drift). Re-run this script if/when it "
                "reappears.",
                file=sys.stderr,
            )
            skipped.append(scenario.source_file)
            continue
        name = _write_scenario(scenario, source_path.read_text(), output_dir)
        written.append(name)

    return written, skipped


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--viewer-dir",
        type=Path,
        default=DEFAULT_VIEWER_DIR,
        help=f"Path to the documentation_robotics_viewer checkout (default: {DEFAULT_VIEWER_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory to write scenario fixtures into (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--prose-extensions",
        nargs="+",
        default=[".md"],
        help="File extensions that qualify as prose source files (default: .md)",
    )
    parser.add_argument(
        "--include-files",
        nargs="+",
        default=None,
        help="Explicit source file list, overriding data-driven discovery",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    viewer_dir = args.viewer_dir.resolve()
    if not viewer_dir.is_dir():
        print(f"Viewer directory not found: {viewer_dir}", file=sys.stderr)
        return 1

    written, skipped = generate_corpus(
        viewer_dir=viewer_dir,
        output_dir=args.output_dir,
        prose_extensions=args.prose_extensions,
        include_files=args.include_files,
    )

    print(f"Wrote {len(written)} scenario(s): {', '.join(written) if written else '(none)'}")
    if skipped:
        print(f"Skipped {len(skipped)} discovered file(s) missing on disk: {', '.join(skipped)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
