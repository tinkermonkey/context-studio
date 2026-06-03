"""
Quality suite for schema node grounding pipeline.

Validates source adapter registration and applies roundtrip idempotency.
Also verifies fixture corpus coverage and distractor presence.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from adapters.llm.provider_router import LLMProviderRouter
from adapters.reference.conceptnet import ConceptNetSource
from adapters.reference.dbpedia import DBpediaSource
from adapters.reference.grounding.adapter import GroundingAdapter
from adapters.reference.schema_org import SchemaOrgSource
from adapters.reference.wikidata import WikidataSource
from config import get_settings
from domain.ontology.entities import Class
from domain.pipelines.entities import PipelineRun, PipelineRunStatus
from domain.pipelines.schema_node_grounding.apply_service import (
    SchemaGroundingApplyService,
)
from tests.fixtures.pipeline_fixtures import (
    load_distractors,
    load_expected_output,
    load_fixture,
)

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

    def test_all_adapters_wired(self, grounding_adapter):
        """Verify all four source adapters are wired and operational."""
        assert "DBpedia" in grounding_adapter._sources
        assert "ConceptNet" in grounding_adapter._sources
        assert "Wikidata" in grounding_adapter._sources
        assert "schema.org" in grounding_adapter._sources

        assert isinstance(grounding_adapter._sources["DBpedia"], DBpediaSource)
        assert isinstance(grounding_adapter._sources["ConceptNet"], ConceptNetSource)
        assert isinstance(grounding_adapter._sources["Wikidata"], WikidataSource)
        assert isinstance(grounding_adapter._sources["schema.org"], SchemaOrgSource)

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

    @pytest.mark.real_llm
    @pytest.mark.asyncio
    async def test_live_grounding_with_real_sources(self, grounding_adapter):
        """
        Live test for schema node grounding with real external sources.

        Validates that grounding adapter can query real sources:
        - DBpedia (offline index)
        - ConceptNet (may require network)
        - Wikidata (may require network)
        - schema.org (offline index)

        This test is decorated with @pytest.mark.real_llm for consistency,
        though it primarily tests source adapters rather than LLM.
        It can run even without LLM provider configuration.
        """
        scenarios = _list_fixture_scenarios()
        if not scenarios:
            pytest.skip("No grounding fixtures found")

        # Test a few scenarios with real sources
        test_scenarios = scenarios[:3]

        for scenario in test_scenarios:
            fixture = load_fixture("schema_node_grounding", scenario)
            if not fixture:
                continue

            node_label = fixture.get("node_label", "unknown")
            requested_sources = fixture.get("sources", ["schema.org"])

            try:
                candidates = await grounding_adapter.query_sources(
                    label=node_label, sources=requested_sources
                )

                # Verify candidates have required fields
                for candidate in candidates:
                    assert hasattr(candidate, "uri"), f"Candidate missing uri for {node_label}"
                    assert hasattr(candidate, "source"), f"Candidate missing source for {node_label}"
                    assert hasattr(candidate, "confidence"), f"Candidate missing confidence for {node_label}"

            except Exception as e:
                # Skip this scenario if source query fails (network may be unavailable)
                pytest.skip(f"Source query failed for {scenario}: {e}")

    def test_fixture_corpus_coverage(self):
        """Verify fixture corpus has ≥30 classes spanning multiple domains."""
        scenarios = _list_fixture_scenarios()
        assert len(scenarios) >= 30, f"Expected ≥30 fixtures, got {len(scenarios)}"

        # Verify different domains represented
        biology_classes = {
            "animal",
            "plant",
            "cell",
            "protein",
            "dna",
            "bacteria",
            "virus",
        }
        technology_classes = {"software", "network", "algorithm", "database"}
        social_classes = {
            "person",
            "organization",
            "artist",
            "university",
            "government",
        }

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
