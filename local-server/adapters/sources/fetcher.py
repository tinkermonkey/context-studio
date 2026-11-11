"""PageFetcher adapter over httpx: one http or https page, size-limited (#1551)."""

from __future__ import annotations

from email.message import Message

import httpx

from domain.extraction.exceptions import SourceFailedError
from domain.extraction.sources import FetchedPage, SourceFailure, check_url

USER_AGENT = "ContextStudio/1.0 (+source fetch)"


class HttpPageFetcher:
    """Fetches one page, following redirects, and stops reading past the size limit."""

    def __init__(
        self,
        timeout_seconds: float = 30.0,
        max_redirects: int = 5,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._timeout = timeout_seconds
        self._max_redirects = max_redirects
        self._transport = transport  # tests pass an httpx.MockTransport

    def fetch(self, url: str, max_bytes: int) -> FetchedPage:
        try:
            with httpx.Client(
                follow_redirects=True,
                max_redirects=self._max_redirects,
                timeout=self._timeout,
                headers={"User-Agent": USER_AGENT},
                transport=self._transport,
            ) as client:
                with client.stream("GET", check_url(url)) as response:
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
                        url=str(response.url),
                        file_name=_disposition_file_name(
                            response.headers.get("content-disposition")
                        ),
                    )
        except httpx.TimeoutException as exc:
            raise _fetch_failed(f"Timed out after {self._timeout:g} seconds") from exc
        # InvalidURL (a typo'd host, a tab in the URL) and StreamError aren't HTTPErrors
        except (httpx.HTTPError, httpx.InvalidURL, httpx.StreamError) as exc:
            raise _fetch_failed(f"Could not fetch the page ({exc})") from exc
        except ValueError as exc:  # check_url: not an http or https URL
            raise _fetch_failed(str(exc)) from exc


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
