"""
The sources routes (#1551) over real SQLite, the real readers and file store,
and a fake page fetcher (tests make no network calls).
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from adapters.persistence.sqlite.connection import create_local_db_engine
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.source_repo import SQLiteSourceRepository
from adapters.sources.file_store import LocalSourceFileStore
from adapters.sources.readers import source_readers
from adapters.web.sources_routes import router
from domain.extraction.sources import SourceService
from domain.ontology.entities import Dataset, Taxonomy
from tests.fakes.fake_source_repository import FakePageFetcher
from tests.integration.sources.pdfs import scanned_pdf, text_pdf
from tests.integration.sources.test_readers import PAGE

T = "tax-1"
MAX_BYTES = 200_000


@pytest.fixture()
def session_factory(tmp_path):
    engine = create_local_db_engine(f"sqlite:///{tmp_path / 'local.db'}")
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


@pytest.fixture()
def ontology(session_factory):
    repo = SQLiteOntologyRepository(session_factory=session_factory)
    repo.save_taxonomy(Taxonomy(id=T, identifier="house", title="House"))
    return repo


@pytest.fixture()
def fetcher():
    return FakePageFetcher()


@pytest.fixture()
def client(tmp_path, session_factory, ontology, fetcher):
    app = FastAPI()
    app.include_router(router)
    app.state.source_service = SourceService(
        sources=SQLiteSourceRepository(session_factory),
        ontology_repo=ontology,
        readers=source_readers(),
        fetcher=fetcher,
        files=LocalSourceFileStore(tmp_path / "sources"),
        max_bytes=MAX_BYTES,
    )
    return TestClient(app)


def upload(client, name, data, content_type, **fields):
    return client.post(
        "/api/sources",
        files={"file": (name, data, content_type)},
        data={"taxonomy_id": T, **fields},
    )


def test_a_pdf_upload_is_ready_with_page_offsets(client, tmp_path):
    pdf = text_pdf(
        [["Use and care guide", "Read all safety instructions."], ["Cleaning", "Unplug it first."]]
    )
    response = upload(client, "wrf555-use-care.pdf", pdf, "application/pdf")

    assert response.status_code == 201, response.text
    source = response.json()
    assert source["status"] == "ready"
    assert source["kind"] == "pdf"
    assert source["title"] == "wrf555-use-care"
    assert source["origin"] == "wrf555-use-care.pdf"
    assert source["pages"] == 2
    assert source["page_starts"][0] == 0 and len(source["page_starts"]) == 2
    assert source["bytes"] == len(pdf)
    assert "text" not in source
    assert (tmp_path / "sources" / f"{source['id']}.pdf").read_bytes() == pdf

    page = client.get(f"/api/sources/{source['id']}/text", params={"page": 2}).json()
    assert page["page"] == 2 and page["pages"] == 2
    assert page["start"] == source["page_starts"][1]
    assert "Unplug it first." in page["text"]
    assert "safety" not in page["text"]

    whole = client.get(f"/api/sources/{source['id']}/text").json()
    assert whole["page"] is None
    assert whole["start"] == 0 and whole["end"] == source["chars"]

    assert client.get(f"/api/sources/{source['id']}/text", params={"page": 3}).status_code == 422


def test_a_scanned_pdf_fails_with_no_text(client):
    source = upload(client, "rheem-install.pdf", scanned_pdf(), "application/pdf").json()
    assert source["status"] == "failed"
    assert source["failure"] == "no_text"
    assert source["pages"] == 0
    assert client.get(f"/api/sources/{source['id']}/text").status_code == 409


def test_an_upload_past_the_limit_is_too_large(client):
    source = upload(client, "big.txt", b"x" * (MAX_BYTES + 10), "text/plain").json()
    assert source["status"] == "failed"
    assert source["failure"] == "too_large"


def test_an_unsupported_upload_fails(client):
    source = upload(client, "deck.pptx", b"PK\x03\x04", "application/octet-stream").json()
    assert source["failure"] == "unsupported_type"


def test_a_markdown_upload_keeps_its_headings(client):
    source = upload(
        client,
        "notes.md",
        b"# Filters\n\nMonthly.\n\n## Sizes\n16x25x1\n",
        "text/markdown",
        title="Furnace notes",
    ).json()
    assert source["status"] == "ready"
    assert source["title"] == "Furnace notes"
    assert source["headings"] == [
        {"start": 0, "title": "Filters", "level": 1},
        {"start": 21, "title": "Sizes", "level": 2},
    ]


def test_pasted_text(client):
    response = client.post(
        "/api/sources",
        json={"taxonomy_id": T, "title": "Water heater notes", "text": "Flush it yearly."},
    )
    assert response.status_code == 201, response.text
    source = response.json()
    assert source["status"] == "ready"
    assert source["kind"] == "text"
    assert source["origin"] is None
    assert source["page_starts"] == [0]
    text = client.get(f"/api/sources/{source['id']}/text", params={"page": 1}).json()
    assert text["text"] == "Flush it yearly."


def test_a_web_page_is_fetched_after_the_response(client, fetcher):
    url = "https://www.energystar.gov/furnace-filter"
    fetcher.add(url, PAGE.encode("utf-8"), "text/html; charset=utf-8")

    response = client.post("/api/sources", json={"taxonomy_id": T, "url": url})
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "fetching"

    # TestClient runs the background fetch before returning
    source = client.get(f"/api/sources/{response.json()['id']}").json()
    assert source["status"] == "ready"
    assert source["kind"] == "web"
    assert source["origin"] == url
    assert source["title"] == "How to replace a furnace filter"
    assert source["content_type"] == "text/html"
    assert [h["title"] for h in source["headings"]] == [
        "How to replace a furnace filter",
        "Find the filter",
    ]
    text = client.get(f"/api/sources/{source['id']}/text").json()["text"]
    assert "Privacy policy" not in text


def test_a_failed_fetch(client):
    response = client.post(
        "/api/sources", json={"taxonomy_id": T, "url": "https://example.org/missing"}
    )
    source = client.get(f"/api/sources/{response.json()['id']}").json()
    assert source["status"] == "failed"
    assert source["failure"] == "fetch_failed"


@pytest.mark.parametrize(
    "body",
    [
        {"taxonomy_id": T},
        {"taxonomy_id": T, "url": "https://x.org", "text": "both"},
        {"taxonomy_id": T, "text": "no title"},
        {"taxonomy_id": T, "url": "ftp://x.org/file"},
    ],
)
def test_bad_json_bodies_are_422(client, body):
    assert client.post("/api/sources", json=body).status_code == 422


def test_an_upload_without_a_taxonomy_is_422(client):
    response = client.post("/api/sources", files={"file": ("a.txt", b"x", "text/plain")})
    assert response.status_code == 422


def test_an_unknown_taxonomy_is_404(client):
    response = client.post("/api/sources", json={"taxonomy_id": "nope", "title": "a", "text": "b"})
    assert response.status_code == 404


def test_list_by_dataset_and_remove(client, ontology):
    for identifier in ("home", "cabin"):
        ontology.save_dataset(
            Dataset(id=f"ds-{identifier}", taxonomy_id=T, identifier=identifier, title=identifier)
        )
    home = client.post(
        "/api/sources", json={"taxonomy_id": T, "dataset": "home", "title": "A", "text": "a"}
    ).json()
    client.post(
        "/api/sources", json={"taxonomy_id": T, "dataset": "ds-cabin", "title": "B", "text": "b"}
    )
    # Several datasets: one must be named
    unnamed = client.post("/api/sources", json={"taxonomy_id": T, "title": "C", "text": "c"})
    assert unnamed.status_code == 422

    listed = client.get("/api/sources", params={"taxonomy_id": T}).json()
    assert listed["total"] == 2
    assert [s["title"] for s in listed["items"]] == ["B", "A"]
    only_home = client.get("/api/sources", params={"taxonomy_id": T, "dataset": "home"}).json()
    assert [s["id"] for s in only_home["items"]] == [home["id"]]
    assert client.get("/api/sources", params={"taxonomy_id": T, "dataset": "x"}).status_code == 404

    removed = client.delete(f"/api/sources/{home['id']}")
    assert removed.status_code == 200
    assert removed.json()["removed_at"] is not None
    assert client.get("/api/sources", params={"taxonomy_id": T}).json()["total"] == 1
    # The record stays for provenance
    assert client.get(f"/api/sources/{home['id']}").json()["removed_at"] is not None
    assert client.delete(f"/api/sources/{home['id']}").status_code == 404
    assert client.get("/api/sources/missing").status_code == 404
