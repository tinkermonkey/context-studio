import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

import numpy as np

from schema_org.manager import SchemaOrgManager
from schema_org.service import SchemaOrgService
from schema_org.errors import BackupError


def _fake_embedding(text: str, dim: int = 384) -> bytes:
    # Deterministic lightweight embedding for tests - using 384 dims to match real embeddings
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


def test_manager_parse_and_populate(monkeypatch, tmp_path):
    # Create temporary DB file path
    db_file = tmp_path / "schemaorg_test.db"
    db_path = str(db_file)

    mgr = SchemaOrgManager(db_path=db_path)

    # Prepare sample jsonld file and monkeypatch download to return it
    tmp_json = str(tmp_path / "sample.jsonld")
    _write_sample_jsonld(tmp_json)
    monkeypatch.setattr(SchemaOrgManager, "_download_schema_org", lambda self: tmp_json)

    # Monkeypatch embedding generator used by the manager to deterministic lightweight embeddings
    monkeypatch.setattr(
        "schema_org.manager.generate_embedding", lambda text: _fake_embedding(text)
    )

    # Run refresh (population)
    res = mgr.refresh_data(force=True)
    assert isinstance(res, dict)
    assert res.get("success") is True

    # Service should be able to read entities
    svc = SchemaOrgService(manager=mgr)
    search_res = svc.semantic_search(
        query="Fruit", search_type="entities", limit=5, similarity_threshold=0.0
    )
    assert "items" in search_res
    assert len(search_res["items"]) >= 1
    titles = [it.get("title") for it in search_res["items"]]
    assert any("Fruit" in t for t in titles if t)


def test_semantic_search_fallback_uses_cache(monkeypatch, tmp_path):
    db_file = tmp_path / "schemaorg_test2.db"
    db_path = str(db_file)
    mgr = SchemaOrgManager(db_path=db_path)

    # Create and populate minimal DB via direct manager population
    tmp_json = str(tmp_path / "sample2.jsonld")
    _write_sample_jsonld(tmp_json)
    monkeypatch.setattr(SchemaOrgManager, "_download_schema_org", lambda self: tmp_json)

    monkeypatch.setattr(
        "schema_org.manager.generate_embedding", lambda text: _fake_embedding(text)
    )

    res = mgr.refresh_data(force=True)
    assert res.get("success") is True

    svc = SchemaOrgService(manager=mgr)
    # Ensure first call populates the embedding cache and returns results
    r1 = svc.semantic_search(
        query="Fruit", search_type="both", limit=10, similarity_threshold=0.0
    )
    assert r1["total_count"] >= 1

    # Second call should hit the in-memory cache path and return same results
    r2 = svc.semantic_search(
        query="Fruit", search_type="both", limit=10, similarity_threshold=0.0
    )
    assert r2["total_count"] == r1["total_count"]


def test_refresh_handles_backup_failure(monkeypatch, tmp_path):
    db_file = tmp_path / "schemaorg_test3.db"
    db_path = str(db_file)
    mgr = SchemaOrgManager(db_path=db_path)

    # Force _create_backup to raise BackupError
    monkeypatch.setattr(
        SchemaOrgManager,
        "_create_backup",
        lambda self: (_ for _ in ()).throw(BackupError("permission_denied")),
    )

    # Call refresh_data and expect it to return a dict with backup_failed
    res = mgr.refresh_data(force=True)
    assert res.get("success") is False
    assert "backup_failed" in res.get("message", "")
