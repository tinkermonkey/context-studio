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

import asyncio
import time

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from adapters.web import reference_routes
from adapters.web.dependencies import get_reference_sources
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
    source3 = FakeReferenceSource(name="source-3-down", should_fail=True)
    source3.is_available = lambda: False  # type: ignore[method-assign]

    # Inject into app state
    app.state.reference_sources = [source1, source2, source3]

    return app


@pytest.fixture
def client_with_sources(app_with_sources):
    """Create test client with reference sources."""
    return TestClient(app_with_sources)


def _hanging_source(name: str) -> FakeReferenceSource:
    """A source whose search and relations calls never answer."""
    source = FakeReferenceSource(name=name)

    async def never_answers(*args, **kwargs):
        await asyncio.sleep(5)
        return []

    source.search_async = never_answers  # type: ignore[method-assign]
    source.get_relations_async = never_answers  # type: ignore[method-assign]
    return source


def _no_availability_checks(sources: list[FakeReferenceSource]) -> None:
    """Make any availability check fail the test."""

    async def must_not_be_called() -> bool:
        raise AssertionError("availability was checked")

    for source in sources:
        source.is_available_async = must_not_be_called  # type: ignore[method-assign]


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
        assert "source-3-down" in source_names

    def test_reference_status_no_sources_configured(self):
        """Status endpoint returns 500 if no sources configured."""
        # Create app without sources, override dependency to return empty list
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_reference_sources] = lambda: []

        client = TestClient(app)
        response = client.get("/api/reference/status")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "No reference sources configured" in data["detail"]

        # Clean up dependency override
        app.dependency_overrides.clear()

    def test_reference_status_reports_a_slow_source_unavailable(self, app, monkeypatch):
        """A source that doesn't answer in time is unavailable; it doesn't hold the response."""
        monkeypatch.setattr(reference_routes, "STATUS_CHECK_TIMEOUT_SECONDS", 0.05)
        slow = FakeReferenceSource(name="slow")

        async def never_answers() -> bool:
            await asyncio.sleep(5)
            return True

        slow.is_available_async = never_answers  # type: ignore[method-assign]
        app.state.reference_sources = [FakeReferenceSource(name="fast"), slow]

        started = time.monotonic()
        response = TestClient(app).get("/api/reference/status")

        assert time.monotonic() - started < 2
        assert response.status_code == status.HTTP_200_OK
        by_name = {s["name"]: s["available"] for s in response.json()["sources"]}
        assert by_name == {"fast": True, "slow": False}


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
        assert "source-3-down" in data["sources_failed"]

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

    def test_reference_search_no_sources_configured(self):
        """Search endpoint returns 500 if no sources configured."""
        # Create app without sources, override dependency to return empty list
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_reference_sources] = lambda: []

        client = TestClient(app)
        request_body = {"term": "test", "limit": 10}
        response = client.post("/api/reference/search", json=request_body)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        # Clean up dependency override
        app.dependency_overrides.clear()

    def test_reference_search_handles_source_failure_gracefully(self, app_with_sources):
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

    def test_reference_search_does_not_check_availability(self, app):
        """Search goes straight to each source; it never probes the upstream first (#1506)."""
        sources = [FakeReferenceSource(name="source-1"), FakeReferenceSource(name="source-2")]
        _no_availability_checks(sources)
        app.state.reference_sources = sources

        response = TestClient(app).post("/api/reference/search", json={"term": "water"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["sources_searched"] == ["source-1", "source-2"]
        assert data["sources_failed"] == []
        assert data["total_results"] == 2

    def test_reference_search_does_not_wait_on_a_hanging_source(self, app, monkeypatch):
        """A source that never answers is listed as failed; the others' results return (#1506)."""
        monkeypatch.setattr(reference_routes, "SOURCE_QUERY_TIMEOUT_SECONDS", 0.05)
        app.state.reference_sources = [FakeReferenceSource(name="fast"), _hanging_source("hung")]

        started = time.monotonic()
        response = TestClient(app).post("/api/reference/search", json={"term": "water"})

        assert time.monotonic() - started < 2
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["sources_searched"] == ["fast"]
        assert data["sources_failed"] == ["hung"]
        assert [r["source"] for r in data["results"]] == ["fast"]


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
        assert "source-3-down" in data["sources_failed"]

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

    def test_reference_relations_no_sources_configured(self):
        """Relations endpoint returns 500 if no sources configured."""
        # Create app without sources, override dependency to return empty list
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_reference_sources] = lambda: []

        client = TestClient(app)
        request_body = {"uri": "fake://test", "limit": 10}
        response = client.post("/api/reference/relations", json=request_body)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        # Clean up dependency override
        app.dependency_overrides.clear()

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

    def test_reference_relations_does_not_check_availability(self, app):
        """Relations go straight to each source; nothing probes the upstream first (#1506)."""
        sources = [FakeReferenceSource(name="source-1"), FakeReferenceSource(name="source-2")]
        _no_availability_checks(sources)
        app.state.reference_sources = sources

        response = TestClient(app).post("/api/reference/relations", json={"uri": "fake://water"})

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["sources_queried"] == ["source-1", "source-2"]

    def test_reference_relations_do_not_wait_on_a_hanging_source(self, app, monkeypatch):
        """A source that never answers is listed as failed and doesn't hold the response."""
        monkeypatch.setattr(reference_routes, "SOURCE_QUERY_TIMEOUT_SECONDS", 0.05)
        app.state.reference_sources = [FakeReferenceSource(name="fast"), _hanging_source("hung")]

        started = time.monotonic()
        response = TestClient(app).post("/api/reference/relations", json={"uri": "fake://water"})

        assert time.monotonic() - started < 2
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["sources_queried"] == ["fast"]
        assert data["sources_failed"] == ["hung"]
