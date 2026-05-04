"""
Integration tests for Data Interchange API routes.

Tests verify the HTTP endpoints for import/export operations:
- POST /api/v1/interchange/export — Export ontology data in various formats
- POST /api/v1/interchange/import — Import ontology data with conflict detection
- GET /api/v1/interchange/runs — List import runs with filtering and pagination
- GET /api/v1/interchange/runs/{run_id} — Get specific import run details
- GET /api/v1/interchange/runs/{run_id}/change-events — Get change events for a run

These tests exercise the complete stack: routes → domain service → adapters.
Focus areas:
- Multipart form parsing for import endpoint
- dry_run string-to-bool conversion (line 268 in routes)
- Query parameter validation (offset, limit, status filters)
- StreamingResponse behavior for export
- 404 handling for non-existent resources
"""

import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
)

import pytest
import json
from io import BytesIO
from datetime import datetime
from uuid import uuid4

from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from domain.interchange.entities import ImportRun, ImportRunStatus
from domain.interchange.value_objects import (
    SerializationScope,
    SerializationScopeType,
    SerializationFormat,
    ImportPlan,
)
from adapters.web.interchange_routes import router
from tests.fakes.fake_interchange_repository import FakeInterchangeRepository
from tests.fakes.fake_ontology_repository import FakeOntologyRepository


class FakeSerializer:
    """Fake serializer that returns minimal valid data."""

    def serialize(self, scope: SerializationScope) -> bytes:
        """Return dummy serialized data."""
        return b"<rdf:RDF>test export data</rdf:RDF>"


class FakeDeserializer:
    """Fake deserializer that returns an ImportPlan."""

    def __init__(self, interchange_repo, format: SerializationFormat | None = None):
        """Initialize with repository and format."""
        self.interchange_repo = interchange_repo
        self.format = format or SerializationFormat.SKOS

    def deserialize(
        self, source: bytes, dry_run: bool = True, resolutions: list | None = None
    ):
        """Return a minimal ImportPlan."""
        plan = ImportPlan(
            conflicts=(),
            new_entity_count=0,
            import_run_id=str(uuid4()) if not dry_run else None,
            warnings=(),
            source_hash="abc123",
            scope=SerializationScope(
                scope_type=SerializationScopeType.WHOLE_GRAPH,
            ),
        )

        # For non-dry-run, create and store an ImportRun
        if not dry_run:
            import_run = ImportRun(
                id=plan.import_run_id or str(uuid4()),
                created_at=datetime.now(),
                created_by=None,
                format=self.format,
                source_uri="test.skos",
                source_hash="abc123",
                scope=plan.scope or SerializationScope(
                    scope_type=SerializationScopeType.WHOLE_GRAPH,
                ),
                resolutions=[],
                affected_entity_ids=[],
                status=ImportRunStatus.COMMITTED,
            )
            self.interchange_repo.create(import_run)

        return plan


@pytest.fixture
def ontology_repo():
    """Create a fake ontology repository."""
    return FakeOntologyRepository()


@pytest.fixture
def interchange_repo():
    """Create a fake interchange repository."""
    return FakeInterchangeRepository()


@pytest.fixture
def app(ontology_repo, interchange_repo):
    """Create a FastAPI app with interchange routes."""
    app = FastAPI()
    app.include_router(router)
    app.state.ontology_repo = ontology_repo
    app.state.interchange_repo = interchange_repo
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


