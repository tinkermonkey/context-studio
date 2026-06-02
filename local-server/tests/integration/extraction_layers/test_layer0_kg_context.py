"""
Layer 0 (KG Context) isolation tests.

Exercises `domain.extraction.layers.kg_context.execute` against a real
SQLiteOntologyRepository pre-populated with canon classes. Layer 0 walks the
repo, scores each class by semantic similarity against the input text, and
emits ExtractedEntity rows above a 0.7 threshold.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.extraction.layers import kg_context
from domain.ontology.entities import Class, ConceptScheme, Taxonomy
from tests.fakes.fake_embedding_service import FakeEmbeddingService


@pytest.fixture
def session_factory():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_url = f"sqlite:///{Path(tmpdir) / 'test.db'}"
        engine = create_engine(db_url)
        Base.metadata.create_all(engine)
        yield sessionmaker(bind=engine)


@pytest.fixture
def embedding_service():
    return FakeEmbeddingService()


@pytest.fixture
def ontology_with_canon_class(session_factory, embedding_service):
    """
    Repo with one canon-aligned Class whose embedding matches the seed text.

    The class embedding is derived from `seed_text` so that calling
    Layer 0 with the same text yields similarity 1.0 and a guaranteed match.
    """
    repo = SQLiteOntologyRepository(session_factory)
    tax = Taxonomy(
        id=str(uuid4()),
        identifier="software_architecture",
        title="Software Architecture",
    )
    repo.save_taxonomy(tax)
    scheme = ConceptScheme(
        id=str(uuid4()),
        identifier="architectural_styles",
        taxonomy_id=tax.id,
        title="Architectural Styles",
    )
    repo.save_concept_scheme(scheme)

    seed_text = "Representational State Transfer is an architectural style."
    embedded = embedding_service.embed(seed_text)
    rest_cls = Class(
        id=str(uuid4()),
        identifier="rest",
        concept_scheme_id=scheme.id,
        taxonomy_id=tax.id,
        title="REST",
        description="Representational State Transfer",
        embedding=embedded,
    )
    repo.save_class(rest_cls)
    return repo, seed_text, rest_cls


def test_empty_text_returns_no_entities(session_factory, embedding_service):
    repo = SQLiteOntologyRepository(session_factory)
    out = kg_context.execute("", repo, embedding_service)
    assert out.entities == ()
    assert out.metadata is not None and out.metadata.get("reason") == "empty_text"


def test_whitespace_only_text_returns_no_entities(session_factory, embedding_service):
    repo = SQLiteOntologyRepository(session_factory)
    out = kg_context.execute("   \n\t ", repo, embedding_service)
    assert out.entities == ()
    assert out.metadata is not None and out.metadata.get("reason") == "empty_text"


def test_empty_repo_returns_no_entities(session_factory, embedding_service):
    repo = SQLiteOntologyRepository(session_factory)
    out = kg_context.execute("anything", repo, embedding_service)
    assert out.entities == ()
    assert out.metadata is not None
    assert out.metadata.get("reason") == "no_entities_in_repo"
    assert out.metadata.get("matches_found") == 0


def test_class_above_threshold_yields_layer_0_entity(ontology_with_canon_class, embedding_service):
    repo, seed_text, rest_cls = ontology_with_canon_class
    out = kg_context.execute(seed_text, repo, embedding_service)

    layer0_entities = [e for e in out.entities if e.source_layer == 0]
    assert layer0_entities, (
        f"Expected ≥1 layer-0 entity from a class with matching embedding; "
        f"got {len(out.entities)} total entities"
    )
    match = layer0_entities[0]
    assert match.label == rest_cls.title
    assert match.entity_type == "Class"
    assert match.source_layer == 0
    assert match.confidence >= 0.7  # threshold
    assert match.properties.get("kg_entity_id") == rest_cls.id


def test_class_without_embedding_is_skipped(session_factory, embedding_service):
    """A Class with no embedding cannot be similarity-matched and must be skipped."""
    repo = SQLiteOntologyRepository(session_factory)
    tax = Taxonomy(id=str(uuid4()), identifier="tax", title="T")
    repo.save_taxonomy(tax)
    scheme = ConceptScheme(id=str(uuid4()), identifier="sch", taxonomy_id=tax.id, title="S")
    repo.save_concept_scheme(scheme)
    repo.save_class(
        Class(
            id=str(uuid4()),
            identifier="no_embed",
            concept_scheme_id=scheme.id,
            taxonomy_id=tax.id,
            title="No Embedding Class",
            embedding=None,
        )
    )

    out = kg_context.execute("anything related", repo, embedding_service)
    assert out.entities == ()
    # metadata should still report that we walked the repo
    assert out.metadata is not None
    assert out.metadata.get("matches_found") == 0


def test_metadata_includes_threshold_and_entities_checked(
    ontology_with_canon_class, embedding_service
):
    repo, seed_text, _ = ontology_with_canon_class
    out = kg_context.execute(seed_text, repo, embedding_service)
    assert out.metadata is not None
    assert out.metadata["threshold"] == 0.7
    assert out.metadata["entities_checked"] >= 1
    assert out.metadata["matches_found"] >= 1


def test_threshold_filters_unrelated_query_text(ontology_with_canon_class, embedding_service):
    """
    Layer 0 must drop class matches whose similarity falls below 0.7.

    The fixture's REST class is embedded on
    'Representational State Transfer is an architectural style.'
    Querying with an unrelated phrase produces a FakeEmbeddingService
    cosine similarity of ~0.61 (probed value), which is below the 0.7
    inclusion threshold. The layer must NOT surface the class.

    This is the canonical near-miss test: it proves the threshold filter
    is doing real work rather than being a no-op disguised by the
    FakeEmbeddingService's `embedding_a == embedding_b -> 1.0` shortcut.
    """
    repo, _, _ = ontology_with_canon_class
    unrelated_query = "Conflict-free replicated data types"

    # Sanity check: confirm the probed similarity is genuinely sub-threshold
    # so this test fails for the right reason if FakeEmbeddingService changes.
    seed_embed = embedding_service.embed(
        "Representational State Transfer is an architectural style."
    )
    unrelated_embed = embedding_service.embed(unrelated_query)
    actual_similarity = embedding_service.similarity(seed_embed, unrelated_embed)
    assert actual_similarity < 0.7, (
        f"Test predicate broke: FakeEmbeddingService now returns "
        f"similarity={actual_similarity:.4f} >= 0.7 between the seed text "
        f"and {unrelated_query!r}. Pick a different unrelated phrase."
    )

    out = kg_context.execute(unrelated_query, repo, embedding_service)
    layer0_entities = [e for e in out.entities if e.source_layer == 0]
    assert layer0_entities == [], (
        f"Layer 0 surfaced {len(layer0_entities)} match(es) below the 0.7 "
        f"threshold (similarity={actual_similarity:.4f}). The threshold "
        f"filter is broken."
    )
    # metadata still reports the walk: the class was checked, just below threshold
    assert out.metadata is not None
    assert out.metadata.get("entities_checked") >= 1
    assert out.metadata.get("matches_found") == 0
