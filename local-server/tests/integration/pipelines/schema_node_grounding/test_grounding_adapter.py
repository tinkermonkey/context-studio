"""Tests for grounding adapter."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import pytest
from unittest.mock import AsyncMock, MagicMock

from adapters.reference.grounding import GroundingAdapter
from domain.extraction.ports import ReferenceResult
from domain.pipelines.schema_node_grounding.scoring import GroundingCandidate, NodeType


class TestGroundingAdapter:
    """Tests for GroundingAdapter."""

    @pytest.fixture
    def mock_dbpedia(self):
        """Create mock DBpedia source."""
        mock = MagicMock()
        mock.search_async = AsyncMock(
            return_value=[
                ReferenceResult(
                    uri="http://dbpedia.org/resource/Person",
                    label="Person",
                    description="A human being",
                    source="DBpedia",
                ),
                ReferenceResult(
                    uri="http://dbpedia.org/resource/Individual",
                    label="Individual",
                    description="A single thing or entity",
                    source="DBpedia",
                ),
            ]
        )
        return mock

    @pytest.fixture
    def mock_conceptnet(self):
        """Create mock ConceptNet source."""
        mock = MagicMock()
        mock.search_async = AsyncMock(
            return_value=[
                ReferenceResult(
                    uri="http://conceptnet.io/c/en/person",
                    label="person",
                    description="a human being",
                    source="ConceptNet",
                ),
            ]
        )
        return mock

    @pytest.mark.asyncio
    async def test_query_sources_with_both_sources(self, mock_dbpedia, mock_conceptnet):
        """Test querying both DBpedia and ConceptNet."""
        adapter = GroundingAdapter(dbpedia=mock_dbpedia, conceptnet=mock_conceptnet)

        candidates = await adapter.query_sources(
            label="person",
            sources=["DBpedia", "ConceptNet"],
        )

        assert len(candidates) == 3
        assert all(isinstance(c, GroundingCandidate) for c in candidates)
        assert candidates[0].source in ["DBpedia", "ConceptNet"]

    @pytest.mark.asyncio
    async def test_query_sources_dbpedia_only(self, mock_dbpedia, mock_conceptnet):
        """Test querying only DBpedia."""
        adapter = GroundingAdapter(dbpedia=mock_dbpedia, conceptnet=mock_conceptnet)

        candidates = await adapter.query_sources(
            label="person",
            sources=["DBpedia"],
        )

        assert len(candidates) == 2
        assert all(c.source == "DBpedia" for c in candidates)

    @pytest.mark.asyncio
    async def test_query_sources_empty_label(self, mock_dbpedia, mock_conceptnet):
        """Test with empty label returns empty list."""
        adapter = GroundingAdapter(dbpedia=mock_dbpedia, conceptnet=mock_conceptnet)

        candidates = await adapter.query_sources(label="", sources=["DBpedia"])

        assert candidates == []

    @pytest.mark.asyncio
    async def test_query_sources_unknown_source(self, mock_dbpedia, mock_conceptnet):
        """Test with unknown source name."""
        adapter = GroundingAdapter(dbpedia=mock_dbpedia, conceptnet=mock_conceptnet)

        candidates = await adapter.query_sources(
            label="person",
            sources=["UnknownSource"],
        )

        assert candidates == []

    @pytest.mark.asyncio
    async def test_query_sources_source_exception(self, mock_dbpedia, mock_conceptnet):
        """Test exception handling when source query fails."""
        mock_dbpedia.search_async = AsyncMock(side_effect=Exception("DBpedia error"))
        adapter = GroundingAdapter(dbpedia=mock_dbpedia, conceptnet=mock_conceptnet)

        candidates = await adapter.query_sources(
            label="person",
            sources=["DBpedia", "ConceptNet"],
        )

        # ConceptNet should succeed even though DBpedia failed
        assert len(candidates) == 1
        assert candidates[0].source == "ConceptNet"
