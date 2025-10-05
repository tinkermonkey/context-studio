#!/usr/bin/env python
"""
Standalone verification script for Phase 5 cleanup and optimization.
Runs without pytest to avoid conftest dependencies.
"""

import sys
from pathlib import Path

# Track results
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


print("Phase 5: Code Cleanup and Optimization Verification")
print("=" * 60)

# Test 1: FTS5 removed from manager
print("\n1. Testing FTS5 removal...")
manager_path = Path(__file__).parent / "schema_org" / "manager.py"
with open(manager_path, 'r') as f:
    manager_content = f.read()

test("FTS5 not in manager.py (lowercase)",
     "fts5" not in manager_content.lower(),
     "FTS5 references still present")
test("FTS5 not in manager.py (uppercase)",
     "FTS5" not in manager_content,
     "FTS5 references still present")

# Test 2: Backup/Restore errors removed
print("\n2. Testing backup/restore error removal...")
errors_path = Path(__file__).parent / "schema_org" / "errors.py"
with open(errors_path, 'r') as f:
    errors_content = f.read()

test("BackupError removed",
     "BackupError" not in errors_content,
     "BackupError still present in errors.py")
test("RestoreError removed",
     "RestoreError" not in errors_content,
     "RestoreError still present in errors.py")

# Test 3: Backup methods removed from manager
print("\n3. Testing backup/restore method removal...")
test("_create_backup removed",
     "_create_backup" not in manager_content,
     "_create_backup method still present")
test("_restore_from_backup removed",
     "_restore_from_backup" not in manager_content,
     "_restore_from_backup method still present")
test("backup_path removed",
     "backup_path" not in manager_content,
     "backup_path attribute still present")

# Test 4: Metrics module exists
print("\n4. Testing metrics implementation...")
metrics_path = Path(__file__).parent / "schema_org" / "metrics.py"
test("Metrics module exists",
     metrics_path.exists(),
     "Metrics module not found")

# Test 5: Import and use metrics
print("\n5. Testing metrics functionality...")
try:
    from schema_org.metrics import ImportMetrics, SearchMetrics, MetricsTracker

    # Test ImportMetrics
    import_metrics = ImportMetrics(
        duration_seconds=10.0,
        entity_count=100,
        property_count=50
    )
    test("ImportMetrics instantiation",
         import_metrics.entity_count == 100,
         "ImportMetrics failed")

    metrics_dict = import_metrics.to_dict()
    test("ImportMetrics to_dict",
         isinstance(metrics_dict, dict) and metrics_dict["entity_count"] == 100,
         "to_dict failed")

    # Test SearchMetrics
    search_metrics = SearchMetrics(
        query_time_ms=25.5,
        result_count=15,
        search_type="semantic"
    )
    test("SearchMetrics instantiation",
         search_metrics.query_time_ms == 25.5,
         "SearchMetrics failed")

    # Test MetricsTracker
    import time
    with MetricsTracker("test") as tracker:
        time.sleep(0.01)
    elapsed = tracker.elapsed_seconds()
    test("MetricsTracker context manager",
         elapsed >= 0.01,
         f"Expected >= 0.01s, got {elapsed}s")

except Exception as e:
    test("Metrics import and usage", False, str(e))

# Test 6: Configuration documentation
print("\n6. Testing configuration documentation...")
config_path = Path(__file__).parent / "schema_org" / "CONFIGURATION.md"
test("CONFIGURATION.md exists",
     config_path.exists(),
     "CONFIGURATION.md not found")

if config_path.exists():
    with open(config_path, 'r') as f:
        config_content = f.read()

    test("Documents batch size configuration",
         "Batch Size Configuration" in config_content,
         "Missing batch size section")
    test("Documents trade-offs",
         "Trade-offs" in config_content,
         "Missing trade-offs section")
    test("Documents memory usage",
         "Memory Usage" in config_content,
         "Missing memory usage section")

# Test 7: Fixtures README
print("\n7. Testing fixtures documentation...")
readme_path = Path(__file__).parent / "tests" / "fixtures" / "README.md"
test("Fixtures README.md exists",
     readme_path.exists(),
     "README.md not found")

if readme_path.exists():
    with open(readme_path, 'r') as f:
        readme_content = f.read()

    test("Documents version pinning",
         "Version Pinning" in readme_content,
         "Missing version pinning section")
    test("Documents Schema.org",
         "Schema.org" in readme_content,
         "Missing Schema.org documentation")
    test("Documents update procedure",
         "Updating" in readme_content or "Update" in readme_content,
         "Missing update procedure")

# Test 8: Performance baselines
print("\n8. Testing performance baselines...")
baselines_dir = Path(__file__).parent / "tests" / "performance" / "baselines"
test("Baselines directory exists",
     baselines_dir.exists(),
     "Baselines directory not found")

baseline_file = baselines_dir / "vector_search_baseline.json"
test("vector_search_baseline.json exists",
     baseline_file.exists(),
     "Baseline file not found")

if baseline_file.exists():
    import json
    with open(baseline_file, 'r') as f:
        baseline = json.load(f)

    test("Baseline has version",
         "version" in baseline,
         "Missing version")
    test("Baseline has baselines section",
         "baselines" in baseline,
         "Missing baselines section")
    test("Has latency baseline",
         "top_20_query_latency_ms" in baseline.get("baselines", {}),
         "Missing latency baseline")
    test("Has throughput baseline",
         "concurrent_throughput_qps" in baseline.get("baselines", {}),
         "Missing throughput baseline")

# Test 9: Enhanced error handling
print("\n9. Testing error handling improvements...")
test("Manager has user-friendly error messages",
     "Please check" in manager_content or "Please ensure" in manager_content,
     "Missing user-friendly error messages")
test("Manager has sqlite-vec error handling",
     "sqlite-vec" in manager_content.lower(),
     "Missing sqlite-vec error handling")

# Test 10: Service integration
print("\n10. Testing service integration...")
service_path = Path(__file__).parent / "schema_org" / "service.py"
with open(service_path, 'r') as f:
    service_content = f.read()

test("Service imports SearchMetrics",
     "from .metrics import SearchMetrics" in service_content,
     "SearchMetrics not imported")
test("Service uses SearchMetrics",
     "SearchMetrics(" in service_content,
     "SearchMetrics not instantiated")

# Summary
print("\n" + "=" * 60)
print(f"Tests passed: {tests_passed}")
print(f"Tests failed: {tests_failed}")

if failures:
    print("\nFailures:")
    for name, message in failures:
        print(f"  - {name}: {message}")
    sys.exit(1)
else:
    print("\n✓ All Phase 5 verification tests passed!")
    sys.exit(0)
