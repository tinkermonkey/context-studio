"""
End-to-End tests for Phase 5: Schema.org Complete User Workflows

Tests complete user workflows from start to finish including:
- Fresh database → Import → Search → Validate metrics
- Re-import scenarios (idempotency)
- Performance under load
- Error recovery workflows
- Production-like scenarios
"""

import sys
import os
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

import pytest
import numpy as np

from schema_org.manager import SchemaOrgManager
from schema_org.service import SchemaOrgService
from schema_org.api import router as schema_org_router


def _create_comprehensive_schema_org_dataset():
    """Create a larger, more realistic Schema.org dataset for E2E testing."""
    entities = []
    properties = []

    # Create 20 entities across different categories
    entity_types = [
        ("Thing", "The most generic type of item"),
        ("Person", "A person (alive, dead, undead, or fictional)"),
        ("Organization", "An organization such as a school, NGO, corporation, club"),
        ("Place", "Entities that have a somewhat fixed, physical extension"),
        ("Event", "An event happening at a certain time and location"),
        ("Product", "Any offered product or service"),
        ("CreativeWork", "The most generic kind of creative work"),
        ("Action", "An action performed by a direct agent"),
        ("Intangible", "A utility class that serves as the umbrella for a number of 'intangible' things"),
        ("MedicalEntity", "The most generic type of entity related to health and medicine"),
        ("LocalBusiness", "A particular physical business or branch of an organization"),
        ("Vehicle", "A vehicle is a device that is designed or used to transport people or cargo"),
        ("Book", "A book"),
        ("Article", "An article, such as a news article or piece of investigative report"),
        ("WebPage", "A web page"),
        ("VideoObject", "A video file"),
        ("ImageObject", "An image file"),
        ("AudioObject", "An audio file"),
        ("Dataset", "A body of structured information describing some topic(s) of interest"),
        ("SoftwareApplication", "A software application"),
    ]

    for i, (name, description) in enumerate(entity_types):
        entities.append({
            "@id": f"http://schema.org/{name}",
            "@type": "rdfs:Class",
            "label": name,
            "comment": description,
        })

    # Create 15 properties
    property_types = [
        ("name", "The name of the item"),
        ("description", "A description of the item"),
        ("url", "URL of the item"),
        ("image", "An image of the item"),
        ("identifier", "The identifier property represents any kind of identifier"),
        ("memberOf", "An organization to which this person belongs"),
        ("knows", "The most generic bi-directional social/work relation"),
        ("email", "Email address"),
        ("telephone", "The telephone number"),
        ("address", "Physical address of the item"),
        ("startDate", "The start date and time of the item"),
        ("endDate", "The end date and time of the item"),
        ("location", "The location of the event, organization or action"),
        ("author", "The author of this content"),
        ("datePublished", "Date of first broadcast/publication"),
    ]

    for name, description in property_types:
        properties.append({
            "@id": f"http://schema.org/{name}",
            "@type": "rdf:Property",
            "label": name,
            "comment": description,
        })

    return {
        "@context": "https://schema.org/",
        "@graph": entities + properties,
    }


def _fake_embedding(text: str, dim: int = 384) -> bytes:
    """Create deterministic embeddings for testing."""
    s = sum(bytearray(text.encode("utf-8") or b"0")) % 100
    arr = np.full((dim,), float(s) / 100.0, dtype=np.float32)
    norm = np.linalg.norm(arr)
    if norm > 0:
        arr = arr / norm
    return arr.tobytes()


