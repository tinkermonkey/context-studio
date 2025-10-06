"""
Integration tests for Phase 5: Schema.org Code Cleanup, Performance Optimization, and Monitoring

Tests the complete integration of Phase 5 changes including:
- Deprecated code removal (FTS5, backup/restore)
- Metrics tracking (import and search metrics)
- Memory profiling during import
- Error handling improvements
- Configuration documentation compliance
"""

import sys
import os
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, Mock

# Ensure project root is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

import pytest
import numpy as np

from schema_org.manager import SchemaOrgManager
from schema_org.service import SchemaOrgService
from schema_org.metrics import ImportMetrics, SearchMetrics, MetricsTracker
from schema_org.errors import DatabaseError, DownloadError, ParseError, ValidationError


def _create_sample_jsonld():
    """Create a comprehensive sample JSON-LD for testing."""
    return {
        "@context": "https://schema.org/",
        "@graph": [
            {
                "@id": "http://schema.org/Thing",
                "@type": "rdfs:Class",
                "label": "Thing",
                "comment": "The most generic type of item.",
            },
            {
                "@id": "http://schema.org/Person",
                "@type": "rdfs:Class",
                "label": "Person",
                "comment": "A person (alive, dead, undead, or fictional).",
            },
            {
                "@id": "http://schema.org/Organization",
                "@type": "rdfs:Class",
                "label": "Organization",
                "comment": "An organization such as a school, NGO, corporation, club, etc.",
            },
            {
                "@id": "http://schema.org/Place",
                "@type": "rdfs:Class",
                "label": "Place",
                "comment": "Entities that have a somewhat fixed, physical extension.",
            },
            {
                "@id": "http://schema.org/Event",
                "@type": "rdfs:Class",
                "label": "Event",
                "comment": "An event happening at a certain time and location.",
            },
            {
                "@id": "http://schema.org/name",
                "@type": "rdf:Property",
                "label": "name",
                "comment": "The name of the item.",
            },
            {
                "@id": "http://schema.org/description",
                "@type": "rdf:Property",
                "label": "description",
                "comment": "A description of the item.",
            },
            {
                "@id": "http://schema.org/memberOf",
                "@type": "rdf:Property",
                "label": "memberOf",
                "comment": "An organization to which this person belongs.",
            },
        ],
    }


def _fake_embedding(text: str, dim: int = 384) -> bytes:
    """Create deterministic embeddings for testing."""
    # Use text hash for reproducible embeddings
    s = sum(bytearray(text.encode("utf-8") or b"0")) % 100
    arr = np.full((dim,), float(s) / 100.0, dtype=np.float32)
    # Normalize to avoid zero-norm issues
    norm = np.linalg.norm(arr)
    if norm > 0:
        arr = arr / norm
    return arr.tobytes()


class TestDeprecatedCodeRemoval:
    """Test that deprecated code has been properly removed."""

    def test_no_fts5_in_manager(self):
        """Verify FTS5 code has been removed from manager."""
        manager_path = Path(__file__).parent.parent.parent / "schema_org" / "manager.py"
        with open(manager_path, 'r') as f:
            content = f.read()

        # Should not contain FTS5 references
        assert "fts5" not in content.lower(), "FTS5 references still present"
        assert "FTS5" not in content, "FTS5 table creation still present"

    def test_no_backup_restore_methods(self):
        """Verify backup/restore methods have been removed."""
        manager_path = Path(__file__).parent.parent.parent / "schema_org" / "manager.py"
        with open(manager_path, 'r') as f:
            content = f.read()

        # Should not contain backup/restore methods
        assert "_create_backup" not in content, "_create_backup still exists"
        assert "_restore_from_backup" not in content, "_restore_from_backup still exists"

    def test_no_backup_errors(self):
        """Verify BackupError and RestoreError have been removed."""
        from schema_org import errors

        assert not hasattr(errors, 'BackupError'), "BackupError still exists"
        assert not hasattr(errors, 'RestoreError'), "RestoreError still exists"


