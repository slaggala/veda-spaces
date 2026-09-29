"""Client address handling (05 §4 A-01, 02 §11, SEC-006).

* The client IP comes from ``CF-Connecting-IP`` only when the TCP peer is a configured trusted proxy
  (the Cloudflare tunnel or edge in front of the origin); otherwise the peer address is the client (IR-35).
* Networks are IPv4 /24 and IPv6 /64, computed on parsed addresses so that compressed and IPv4-mapped
  IPv6 forms group correctly (IR-22).
"""

from __future__ import annotations

import ipaddress
from functools import lru_cache

from veda.config import settings


def parse(value: str | None) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    if not value:
        return None
    try:
        addr = ipaddress.ip_address(value.strip())
    except ValueError:
        return None
    if addr.version == 6 and addr.ipv4_mapped is not None:
        return addr.ipv4_mapped
    return addr


def network_of(ip: str | None) -> str:
    """IPv4 /24 or IPv6 /64 (05 §4, A-01)."""
    addr = parse(ip)
    if addr is None:
        return "unknown"
    prefix = 24 if addr.version == 4 else 64
    return str(ipaddress.ip_network(f"{addr}/{prefix}", strict=False))


def limiter_key(ip: str | None) -> str:
    """Per-IP limits count an IPv6 client by its /64, which one subscriber controls entirely."""
    addr = parse(ip)
    if addr is None:
        return "unknown"
    return str(addr) if addr.version == 4 else network_of(str(addr))


@lru_cache(maxsize=16)
def _networks(cidrs: tuple[str, ...]) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    return tuple(ipaddress.ip_network(c, strict=False) for c in cidrs)


def is_trusted_proxy(peer: str | None) -> bool:
    addr = parse(peer)
    return addr is not None and any(addr in n for n in _networks(tuple(settings().trusted_proxy_cidrs)))


def client_ip(peer: str | None, forwarded: str | None) -> str | None:
    if forwarded and is_trusted_proxy(peer):
        addr = parse(forwarded)
        if addr is not None:
            return str(addr)
    addr = parse(peer)
    return str(addr) if addr is not None else None


def mask(ip: str | None) -> str | None:
    """Display form: the first half of the address only."""
    addr = parse(ip)
    if addr is None:
        return None
    if addr.version == 4:
        a, b, _, _ = str(addr).split(".")
        return f"{a}.{b}.xxx.xxx"
    return ":".join(addr.exploded.split(":")[:3]) + ":xxxx"
