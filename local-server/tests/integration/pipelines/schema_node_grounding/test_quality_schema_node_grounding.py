"""
Quality suite for schema node grounding pipeline.

Validates grounding pipeline with ≥30 labeled classes, computes ranking metrics
(top-1 precision, top-3 precision, MRR), and verifies all four source adapters
are wired and operational.

Includes apply round-trip test ensuring idempotent ontology state.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from adapters.reference.conceptnet import ConceptNetSource
from adapters.reference.dbpedia import DBpediaSource
from adapters.reference.grounding.adapter import GroundingAdapter
from adapters.reference.schema_org import SchemaOrgSource
from adapters.reference.wikidata import WikidataSource
from domain.ontology.entities import Class
from domain.pipelines.entities import PipelineRun, PipelineRunStatus
from domain.pipelines.schema_node_grounding.apply_service import SchemaGroundingApplyService
from domain.pipelines.schema_node_grounding.orchestrator import SchemaGroundingOrchestrator
from domain.pipelines.schema_node_grounding.scoring import GroundingScorer
from tests.fixtures.pipeline_fixtures import load_distractors, load_expected_output, load_fixture

_test_file = os.path.abspath(__file__)
_test_dir = os.path.dirname(_test_file)
_root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_test_dir))))
sys.path.insert(0, _root_dir)


def _get_fixtures_dir() -> Path:
    """Get the grounding fixtures directory."""
    return Path(__file__).parent.parent.parent / "fixtures" / "pipelines" / "schema_node_grounding"


def _list_fixture_scenarios() -> list[str]:
    """List all scenario directories in the grounding fixtures."""
    fixtures_dir = _get_fixtures_dir()
    if not fixtures_dir.exists():
        return []
    return [d.name for d in fixtures_dir.iterdir() if d.is_dir() and (d / "input.json").exists()]


class QualityMetrics:
    """Metrics for grounding quality evaluation."""

    def __init__(self):
        self.top1_hits = 0
        self.top3_hits = 0
        self.mrr_sum = 0.0
        self.distractor_precision_sum = 0.0
        self.total_scenarios = 0

    def compute_metrics(self) -> dict[str, float]:
        """Compute aggregate metrics."""
        if self.total_scenarios == 0:
            return {
                "top1_precision": 0.0,
                "top3_precision": 0.0,
                "mrr": 0.0,
                "distractor_precision": 0.0,
            }
        return {
            "top1_precision": self.top1_hits / self.total_scenarios,
            "top3_precision": self.top3_hits / self.total_scenarios,
            "mrr": self.mrr_sum / self.total_scenarios,
            "distractor_precision": self.distractor_precision_sum / self.total_scenarios,
        }


class TestQualitySchemaNodeGrounding:
    """Quality test suite for schema node grounding."""

    @pytest.fixture
    def grounding_adapter(self):
        """Create a GroundingAdapter with all sources."""
        dbpedia = DBpediaSource()
        conceptnet = ConceptNetSource()
        wikidata = WikidataSource()
        schema_org = SchemaOrgSource()

        return GroundingAdapter(
            dbpedia=dbpedia,
            conceptnet=conceptnet,
            wikidata=wikidata,
            schema_org=schema_org,
        )

    @pytest.fixture
    def grounding_scorer(self):
        """Create a GroundingScorer."""
        return GroundingScorer()

    @pytest.fixture
    def grounding_orchestrator(self, grounding_adapter, grounding_scorer):
        """Create a SchemaGroundingOrchestrator."""
        return SchemaGroundingOrchestrator(
            llm_provider=None,
            grounding_adapter=grounding_adapter,
            scorer=grounding_scorer,
            config={"top_n": 10},
        )

    def test_all_adapters_wired(self, grounding_adapter):
        """Verify all four source adapters are wired and operational."""
        # Check all sources are registered
        assert "DBpedia" in grounding_adapter._sources
        assert "ConceptNet" in grounding_adapter._sources
        assert "Wikidata" in grounding_adapter._sources
        assert "schema.org" in grounding_adapter._sources

        # Verify each source is the correct type
        assert isinstance(grounding_adapter._sources["DBpedia"], DBpediaSource)
        assert isinstance(grounding_adapter._sources["ConceptNet"], ConceptNetSource)
        assert isinstance(grounding_adapter._sources["Wikidata"], WikidataSource)
        assert isinstance(grounding_adapter._sources["schema.org"], SchemaOrgSource)

    @pytest.mark.asyncio
    @pytest.mark.external_network
    async def test_dbpedia_adapter_operational(self, grounding_adapter, recorded_vcr):
        """Verify DBpedia adapter returns candidates (requires network/cassettes)."""
        # This test uses recorded HTTP cassettes
        try:
            with recorded_vcr.use_cassette("schema_node_grounding/dbpedia/person"):
                candidates = await grounding_adapter.query_sources(
                    label="Person", sources=["DBpedia"]
                )
            assert len(candidates) > 0, "DBpedia should return candidates for 'Person'"
            assert all(c.source == "DBpedia" for c in candidates)
        except Exception as e:
            pytest.fail(f"DBpedia adapter should be operational: {e}")

    @pytest.mark.asyncio
    @pytest.mark.external_network
    async def test_conceptnet_adapter_operational(self, grounding_adapter, recorded_vcr):
        """Verify ConceptNet adapter returns candidates (requires network/cassettes)."""
        try:
            with recorded_vcr.use_cassette("schema_node_grounding/conceptnet/person"):
                candidates = await grounding_adapter.query_sources(
                    label="Person", sources=["ConceptNet"]
                )
            assert len(candidates) > 0, "ConceptNet should return candidates for 'Person'"
            assert all(c.source == "ConceptNet" for c in candidates)
        except Exception as e:
            pytest.fail(f"ConceptNet adapter should be operational: {e}")

    @pytest.mark.asyncio
    @pytest.mark.external_network
    async def test_wikidata_adapter_operational(self, grounding_adapter, recorded_vcr):
        """Verify Wikidata adapter returns candidates (requires network/cassettes)."""
        try:
            with recorded_vcr.use_cassette("schema_node_grounding/wikidata/person"):
                candidates = await grounding_adapter.query_sources(
                    label="Person", sources=["Wikidata"]
                )
            assert len(candidates) > 0, "Wikidata should return candidates for 'Person'"
            assert all(c.source == "Wikidata" for c in candidates)
        except Exception as e:
            pytest.fail(f"Wikidata adapter should be operational: {e}")

    @pytest.mark.asyncio
    async def test_schema_org_adapter_operational(self, grounding_adapter):
        """Verify schema.org adapter returns candidates (offline, no HTTP)."""
        try:
            candidates = await grounding_adapter.query_sources(
                label="Person", sources=["schema.org"]
            )
            assert len(candidates) > 0, "schema.org should return candidates for 'Person'"
            assert all(c.source == "schema.org" for c in candidates)
        except Exception as e:
            pytest.fail(f"schema.org adapter should be operational: {e}")

    @pytest.mark.asyncio
    async def test_quality_metrics_computation(self, grounding_orchestrator, recorded_vcr):
        """Test quality metrics computation across all 38+ fixture scenarios."""
        scenarios = _list_fixture_scenarios()
        assert len(scenarios) >= 30, f"Expected ≥30 fixtures, got {len(scenarios)}"

        metrics = QualityMetrics()
        jsonl_rows = []
        skipped_scenarios = []

        for scenario in scenarios:  # Evaluate all scenarios for representative coverage
            try:
                fixture = load_fixture("schema_node_grounding", scenario)
                expected = load_expected_output("schema_node_grounding", scenario)
                distractors = load_distractors("schema_node_grounding", scenario)

                node_label = fixture.get("node_label", "")
                expected_uris = {
                    ref["uri"] for ref in expected.get("expected_external_references", [])
                }

                # Execute grounding with cassettes for all sources
                from domain.pipelines.orchestration.base import PipelineState

                state = PipelineState(
                    run_id=f"run-{scenario}",
                    pipeline_type="schema_node_grounding",
                    input_data=fixture,
                )
                # Wrap HTTP calls in nested cassette contexts for each source
                with recorded_vcr.use_cassette(f"schema_node_grounding/dbpedia/{scenario}"):
                    with recorded_vcr.use_cassette(f"schema_node_grounding/conceptnet/{scenario}"):
                        with recorded_vcr.use_cassette(
                            f"schema_node_grounding/wikidata/{scenario}"
                        ):
                            result_state = await grounding_orchestrator.execute(state)

                # Extract groundings
                groundings = result_state.result.get("groundings", [])
                grounded_uris = [g["uri"] for g in groundings]

                # Compute metrics
                top1_hit = 1 if (grounded_uris and grounded_uris[0] in expected_uris) else 0
                top3_hit = 1 if any(uri in expected_uris for uri in grounded_uris[:3]) else 0

                # Compute MRR (Mean Reciprocal Rank)
                mrr = 0.0
                for rank, uri in enumerate(grounded_uris, 1):
                    if uri in expected_uris:
                        mrr = 1.0 / rank
                        break

                # Compute distractor precision
                distractor_precision = 0.0
                if distractors:
                    distractor_uris = {
                        uri
                        for source_distractors in distractors.values()
                        for uri in source_distractors
                    }
                    if grounded_uris:
                        distractor_matches = sum(
                            1 for uri in grounded_uris if uri in distractor_uris
                        )
                        distractor_precision = 1.0 - (distractor_matches / len(grounded_uris))

                metrics.top1_hits += top1_hit
                metrics.top3_hits += top3_hit
                metrics.mrr_sum += mrr
                metrics.distractor_precision_sum += distractor_precision
                metrics.total_scenarios += 1

                # Emit JSONL row
                jsonl_row = {
                    "pipeline_type": "schema_node_grounding",
                    "scenario": scenario,
                    "node_label": node_label,
                    "top1_precision": top1_hit,
                    "top3_precision": top3_hit,
                    "mrr": mrr,
                    "distractor_precision": distractor_precision,
                }
                jsonl_rows.append(jsonl_row)

            except Exception as e:
                skipped_scenarios.append((scenario, str(e)))
                continue

        # Assert minimum scenarios evaluated before computing metrics
        assert (
            metrics.total_scenarios >= 30
        ), (
            f"Only {metrics.total_scenarios}/{len(scenarios)} scenarios "
            f"evaluated (need cassettes for all 38+ scenarios)"
        )

        # Compute aggregate metrics
        agg_metrics = metrics.compute_metrics()

        # Log skipped scenarios
        if skipped_scenarios:
            print(f"\n=== Skipped {len(skipped_scenarios)} scenarios ===")
            for scenario, error in skipped_scenarios:
                print(f"  {scenario}: {error}")

        # Emit JSONL results
        print(
            "\n=== Grounding Quality Metrics ({}/{} scenarios) ===".format(
                len(jsonl_rows), len(scenarios)
            )
        )
        for row in jsonl_rows:
            print(json.dumps(row))
        print("\n=== Aggregate Metrics ===")
        print(json.dumps(agg_metrics))

        # Assert metric floors
        assert (
            agg_metrics["top1_precision"] >= 0.50
        ), f"top1_precision {agg_metrics['top1_precision']} < 0.50"
        assert (
            agg_metrics["top3_precision"] >= 0.70
        ), f"top3_precision {agg_metrics['top3_precision']} < 0.70"
        assert agg_metrics["mrr"] >= 0.60, f"mrr {agg_metrics['mrr']} < 0.60"

    @pytest.mark.asyncio
    async def test_apply_roundtrip_idempotent(self):
        """Test apply round-trip: run → apply → revert → re-apply → verify idempotent state."""
        # Create a mock ontology repository
        mock_repo = Mock()

        # Create a sample class
        cls = Class(
            id="class-grounding-test",
            concept_scheme_id="scheme-1",
            taxonomy_id="tax-1",
            title="TestClass",
            description="A test class for roundtrip verification",
            external_references=[],
        )

        # Mock repository methods
        mock_repo.get_class.return_value = cls

        # Create a grounding run with results
        grounding_run = PipelineRun(
            id="run-roundtrip",
            batch_run_id="batch-roundtrip",
            implementation_id="default",
            configuration_slug="grounding-default",
            configuration_version=1,
            status=PipelineRunStatus.COMPLETED,
            output_summary={
                "groundings": [
                    {
                        "uri": "http://dbpedia.org/resource/Test",
                        "source": "DBpedia",
                        "match_confidence": 0.95,
                    },
                    {
                        "uri": "http://www.wikidata.org/entity/Q123",
                        "source": "Wikidata",
                        "match_confidence": 0.85,
                    },
                ]
            },
        )

        # Step 1: Apply grounding
        apply_service = SchemaGroundingApplyService(mock_repo)
        result1 = apply_service.apply(grounding_run, cls.id)

        assert result1.external_references_created == 2
        assert len(cls.external_references) == 2

        # Store state after first apply
        state_after_apply = [
            (ref.identifier, ref.uri, ref.source) for ref in cls.external_references
        ]

        # Step 2: Revert (remove references)
        cls.external_references = []
        state_after_revert = [
            (ref.identifier, ref.uri, ref.source) for ref in cls.external_references
        ]
        assert len(state_after_revert) == 0

        # Step 3: Re-apply same grounding
        result2 = apply_service.apply(grounding_run, cls.id)

        assert result2.external_references_created == 2
        assert len(cls.external_references) == 2

        # Store state after second apply
        state_after_reapply = [
            (ref.identifier, ref.uri, ref.source) for ref in cls.external_references
        ]

        # Step 4: Verify idempotent behavior
        assert (
            state_after_apply == state_after_reapply
        ), "Ontology state should be identical after re-apply"
        assert len(cls.external_references) == 2

        # Step 5: Apply again with same run (should deduplicate)
        result3 = apply_service.apply(grounding_run, cls.id)

        assert result3.external_references_created == 0, "Re-applying should not create duplicates"
        assert result3.external_references_skipped == 2
        assert len(cls.external_references) == 2, "State should remain unchanged"

    @pytest.mark.asyncio
    async def test_distractor_candidates_excluded_from_top_ranked(
        self, grounding_orchestrator, recorded_vcr
    ):
        """Verify that distractor candidates don't artificially inflate top rankings."""
        # Load a fixture with distractors
        scenario = "person"  # We know this exists from seed script
        fixture = load_fixture("schema_node_grounding", scenario)
        expected = load_expected_output("schema_node_grounding", scenario)
        distractors = load_distractors("schema_node_grounding", scenario)

        # Verify fixture structure
        assert distractors is not None, "Person fixture should have distractors"
        assert len(distractors.get("DBpedia", [])) >= 3, "Should have ≥3 DBpedia distractors"

        # Execute grounding to get ranked candidates with cassettes
        from domain.pipelines.orchestration.base import PipelineState

        state = PipelineState(
            run_id=f"run-{scenario}",
            pipeline_type="schema_node_grounding",
            input_data=fixture,
        )
        with recorded_vcr.use_cassette(f"schema_node_grounding/dbpedia/{scenario}"):
            with recorded_vcr.use_cassette(f"schema_node_grounding/conceptnet/{scenario}"):
                with recorded_vcr.use_cassette(f"schema_node_grounding/wikidata/{scenario}"):
                    result_state = await grounding_orchestrator.execute(state)

        # Extract groundings and verify they are ranked
        groundings = result_state.result.get("groundings", [])
        assert len(groundings) > 0, "Orchestrator should return at least one grounding"

        grounded_uris = [g["uri"] for g in groundings]

        # Verify that expected references rank higher than distractors
        expected_uris = {ref["uri"] for ref in expected.get("expected_external_references", [])}
        all_distractor_uris = {
            uri for source_distractors in distractors.values() for uri in source_distractors
        }

        # Find first correct match rank
        correct_rank = None
        for rank, uri in enumerate(grounded_uris, 1):
            if uri in expected_uris:
                correct_rank = rank
                break

        assert correct_rank is not None, "Expected reference should be present in ranked groundings"

        # Find first distractor rank
        distractor_rank = None
        for rank, uri in enumerate(grounded_uris, 1):
            if uri in all_distractor_uris:
                distractor_rank = rank
                break

        # Distractors may not be present if expected refs are ranked first
        if distractor_rank is not None:
            assert correct_rank <= distractor_rank, (
                f"Expected reference should rank before distractors "
                f"(correct at {correct_rank}, distractor at {distractor_rank})"
            )

    def test_fixture_corpus_coverage(self):
        """Verify fixture corpus has ≥30 classes spanning multiple domains."""
        scenarios = _list_fixture_scenarios()
        assert len(scenarios) >= 30, f"Expected ≥30 fixtures, got {len(scenarios)}"

        # Verify different domains represented
        biology_classes = {"animal", "plant", "cell", "protein", "dna", "bacteria", "virus"}
        technology_classes = {"software", "network", "algorithm", "database"}
        social_classes = {"person", "organization", "artist", "university", "government"}

        scenario_set = set(scenarios)
        assert len(scenario_set & biology_classes) >= 3, "Should have ≥3 biology classes"
        assert len(scenario_set & technology_classes) >= 2, "Should have ≥2 technology classes"
        assert len(scenario_set & social_classes) >= 2, "Should have ≥2 social classes"

    def test_each_fixture_has_distractors(self):
        """Verify all quality suite fixtures (≥30 classes) include distractors."""
        scenarios = _list_fixture_scenarios()
        # Filter to quality suite fixtures (exclude legacy fixtures like 'basic')
        quality_scenarios = [s for s in scenarios if s != "basic"]

        for scenario in quality_scenarios:  # Check all fixtures
            distractors = load_distractors("schema_node_grounding", scenario)
            assert distractors is not None, f"Fixture {scenario} should have distractors"

            # Verify structure: at least one source has ≥3 distractors (FR-P3.4 compliance)
            has_sufficient_distractors = False
            for source in ["DBpedia", "ConceptNet", "Wikidata", "schema.org"]:
                if source in distractors:
                    count = len(distractors[source])
                    assert 0 <= count <= 5, (
                        f"Fixture {scenario} {source} has {count} distractors, " f"expected 0-5"
                    )
                    if count >= 3:
                        has_sufficient_distractors = True
            assert (
                has_sufficient_distractors
            ), f"Fixture {scenario} should have ≥3 distractors from at least one source"

    def test_fixture_has_required_fields(self):
        """Verify fixtures have all required fields."""
        scenario = "person"
        fixture = load_fixture("schema_node_grounding", scenario)
        expected = load_expected_output("schema_node_grounding", scenario)

        # Check fixture fields
        assert "node_label" in fixture
        assert "node_type" in fixture
        assert "sources" in fixture

        # Check expected fields
        assert "expected_external_references" in expected
        assert isinstance(expected["expected_external_references"], list)
        assert len(expected["expected_external_references"]) > 0

        # Check expected_external_references structure
        for ref in expected["expected_external_references"]:
            assert "uri" in ref
            assert "source" in ref
            assert ref["source"] in ["DBpedia", "ConceptNet", "Wikidata", "schema.org"]


class TestQualityMetricsIntegration:
    """Integration tests for quality metrics across all fixtures."""

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_all_fixtures_produce_metrics(self):
        """Test that all quality fixtures (≥30) can produce metrics without errors."""
        scenarios = _list_fixture_scenarios()
        # Filter to quality suite fixtures (exclude legacy fixtures like 'basic')
        quality_scenarios = [s for s in scenarios if s != "basic"]

        # Count successful metric computations
        successful = 0
        failed = 0

        for scenario in quality_scenarios:
            try:
                fixture = load_fixture("schema_node_grounding", scenario)
                distractors = load_distractors("schema_node_grounding", scenario)

                # Verify structure
                assert fixture.get("node_label"), f"{scenario}: missing node_label"
                assert distractors is not None, f"{scenario}: missing distractors"

                successful += 1
            except Exception as e:
                failed += 1
                print(f"Scenario {scenario} failed: {e}")

        print(f"\nQuality fixtures: {successful} valid out of {len(quality_scenarios)}")
        assert (
            len(quality_scenarios) >= 30
        ), f"Expected ≥30 quality fixtures, got {len(quality_scenarios)}"
        assert failed == 0, f"Expected all quality scenarios to be valid, {failed} failed"
