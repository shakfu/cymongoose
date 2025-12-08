"""Tests for HTTP server functionality."""

import pytest
import threading
import time
import urllib.request
import urllib.error
from cymongoose import Manager, MG_EV_HTTP_MSG, MG_EV_ACCEPT, MG_EV_CLOSE
from .conftest import ServerThread


class TestHTTPServer:
    """Test HTTP server basic functionality."""

    @pytest.fixture
    def server_thread(self):
        """Start a test server in a background thread."""

        def handler(conn, event, data):
            if event == MG_EV_HTTP_MSG:
                conn.reply(200, "Test Response")

        with ServerThread(handler) as port:
            yield port

    def test_basic_http_request(self, server_thread):
        """Test basic HTTP request/response."""
        port = server_thread
        url = f"http://localhost:{port}/"

        response = urllib.request.urlopen(url, timeout=5)
        body = response.read().decode("utf-8")

        assert response.status == 200
        assert body == "Test Response"

    def test_multiple_requests(self, server_thread):
        """Test handling multiple sequential requests."""
        port = server_thread
        url = f"http://localhost:{port}/test"

        for i in range(3):
            response = urllib.request.urlopen(url, timeout=5)
            assert response.status == 200
            body = response.read().decode("utf-8")
            assert body == "Test Response"
            time.sleep(0.1)  # Small delay between requests

    def test_different_paths(self, server_thread):
        """Test requests to different paths."""
        port = server_thread
        paths = ["/", "/test", "/api/data"]

        for path in paths:
            url = f"http://localhost:{port}{path}"
            response = urllib.request.urlopen(url, timeout=5)
            assert response.status == 200
            time.sleep(0.1)  # Small delay between requests


class TestHTTPHeaders:
    """Test HTTP header handling."""

    @pytest.fixture
    def header_server(self):
        """Start server that echoes request information."""
        captured_data = {}

        def handler(conn, event, data):
            if event == MG_EV_HTTP_MSG:
                captured_data["method"] = data.method
                captured_data["uri"] = data.uri
                captured_data["query"] = data.query
                captured_data["user_agent"] = data.header("User-Agent")

                headers = {"Content-Type": "application/json"}
                conn.reply(200, '{"status": "ok"}', headers)

        with ServerThread(handler) as port:
            yield port, captured_data

    def test_request_method(self, header_server):
        """Test capturing HTTP request method."""
        port, data = header_server
        url = f"http://localhost:{port}/test"

        urllib.request.urlopen(url, timeout=5)

        assert data["method"] == "GET"
        assert data["uri"] == "/test"

    def test_query_string(self, header_server):
        """Test query string parsing."""
        port, data = header_server
        url = f"http://localhost:{port}/api?foo=bar&baz=qux"

        urllib.request.urlopen(url, timeout=5)
        time.sleep(0.2)  # Give handler time to process

        assert data["query"] == "foo=bar&baz=qux"

    def test_custom_headers(self, header_server):
        """Test reading custom headers."""
        port, data = header_server
        url = f"http://localhost:{port}/"

        req = urllib.request.Request(url)
        req.add_header("User-Agent", "CyMongoose-Test/1.0")

        urllib.request.urlopen(req, timeout=5)
        time.sleep(0.2)  # Give handler time to process

        assert "CyMongoose-Test/1.0" in data["user_agent"]


class TestHTTPMessage:
    """Test HttpMessage data structure."""

    def test_http_message_properties(self):
        """Test HttpMessage exposes request properties correctly."""
        received_data = {}

        def handler(conn, event, data):
            if event == MG_EV_HTTP_MSG:
                received_data["method"] = data.method
                received_data["uri"] = data.uri
                received_data["query"] = data.query
                received_data["body_text"] = data.body_text
                received_data["headers"] = data.headers()
                conn.reply(200, "OK")

        with ServerThread(handler) as port:
            url = f"http://localhost:{port}/test?key=value"
            urllib.request.urlopen(url, timeout=2)
            time.sleep(0.2)

            assert received_data["method"] == "GET"
            assert received_data["uri"] == "/test"
            assert received_data["query"] == "key=value"
            assert isinstance(received_data["headers"], list)


class TestConnectionLifecycle:
    """Test connection lifecycle and event handling."""

    def test_connection_events(self):
        """Test that connection events fire correctly."""
        events = []

        def handler(conn, event, data):
            events.append(event)
            if event == MG_EV_HTTP_MSG:
                conn.reply(200, "OK")

        with ServerThread(handler) as port:
            urllib.request.urlopen(f"http://localhost:{port}/", timeout=2)
            time.sleep(0.3)

            assert MG_EV_ACCEPT in events
            assert MG_EV_HTTP_MSG in events
            assert MG_EV_CLOSE in events


class TestManagerLifecycle:
    """Test Manager initialization and cleanup."""

    def test_manager_creation(self):
        """Test Manager can be created and closed."""
        manager = Manager()
        assert manager is not None
        manager.close()

    def test_manager_with_handler(self):
        """Test Manager accepts a default handler."""

        def handler(conn, event, data):
            pass

        manager = Manager(handler)
        assert manager is not None
        manager.close()

    def test_listen_returns_connection(self):
        """Test listen() returns a Connection object."""
        from .conftest import get_free_port

        manager = Manager()
        port = get_free_port()
        conn = manager.listen(f"http://0.0.0.0:{port}", http=True)

        assert conn is not None
        assert conn.is_listening

        manager.close()

    def test_poll_runs_without_error(self):
        """Test poll() executes without error."""
        from .conftest import get_free_port

        manager = Manager()
        port = get_free_port()
        manager.listen(f"http://0.0.0.0:{port}", http=True)

        for _ in range(5):
            manager.poll(10)

        manager.close()


class TestErrorHandling:
    """Test error handling."""

    def test_listen_on_invalid_address_raises(self):
        """Test listening on invalid address raises RuntimeError."""
        manager = Manager()

        with pytest.raises(RuntimeError, match="Failed to listen"):
            manager.listen("invalid://address", http=True)

        manager.close()

    def test_handler_exceptions_dont_crash(self):
        """Test that exceptions in handler don't crash the server."""
        request_count = [0]

        def bad_handler(conn, event, data):
            if event == MG_EV_HTTP_MSG:
                request_count[0] += 1
                if request_count[0] == 1:
                    raise ValueError("Test exception")
                conn.reply(200, "OK")

        with ServerThread(bad_handler) as port:
            # First request causes exception
            try:
                urllib.request.urlopen(f"http://localhost:{port}/", timeout=2)
            except:
                pass

            time.sleep(0.2)

            # Second request should work
            response = urllib.request.urlopen(f"http://localhost:{port}/", timeout=2)
            assert response.status == 200
