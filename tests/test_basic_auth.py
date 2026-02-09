"""Tests for HTTP Basic Authentication."""

import base64

from cymongoose import Manager


def test_http_basic_auth_method_exists():
    """Test that http_basic_auth method exists."""
    manager = Manager()

    try:
        # Create a listening server to accept the connection
        listener = manager.listen("tcp://127.0.0.1:0")
        port = listener.local_addr[1]

        # Connect to our own server
        conn = manager.connect(f"tcp://127.0.0.1:{port}")
        manager.poll(50)

        # Method should exist and write to send buffer
        conn.http_basic_auth("testuser", "testpass")

        assert conn.send_len > 0
    finally:
        manager.close()


def test_http_basic_auth_sends_header():
    """Test that basic auth writes Authorization header to send buffer."""
    manager = Manager()

    try:
        # Create a listening server to accept the connection
        listener = manager.listen("tcp://127.0.0.1:0")
        port = listener.local_addr[1]

        # Connect to our own server
        conn = manager.connect(f"tcp://127.0.0.1:{port}")
        manager.poll(50)

        conn.http_basic_auth("user", "pass")

        # http_basic_auth writes "Authorization: Basic <b64>\r\n" to send buffer
        assert b"Authorization: Basic" in conn.send_data()
    finally:
        manager.close()


def test_http_basic_auth_format():
    """Test basic auth credentials encoding."""
    # Basic auth should encode as "Basic base64(username:password)"
    username = "testuser"
    password = "testpass"

    # Expected format
    credentials = f"{username}:{password}"
    encoded = base64.b64encode(credentials.encode()).decode()
    expected_header = f"Basic {encoded}"

    manager = Manager()
    try:
        # Create a listening server to accept the connection
        listener = manager.listen("tcp://127.0.0.1:0")
        port = listener.local_addr[1]

        # Connect to our own server
        conn = manager.connect(f"tcp://127.0.0.1:{port}")
        manager.poll(50)

        conn.http_basic_auth(username, password)

        # Verify the expected base64-encoded credentials appear in the send buffer
        assert expected_header.encode() in conn.send_data()
    finally:
        manager.close()


def test_http_basic_auth_unicode():
    """Test basic auth with unicode characters."""
    manager = Manager()

    try:
        # Create a listening server to accept the connection
        listener = manager.listen("tcp://127.0.0.1:0")
        port = listener.local_addr[1]

        # Connect to our own server
        conn = manager.connect(f"tcp://127.0.0.1:{port}")
        manager.poll(50)

        # Should handle unicode properly
        conn.http_basic_auth("用户", "密码")

        assert b"Authorization: Basic" in conn.send_data()
    finally:
        manager.close()


def test_http_basic_auth_special_chars():
    """Test basic auth with special characters."""
    manager = Manager()

    try:
        # Create a listening server to accept the connection
        listener = manager.listen("tcp://127.0.0.1:0")
        port = listener.local_addr[1]

        # Connect to our own server
        conn = manager.connect(f"tcp://127.0.0.1:{port}")
        manager.poll(50)

        # Should handle special characters
        conn.http_basic_auth("user@example.com", "p@ss:word!")

        assert b"Authorization: Basic" in conn.send_data()
    finally:
        manager.close()


def test_http_basic_auth_empty_credentials():
    """Test basic auth with empty credentials."""
    manager = Manager()

    try:
        # Create a listening server to accept the connection
        listener = manager.listen("tcp://127.0.0.1:0")
        port = listener.local_addr[1]

        # Connect to our own server
        conn = manager.connect(f"tcp://127.0.0.1:{port}")
        manager.poll(50)

        # Should handle empty strings
        conn.http_basic_auth("", "")

        assert b"Authorization: Basic" in conn.send_data()
    finally:
        manager.close()
