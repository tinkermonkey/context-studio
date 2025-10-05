"""
Unit tests for Phase 5: Code Cleanup, Performance Optimization, and Monitoring.

Tests that deprecated code has been removed and new monitoring features work.
"""

import pytest
import os
from pathlib import Path


class TestDeprecatedCodeRemoval:
    """Test that deprecated code has been removed."""

    def test_fts5_removed_from_manager(self):
        """Verify FTS5 code has been removed from schema_org manager."""
        manager_path = Path(__file__).parent.parent.parent / "schema_org" / "manager.py"

        with open(manager_path, 'r') as f:
            content = f.read()

        # Should not contain FTS5 references
        assert "fts5" not in content.lower(), "FTS5 references still present in manager"
        assert "FTS5" not in content, "FTS5 references still present in manager"

    def test_backup_restore_errors_removed(self):
        """Verify BackupError and RestoreError have been removed."""
        errors_path = Path(__file__).parent.parent.parent / "schema_org" / "errors.py"

        with open(errors_path, 'r') as f:
            content = f.read()

        # Should not contain BackupError or RestoreError
        assert "BackupError" not in content, "BackupError still present in errors.py"
        assert "RestoreError" not in content, "RestoreError still present in errors.py"

    def test_backup_methods_removed_from_manager(self):
        """Verify backup/restore methods have been removed from manager."""
        manager_path = Path(__file__).parent.parent.parent / "schema_org" / "manager.py"

        with open(manager_path, 'r') as f:
            content = f.read()

        # Should not contain backup methods
        assert "_create_backup" not in content, "_create_backup method still present"
        assert "_restore_from_backup" not in content, "_restore_from_backup method still present"
        assert "backup_path" not in content, "backup_path attribute still present"


class TestMetricsImplementation:
    """Test that metrics and monitoring have been implemented."""

    def test_metrics_module_exists(self):
        """Verify metrics module exists."""
        metrics_path = Path(__file__).parent.parent.parent / "schema_org" / "metrics.py"
        assert metrics_path.exists(), "Metrics module not found"

    def test_import_metrics_class(self):
        """Verify ImportMetrics class can be imported and used."""
        from schema_org.metrics import ImportMetrics

        metrics = ImportMetrics(
            duration_seconds=10.0,
            entity_count=100,
            property_count=50,
            embedding_failures=2,
            retry_counts=1,
            download_duration_seconds=2.0,
            parse_duration_seconds=1.0,
            populate_duration_seconds=7.0,
            total_embeddings_generated=300,
            peak_memory_mb=120.5
        )

        assert metrics.entity_count == 100
        assert metrics.property_count == 50
        assert metrics.peak_memory_mb == 120.5

        # Test to_dict conversion
        metrics_dict = metrics.to_dict()
        assert isinstance(metrics_dict, dict)
        assert metrics_dict["entity_count"] == 100

    def test_search_metrics_class(self):
        """Verify SearchMetrics class can be imported and used."""
        from schema_org.metrics import SearchMetrics

        metrics = SearchMetrics(
            query_time_ms=25.5,
            result_count=15,
            search_type="semantic",
            threshold=0.7,
            limit=20
        )

        assert metrics.query_time_ms == 25.5
        assert metrics.result_count == 15
        assert metrics.search_type == "semantic"

        # Test to_dict conversion
        metrics_dict = metrics.to_dict()
        assert isinstance(metrics_dict, dict)
        assert metrics_dict["query_time_ms"] == 25.5

    def test_metrics_tracker_context_manager(self):
        """Verify MetricsTracker context manager works."""
        import time
        from schema_org.metrics import MetricsTracker

        with MetricsTracker("test_operation") as tracker:
            time.sleep(0.01)  # Sleep for 10ms

        elapsed = tracker.elapsed_seconds()
        assert elapsed >= 0.01, f"Expected >= 0.01s, got {elapsed}s"


