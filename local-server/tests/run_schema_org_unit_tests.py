#!/usr/bin/env python
"""
Standalone test runner for schema_org unit tests.
Bypasses conftest to avoid dependency issues.
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import tempfile
import json
import numpy as np

from schema_org.manager import SchemaOrgManager
from schema_org.service import SchemaOrgService
from schema_org.errors import DatabaseError

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


def _fake_embedding(text: str, dim: int = 384) -> bytes:
    """Deterministic lightweight embedding for tests."""
    s = sum(bytearray(text.encode("utf-8") or b"0")) % 100
    arr = np.full((dim,), float(s) / 100.0, dtype=np.float32)
    return arr.tobytes()


def _write_sample_jsonld(path: str):
    sample = {
        "@context": {},
        "@graph": [
            {
                "@id": "http://example.org/Entity/1",
                "@type": "rdfs:Class",
                "label": "Fruit",
                "comment": "A test fruit entity",
            },
            {
                "@id": "http://example.org/Property/1",
                "@type": "rdf:Property",
                "label": "color",
                "comment": "Color of the fruit",
            },
        ],
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(sample, fh)


print("=" * 70)
print("Schema.org Unit Tests")
print("=" * 70)

# Test 1: Manager parse and populate
print("\n1. Testing manager parse and populate...")
try:
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test1.db")
        mgr = SchemaOrgManager(db_path=db_path)

        tmp_json = os.path.join(tmp_dir, "sample.jsonld")
        _write_sample_jsonld(tmp_json)

        # Mock download
        original_download = SchemaOrgManager._download_schema_org
        SchemaOrgManager._download_schema_org = lambda self: tmp_json

        # Mock embedding
        import schema_org.manager as mgr_module
        original_embed = getattr(mgr_module, 'generate_embedding', None)
        mgr_module.generate_embedding = lambda text: _fake_embedding(text)

        try:
            res = mgr.refresh_data(force=True)
            test("refresh_data returns dict", isinstance(res, dict), f"Got {type(res)}")
            test("refresh_data success", res.get("success") is True, f"Got {res}")
            # Phase 5: metrics now nested under 'metrics' key
            metrics = res.get("metrics", {})
            test("entity_count >= 1", metrics.get("entity_count", 0) >= 1, f"Got {metrics.get('entity_count')}")

            # Test search
            svc = SchemaOrgService(manager=mgr)

            # Mock embedding for search
            import schema_org.service as svc_module
            svc_module.generate_embedding = lambda text: _fake_embedding(text)

            search_res = svc.semantic_search(
                query="Fruit", search_type="entities", limit=5, similarity_threshold=0.0
            )
            test("search returns items", "items" in search_res, f"Got {search_res.keys()}")
            test("search finds results", len(search_res.get("items", [])) >= 1, f"Got {len(search_res.get('items', []))}")

        finally:
            # Restore
            SchemaOrgManager._download_schema_org = original_download
            if original_embed:
                mgr_module.generate_embedding = original_embed

except Exception as e:
    test("manager_parse_and_populate", False, str(e))

# Test 2: Semantic search uses cache
print("\n2. Testing semantic search cache...")
try:
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test2.db")
        mgr = SchemaOrgManager(db_path=db_path)

        tmp_json = os.path.join(tmp_dir, "sample2.jsonld")
        _write_sample_jsonld(tmp_json)

        SchemaOrgManager._download_schema_org = lambda self: tmp_json

        import schema_org.manager as mgr_module
        import schema_org.service as svc_module
        mgr_module.generate_embedding = lambda text: _fake_embedding(text)
        svc_module.generate_embedding = lambda text: _fake_embedding(text)

        res = mgr.refresh_data(force=True)
        test("refresh_data_2 success", res.get("success") is True, f"Got {res}")

        svc = SchemaOrgService(manager=mgr)
        r1 = svc.semantic_search(query="Fruit", search_type="both", limit=10, similarity_threshold=0.0)
        test("first search returns results", r1.get("total_count", 0) >= 1, f"Got {r1.get('total_count')}")

        r2 = svc.semantic_search(query="Fruit", search_type="both", limit=10, similarity_threshold=0.0)
        test("second search returns same count", r2.get("total_count") == r1.get("total_count"),
             f"Got {r2.get('total_count')} vs {r1.get('total_count')}")

except Exception as e:
    test("semantic_search_cache", False, str(e))

# Test 3: Refresh data validation
print("\n3. Testing refresh data validation...")
try:
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test3.db")
        mgr = SchemaOrgManager(db_path=db_path)

        tmp_json = os.path.join(tmp_dir, "sample3.jsonld")
        _write_sample_jsonld(tmp_json)

        SchemaOrgManager._download_schema_org = lambda self: tmp_json

        import schema_org.manager as mgr_module
        mgr_module.generate_embedding = lambda text: _fake_embedding(text)

        res = mgr.refresh_data(force=True)
        test("refresh_data_3 success", res.get("success") is True, f"Got {res}")
        # Phase 5: metrics now nested under 'metrics' key
        metrics = res.get("metrics", {})
        test("entity_count correct", metrics.get("entity_count", 0) >= 1, f"Got {metrics.get('entity_count')}")

except Exception as e:
    test("refresh_data_validation", False, str(e))

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
    print("\n✓ All schema_org unit tests passed!")
    sys.exit(0)