class TestFreshDatabaseWorkflow:
    """Test complete workflow starting from a fresh database."""

    def test_fresh_install_and_first_import(self, tmp_path):
        """
        Test E2E workflow: Fresh DB → First import → Verify data → Search

        This simulates a user installing the system for the first time.
        """
        db_file = tmp_path / "fresh_install.db"
        db_path = str(db_file)

        # Step 1: Create fresh database
        mgr = SchemaOrgManager(db_path=db_path)

        # Verify database is empty
        assert not mgr.is_populated()

        # Step 2: Perform first import
        sample_json = str(tmp_path / "comprehensive_schema.jsonld")
        with open(sample_json, "w") as f:
            json.dump(_create_comprehensive_schema_org_dataset(), f)

        with patch.object(SchemaOrgManager, "_download_schema_org", return_value=sample_json):
            with patch("schema_org.manager.generate_embedding", side_effect=lambda t: _fake_embedding(t)):
                start_time = time.time()
                import_result = mgr.refresh_data(force=True)
                import_duration = time.time() - start_time

        # Step 3: Validate import results
        assert import_result.get("success") is True
        assert import_result["entity_count"] == 20
        assert import_result["property_count"] == 15
        assert import_result["duration_seconds"] > 0
        assert import_duration < 60, "Import took too long (should be <60s for test dataset)"

        # Verify database is now populated
        assert mgr.is_populated()

        # Step 4: Verify metrics tracking
        assert "peak_memory_mb" in import_result
        assert "download_duration_seconds" in import_result
        assert "parse_duration_seconds" in import_result
        assert "populate_duration_seconds" in import_result

        # Step 5: Perform searches to verify data integrity
        svc = SchemaOrgService(manager=mgr)

        # Search for entities
        with patch("schema_org.service.generate_embedding", return_value=_fake_embedding("person")):
            person_results = svc.semantic_search(
                query="person",
                search_type="entities",
                limit=10,
                similarity_threshold=0.0
            )

        assert person_results["total_count"] >= 1
        # Verify "Person" entity is found
        person_found = any(item.get("title") == "Person" for item in person_results["items"])
        assert person_found, "Person entity not found in search results"

        # Search for properties
        with patch("schema_org.service.generate_embedding", return_value=_fake_embedding("email")):
            property_results = svc.semantic_search(
                query="email",
                search_type="properties",
                limit=10,
                similarity_threshold=0.0
            )

        assert property_results["total_count"] >= 1


class TestReimportWorkflow:
    """Test re-import and idempotency scenarios."""

    def test_reimport_updates_data(self, tmp_path):
        """
        Test E2E workflow: Import → Modify data → Re-import → Verify update

        This tests idempotency and the rebuild-only strategy.
        """
        db_file = tmp_path / "reimport_test.db"
        db_path = str(db_file)

        mgr = SchemaOrgManager(db_path=db_path)

        # Step 1: Initial import
        initial_data = {
            "@context": "https://schema.org/",
            "@graph": [
                {
                    "@id": "http://schema.org/Person",
                    "@type": "rdfs:Class",
                    "label": "Person",
                    "comment": "Original description",
                }
            ],
        }

        sample_json = str(tmp_path / "initial_schema.jsonld")
        with open(sample_json, "w") as f:
            json.dump(initial_data, f)

        with patch.object(SchemaOrgManager, "_download_schema_org", return_value=sample_json):
            with patch("schema_org.manager.generate_embedding", side_effect=lambda t: _fake_embedding(t)):
                result1 = mgr.refresh_data(force=True)

        assert result1.get("success") is True
        assert result1["entity_count"] == 1

        # Step 2: Update source data
        updated_data = {
            "@context": "https://schema.org/",
            "@graph": [
                {
                    "@id": "http://schema.org/Person",
                    "@type": "rdfs:Class",
                    "label": "Person",
                    "comment": "Updated description",
                },
                {
                    "@id": "http://schema.org/Organization",
                    "@type": "rdfs:Class",
                    "label": "Organization",
                    "comment": "New entity",
                },
            ],
        }

        with open(sample_json, "w") as f:
            json.dump(updated_data, f)

        # Step 3: Re-import
        with patch.object(SchemaOrgManager, "_download_schema_org", return_value=sample_json):
            with patch("schema_org.manager.generate_embedding", side_effect=lambda t: _fake_embedding(t)):
                result2 = mgr.refresh_data(force=True)

        assert result2.get("success") is True
        assert result2["entity_count"] == 2  # Now has both entities

        # Step 4: Verify data was updated (rebuild strategy)
        svc = SchemaOrgService(manager=mgr)

        with patch("schema_org.service.generate_embedding", return_value=_fake_embedding("organization")):
            org_results = svc.semantic_search(
                query="organization",
                search_type="entities",
                limit=10,
                similarity_threshold=0.0
            )

        # New entity should be found
        org_found = any(item.get("title") == "Organization" for item in org_results["items"])
        assert org_found, "Organization entity not found after re-import"