class TestConfigurationDocumentation:
    """Test that configuration documentation has been created."""

    def test_configuration_md_exists(self):
        """Verify CONFIGURATION.md exists."""
        config_path = Path(__file__).parent.parent.parent / "schema_org" / "CONFIGURATION.md"
        assert config_path.exists(), "CONFIGURATION.md not found"

    def test_configuration_documents_batch_size(self):
        """Verify CONFIGURATION.md documents batch size trade-offs."""
        config_path = Path(__file__).parent.parent.parent / "schema_org" / "CONFIGURATION.md"

        with open(config_path, 'r') as f:
            content = f.read()

        # Check for key sections
        assert "Batch Size Configuration" in content, "Missing batch size section"
        assert "Trade-offs" in content, "Missing trade-offs section"
        assert "Small Batch Sizes" in content, "Missing small batch documentation"
        assert "Large Batch Sizes" in content, "Missing large batch documentation"
        assert "Memory Usage" in content, "Missing memory usage documentation"

    def test_fixtures_readme_exists(self):
        """Verify fixtures README exists."""
        readme_path = Path(__file__).parent.parent / "fixtures" / "README.md"
        assert readme_path.exists(), "Fixtures README.md not found"

    def test_fixtures_readme_documents_schema_org_pinning(self):
        """Verify fixtures README documents Schema.org version pinning."""
        readme_path = Path(__file__).parent.parent / "fixtures" / "README.md"

        with open(readme_path, 'r') as f:
            content = f.read()

        # Check for key sections
        assert "Version Pinning" in content, "Missing version pinning section"
        assert "Schema.org" in content, "Missing Schema.org documentation"
        assert "Updating" in content, "Missing update procedure"


class TestPerformanceBaselines:
    """Test that performance baselines have been created."""

    def test_baseline_directory_exists(self):
        """Verify performance baselines directory exists."""
        baselines_dir = Path(__file__).parent.parent / "performance" / "baselines"
        assert baselines_dir.exists(), "Baselines directory not found"

    def test_vector_search_baseline_exists(self):
        """Verify vector search baseline file exists."""
        baseline_path = Path(__file__).parent.parent / "performance" / "baselines" / "vector_search_baseline.json"
        assert baseline_path.exists(), "vector_search_baseline.json not found"

    def test_vector_search_baseline_structure(self):
        """Verify vector search baseline has correct structure."""
        import json

        baseline_path = Path(__file__).parent.parent / "performance" / "baselines" / "vector_search_baseline.json"

        with open(baseline_path, 'r') as f:
            baseline = json.load(f)

        # Check structure
        assert "version" in baseline, "Missing version"
        assert "baselines" in baseline, "Missing baselines section"
        assert "last_updated" in baseline, "Missing last_updated"

        # Check specific baselines
        assert "top_20_query_latency_ms" in baseline["baselines"], "Missing latency baseline"
        assert "concurrent_throughput_qps" in baseline["baselines"], "Missing throughput baseline"

        # Check baseline structure
        latency_baseline = baseline["baselines"]["top_20_query_latency_ms"]
        assert "target" in latency_baseline, "Missing target in baseline"
        assert "tolerance_pct" in latency_baseline, "Missing tolerance in baseline"
        assert "description" in latency_baseline, "Missing description in baseline"


class TestErrorHandling:
    """Test that error handling has been enhanced."""

    def test_manager_has_clear_error_messages(self):
        """Verify manager provides clear error messages."""
        manager_path = Path(__file__).parent.parent.parent / "schema_org" / "manager.py"

        with open(manager_path, 'r') as f:
            content = f.read()

        # Check for enhanced error messages
        assert "Please check" in content or "Please ensure" in content, "Missing user-friendly error messages"
        assert "sqlite-vec" in content.lower(), "Missing sqlite-vec error handling"

    def test_service_imports_search_metrics(self):
        """Verify service imports and uses SearchMetrics."""
        service_path = Path(__file__).parent.parent.parent / "schema_org" / "service.py"

        with open(service_path, 'r') as f:
            content = f.read()

        # Check for SearchMetrics import and usage
        assert "from .metrics import SearchMetrics" in content, "SearchMetrics not imported"
        assert "SearchMetrics(" in content, "SearchMetrics not used"
