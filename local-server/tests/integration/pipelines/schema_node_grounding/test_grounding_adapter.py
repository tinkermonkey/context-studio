"""Tests for grounding adapter."""

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.reference.grounding import GroundingAdapter
from domain.extraction.ports import ReferenceResult
from domain.pipelines.exceptions import PipelineExternalServiceError, PipelineInputError
from domain.pipelines.schema_node_grounding.scoring import GroundingCandidate

_test_file = os.path.abspath(__file__)
_test_dir = os.path.dirname(_test_file)
_root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_test_dir))))
sys.path.insert(0, _root_dir)


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
        """Test with unknown source name raises PipelineInputError."""
        adapter = GroundingAdapter(dbpedia=mock_dbpedia, conceptnet=mock_conceptnet)

        with pytest.raises(PipelineInputError) as exc_info:
            await adapter.query_sources(
                label="person",
                sources=["UnknownSource"],
            )

        assert "Unknown grounding sources" in str(exc_info.value)
        assert "UnknownSource" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_query_sources_single_source_exception(self, mock_dbpedia, mock_conceptnet):
        """Test exception handling when one source query fails."""
        mock_dbpedia.search_async = AsyncMock(side_effect=Exception("DBpedia error"))
        adapter = GroundingAdapter(dbpedia=mock_dbpedia, conceptnet=mock_conceptnet)

        candidates = await adapter.query_sources(
            label="person",
            sources=["DBpedia", "ConceptNet"],
        )

        # ConceptNet should succeed even though DBpedia failed
        assert len(candidates) == 1
        assert candidates[0].source == "ConceptNet"

    @pytest.mark.asyncio
    async def test_query_sources_all_sources_fail(self, mock_dbpedia, mock_conceptnet):
        """Test exception raised when all sources fail."""
        mock_dbpedia.search_async = AsyncMock(side_effect=Exception("DBpedia error"))
        mock_conceptnet.search_async = AsyncMock(side_effect=Exception("ConceptNet error"))
        adapter = GroundingAdapter(dbpedia=mock_dbpedia, conceptnet=mock_conceptnet)

        with pytest.raises(PipelineExternalServiceError) as exc_info:
            await adapter.query_sources(
                label="person",
                sources=["DBpedia", "ConceptNet"],
            )

        assert "All grounding sources failed" in str(exc_info.value)
