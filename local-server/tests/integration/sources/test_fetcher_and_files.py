"""HttpPageFetcher over a mock transport, and LocalSourceFileStore on disk (#1551)."""

import httpx
import pytest

from adapters.reference.http_headers import USER_AGENT
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


def test_the_fetch_names_itself_with_a_contact_url():
    """Wikimedia answers HTTP 403 to agents without one."""
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["user-agent"])
        return httpx.Response(200, content=b"hi", headers={"content-type": "text/plain"})

    fetcher_for(handler).fetch("https://example.org/x", 1000)
    assert seen == [USER_AGENT]
    assert "https://" in USER_AGENT


PROXY = "http://127.0.0.1:5555/wikipedia"


def test_a_proxied_site_is_fetched_through_the_proxy_under_its_own_url():
    requested = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(200, content=b"<p>ribosome</p>", headers={"content-type": "text/html"})

    fetcher = HttpPageFetcher(
        transport=httpx.MockTransport(handler),
        proxied={"https://en.wikipedia.org": PROXY},
    )
    page = fetcher.fetch("https://en.wikipedia.org/wiki/Ribosome?oldid=1", 1000)
    other = fetcher.fetch("https://en.wikipedia.org.example.com/wiki/Ribosome", 1000)

    assert requested == [
        f"{PROXY}/wiki/Ribosome?oldid=1",
        "https://en.wikipedia.org.example.com/wiki/Ribosome",
    ]
    assert page.url == "https://en.wikipedia.org/wiki/Ribosome?oldid=1"
    assert other.url == "https://en.wikipedia.org.example.com/wiki/Ribosome"


def test_with_the_proxy_off_a_site_is_fetched_directly():
    requested = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(200, content=b"hi", headers={"content-type": "text/plain"})

    # The proxy hands out the site's own URL when it isn't running
    HttpPageFetcher(
        transport=httpx.MockTransport(handler),
        proxied={"https://en.wikipedia.org": "https://en.wikipedia.org"},
    ).fetch("https://en.wikipedia.org/wiki/Ribosome", 1000)
    assert requested == ["https://en.wikipedia.org/wiki/Ribosome"]


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


@pytest.mark.parametrize("url", ["http://exämple..com/", "http://exa\tmple.com/"])
def test_an_invalid_url_fails_the_fetch(url):
    # httpx raises InvalidURL, which isn't an HTTPError; no request is made
    with pytest.raises(SourceFailedError) as raised:
        HttpPageFetcher(timeout_seconds=1).fetch(url, 1000)
    assert raised.value.failure == "fetch_failed"


def test_the_content_disposition_file_name_comes_back():
    def handler(request):
        return httpx.Response(
            200,
            content=b"# Guide",
            headers={
                "content-type": "application/octet-stream",
                "content-disposition": 'attachment; filename="install guide.md"',
            },
        )

    page = fetcher_for(handler).fetch("https://example.org/download?id=7", 1000)
    assert page.file_name == "install guide.md"


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