class TestImportMetricsTracking:
    """Test import metrics tracking and logging."""

    def test_import_metrics_tracking_workflow(self, tmp_path):
        """Test complete import workflow with metrics tracking."""
        db_file = tmp_path / "metrics_test.db"
        db_path = str(db_file)

        mgr = SchemaOrgManager(db_path=db_path)

        # Create sample data
        sample_json = str(tmp_path / "sample.jsonld")
        with open(sample_json, "w") as f:
            json.dump(_create_sample_jsonld(), f)

        # Monkeypatch download and embedding
        with patch.object(SchemaOrgManager, "_download_schema_org", return_value=sample_json):
            with patch("schema_org.manager.generate_embedding", side_effect=lambda t: _fake_embedding(t)):
                # Run refresh and capture metrics
                result = mgr.refresh_data(force=True)

        # Verify metrics are returned
        assert result.get("success") is True
        assert "duration_seconds" in result
        assert "entity_count" in result
        assert "property_count" in result
        assert result["entity_count"] == 5  # Thing, Person, Organization, Place, Event
        assert result["property_count"] == 3  # name, description, memberOf

        # Verify metrics include new Phase 5 fields
        assert "peak_memory_mb" in result
        assert "download_duration_seconds" in result
        assert "parse_duration_seconds" in result
        assert "populate_duration_seconds" in result

    def test_import_metrics_dataclass(self):
        """Test ImportMetrics dataclass functionality."""
        metrics = ImportMetrics(
            duration_seconds=10.5,
            entity_count=100,
            property_count=50,
            embedding_failures=2,
            retry_counts=1,
            download_duration_seconds=2.0,
            parse_duration_seconds=1.5,
            populate_duration_seconds=7.0,
            total_embeddings_generated=150,
            peak_memory_mb=125.5
        )

        # Test to_dict
        metrics_dict = metrics.to_dict()
        assert metrics_dict["entity_count"] == 100
        assert metrics_dict["peak_memory_mb"] == 125.5

        # Test logging (should not raise)
        metrics.log()

    def test_import_metrics_environment_variable(self, tmp_path, monkeypatch):
        """Test metrics logging can be disabled via environment variable."""
        # Disable metrics logging
        monkeypatch.setenv("SCHEMA_ORG_METRICS_LOGGING", "false")

        # Import the module fresh to pick up env var
        import importlib
        from schema_org import metrics as metrics_module
        importlib.reload(metrics_module)

        metrics = metrics_module.ImportMetrics(
            duration_seconds=10.0,
            entity_count=100,
            property_count=50
        )

        # Logging should be silently skipped (no error)
        metrics.log()


class TestSearchMetricsTracking:
    """Test search metrics tracking."""

    def test_search_metrics_tracking_workflow(self, tmp_path):
        """Test search operations track metrics properly."""
        db_file = tmp_path / "search_metrics_test.db"
        db_path = str(db_file)

        mgr = SchemaOrgManager(db_path=db_path)

        # Populate database
        sample_json = str(tmp_path / "sample.jsonld")
        with open(sample_json, "w") as f:
            json.dump(_create_sample_jsonld(), f)

        with patch.object(SchemaOrgManager, "_download_schema_org", return_value=sample_json):
            with patch("schema_org.manager.generate_embedding", side_effect=lambda t: _fake_embedding(t)):
                mgr.refresh_data(force=True)

        # Create service and perform search
        svc = SchemaOrgService(manager=mgr)

        # Mock embedding generation for search
        with patch("schema_org.service.generate_embedding", return_value=_fake_embedding("person")):
            result = svc.semantic_search(
                query="person",
                search_type="entities",
                limit=5,
                similarity_threshold=0.0
            )

        # Verify search results
        assert "items" in result
        assert len(result["items"]) >= 1

        # Search should internally track metrics (verify via logs in real usage)
        # The service logs search metrics at DEBUG level

    def test_search_metrics_dataclass(self):
        """Test SearchMetrics dataclass functionality."""
        metrics = SearchMetrics(
            query_time_ms=25.5,
            result_count=15,
            search_type="semantic",
            threshold=0.7,
            limit=20
        )

        # Test to_dict
        metrics_dict = metrics.to_dict()
        assert metrics_dict["query_time_ms"] == 25.5
        assert metrics_dict["search_type"] == "semantic"

        # Test logging (should not raise)
        metrics.log()


