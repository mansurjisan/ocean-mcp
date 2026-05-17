"""Pydantic and enum validation tests for erddap-mcp models."""

import pytest

from erddap_mcp.models import Protocol, ResponseFormat
from erddap_mcp.registry import ERDDAPServer, SERVERS, get_servers


class TestProtocolEnum:
    """Tests for the Protocol str enum."""

    def test_griddap_value(self):
        """Protocol.GRIDDAP has the string value 'griddap'."""
        assert Protocol.GRIDDAP == "griddap"
        assert Protocol.GRIDDAP.value == "griddap"

    def test_tabledap_value(self):
        """Protocol.TABLEDAP has the string value 'tabledap'."""
        assert Protocol.TABLEDAP == "tabledap"
        assert Protocol.TABLEDAP.value == "tabledap"

    def test_create_from_valid_string(self):
        """Protocol can be created from its valid string values."""
        assert Protocol("griddap") is Protocol.GRIDDAP
        assert Protocol("tabledap") is Protocol.TABLEDAP

    def test_reject_invalid_string(self):
        """Protocol rejects values not in the enum."""
        with pytest.raises(ValueError):
            Protocol("invalid")

    def test_reject_empty_string(self):
        """Protocol rejects an empty string."""
        with pytest.raises(ValueError):
            Protocol("")

    def test_is_str_subclass(self):
        """Protocol members are also plain strings."""
        assert isinstance(Protocol.GRIDDAP, str)


class TestResponseFormatEnum:
    """Tests for the ResponseFormat str enum."""

    def test_markdown_value(self):
        """ResponseFormat.MARKDOWN has the string value 'markdown'."""
        assert ResponseFormat.MARKDOWN == "markdown"
        assert ResponseFormat.MARKDOWN.value == "markdown"

    def test_json_value(self):
        """ResponseFormat.JSON has the string value 'json'."""
        assert ResponseFormat.JSON == "json"
        assert ResponseFormat.JSON.value == "json"

    def test_create_from_valid_string(self):
        """ResponseFormat can be created from its valid string values."""
        assert ResponseFormat("markdown") is ResponseFormat.MARKDOWN
        assert ResponseFormat("json") is ResponseFormat.JSON

    def test_reject_invalid_string(self):
        """ResponseFormat rejects values not in the enum."""
        with pytest.raises(ValueError):
            ResponseFormat("xml")

    def test_reject_empty_string(self):
        """ResponseFormat rejects an empty string."""
        with pytest.raises(ValueError):
            ResponseFormat("")

    def test_is_str_subclass(self):
        """ResponseFormat members are also plain strings."""
        assert isinstance(ResponseFormat.MARKDOWN, str)


class TestERDDAPServerDataclass:
    """Tests for the ERDDAPServer dataclass."""

    def test_instantiation(self):
        """ERDDAPServer can be instantiated with required fields."""
        server = ERDDAPServer(
            name="Test Server",
            url="https://example.com/erddap",
            focus="Testing",
            region="Global",
        )
        assert server.name == "Test Server"
        assert server.url == "https://example.com/erddap"
        assert server.focus == "Testing"
        assert server.region == "Global"

    def test_equality(self):
        """Two ERDDAPServer instances with the same fields are equal."""
        a = ERDDAPServer(name="A", url="https://a.com", focus="f", region="r")
        b = ERDDAPServer(name="A", url="https://a.com", focus="f", region="r")
        assert a == b


class TestServerRegistry:
    """Tests for the built-in ERDDAP server registry."""

    def test_servers_list_is_non_empty(self):
        """The SERVERS list contains at least one entry."""
        assert len(SERVERS) > 0

    def test_all_entries_are_erddap_server(self):
        """Every entry in SERVERS is an ERDDAPServer instance."""
        for server in SERVERS:
            assert isinstance(server, ERDDAPServer)

    def test_coastwatch_in_registry(self):
        """CoastWatch West Coast server is present in the registry."""
        names = [s.name for s in SERVERS]
        assert "CoastWatch West Coast" in names

    def test_get_servers_no_filter_returns_all(self):
        """get_servers with no filter returns the full list."""
        result = get_servers()
        assert result == SERVERS

    def test_get_servers_filter_by_region(self):
        """get_servers filters by region (case-insensitive substring)."""
        result = get_servers(region="global")
        assert len(result) > 0
        for s in result:
            assert "global" in s.region.lower()

    def test_get_servers_filter_by_keyword(self):
        """get_servers filters by keyword across name, focus, and region."""
        result = get_servers(keyword="glider")
        assert len(result) > 0
        for s in result:
            text = (s.name + s.focus + s.region).lower()
            assert "glider" in text

    def test_get_servers_no_match(self):
        """get_servers returns empty list when nothing matches."""
        result = get_servers(keyword="zzz_nonexistent_zzz")
        assert result == []


class TestSSRFGuard:
    """SSRF guard for the caller-supplied server_url (_validate_public_http_url)."""

    def test_security_error_is_value_error(self):
        """ERDDAPSecurityError is a ValueError so existing handlers catch it."""
        from erddap_mcp.client import ERDDAPSecurityError

        assert issubclass(ERDDAPSecurityError, ValueError)

    @pytest.mark.parametrize(
        "url",
        [
            "file:///etc/passwd",
            "ftp://example.com/x",
            "gopher://example.com/",
            "dict://example.com:11211/",
            "//example.com/no-scheme",
            "ssh://example.com",
        ],
    )
    def test_blocks_non_http_schemes(self, url):
        """Non-http(s) schemes are rejected."""
        from erddap_mcp.client import ERDDAPSecurityError, _validate_public_http_url

        with pytest.raises(ERDDAPSecurityError):
            _validate_public_http_url(url)

    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1/erddap",
            "http://localhost/erddap",
            "http://169.254.169.254/latest/meta-data/",  # cloud metadata
            "http://10.0.0.5/erddap",
            "http://192.168.1.10/erddap",
            "http://172.16.0.1/erddap",
            "http://[::1]/erddap",
            "http://0.0.0.0/erddap",
        ],
    )
    def test_blocks_private_and_internal_hosts(self, url):
        """Loopback, RFC1918, link-local (incl. 169.254.169.254) are rejected."""
        from erddap_mcp.client import ERDDAPSecurityError, _validate_public_http_url

        with pytest.raises(ERDDAPSecurityError):
            _validate_public_http_url(url)

    def test_allows_public_host(self, monkeypatch):
        """A host resolving only to public IPs passes (DNS stubbed: hermetic)."""
        import erddap_mcp.client as c
        from erddap_mcp.client import _validate_public_http_url

        def fake_gai(host, port, *a, **k):
            import ipaddress

            try:
                ip = str(ipaddress.ip_address(host))
            except ValueError:
                ip = "93.184.216.34"  # public (example.com range)
            return [(2, 1, 6, "", (ip, port or 0))]

        monkeypatch.setattr(c.socket, "getaddrinfo", fake_gai)
        # Should not raise.
        _validate_public_http_url("https://coastwatch.pfeg.noaa.gov/erddap")

    def test_blocks_public_name_resolving_to_private(self, monkeypatch):
        """DNS-rebinding style: a name resolving to a private IP is rejected."""
        import erddap_mcp.client as c
        from erddap_mcp.client import ERDDAPSecurityError, _validate_public_http_url

        monkeypatch.setattr(
            c.socket,
            "getaddrinfo",
            lambda *a, **k: [(2, 1, 6, "", ("10.0.0.1", 0))],
        )
        with pytest.raises(ERDDAPSecurityError):
            _validate_public_http_url("https://innocent.example.com/erddap")
