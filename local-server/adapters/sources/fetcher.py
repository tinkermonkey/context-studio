"""PageFetcher adapter over httpx: one http or https page, size-limited (#1551)."""

from __future__ import annotations

from collections.abc import Mapping
from email.message import Message

import httpx

from adapters.reference.http_headers import USER_AGENT
from adapters.sources.network_guard import (
    BlockedAddressError,
    GuardedNetworkBackend,
    GuardedTransport,
)
from domain.extraction.exceptions import SourceFailedError
from domain.extraction.sources import FetchedPage, SourceFailure, check_url
from utils.logger import get_logger

logger = get_logger(__name__)


class HttpPageFetcher:
    """
    Fetches one page and stops reading past the size limit.

    Only public addresses are fetched (#1656): the connection itself checks the
    address it makes (see network_guard), and every redirect is a new request
    that is checked the same way.
    """

    def __init__(
        self,
        timeout_seconds: float = 30.0,
        max_redirects: int = 5,
        transport: httpx.BaseTransport | None = None,
        proxied: Mapping[str, str] | None = None,
        allow_private_urls: bool = False,
    ) -> None:
        """
        Args:
            transport: Tests pass an httpx.MockTransport, which makes no connection
                and so is not checked; None uses the checked network transport
            proxied: A site's base URL -> where to send its pages instead: the
                reference proxy's URL for that site (Wikipedia), which caches and
                rate limits them. A site sent to itself (proxy off) goes direct.
                The proxy's address is the one non-public address that is fetched.
            allow_private_urls: Fetch loopback, private and link-local addresses too
                (sources.allow_private_urls)
        """
        self._timeout = timeout_seconds
        self._max_redirects = max_redirects
        self._transport = transport
        self._allow_private_urls = allow_private_urls
        self._proxied = {
            site.rstrip("/"): via.rstrip("/")
            for site, via in (proxied or {}).items()
            if site.rstrip("/") != via.rstrip("/")
        }

    def fetch(self, url: str, max_bytes: int) -> FetchedPage:
        try:
            current = check_url(url)
            for _ in range(self._max_redirects + 1):
                routed = self._route(current)
                # A new client for every hop: the connection's address check depends on
                # whether this hop is the proxy's, and nothing carries over from a redirect.
                with self._client(
                    proxy_origin=_origin(routed) if routed != current else None
                ) as client:
                    with client.stream("GET", routed) as response:
                        if response.has_redirect_location:
                            location = response.headers["location"]
                            current = check_url(self._unroute(str(response.url.join(location))))
                            continue
                        return self._read(response, current, max_bytes)
            raise _fetch_failed(f"Followed more than {self._max_redirects} redirects")
        except BlockedAddressError as exc:
            logger.warning("Refused a source fetch to a non-public address (%s)", exc)
            raise _fetch_failed(
                "Only public web addresses can be fetched "
                "(sources.allow_private_urls in config.json allows others)"
            ) from exc
        except httpx.TimeoutException as exc:
            raise _fetch_failed(f"Timed out after {self._timeout:g} seconds") from exc
        # InvalidURL (a typo'd host, a tab in the URL) and StreamError aren't HTTPErrors
        except (httpx.HTTPError, httpx.InvalidURL, httpx.StreamError) as exc:
            # What went wrong stays in the log: an answer that says "refused" or "no route"
            # for a port is a port scan for whoever supplied the URL
            logger.warning("A source fetch failed: %s", exc)
            raise _fetch_failed("Could not fetch the page") from exc
        except ValueError as exc:  # check_url: not an http or https URL
            raise _fetch_failed(str(exc)) from exc

    def _client(self, proxy_origin: tuple[str, int] | None) -> httpx.Client:
        """A client for one request: no redirects, no proxy settings from the environment."""
        transport = self._transport or GuardedTransport(
            GuardedNetworkBackend(
                allowed_origin=proxy_origin, allow_private=self._allow_private_urls
            )
        )
        return httpx.Client(
            follow_redirects=False,
            trust_env=False,
            timeout=self._timeout,
            headers={"User-Agent": USER_AGENT},
            transport=transport,
        )

    def _read(self, response: httpx.Response, url: str, max_bytes: int) -> FetchedPage:
        """The page an answer carries, read up to the size limit."""
        if response.status_code >= 400:
            raise _fetch_failed(f"The server answered HTTP {response.status_code}")
        declared = response.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > max_bytes:
            raise _too_large(max_bytes)
        body = bytearray()
        for chunk in response.iter_bytes():
            body.extend(chunk)
            if len(body) > max_bytes:
                raise _too_large(max_bytes)
        return FetchedPage(
            data=bytes(body),
            content_type=response.headers.get("content-type"),
            url=url,
            file_name=_disposition_file_name(response.headers.get("content-disposition")),
        )

    def _route(self, url: str) -> str:
        """The URL to request: through the proxy when its site is proxied."""
        for site, via in self._proxied.items():
            if _on_site(url, site):
                return via + url[len(site) :]
        return url

    def _unroute(self, url: str) -> str:
        """A fetched page's URL as its site's own, not the proxy's."""
        for site, via in self._proxied.items():
            if _on_site(url, via):
                return site + url[len(via) :]
        return url


def _origin(url: str) -> tuple[str, int]:
    """The (host, port) a request to the URL connects to, as httpcore passes them on."""
    parsed = httpx.URL(url)
    return parsed.host.lower(), parsed.port or (443 if parsed.scheme == "https" else 80)


def _on_site(url: str, base: str) -> bool:
    """Whether a URL is the base URL or below it (scheme and host compared as written)."""
    return url == base or url.startswith(base + "/") or url.startswith(base + "?")


def _disposition_file_name(header: str | None) -> str | None:
    """The file name in a Content-Disposition header (filename or filename*), if any."""
    if not header:
        return None
    message = Message()
    message["content-disposition"] = header
    return message.get_filename()


def _fetch_failed(detail: str) -> SourceFailedError:
    return SourceFailedError(SourceFailure.FETCH_FAILED.value, detail)


def _too_large(max_bytes: int) -> SourceFailedError:
    return SourceFailedError(
        SourceFailure.TOO_LARGE.value, f"Larger than the {max_bytes // (1024 * 1024)} MB limit"
    )
