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
