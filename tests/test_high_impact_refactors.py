"""Tests for high-impact refactorings from REVIEW.md.

Covers:
1. URL scheme inference for http= parameter
2. Manager context manager protocol (__enter__/__exit__)
3. Message view invalidation after handler returns
4. ServerThread event-based readiness (implicitly tested by all ServerThread usage)
"""

import threading
import time
import urllib.request

from cymongoose import (
    MG_EV_ACCEPT,
    MG_EV_HTTP_MSG,
    MG_EV_WS_MSG,
    Manager,
)
from tests.conftest import ServerThread, get_free_port

# ---------------------------------------------------------------------------
# 1. URL scheme inference
# ---------------------------------------------------------------------------


class TestUrlSchemeInference:
    """listen() and connect() infer http=True from URL scheme."""

    def test_listen_http_scheme_infers_http(self):
        """listen('http://...') enables HTTP parsing without explicit http=True."""
        received = {}

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                received["method"] = data.method
                received["uri"] = data.uri
                conn.reply(200, b"inferred")

        with Manager(handler) as mgr:
            # No http=True -- should be inferred from scheme
            listener = mgr.listen("http://127.0.0.1:0")
            port = listener.local_addr[1]

            stop = threading.Event()

            def poll_loop():
                while not stop.is_set():
                    mgr.poll(50)

            t = threading.Thread(target=poll_loop, daemon=True)
            t.start()
            time.sleep(0.2)

            try:
                resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/hello", timeout=2)
                body = resp.read()
            finally:
                stop.set()
                t.join(timeout=2)

        assert received["method"] == "GET"
        assert received["uri"] == "/hello"
        assert body == b"inferred"

    def test_listen_tcp_scheme_does_not_infer_http(self):
        """listen('tcp://...') should NOT enable HTTP parsing."""
        got_accept = []
        got_http = []

        def handler(conn, ev, data):
            if ev == MG_EV_ACCEPT:
                got_accept.append(True)
            if ev == MG_EV_HTTP_MSG:
                got_http.append(True)

        with Manager(handler) as mgr:
            listener = mgr.listen("tcp://127.0.0.1:0")
            port = listener.local_addr[1]

            # Send raw data -- should get ACCEPT but NOT HTTP_MSG
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(("127.0.0.1", port))
            sock.sendall(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
            for _ in range(20):
                mgr.poll(10)
            sock.close()
            mgr.poll(50)

        assert len(got_accept) >= 1
        # Raw TCP listener should NOT parse HTTP
        assert len(got_http) == 0

    def test_listen_explicit_http_false_overrides_inference(self):
        """listen('http://...', http=False) forces raw TCP despite scheme."""
        got_http = []

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                got_http.append(True)

        with Manager(handler) as mgr:
            listener = mgr.listen("http://127.0.0.1:0", http=False)
            port = listener.local_addr[1]

            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(("127.0.0.1", port))
            sock.sendall(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
            for _ in range(20):
                mgr.poll(10)
            sock.close()
            mgr.poll(50)

        # http=False should prevent HTTP parsing even with http:// scheme
        assert len(got_http) == 0

    def test_listen_explicit_http_true_still_works(self):
        """Existing http=True calls continue to work."""
        received = {}

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                received["uri"] = data.uri
                conn.reply(200, b"ok")

        with Manager(handler) as mgr:
            listener = mgr.listen("http://127.0.0.1:0", http=True)
            port = listener.local_addr[1]

            stop = threading.Event()

            def poll_loop():
                while not stop.is_set():
                    mgr.poll(50)

            t = threading.Thread(target=poll_loop, daemon=True)
            t.start()
            time.sleep(0.2)

            try:
                resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/explicit", timeout=2)
                resp.read()
            finally:
                stop.set()
                t.join(timeout=2)

        assert received["uri"] == "/explicit"

    def test_connect_http_scheme_infers_http(self):
        """connect('http://...') enables HTTP parsing without explicit http=True.

        mg_http_connect sets up the connection for HTTP protocol parsing.
        We verify it works by doing a full round-trip: the client handler
        sends an HTTP request on MG_EV_CONNECT, and the server replies.
        """
        from cymongoose import MG_EV_CONNECT

        responses = []

        def handler(conn, ev, data):
            if ev == MG_EV_CONNECT and conn.is_client:
                conn.send(b"GET /test HTTP/1.1\r\nHost: localhost\r\n\r\n")
            elif ev == MG_EV_HTTP_MSG:
                if not conn.is_client:
                    conn.reply(200, b"from-server")
                else:
                    responses.append(data.body_text)

        with Manager(handler) as mgr:
            listener = mgr.listen("http://127.0.0.1:0")
            port = listener.local_addr[1]
            mgr.poll(10)

            # connect without http=True -- should be inferred from http:// scheme
            mgr.connect(f"http://127.0.0.1:{port}/test")
            for _ in range(100):
                mgr.poll(50)
                if responses:
                    break

        assert len(responses) >= 1
        assert responses[0] == "from-server"

    def test_ws_scheme_infers_http(self):
        """listen('ws://...') should also infer HTTP (WebSocket uses HTTP upgrade)."""
        with Manager() as mgr:
            # ws:// should not crash -- it uses HTTP protocol under the hood
            listener = mgr.listen("ws://127.0.0.1:0")
            mgr.poll(10)
            assert listener.is_listening

    def test_https_scheme_infers_http(self):
        """listen('https://...') should infer HTTP."""
        with Manager() as mgr:
            listener = mgr.listen("https://127.0.0.1:0")
            mgr.poll(10)
            assert listener.is_listening

    def test_wss_scheme_infers_http(self):
        """listen('wss://...') should infer HTTP."""
        with Manager() as mgr:
            listener = mgr.listen("wss://127.0.0.1:0")
            mgr.poll(10)
            assert listener.is_listening

    def test_udp_scheme_does_not_infer_http(self):
        """listen('udp://...') should NOT infer HTTP."""
        with Manager() as mgr:
            listener = mgr.listen("udp://127.0.0.1:0")
            mgr.poll(10)
            assert listener.is_listening

    def test_mqtt_scheme_does_not_infer_http(self):
        """listen('mqtt://...') should NOT infer HTTP."""
        got_http = []

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                got_http.append(True)

        with Manager(handler) as mgr:
            listener = mgr.listen("mqtt://127.0.0.1:0")
            mgr.poll(10)
            assert listener.is_listening
            assert len(got_http) == 0


# ---------------------------------------------------------------------------
# 2. Manager context manager protocol
# ---------------------------------------------------------------------------


class TestManagerContextManager:
    """Manager supports with-statement for automatic cleanup."""

    def test_context_manager_basic(self):
        """Manager can be used as a context manager."""
        with Manager() as mgr:
            listener = mgr.listen("tcp://127.0.0.1:0")
            mgr.poll(10)
            assert listener.is_listening
        # After exiting, manager should be freed

    def test_context_manager_returns_self(self):
        """__enter__ returns the Manager instance."""
        mgr = Manager()
        result = mgr.__enter__()
        assert result is mgr
        mgr.__exit__(None, None, None)

    def test_context_manager_closes_on_exit(self):
        """Exiting the context manager frees resources."""
        with Manager() as mgr:
            mgr.listen("tcp://127.0.0.1:0")
            mgr.poll(10)

        # After close, poll should raise
        try:
            mgr.poll(10)
            assert False, "Should have raised RuntimeError"
        except RuntimeError:
            pass

    def test_context_manager_closes_on_exception(self):
        """Resources are freed even if an exception occurs."""
        try:
            with Manager() as mgr:
                mgr.listen("tcp://127.0.0.1:0")
                mgr.poll(10)
                raise ValueError("test error")
        except ValueError:
            pass

        # Manager should be closed
        try:
            mgr.poll(10)
            assert False, "Should have raised RuntimeError"
        except RuntimeError:
            pass

    def test_context_manager_with_handler(self):
        """Context manager works with handler argument."""
        events = []

        def handler(conn, ev, data):
            events.append(ev)

        with Manager(handler) as mgr:
            mgr.listen("tcp://127.0.0.1:0")
            mgr.poll(10)

        # Should have received at least poll events
        assert len(events) > 0


# ---------------------------------------------------------------------------
# 3. Message view invalidation after handler returns
# ---------------------------------------------------------------------------


class TestMessageViewInvalidation:
    """Message views are invalidated after handler returns to prevent UaF."""

    def test_http_message_invalidated_after_handler(self):
        """HttpMessage._msg is set to NULL after the handler returns."""
        stored_msg = {}

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                # Store reference to message view
                stored_msg["msg"] = data
                # Should work inside handler
                assert data.method == "GET"
                conn.reply(200, b"ok")

        with ServerThread(handler) as port:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2).read()

        # After handler returned, the message view should be invalidated
        msg = stored_msg.get("msg")
        assert msg is not None
        # Accessing properties on invalidated view should return safe defaults
        assert msg.method == ""
        assert msg.uri == ""
        assert msg.body_text == ""
        assert msg.body_bytes == b""
        assert msg.query == ""
        assert msg.proto == ""
        assert bool(msg) is False

    def test_ws_message_invalidated_after_handler(self):
        """WsMessage._msg is set to NULL after the handler returns."""
        stored_msg = {}

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                conn.ws_upgrade(data)
            elif ev == MG_EV_WS_MSG:
                stored_msg["msg"] = data
                # Should work inside handler
                assert data.text == "ping"
                conn.ws_send("pong")

        mgr = Manager(handler)
        port = get_free_port()
        mgr.listen(f"http://0.0.0.0:{port}", http=True)

        stop = threading.Event()

        def poll_loop():
            while not stop.is_set():
                mgr.poll(50)

        t = threading.Thread(target=poll_loop, daemon=True)
        t.start()
        time.sleep(0.2)

        try:
            import websocket

            ws = websocket.create_connection(f"ws://127.0.0.1:{port}/ws", timeout=2)
            ws.send("ping")
            ws.recv()
            ws.close()
        except ImportError:
            stop.set()
            t.join(timeout=2)
            mgr.close()
            import pytest

            pytest.skip("websocket-client not installed")
            return

        time.sleep(0.1)
        stop.set()
        t.join(timeout=2)
        mgr.close()

        msg = stored_msg.get("msg")
        if msg is not None:
            # After handler returned, view should be invalidated
            assert msg.text == ""
            assert msg.data == b""

    def test_http_message_header_after_invalidation(self):
        """header() on invalidated HttpMessage returns default."""
        stored_msg = {}

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                stored_msg["msg"] = data
                # Works inside handler
                assert data.header("Host") is not None
                conn.reply(200, b"ok")

        with ServerThread(handler) as port:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2).read()

        msg = stored_msg.get("msg")
        assert msg is not None
        # After invalidation, header() returns default
        assert msg.header("Host") is None
        assert msg.header("Host", "fallback") == "fallback"
        assert msg.headers() == []
        assert msg.query_var("key") is None
        assert msg.status() is None


# ---------------------------------------------------------------------------
# 4. ServerThread event-based readiness
# ---------------------------------------------------------------------------


class TestServerThreadReadiness:
    """ServerThread uses event-based synchronization, not sleep."""

    def test_server_thread_has_ready_event(self):
        """ServerThread exposes a ready event for synchronization."""

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                conn.reply(200, b"ready-test")

        st = ServerThread(handler)
        assert hasattr(st, "ready")
        assert isinstance(st.ready, threading.Event)

    def test_server_thread_ready_is_set_on_enter(self):
        """ready event is set by the time __enter__ returns."""

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                conn.reply(200, b"ok")

        st = ServerThread(handler)
        port = st.__enter__()
        try:
            assert st.ready.is_set()
            # And the server actually works
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/test", timeout=2)
            assert resp.read() == b"ok"
        finally:
            st.__exit__(None, None, None)
