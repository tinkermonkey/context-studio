"""SourceService and the Source entity (#1551), over fake ports."""

import pytest

from domain.extraction.exceptions import SourceNotReadyError
from domain.extraction.sources import (
    Source,
    SourceFailure,
    SourceKind,
    SourceService,
    SourceStatus,
    check_url,
    fetched_kind,
    file_kind,
)
from domain.ontology.entities import Dataset, Taxonomy
from domain.ontology.exceptions import DatasetRequiredError, EntityNotFoundError
from tests.fakes.fake_ontology_repository import FakeOntologyRepository
from tests.fakes.fake_source_repository import (
    FakePageFetcher,
    FakeSourceFileStore,
    FakeSourceRepository,
    fake_readers,
)

T = "tax-1"


@pytest.fixture()
def ontology():
    repo = FakeOntologyRepository()
    repo.save_taxonomy(Taxonomy(id=T, identifier="house", title="House"))
    return repo


@pytest.fixture()
def repo():
    return FakeSourceRepository()


@pytest.fixture()
def fetcher():
    return FakePageFetcher()


@pytest.fixture()
def files():
    return FakeSourceFileStore()


def make_service(ontology, repo, fetcher, files, max_bytes=1000, **failures):
    return SourceService(
        sources=repo,
        ontology_repo=ontology,
        readers=fake_readers(**failures),
        fetcher=fetcher,
        files=files,
        max_bytes=max_bytes,
    )


@pytest.fixture()
def service(ontology, repo, fetcher, files):
    return make_service(ontology, repo, fetcher, files)


# ---- kinds and URLs ----


@pytest.mark.parametrize(
    "name, content_type, kind",
    [
        ("manual.PDF", None, SourceKind.PDF),
        ("notes.md", "application/octet-stream", SourceKind.MARKDOWN),
        ("page.htm", None, SourceKind.HTML),
        ("readme.txt", None, SourceKind.TEXT),
        ("upload", "text/markdown; charset=utf-8", SourceKind.MARKDOWN),
        ("slides.pptx", "application/octet-stream", None),
    ],
)
def test_file_kind(name, content_type, kind):
    assert file_kind(name, content_type) == kind


def test_file_kind_sniffs_a_pdf():
    assert file_kind("manual", "application/octet-stream", b"%PDF-1.7\n...") == SourceKind.PDF


def test_fetched_kind_prefers_the_content_type_and_calls_html_web():
    assert fetched_kind("https://x.org/a", "text/html; charset=utf-8") == SourceKind.WEB
    assert fetched_kind("https://x.org/m.pdf", None) == SourceKind.PDF
    assert fetched_kind("https://x.org/m", "application/pdf") == SourceKind.PDF
    assert fetched_kind("https://x.org/i.png", "image/png") is None
    # A specific type wins over the URL's extension
    assert fetched_kind("https://x.org/page.md", "text/html") == SourceKind.WEB


@pytest.mark.parametrize(
    "url, content_type, data, file_name, kind",
    [
        # PDF magic bytes win over anything the server says
        ("https://x.org/get?id=1", "text/html", b"%PDF-1.4 ...", None, SourceKind.PDF),
        # Generic types: the URL's extension wins when it is known
        ("https://x.org/README.md", "text/plain", b"# A", None, SourceKind.MARKDOWN),
        ("https://x.org/m.pdf", "application/x-pdf", b"", None, SourceKind.PDF),
        ("https://x.org/notes.txt", "application/octet-stream", b"a", None, SourceKind.TEXT),
        ("https://x.org/page", "text/plain", b"a", None, SourceKind.TEXT),
        ("https://x.org/blob", "application/octet-stream", b"a", None, None),
        # ... and a Content-Disposition file name before the URL's
        (
            "https://x.org/download",
            "application/octet-stream",
            b"#",
            "guide.md",
            SourceKind.MARKDOWN,
        ),
        ("https://x.org/a.txt", "text/plain", b"<p>", "page.html", SourceKind.WEB),
    ],
)
def test_fetched_kind_for_generic_content_types(url, content_type, data, file_name, kind):
    assert fetched_kind(url, content_type, data, file_name) == kind


@pytest.mark.parametrize("url", ["ftp://x.org/a", "file:///etc/passwd", "x.org", "http://"])
def test_check_url_refuses_anything_but_http_and_https(url):
    with pytest.raises(ValueError):
        check_url(url)


# ---- the entity ----


def test_page_range_and_page_at():
    source = Source(
        taxonomy_id=T,
        dataset_id="d",
        kind=SourceKind.PDF,
        title="Manual",
        text="aaaa\n\nbbb\n\ncc",
        chars=13,
        pages=3,
        page_starts=[0, 6, 11],
    )
    assert source.page_range(1) == (0, 6)
    assert source.page_range(3) == (11, 13)
    assert [source.page_at(o) for o in (0, 5, 6, 12)] == [1, 1, 2, 3]
    with pytest.raises(ValueError):
        source.page_range(4)


# ---- adding ----


