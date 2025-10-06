#!/usr/bin/env python
"""
Standalone test runner for Phase 5 cleanup tests.
Bypasses conftest to avoid dependency issues.
"""

import sys
import os
from pathlib import Path
import json
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Test tracking
tests_passed = 0
tests_failed = 0
failures = []


def test(name, condition, message=""):
    """Simple test helper."""
    global tests_passed, tests_failed, failures
    if condition:
        print(f"✓ {name}")
        tests_passed += 1
    else:
        print(f"✗ {name}: {message}")
        tests_failed += 1
        failures.append((name, message))


print("=" * 70)
print("Phase 5 Cleanup Tests")
print("=" * 70)

# Test 1: Deprecated code removal
print("\n1. Testing deprecated code removal...")
manager_path = Path(__file__).parent.parent / "schema_org" / "manager.py"
with open(manager_path, 'r') as f:
    manager_content = f.read()

test("No FTS5 in manager (lowercase)", "fts5" not in manager_content.lower(), "FTS5 still present")
test("No FTS5 in manager (uppercase)", "FTS5" not in manager_content, "FTS5 still present")
test("No _create_backup", "_create_backup" not in manager_content, "_create_backup still exists")
test("No _restore_from_backup", "_restore_from_backup" not in manager_content, "_restore_from_backup still exists")
test("No backup_path", "backup_path" not in manager_content, "backup_path still exists")

errors_path = Path(__file__).parent.parent / "schema_org" / "errors.py"
with open(errors_path, 'r') as f:
    errors_content = f.read()

test("BackupError removed", "BackupError" not in errors_content, "BackupError still exists")
test("RestoreError removed", "RestoreError" not in errors_content, "RestoreError still exists")

# Test 2: Metrics implementation
print("\n2. Testing metrics implementation...")
metrics_path = Path(__file__).parent.parent / "schema_org" / "metrics.py"
test("Metrics module exists", metrics_path.exists(), "metrics.py not found")

try:
    from schema_org.metrics import ImportMetrics, SearchMetrics, MetricsTracker

    # Test ImportMetrics
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
    test("ImportMetrics instantiation", metrics.entity_count == 100, "Values not set correctly")

    metrics_dict = metrics.to_dict()
    test("ImportMetrics to_dict", isinstance(metrics_dict, dict) and metrics_dict["entity_count"] == 100,
         "to_dict failed")

    # Test SearchMetrics
    search_metrics = SearchMetrics(
        query_time_ms=25.5,
        result_count=15,
        search_type="semantic",
        threshold=0.7,
        limit=20
    )
    test("SearchMetrics instantiation", search_metrics.query_time_ms == 25.5, "Values not set correctly")

    search_dict = search_metrics.to_dict()
    test("SearchMetrics to_dict", isinstance(search_dict, dict) and search_dict["query_time_ms"] == 25.5,
         "to_dict failed")

    # Test MetricsTracker
    with MetricsTracker("test_operation") as tracker:
        time.sleep(0.01)

    elapsed = tracker.elapsed_seconds()
    test("MetricsTracker context manager", elapsed >= 0.01, f"Expected >= 0.01s, got {elapsed}s")

except Exception as e:
    test("Metrics functionality", False, str(e))

# Test 3: Configuration documentation
print("\n3. Testing configuration documentation...")
config_path = Path(__file__).parent.parent / "schema_org" / "CONFIGURATION.md"
test("CONFIGURATION.md exists", config_path.exists(), "CONFIGURATION.md not found")

if config_path.exists():
    with open(config_path, 'r') as f:
        config_content = f.read()

    test("Documents batch size", "Batch Size" in config_content or "batch" in config_content.lower(),
         "Missing batch size documentation")
    test("Documents trade-offs", "Trade-offs" in config_content or "trade-off" in config_content.lower(),
         "Missing trade-offs documentation")
    test("Documents memory usage", "Memory Usage" in config_content or "Memory" in config_content,
         "Missing memory documentation")

readme_path = Path(__file__).parent / "fixtures" / "README.md"
test("Fixtures README exists", readme_path.exists(), "fixtures/README.md not found")

if readme_path.exists():
    with open(readme_path, 'r') as f:
        readme_content = f.read()

    test("Documents version pinning", "Version Pinning" in readme_content or "version" in readme_content.lower(),
         "Missing version pinning documentation")
    test("Documents Schema.org", "Schema.org" in readme_content or "schema.org" in readme_content.lower(),
         "Missing Schema.org documentation")

# Test 4: Performance baselines
print("\n4. Testing performance baselines...")
baselines_dir = Path(__file__).parent / "performance" / "baselines"
test("Baselines directory exists", baselines_dir.exists(), "Baselines directory not found")

baseline_file = baselines_dir / "vector_search_baseline.json"
test("vector_search_baseline.json exists", baseline_file.exists(), "Baseline file not found")

if baseline_file.exists():
    with open(baseline_file, 'r') as f:
        baseline = json.load(f)

    test("Baseline has version", "version" in baseline, "Missing version field")
    test("Baseline has baselines section", "baselines" in baseline, "Missing baselines section")
    test("Baseline has last_updated", "last_updated" in baseline, "Missing last_updated field")

    baselines = baseline.get("baselines", {})
    test("Has latency baseline", "top_20_query_latency_ms" in baselines, "Missing latency baseline")
    test("Has throughput baseline", "concurrent_throughput_qps" in baselines, "Missing throughput baseline")

    # Verify baseline structure
    if "top_20_query_latency_ms" in baselines:
        latency_baseline = baselines["top_20_query_latency_ms"]
        test("Latency baseline has target", "target" in latency_baseline, "Missing target")
        test("Latency baseline has tolerance", "tolerance_pct" in latency_baseline, "Missing tolerance")
        test("Tolerance is ±15%", latency_baseline.get("tolerance_pct") == 15, f"Got {latency_baseline.get('tolerance_pct')}%")

# Test 5: Error handling improvements
print("\n5. Testing error handling improvements...")
test("Manager has user-friendly errors", "Please check" in manager_content or "Please ensure" in manager_content,
     "Missing user-friendly error messages")
test("Manager has sqlite-vec error handling", "sqlite-vec" in manager_content.lower(),
     "Missing sqlite-vec error handling")

service_path = Path(__file__).parent.parent / "schema_org" / "service.py"
with open(service_path, 'r') as f:
    service_content = f.read()

test("Service imports SearchMetrics", "from .metrics import SearchMetrics" in service_content,
     "SearchMetrics not imported")
test("Service uses SearchMetrics", "SearchMetrics(" in service_content,
     "SearchMetrics not used")

# Summary
print("\n" + "=" * 70)
print(f"Tests passed: {tests_passed}")
print(f"Tests failed: {tests_failed}")

if failures:
    print("\nFailures:")
    for name, message in failures:
        print(f"  - {name}: {message}")
    sys.exit(1)
else:
    print("\n✓ All Phase 5 cleanup tests passed!")
    sys.exit(0)
