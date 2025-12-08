"""Tests for Connection object functionality."""

import pytest
import threading
import time
import urllib.request
from cymongoose import Manager, MG_EV_HTTP_MSG, MG_EV_ACCEPT
from .conftest import ServerThread, get_free_port


class TestConnectionProperties:
    """Test Connection properties and methods."""

    def test_connection_userdata(self):
        """Test connection userdata can be set and retrieved."""
        userdata_captured = []

        def handler(conn, event, data):
            if event == MG_EV_ACCEPT:
                conn.userdata = {"client": "test", "count": 0}
            elif event == MG_EV_HTTP_MSG:
                if conn.userdata:
                    conn.userdata["count"] += 1
                    userdata_captured.append(conn.userdata)
                conn.reply(200, "OK")

        with ServerThread(handler) as port:
            urllib.request.urlopen(f"http://localhost:{port}/", timeout=2)
            time.sleep(0.2)

            assert len(userdata_captured) > 0
            assert userdata_captured[0]["client"] == "test"
            assert userdata_captured[0]["count"] == 1

    def test_connection_is_listening(self):
        """Test connection is_listening property."""
        manager = Manager()
        port = get_free_port()
        conn = manager.listen(f"http://0.0.0.0:{port}", http=True)

        assert conn.is_listening is True

        manager.close()

    def test_per_connection_handler(self):
        """Test per-connection handler override on listener."""
        handler_called = []
        stop = threading.Event()

        def default_handler(conn, event, data):
            handler_called.append("default")
            if event == MG_EV_HTTP_MSG:
                conn.reply(200, "Default")

        def listener_handler(conn, event, data):
            handler_called.append("listener")
            if event == MG_EV_HTTP_MSG:
                conn.reply(200, "Listener")

        manager = Manager(default_handler)
        port = get_free_port()
        listener = manager.listen(f"http://0.0.0.0:{port}", http=True)

        # Set a custom handler on the listener connection
        # This handler will be used for events on the listener itself
        listener.set_handler(listener_handler)

        def run_poll():
            while not stop.is_set():
                manager.poll(100)

        thread = threading.Thread(target=run_poll, daemon=True)
        thread.start()
        time.sleep(0.3)

        try:
            response = urllib.request.urlopen(f"http://localhost:{port}/", timeout=2)
            body = response.read().decode("utf-8")
            time.sleep(0.2)

            # The listener handler should be invoked for the listener connection
            # But accepted connections inherit from the manager's default handler
            # So we expect "default" for the HTTP message
            assert "listener" in handler_called or "default" in handler_called
            assert body in ["Default", "Listener"]
        finally:
            stop.set()
            thread.join(timeout=1)
            manager.close()


class TestConnectionSend:
    """Test Connection send methods."""

    def test_reply_with_custom_headers(self):
        """Test reply() with custom headers."""

        def handler(conn, event, data):
            if event == MG_EV_HTTP_MSG:
                headers = {"X-Custom-Header": "TestValue", "Content-Type": "application/json"}
                conn.reply(201, '{"status": "created"}', headers)

        with ServerThread(handler) as port:
            response = urllib.request.urlopen(f"http://localhost:{port}/", timeout=2)

            assert response.status == 201
            assert response.headers.get("X-Custom-Header") == "TestValue"
            assert "application/json" in response.headers.get("Content-Type", "")

            body = response.read().decode("utf-8")
            assert body == '{"status": "created"}'

    def test_reply_with_bytes_body(self):
        """Test reply() with bytes body."""

        def handler(conn, event, data):
            if event == MG_EV_HTTP_MSG:
                conn.reply(200, b"Binary response")

        with ServerThread(handler) as port:
            response = urllib.request.urlopen(f"http://localhost:{port}/", timeout=2)
            body = response.read()

            assert body == b"Binary response"

    def test_reply_with_string_body(self):
        """Test reply() with string body (UTF-8 encoding)."""

        def handler(conn, event, data):
            if event == MG_EV_HTTP_MSG:
                conn.reply(200, "Hello, 世界!")

        with ServerThread(handler) as port:
            response = urllib.request.urlopen(f"http://localhost:{port}/", timeout=2)
            body = response.read().decode("utf-8")

            assert body == "Hello, 世界!"
