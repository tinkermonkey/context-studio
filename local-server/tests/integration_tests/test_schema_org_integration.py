import sys
import os
import json

# Ensure project root is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))


from schema_org.manager import SchemaOrgManager
from schema_org import api as schema_org_api
from schema_org.service import SchemaOrgService

# Use triage helper to create a test app with migrations applied (ensures vec tables pattern)
from triage_scripts.triage_helper import (
    create_test_app_with_migrations,
    create_test_client,
    cleanup_test_database,
)


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


def test_schema_org_endpoints_flow(tmp_path, monkeypatch):
    # Create a test FastAPI app + DB with migrations applied (triage helper)
    app, test_db_fd, test_db_path, engine, TestingSessionLocal = (
        create_test_app_with_migrations()
    )
    client = create_test_client(app)

    try:
        # Bind SchemaOrgManager to the test DB and inject into API module
        mgr = SchemaOrgManager(db_path=str(test_db_path))
        schema_org_api.manager = mgr
        schema_org_api.service = SchemaOrgService(manager=mgr)

        # monkeypatch download to return our sample
        sample_file = str(tmp_path / "sample_integ.jsonld")
        _write_sample_jsonld(sample_file)
        import shutil
        import tempfile

        def _fake_download(self):
            tf = tempfile.NamedTemporaryFile(delete=False, suffix=".jsonld")
            tf.close()
            shutil.copy2(sample_file, tf.name)
            return tf.name

        monkeypatch.setattr(SchemaOrgManager, "_download_schema_org", _fake_download)

        # deterministic non-zero embedding bytes to avoid zero-norm
        import struct

        def _deterministic_embedding(text: str):
            vals = [0.1] * 8
            return struct.pack("f" * len(vals), *vals)

        monkeypatch.setattr(
            "embeddings.generate_embeddings.generate_embedding",
            _deterministic_embedding,
        )
        monkeypatch.setattr(
            "schema_org.manager.generate_embedding", _deterministic_embedding
        )

        # Trigger refresh via API
        resp = client.post("/api/schema-org/refresh")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True

        # Check status endpoint
        resp = client.get("/api/schema-org/status")
        assert resp.status_code == 200
        status = resp.json()
        assert status.get("is_populated") is True

        # Query semantic search (should return items)
        resp = client.get(
            "/api/schema-org/search",
            params={
                "query": "Fruit",
                "search_type": "both",
                "similarity_threshold": 0.0,
            },
        )
        assert resp.status_code == 200
        sdata = resp.json()
        assert sdata.get("total_count", 0) >= 1

        # Test that vector search functionality works (which requires vec tables to exist)
        # This is the same approach used in test_vec_layers.py - test the functionality, not table existence
        resp = client.get(
            "/api/schema-org/search",
            params={
                "query": "Fruit",
                "search_type": "entities",
                "similarity_threshold": 0.0,
                "limit": 5,
            },
        )
        assert resp.status_code == 200
        sdata = resp.json()

        # Should find the "Fruit" entity via vector similarity
        assert (
            sdata.get("total_count", 0) >= 1
        ), "Vector search should find the Fruit entity"
        items = sdata.get("items", [])
        assert len(items) >= 1, "Vector search should return at least one item"

        # Verify the found entity matches our test data
        fruit_entity = items[0]
        assert (
            fruit_entity.get("title") == "Fruit"
        ), f"Expected 'Fruit', got '{fruit_entity.get('title')}'"

        # Test property vector search as well
        resp = client.get(
            "/api/schema-org/search",
            params={
                "query": "color",
                "search_type": "properties",
                "similarity_threshold": 0.0,
                "limit": 5,
            },
        )
        assert resp.status_code == 200
        pdata = resp.json()

        # Should find the "color" property via vector similarity
        assert (
            pdata.get("total_count", 0) >= 1
        ), "Vector search should find the color property"
        pitems = pdata.get("items", [])
        assert len(pitems) >= 1, "Vector search should return at least one property"

        # Verify the found property matches our test data
        color_prop = pitems[0]
        assert (
            color_prop.get("title") == "color"
        ), f"Expected 'color', got '{color_prop.get('title')}'"
    finally:
        # cleanup temporary DB created by triage helper
        try:
            cleanup_test_database(test_db_fd, test_db_path)
        except Exception:
            pass
