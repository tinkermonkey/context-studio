"""
Unit tests for the Wave 1 DR bootstrap corpus discovery/filter logic
(scripts/dr_bootstrap_loader.py).

Uses tiny synthetic viewer model directories (not the real
documentation_robotics_viewer checkout, which is an external dependency not
available in CI) to exercise data-driven file discovery, extracted/inferred
filtering, multi-location matching, and relationship endpoint filtering.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import yaml

from scripts.dr_bootstrap_loader import (
    BootstrapScenario,
    build_scenarios,
    discover_prose_files,
    iter_elements,
    load_relationships,
    scenario_triples,
)


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


def _write_layer(viewer_dir, layer_dir, filename, elements):
    model_dir = viewer_dir / "documentation-robotics" / "model" / layer_dir
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / filename).write_text(yaml.safe_dump({el["path"]: el for el in elements}))


def _write_relationships(viewer_dir, relationships):
    model_dir = viewer_dir / "documentation-robotics" / "model"
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "relationships.yaml").write_text(yaml.safe_dump(relationships))


def _write_manifest(viewer_dir):
    model_dir = viewer_dir / "documentation-robotics" / "model"
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "manifest.yaml").write_text(yaml.safe_dump({"version": "0.1.0"}))


class TestDiscoverProseFiles:
    def test_finds_md_files_referenced_by_elements(self, tmp_path):
        elements = [
            _element("motivation.goal.a", "A", "motivation.goal", "extracted", ["README.md"]),
            _element("motivation.goal.b", "B", "motivation.goal", "inferred", ["CLAUDE.md"]),
        ]
        assert discover_prose_files(elements, [".md"]) == ["CLAUDE.md", "README.md"]

    def test_ignores_non_matching_extensions(self, tmp_path):
        elements = [
            _element(
                "application.svc.a",
                "A",
                "application.applicationservice",
                "extracted",
                ["src/app.ts"],
            ),
            _element("motivation.goal.a", "A", "motivation.goal", "extracted", ["README.md"]),
        ]
        assert discover_prose_files(elements, [".md"]) == ["README.md"]

    def test_dedups_across_elements(self, tmp_path):
        elements = [
            _element("motivation.goal.a", "A", "motivation.goal", "extracted", ["README.md"]),
            _element("motivation.goal.b", "B", "motivation.goal", "extracted", ["README.md"]),
        ]
        assert discover_prose_files(elements, [".md"]) == ["README.md"]

    def test_element_with_no_source_reference_is_ignored(self, tmp_path):
        assert discover_prose_files([{"path": "x", "name": "X"}], [".md"]) == []

    def test_extension_match_is_case_insensitive(self, tmp_path):
        elements = [
            _element("motivation.goal.a", "A", "motivation.goal", "extracted", ["README.MD"])
        ]
        assert discover_prose_files(elements, [".md"]) == ["README.MD"]


class TestIterElementsAndLoadRelationships:
    def test_iter_elements_reads_all_layer_files_excluding_manifest_and_relationships(
        self, tmp_path
    ):
        _write_manifest(tmp_path)
        _write_layer(
            tmp_path,
            "01_motivation",
            "goal.yaml",
            [_element("motivation.goal.a", "A", "motivation.goal", "extracted", ["README.md"])],
        )
        _write_relationships(
            tmp_path,
            [{"source": "motivation.goal.a", "target": "motivation.goal.a", "predicate": "self"}],
        )
        elements = iter_elements(tmp_path)
        assert [el["path"] for el in elements] == ["motivation.goal.a"]

    def test_load_relationships_missing_file_returns_empty(self, tmp_path):
        (tmp_path / "documentation-robotics" / "model").mkdir(parents=True)
        assert load_relationships(tmp_path) == []


class TestBuildScenarios:
    def _setup_basic_model(self, viewer_dir):
        _write_manifest(viewer_dir)
        _write_layer(
            viewer_dir,
            "01_motivation",
            "goal.yaml",
            [
                _element(
                    "motivation.goal.extracted-readme",
                    "Extracted Readme Goal",
                    "motivation.goal",
                    "extracted",
                    ["README.md"],
                ),
                _element(
                    "motivation.goal.inferred-readme",
                    "Inferred Readme Goal",
                    "motivation.goal",
                    "inferred",
                    ["README.md"],
                ),
                _element(
                    "motivation.goal.extracted-claude",
                    "Extracted Claude Goal",
                    "motivation.goal",
                    "extracted",
                    ["CLAUDE.md"],
                ),
            ],
        )

    def test_one_scenario_per_qualifying_file(self, tmp_path):
        self._setup_basic_model(tmp_path)
        _write_relationships(tmp_path, [])
        scenarios = build_scenarios(tmp_path, prose_extensions=[".md"])
        assert [s.source_file for s in scenarios] == ["CLAUDE.md", "README.md"]

    def test_inferred_individuals_excluded(self, tmp_path):
        self._setup_basic_model(tmp_path)
        _write_relationships(tmp_path, [])
        scenarios = build_scenarios(tmp_path, prose_extensions=[".md"])
        readme_scenario = next(s for s in scenarios if s.source_file == "README.md")
        assert [el["path"] for el in readme_scenario.individuals] == [
            "motivation.goal.extracted-readme"
        ]

    def test_non_prose_source_file_never_produces_a_scenario(self, tmp_path):
        _write_manifest(tmp_path)
        _write_layer(
            tmp_path,
            "04_application",
            "applicationservice.yaml",
            [
                _element(
                    "application.applicationservice.a",
                    "A",
                    "application.applicationservice",
                    "extracted",
                    ["src/app.ts"],
                )
            ],
        )
        _write_relationships(tmp_path, [])
        assert build_scenarios(tmp_path, prose_extensions=[".md"]) == []

    def test_element_with_multiple_locations_appears_in_every_qualifying_scenario(self, tmp_path):
        _write_manifest(tmp_path)
        _write_layer(
            tmp_path,
            "01_motivation",
            "goal.yaml",
            [
                _element(
                    "motivation.goal.shared",
                    "Shared Goal",
                    "motivation.goal",
                    "extracted",
                    ["README.md", "CLAUDE.md"],
                )
            ],
        )
        _write_relationships(tmp_path, [])
        scenarios = build_scenarios(tmp_path, prose_extensions=[".md"])
        assert {s.source_file: [el["path"] for el in s.individuals] for s in scenarios} == {
            "CLAUDE.md": ["motivation.goal.shared"],
            "README.md": ["motivation.goal.shared"],
        }

    def test_include_files_overrides_discovery(self, tmp_path):
        self._setup_basic_model(tmp_path)
        _write_relationships(tmp_path, [])
        scenarios = build_scenarios(tmp_path, prose_extensions=[".md"], include_files=["README.md"])
        assert [s.source_file for s in scenarios] == ["README.md"]

    def test_relationship_with_both_extracted_endpoints_in_same_file_is_included(self, tmp_path):
        _write_manifest(tmp_path)
        _write_layer(
            tmp_path,
            "01_motivation",
            "goal.yaml",
            [
                _element(
                    "motivation.goal.a", "Goal A", "motivation.goal", "extracted", ["README.md"]
                ),
                _element(
                    "motivation.goal.b", "Goal B", "motivation.goal", "extracted", ["README.md"]
                ),
            ],
        )
        _write_relationships(
            tmp_path,
            [
                {
                    "source": "motivation.goal.a",
                    "target": "motivation.goal.b",
                    "predicate": "associated-with",
                    "properties": {"source_provenance": "extracted"},
                }
            ],
        )
        scenarios = build_scenarios(tmp_path, prose_extensions=[".md"])
        assert len(scenarios[0].relationships) == 1

    def test_relationship_touching_an_inferred_individual_is_excluded(self, tmp_path):
        _write_manifest(tmp_path)
        _write_layer(
            tmp_path,
            "01_motivation",
            "goal.yaml",
            [
                _element(
                    "motivation.goal.a", "Goal A", "motivation.goal", "extracted", ["README.md"]
                ),
                _element(
                    "motivation.goal.b", "Goal B", "motivation.goal", "inferred", ["README.md"]
                ),
            ],
        )
        _write_relationships(
            tmp_path,
            [
                {
                    "source": "motivation.goal.a",
                    "target": "motivation.goal.b",
                    "predicate": "associated-with",
                    "properties": {"source_provenance": "extracted"},
                }
            ],
        )
        scenarios = build_scenarios(tmp_path, prose_extensions=[".md"])
        assert scenarios[0].relationships == []

    def test_relationship_spanning_two_files_is_excluded_from_both(self, tmp_path):
        self._setup_basic_model(tmp_path)
        _write_relationships(
            tmp_path,
            [
                {
                    "source": "motivation.goal.extracted-readme",
                    "target": "motivation.goal.extracted-claude",
                    "predicate": "associated-with",
                    "properties": {"source_provenance": "extracted"},
                }
            ],
        )
        scenarios = build_scenarios(tmp_path, prose_extensions=[".md"])
        assert all(s.relationships == [] for s in scenarios)

    def test_relationship_with_inferred_source_provenance_is_excluded(self, tmp_path):
        _write_manifest(tmp_path)
        _write_layer(
            tmp_path,
            "01_motivation",
            "goal.yaml",
            [
                _element(
                    "motivation.goal.a", "Goal A", "motivation.goal", "extracted", ["README.md"]
                ),
                _element(
                    "motivation.goal.b", "Goal B", "motivation.goal", "extracted", ["README.md"]
                ),
            ],
        )
        _write_relationships(
            tmp_path,
            [
                {
                    "source": "motivation.goal.a",
                    "target": "motivation.goal.b",
                    "predicate": "associated-with",
                    "properties": {"source_provenance": "inferred"},
                }
            ],
        )
        scenarios = build_scenarios(tmp_path, prose_extensions=[".md"])
        assert scenarios[0].relationships == []

    def test_missing_source_file_on_disk_still_produces_a_scenario(self, tmp_path):
        # build_scenarios is pure data-model logic; it does not touch the
        # filesystem for the prose files themselves -- that's the generator
        # script's job, so a source file's real absence from disk has no
        # bearing on whether it is discovered as a scenario here.
        self._setup_basic_model(tmp_path)
        _write_relationships(tmp_path, [])
        scenarios = build_scenarios(tmp_path, prose_extensions=[".md"])
        assert len(scenarios) == 2


class TestScenarioTriples:
    def test_individual_triples_use_is_a_predicate_and_spec_node_id_object(self, tmp_path):
        scenario = BootstrapScenario(
            source_file="README.md",
            individuals=[
                _element(
                    "motivation.goal.a", "Goal A", "motivation.goal", "extracted", ["README.md"]
                )
            ],
            relationships=[],
        )
        triples = scenario_triples(scenario)
        assert triples == [
            {
                "subject": {"label": "Goal A", "kind": "individual"},
                "predicate": {"label": "is_a", "kind": "property"},
                "object": {"label": "motivation.goal", "kind": "individual"},
                "confidence": 1.0,
            }
        ]

    def test_relationship_triples_use_relationship_predicate_and_endpoint_names(self, tmp_path):
        individual_a = _element(
            "motivation.goal.a", "Goal A", "motivation.goal", "extracted", ["README.md"]
        )
        individual_b = _element(
            "motivation.goal.b", "Goal B", "motivation.goal", "extracted", ["README.md"]
        )
        scenario = BootstrapScenario(
            source_file="README.md",
            individuals=[individual_a, individual_b],
            relationships=[
                {
                    "source": "motivation.goal.a",
                    "target": "motivation.goal.b",
                    "predicate": "associated-with",
                    "properties": {"source_provenance": "extracted"},
                }
            ],
        )
        triples = scenario_triples(scenario)
        assert triples[-1] == {
            "subject": {"label": "Goal A", "kind": "individual"},
            "predicate": {"label": "associated-with", "kind": "property"},
            "object": {"label": "Goal B", "kind": "individual"},
            "confidence": 1.0,
        }

    def test_empty_scenario_produces_no_triples(self, tmp_path):
        scenario = BootstrapScenario(
            source_file="tests/README.md", individuals=[], relationships=[]
        )
        assert scenario_triples(scenario) == []
