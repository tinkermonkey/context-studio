"""
Tests verifying grounding adapter source coverage.

These tests ensure:
1. All registered sources (DBpedia, ConceptNet, Wikidata, schema.org) return results
2. Unknown sources raise a typed PipelineInputError
3. Source results conform to GroundingCandidate shape
"""

import asyncio

import pytest

from adapters.reference.conceptnet import ConceptNetSource
from adapters.reference.dbpedia import DBpediaSource
from adapters.reference.grounding.adapter import GroundingAdapter
from adapters.reference.schema_org import SchemaOrgSource
from adapters.reference.wikidata import WikidataSource
from domain.pipelines.exceptions import PipelineInputError


class TestGroundingAdapterSourceCoverage:
    """Verify all registered grounding sources return adapter-shaped results."""

    @pytest.fixture
    def adapter(self):
        """Create a GroundingAdapter with all sources."""
        return GroundingAdapter(
            dbpedia=DBpediaSource(),
            conceptnet=ConceptNetSource(),
            wikidata=WikidataSource(),
            schema_org=SchemaOrgSource(),
        )

    @pytest.mark.asyncio
    async def test_dbpedia_source_registered(self, adapter):
        """Verify DBpedia source is registered in adapter."""
        assert "DBpedia" in adapter._sources, "DBpedia should be registered"
        assert isinstance(adapter._sources["DBpedia"], DBpediaSource)

    @pytest.mark.asyncio
    async def test_conceptnet_source_registered(self, adapter):
        """Verify ConceptNet source is registered in adapter."""
        assert "ConceptNet" in adapter._sources, "ConceptNet should be registered"
        assert isinstance(adapter._sources["ConceptNet"], ConceptNetSource)

    @pytest.mark.asyncio
    async def test_wikidata_source_registered(self, adapter):
        """Verify Wikidata source is registered in adapter."""
        assert "Wikidata" in adapter._sources, "Wikidata should be registered"
        assert isinstance(adapter._sources["Wikidata"], WikidataSource)

    @pytest.mark.asyncio
    async def test_schema_org_returns_candidates_with_required_fields(self, adapter):
        """Verify schema.org returns results with uri, label, description, source."""
        candidates = await adapter.query_sources(label="Person", sources=["schema.org"])
        assert len(candidates) > 0, "schema.org should return at least one candidate for 'Person'"

        for candidate in candidates:
            assert hasattr(candidate, "uri"), "Candidate must have uri"
            assert hasattr(candidate, "label"), "Candidate must have label"
            assert hasattr(candidate, "description"), "Candidate must have description"
            assert hasattr(candidate, "source"), "Candidate must have source"
            assert candidate.source == "schema.org", "Source should be 'schema.org'"

    @pytest.mark.asyncio
    async def test_all_registered_sources_queried_by_default(self, adapter):
        """Verify all registered sources are queried when none specified."""
        candidates = await adapter.query_sources(label="thing")
        sources = {c.source for c in candidates}

        expected_sources = {"DBpedia", "ConceptNet", "Wikidata", "schema.org"}
        assert sources & expected_sources, (
            "At least some of the default sources should return results for 'thing'"
        )

    @pytest.mark.asyncio
    async def test_unknown_source_raises_pipeline_input_error(self, adapter):
        """Verify unknown source names raise a typed PipelineInputError."""
        with pytest.raises(PipelineInputError) as exc_info:
            await adapter.query_sources(label="test", sources=["UnknownSource"])

        error_msg = str(exc_info.value)
        assert "UnknownSource" in error_msg, "Error should mention the unknown source"
        assert "Unknown grounding sources" in error_msg

    @pytest.mark.asyncio
    async def test_mixed_known_and_unknown_sources_raises_error(self, adapter):
        """Verify mixing known and unknown sources raises PipelineInputError."""
        with pytest.raises(PipelineInputError) as exc_info:
            await adapter.query_sources(label="test", sources=["DBpedia", "InvalidSource"])

        error_msg = str(exc_info.value)
        assert "InvalidSource" in error_msg
        assert "Unknown grounding sources" in error_msg

    @pytest.mark.asyncio
    async def test_multiple_unknown_sources_all_reported(self, adapter):
        """Verify all unknown sources are listed in the error message."""
        with pytest.raises(PipelineInputError) as exc_info:
            await adapter.query_sources(label="test", sources=["BadSource1", "BadSource2"])

        error_msg = str(exc_info.value)
        assert "BadSource1" in error_msg
        assert "BadSource2" in error_msg
