"""
Integration tests for Reference Sources API routes.

Tests verify the HTTP endpoints for reference source operations:
- GET /api/reference/status — Check availability of reference sources
- POST /api/reference/search — Search references across sources
- POST /api/reference/relations — Get relationships for a reference URI

These tests use fake reference sources and verify:
- Concurrent asyncio.gather execution
- Source filtering by name
- Per-source failure tracking
- Proper error handling and graceful degradation
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from adapters.web.reference_routes import router
from tests.fakes.fake_reference_source import FakeReferenceSource


@pytest.fixture
def app():
    """Create a FastAPI app with reference routes."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def app_with_sources(app):
    """Create FastAPI app with mock reference sources."""
    # Create fake reference sources
    source1 = FakeReferenceSource(name="source-1")
    source2 = FakeReferenceSource(name="source-2")
    source3 = FakeReferenceSource(name="source-3-unavailable")
    source3.is_available = lambda: False  # type: ignore[method-assign]

    # Inject into app state
    app.state.reference_sources = [source1, source2, source3]

    return app


@pytest.fixture
def client_with_sources(app_with_sources):
    """Create test client with reference sources."""
    return TestClient(app_with_sources)


class TestReferenceStatusEndpoint:
    """Tests for GET /api/reference/status endpoint."""

    def test_reference_status_returns_all_sources(self, client_with_sources):
        """Status endpoint returns availability of all sources."""
        response = client_with_sources.get("/api/reference/status")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "sources" in data
        assert "sources_available" in data
        assert "timestamp" in data
        assert len(data["sources"]) == 3

    def test_reference_status_tracks_available_count(self, client_with_sources):
        """Status endpoint counts available sources correctly."""
        response = client_with_sources.get("/api/reference/status")

        data = response.json()
        # First two sources are available, third is not
        assert data["sources_available"] == 2

    def test_reference_status_includes_source_names(self, client_with_sources):
        """Status endpoint includes all source names."""
        response = client_with_sources.get("/api/reference/status")

        data = response.json()
        source_names = [s["name"] for s in data["sources"]]
        assert "source-1" in source_names
        assert "source-2" in source_names
        assert "source-3-unavailable" in source_names

    def test_reference_status_no_sources_configured(self, client):
        """Status endpoint returns 500 if no sources configured."""
        response = client.get("/api/reference/status")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "No reference sources configured" in data["detail"]


class TestReferenceSearchEndpoint:
    """Tests for POST /api/reference/search endpoint."""

    def test_reference_search_finds_results(self, client_with_sources):
        """Search endpoint returns results from all sources."""
        request_body = {"term": "apple", "limit": 10}
        response = client_with_sources.post("/api/reference/search", json=request_body)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "term" in data
        assert data["term"] == "apple"
        assert "results" in data
        assert len(data["results"]) > 0

    def test_reference_search_aggregates_results_from_multiple_sources(self, client_with_sources):
        """Search endpoint aggregates results from all available sources."""
        request_body = {"term": "test", "limit": 10}
        response = client_with_sources.post("/api/reference/search", json=request_body)

        data = response.json()
        # Should have results from at least the two available sources
        assert len(data["results"]) >= 2
        assert data["total_results"] == len(data["results"])

    def test_reference_search_tracks_searched_sources(self, client_with_sources):
        """Search endpoint tracks which sources were successfully searched."""
        request_body = {"term": "test", "limit": 10}
        response = client_with_sources.post("/api/reference/search", json=request_body)

        data = response.json()
        assert "sources_searched" in data
        assert "source-1" in data["sources_searched"]
        assert "source-2" in data["sources_searched"]

    def test_reference_search_tracks_failed_sources(self, client_with_sources):
        """Search endpoint tracks which sources failed or were unavailable."""
        request_body = {"term": "test", "limit": 10}
        response = client_with_sources.post("/api/reference/search", json=request_body)

        data = response.json()
        assert "sources_failed" in data
        assert "source-3-unavailable" in data["sources_failed"]

    def test_reference_search_filters_by_source_names(self, client_with_sources):
        """Search endpoint respects source filter in request."""
        request_body = {"term": "test", "limit": 10, "sources": ["source-1"]}
        response = client_with_sources.post("/api/reference/search", json=request_body)

        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert "source-1" in data["sources_searched"]
        # Should not search other sources
        assert "source-2" not in data["sources_searched"]

    def test_reference_search_invalid_source_name_returns_400(self, client_with_sources):
        """Search endpoint returns 400 if requested sources don't exist."""
        request_body = {
            "term": "test",
            "limit": 10,
            "sources": ["nonexistent-source"],
        }
        response = client_with_sources.post("/api/reference/search", json=request_body)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "None of the requested sources are available" in data["detail"]

    def test_reference_search_no_sources_configured(self, client):
        """Search endpoint returns 500 if no sources configured."""
        request_body = {"term": "test", "limit": 10}
        response = client.post("/api/reference/search", json=request_body)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_reference_search_handles_source_failure_gracefully(
        self, app_with_sources
    ):
        """Search endpoint continues when a source fails."""
        # Make one source fail
        sources = app_with_sources.state.reference_sources
        sources[0].should_fail = True  # type: ignore[attr-defined]

        client = TestClient(app_with_sources)
        request_body = {"term": "test", "limit": 10}
        response = client.post("/api/reference/search", json=request_body)

        # Should still return 200 OK with results from working sources
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "source-1" in data["sources_failed"]
        assert "source-2" in data["sources_searched"]


