"""Tests for medium-impact refactorings from REVIEW.md.

Covers:
5. Extract address formatting helper (local_addr/remote_addr dedup)
6. event_name() utility function
7. reply_json() convenience method
8. Dead code removal (Timer._set_timer, comment artifact)
9. Consolidate close()/dealloc cleanup
10. Manager.connections property
"""

import json
import socket
import urllib.request

from cymongoose import (
    MG_EV_ACCEPT,
    MG_EV_CLOSE,
    MG_EV_CONNECT,
    MG_EV_ERROR,
    MG_EV_HTTP_HDRS,
    MG_EV_HTTP_MSG,
    MG_EV_MQTT_CMD,
    MG_EV_MQTT_MSG,
    MG_EV_MQTT_OPEN,
    MG_EV_OPEN,
    MG_EV_POLL,
    MG_EV_READ,
    MG_EV_RESOLVE,
    MG_EV_SNTP_TIME,
    MG_EV_TLS_HS,
    MG_EV_USER,
    MG_EV_WAKEUP,
    MG_EV_WRITE,
    MG_EV_WS_CTL,
    MG_EV_WS_MSG,
    MG_EV_WS_OPEN,
    Connection,
    Manager,
    event_name,
)
from tests.conftest import ServerThread

# ---------------------------------------------------------------------------
# 5. Address formatting helper (indirect -- verify local_addr/remote_addr still work)
# ---------------------------------------------------------------------------


class TestAddressFormatting:
    """local_addr and remote_addr return consistent (ip, port, is_ipv6) tuples."""

    def test_listener_local_addr(self):
        """Listener returns valid local address tuple."""
        with Manager() as mgr:
            listener = mgr.listen("tcp://127.0.0.1:0")
            mgr.poll(10)
            addr = listener.local_addr
            assert addr is not None
            ip, port, is_ipv6 = addr
            assert isinstance(ip, str)
            assert isinstance(port, int)
            assert isinstance(is_ipv6, bool)
            assert port > 0
            assert not is_ipv6

    def test_accepted_connection_has_remote_addr(self):
        """Accepted connections report the client's remote address."""
        remote = {}

        def handler(conn, ev, data):
            if ev == MG_EV_ACCEPT:
                addr = conn.remote_addr
                if addr:
                    remote["ip"], remote["port"], remote["v6"] = addr

        with Manager(handler) as mgr:
            listener = mgr.listen("tcp://127.0.0.1:0")
            mgr.poll(10)
            port = listener.local_addr[1]

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(("127.0.0.1", port))
            for _ in range(20):
                mgr.poll(10)
            sock.close()
            mgr.poll(50)

        assert "ip" in remote
        assert remote["port"] > 0
        assert remote["v6"] is False


# ---------------------------------------------------------------------------
# 6. event_name() utility
# ---------------------------------------------------------------------------


