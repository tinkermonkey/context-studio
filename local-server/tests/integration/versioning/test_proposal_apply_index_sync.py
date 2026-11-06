"""
Integration test: applying a proposal's type updates keeps the schema vector
index in sync without contending for SQLite's write lock.

Each operation applies inside one transaction scope (BEGIN IMMEDIATE). The
vector index writes embeddings onto the same ontology_entities rows, so it must
share the scope's session (as app.py wires it). A separate session would wait
the full busy_timeout for the scope's lock, then fail with "database is locked"
and leave the index stale.

File-based SQLite with WAL and a real (lowered) busy_timeout.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import logging
import tempfile
import time
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from adapters.events.in_process import InProcessEventPublisher
from adapters.persistence.sqlite import connection
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.individual_vector_index import SqliteIndividualVectorIndex
from adapters.persistence.sqlite.mappers import _deserialize_embedding
from adapters.persistence.sqlite.models import Base, OntologyEntity
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.proposal_repo import SQLiteChangeProposalRepository
from adapters.persistence.sqlite.schema_vector_index import SqliteSchemaVectorIndex
from adapters.persistence.sqlite.transaction import SharedSessionFactory, SqliteTransactionScope
from domain.ontology.services import OntologyService
from domain.versioning.proposal_service import OperationDraft, ProposalService
from domain.versioning.proposals import OperationKind as K
from domain.versioning.proposals import OperationStatus, ProposalSource
from domain.versioning.proposals import OperationType as T
from domain.versioning.revert_service import RevertService
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.utils.change_recording import wire_change_recorder

BUSY_TIMEOUT_MS = 1000
TYPE_COUNT = 4


@pytest.fixture()
def session_factory(monkeypatch):
    monkeypatch.setattr(connection, "BUSY_TIMEOUT_MS", BUSY_TIMEOUT_MS)
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = connection.create_local_db_engine(f"sqlite:///{Path(tmpdir) / 'local.db'}")
        Base.metadata.create_all(engine)
        yield sessionmaker(bind=engine)
        engine.dispose()


@pytest.fixture()
def parts(session_factory):
    """Wired as in app.py: repositories and vector indexes share one session factory."""
    shared = SharedSessionFactory(session_factory)
    embedding = FakeEmbeddingService()
    ontology_repo = SQLiteOntologyRepository(session_factory=shared)
    change_repo = SQLiteChangeRepository(session_factory=shared)
    schema_index = SqliteSchemaVectorIndex(shared, embedding)
    individual_index = SqliteIndividualVectorIndex(shared, embedding)
    publisher = InProcessEventPublisher()
    wire_change_recorder(publisher, change_repo)
    ontology = OntologyService(
        ontology_repo,
        embedding,
        publisher,
        schema_index=schema_index,
        individual_index=individual_index,
    )
    scope = SqliteTransactionScope(shared)
    service = ProposalService(
        SQLiteChangeProposalRepository(shared),
        ontology,
        ontology_repo,
        RevertService(
            change_repo=change_repo,
            ontology_repo=ontology_repo,
            schema_index=schema_index,
            individual_index=individual_index,
            transaction_scope=scope,
        ),
        transaction_scope=scope,
    )
    return ontology, service, scope, embedding, session_factory


def stored_title_embedding(session_factory, entity_id):
    with session_factory() as session:
        return _deserialize_embedding(session.get(OntologyEntity, entity_id).title_embedding)


def test_type_updates_apply_fast_and_refresh_their_embeddings(parts, caplog):
    ontology, service, _, embedding, session_factory = parts
    taxonomy = ontology.create_taxonomy(title="House")
    vocab = ontology.create_scheme(taxonomy_id=taxonomy.id, title="Vocabulary")
    room = ontology.create_class(vocab.id, "Room")
    types = [
        ontology.create_property_definition(f"rel_{i}", f"rel {i}", domain_class_id=room.id)
        for i in range(TYPE_COUNT)
    ]
    proposal = service.propose(
        taxonomy.id,
        "Renames",
        [
            OperationDraft(i + 1, T.UPDATE, K.PROPERTY, t.id, fields={"title": f"renamed {i}"})
            for i, t in enumerate(types)
        ],
        ProposalSource.MCP,
    )

    caplog.set_level(logging.ERROR)
    started = time.monotonic()
    applied = service.apply(proposal.id, [o.id for o in proposal.operations])
    elapsed = time.monotonic() - started

    assert [o.status for o in applied.operations] == [OperationStatus.APPLIED] * TYPE_COUNT, [
        o.reason for o in applied.operations
    ]
    assert "database is locked" not in caplog.text
    assert "Vector index sync failed" not in caplog.text
    # A lock wait costs a full busy_timeout per operation.
    assert elapsed < BUSY_TIMEOUT_MS / 1000
    for i, t in enumerate(types):
        assert stored_title_embedding(session_factory, t.id) == pytest.approx(
            embedding.embed(f"renamed {i}")
        )


def test_a_rolled_back_scope_leaves_the_embedding_as_it_was(parts):
    ontology, _, scope, embedding, session_factory = parts
    taxonomy = ontology.create_taxonomy(title="House")
    vocab = ontology.create_scheme(taxonomy_id=taxonomy.id, title="Vocabulary")
    room = ontology.create_class(vocab.id, "Room")
    near = ontology.create_property_definition("near", "near", domain_class_id=room.id)
    before = stored_title_embedding(session_factory, near.id)
    assert before == pytest.approx(embedding.embed("near"))

    with pytest.raises(RuntimeError, match="abort"):
        with scope.atomic():
            ontology.update_property_definition(near.id, title="far")
            raise RuntimeError("abort")

    assert stored_title_embedding(session_factory, near.id) == pytest.approx(before)
    with session_factory() as session:
        assert session.get(OntologyEntity, near.id).title == "near"