class TestReferenceRelationsEndpoint:
    """Tests for POST /api/reference/relations endpoint."""

    def test_reference_relations_returns_relations(self, client_with_sources):
        """Relations endpoint returns relationships for a URI."""
        request_body = {"uri": "fake://apple", "limit": 10}
        response = client_with_sources.post("/api/reference/relations", json=request_body)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "uri" in data
        assert data["uri"] == "fake://apple"
        assert "relations" in data
        assert isinstance(data["relations"], list)

    def test_reference_relations_tracks_queried_sources(self, client_with_sources):
        """Relations endpoint tracks which sources were queried."""
        request_body = {"uri": "fake://test", "limit": 10}
        response = client_with_sources.post("/api/reference/relations", json=request_body)

        data = response.json()
        assert "sources_queried" in data
        assert "source-1" in data["sources_queried"]
        assert "source-2" in data["sources_queried"]

    def test_reference_relations_tracks_failed_sources(self, client_with_sources):
        """Relations endpoint tracks which sources failed or were unavailable."""
        request_body = {"uri": "fake://test", "limit": 10}
        response = client_with_sources.post("/api/reference/relations", json=request_body)

        data = response.json()
        assert "sources_failed" in data
        assert "source-3-unavailable" in data["sources_failed"]

    def test_reference_relations_filters_by_source_names(self, client_with_sources):
        """Relations endpoint respects source filter in request."""
        request_body = {"uri": "fake://test", "limit": 10, "sources": ["source-1"]}
        response = client_with_sources.post("/api/reference/relations", json=request_body)

        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert "source-1" in data["sources_queried"]
        assert "source-2" not in data["sources_queried"]

    def test_reference_relations_invalid_source_name_returns_400(self, client_with_sources):
        """Relations endpoint returns 400 if requested sources don't exist."""
        request_body = {
            "uri": "fake://test",
            "limit": 10,
            "sources": ["nonexistent-source"],
        }
        response = client_with_sources.post("/api/reference/relations", json=request_body)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_reference_relations_no_sources_configured(self, client):
        """Relations endpoint returns 500 if no sources configured."""
        request_body = {"uri": "fake://test", "limit": 10}
        response = client.post("/api/reference/relations", json=request_body)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_reference_relations_handles_source_failure_gracefully(self, app_with_sources):
        """Relations endpoint continues when a source fails."""
        # Make one source fail
        sources = app_with_sources.state.reference_sources
        sources[0].should_fail = True  # type: ignore[attr-defined]

        client = TestClient(app_with_sources)
        request_body = {"uri": "fake://test", "limit": 10}
        response = client.post("/api/reference/relations", json=request_body)

        # Should still return 200 OK with results from working sources
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "source-1" in data["sources_failed"]
        assert "source-2" in data["sources_queried"]