def test_add_file_reads_it_and_keeps_the_original(service, files, ontology):
    source = service.add_file(T, "manual.pdf", b"page one\fpage two", "application/pdf")

    assert source.status is SourceStatus.READY
    assert source.kind is SourceKind.PDF
    assert source.title == "Read title"  # the file's own title over its name
    assert source.origin == "manual.pdf"
    assert source.pages == 2
    assert source.page_starts == [0, 9]
    assert source.chars == len(source.text) == 17
    assert source.bytes == 17
    assert files.files[source.id] == (SourceKind.PDF, b"page one\fpage two")
    # The taxonomy had no dataset: the source's write created `default`
    assert [d.identifier for d in ontology.list_datasets(T)] == ["default"]
    assert source.dataset_id == ontology.list_datasets(T)[0].id


def test_a_title_given_wins_over_the_files_own(service):
    assert service.add_file(T, "a.md", b"# x", title=" Mine ").title == "Mine"


def test_a_file_too_large_fails_and_keeps_no_original(ontology, repo, fetcher, files):
    service = make_service(ontology, repo, fetcher, files, max_bytes=4)
    source = service.add_file(T, "a.txt", b"12345")
    assert source.status is SourceStatus.FAILED
    assert source.failure is SourceFailure.TOO_LARGE
    assert files.files == {}
    assert repo.get(source.id).failure is SourceFailure.TOO_LARGE


def test_an_unsupported_file_fails(service, files):
    source = service.add_file(T, "deck.pptx", b"PK..", "application/vnd.ms-powerpoint")
    assert source.status is SourceStatus.FAILED
    assert source.failure is SourceFailure.UNSUPPORTED_TYPE
    assert "application/vnd.ms-powerpoint" in source.failure_detail
    assert files.files == {}


def test_a_pdf_without_text_fails_with_no_text(ontology, repo, fetcher, files):
    service = make_service(ontology, repo, fetcher, files, pdf=SourceFailure.NO_TEXT)
    source = service.add_file(T, "scan.pdf", b"%PDF")
    assert source.status is SourceStatus.FAILED
    assert source.failure is SourceFailure.NO_TEXT
    assert source.text == "" and source.page_starts == []


def test_blank_text_fails_with_no_text(service):
    source = service.add_file(T, "blank.txt", b"  \n ")
    assert source.failure is SourceFailure.NO_TEXT


def test_add_text_is_one_page_with_no_original(service, files):
    source = service.add_text(T, "Water heater notes", "Flush the tank yearly.")
    assert source.status is SourceStatus.READY
    assert source.kind is SourceKind.TEXT
    assert source.title == "Water heater notes"
    assert source.origin is None
    assert source.page_starts == [0]
    assert files.files == {}


@pytest.mark.parametrize("title, text", [("", "x"), ("T", "  ")])
def test_add_text_needs_a_title_and_text(service, title, text):
    with pytest.raises(ValueError):
        service.add_text(T, title, text)


def test_add_url_is_fetching_until_fetched(service, fetcher, files):
    fetcher.add("https://example.org/filter", b"Replace the filter")
    source = service.add_url(T, " https://example.org/filter ")
    assert source.status is SourceStatus.FETCHING
    assert source.title == source.origin == "https://example.org/filter"
    assert fetcher.fetched == []

    fetched = service.fetch(source.id)
    assert fetched.status is SourceStatus.READY
    assert fetched.kind is SourceKind.WEB
    assert fetched.title == "Read title"
    assert fetched.content_type == "text/html"
    assert fetched.text == "Replace the filter"
    assert files.files[source.id][0] is SourceKind.WEB
    # Fetching again does nothing: it is no longer fetching
    service.fetch(source.id)
    assert fetcher.fetched == ["https://example.org/filter"]


def test_a_url_to_a_pdf_becomes_a_pdf_source(service, fetcher):
    fetcher.add("https://example.org/m.pdf", b"one\ftwo", "application/pdf")
    source = service.fetch(service.add_url(T, "https://example.org/m.pdf", title="Manual").id)
    assert source.kind is SourceKind.PDF
    assert source.title == "Manual"
    assert source.pages == 2


def test_a_failed_fetch_fails_the_source(service, fetcher):
    source = service.fetch(service.add_url(T, "https://example.org/missing").id)
    assert source.status is SourceStatus.FAILED
    assert source.failure is SourceFailure.FETCH_FAILED
    assert source.failure_detail == "HTTP 404"


def test_a_fetched_page_of_an_unsupported_type_fails(service, fetcher):
    fetcher.add("https://example.org/i.png", b"\x89PNG", "image/png")
    source = service.fetch(service.add_url(T, "https://example.org/i.png").id)
    assert source.failure is SourceFailure.UNSUPPORTED_TYPE


def test_add_url_refuses_other_schemes(service):
    with pytest.raises(ValueError):
        service.add_url(T, "file:///etc/hosts")


def test_markdown_served_as_text_plain_is_markdown(service, fetcher):
    fetcher.add("https://example.org/README.md", b"# Readme", "text/plain; charset=utf-8")
    source = service.fetch(service.add_url(T, "https://example.org/README.md").id)
    assert source.kind is SourceKind.MARKDOWN


