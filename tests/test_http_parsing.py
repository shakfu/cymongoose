"""Tests for HTTP status and header parsing functions."""

import urllib.request

from cymongoose import MG_EV_HTTP_MSG, Manager
from tests.conftest import ServerThread


def test_http_status_method_exists():
    """Test that HttpMessage.status() method exists and returns an integer."""
    status_result = []

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            # Access status() INSIDE the handler while message is valid
            status = data.status()
            status_result.append(status)
            conn.reply(200, b"OK")

    with ServerThread(handler) as port:
        # Make a request
        urllib.request.urlopen(f"http://localhost:{port}/", timeout=5)

    # Verify we captured a status
    assert len(status_result) > 0
    status = status_result[0]
    assert isinstance(status, int)
    assert status >= 0  # Valid status codes are >= 0


def test_http_header_var_method_exists():
    """Test that HttpMessage.header_var() method exists and works."""
    charset_result = []

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            # Access header_var() INSIDE the handler while message is valid
            charset = data.header_var("Content-Type", "charset")
            charset_result.append(charset)
            conn.reply(200, b"OK", headers={"Content-Type": "text/html; charset=utf-8"})

    with ServerThread(handler) as port:
        # Make a request with headers
        req = urllib.request.Request(
            f"http://localhost:{port}/", headers={"Content-Type": "application/json; charset=utf-8"}
        )
        urllib.request.urlopen(req, timeout=5)

    # Verify we called header_var()
    assert len(charset_result) > 0
    charset = charset_result[0]
    # Should return the charset value or None
    assert charset is None or isinstance(charset, str)


def test_http_header_var_not_found():
    """Test header_var returns None when variable not found."""
    results = []

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            # Access header_var() INSIDE the handler while message is valid
            # Try to get non-existent variable
            result1 = data.header_var("Content-Type", "nonexistent")
            # Try to get variable from non-existent header
            result2 = data.header_var("X-Custom-Header", "param")
            results.append((result1, result2))
            conn.reply(200, b"Test")

    with ServerThread(handler) as port:
        urllib.request.urlopen(f"http://localhost:{port}/", timeout=5)

    # Verify we got results
    assert len(results) > 0
    result1, result2 = results[0]
    assert result1 is None
    assert result2 is None


def test_http_status_none_when_invalid():
    """Test status() returns value for invalid/null message."""
    # Create an HttpMessage that's not assigned to anything
    from cymongoose._mongoose import HttpMessage

    msg = HttpMessage.__new__(HttpMessage)
    # _msg is NULL, so status() should return None
    assert msg.status() is None


def test_connection_error_method_exists():
    """Test that Connection.error() method exists."""
    from cymongoose import MG_EV_ERROR

    manager = Manager()
    errors = []

    def handler(conn, ev, data):
        if ev == MG_EV_ERROR:
            errors.append(data)

    try:
        listener = manager.listen("tcp://127.0.0.1:0", handler=handler)
        manager.poll(10)

        # Test error() method exists
        listener.error("Test error")
        manager.poll(10)

        # Should have triggered error event
        assert len(errors) > 0
    finally:
        manager.close()
