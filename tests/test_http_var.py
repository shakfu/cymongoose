"""Tests for mg_http_var based variable extraction."""

import cymongoose as cm


class TestHttpVar:
    def test_simple_query(self):
        assert cm.http_var("foo=bar&baz=qux", "foo") == "bar"

    def test_second_param(self):
        assert cm.http_var("foo=bar&baz=qux", "baz") == "qux"

    def test_missing_param(self):
        assert cm.http_var("foo=bar", "missing") is None

    def test_empty_value(self):
        assert cm.http_var("foo=&bar=1", "foo") == ""

    def test_url_encoded(self):
        result = cm.http_var("msg=hello+world", "msg")
        assert result is not None

    def test_bytes_input(self):
        assert cm.http_var(b"key=val", "key") == "val"

    def test_empty_buffer(self):
        assert cm.http_var("", "foo") is None
