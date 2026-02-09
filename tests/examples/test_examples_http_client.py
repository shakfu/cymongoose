#!/usr/bin/env python3
"""
Comprehensive tests for HTTP client example.

Tests the http_client.py example's structure and importability.
Full integration testing with separate client/server managers is avoided
due to Mongoose limitations with multiple simultaneous managers.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def test_http_client_example_importable():
    """Test that the http_client.py example can be imported."""
    # Add example directory to path
    sys.path.insert(0, str(Path(__file__).parent / "http"))

    try:
        import http_client

        assert hasattr(http_client, "HttpClient")
        assert hasattr(http_client, "main")

        # Test class can be instantiated
        client = http_client.HttpClient("http://example.com", timeout=1)
        assert client.url == "http://example.com"
        assert client.method == "GET"
        assert client.timeout == 1
        assert not client.done
        assert client.response_code is None

    finally:
        # Remove from path
        sys.path.pop(0)


def test_http_client_structure():
    """Test HttpClient class structure."""
    sys.path.insert(0, str(Path(__file__).parent / "http"))

    try:
        import http_client

        # Test POST client
        client = http_client.HttpClient(
            "http://example.com/api",
            method="POST",
            data="test payload",
            headers={"Custom": "header"},
            timeout=5,
        )

        assert client.method == "POST"
        assert client.data == "test payload"
        assert "Custom" in client.headers
        assert client.headers["Custom"] == "header"
        assert client.timeout == 5

    finally:
        sys.path.pop(0)


def test_http_client_handler_methods():
    """Test that HttpClient has handler and execute methods."""
    sys.path.insert(0, str(Path(__file__).parent / "http"))

    try:
        import http_client

        client = http_client.HttpClient("http://example.com")

        # Should have handler and execute methods
        assert callable(client.handler)
        assert callable(client.execute)

        # Handler should be a function that takes (conn, event, data)
        import inspect

        sig = inspect.signature(client.handler)
        assert len(sig.parameters) == 3

    finally:
        sys.path.pop(0)
