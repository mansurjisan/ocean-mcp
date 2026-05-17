"""Shared fixtures for erddap-mcp tests."""

import ipaddress

import pytest

import erddap_mcp.client as _erddap_client
from erddap_mcp.client import ERDDAPClient


@pytest.fixture(autouse=True)
def _hermetic_dns(request, monkeypatch):
    """Stub DNS for the SSRF guard so unit tests stay offline.

    respx already stubs the HTTP layer; the SSRF guard added to the client
    additionally resolves hostnames, so unit tests must stub DNS too. IP
    literals pass through unchanged (so private/link-local addresses are
    still correctly classified and blocked); hostnames resolve to a fixed
    public IP. Integration tests (live network) are left untouched.
    """
    if request.node.get_closest_marker("integration"):
        return

    def fake_getaddrinfo(host, port, *args, **kwargs):
        if host in ("localhost", "localhost.localdomain"):
            ip = "127.0.0.1"  # realistic: localhost is always loopback
        else:
            try:
                ip = str(ipaddress.ip_address(host))
            except ValueError:
                ip = "93.184.216.34"  # public address (documentation range)
        return [(2, 1, 6, "", (ip, port or 0))]

    monkeypatch.setattr(_erddap_client.socket, "getaddrinfo", fake_getaddrinfo)


@pytest.fixture
async def client():
    """Create an ERDDAPClient and close it after the test."""
    c = ERDDAPClient()
    yield c
    await c.close()
