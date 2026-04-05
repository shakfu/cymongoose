"""Tests for URL parsing utilities."""

import cymongoose as cm


class TestUrlPort:
    def test_explicit_port(self):
        assert cm.url_port("http://example.com:8080/path") == 8080

    def test_default_http(self):
        assert cm.url_port("http://example.com/path") == 80

    def test_default_https(self):
        assert cm.url_port("https://example.com/path") == 443

    def test_default_ws(self):
        assert cm.url_port("ws://example.com/path") == 80

    def test_default_wss(self):
        assert cm.url_port("wss://example.com/path") == 443

    def test_default_mqtt(self):
        assert cm.url_port("mqtt://example.com") == 1883

    def test_default_mqtts(self):
        assert cm.url_port("mqtts://example.com") == 8883


class TestUrlHost:
    def test_simple(self):
        assert cm.url_host("http://example.com/path") == "example.com"

    def test_with_port(self):
        assert cm.url_host("http://example.com:8080/path") == "example.com"

    def test_ip_address(self):
        assert cm.url_host("http://192.168.1.1:80/") == "192.168.1.1"

    def test_with_userinfo(self):
        assert cm.url_host("http://user:pass@example.com/") == "example.com"


class TestUrlUser:
    def test_with_user(self):
        assert cm.url_user("http://admin:secret@example.com/") == "admin"

    def test_no_user(self):
        assert cm.url_user("http://example.com/") == ""

    def test_user_no_password(self):
        assert cm.url_user("http://admin@example.com/") == "admin"


class TestUrlPass:
    def test_with_password(self):
        assert cm.url_pass("http://admin:secret@example.com/") == "secret"

    def test_no_password(self):
        assert cm.url_pass("http://example.com/") == ""


class TestUrlUri:
    def test_with_path(self):
        assert cm.url_uri("http://example.com/api/v1") == "/api/v1"

    def test_root(self):
        assert cm.url_uri("http://example.com/") == "/"

    def test_no_path(self):
        assert cm.url_uri("http://example.com") == "/"

    def test_with_query(self):
        assert cm.url_uri("http://example.com/search?q=test") == "/search?q=test"


class TestUrlIsSsl:
    def test_https(self):
        assert cm.url_is_ssl("https://example.com") is True

    def test_http(self):
        assert cm.url_is_ssl("http://example.com") is False

    def test_wss(self):
        assert cm.url_is_ssl("wss://example.com") is True

    def test_ws(self):
        assert cm.url_is_ssl("ws://example.com") is False

    def test_mqtts(self):
        assert cm.url_is_ssl("mqtts://example.com") is True
