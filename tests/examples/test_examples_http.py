#!/usr/bin/env python3
"""
Tests all specialized HTTP features:
- HTTP Streaming Client
- HTTP File Upload
- HTTP RESTful Server
- Server-Sent Events
"""

import json
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cymongoose import (
    MG_EV_HTTP_MSG,
    Manager,
)

# ===== HTTP Streaming Client Tests =====


def test_streaming_client_can_import():
    """Test that streaming client module can be imported."""
    try:
        # Just verify the module exists and is valid Python
        with open("tests/examples/http/http_streaming_client.py") as f:
            code = f.read()
            compile(code, "http_streaming_client.py", "exec")
    except SyntaxError as e:
        assert False, f"Syntax error in http_streaming_client.py: {e}"


def test_streaming_client_url_parsing():
    """Test URL parsing functionality."""
    sys.path.insert(0, "tests/examples/http")
    try:
        import http_streaming_client

        # Test HTTP URL
        scheme, host, port, uri = http_streaming_client.parse_url("http://example.com/path")
        assert scheme == "http"
        assert host == "example.com"
        assert port == 80
        assert uri == "/path"

        # Test HTTPS URL
        scheme, host, port, uri = http_streaming_client.parse_url("https://example.com:8443/test")
        assert scheme == "https"
        assert host == "example.com"
        assert port == 8443
        assert uri == "/test"

        # Test root path
        scheme, host, port, uri = http_streaming_client.parse_url("http://example.com")
        assert uri == "/"

    finally:
        sys.path.pop(0)


# ===== HTTP File Upload Tests =====


def test_file_upload_basic_server():
    """Test file upload server can start and respond."""
    upload_received = threading.Event()

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            hm = data
            if hm.uri == "/":
                conn.reply(200, "Upload server ready")
            elif hm.uri.startswith("/upload/"):
                # Simple upload response
                conn.reply(200, "100 bytes uploaded")
                upload_received.set()

    manager = Manager(handler)
    listener = manager.listen("http://127.0.0.1:0", http=True)
    port = listener.local_addr[1]

    stop = threading.Event()

    def poll_loop():
        while not stop.is_set():
            manager.poll(50)

    poll_thread = threading.Thread(target=poll_loop, daemon=True)
    poll_thread.start()
    time.sleep(0.1)

    try:
        # Test home page
        response = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
        assert response.status == 200

        # Test upload endpoint
        data = b"test data"
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/upload/test.txt", data=data, method="POST"
        )
        response = urllib.request.urlopen(req, timeout=2)
        assert response.status == 200

    finally:
        stop.set()
        poll_thread.join(timeout=1)
        manager.close()


def test_file_upload_to_disk(tmp_path):
    """Test actual file upload to disk."""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()

    upload_complete = threading.Event()
    uploaded_file = None

    def handler(conn, ev, data):
        nonlocal uploaded_file

        if ev == MG_EV_HTTP_MSG:
            hm = data
            if hm.uri.startswith("/upload/"):
                # Extract filename
                filename = hm.uri[8:]
                filepath = upload_dir / filename

                # Write uploaded data
                with open(filepath, "wb") as f:
                    f.write(hm.body_bytes)

                uploaded_file = filepath
                conn.reply(200, f"{len(hm.body_bytes)} bytes uploaded")
                upload_complete.set()

    manager = Manager(handler)
    listener = manager.listen("http://127.0.0.1:0", http=True)
    port = listener.local_addr[1]

    stop = threading.Event()

    def poll_loop():
        while not stop.is_set():
            manager.poll(50)

    poll_thread = threading.Thread(target=poll_loop, daemon=True)
    poll_thread.start()
    time.sleep(0.1)

    try:
        # Upload a file
        test_data = b"This is test file content\n" * 100
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/upload/test.txt", data=test_data, method="POST"
        )
        response = urllib.request.urlopen(req, timeout=2)
        assert response.status == 200

        # Wait for upload to complete
        upload_complete.wait(timeout=2)
        assert upload_complete.is_set()

        # Verify file was written
        assert uploaded_file is not None
        assert uploaded_file.exists()
        assert uploaded_file.read_bytes() == test_data

    finally:
        stop.set()
        poll_thread.join(timeout=1)
        manager.close()


# ===== HTTP RESTful Server Tests =====