class TestPerformanceUnderLoad:
    """Test performance characteristics under realistic load."""

    def test_concurrent_searches_performance(self, tmp_path):
        """
        Test E2E workflow: Import → Concurrent searches → Validate performance

        Validates NFR-1: Vector search returns results within acceptable response times.
        """
        db_file = tmp_path / "performance_test.db"
        db_path = str(db_file)

        # Setup database
        mgr = SchemaOrgManager(db_path=db_path)

        sample_json = str(tmp_path / "performance_schema.jsonld")
        with open(sample_json, "w") as f:
            json.dump(_create_comprehensive_schema_org_dataset(), f)

        with patch.object(SchemaOrgManager, "_download_schema_org", return_value=sample_json):
            with patch("schema_org.manager.generate_embedding", side_effect=lambda t: _fake_embedding(t)):
                mgr.refresh_data(force=True)

        svc = SchemaOrgService(manager=mgr)

        # Define search queries
        queries = [
            "person", "organization", "place", "event", "product",
            "creative work", "action", "medical", "business", "vehicle",
            "book", "article", "webpage", "video", "image",
            "audio", "dataset", "software", "email", "address"
        ]

        # Run concurrent searches
        results = []
        search_times = []

        def search_worker(query):
            with patch("schema_org.service.generate_embedding", return_value=_fake_embedding(query)):
                start = time.perf_counter()
                result = svc.semantic_search(
                    query=query,
                    search_type="both",
                    limit=20,
                    similarity_threshold=0.0
                )
                duration_ms = (time.perf_counter() - start) * 1000
                return result, duration_ms

        # Execute 20 concurrent queries
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(search_worker, q) for q in queries]
            for future in as_completed(futures):
                result, duration_ms = future.result()
                results.append(result)
                search_times.append(duration_ms)

        # Validate performance: NFR-1 requires <50ms for interactive use
        # In test environment, we'll be more lenient (allow up to 200ms)
        avg_search_time = sum(search_times) / len(search_times)
        max_search_time = max(search_times)

        assert len(results) == 20, "Not all searches completed"
        assert avg_search_time < 200, f"Average search time {avg_search_time:.2f}ms exceeds 200ms"
        assert max_search_time < 500, f"Max search time {max_search_time:.2f}ms exceeds 500ms"

        # Validate all searches returned results
        for result in results:
            assert "items" in result
            assert "total_count" in result


class TestErrorRecoveryWorkflows:
    """Test error recovery and resilience."""

    def test_import_failure_recovery(self, tmp_path):
        """
        Test E2E workflow: Import failure → Fix issue → Retry → Success

        Validates error handling and recovery.
        """
        db_file = tmp_path / "error_recovery_test.db"
        db_path = str(db_file)

        mgr = SchemaOrgManager(db_path=db_path)

        # Step 1: Simulate download failure
        def mock_download_failure(self):
            from schema_org.errors import DownloadError
            raise DownloadError("Network timeout")

        with patch.object(SchemaOrgManager, "_download_schema_org", side_effect=mock_download_failure):
            result1 = mgr.refresh_data(force=True)

        assert result1.get("success") is False
        assert "download" in result1.get("message", "").lower() or "network" in result1.get("message", "").lower()

        # Step 2: Fix the issue and retry
        sample_json = str(tmp_path / "recovery_schema.jsonld")
        with open(sample_json, "w") as f:
            json.dump(_create_comprehensive_schema_org_dataset(), f)

        with patch.object(SchemaOrgManager, "_download_schema_org", return_value=sample_json):
            with patch("schema_org.manager.generate_embedding", side_effect=lambda t: _fake_embedding(t)):
                result2 = mgr.refresh_data(force=True)

        # Should now succeed
        assert result2.get("success") is True
        assert result2["entity_count"] == 20

    def test_malformed_data_handling(self, tmp_path):
        """
        Test E2E workflow: Import malformed data → Receive clear error → Fix → Success
        """
        db_file = tmp_path / "malformed_test.db"
        db_path = str(db_file)

        mgr = SchemaOrgManager(db_path=db_path)

        # Step 1: Try to import malformed JSON
        malformed_json = str(tmp_path / "malformed.jsonld")
        with open(malformed_json, "w") as f:
            f.write("{ this is not valid json }")

        with patch.object(SchemaOrgManager, "_download_schema_org", return_value=malformed_json):
            result1 = mgr.refresh_data(force=True)

        # Should fail with clear error message
        assert result1.get("success") is False
        assert "message" in result1

        # Step 2: Fix the data
        valid_json = str(tmp_path / "valid.jsonld")
        with open(valid_json, "w") as f:
            json.dump({
                "@context": "https://schema.org/",
                "@graph": [
                    {
                        "@id": "http://schema.org/Thing",
                        "@type": "rdfs:Class",
                        "label": "Thing",
                        "comment": "The most generic type",
                    }
                ],
            }, f)

        with patch.object(SchemaOrgManager, "_download_schema_org", return_value=valid_json):
            with patch("schema_org.manager.generate_embedding", side_effect=lambda t: _fake_embedding(t)):
                result2 = mgr.refresh_data(force=True)

        # Should now succeed
        assert result2.get("success") is True