class TestEventName:
    """event_name() maps event constants to human-readable strings."""

    def test_known_events(self):
        assert event_name(MG_EV_POLL) == "MG_EV_POLL"
        assert event_name(MG_EV_ACCEPT) == "MG_EV_ACCEPT"
        assert event_name(MG_EV_CONNECT) == "MG_EV_CONNECT"
        assert event_name(MG_EV_READ) == "MG_EV_READ"
        assert event_name(MG_EV_WRITE) == "MG_EV_WRITE"
        assert event_name(MG_EV_CLOSE) == "MG_EV_CLOSE"
        assert event_name(MG_EV_HTTP_MSG) == "MG_EV_HTTP_MSG"
        assert event_name(MG_EV_HTTP_HDRS) == "MG_EV_HTTP_HDRS"
        assert event_name(MG_EV_WS_OPEN) == "MG_EV_WS_OPEN"
        assert event_name(MG_EV_WS_MSG) == "MG_EV_WS_MSG"
        assert event_name(MG_EV_WS_CTL) == "MG_EV_WS_CTL"
        assert event_name(MG_EV_MQTT_CMD) == "MG_EV_MQTT_CMD"
        assert event_name(MG_EV_MQTT_MSG) == "MG_EV_MQTT_MSG"
        assert event_name(MG_EV_MQTT_OPEN) == "MG_EV_MQTT_OPEN"
        assert event_name(MG_EV_SNTP_TIME) == "MG_EV_SNTP_TIME"
        assert event_name(MG_EV_WAKEUP) == "MG_EV_WAKEUP"

    def test_error_event(self):
        assert event_name(MG_EV_ERROR) == "MG_EV_ERROR"

    def test_open_event(self):
        assert event_name(MG_EV_OPEN) == "MG_EV_OPEN"

    def test_resolve_event(self):
        assert event_name(MG_EV_RESOLVE) == "MG_EV_RESOLVE"

    def test_tls_event(self):
        assert event_name(MG_EV_TLS_HS) == "MG_EV_TLS_HS"

    def test_user_event_base(self):
        assert event_name(MG_EV_USER) == "MG_EV_USER"

    def test_user_event_offset(self):
        result = event_name(MG_EV_USER + 5)
        assert result == "MG_EV_USER+5"

    def test_unknown_event(self):
        # Use -1 or some value not in the known range
        result = event_name(-1)
        assert "UNKNOWN" in result

    def test_event_name_in_handler(self):
        """event_name() is useful inside handlers for debugging."""
        seen_names = []

        def handler(conn, ev, data):
            name = event_name(ev)
            if name not in seen_names:
                seen_names.append(name)

        with Manager(handler) as mgr:
            mgr.listen("tcp://127.0.0.1:0")
            mgr.poll(10)

        assert "MG_EV_POLL" in seen_names


# ---------------------------------------------------------------------------
# 7. reply_json() convenience method
# ---------------------------------------------------------------------------


class TestReplyJson:
    """Connection.reply_json() sends JSON with correct Content-Type."""

    def test_reply_json_basic(self):
        """reply_json() serializes data and sets Content-Type."""
        payload = {"key": "value", "count": 42}

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                conn.reply_json(payload)

        with ServerThread(handler) as port:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/test", timeout=2)
            body = resp.read()
            content_type = resp.headers.get("Content-Type", "")

        parsed = json.loads(body)
        assert parsed == payload
        assert "application/json" in content_type

    def test_reply_json_custom_status(self):
        """reply_json() respects custom status code."""

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                conn.reply_json({"error": "not found"}, status_code=404)

        with ServerThread(handler) as port:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/missing", timeout=2)
                assert False, "Should have raised HTTPError"
            except urllib.error.HTTPError as e:
                assert e.code == 404
                body = json.loads(e.read())
                assert body == {"error": "not found"}

    def test_reply_json_with_extra_headers(self):
        """reply_json() merges user headers with Content-Type."""

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                conn.reply_json(
                    {"ok": True},
                    headers={"X-Custom": "test-value"},
                )

        with ServerThread(handler) as port:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
            resp.read()
            assert resp.headers.get("X-Custom") == "test-value"
            assert "application/json" in resp.headers.get("Content-Type", "")

    def test_reply_json_list(self):
        """reply_json() works with lists."""
        payload = [1, 2, 3]

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                conn.reply_json(payload)

        with ServerThread(handler) as port:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
            parsed = json.loads(resp.read())
            assert parsed == [1, 2, 3]

    def test_reply_json_string(self):
        """reply_json() works with plain strings."""

        def handler(conn, ev, data):
            if ev == MG_EV_HTTP_MSG:
                conn.reply_json("hello")

        with ServerThread(handler) as port:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
            parsed = json.loads(resp.read())
            assert parsed == "hello"


# ---------------------------------------------------------------------------
# 8. Dead code removal (verified by absence -- no direct test needed)
#    Timer._set_timer() and comment artifact removed.
#    We verify Timer still works correctly.
# ---------------------------------------------------------------------------


