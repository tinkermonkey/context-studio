"""
Integration tests for SqliteSchemaVectorIndex.

Uses a real temp SQLite database (full ORM schema) and a deterministic fake
embedding service with hand-crafted orthogonal vectors, so similarity outcomes
are predictable without loading the SentenceTransformer model.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import adapters.persistence.sqlite.schema_vector_index as svi_module
from adapters.persistence.sqlite.mappers import _serialize_embedding
from adapters.persistence.sqlite.models import Base, OntologyEntity
from adapters.persistence.sqlite.models import Relationship as RelationshipORM
from adapters.persistence.sqlite.schema_vector_index import SqliteSchemaVectorIndex

# Deterministic 3-dim embeddings keyed by exact text.
_VECTORS = {
    "Microservice": [1.0, 0.0, 0.0],
    "An independently deployable service": [0.9, 0.1, 0.0],
    "Database": [0.0, 1.0, 0.0],
    "A persistent data store": [0.0, 0.9, 0.1],
    "connects to": [0.0, 0.0, 1.0],
    "links one service to another": [0.1, 0.0, 0.9],
}


class FakeEmbedding:
    """Deterministic embedding service backed by a fixed text→vector map."""

    def embed(self, text: str) -> list[float]:
        return _VECTORS.get(text, [0.0, 0.0, 0.0])

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]

    def similarity(self, a, b):  # unused by the index
        raise NotImplementedError


CLASS_A = "11111111-1111-1111-1111-111111111111"
CLASS_B = "22222222-2222-2222-2222-222222222222"
PROP_P = "33333333-3333-3333-3333-333333333333"
REL_R = "44444444-4444-4444-4444-444444444444"


@pytest.fixture
def index():
    """A SqliteSchemaVectorIndex over a seeded temp DB, already reindexed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_engine(f"sqlite:///{Path(tmpdir) / 'test.db'}")
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine)

        with factory() as session:
            session.add_all(
                [
                    OntologyEntity(
                        id=CLASS_A,
                        node_type="class",
                        title="Microservice",
                        description="An independently deployable service",
                    ),
                    OntologyEntity(
                        id=CLASS_B,
                        node_type="class",
                        title="Database",
                        description="A persistent data store",
                    ),
                    OntologyEntity(
                        id=PROP_P,
                        node_type="property_definition",
                        title="connects to",
                        description="links one service to another",
                        identifier="connects_to",
                    ),
                ]
            )
            session.add(
                RelationshipORM(
                    id=REL_R,
                    source_id=CLASS_A,
                    target_id=CLASS_B,
                    property_definition_id=PROP_P,
                )
            )
            session.commit()

        idx = SqliteSchemaVectorIndex(factory, FakeEmbedding())
        idx.reindex_all()
        yield idx


def test_reindex_all_counts_entities():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_engine(f"sqlite:///{Path(tmpdir) / 'test.db'}")
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine)
        with factory() as session:
            session.add(
                OntologyEntity(id=CLASS_A, node_type="class", title="Microservice")
            )
            session.commit()
        idx = SqliteSchemaVectorIndex(factory, FakeEmbedding())
        assert idx.reindex_all() == 1


def test_search_title_match(index):
    matches = index.search([1.0, 0.0, 0.0], kinds=["class"])
    assert matches[0].entity_id == CLASS_A
    assert matches[0].kind == "class"
    assert matches[0].matched_field == "title"
    assert matches[0].score > 0.99


def test_search_definition_can_win(index):
    # Query equals Class B's definition vector → definition beats title.
    matches = index.search([0.0, 0.9, 0.1], kinds=["class"])
    assert matches[0].entity_id == CLASS_B
    assert matches[0].matched_field == "definition"


def test_kinds_filter_excludes_other_kinds(index):
    class_only = index.search([0.0, 0.0, 1.0], kinds=["class"])
    assert all(m.kind == "class" for m in class_only)

    prop_only = index.search([0.0, 0.0, 1.0], kinds=["property_definition"])
    assert prop_only[0].entity_id == PROP_P
    assert prop_only[0].kind == "property_definition"


def test_relationship_matched_via_property_definition(index):
    matches = index.search([0.0, 0.0, 1.0], kinds=["relationship"])
    assert len(matches) == 1
    assert matches[0].entity_id == REL_R
    assert matches[0].kind == "relationship"
    assert matches[0].label == "connects to"


def test_threshold_filters_low_scores(index):
    # Query orthogonal to Microservice's title; high threshold drops weak matches.
    matches = index.search([0.0, 1.0, 0.0], kinds=["class"], threshold=0.9)
    assert all(m.score >= 0.9 for m in matches)
    assert all(m.entity_id != CLASS_A for m in matches)


def test_top_k_limits_results(index):
    matches = index.search([1.0, 1.0, 1.0], kinds=["class", "property_definition"], top_k=1)
    assert len(matches) == 1


