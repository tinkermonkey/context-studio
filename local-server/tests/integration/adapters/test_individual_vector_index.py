"""
Integration tests for SqliteIndividualVectorIndex (recognition, issue #1142).

Two layers:
- Deterministic mechanics (fake orthogonal vectors): class-scoping, threshold,
  ranking, remove, reindex — the adapter contract, no model load.
- A real-embedding proof that specific->specific retrieval is strong: an
  extracted "K8s" mention resolves to an existing "Kubernetes" individual with a
  clear margin, while a wrong-class candidate is excluded. This is the hypothesis
  the #1141 typing smoke could NOT satisfy for specific->generic, validated here
  for specific->specific.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from adapters.persistence.sqlite.individual_vector_index import SqliteIndividualVectorIndex
from adapters.persistence.sqlite.models import Base, IndividualClass, OntologyEntity

CLASS_SW = "11111111-1111-1111-1111-111111111111"  # System Software
CLASS_DB = "22222222-2222-2222-2222-222222222222"  # Data store
KUBERNETES = "aaaaaaaa-0000-0000-0000-000000000001"
NEXTFLOW = "aaaaaaaa-0000-0000-0000-000000000002"
POSTGRES = "aaaaaaaa-0000-0000-0000-000000000003"


def _seed(factory, individuals):
    """individuals: list of (id, title, [class_ids])."""
    with factory() as session:
        session.add_all(
            [
                OntologyEntity(id=CLASS_SW, node_type="class", title="System Software"),
                OntologyEntity(id=CLASS_DB, node_type="class", title="Data Store"),
            ]
        )
        for ind_id, title, class_ids in individuals:
            session.add(OntologyEntity(id=ind_id, node_type="individual", title=title))
            for pos, cid in enumerate(class_ids):
                session.add(IndividualClass(individual_id=ind_id, class_id=cid, position=pos))
        session.commit()


class _FakeEmbedding:
    """Deterministic text->vector map (3-dim)."""

    def __init__(self, vectors):
        self._vectors = vectors

    def embed(self, text):
        return self._vectors.get(text, [0.0, 0.0, 0.0])

    def embed_batch(self, texts):
        return [self.embed(t) for t in texts]


@pytest.fixture
def factory():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_engine(f"sqlite:///{Path(tmpdir) / 'test.db'}")
        Base.metadata.create_all(engine)
        yield sessionmaker(bind=engine)


class TestMechanics:
    _VECTORS = {
        "Kubernetes": [1.0, 0.0, 0.0],
        "Nextflow": [0.0, 1.0, 0.0],
        "PostgreSQL": [0.0, 0.0, 1.0],
        "k8s": [0.98, 0.02, 0.0],   # close to Kubernetes
    }

    def _index(self, factory):
        _seed(
            factory,
            [
                (KUBERNETES, "Kubernetes", [CLASS_SW]),
                (NEXTFLOW, "Nextflow", [CLASS_SW]),
                (POSTGRES, "PostgreSQL", [CLASS_DB]),
            ],
        )
        idx = SqliteIndividualVectorIndex(factory, _FakeEmbedding(self._VECTORS))
        assert idx.reindex_all_individuals() == 3
        return idx

    def test_resolves_a_variant_to_the_right_individual_scoped_to_its_class(self, factory):
        idx = self._index(factory)
        matches = idx.search(self._VECTORS["k8s"], class_ids=[CLASS_SW], top_k=5, threshold=0.5)
        assert matches, "expected a match for k8s"
        assert matches[0].individual_id == KUBERNETES
        assert matches[0].title == "Kubernetes"
        assert CLASS_SW in matches[0].class_ids
        # clear margin over the next candidate
        if len(matches) > 1:
            assert matches[0].score - matches[1].score > 0.1

    def test_class_scoping_excludes_individuals_of_other_classes(self, factory):
        idx = self._index(factory)
        # query is closest to Kubernetes (a System Software), but scope to Data Store
        matches = idx.search(self._VECTORS["k8s"], class_ids=[CLASS_DB], top_k=5, threshold=0.0)
        assert all(m.individual_id != KUBERNETES for m in matches)

    def test_threshold_prunes_weak_matches(self, factory):
        idx = self._index(factory)
        # PostgreSQL is orthogonal to the k8s query -> score 0, excluded by threshold
        matches = idx.search(self._VECTORS["k8s"], class_ids=[CLASS_SW], top_k=5, threshold=0.5)
        assert all(m.individual_id != POSTGRES for m in matches)

    def test_remove_drops_the_individual(self, factory):
        idx = self._index(factory)
        idx.remove_individual(KUBERNETES)
        matches = idx.search(self._VECTORS["k8s"], class_ids=[CLASS_SW], top_k=5, threshold=0.5)
        assert all(m.individual_id != KUBERNETES for m in matches)


class TestRealEmbeddingRecognition:
    """The load-bearing hypothesis: specific mention -> existing specific individual."""

    def test_k8s_resolves_to_kubernetes_with_a_clear_margin(self, factory):
        # Load the (cached) model offline — the test harness blocks network, and
        # the tournament runs the same way (HF_HUB_OFFLINE). Skip cleanly if the
        # model isn't cached in this environment.
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding

        try:
            emb = SentenceTransformerEmbedding()
            emb.embed("warmup")
        except Exception as exc:  # model not cached offline in this env
            pytest.skip(f"SentenceTransformer model unavailable offline: {exc}")
        _seed(
            factory,
            [
                (KUBERNETES, "Kubernetes", [CLASS_SW]),
                (NEXTFLOW, "Nextflow", [CLASS_SW]),
                (POSTGRES, "PostgreSQL", [CLASS_DB]),
            ],
        )
        idx = SqliteIndividualVectorIndex(factory, emb)
        idx.reindex_all_individuals()

        matches = idx.search(
            emb.embed("K8s"), class_ids=[CLASS_SW], top_k=5, threshold=0.0
        )
        assert matches, "expected candidates within the System Software class"
        assert matches[0].individual_id == KUBERNETES, (
            f"K8s should resolve to Kubernetes, got {matches[0].title}"
        )
        # a usable recognition margin over the next same-class candidate (Nextflow)
        assert len(matches) >= 2
        assert matches[0].score - matches[1].score > 0.1, (
            f"insufficient margin: {[(m.title, round(m.score, 3)) for m in matches[:2]]}"
        )
