"""Tests for Connection object functionality."""

import threading
import time
import urllib.request

from cymongoose import MG_EV_ACCEPT, MG_EV_HTTP_MSG, Manager

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
        """Test per-listener handler is inherited by accepted child connections."""
        default_events = []
        listener_events = []
        stop = threading.Event()

        def default_handler(conn, event, data):
            if event == MG_EV_HTTP_MSG:
                default_events.append("http_msg")
                conn.reply(200, "Default")

        def listener_handler(conn, event, data):
            if event == MG_EV_HTTP_MSG:
                listener_events.append("http_msg")
                conn.reply(200, "Listener")

        manager = Manager(default_handler)
        port = get_free_port()
        manager.listen(
            f"http://0.0.0.0:{port}", handler=listener_handler, http=True
        )

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

            # Child connection must use the per-listener handler, not the default
            assert body == "Listener"
            assert len(listener_events) > 0
            assert len(default_events) == 0
        finally:
            stop.set()
            thread.join(timeout=1)
            manager.close()

    def test_set_handler_on_listener_inherits(self):
        """Test set_handler() on a listener propagates to accepted children."""
        stop = threading.Event()

        def default_handler(conn, event, data):
            if event == MG_EV_HTTP_MSG:
                conn.reply(200, "Default")

        def custom_handler(conn, event, data):
            if event == MG_EV_HTTP_MSG:
                conn.reply(200, "Custom")

        manager = Manager(default_handler)
        port = get_free_port()
        listener = manager.listen(f"http://0.0.0.0:{port}", http=True)
        listener.set_handler(custom_handler)

        def run_poll():
            while not stop.is_set():
                manager.poll(100)

        thread = threading.Thread(target=run_poll, daemon=True)
        thread.start()
        time.sleep(0.3)

        try:
            response = urllib.request.urlopen(f"http://localhost:{port}/", timeout=2)
            body = response.read().decode("utf-8")

            assert body == "Custom"
        finally:
            stop.set()
            thread.join(timeout=1)
            manager.close()

    def test_multiple_listeners_different_handlers(self):
        """Test two listeners on different ports use their own handlers."""
        stop = threading.Event()

        def default_handler(conn, event, data):
            if event == MG_EV_HTTP_MSG:
                conn.reply(200, "Default")

        def handler_a(conn, event, data):
            if event == MG_EV_HTTP_MSG:
                conn.reply(200, "HandlerA")

        def handler_b(conn, event, data):
            if event == MG_EV_HTTP_MSG:
                conn.reply(200, "HandlerB")

        manager = Manager(default_handler)
        port_a = get_free_port()
        port_b = get_free_port()
        manager.listen(f"http://0.0.0.0:{port_a}", handler=handler_a, http=True)
        manager.listen(f"http://0.0.0.0:{port_b}", handler=handler_b, http=True)

        def run_poll():
            while not stop.is_set():
                manager.poll(100)

        thread = threading.Thread(target=run_poll, daemon=True)
        thread.start()
        time.sleep(0.3)

        try:
            resp_a = urllib.request.urlopen(
                f"http://localhost:{port_a}/", timeout=2
            )
            body_a = resp_a.read().decode("utf-8")

            resp_b = urllib.request.urlopen(
                f"http://localhost:{port_b}/", timeout=2
            )
            body_b = resp_b.read().decode("utf-8")

            assert body_a == "HandlerA"
            assert body_b == "HandlerB"
        finally:
            stop.set()
            thread.join(timeout=1)
            manager.close()

    def test_listen_without_handler_uses_default(self):
        """Test listen() without handler falls back to Manager default."""
        stop = threading.Event()

        def default_handler(conn, event, data):
            if event == MG_EV_HTTP_MSG:
                conn.reply(200, "Default")

        manager = Manager(default_handler)
        port = get_free_port()
        manager.listen(f"http://0.0.0.0:{port}", http=True)

        def run_poll():
            while not stop.is_set():
                manager.poll(100)

        thread = threading.Thread(target=run_poll, daemon=True)
        thread.start()
        time.sleep(0.3)

        try:
            response = urllib.request.urlopen(f"http://localhost:{port}/", timeout=2)
            body = response.read().decode("utf-8")

            assert body == "Default"
        finally:
            stop.set()
            thread.join(timeout=1)
            manager.close()


    def test_set_handler_none_clears_inheritance(self):
        """Test set_handler(None) on listener reverts children to default."""
        stop = threading.Event()

        def default_handler(conn, event, data):
            if event == MG_EV_HTTP_MSG:
                conn.reply(200, "Default")

        def custom_handler(conn, event, data):
            if event == MG_EV_HTTP_MSG:
                conn.reply(200, "Custom")

        manager = Manager(default_handler)
        port = get_free_port()
        listener = manager.listen(f"http://0.0.0.0:{port}", http=True)
        listener.set_handler(custom_handler)
        # Clear -- future children should fall back to default
        listener.set_handler(None)

        def run_poll():
            while not stop.is_set():
                manager.poll(100)

        thread = threading.Thread(target=run_poll, daemon=True)
        thread.start()
        time.sleep(0.3)

        try:
            response = urllib.request.urlopen(f"http://localhost:{port}/", timeout=2)
            body = response.read().decode("utf-8")

            assert body == "Default"
        finally:
            stop.set()
            thread.join(timeout=1)
            manager.close()

    def test_no_default_handler_no_listener_handler(self):
        """Test Manager with no default handler and listen with no handler does not crash."""
        stop = threading.Event()

        manager = Manager()  # no default handler
        port = get_free_port()
        manager.listen(f"http://0.0.0.0:{port}", http=True)

        def run_poll():
            while not stop.is_set():
                manager.poll(100)

        thread = threading.Thread(target=run_poll, daemon=True)
        thread.start()
        time.sleep(0.3)

        try:
            # Server has no handler, so it won't reply. The request should
            # time out, but the server must not crash.
            try:
                urllib.request.urlopen(f"http://localhost:{port}/", timeout=1)
            except Exception:
                pass  # timeout or incomplete response expected

            # Verify the manager is still alive by polling without error
            time.sleep(0.2)
            manager.poll(0)
        finally:
            stop.set()
            thread.join(timeout=1)
            manager.close()

    def test_listener_handler_persists_across_multiple_requests(self):
        """Test per-listener handler is used for multiple sequential requests."""
        request_count = []
        stop = threading.Event()

        def default_handler(conn, event, data):
            if event == MG_EV_HTTP_MSG:
                conn.reply(200, "Default")

        def listener_handler(conn, event, data):
            if event == MG_EV_HTTP_MSG:
                request_count.append(1)
                conn.reply(200, f"Request-{len(request_count)}")

        manager = Manager(default_handler)
        port = get_free_port()
        manager.listen(
            f"http://0.0.0.0:{port}", handler=listener_handler, http=True
        )

        def run_poll():
            while not stop.is_set():
                manager.poll(100)

        thread = threading.Thread(target=run_poll, daemon=True)
        thread.start()
        time.sleep(0.3)

        try:
            bodies = []
            for _ in range(3):
                resp = urllib.request.urlopen(f"http://localhost:{port}/", timeout=2)
                bodies.append(resp.read().decode("utf-8"))

            assert bodies == ["Request-1", "Request-2", "Request-3"]
            assert len(request_count) == 3
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