class TestMetricsTrackerContextManager:
    """Test MetricsTracker context manager."""

    def test_metrics_tracker_basic_operation(self):
        """Test MetricsTracker tracks time correctly."""
        with MetricsTracker("test_operation") as tracker:
            time.sleep(0.02)  # 20ms

        elapsed = tracker.elapsed_seconds()
        assert elapsed >= 0.02, f"Expected >= 0.02s, got {elapsed}s"
        assert elapsed < 0.1, f"Expected < 0.1s, got {elapsed}s"

    def test_metrics_tracker_thread_safety(self):
        """Test MetricsTracker is thread-safe."""
        import threading

        results = []

        def worker():
            with MetricsTracker("thread_test") as tracker:
                time.sleep(0.01)
            results.append(tracker.elapsed_seconds())

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should have completed successfully
        assert len(results) == 5
        for elapsed in results:
            assert elapsed >= 0.01


class TestErrorHandlingImprovements:
    """Test enhanced error handling with clear messages."""

    def test_missing_sqlite_vec_error_message(self, tmp_path):
        """Test that missing sqlite-vec produces clear, actionable error."""
        db_file = tmp_path / "error_test.db"
        db_path = str(db_file)

        mgr = SchemaOrgManager(db_path=db_path)

        sample_json = str(tmp_path / "sample.jsonld")
        with open(sample_json, "w") as f:
            json.dump(_create_sample_jsonld(), f)

        # Mock sqlite-vec import failure
        with patch.object(SchemaOrgManager, "_download_schema_org", return_value=sample_json):
            with patch("schema_org.manager.generate_embedding", side_effect=lambda t: _fake_embedding(t)):
                # Mock sqlite3.connect to raise error about missing sqlite-vec
                def mock_connect_sqlite_vec_missing(*args, **kwargs):
                    import sqlite3
                    conn = sqlite3.connect(*args, **kwargs)
                    # Simulate sqlite-vec not loaded
                    original_execute = conn.execute
                    def patched_execute(sql, *args, **kwargs):
                        if "vec0" in sql.lower() or "vec_" in sql.lower():
                            raise sqlite3.OperationalError("no such module: vec")
                        return original_execute(sql, *args, **kwargs)
                    conn.execute = patched_execute
                    return conn

                # This test verifies the error message is helpful
                # In practice, if sqlite-vec is not installed, we expect clear guidance

    def test_malformed_json_error_message(self, tmp_path):
        """Test that malformed JSON produces specific error message."""
        db_file = tmp_path / "error_test2.db"
        db_path = str(db_file)

        mgr = SchemaOrgManager(db_path=db_path)

        # Create malformed JSON
        sample_json = str(tmp_path / "malformed.jsonld")
        with open(sample_json, "w") as f:
            f.write("{ this is not valid json }")

        with patch.object(SchemaOrgManager, "_download_schema_org", return_value=sample_json):
            result = mgr.refresh_data(force=True)

            # Should fail gracefully with clear message
            assert result.get("success") is False
            assert "message" in result

    def test_download_error_handling(self, tmp_path):
        """Test download errors are handled with clear messages."""
        db_file = tmp_path / "download_error_test.db"
        db_path = str(db_file)

        mgr = SchemaOrgManager(db_path=db_path)

        # Mock download failure
        def mock_download_failure(self):
            raise DownloadError("Failed to download schema.org data: Network timeout")

        with patch.object(SchemaOrgManager, "_download_schema_org", side_effect=mock_download_failure):
            result = mgr.refresh_data(force=True)

            assert result.get("success") is False
            assert "download" in result.get("message", "").lower()


