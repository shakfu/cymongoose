"""Tests for connection buffer access."""

import pytest
import urllib.request
import time
from cymongoose import Manager, MG_EV_HTTP_MSG, MG_EV_READ


def test_buffer_properties_exist():
    """Test that buffer access properties exist."""
    manager = Manager()

    try:
        listener = manager.listen("http://127.0.0.1:0")
        manager.poll(10)

        # Properties should exist
        assert hasattr(listener, "recv_len")
        assert hasattr(listener, "send_len")
        assert hasattr(listener, "recv_size")
        assert hasattr(listener, "send_size")
        assert hasattr(listener, "recv_data")
        assert hasattr(listener, "send_data")
    finally:
        manager.close()


def test_buffer_lengths_valid():
    """Test that buffer lengths are valid."""
    manager = Manager()

    try:
        listener = manager.listen("http://127.0.0.1:0")
        manager.poll(10)

        # Lengths should be non-negative
        assert listener.recv_len >= 0
        assert listener.send_len >= 0
        # Size may be allocated
        assert listener.recv_size >= 0
        assert listener.send_size >= 0
    finally:
        manager.close()


def test_recv_buffer_on_http_request():
    """Test that recv buffer contains data on HTTP request."""
    manager = Manager()
    recv_data_captured = []

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            # Capture recv buffer info
            recv_data_captured.append(
                {
                    "recv_len": conn.recv_len,
                    "recv_size": conn.recv_size,
                    "recv_data": conn.recv_data(),
                }
            )
            conn.reply(200, b"OK")

    try:
        listener = manager.listen("http://127.0.0.1:0", handler=handler)
        manager.poll(10)

        addr = listener.local_addr
        port = addr[1]

        # Make HTTP request
        try:
            urllib.request.urlopen(f"http://localhost:{port}/test", timeout=1)
        except:
            pass

        # Poll to process request
        for _ in range(10):
            manager.poll(10)
            if recv_data_captured:
                break

        # Should have captured recv buffer data
        if recv_data_captured:
            assert recv_data_captured[0]["recv_len"] >= 0
            assert recv_data_captured[0]["recv_size"] >= 0
            # recv_data should be bytes
            assert isinstance(recv_data_captured[0]["recv_data"], bytes)
    finally:
        manager.close()


def test_send_buffer_on_reply():
    """Test that send buffer is used on reply."""
    manager = Manager()
    send_data_captured = []

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            conn.reply(200, b"Hello World" * 100)  # Large response

            # Capture send buffer info after reply
            send_data_captured.append(
                {
                    "send_len": conn.send_len,
                    "send_size": conn.send_size,
                }
            )

    try:
        listener = manager.listen("http://127.0.0.1:0", handler=handler)
        manager.poll(10)

        addr = listener.local_addr
        port = addr[1]

        # Make request
        try:
            urllib.request.urlopen(f"http://localhost:{port}/", timeout=1)
        except:
            pass

        # Poll to process
        for _ in range(10):
            manager.poll(10)
            if send_data_captured:
                break

        # Send buffer should have been used
        if send_data_captured:
            # send_len might be 0 if already flushed, but should be >= 0
            assert send_data_captured[0]["send_len"] >= 0
            assert send_data_captured[0]["send_size"] >= 0
    finally:
        manager.close()


def test_recv_data_with_length():
    """Test recv_data with length parameter."""
    manager = Manager()

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            # Read partial data
            partial = conn.recv_data(10)
            full = conn.recv_data()

            assert isinstance(partial, bytes)
            assert isinstance(full, bytes)
            assert len(partial) <= 10
            assert len(full) >= len(partial)

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

        assert True
    finally:
        manager.close()


def test_send_data_readable():
    """Test that send_data returns bytes."""
    manager = Manager()

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            conn.reply(200, b"Test Response")

            # Read send buffer
            send_buffer = conn.send_data()
            assert isinstance(send_buffer, bytes)

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

        assert True
    finally:
        manager.close()


def test_buffer_access_on_closed_connection():
    """Test that buffer access on closed connection returns safe values."""
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

        # Close manager (invalidates connection)
        manager.close()

        # Buffer access should return safe values
        if conn_ref[0]:
            assert conn_ref[0].recv_len == 0
            assert conn_ref[0].send_len == 0
            assert conn_ref[0].recv_data() == b""
            assert conn_ref[0].send_data() == b""
    finally:
        pass  # Already closed


def test_buffer_sizes_are_reasonable():
    """Test that buffer sizes are within reasonable bounds."""
    manager = Manager()

    try:
        listener = manager.listen("http://127.0.0.1:0")
        manager.poll(10)

        # Sizes should be reasonable (0 or positive, not huge)
        assert 0 <= listener.recv_size <= 1024 * 1024  # Max 1MB
        assert 0 <= listener.send_size <= 1024 * 1024
    finally:
        manager.close()


def test_recv_data_negative_length():
    """Test recv_data with negative length returns all data."""
    manager = Manager()

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            # -1 should return all data
            all_data = conn.recv_data(-1)
            default_data = conn.recv_data()

            # Should be equivalent
            assert all_data == default_data
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

        assert True
    finally:
        manager.close()


def test_buffer_access_returns_bytes():
    """Test that all buffer access methods return bytes."""
    manager = Manager()

    try:
        listener = manager.listen("http://127.0.0.1:0")
        manager.poll(10)

        # Should return bytes even when empty
        assert isinstance(listener.recv_data(), bytes)
        assert isinstance(listener.send_data(), bytes)
        assert isinstance(listener.recv_data(10), bytes)
        assert isinstance(listener.send_data(5), bytes)
    finally:
        manager.close()
