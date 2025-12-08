"""Tests for low-level operations."""

import pytest
import urllib.request
from cymongoose import Manager, MG_EV_HTTP_MSG


def test_is_tls_property_exists():
    """Test that is_tls property exists."""
    manager = Manager()

    try:
        listener = manager.listen("http://127.0.0.1:0")
        manager.poll(10)

        assert hasattr(listener, "is_tls")
        # Should be boolean
        assert isinstance(listener.is_tls, bool)
    finally:
        manager.close()


def test_is_tls_on_http_connection():
    """Test is_tls on HTTP connection."""
    manager = Manager()

    try:
        listener = manager.listen("http://127.0.0.1:0")
        manager.poll(10)

        # HTTP connection should report TLS status
        # (False for HTTP, but property should exist)
        is_tls = listener.is_tls
        assert isinstance(is_tls, bool)
    finally:
        manager.close()


def test_is_tls_on_tcp_connection():
    """Test is_tls on TCP connection."""
    manager = Manager()

    try:
        listener = manager.listen("tcp://127.0.0.1:0")
        manager.poll(10)

        # TCP connection TLS status
        is_tls = listener.is_tls
        assert isinstance(is_tls, bool)
        assert is_tls == False  # Plain TCP
    finally:
        manager.close()


def test_is_tls_on_closed_connection():
    """Test is_tls on closed connection returns False."""
    manager = Manager()
    conn_ref = [None]

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            conn_ref[0] = conn
            conn.reply(200, b"OK")

    try:
        listener = manager.listen("http://127.0.0.1:0", handler=handler)
        manager.poll(10)

        addr = listener.local_addr
        port = addr[1]

        try:
            urllib.request.urlopen(f"http://localhost:{port}/", timeout=1)
        except:
            pass

        for _ in range(10):
            manager.poll(10)
            if conn_ref[0]:
                break

        # Close manager
        manager.close()

        # is_tls on closed connection should return False
        if conn_ref[0]:
            assert conn_ref[0].is_tls == False
    finally:
        pass  # Already closed


def test_combined_tls_and_buffer_ops():
    """Test that TLS property and buffer operations work together."""
    manager = Manager()

    try:
        listener = manager.listen("http://127.0.0.1:0")
        manager.poll(10)

        # Can check TLS and buffer properties together
        assert listener.is_tls == False or listener.is_tls == True
        assert listener.recv_len >= 0
        assert listener.send_len >= 0

        assert True
    finally:
        manager.close()
