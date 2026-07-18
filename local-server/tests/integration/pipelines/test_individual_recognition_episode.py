"""
End-to-end recognition measurement over a multi-document episode (issue #1142, Phase 3).

Isolates RECOGNITION from LLM-extraction variance: it feeds the ground-truth
mentions (from expected_entities.json) directly through the recognition step +
individual index, document by document with a shared accumulating graph, and
scores the resulting cross-document clustering. Uses real (offline, cached)
embeddings — recognition is non-LLM, so no cassettes are needed. The
LLM-extraction-integrated path (with cassettes) is a follow-up.

The load-bearing assertion is PRECISION (no false merges); recall/F1 are reported
for the first numbers and tuned in Phase 4.
"""

import json
import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tests.integration.pipelines._harness.metrics import recognition_metrics

_EPISODES = Path(__file__).parent.parent / "fixtures" / "pipelines" / "individual_recognition"


def _typing_triple(surface, class_ref):
    return {
        "subject": {"kind": "individual", "id": None, "label": surface},
        "predicate": {"label": "is_a"},
        "object": {"kind": "class", "label": class_ref},
    }


def _build_service_over_dr():
    """DR ontology in a fresh in-memory graph + a real individual vector index."""
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    sys.path.append(str(Path(__file__).parent))
    from tests.integration.pipelines.conftest import _find_dr_spec_dir

    if _find_dr_spec_dir() is None:
        pytest.skip("DR spec checkout not available")

    from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
    from adapters.events.in_process import InProcessEventPublisher
    from adapters.persistence.sqlite.connection import (
        create_local_db_engine,
        create_session_factory,
    )
    from adapters.persistence.sqlite.individual_vector_index import SqliteIndividualVectorIndex
    from adapters.persistence.sqlite.models import Base
    from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
    from domain.extraction.services import ExtractionService
    from domain.ontology.services import OntologyService
    from scripts.import_dr_ontology import import_dr_ontology

    try:
        emb = SentenceTransformerEmbedding()
        emb.embed("warmup")
    except Exception as exc:
        pytest.skip(f"SentenceTransformer unavailable offline: {exc}")

    engine = create_local_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    repo = SQLiteOntologyRepository(session_factory)
    ontology_service = OntologyService(
        repository=repo, embedding_service=emb,
        event_publisher=InProcessEventPublisher(), schema_index=None,
    )
    import_dr_ontology(ontology_service, repo, _find_dr_spec_dir())
    index = SqliteIndividualVectorIndex(session_factory, emb)

    from unittest.mock import Mock

    service = ExtractionService(
        ontology_repo=repo, embedding_service=emb, llm=Mock(), nlp=Mock(),
        reference_sources=[], event_publisher=Mock(), extraction_repo=Mock(),
        extraction_run_repo=Mock(), individual_index=index,
    )
    return service, repo, index, emb


def test_recognition_episode_kubernetes_energy():
    service, repo, index, _emb = _build_service_over_dr()
    from domain.ontology.entities import Individual

    tax = repo.list_taxonomies()[0]
    by_alias, _ = service._class_index(tax)
    expected = json.load(open(_EPISODES / "kubernetes_energy" / "expected_entities.json"))

    docs = sorted({m["doc"] for e in expected for m in e["mentions"]})
    records = []
    for doc in docs:
        doc_mentions = [(e, m) for e in expected for m in e["mentions"] if m["doc"] == doc]
        triples = [_typing_triple(m["surface"], e["class_ref"]) for e, m in doc_mentions]
        service._recognize_individuals(triples, tax)
        for (entity, mention), triple in zip(doc_mentions, triples):
            subject = triple["subject"]
            if subject.get("id"):
                node_id, title = subject["id"], subject["label"]
            else:
                cls = by_alias.get(entity["class_ref"].strip().lower())
                assert cls is not None, f"class_ref {entity['class_ref']} not in DR ontology"
                node_id = str(uuid4())
                repo.save_individual(
                    Individual(id=node_id, class_ids=[str(cls.id)], title=mention["surface"])
                )
                index.index_individual(node_id, mention["surface"], None)
                title = mention["surface"]
            records.append({
                "entity_key": entity["entity_key"],
                "canonical_title": entity["canonical_title"],
                "node_id": node_id,
                "title": title,
            })

    metrics = recognition_metrics(records)
    print(
        f"\n── recognition (kubernetes_energy) ──\n"
        f"  dedup_precision={metrics.dedup_precision}  dedup_recall={metrics.dedup_recall}  "
        f"dedup_f1={metrics.dedup_f1}\n"
        f"  resolution_accuracy={metrics.resolution_accuracy}  "
        f"node_count_ratio={metrics.node_count_ratio}  "
        f"canonical_label_accuracy={metrics.canonical_label_accuracy}\n"
        f"  gt_entities={metrics.gt_entity_count}  predicted_nodes={metrics.predicted_node_count}"
    )

    # Precision is the safety guarantee: no false merges of distinct entities.
    assert metrics.dedup_precision >= 0.9, f"false merges: {metrics}"