def test_empty_query_returns_empty(index):
    assert index.search([0.0, 0.0, 0.0], kinds=["class"]) == []


def test_index_entity_updates_single_row(index):
    # Re-point Class B's title embedding by re-indexing it with new text mapping.
    index.index_entity(CLASS_B, "Microservice", None)  # now embeds to [1,0,0]
    matches = index.search([1.0, 0.0, 0.0], kinds=["class"], threshold=0.99)
    ids = {m.entity_id for m in matches}
    assert CLASS_A in ids and CLASS_B in ids


@pytest.fixture
def index_with_factory():
    """Same seed as ``index``, but also exposes the session factory so tests can
    manipulate raw embedding blobs / is_indexed flags directly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_engine(f"sqlite:///{Path(tmpdir) / 'test.db'}")
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine)

        with factory() as session:
            session.add_all(
                [
                    OntologyEntity(
                        id=CLASS_A,
                        node_type="class",
                        title="Microservice",
                        description="An independently deployable service",
                    ),
                    OntologyEntity(
                        id=CLASS_B,
                        node_type="class",
                        title="Database",
                        description="A persistent data store",
                    ),
                    OntologyEntity(
                        id=PROP_P,
                        node_type="property_definition",
                        title="connects to",
                        description="links one service to another",
                        identifier="connects_to",
                    ),
                ]
            )
            session.add(
                RelationshipORM(
                    id=REL_R,
                    source_id=CLASS_A,
                    target_id=CLASS_B,
                    property_definition_id=PROP_P,
                )
            )
            session.commit()

        idx = SqliteSchemaVectorIndex(factory, FakeEmbedding())
        idx.reindex_all()
        yield idx, factory


def test_is_indexed_false_excludes_entity(index_with_factory):
    idx, factory = index_with_factory
    with factory() as session:
        session.get(OntologyEntity, CLASS_A).is_indexed = False
        session.commit()

    matches = idx.search([1.0, 0.0, 0.0], kinds=["class"])
    assert all(m.entity_id != CLASS_A for m in matches)


def test_is_indexed_false_on_property_excludes_relationship(index_with_factory):
    idx, factory = index_with_factory
    with factory() as session:
        session.get(OntologyEntity, PROP_P).is_indexed = False
        session.commit()

    matches = idx.search([0.0, 0.0, 1.0], kinds=["relationship"])
    assert matches == []


def test_stale_dimension_vector_is_skipped_not_raised(index_with_factory, caplog):
    idx, factory = index_with_factory
    # Overwrite Class A's title with a 4-dim blob; the query is 3-dim.
    with factory() as session:
        session.get(OntologyEntity, CLASS_A).title_embedding = _serialize_embedding(
            [1.0, 0.0, 0.0, 0.0]
        )
        session.commit()

    svi_module._dim_mismatch_warned = False  # allow the one-time warning to fire
    matches = idx.search([1.0, 0.0, 0.0], kinds=["class"])
    # No exception, and the stale (title) field simply did not contribute a
    # title match for Class A.
    assert all(
        not (m.entity_id == CLASS_A and m.matched_field == "title") for m in matches
    )
    assert any("stale dimension" in r.message for r in caplog.records)


def test_zero_norm_candidate_is_skipped(index_with_factory):
    idx, factory = index_with_factory
    # Zero the title vector; the definition vector still scores normally.
    with factory() as session:
        row = session.get(OntologyEntity, CLASS_A)
        row.title_embedding = _serialize_embedding([0.0, 0.0, 0.0])
        session.commit()

    matches = idx.search([1.0, 0.0, 0.0], kinds=["class"])
    class_a = [m for m in matches if m.entity_id == CLASS_A]
    # The zero-norm title is skipped, so any Class A match comes from the
    # definition field (never the zeroed title).
    assert all(m.matched_field == "definition" for m in class_a)


def test_negative_cosine_clamped_to_zero(index_with_factory):
    idx, factory = index_with_factory
    # Anti-parallel title/definition to the query → raw cosine -1, clamped to 0.
    with factory() as session:
        row = session.get(OntologyEntity, CLASS_A)
        row.title_embedding = _serialize_embedding([-1.0, 0.0, 0.0])
        row.definition_embedding = _serialize_embedding([-1.0, 0.0, 0.0])
        session.commit()

    matches = idx.search([1.0, 0.0, 0.0], kinds=["class"], threshold=0.0)
    class_a = [m for m in matches if m.entity_id == CLASS_A]
    assert len(class_a) == 1
    assert class_a[0].score == 0.0


def test_index_entity_missing_id_does_not_raise(index_with_factory):
    idx, _ = index_with_factory
    # Should log a warning and return without raising.
    idx.index_entity("99999999-9999-9999-9999-999999999999", "Ghost", "nobody")
