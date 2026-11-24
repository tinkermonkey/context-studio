"""URL sources refuse loopback, private and link-local addresses (#1656, SSRF).

These use real sockets: the check sits in the connection, so a mock transport
would skip it. Local listeners count the requests they get, and a refused fetch
must leave their count at zero.
"""

import ipaddress
import socket
import threading
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import httpcore
import pytest

from adapters.sources.fetcher import HttpPageFetcher
from adapters.sources.network_guard import (
    BlockedAddressError,
    GuardedNetworkBackend,
    is_public_address,
)
from domain.extraction.exceptions import SourceFailedError

BLOCKED_DETAIL = "Only public web addresses can be fetched"
LOOPBACK_HOSTS = {"127.0.0.1", "::1"}
_original_connect = socket.socket.connect


def _loopback_only_connect(sock, address):
    """Refuse any connection that leaves this machine."""
    host = address[0] if isinstance(address, tuple) else address
    if sock.family in (socket.AF_INET, socket.AF_INET6) and host not in LOOPBACK_HOSTS:
        raise RuntimeError(f"Network access is blocked during test runs: {address}")
    return _original_connect(sock, address)


@pytest.fixture(autouse=True)
def block_network():
    """Overrides the integration conftest: these tests run listeners on loopback only."""
    with patch.object(socket.socket, "connect", _loopback_only_connect):
        yield



class Listener:
    """A local HTTP server that answers each path by a rule and records what it was asked."""

    def __init__(self, answer: Callable[[str], tuple[int, dict[str, str], bytes]]) -> None:
        self.paths: list[str] = []
        listener = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 (http.server's name)
                listener.paths.append(self.path)
                status, headers, body = answer(self.path)
                self.send_response(status)
                for name, value in headers.items():
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args) -> None:
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._server.server_address[1]
        threading.Thread(target=self._server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()

    @property
    def origin(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()


@pytest.fixture
def make_listener() -> Iterator[Callable[..., Listener]]:
    listeners: list[Listener] = []

    def make(answer=lambda path: (200, {"Content-Type": "text/plain"}, b"internal")) -> Listener:
        listeners.append(Listener(answer))
        return listeners[-1]

    yield make
    for listener in listeners:
        listener.close()


def refused(fetcher: HttpPageFetcher, url: str) -> SourceFailedError:
    with pytest.raises(SourceFailedError) as raised:
        fetcher.fetch(url, 10_000)
    return raised.value


# --- A direct private URL -------------------------------------------------------------


def test_a_direct_loopback_url_is_refused_without_a_request(make_listener):
    listener = make_listener()

    error = refused(HttpPageFetcher(timeout_seconds=2), f"{listener.origin}/secret")

    assert error.failure == "fetch_failed"
    assert BLOCKED_DETAIL in error.detail
    assert listener.paths == []


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/",
        "http://[::1]/",
        "http://0.0.0.0/",
        "http://10.1.2.3/",
        "http://172.16.0.9:8080/",
        "http://192.168.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://100.64.0.1/",
        "http://[fd00::1]/",
        "http://[fe80::1]/",
        "http://[::ffff:7f00:1]/",  # IPv4-mapped loopback
        "http://[64:ff9b::a00:1]/",  # NAT64 around 10.0.0.1
        "http://2130706433/",  # 127.0.0.1 as one number
        "http://0x7f.1/",  # 127.0.0.1 in hex
        "https://127.1/",
    ],
)
def test_private_forms_of_an_address_are_refused(url):
    error = refused(HttpPageFetcher(timeout_seconds=2), url)

    assert BLOCKED_DETAIL in error.detail
    # Nothing about the target comes back: not its address, not why
    assert "127" not in error.detail
    assert "169.254" not in error.detail


def test_every_refusal_reads_the_same_whatever_the_port_does(make_listener):
    """Open port, closed port: the answer can't tell them apart."""
    listener = make_listener()
    with socket.socket() as spare:
        spare.bind(("127.0.0.1", 0))
        closed = spare.getsockname()[1]

    fetcher = HttpPageFetcher(timeout_seconds=2)
    open_port = refused(fetcher, f"{listener.origin}/")
    closed_port = refused(fetcher, f"http://127.0.0.1:{closed}/")

    assert open_port.detail == closed_port.detail


# --- A name that resolves to a private address ----------------------------------------