class TestTimerStillWorks:
    """Timer works correctly after dead code removal."""

    def test_timer_fires(self):
        """timer_add still works after removing dead _set_timer method."""
        fired = []

        def callback():
            fired.append(True)

        with Manager() as mgr:
            mgr.timer_add(10, callback, repeat=False)
            for _ in range(20):
                mgr.poll(10)

        assert len(fired) >= 1

    def test_timer_repeat(self):
        """Repeating timer still works."""
        count = []

        def callback():
            count.append(1)

        with Manager() as mgr:
            mgr.timer_add(10, callback, repeat=True)
            for _ in range(30):
                mgr.poll(10)

        assert len(count) >= 2


# ---------------------------------------------------------------------------
# 9. Consolidate close()/dealloc cleanup
# ---------------------------------------------------------------------------


class TestCleanupConsolidation:
    """close() and __dealloc__ use shared cleanup path."""

    def test_close_is_idempotent(self):
        """Calling close() twice should not crash."""
        mgr = Manager()
        mgr.listen("tcp://127.0.0.1:0")
        mgr.poll(10)
        mgr.close()
        mgr.close()  # second call should be safe

    def test_close_then_dealloc(self):
        """close() followed by garbage collection should not crash."""
        mgr = Manager()
        mgr.listen("tcp://127.0.0.1:0")
        mgr.poll(10)
        mgr.close()
        del mgr  # triggers __dealloc__

    def test_poll_after_close_raises(self):
        """poll() after close() raises RuntimeError."""
        mgr = Manager()
        mgr.close()
        try:
            mgr.poll(10)
            assert False, "Should have raised RuntimeError"
        except RuntimeError:
            pass


# ---------------------------------------------------------------------------
# 10. Manager.connections property
# ---------------------------------------------------------------------------


class TestManagerConnections:
    """Manager.connections exposes active connections as a read-only tuple."""

    def test_connections_starts_empty(self):
        """No connections initially."""
        with Manager() as mgr:
            mgr.poll(10)
            assert mgr.connections == ()

    def test_connections_includes_listener(self):
        """Listener appears in connections."""
        with Manager() as mgr:
            listener = mgr.listen("tcp://127.0.0.1:0")
            mgr.poll(10)
            conns = mgr.connections
            assert len(conns) >= 1
            assert listener in conns

    def test_connections_includes_accepted(self):
        """Accepted client connections appear in connections."""
        with Manager() as mgr:
            listener = mgr.listen("tcp://127.0.0.1:0")
            mgr.poll(10)
            port = listener.local_addr[1]

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(("127.0.0.1", port))
            for _ in range(20):
                mgr.poll(10)

            conns = mgr.connections
            # At least: listener + accepted connection
            assert len(conns) >= 2
            sock.close()
            mgr.poll(50)

    def test_connections_returns_tuple(self):
        """connections property returns a tuple (immutable snapshot)."""
        with Manager() as mgr:
            mgr.listen("tcp://127.0.0.1:0")
            mgr.poll(10)
            conns = mgr.connections
            assert isinstance(conns, tuple)

    def test_connections_elements_are_connection(self):
        """Each element is a Connection instance."""
        with Manager() as mgr:
            mgr.listen("tcp://127.0.0.1:0")
            mgr.poll(10)
            for conn in mgr.connections:
                assert isinstance(conn, Connection)

    def test_connections_shrinks_after_close(self):
        """Closed connections are removed from the set."""
        with Manager() as mgr:
            listener = mgr.listen("tcp://127.0.0.1:0")
            mgr.poll(10)
            port = listener.local_addr[1]

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(("127.0.0.1", port))
            for _ in range(20):
                mgr.poll(10)
            count_before = len(mgr.connections)

            sock.close()
            for _ in range(20):
                mgr.poll(10)
            count_after = len(mgr.connections)

            assert count_after < count_before
