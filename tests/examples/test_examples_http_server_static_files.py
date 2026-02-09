#!/usr/bin/env python3
"""
Comprehensive tests for HTTP server example.
"""

import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cymongoose import MG_EV_HTTP_MSG, Manager


def test_http_server_static_files(tmp_path):
    """Test static file serving."""
    # Create test web root
    web_root = tmp_path / "web_root"
    web_root.mkdir()
    test_file = web_root / "test.html"
    test_file.write_text("<html><body>Test Page</body></html>")

    received = []

    def handler(conn, event, data):
        if event == MG_EV_HTTP_MSG:
            received.append(data.uri)
            conn.serve_dir(data, root_dir=str(web_root))

    manager = Manager(handler)
    conn = manager.listen("http://127.0.0.1:0", http=True)
    port = conn.local_addr[1]

    # Poll in background
    stop = threading.Event()

    def poll_loop():
        while not stop.is_set():
            manager.poll(100)

    poll_thread = threading.Thread(target=poll_loop)
    poll_thread.start()
    time.sleep(0.2)

    try:
        # Test static file
        response = urllib.request.urlopen(f"http://127.0.0.1:{port}/test.html", timeout=2)
        assert response.status == 200
        content = response.read().decode()
        assert "Test Page" in content
        assert "/test.html" in received
    finally:
        stop.set()
        poll_thread.join(timeout=1.0)
        manager.close()


def test_http_server_api_endpoint(tmp_path):
    """Test JSON API endpoint."""
    import json

    def handler(conn, event, data):
        if event == MG_EV_HTTP_MSG:
            if data.uri == "/api/test":
                response = json.dumps({"status": "ok", "value": 42})
                conn.reply(200, response, headers={"Content-Type": "application/json"})
            else:
                conn.reply(404, "Not Found")

    manager = Manager(handler)
    conn = manager.listen("http://127.0.0.1:0", http=True)
    port = conn.local_addr[1]

    stop = threading.Event()

    def poll_loop():
        while not stop.is_set():
            manager.poll(100)

    poll_thread = threading.Thread(target=poll_loop)
    poll_thread.start()
    time.sleep(0.2)

    try:
        # Test API endpoint
        response = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/test", timeout=2)
        assert response.status == 200
        data = json.loads(response.read().decode())
        assert data["status"] == "ok"
        assert data["value"] == 42
    finally:
        stop.set()
        poll_thread.join(timeout=1.0)
        manager.close()


def test_http_server_multipart_upload(tmp_path):
    """Test multipart file upload handling."""
    from cymongoose import http_parse_multipart

    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    uploaded_files = []

    def handler(conn, event, data):
        if event == MG_EV_HTTP_MSG and data.uri == "/upload":
            body = data.body_bytes
            offset = 0

            while True:
                offset, part = http_parse_multipart(body, offset)
                if part is None:
                    break

                if part["filename"]:
                    filepath = upload_dir / part["filename"]
                    with open(filepath, "wb") as f:
                        f.write(part["body"])
                    uploaded_files.append(part["filename"])

            if uploaded_files:
                conn.reply(200, f"Uploaded: {', '.join(uploaded_files)}")
            else:
                conn.reply(400, "No files")

    manager = Manager(handler)
    conn = manager.listen("http://127.0.0.1:0", http=True)
    port = conn.local_addr[1]

    stop = threading.Event()

    def poll_loop():
        while not stop.is_set():
            manager.poll(100)

    poll_thread = threading.Thread(target=poll_loop)
    poll_thread.start()
    time.sleep(0.2)

    try:
        # Create multipart form data
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        body = (
            "------WebKitFormBoundary7MA4YWxkTrZu0gW\r\n"
            'Content-Disposition: form-data; name="file"; filename="test.txt"\r\n'
            "Content-Type: text/plain\r\n"
            "\r\n"
            "Test file content\r\n"
            "------WebKitFormBoundary7MA4YWxkTrZu0gW--\r\n"
        ).encode("utf-8")

        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/upload",
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(body)),
            },
            method="POST",
        )

        response = urllib.request.urlopen(req, timeout=2)
        assert response.status == 200
        assert "test.txt" in uploaded_files

        # Verify file was saved
        saved_file = upload_dir / "test.txt"
        assert saved_file.exists()
        assert saved_file.read_text() == "Test file content"

    finally:
        stop.set()
        poll_thread.join(timeout=1.0)
        manager.close()


def test_http_server_custom_headers():
    """Test custom response headers."""

    def handler(conn, event, data):
        if event == MG_EV_HTTP_MSG:
            conn.reply(
                200,
                "OK",
                headers={"X-Custom-Header": "test-value", "Access-Control-Allow-Origin": "*"},
            )

    manager = Manager(handler)
    conn = manager.listen("http://127.0.0.1:0", http=True)
    port = conn.local_addr[1]

    stop = threading.Event()

    def poll_loop():
        while not stop.is_set():
            manager.poll(100)

    poll_thread = threading.Thread(target=poll_loop)
    poll_thread.start()
    time.sleep(0.2)

    try:
        response = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
        assert response.status == 200
        assert response.headers.get("X-Custom-Header") == "test-value"
        assert response.headers.get("Access-Control-Allow-Origin") == "*"
    finally:
        stop.set()
        poll_thread.join(timeout=1.0)
        manager.close()


def test_http_server_different_methods():
    """Test handling different HTTP methods."""
    requests_received = []

    def handler(conn, event, data):
        if event == MG_EV_HTTP_MSG:
            requests_received.append({"method": data.method, "uri": data.uri})
            conn.reply(200, f"Method: {data.method}")

    manager = Manager(handler)
    conn = manager.listen("http://127.0.0.1:0", http=True)
    port = conn.local_addr[1]

    stop = threading.Event()

    def poll_loop():
        while not stop.is_set():
            manager.poll(100)

    poll_thread = threading.Thread(target=poll_loop)
    poll_thread.start()
    time.sleep(0.2)

    try:
        # Test GET
        response = urllib.request.urlopen(f"http://127.0.0.1:{port}/test", timeout=2)
        assert response.status == 200
        assert b"Method: GET" in response.read()

        # Test POST
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/test", data=b"test data", method="POST"
        )
        response = urllib.request.urlopen(req, timeout=2)
        assert response.status == 200
        assert b"Method: POST" in response.read()

        # Verify both requests were received
        assert len(requests_received) == 2
        assert requests_received[0]["method"] == "GET"
        assert requests_received[1]["method"] == "POST"

    finally:
        stop.set()
        poll_thread.join(timeout=1.0)
        manager.close()