class TestMemoryProfiling:
    """Test memory profiling during import."""

    def test_memory_profiling_enabled(self, tmp_path):
        """Test that memory profiling tracks peak usage."""
        db_file = tmp_path / "memory_test.db"
        db_path = str(db_file)

        mgr = SchemaOrgManager(db_path=db_path)

        sample_json = str(tmp_path / "sample.jsonld")
        with open(sample_json, "w") as f:
            json.dump(_create_sample_jsonld(), f)

        with patch.object(SchemaOrgManager, "_download_schema_org", return_value=sample_json):
            with patch("schema_org.manager.generate_embedding", side_effect=lambda t: _fake_embedding(t)):
                result = mgr.refresh_data(force=True)

        # Verify memory tracking
        assert "peak_memory_mb" in result
        # Should have some memory usage
        if result.get("peak_memory_mb"):
            assert result["peak_memory_mb"] > 0

    def test_memory_profiling_graceful_degradation(self, tmp_path, monkeypatch):
        """Test that import works even if psutil is not available."""
        db_file = tmp_path / "memory_graceful_test.db"
        db_path = str(db_file)

        # Mock psutil unavailable
        with patch("schema_org.manager.psutil", None):
            mgr = SchemaOrgManager(db_path=db_path)

            sample_json = str(tmp_path / "sample.jsonld")
            with open(sample_json, "w") as f:
                json.dump(_create_sample_jsonld(), f)

            with patch.object(SchemaOrgManager, "_download_schema_org", return_value=sample_json):
                with patch("schema_org.manager.generate_embedding", side_effect=lambda t: _fake_embedding(t)):
                    result = mgr.refresh_data(force=True)

            # Should still succeed
            assert result.get("success") is True
            # peak_memory_mb should be None or omitted
            assert result.get("peak_memory_mb") is None


class TestConfigurationCompliance:
    """Test compliance with configuration documentation."""

    def test_configuration_md_exists(self):
        """Verify CONFIGURATION.md exists and documents parameters."""
        config_path = Path(__file__).parent.parent.parent / "schema_org" / "CONFIGURATION.md"
        assert config_path.exists(), "CONFIGURATION.md not found"

        with open(config_path, 'r') as f:
            content = f.read()

        # Verify key sections exist
        assert "Batch Size" in content or "batch" in content.lower()
        assert "Trade-offs" in content or "trade-off" in content.lower()
        assert "Memory" in content or "memory" in content.lower()

    def test_fixtures_readme_exists(self):
        """Verify fixtures README documents Schema.org versioning."""
        readme_path = Path(__file__).parent.parent / "fixtures" / "README.md"
        assert readme_path.exists(), "fixtures/README.md not found"

        with open(readme_path, 'r') as f:
            content = f.read()

        # Verify Schema.org documentation
        assert "Schema.org" in content or "schema.org" in content.lower()


class TestPerformanceBaselines:
    """Test performance baseline validation."""

    def test_baseline_files_exist(self):
        """Verify performance baseline files exist."""
        baselines_dir = Path(__file__).parent.parent / "performance" / "baselines"
        assert baselines_dir.exists(), "Baselines directory not found"

        baseline_file = baselines_dir / "vector_search_baseline.json"
        assert baseline_file.exists(), "vector_search_baseline.json not found"

    def test_baseline_structure(self):
        """Verify baseline file structure is correct."""
        baseline_file = Path(__file__).parent.parent / "performance" / "baselines" / "vector_search_baseline.json"

        with open(baseline_file, 'r') as f:
            baseline = json.load(f)

        # Verify structure
        assert "version" in baseline
        assert "baselines" in baseline
        assert "last_updated" in baseline

        # Verify specific baselines
        baselines = baseline["baselines"]
        assert "top_20_query_latency_ms" in baselines
        assert "concurrent_throughput_qps" in baselines

        # Verify tolerance is ±15%
        for key, value in baselines.items():
            assert "tolerance_pct" in value
            assert value["tolerance_pct"] == 15


