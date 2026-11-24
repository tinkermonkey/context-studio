"""Connect-time address check for fetched URL sources (#1656, SSRF).

The address is checked where the connection is made, on the address the socket
connects to. Resolving the name first and requesting it afterwards would let a
DNS answer change between the check and the connection (DNS rebinding).
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Iterable
from typing import Any

import httpcore
import httpx

_NAT64_PREFIX = ipaddress.ip_network("64:ff9b::/96")
_IPV4_COMPATIBLE_PREFIX = ipaddress.ip_network("::/96")  # deprecated ::a.b.c.d
_IPV4_TRANSLATED_PREFIX = ipaddress.ip_network("::ffff:0:0:0/96")  # SIIT
_SITE_LOCAL_PREFIX = ipaddress.ip_network("fec0::/10")  # deprecated private range


class BlockedAddressError(Exception):
    """A connection was refused because the host is not a public address."""


def is_public_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """
    Whether an address is routable on the public internet.

    Refuses loopback, private (RFC 1918 and ULA), link-local (169.254.0.0/16,
    which holds cloud metadata services), unspecified, shared (100.64.0.0/10),
    reserved and multicast addresses, and IPv6 forms that carry such an IPv4
    address (IPv4-mapped, IPv4-compatible, IPv4-translated, NAT64, 6to4, Teredo) and the
    deprecated site-local range.
    """
    if isinstance(address, ipaddress.IPv6Address):
        if address in _SITE_LOCAL_PREFIX:
            return False
        embedded = _embedded_ipv4(address)
        if embedded is not None:
            return is_public_address(embedded)
    return address.is_global and not address.is_multicast


def _embedded_ipv4(address: ipaddress.IPv6Address) -> ipaddress.IPv4Address | None:
    """The IPv4 address an IPv6 address wraps, if it wraps one."""
    if address.ipv4_mapped is not None:
        return address.ipv4_mapped
    if address in _NAT64_PREFIX or address in _IPV4_TRANSLATED_PREFIX:
        return ipaddress.IPv4Address(int(address) & 0xFFFFFFFF)
    if address in _IPV4_COMPATIBLE_PREFIX and int(address) > 1:  # not :: and ::1
        return ipaddress.IPv4Address(int(address) & 0xFFFFFFFF)
    if address.sixtofour is not None:
        return address.sixtofour
    if address.teredo is not None:
        return address.teredo[1]
    return None


class GuardedNetworkBackend(httpcore.NetworkBackend):
    """
    An httpcore network backend that connects only to public addresses.

    It resolves the host once, refuses the connection when any answer is not
    public, and connects to an address it vetted. The TLS server name stays the
    request's host, because httpcore takes it from the request and not from the
    address it connected to.
    """

    def __init__(
        self,
        allowed_origin: tuple[str, int] | None = None,
        allow_private: bool = False,
        inner: httpcore.NetworkBackend | None = None,
    ) -> None:
        """
        Args:
            allowed_origin: One (host, port) that connects without the check:
                the reference proxy's own address, which is on loopback
            allow_private: Skip the check (sources.allow_private_urls)
            inner: The backend that opens the sockets (tests pass a recording one)
        """
        self._allowed_origin = allowed_origin
        self._allow_private = allow_private
        self._inner = inner or httpcore.SyncBackend()

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore.NetworkStream:
        if self._allow_private or (host.lower(), port) == self._allowed_origin:
            return self._inner.connect_tcp(host, port, timeout, local_address, socket_options)

        addresses = _resolve(host, port)
        if not all(is_public_address(address) for address in addresses):
            raise BlockedAddressError(host)
        last_error: Exception = httpcore.ConnectError("The host name has no address")
        for address in addresses:
            try:
                return self._inner.connect_tcp(
                    str(address), port, timeout, local_address, socket_options
                )
            except httpcore.ConnectError as exc:
                last_error = exc
        raise last_error

    def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore.NetworkStream:
        raise BlockedAddressError(path)

    def sleep(self, seconds: float) -> None:
        self._inner.sleep(seconds)


def _resolve(host: str, port: int) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """The addresses a host name (or address literal) resolves to, in the resolver's order."""
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        # Refused like a private address, so the answer doesn't say which one it was
        raise BlockedAddressError(host) from exc
    addresses = []
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if address not in addresses:
            addresses.append(address)
    return addresses


class GuardedTransport(httpx.HTTPTransport):
    """An httpx transport whose connections all go through a GuardedNetworkBackend."""

    def __init__(self, backend: GuardedNetworkBackend) -> None:
        super().__init__()
        # httpx offers no parameter for a network backend; this is its connection pool's
        # seam. test_fetcher_private_addresses fails if an httpx upgrade moves it.
        self._pool._network_backend = backend  # type: ignore[attr-defined]
