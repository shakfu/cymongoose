"""Tests for HTTP Basic Authentication."""

import pytest
import base64
from cymongoose import Manager, MG_EV_HTTP_MSG
from tests.conftest import ServerThread


def test_http_basic_auth_method_exists():
    """Test that http_basic_auth method exists."""
    manager = Manager()

    try:
        conn = manager.connect("tcp://0.0.0.0:0")
        manager.poll(10)

        # Method should exist and write to send buffer
        conn.http_basic_auth("testuser", "testpass")
        manager.poll(10)

        assert conn.send_len > 0
    finally:
        manager.close()


def test_http_basic_auth_sends_header():
    """Test that basic auth writes Authorization header to send buffer."""
    manager = Manager()

    try:
        conn = manager.connect("tcp://0.0.0.0:0")
        manager.poll(10)

        conn.http_basic_auth("user", "pass")
        manager.poll(10)

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
        conn = manager.connect("tcp://0.0.0.0:0")
        manager.poll(10)

        conn.http_basic_auth(username, password)

        # Verify the expected base64-encoded credentials appear in the send buffer
        assert expected_header.encode() in conn.send_data()
    finally:
        manager.close()


def test_http_basic_auth_unicode():
    """Test basic auth with unicode characters."""
    manager = Manager()

    try:
        conn = manager.connect("tcp://0.0.0.0:0")
        manager.poll(10)

        # Should handle unicode properly
        conn.http_basic_auth("用户", "密码")

        assert b"Authorization: Basic" in conn.send_data()
    finally:
        manager.close()


def test_http_basic_auth_special_chars():
    """Test basic auth with special characters."""
    manager = Manager()

    try:
        conn = manager.connect("tcp://0.0.0.0:0")
        manager.poll(10)

        # Should handle special characters
        conn.http_basic_auth("user@example.com", "p@ss:word!")

        assert b"Authorization: Basic" in conn.send_data()
    finally:
        manager.close()


def test_http_basic_auth_empty_credentials():
    """Test basic auth with empty credentials."""
    manager = Manager()

    try:
        conn = manager.connect("tcp://0.0.0.0:0")
        manager.poll(10)

        # Should handle empty strings
        conn.http_basic_auth("", "")

        assert b"Authorization: Basic" in conn.send_data()
    finally:
        manager.close()