class _Exploding:
    def __init__(self, error):
        self.error = error

    def fetch(self, url, max_bytes):
        raise self.error

    def save(self, source_id, kind, data):
        raise self.error

    def delete(self, source_id):
        pass


def test_an_unexpected_fetch_error_fails_the_source_instead_of_leaving_it_fetching(
    ontology, repo, files
):
    service = make_service(ontology, repo, _Exploding(RuntimeError("bad url")), files)
    source = service.fetch(service.add_url(T, "https://example.org/a").id)
    assert source.status is SourceStatus.FAILED
    assert source.failure is SourceFailure.FETCH_FAILED
    assert source.failure_detail == "RuntimeError: bad url"
    assert repo.get(source.id).status is SourceStatus.FAILED


def test_a_file_store_error_during_a_fetch_fails_the_source(ontology, repo, fetcher):
    fetcher.add("https://example.org/a", b"page")
    service = make_service(ontology, repo, fetcher, _Exploding(OSError("disk full")))
    source = service.fetch(service.add_url(T, "https://example.org/a").id)
    assert source.failure is SourceFailure.FETCH_FAILED
    assert "disk full" in source.failure_detail


def test_a_source_removed_before_its_fetch_is_not_fetched(service, fetcher):
    source = service.add_url(T, "https://example.org/a")
    service.remove(source.id)
    assert service.fetch(source.id).removed_at is not None
    assert fetcher.fetched == []


def test_a_source_removed_during_its_fetch_stays_removed(service, fetcher, files, repo):
    fetcher.add("https://example.org/a", b"page")
    source = service.add_url(T, "https://example.org/a")
    fetcher.before_answer = lambda: service.remove(source.id)

    result = service.fetch(source.id)

    assert result.removed_at is not None
    stored = repo.get(source.id)
    assert stored.removed_at is not None
    assert stored.status is SourceStatus.FETCHING  # the fetch's result was not saved
    assert files.files == {}  # nor its original written
    assert service.list_sources(T) == ([], 0)


def test_a_source_removed_during_a_failed_fetch_stays_removed(service, fetcher, repo):
    source = service.add_url(T, "https://example.org/missing")
    fetcher.before_answer = lambda: service.remove(source.id)
    service.fetch(source.id)
    assert repo.get(source.id).removed_at is not None


def test_fail_interrupted_fetches(service, repo):
    source = service.add_url(T, "https://example.org/a")
    assert service.fail_interrupted_fetches() == 1
    assert repo.get(source.id).failure is SourceFailure.FETCH_FAILED


# ---- datasets ----


def test_dataset_by_identifier_or_id_and_required_when_several(service, ontology):
    for identifier in ("home", "cabin"):
        ontology.save_dataset(
            Dataset(id=f"ds-{identifier}", taxonomy_id=T, identifier=identifier, title=identifier)
        )
    assert service.add_text(T, "a", "x", dataset="cabin").dataset_id == "ds-cabin"
    assert service.add_text(T, "b", "y", dataset="ds-home").dataset_id == "ds-home"
    with pytest.raises(DatasetRequiredError):
        service.add_text(T, "c", "z")
    with pytest.raises(EntityNotFoundError):
        service.add_text(T, "d", "z", dataset="garage")

    assert [s.title for s in service.list_sources(T)[0]] == ["b", "a"]
    assert [s.title for s in service.list_sources(T, dataset="home")[0]] == ["b"]


def test_list_pages_counts_and_leaves_the_text_out(service):
    for title in ("a", "b", "c"):
        service.add_text(T, title, f"text {title}")
    page, total = service.list_sources(T, limit=1, offset=1)
    assert total == 3
    assert [s.title for s in page] == ["b"]
    assert page[0].text == "" and page[0].chars == 6
    assert service.get(page[0].id).text == "text b"


def test_an_unknown_taxonomy_is_not_found(service):
    with pytest.raises(EntityNotFoundError):
        service.add_text("nope", "a", "x")
    with pytest.raises(EntityNotFoundError):
        service.list_sources("nope")


# ---- reading and removing ----


def test_text_by_page(service):
    source = service.add_file(T, "m.pdf", b"one\ftwo")
    assert service.text(source.id)[1:] == (0, 7)
    _, start, end = service.text(source.id, page=2)
    assert source.text[start:end] == "two"
    with pytest.raises(ValueError):
        service.text(source.id, page=3)


def test_text_of_a_source_not_ready(service):
    source = service.add_url(T, "https://example.org/a")
    with pytest.raises(SourceNotReadyError):
        service.text(source.id)


def test_remove_keeps_the_record_for_provenance(service, files):
    source = service.add_file(T, "a.md", b"# A")
    removed = service.remove(source.id)

    assert removed.removed_at is not None
    assert service.list_sources(T) == ([], 0)
    assert service.get(source.id).removed_at is not None
    assert files.files == {}
    with pytest.raises(EntityNotFoundError):
        service.remove(source.id)
    with pytest.raises(EntityNotFoundError):
        service.get("missing")
