"""
Integration tests for scripts/generate_dr_bootstrap_corpus.py.

Builds a small synthetic viewer checkout on disk (model YAML + real prose
files) under tmp_path and runs the actual corpus-writing code end-to-end,
verifying the fixture files it produces -- not just the pure discovery
logic already covered by tests/unit/scripts/test_dr_bootstrap_loader.py.
"""

import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import yaml

from scripts.generate_dr_bootstrap_corpus import generate_corpus, scenario_name


def _write_layer(viewer_dir, layer_dir, filename, elements):
    model_dir = viewer_dir / "documentation-robotics" / "model" / layer_dir
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / filename).write_text(yaml.safe_dump({el["path"]: el for el in elements}))


def _write_relationships(viewer_dir, relationships):
    model_dir = viewer_dir / "documentation-robotics" / "model"
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "relationships.yaml").write_text(yaml.safe_dump(relationships))


def _element(path, name, spec_node_id, provenance, locations):
    return {
        "path": path,
        "name": name,
        "spec_node_id": spec_node_id,
        "source_reference": {
            "provenance": provenance,
            "locations": [{"file": file} for file in locations],
        },
    }


class TestScenarioName:
    def test_simple_filename(self):
        assert scenario_name("README.md") == "dr_bootstrap_readme"

    def test_nested_path_is_disambiguated_from_top_level_namesake(self):
        assert scenario_name("tests/README.md") == "dr_bootstrap_tests_readme"
        assert scenario_name("README.md") != scenario_name("tests/README.md")

    def test_nested_path_separators_become_underscores(self):
        assert (
            scenario_name("documentation/ACCESSIBILITY.md")
            == "dr_bootstrap_documentation_accessibility"
        )


class TestGenerateCorpus:
    def _setup_viewer(self, viewer_dir):
        _write_layer(
            viewer_dir,
            "01_motivation",
            "goal.yaml",
            [
                _element(
                    "motivation.goal.readme-goal",
                    "Readme Goal",
                    "motivation.goal",
                    "extracted",
                    ["README.md"],
                ),
                _element(
                    "motivation.goal.missing-goal",
                    "Missing File Goal",
                    "motivation.goal",
                    "extracted",
                    ["documentation/ACCESSIBILITY.md"],
                ),
            ],
        )
        _write_relationships(viewer_dir, [])
        (viewer_dir / "README.md").write_text("# Real README\n\nThis is the real pinned content.\n")
        # documentation/ACCESSIBILITY.md is intentionally NOT written to disk,
        # simulating a file discoverable from model data but absent upstream.

    def test_writes_input_expected_distractors_and_readme_for_existing_files(self, tmp_path):
        viewer_dir = tmp_path / "viewer"
        output_dir = tmp_path / "fixtures"
        self._setup_viewer(viewer_dir)

        written, skipped = generate_corpus(
            viewer_dir=viewer_dir,
            output_dir=output_dir,
            prose_extensions=[".md"],
            include_files=None,
        )

        assert written == ["dr_bootstrap_readme"]
        scenario_dir = output_dir / "dr_bootstrap_readme"
        assert (scenario_dir / "input.json").is_file()
        assert (scenario_dir / "expected.json").is_file()
        assert (scenario_dir / "distractors.json").is_file()
        assert (scenario_dir / "README.md").is_file()

    def test_input_json_contains_real_pinned_content_and_dr_ontology_id(self, tmp_path):
        viewer_dir = tmp_path / "viewer"
        output_dir = tmp_path / "fixtures"
        self._setup_viewer(viewer_dir)

        generate_corpus(
            viewer_dir=viewer_dir,
            output_dir=output_dir,
            prose_extensions=[".md"],
            include_files=None,
        )

        input_payload = json.loads((output_dir / "dr_bootstrap_readme" / "input.json").read_text())
        assert input_payload["text"] == "# Real README\n\nThis is the real pinned content.\n"
        assert input_payload["ontology_id"] == "dr_spec"

    def test_expected_json_contains_extracted_individual_triple(self, tmp_path):
        viewer_dir = tmp_path / "viewer"
        output_dir = tmp_path / "fixtures"
        self._setup_viewer(viewer_dir)

        generate_corpus(
            viewer_dir=viewer_dir,
            output_dir=output_dir,
            prose_extensions=[".md"],
            include_files=None,
        )

        expected_payload = json.loads(
            (output_dir / "dr_bootstrap_readme" / "expected.json").read_text()
        )
        triples = expected_payload["result"]["triples"]
        assert triples == [
            {
                "subject": {"label": "Readme Goal", "kind": "individual"},
                "predicate": {"label": "is_a", "kind": "property"},
                "object": {"label": "motivation.goal", "kind": "individual"},
                "confidence": 1.0,
            }
        ]

    def test_distractors_json_is_always_empty(self, tmp_path):
        viewer_dir = tmp_path / "viewer"
        output_dir = tmp_path / "fixtures"
        self._setup_viewer(viewer_dir)

        generate_corpus(
            viewer_dir=viewer_dir,
            output_dir=output_dir,
            prose_extensions=[".md"],
            include_files=None,
        )

        distractors_payload = json.loads(
            (output_dir / "dr_bootstrap_readme" / "distractors.json").read_text()
        )
        assert distractors_payload == {"triples": []}

    def test_readme_explains_the_empty_distractors_disposition(self, tmp_path):
        viewer_dir = tmp_path / "viewer"
        output_dir = tmp_path / "fixtures"
        self._setup_viewer(viewer_dir)

        generate_corpus(
            viewer_dir=viewer_dir,
            output_dir=output_dir,
            prose_extensions=[".md"],
            include_files=None,
        )

        readme_text = (output_dir / "dr_bootstrap_readme" / "README.md").read_text()
        assert "distractors" in readme_text.lower()
        assert "no near-miss" in readme_text.lower()

    def test_file_missing_on_disk_is_skipped_not_fabricated(self, tmp_path):
        viewer_dir = tmp_path / "viewer"
        output_dir = tmp_path / "fixtures"
        self._setup_viewer(viewer_dir)

        written, skipped = generate_corpus(
            viewer_dir=viewer_dir,
            output_dir=output_dir,
            prose_extensions=[".md"],
            include_files=None,
        )

        assert skipped == ["documentation/ACCESSIBILITY.md"]
        assert not (output_dir / "dr_bootstrap_documentation_accessibility").exists()
