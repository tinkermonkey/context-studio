"""
Integration tests for SQLiteApprovalPolicyRepository (#1355) on real SQLite
with foreign keys enforced; the in-memory fake must behave the same.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import tempfile
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.approval_policy_repo import SQLiteApprovalPolicyRepository
from adapters.persistence.sqlite.connection import create_local_db_engine
from adapters.persistence.sqlite.models import ApprovalPolicyRecord, Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from domain.ontology.entities import Taxonomy
from domain.versioning.approval_policy import ApprovalPolicy
from tests.fakes.fake_approval_policy_repository import FakeApprovalPolicyRepository

RULES = {
    "auto_apply": [{"op": "create", "kind": "individual", "class": "house_activity"}],
    "min_probability": 0.25,
}


@pytest.fixture()
def session_factory():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_local_db_engine(f"sqlite:///{Path(tmpdir) / 'local.db'}")
        Base.metadata.create_all(engine)
        yield sessionmaker(bind=engine)
        engine.dispose()


@pytest.fixture()
def ontology_repo(session_factory):
    repo = SQLiteOntologyRepository(session_factory=session_factory)
    repo.save_taxonomy(Taxonomy(id="tax-1", identifier="house", title="House"))
    return repo


@pytest.fixture(params=["sqlite", "fake"])
def repo(request, session_factory, ontology_repo):
    if request.param == "sqlite":
        return SQLiteApprovalPolicyRepository(session_factory)
    return FakeApprovalPolicyRepository()


def test_get_is_none_until_saved(repo):
    assert repo.get("tax-1") is None


def test_save_creates_then_replaces(repo):
    first = repo.save(ApprovalPolicy.from_rules("tax-1", RULES))
    assert first == ApprovalPolicy.from_rules("tax-1", RULES)
    assert repo.get("tax-1") == first

    replaced = repo.save(ApprovalPolicy("tax-1"))
    assert replaced == ApprovalPolicy("tax-1")
    assert repo.get("tax-1") == ApprovalPolicy("tax-1")


def test_stored_as_the_rules_json(session_factory, ontology_repo):
    SQLiteApprovalPolicyRepository(session_factory).save(ApprovalPolicy.from_rules("tax-1", RULES))
    with session_factory() as session:
        row = session.get(ApprovalPolicyRecord, "tax-1")
        assert row.rules == RULES
        assert row.updated_at is not None


def test_deleting_the_taxonomy_deletes_its_policy(session_factory, ontology_repo):
    repo = SQLiteApprovalPolicyRepository(session_factory)
    repo.save(ApprovalPolicy.from_rules("tax-1", RULES))
    ontology_repo.delete_taxonomy("tax-1")
    assert repo.get("tax-1") is None


def test_a_policy_needs_an_existing_entity(session_factory, ontology_repo):
    with pytest.raises(IntegrityError):
        SQLiteApprovalPolicyRepository(session_factory).save(ApprovalPolicy("no-such-taxonomy"))