@pytest.fixture
def resolves_to(monkeypatch):
    """Make getaddrinfo answer for chosen names, as DNS would."""
    real = socket.getaddrinfo
    answers: dict[str, list[str]] = {}

    def getaddrinfo(host, port, *args, **kwargs):
        if host in answers:
            return [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))
                for address in answers[host]
            ]
        return real(host, port, *args, **kwargs)

    monkeypatch.setattr("adapters.sources.network_guard.socket.getaddrinfo", getaddrinfo)
    return answers


def test_a_name_that_resolves_to_loopback_is_refused_without_a_request(make_listener, resolves_to):
    listener = make_listener()
    resolves_to["intranet.example.com"] = ["127.0.0.1"]

    error = refused(
        HttpPageFetcher(timeout_seconds=2), f"http://intranet.example.com:{listener.port}/x"
    )

    assert BLOCKED_DETAIL in error.detail
    assert listener.paths == []


def test_a_name_with_one_private_answer_among_public_ones_is_refused(resolves_to):
    resolves_to["mixed.example.com"] = ["93.184.216.34", "10.0.0.7"]

    error = refused(HttpPageFetcher(timeout_seconds=2), "http://mixed.example.com/")

    assert BLOCKED_DETAIL in error.detail


def test_a_name_that_does_not_resolve_is_a_failed_fetch_not_a_blocked_one(resolves_to):
    error = refused(HttpPageFetcher(timeout_seconds=2), "http://no-such-host.invalid/")

    assert error.detail == "Could not fetch the page"


class RecordingBackend(httpcore.NetworkBackend):
    """Records the address a connection is opened to, and opens none."""

    def __init__(self) -> None:
        self.connected: list[tuple[str, int]] = []

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        self.connected.append((host, port))
        raise httpcore.ConnectError("recording backend")

    def connect_unix_socket(self, path, timeout=None, socket_options=None):
        raise httpcore.ConnectError("recording backend")

    def sleep(self, seconds: float) -> None:
        pass


def test_the_connection_goes_to_the_address_that_was_checked(monkeypatch):
    """DNS rebinding: a name that answers public once and private the next time."""
    answers = iter(["93.184.216.34", "127.0.0.1"])
    monkeypatch.setattr(
        "adapters.sources.network_guard.socket.getaddrinfo",
        lambda host, port, *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (next(answers), port))
        ],
    )
    recording = RecordingBackend()
    backend = GuardedNetworkBackend(inner=recording)

    with pytest.raises(httpcore.ConnectError):  # the recording backend opens nothing
        backend.connect_tcp("rebind.example.com", 80)
    with pytest.raises(BlockedAddressError):  # the next answer is private
        backend.connect_tcp("rebind.example.com", 80)

    # One lookup per connection, and the vetted address is what was connected to,
    # not the name (which could resolve elsewhere by then)
    assert recording.connected == [("93.184.216.34", 80)]


# --- A redirect to a private address ---------------------------------------------------

WIKIPEDIA = "https://en.wikipedia.org"


def through_proxy(listener: Listener) -> HttpPageFetcher:
    return HttpPageFetcher(timeout_seconds=2, proxied={WIKIPEDIA: f"{listener.origin}/wikipedia"})


def test_the_reference_proxy_is_fetched_and_its_page_comes_back_under_the_sites_url(
    make_listener,
):
    proxy = make_listener(lambda path: (200, {"Content-Type": "text/html"}, b"<p>ribosome</p>"))

    page = through_proxy(proxy).fetch(f"{WIKIPEDIA}/wiki/Ribosome", 10_000)

    assert proxy.paths == ["/wikipedia/wiki/Ribosome"]
    assert page.data == b"<p>ribosome</p>"
    assert page.url == f"{WIKIPEDIA}/wiki/Ribosome"


@pytest.mark.parametrize(
    "target",
    ["http://169.254.169.254/latest/meta-data/", "http://localhost:9/", "http://10.0.0.1/admin"],
)
def test_a_redirect_to_a_private_address_is_refused(make_listener, target):
    proxy = make_listener(lambda path: (302, {"Location": target}, b""))

    error = refused(through_proxy(proxy), f"{WIKIPEDIA}/wiki/Ribosome")

    assert BLOCKED_DETAIL in error.detail
    assert proxy.paths == ["/wikipedia/wiki/Ribosome"]


