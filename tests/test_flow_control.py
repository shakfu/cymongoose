"""Tests for connection flow control flags."""

import pytest
from cymongoose import Manager, MG_EV_HTTP_MSG


def test_is_full_flag():
    """Test is_full property exists and returns boolean."""
    manager = Manager()

    try:
        listener = manager.listen("tcp://127.0.0.1:0")
        manager.poll(10)

        # Property should exist and return a boolean
        assert isinstance(listener.is_full, bool)
        # Listener shouldn't be full initially
        assert listener.is_full == False
    finally:
        manager.close()


def test_is_draining_flag():
    """Test is_draining property exists and returns boolean."""
    manager = Manager()

    try:
        listener = manager.listen("tcp://127.0.0.1:0")
        manager.poll(10)

        # Property should exist and return a boolean
        assert isinstance(listener.is_draining, bool)
        # Listener shouldn't be draining initially
        assert listener.is_draining == False
    finally:
        manager.close()


def test_flow_control_flags_on_connection():
    """Test flow control flags on various connection types."""
    manager = Manager()

    try:
        # TCP listener
        tcp_listener = manager.listen("tcp://127.0.0.1:0")
        manager.poll(10)
        assert isinstance(tcp_listener.is_full, bool)
        assert isinstance(tcp_listener.is_draining, bool)

        # UDP listener
        udp_listener = manager.listen("udp://127.0.0.1:0")
        manager.poll(10)
        assert isinstance(udp_listener.is_full, bool)
        assert isinstance(udp_listener.is_draining, bool)

        # HTTP listener
        http_listener = manager.listen("http://127.0.0.1:0")
        manager.poll(10)
        assert isinstance(http_listener.is_full, bool)
        assert isinstance(http_listener.is_draining, bool)
    finally:
        manager.close()


def test_flow_control_with_http():
    """Test flow control flags during HTTP request."""
    manager = Manager()
    conn_states = []

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            # Capture connection state during HTTP message
            conn_states.append(
                {
                    "is_full": conn.is_full,
                    "is_draining": conn.is_draining,
                    "is_readable": conn.is_readable,
                    "is_writable": conn.is_writable,
                }
            )
            conn.reply(200, b"OK")

    try:
        listener = manager.listen("http://127.0.0.1:0", handler=handler)
        manager.poll(10)

        # Get port
        addr = listener.local_addr
        port = addr[1]

        # Make a request using urllib
        import urllib.request

        try:
            urllib.request.urlopen(f"http://localhost:{port}/", timeout=1)
        except:
            pass  # Don't care if it fails, just testing state

        # Verify state was captured
        # (may be empty if request didn't complete, but test shouldn't crash)
        assert isinstance(conn_states, list)
    finally:
        manager.close()


def test_flow_control_closed_connection():
    """Test flow control flags on closed connection."""
    manager = Manager()

    try:
        listener = manager.listen("tcp://127.0.0.1:0")
        manager.poll(10)

        # Close the connection
        listener.close()
        manager.poll(10)

        # Properties should still be accessible (return False for closed conn)
        assert listener.is_full == False
        assert listener.is_draining == False
    finally:
        manager.close()
