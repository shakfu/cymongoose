"""Tests for HTTP Server-Sent Events (SSE)."""

import urllib.request

from cymongoose import MG_EV_HTTP_MSG, Manager
from tests.conftest import ServerThread


def test_http_sse_method_exists():
    """Test that http_sse method exists."""
    manager = Manager()

    try:
        listener = manager.listen("http://127.0.0.1:0")
        manager.poll(10)

        # Method should exist
        assert hasattr(listener, "http_sse")
        assert callable(listener.http_sse)
    finally:
        manager.close()


def test_http_sse_basic():
    """Test basic SSE message sending."""

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            # Send SSE headers
            conn.send(b"HTTP/1.1 200 OK\r\n")
            conn.send(b"Content-Type: text/event-stream\r\n")
            conn.send(b"Cache-Control: no-cache\r\n")
            conn.send(b"Transfer-Encoding: chunked\r\n\r\n")

            # Send SSE events
            conn.http_sse("message", "Hello SSE")
            conn.http_sse("update", "Status: OK")
            conn.http_chunk("")  # End stream

    with ServerThread(handler) as port:
        response = urllib.request.urlopen(f"http://localhost:{port}/", timeout=2)
        body = response.read().decode("utf-8")

        # Should contain SSE formatted data
        assert "Hello SSE" in body


def test_http_sse_format():
    """Test SSE message format."""

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            conn.send(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n")
            conn.http_sse("test", "data123")
            conn.http_chunk("")

    with ServerThread(handler) as port:
        response = urllib.request.urlopen(f"http://localhost:{port}/", timeout=2)
        body = response.read()

        # SSE format should include event and data fields
        assert b"test" in body
        assert b"data123" in body


def test_http_sse_multiple_events():
    """Test sending multiple SSE events."""
    events_sent = []

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            conn.send(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n")

            for i in range(3):
                event_type = f"event{i}"
                event_data = f"data{i}"
                conn.http_sse(event_type, event_data)
                events_sent.append((event_type, event_data))

            conn.http_chunk("")

    with ServerThread(handler) as port:
        try:
            urllib.request.urlopen(f"http://localhost:{port}/", timeout=2)
        except Exception:
            pass

        # Should have sent 3 events
        assert len(events_sent) == 3


def test_http_sse_unicode():
    """Test SSE with unicode strings."""

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            conn.send(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n")
            conn.http_sse("message", "Hello 世界")
            conn.http_sse("update", "Привет мир")
            conn.http_chunk("")

    with ServerThread(handler) as port:
        response = urllib.request.urlopen(f"http://localhost:{port}/", timeout=2)
        body = response.read()

        assert len(body) > 0


def test_http_sse_empty_data():
    """Test SSE with empty data."""

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            conn.send(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n")
            conn.http_sse("ping", "")
            conn.http_chunk("")

    with ServerThread(handler) as port:
        response = urllib.request.urlopen(f"http://localhost:{port}/", timeout=2)
        body = response.read()

        assert b"ping" in body


def test_http_sse_long_data():
    """Test SSE with long data payload."""
    large_data = "X" * 1000

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            conn.send(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n")
            conn.http_sse("message", large_data)
            conn.http_chunk("")

    with ServerThread(handler) as port:
        response = urllib.request.urlopen(f"http://localhost:{port}/", timeout=2)
        body = response.read()

        assert len(body) >= 1000
