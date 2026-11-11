"""HttpPageFetcher over a mock transport, and LocalSourceFileStore on disk (#1551)."""

import httpx
import pytest

from adapters.sources.fetcher import HttpPageFetcher
from adapters.sources.file_store import LocalSourceFileStore
from domain.extraction.exceptions import SourceFailedError
from domain.extraction.sources import SourceKind


def fetcher_for(handler) -> HttpPageFetcher:
    return HttpPageFetcher(timeout_seconds=1, transport=httpx.MockTransport(handler))


def test_fetches_one_page_following_redirects():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/old":
            return httpx.Response(301, headers={"location": "https://example.org/new"})
        return httpx.Response(200, content=b"<p>hi</p>", headers={"content-type": "text/html"})

    page = fetcher_for(handler).fetch("https://example.org/old", 1000)
    assert page.data == b"<p>hi</p>"
    assert page.content_type == "text/html"
    assert page.url == "https://example.org/new"


def test_an_error_status_fails_the_fetch():
    with pytest.raises(SourceFailedError) as raised:
        fetcher_for(lambda r: httpx.Response(404)).fetch("https://example.org/x", 1000)
    assert raised.value.failure == "fetch_failed"
    assert "404" in raised.value.detail


def test_a_page_past_the_limit_is_too_large():
    body = b"x" * 2000
    with pytest.raises(SourceFailedError) as raised:
        fetcher_for(lambda r: httpx.Response(200, content=body)).fetch("https://e.org/x", 1000)
    assert raised.value.failure == "too_large"


def test_a_timeout_fails_the_fetch():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(SourceFailedError) as raised:
        fetcher_for(handler).fetch("https://example.org/x", 1000)
    assert raised.value.failure == "fetch_failed"
    assert "Timed out" in raised.value.detail


def test_only_http_and_https():
    with pytest.raises(SourceFailedError) as raised:
        fetcher_for(lambda r: httpx.Response(200)).fetch("file:///etc/hosts", 1000)
    assert raised.value.failure == "fetch_failed"


def test_file_store_keeps_and_deletes_originals(tmp_path):
    store = LocalSourceFileStore(tmp_path / "sources")
    store.save("s1", SourceKind.PDF, b"%PDF")
    store.save("s2", SourceKind.WEB, b"<html>")

    assert (tmp_path / "sources" / "s1.pdf").read_bytes() == b"%PDF"
    assert (tmp_path / "sources" / "s2.html").exists()
    store.delete("s1")
    store.delete("missing")
    assert sorted(p.name for p in (tmp_path / "sources").iterdir()) == ["s2.html"]