def test_restful_server_api_endpoints():
    """Test RESTful server API endpoints."""

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            hm = data

            if hm.uri == "/api/stats":
                # Return chunked response
                conn.send(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n")
                conn.http_chunk("Test stats\n")
                conn.http_chunk("")  # End

            elif hm.uri.startswith("/api/f2/"):
                # Echo URI in JSON
                response = {"result": hm.uri}
                conn.reply(200, json.dumps(response), headers={"Content-Type": "application/json"})

            elif hm.uri == "/api/data":
                # Process JSON POST
                if hm.body_bytes:
                    request_data = json.loads(hm.body_bytes.decode("utf-8"))
                    response = {"status": "success", "received": request_data}
                    conn.reply(
                        200, json.dumps(response), headers={"Content-Type": "application/json"}
                    )

    manager = Manager(handler)
    listener = manager.listen("http://127.0.0.1:0", http=True)
    port = listener.local_addr[1]

    stop = threading.Event()

    def poll_loop():
        while not stop.is_set():
            manager.poll(50)

    poll_thread = threading.Thread(target=poll_loop, daemon=True)
    poll_thread.start()
    time.sleep(0.1)

    try:
        # Test /api/stats
        response = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/stats", timeout=2)
        assert response.status == 200
        content = response.read()
        assert b"Test stats" in content

        # Test /api/f2/* wildcard
        response = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/f2/test123", timeout=2)
        assert response.status == 200
        data = json.loads(response.read())
        assert data["result"] == "/api/f2/test123"

        # Test /api/data POST
        post_data = {"key": "value", "number": 42}
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/data",
            data=json.dumps(post_data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        response = urllib.request.urlopen(req, timeout=2)
        assert response.status == 200
        data = json.loads(response.read())
        assert data["status"] == "success"
        assert data["received"] == post_data

    finally:
        stop.set()
        poll_thread.join(timeout=1)
        manager.close()


# ===== Server-Sent Events Tests =====


def test_sse_server_basic():
    """Test SSE server basic functionality."""

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            hm = data

            if hm.uri == "/events":
                # Start SSE stream
                headers = "HTTP/1.1 200 OK\r\n"
                headers += "Content-Type: text/event-stream\r\n"
                headers += "Cache-Control: no-cache\r\n"
                headers += "\r\n"
                conn.send(headers.encode("utf-8"))

                # Send test event
                conn.http_sse("test", "Test event data")

            elif hm.uri == "/":
                conn.reply(200, "<html><body>SSE Server</body></html>")

    manager = Manager(handler)
    listener = manager.listen("http://127.0.0.1:0", http=True)
    port = listener.local_addr[1]

    stop = threading.Event()

    def poll_loop():
        while not stop.is_set():
            manager.poll(50)

    poll_thread = threading.Thread(target=poll_loop, daemon=True)
    poll_thread.start()
    time.sleep(0.1)

    try:
        # Test home page
        response = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
        assert response.status == 200

        # Test SSE endpoint (just verify it connects)
        response = urllib.request.urlopen(f"http://127.0.0.1:{port}/events", timeout=2)
        assert response.status == 200
        assert response.headers.get("Content-Type") == "text/event-stream"

    finally:
        stop.set()
        poll_thread.join(timeout=1)
        manager.close()


def test_sse_event_format():
    """Test SSE event formatting."""

    def handler(conn, ev, data):
        if ev == MG_EV_HTTP_MSG:
            hm = data
            if hm.uri == "/events":
                # Start SSE
                headers = "HTTP/1.1 200 OK\r\n"
                headers += "Content-Type: text/event-stream\r\n\r\n"
                conn.send(headers.encode("utf-8"))

                # Send multiple events
                conn.http_sse("message", "First event")
                conn.http_sse("update", "Second event")

                # Close connection after sending events (for testing)
                conn.drain()

    manager = Manager(handler)
    listener = manager.listen("http://127.0.0.1:0", http=True)
    port = listener.local_addr[1]

    stop = threading.Event()

    def poll_loop():
        while not stop.is_set():
            manager.poll(50)

    poll_thread = threading.Thread(target=poll_loop, daemon=True)
    poll_thread.start()
    time.sleep(0.1)

    try:
        # Connect and read SSE data
        response = urllib.request.urlopen(f"http://127.0.0.1:{port}/events", timeout=2)
        data = response.read()  # Read all data (connection will close)

        # Verify SSE format (event: type\ndata: payload\n\n)
        assert b"event:" in data or b"data:" in data  # At least one event field
        # The exact format depends on http_sse implementation

    finally:
        stop.set()
        poll_thread.join(timeout=1)
        manager.close()


if __name__ == "__main__":
    # Run tests
    test_streaming_client_can_import()
    print("[x] test_streaming_client_can_import")

    test_streaming_client_url_parsing()
    print("[x] test_streaming_client_url_parsing")

    test_file_upload_basic_server()
    print("[x] test_file_upload_basic_server")

    import tempfile

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_file_upload_to_disk(Path(tmp_dir))
    print("[x] test_file_upload_to_disk")

    test_restful_server_api_endpoints()
    print("[x] test_restful_server_api_endpoints")

    test_sse_server_basic()
    print("[x] test_sse_server_basic")

    test_sse_event_format()
    print("[x] test_sse_event_format")

    print("\nAll Priority 3 tests passed!")