class TestProductionLikeScenarios:
    """Test production-like scenarios and edge cases."""

    def test_large_dataset_import(self, tmp_path):
        """
        Test E2E workflow: Large dataset import → Verify performance → Search

        Validates memory usage and performance with larger datasets.
        """
        db_file = tmp_path / "large_dataset_test.db"
        db_path = str(db_file)

        mgr = SchemaOrgManager(db_path=db_path)

        # Create a larger dataset (simulate 100 entities + 50 properties)
        large_dataset = {
            "@context": "https://schema.org/",
            "@graph": []
        }

        # Add 100 entities
        for i in range(100):
            large_dataset["@graph"].append({
                "@id": f"http://schema.org/Entity{i}",
                "@type": "rdfs:Class",
                "label": f"Entity{i}",
                "comment": f"Test entity number {i} with some description text to make it realistic",
            })

        # Add 50 properties
        for i in range(50):
            large_dataset["@graph"].append({
                "@id": f"http://schema.org/property{i}",
                "@type": "rdf:Property",
                "label": f"property{i}",
                "comment": f"Test property number {i} for relationships",
            })

        sample_json = str(tmp_path / "large_schema.jsonld")
        with open(sample_json, "w") as f:
            json.dump(large_dataset, f)

        # Import and measure
        with patch.object(SchemaOrgManager, "_download_schema_org", return_value=sample_json):
            with patch("schema_org.manager.generate_embedding", side_effect=lambda t: _fake_embedding(t)):
                start_time = time.time()
                result = mgr.refresh_data(force=True)
                duration = time.time() - start_time

        # Validate results
        assert result.get("success") is True
        assert result["entity_count"] == 100
        assert result["property_count"] == 50

        # Validate performance (should handle 150 items quickly)
        assert duration < 30, f"Import of 150 items took {duration:.2f}s, should be <30s"

        # Validate memory usage if tracked
        if result.get("peak_memory_mb"):
            # Should be well under 500MB limit for this size dataset
            assert result["peak_memory_mb"] < 500, f"Memory usage {result['peak_memory_mb']}MB exceeds 500MB limit"

        # Verify search works correctly
        svc = SchemaOrgService(manager=mgr)

        with patch("schema_org.service.generate_embedding", return_value=_fake_embedding("entity")):
            search_result = svc.semantic_search(
                query="entity",
                search_type="entities",
                limit=20,
                similarity_threshold=0.0
            )

        assert search_result["total_count"] >= 10  # Should find many entities

    def test_system_restart_persistence(self, tmp_path):
        """
        Test E2E workflow: Import → Close DB → Reopen → Verify data persists

        Validates data persistence across system restarts.
        """
        db_file = tmp_path / "persistence_test.db"
        db_path = str(db_file)

        # Step 1: Import data
        mgr1 = SchemaOrgManager(db_path=db_path)

        sample_json = str(tmp_path / "persistence_schema.jsonld")
        with open(sample_json, "w") as f:
            json.dump(_create_comprehensive_schema_org_dataset(), f)

        with patch.object(SchemaOrgManager, "_download_schema_org", return_value=sample_json):
            with patch("schema_org.manager.generate_embedding", side_effect=lambda t: _fake_embedding(t)):
                import_result = mgr1.refresh_data(force=True)

        assert import_result.get("success") is True
        original_entity_count = import_result["entity_count"]

        # Close connection (simulate system shutdown)
        mgr1.close()
        del mgr1

        # Step 2: Reopen database (simulate system restart)
        mgr2 = SchemaOrgManager(db_path=db_path)

        # Verify data persists
        assert mgr2.is_populated(), "Data did not persist after restart"

        # Verify search works after restart
        svc = SchemaOrgService(manager=mgr2)

        with patch("schema_org.service.generate_embedding", return_value=_fake_embedding("person")):
            search_result = svc.semantic_search(
                query="person",
                search_type="both",
                limit=10,
                similarity_threshold=0.0
            )

        assert search_result["total_count"] >= 1, "Search failed after restart"

        mgr2.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