def test_a_redirect_to_another_local_service_is_refused_and_never_requested(make_listener):
    internal = make_listener()
    proxy = make_listener(lambda path: (302, {"Location": f"{internal.origin}/secret"}, b""))

    error = refused(through_proxy(proxy), f"{WIKIPEDIA}/wiki/Ribosome")

    assert BLOCKED_DETAIL in error.detail
    assert internal.paths == []


def test_a_redirect_does_not_inherit_the_proxy_exception_for_other_paths_on_it(make_listener):
    """Only the proxied site's own pages go to the proxy; a Location on its origin is just loopback."""
    proxy = make_listener(
        lambda path: (
            (302, {"Location": "/conceptnet/c/en/x"}, b"")
            if path.startswith("/wikipedia/")
            else (200, {"Content-Type": "text/plain"}, b"other route")
        )
    )

    error = refused(through_proxy(proxy), f"{WIKIPEDIA}/wiki/Ribosome")

    assert BLOCKED_DETAIL in error.detail
    assert proxy.paths == ["/wikipedia/wiki/Ribosome"]


def test_redirects_stop_after_the_limit(make_listener):
    loop = make_listener(lambda path: (302, {"Location": "/again"}, b""))
    fetcher = HttpPageFetcher(timeout_seconds=2, max_redirects=3, allow_private_urls=True)

    error = refused(fetcher, f"{loop.origin}/start")

    assert "redirects" in error.detail
    assert len(loop.paths) == 4


def test_a_redirect_to_a_non_http_scheme_is_refused(make_listener):
    proxy = make_listener(lambda path: (302, {"Location": "file:///etc/passwd"}, b""))

    error = refused(through_proxy(proxy), f"{WIKIPEDIA}/wiki/Ribosome")

    assert error.failure == "fetch_failed"


# --- The explicit exception -------------------------------------------------------------


def test_allow_private_urls_fetches_a_local_server(make_listener):
    listener = make_listener()

    page = HttpPageFetcher(timeout_seconds=2, allow_private_urls=True).fetch(
        f"{listener.origin}/doc", 10_000
    )

    assert page.data == b"internal"
    assert listener.paths == ["/doc"]


def test_proxy_environment_variables_are_ignored(make_listener, monkeypatch):
    """An HTTP_PROXY in the environment must not decide where the connection goes."""
    listener = make_listener()
    with socket.socket() as spare:
        spare.bind(("127.0.0.1", 0))
        dead_proxy = spare.getsockname()[1]
    monkeypatch.setenv("HTTP_PROXY", f"http://127.0.0.1:{dead_proxy}")
    monkeypatch.setenv("http_proxy", f"http://127.0.0.1:{dead_proxy}")

    page = HttpPageFetcher(timeout_seconds=2, allow_private_urls=True).fetch(
        f"{listener.origin}/doc", 10_000
    )

    assert page.data == b"internal"


def test_a_failed_connection_says_nothing_about_why():
    with socket.socket() as spare:
        spare.bind(("127.0.0.1", 0))
        closed = spare.getsockname()[1]

    error = refused(
        HttpPageFetcher(timeout_seconds=2, allow_private_urls=True), f"http://127.0.0.1:{closed}/"
    )

    assert error.detail == "Could not fetch the page"


# --- The address check itself -------------------------------------------------------------


@pytest.mark.parametrize(
    "address, public",
    [
        ("93.184.216.34", True),
        ("8.8.8.8", True),
        ("2606:4700:4700::1111", True),
        ("127.0.0.1", False),
        ("127.255.255.254", False),
        ("10.0.0.1", False),
        ("172.31.255.255", False),
        ("192.168.1.1", False),
        ("169.254.169.254", False),
        ("0.0.0.0", False),
        ("100.64.0.1", False),
        ("224.0.0.1", False),
        ("255.255.255.255", False),
        ("::", False),
        ("::1", False),
        ("fc00::1", False),
        ("fd12:3456::1", False),
        ("fe80::1", False),
        ("ff02::1", False),
        ("::ffff:10.0.0.1", False),
        ("::ffff:93.184.216.34", True),
        ("64:ff9b::7f00:1", False),
        ("2002:a00:1::", False),
    ],
)
def test_which_addresses_are_public(address, public):
    assert is_public_address(ipaddress.ip_address(address)) is public


def test_a_unix_socket_is_never_connected():
    with pytest.raises(BlockedAddressError):
        GuardedNetworkBackend(inner=RecordingBackend()).connect_unix_socket("/var/run/docker.sock")