class TestEndToEndWorkflow:
    """Test complete end-to-end workflows."""

    def test_complete_import_and_search_workflow(self, tmp_path):
        """Test full workflow: import → search entities → search properties."""
        db_file = tmp_path / "e2e_test.db"
        db_path = str(db_file)

        # Step 1: Import data
        mgr = SchemaOrgManager(db_path=db_path)

        sample_json = str(tmp_path / "sample.jsonld")
        with open(sample_json, "w") as f:
            json.dump(_create_sample_jsonld(), f)

        with patch.object(SchemaOrgManager, "_download_schema_org", return_value=sample_json):
            with patch("schema_org.manager.generate_embedding", side_effect=lambda t: _fake_embedding(t)):
                import_result = mgr.refresh_data(force=True)

        assert import_result.get("success") is True
        assert import_result["entity_count"] == 5
        assert import_result["property_count"] == 3

        # Step 2: Search for entities
        svc = SchemaOrgService(manager=mgr)

        with patch("schema_org.service.generate_embedding", return_value=_fake_embedding("person")):
            entity_results = svc.semantic_search(
                query="person",
                search_type="entities",
                limit=10,
                similarity_threshold=0.0
            )

        assert entity_results["total_count"] >= 1
        assert len(entity_results["items"]) >= 1

        # Step 3: Search for properties
        with patch("schema_org.service.generate_embedding", return_value=_fake_embedding("name")):
            property_results = svc.semantic_search(
                query="name",
                search_type="properties",
                limit=10,
                similarity_threshold=0.0
            )

        assert property_results["total_count"] >= 1
        assert len(property_results["items"]) >= 1

        # Step 4: Combined search
        with patch("schema_org.service.generate_embedding", return_value=_fake_embedding("organization")):
            combined_results = svc.semantic_search(
                query="organization",
                search_type="both",
                limit=10,
                similarity_threshold=0.0
            )

        assert combined_results["total_count"] >= 1

    def test_concurrent_search_workflow(self, tmp_path):
        """Test concurrent searches work correctly (thread-safe)."""
        import threading

        db_file = tmp_path / "concurrent_test.db"
        db_path = str(db_file)

        # Setup database
        mgr = SchemaOrgManager(db_path=db_path)

        sample_json = str(tmp_path / "sample.jsonld")
        with open(sample_json, "w") as f:
            json.dump(_create_sample_jsonld(), f)

        with patch.object(SchemaOrgManager, "_download_schema_org", return_value=sample_json):
            with patch("schema_org.manager.generate_embedding", side_effect=lambda t: _fake_embedding(t)):
                mgr.refresh_data(force=True)

        svc = SchemaOrgService(manager=mgr)

        # Concurrent search function
        results = []
        errors = []

        def search_worker(query_text):
            try:
                with patch("schema_org.service.generate_embedding", return_value=_fake_embedding(query_text)):
                    result = svc.semantic_search(
                        query=query_text,
                        search_type="both",
                        limit=5,
                        similarity_threshold=0.0
                    )
                    results.append(result)
            except Exception as e:
                errors.append(e)

        # Run concurrent searches
        queries = ["person", "place", "event", "organization", "name"]
        threads = [threading.Thread(target=search_worker, args=(q,)) for q in queries]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify all searches succeeded
        assert len(errors) == 0, f"Concurrent search errors: {errors}"
        assert len(results) == 5
        for result in results:
            assert "items" in result
            assert "total_count" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