class TestExportEndpoint:
    """Tests for POST /api/v1/interchange/export endpoint."""

    def test_export_returns_200_with_valid_request(self, client, monkeypatch):
        """Export endpoint returns 200 with valid request."""
        # Mock serializer
        monkeypatch.setattr(
            "adapters.web.interchange_routes._get_serializer",
            lambda fmt, repo, split_mode=False: FakeSerializer(),
        )

        request_body = {
            "format": "skos",
            "scope": {
                "scope_type": "whole_graph",
            },
        }
        response = client.post("/api/v1/interchange/export", json=request_body)

        assert response.status_code == status.HTTP_200_OK

    def test_export_returns_binary_data(self, client, monkeypatch):
        """Export endpoint returns binary data with correct media type."""
        monkeypatch.setattr(
            "adapters.web.interchange_routes._get_serializer",
            lambda fmt, repo, split_mode=False: FakeSerializer(),
        )

        request_body = {
            "format": "owl",
            "scope": {
                "scope_type": "whole_graph",
            },
        }
        response = client.post("/api/v1/interchange/export", json=request_body)

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "application/octet-stream"
        assert b"<rdf:RDF>" in response.content

    def test_export_sets_content_disposition_header(self, client, monkeypatch):
        """Export endpoint sets proper Content-Disposition header."""
        monkeypatch.setattr(
            "adapters.web.interchange_routes._get_serializer",
            lambda fmt, repo, split_mode=False: FakeSerializer(),
        )

        request_body = {
            "format": "graphml",
            "scope": {
                "scope_type": "whole_graph",
            },
        }
        response = client.post("/api/v1/interchange/export", json=request_body)

        assert "Content-Disposition" in response.headers
        assert "attachment" in response.headers["Content-Disposition"]
        assert "graphml" in response.headers["Content-Disposition"]

    def test_export_rejects_invalid_format(self, client):
        """Export endpoint returns 422 for unsupported format (Pydantic validation)."""
        request_body = {
            "format": "invalid_format",
            "scope": {
                "scope_type": "whole_graph",
            },
        }
        response = client.post("/api/v1/interchange/export", json=request_body)

        # Pydantic validates Literal types at schema level, returning 422
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_export_accepts_taxonomy_scope(self, client, monkeypatch):
        """Export endpoint accepts taxonomy scope."""
        monkeypatch.setattr(
            "adapters.web.interchange_routes._get_serializer",
            lambda fmt, repo, split_mode=False: FakeSerializer(),
        )

        taxonomy_id = str(uuid4())
        request_body = {
            "format": "skos",
            "scope": {
                "scope_type": "taxonomy",
                "taxonomy_id": taxonomy_id,
            },
        }
        response = client.post("/api/v1/interchange/export", json=request_body)

        assert response.status_code == status.HTTP_200_OK

    def test_export_accepts_scheme_scope(self, client, monkeypatch):
        """Export endpoint accepts concept scheme scope."""
        monkeypatch.setattr(
            "adapters.web.interchange_routes._get_serializer",
            lambda fmt, repo, split_mode=False: FakeSerializer(),
        )

        scheme_id = str(uuid4())
        request_body = {
            "format": "owl",
            "scope": {
                "scope_type": "scheme",
                "scheme_id": scheme_id,
                "include_descendants": True,
            },
        }
        response = client.post("/api/v1/interchange/export", json=request_body)

        assert response.status_code == status.HTTP_200_OK

    def test_export_accepts_entity_set_scope(self, client, monkeypatch):
        """Export endpoint accepts entity set scope."""
        monkeypatch.setattr(
            "adapters.web.interchange_routes._get_serializer",
            lambda fmt, repo, split_mode=False: FakeSerializer(),
        )

        entity_ids = [str(uuid4()), str(uuid4())]
        request_body = {
            "format": "graphml",
            "scope": {
                "scope_type": "entity_set",
                "entity_ids": entity_ids,
            },
        }
        response = client.post("/api/v1/interchange/export", json=request_body)

        assert response.status_code == status.HTTP_200_OK

    def test_export_with_split_mode_true(self, client, monkeypatch):
        """Export endpoint passes split_mode=True to serializer for OWL format."""
        split_mode_received = []

        def capture_serializer(fmt, repo, split_mode=False):
            split_mode_received.append(split_mode)
            return FakeSerializer()

        monkeypatch.setattr(
            "adapters.web.interchange_routes._get_serializer",
            capture_serializer,
        )

        request_body = {
            "format": "owl",
            "scope": {
                "scope_type": "whole_graph",
            },
            "split_mode": True,
        }
        response = client.post("/api/v1/interchange/export", json=request_body)

        assert response.status_code == status.HTTP_200_OK
        assert len(split_mode_received) == 1
        assert split_mode_received[0] is True

    def test_export_with_split_mode_false(self, client, monkeypatch):
        """Export endpoint passes split_mode=False to serializer by default."""
        split_mode_received = []

        def capture_serializer(fmt, repo, split_mode=False):
            split_mode_received.append(split_mode)
            return FakeSerializer()

        monkeypatch.setattr(
            "adapters.web.interchange_routes._get_serializer",
            capture_serializer,
        )

        request_body = {
            "format": "owl",
            "scope": {
                "scope_type": "whole_graph",
            },
        }
        response = client.post("/api/v1/interchange/export", json=request_body)

        assert response.status_code == status.HTTP_200_OK
        assert len(split_mode_received) == 1
        assert split_mode_received[0] is False


