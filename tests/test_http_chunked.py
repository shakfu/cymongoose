"""Tests for HTTP chunked transfer encoding."""

import urllib.request

from cymongoose import MG_EV_HTTP_MSG, Manager
from tests.conftest import ServerThread


def test_http_chunk_method_exists():
    """Test that http_chunk method exists."""
    manager = Manager()

    try:
        listener = manager.listen("http://127.0.0.1:0")
        manager.poll(10)

        # Method should exist
        assert hasattr(listener, "http_chunk")
        assert callable(listener.http_chunk)
    finally:
        manager.close()


def test_http_chunked_response():
    """Test sending chunked HTTP response."""

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            # Send chunked response
            conn.send(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n")
            conn.http_chunk("First")
            conn.http_chunk("Second")
            conn.http_chunk("Third")
            conn.http_chunk("")  # End chunks

    with ServerThread(handler) as port:
        response = urllib.request.urlopen(f"http://localhost:{port}/", timeout=2)
        body = response.read().decode("utf-8")

        # All chunks should be concatenated
        assert "First" in body
        assert "Second" in body
        assert "Third" in body


def test_http_chunk_with_bytes():
    """Test http_chunk with bytes input."""

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            conn.send(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n")
            conn.http_chunk(b"Binary data")
            conn.http_chunk(b"More binary")
            conn.http_chunk(b"")  # End

    with ServerThread(handler) as port:
        response = urllib.request.urlopen(f"http://localhost:{port}/", timeout=2)
        body = response.read()

        assert b"Binary data" in body


def test_http_chunk_empty_ends_stream():
    """Test that empty chunk ends the stream."""

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            conn.send(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n")
            conn.http_chunk("Data")
            conn.http_chunk("")  # This should end the chunked stream

    with ServerThread(handler) as port:
        response = urllib.request.urlopen(f"http://localhost:{port}/", timeout=2)
        body = response.read()

        # Stream terminates cleanly and we get the data
        assert b"Data" in body


def test_http_chunk_unicode():
    """Test http_chunk with unicode strings."""

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            conn.send(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n")
            conn.http_chunk("Hello 世界")
            conn.http_chunk("Привет мир")
            conn.http_chunk("")

    with ServerThread(handler) as port:
        response = urllib.request.urlopen(f"http://localhost:{port}/", timeout=2)
        body = response.read().decode("utf-8")

        assert "Hello 世界" in body


def test_http_chunk_large_data():
    """Test http_chunk with large data."""
    large_chunk = "X" * 10000

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            conn.send(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n")
            conn.http_chunk(large_chunk)
            conn.http_chunk("")

    with ServerThread(handler) as port:
        response = urllib.request.urlopen(f"http://localhost:{port}/", timeout=2)
        body = response.read()

        assert len(body) >= 10000
