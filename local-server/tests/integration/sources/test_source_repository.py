"""
SQLiteSourceRepository (#1551) on real SQLite with foreign keys enforced; the
in-memory fake must behave the same.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.connection import create_local_db_engine
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.source_repo import SQLiteSourceRepository
from domain.extraction.sources import (
    Source,
    SourceFailure,
    SourceHeading,
    SourceKind,
    SourceStatus,
)
from domain.ontology.entities import Dataset, Taxonomy
from tests.fakes.fake_source_repository import FakeSourceRepository

T = "tax-1"
WHEN = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def session_factory(tmp_path):
    engine = create_local_db_engine(f"sqlite:///{tmp_path / 'local.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    ontology = SQLiteOntologyRepository(session_factory=factory)
    ontology.save_taxonomy(Taxonomy(id=T, identifier="house", title="House"))
    for identifier in ("home", "cabin"):
        ontology.save_dataset(
            Dataset(id=f"ds-{identifier}", taxonomy_id=T, identifier=identifier, title=identifier)
        )
    yield factory
    engine.dispose()


@pytest.fixture(params=["sqlite", "fake"])
def repo(request, session_factory):
    if request.param == "sqlite":
        return SQLiteSourceRepository(session_factory)
    return FakeSourceRepository()


def source(title="Manual", dataset_id="ds-home", minutes=0, **kwargs):
    return Source(
        taxonomy_id=T,
        dataset_id=dataset_id,
        kind=SourceKind.PDF,
        title=title,
        created_at=WHEN + timedelta(minutes=minutes),
        updated_at=WHEN + timedelta(minutes=minutes),
        **kwargs,
    )


def test_save_and_get_round_trip(repo):
    saved = repo.save(
        source(
            origin="wrf555.pdf",
            content_type="application/pdf",
            bytes=2048,
            pages=2,
            chars=11,
            text="aaaa\n\nbbbbb",
            page_starts=[0, 6],
            headings=[SourceHeading(start=6, title="Cleaning", level=1)],
        )
    )
    got = repo.get(saved.id)

    assert got == saved
    assert got.page_starts == [0, 6]
    assert got.headings == [SourceHeading(start=6, title="Cleaning", level=1)]
    assert got.created_at == WHEN
    assert got.status is SourceStatus.READY
    assert repo.get("missing") is None


def test_save_replaces_by_id(repo):
    saved = repo.save(source(status=SourceStatus.FETCHING))
    saved.status = SourceStatus.FAILED
    saved.failure = SourceFailure.FETCH_FAILED
    saved.failure_detail = "HTTP 500"
    repo.save(saved)

    got = repo.get(saved.id)
    assert got.status is SourceStatus.FAILED
    assert got.failure is SourceFailure.FETCH_FAILED
    assert got.failure_detail == "HTTP 500"


def test_list_filters_newest_first_without_removed(repo):
    old = repo.save(source("old", minutes=0))
    new = repo.save(source("new", minutes=5))
    cabin = repo.save(source("cabin", dataset_id="ds-cabin", minutes=3))
    fetching = repo.save(source("fetching", minutes=1, status=SourceStatus.FETCHING))
    repo.save(source("removed", minutes=9, removed_at=WHEN))

    assert [s.title for s in repo.list_sources(taxonomy_id=T)] == [
        "new",
        "cabin",
        "fetching",
        "old",
    ]
    assert [s.id for s in repo.list_sources(taxonomy_id=T, dataset_id="ds-cabin")] == [cabin.id]
    assert [s.id for s in repo.list_sources(status=SourceStatus.FETCHING)] == [fetching.id]
    assert repo.list_sources(taxonomy_id="other") == []
    assert {old.id, new.id} <= {s.id for s in repo.list_sources()}
    assert repo.count_sources(taxonomy_id=T) == 4
    assert repo.count_sources(taxonomy_id=T, dataset_id="ds-cabin") == 1
    assert repo.count_sources(status=SourceStatus.FETCHING) == 1


def test_list_pages_and_leaves_the_text_out(repo):
    for minutes in range(5):
        repo.save(source(f"s{minutes}", minutes=minutes, text="body " * 100, chars=500))

    page = repo.list_sources(taxonomy_id=T, limit=2, offset=1)
    assert [s.title for s in page] == ["s3", "s2"]
    assert all(s.text == "" and s.chars == 500 for s in page)
    assert repo.get(page[0].id).text == "body " * 100
    assert repo.count_sources(taxonomy_id=T) == 5