class TestImportEndpoint:
    """Tests for POST /api/v1/interchange/import endpoint."""

    def test_import_multipart_form_parsing(self, client, monkeypatch):
        """Import endpoint correctly parses multipart form data."""
        monkeypatch.setattr(
            "adapters.web.interchange_routes._get_deserializer",
            lambda fmt, onto_repo, int_repo: FakeDeserializer(client.app.state.interchange_repo),
        )

        file_content = b"<rdf:RDF>test data</rdf:RDF>"
        response = client.post(
            "/api/v1/interchange/import",
            data={
                "format": "skos",
                "dry_run": "true",
            },
            files={"file": ("test.skos", BytesIO(file_content), "application/xml")},
        )

        assert response.status_code == status.HTTP_200_OK

    def test_import_dry_run_true_returns_import_plan(self, client, monkeypatch):
        """Import with dry_run=true returns ImportPlanResponse."""
        monkeypatch.setattr(
            "adapters.web.interchange_routes._get_deserializer",
            lambda fmt, onto_repo, int_repo: FakeDeserializer(client.app.state.interchange_repo),
        )

        file_content = b"<rdf:RDF>test data</rdf:RDF>"
        response = client.post(
            "/api/v1/interchange/import",
            data={
                "format": "skos",
                "dry_run": "true",
            },
            files={"file": ("test.skos", BytesIO(file_content), "application/xml")},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "conflicts" in data
        assert "new_entity_count" in data
        assert "warnings" in data
        assert "source_hash" in data

    def test_import_dry_run_false_returns_import_run(self, client, monkeypatch):
        """Import with dry_run=false returns ImportRunResponse."""
        def get_deserializer(fmt, onto_repo, int_repo):
            return FakeDeserializer(int_repo, format=fmt)

        monkeypatch.setattr(
            "adapters.web.interchange_routes._get_deserializer",
            get_deserializer,
        )

        file_content = b"<rdf:RDF>test data</rdf:RDF>"
        response = client.post(
            "/api/v1/interchange/import",
            data={
                "format": "owl",
                "dry_run": "false",
            },
            files={"file": ("test.owl", BytesIO(file_content), "application/xml")},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "id" in data
        assert "created_at" in data
        assert "format" in data
        assert data["format"] == "owl"
        assert "status" in data
        assert data["status"] == "committed"

    def test_import_dry_run_string_to_bool_conversion(self, client, monkeypatch):
        """Import endpoint converts dry_run string 'true' to boolean correctly."""
        monkeypatch.setattr(
            "adapters.web.interchange_routes._get_deserializer",
            lambda fmt, onto_repo, int_repo: FakeDeserializer(client.app.state.interchange_repo),
        )

        file_content = b"test data"

        # Test with "true"
        response = client.post(
            "/api/v1/interchange/import",
            data={"format": "skos", "dry_run": "true"},
            files={"file": ("test.skos", BytesIO(file_content))},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # ImportPlanResponse should not have import_run_id when dry_run=true
        assert data.get("import_run_id") is None

    def test_import_dry_run_false_string(self, client, monkeypatch):
        """Import endpoint handles dry_run='false' correctly."""
        monkeypatch.setattr(
            "adapters.web.interchange_routes._get_deserializer",
            lambda fmt, onto_repo, int_repo: FakeDeserializer(client.app.state.interchange_repo),
        )

        file_content = b"test data"
        response = client.post(
            "/api/v1/interchange/import",
            data={"format": "skos", "dry_run": "false"},
            files={"file": ("test.skos", BytesIO(file_content))},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # ImportRunResponse should have id and status
        assert "id" in data
        assert "status" in data

    def test_import_default_dry_run_is_true(self, client, monkeypatch):
        """Import endpoint defaults dry_run to true when not provided."""
        monkeypatch.setattr(
            "adapters.web.interchange_routes._get_deserializer",
            lambda fmt, onto_repo, int_repo: FakeDeserializer(client.app.state.interchange_repo),
        )

        file_content = b"test data"
        response = client.post(
            "/api/v1/interchange/import",
            data={"format": "skos"},  # No dry_run specified
            files={"file": ("test.skos", BytesIO(file_content))},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Default dry_run=true, so no import_run_id
        assert data.get("import_run_id") is None

    def test_import_rejects_invalid_format(self, client):
        """Import endpoint returns 400 for unsupported format."""
        file_content = b"test data"
        response = client.post(
            "/api/v1/interchange/import",
            data={"format": "invalid_format"},
            files={"file": ("test.xyz", BytesIO(file_content))},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "Unsupported format" in data["detail"]

    def test_import_rejects_missing_file(self, client):
        """Import endpoint returns 422 when file is missing."""
        response = client.post(
            "/api/v1/interchange/import",
            data={"format": "skos"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_import_rejects_missing_format(self, client):
        """Import endpoint returns 422 when format is missing."""
        file_content = b"test data"
        response = client.post(
            "/api/v1/interchange/import",
            files={"file": ("test.skos", BytesIO(file_content))},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_import_accepts_resolutions_json(self, client, monkeypatch):
        """Import endpoint parses resolutions JSON parameter correctly."""
        monkeypatch.setattr(
            "adapters.web.interchange_routes._get_deserializer",
            lambda fmt, onto_repo, int_repo: FakeDeserializer(client.app.state.interchange_repo),
        )

        file_content = b"test data"
        resolutions = json.dumps([])

        response = client.post(
            "/api/v1/interchange/import",
            data={
                "format": "skos",
                "dry_run": "false",
                "resolutions": resolutions,
            },
            files={"file": ("test.skos", BytesIO(file_content))},
        )

        assert response.status_code == status.HTTP_200_OK

    def test_import_rejects_malformed_resolutions_json(self, client):
        """Import endpoint returns 400 for malformed resolutions JSON."""
        file_content = b"test data"
        response = client.post(
            "/api/v1/interchange/import",
            data={
                "format": "skos",
                "resolutions": "not valid json {",
            },
            files={"file": ("test.skos", BytesIO(file_content))},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "Invalid resolutions JSON" in data["detail"]

    def test_import_accepts_all_formats(self, client, monkeypatch):
        """Import endpoint accepts all supported formats."""
        monkeypatch.setattr(
            "adapters.web.interchange_routes._get_deserializer",
            lambda fmt, onto_repo, int_repo: FakeDeserializer(client.app.state.interchange_repo),
        )

        file_content = b"test data"

        for format_name in ["skos", "owl", "graphml"]:
            response = client.post(
                "/api/v1/interchange/import",
                data={"format": format_name, "dry_run": "true"},
                files={"file": (f"test.{format_name}", BytesIO(file_content))},
            )
            assert response.status_code == status.HTTP_200_OK

    def test_import_rejects_oversized_file(self, client, monkeypatch):
        """Import endpoint returns 413 Payload Too Large when file exceeds size limit."""
        monkeypatch.setattr(
            "adapters.web.interchange_routes._get_deserializer",
            lambda fmt, onto_repo, int_repo: FakeDeserializer(client.app.state.interchange_repo),
        )

        # Create a file larger than MAX_UPLOAD_SIZE (500 MB)
        # We'll use a custom UploadFile-like object that streams data
        oversized_content = b"x" * (600 * 1024 * 1024)  # 600 MB

        response = client.post(
            "/api/v1/interchange/import",
            data={"format": "skos", "dry_run": "true"},
            files={"file": ("oversized.skos", BytesIO(oversized_content))},
        )

        assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
        data = response.json()
        assert "exceeds maximum allowed size" in data["detail"]
        assert "500" in data["detail"]  # MB limit should be mentioned

    def test_import_accepts_file_at_size_limit(self, client, monkeypatch):
        """Import endpoint accepts files at the exact size limit."""
        monkeypatch.setattr(
            "adapters.web.interchange_routes._get_deserializer",
            lambda fmt, onto_repo, int_repo: FakeDeserializer(client.app.state.interchange_repo),
        )

        # Create a file at exactly the limit (500 MB)
        # This would be too large in real usage, so we'll use a smaller test version
        # by mocking MAX_UPLOAD_SIZE for this test
        import adapters.web.interchange_routes as routes_module
        original_max = routes_module.MAX_UPLOAD_SIZE

        try:
            # Set limit to 1 KB for testing
            routes_module.MAX_UPLOAD_SIZE = 1024

            file_content = b"x" * 1024  # Exactly at limit
            response = client.post(
                "/api/v1/interchange/import",
                data={"format": "skos", "dry_run": "true"},
                files={"file": ("at_limit.skos", BytesIO(file_content))},
            )

            assert response.status_code == status.HTTP_200_OK
        finally:
            # Restore original limit
            routes_module.MAX_UPLOAD_SIZE = original_max

    def test_import_rejects_file_just_over_limit(self, client, monkeypatch):
        """Import endpoint rejects files just over the size limit."""
        monkeypatch.setattr(
            "adapters.web.interchange_routes._get_deserializer",
            lambda fmt, onto_repo, int_repo: FakeDeserializer(client.app.state.interchange_repo),
        )

        # Mock MAX_UPLOAD_SIZE for testing
        import adapters.web.interchange_routes as routes_module
        original_max = routes_module.MAX_UPLOAD_SIZE

        try:
            # Set limit to 1 KB for testing
            routes_module.MAX_UPLOAD_SIZE = 1024

            file_content = b"x" * 1025  # One byte over limit
            response = client.post(
                "/api/v1/interchange/import",
                data={"format": "skos", "dry_run": "true"},
                files={"file": ("over_limit.skos", BytesIO(file_content))},
            )

            assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
        finally:
            # Restore original limit
            routes_module.MAX_UPLOAD_SIZE = original_max


class TestListImportRunsEndpoint:
    """Tests for GET /api/v1/interchange/runs endpoint."""

    def test_list_import_runs_returns_200(self, client, interchange_repo):
        """List endpoint returns 200 with valid request."""
        response = client.get("/api/v1/interchange/runs")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "offset" in data
        assert "limit" in data

    def test_list_import_runs_empty_list(self, client):
        """List endpoint returns empty list when no runs exist."""
        response = client.get("/api/v1/interchange/runs")

        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_import_runs_with_pagination(self, client, interchange_repo):
        """List endpoint supports pagination with offset and limit."""
        # Create multiple import runs
        for i in range(5):
            run = ImportRun(
                id=str(uuid4()),
                created_at=datetime.now(),
                created_by=None,
                format=SerializationFormat.SKOS,
                source_uri=f"test{i}.skos",
                source_hash=f"hash{i}",
                scope=SerializationScope(
                    scope_type=SerializationScopeType.WHOLE_GRAPH,
                ),
                status=ImportRunStatus.COMMITTED,
            )
            interchange_repo.create(run)

        response = client.get("/api/v1/interchange/runs?offset=1&limit=2")

        data = response.json()
        assert data["offset"] == 1
        assert data["limit"] == 2
        assert len(data["items"]) == 2
        assert data["total"] == 5

    def test_list_import_runs_default_pagination(self, client, interchange_repo):
        """List endpoint uses default offset=0 and limit=100."""
        # Create a run
        run = ImportRun(
            id=str(uuid4()),
            created_at=datetime.now(),
            created_by=None,
            format=SerializationFormat.SKOS,
            source_uri="test.skos",
            source_hash="hash",
            scope=SerializationScope(
                scope_type=SerializationScopeType.WHOLE_GRAPH,
            ),
            status=ImportRunStatus.COMMITTED,
        )
        interchange_repo.create(run)

        response = client.get("/api/v1/interchange/runs")

        data = response.json()
        assert data["offset"] == 0
        assert data["limit"] == 100

    def test_list_import_runs_filter_by_status(self, client, interchange_repo):
        """List endpoint filters by status parameter."""
        # Create runs with different statuses
        for run_status in [
            ImportRunStatus.COMMITTED,
            ImportRunStatus.COMMITTED,
            ImportRunStatus.FAILED,
        ]:
            run = ImportRun(
                id=str(uuid4()),
                created_at=datetime.now(),
                created_by=None,
                format=SerializationFormat.SKOS,
                source_uri="test.skos",
                source_hash="hash",
                scope=SerializationScope(
                    scope_type=SerializationScopeType.WHOLE_GRAPH,
                ),
                status=run_status,
            )
            interchange_repo.create(run)

        response = client.get("/api/v1/interchange/runs?status=committed")

        data = response.json()
        assert data["total"] == 2
        assert all(item["status"] == "committed" for item in data["items"])

    def test_list_import_runs_rejects_invalid_status(self, client):
        """List endpoint returns 400 for invalid status filter."""
        response = client.get("/api/v1/interchange/runs?status=invalid_status")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "Invalid status" in data["detail"]

    def test_list_import_runs_rejects_negative_offset(self, client):
        """List endpoint rejects negative offset."""
        response = client.get("/api/v1/interchange/runs?offset=-1")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_list_import_runs_rejects_zero_limit(self, client):
        """List endpoint rejects zero or negative limit."""
        response = client.get("/api/v1/interchange/runs?limit=0")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_list_import_runs_rejects_limit_over_500(self, client):
        """List endpoint rejects limit over 500."""
        response = client.get("/api/v1/interchange/runs?limit=501")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_list_import_runs_returns_import_run_structure(self, client, interchange_repo):
        """List endpoint returns proper ImportRunResponse structure."""
        run = ImportRun(
            id=str(uuid4()),
            created_at=datetime.now(),
            created_by="test_user",
            format=SerializationFormat.OWL,
            source_uri="test.owl",
            source_hash="abc123",
            scope=SerializationScope(
                scope_type=SerializationScopeType.TAXONOMY,
                taxonomy_id=str(uuid4()),
            ),
            status=ImportRunStatus.COMMITTED,
        )
        interchange_repo.create(run)

        response = client.get("/api/v1/interchange/runs")

        data = response.json()
        assert len(data["items"]) == 1
        item = data["items"][0]
        assert item["id"] == run.id
        assert item["format"] == "owl"
        assert item["status"] == "committed"
        assert item["created_by"] == "test_user"


class TestGetImportRunEndpoint:
    """Tests for GET /api/v1/interchange/runs/{run_id} endpoint."""

    def test_get_import_run_returns_200(self, client, interchange_repo):
        """Get endpoint returns 200 for existing run."""
        run = ImportRun(
            id=str(uuid4()),
            created_at=datetime.now(),
            created_by=None,
            format=SerializationFormat.SKOS,
            source_uri="test.skos",
            source_hash="hash",
            scope=SerializationScope(
                scope_type=SerializationScopeType.WHOLE_GRAPH,
            ),
            status=ImportRunStatus.COMMITTED,
        )
        interchange_repo.create(run)

        response = client.get(f"/api/v1/interchange/runs/{run.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == run.id

    def test_get_import_run_returns_404_for_nonexistent(self, client):
        """Get endpoint returns 404 for non-existent run."""
        nonexistent_id = str(uuid4())
        response = client.get(f"/api/v1/interchange/runs/{nonexistent_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_get_import_run_returns_correct_structure(self, client, interchange_repo):
        """Get endpoint returns correct ImportRunResponse structure."""
        scope = SerializationScope(
            scope_type=SerializationScopeType.SCHEME,
            scheme_id=str(uuid4()),
            include_descendants=True,
        )
        run = ImportRun(
            id=str(uuid4()),
            created_at=datetime.now(),
            created_by="test_user",
            format=SerializationFormat.GRAPHML,
            source_uri="test.graphml",
            source_hash="hash123",
            scope=scope,
            status=ImportRunStatus.FAILED,
        )
        interchange_repo.create(run)

        response = client.get(f"/api/v1/interchange/runs/{run.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == run.id
        assert data["format"] == "graphml"
        assert data["status"] == "failed"
        assert data["created_by"] == "test_user"
        assert data["scope"]["scope_type"] == "scheme"
        assert data["scope"]["scheme_id"] == scope.scheme_id
        assert data["scope"]["include_descendants"] is True


class TestGetChangeEventsEndpoint:
    """Tests for GET /api/v1/interchange/runs/{run_id}/change-events endpoint."""

    def test_get_change_events_returns_200(self, client, interchange_repo):
        """Change events endpoint returns 200 for existing run."""
        run = ImportRun(
            id=str(uuid4()),
            created_at=datetime.now(),
            created_by=None,
            format=SerializationFormat.SKOS,
            source_uri="test.skos",
            source_hash="hash",
            scope=SerializationScope(
                scope_type=SerializationScopeType.WHOLE_GRAPH,
            ),
            status=ImportRunStatus.COMMITTED,
        )
        interchange_repo.create(run)

        response = client.get(f"/api/v1/interchange/runs/{run.id}/change-events")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "offset" in data
        assert "limit" in data

    def test_get_change_events_returns_404_for_nonexistent_run(self, client):
        """Change events endpoint returns 404 for non-existent run."""
        nonexistent_id = str(uuid4())
        response = client.get(f"/api/v1/interchange/runs/{nonexistent_id}/change-events")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_get_change_events_with_no_events(self, client, interchange_repo):
        """Change events endpoint returns empty list when no events exist."""
        run = ImportRun(
            id=str(uuid4()),
            created_at=datetime.now(),
            created_by=None,
            format=SerializationFormat.SKOS,
            source_uri="test.skos",
            source_hash="hash",
            scope=SerializationScope(
                scope_type=SerializationScopeType.WHOLE_GRAPH,
            ),
            status=ImportRunStatus.COMMITTED,
        )
        interchange_repo.create(run)

        response = client.get(f"/api/v1/interchange/runs/{run.id}/change-events")

        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_get_change_events_with_events(self, client, interchange_repo):
        """Change events endpoint returns events for existing run."""
        run = ImportRun(
            id=str(uuid4()),
            created_at=datetime.now(),
            created_by=None,
            format=SerializationFormat.SKOS,
            source_uri="test.skos",
            source_hash="hash",
            scope=SerializationScope(
                scope_type=SerializationScopeType.WHOLE_GRAPH,
            ),
            status=ImportRunStatus.COMMITTED,
        )
        interchange_repo.create(run)

        # Add some change events
        interchange_repo.add_change_event(
            run.id,
            {
                "id": str(uuid4()),
                "timestamp": datetime.now(),
                "entity_id": str(uuid4()),
                "entity_type": "Class",
                "operation": "create",
                "new_state": {"title": "New Class"},
                "previous_state": None,
            },
        )
        interchange_repo.add_change_event(
            run.id,
            {
                "id": str(uuid4()),
                "timestamp": datetime.now(),
                "entity_id": str(uuid4()),
                "entity_type": "Taxonomy",
                "operation": "update",
                "new_state": {"description": "Updated"},
                "previous_state": {"description": "Old"},
            },
        )

        response = client.get(f"/api/v1/interchange/runs/{run.id}/change-events")

        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert data["items"][0]["entity_type"] == "Class"
        assert data["items"][1]["entity_type"] == "Taxonomy"

    def test_get_change_events_supports_pagination(self, client, interchange_repo):
        """Change events endpoint supports pagination."""
        run = ImportRun(
            id=str(uuid4()),
            created_at=datetime.now(),
            created_by=None,
            format=SerializationFormat.SKOS,
            source_uri="test.skos",
            source_hash="hash",
            scope=SerializationScope(
                scope_type=SerializationScopeType.WHOLE_GRAPH,
            ),
            status=ImportRunStatus.COMMITTED,
        )
        interchange_repo.create(run)

        # Add multiple events
        for i in range(5):
            interchange_repo.add_change_event(
                run.id,
                {
                    "id": str(uuid4()),
                    "timestamp": datetime.now(),
                    "entity_id": str(uuid4()),
                    "entity_type": "Class",
                    "operation": "create",
                    "new_state": None,
                    "previous_state": None,
                },
            )

        response = client.get(
            f"/api/v1/interchange/runs/{run.id}/change-events?offset=1&limit=2"
        )

        data = response.json()
        assert data["offset"] == 1
        assert data["limit"] == 2
        assert len(data["items"]) == 2
        assert data["total"] == 5

    def test_get_change_events_filter_by_entity_type(self, client, interchange_repo):
        """Change events endpoint filters by entity_type parameter."""
        run = ImportRun(
            id=str(uuid4()),
            created_at=datetime.now(),
            created_by=None,
            format=SerializationFormat.SKOS,
            source_uri="test.skos",
            source_hash="hash",
            scope=SerializationScope(
                scope_type=SerializationScopeType.WHOLE_GRAPH,
            ),
            status=ImportRunStatus.COMMITTED,
        )
        interchange_repo.create(run)

        # Add events of different types
        interchange_repo.add_change_event(
            run.id,
            {
                "id": str(uuid4()),
                "timestamp": datetime.now(),
                "entity_id": str(uuid4()),
                "entity_type": "Class",
                "operation": "create",
                "new_state": None,
                "previous_state": None,
            },
        )
        interchange_repo.add_change_event(
            run.id,
            {
                "id": str(uuid4()),
                "timestamp": datetime.now(),
                "entity_id": str(uuid4()),
                "entity_type": "Taxonomy",
                "operation": "create",
                "new_state": None,
                "previous_state": None,
            },
        )

        response = client.get(
            f"/api/v1/interchange/runs/{run.id}/change-events?entity_type=Class"
        )

        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["entity_type"] == "Class"

    def test_get_change_events_filter_by_change_type(self, client, interchange_repo):
        """Change events endpoint filters by change_type (operation) parameter."""
        run = ImportRun(
            id=str(uuid4()),
            created_at=datetime.now(),
            created_by=None,
            format=SerializationFormat.SKOS,
            source_uri="test.skos",
            source_hash="hash",
            scope=SerializationScope(
                scope_type=SerializationScopeType.WHOLE_GRAPH,
            ),
            status=ImportRunStatus.COMMITTED,
        )
        interchange_repo.create(run)

        # Add events with different operations
        interchange_repo.add_change_event(
            run.id,
            {
                "id": str(uuid4()),
                "timestamp": datetime.now(),
                "entity_id": str(uuid4()),
                "entity_type": "Class",
                "operation": "create",
                "new_state": None,
                "previous_state": None,
            },
        )
        interchange_repo.add_change_event(
            run.id,
            {
                "id": str(uuid4()),
                "timestamp": datetime.now(),
                "entity_id": str(uuid4()),
                "entity_type": "Class",
                "operation": "update",
                "new_state": None,
                "previous_state": None,
            },
        )

        response = client.get(
            f"/api/v1/interchange/runs/{run.id}/change-events?change_type=update"
        )

        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["operation"] == "update"

    def test_get_change_events_combined_filters_and_pagination(
        self, client, interchange_repo
    ):
        """Change events endpoint handles combined filters and pagination."""
        run = ImportRun(
            id=str(uuid4()),
            created_at=datetime.now(),
            created_by=None,
            format=SerializationFormat.SKOS,
            source_uri="test.skos",
            source_hash="hash",
            scope=SerializationScope(
                scope_type=SerializationScopeType.WHOLE_GRAPH,
            ),
            status=ImportRunStatus.COMMITTED,
        )
        interchange_repo.create(run)

        # Add 4 create events and 2 update events
        for i in range(4):
            interchange_repo.add_change_event(
                run.id,
                {
                    "id": str(uuid4()),
                    "timestamp": datetime.now(),
                    "entity_id": str(uuid4()),
                    "entity_type": "Class",
                    "operation": "create",
                    "new_state": None,
                    "previous_state": None,
                },
            )
        for i in range(2):
            interchange_repo.add_change_event(
                run.id,
                {
                    "id": str(uuid4()),
                    "timestamp": datetime.now(),
                    "entity_id": str(uuid4()),
                    "entity_type": "Class",
                    "operation": "update",
                    "new_state": None,
                    "previous_state": None,
                },
            )

        response = client.get(
            f"/api/v1/interchange/runs/{run.id}/change-events?change_type=create&offset=1&limit=2"
        )

        data = response.json()
        assert data["total"] == 4  # Total of 4 create events
        assert data["offset"] == 1
        assert data["limit"] == 2
        assert len(data["items"]) == 2
        assert all(item["operation"] == "create" for item in data["items"])
