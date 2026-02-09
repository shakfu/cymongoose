"""Concurrent client tests for the HTTP and WebSocket server.

Uses ThreadPoolExecutor to fire parallel requests and verify correctness
under concurrent access -- no crashes, no mixed-up responses, no drops.
"""

import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

try:
    import websocket

    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False

from cymongoose import (
    MG_EV_HTTP_MSG,
    MG_EV_WS_MSG,
    WEBSOCKET_OP_TEXT,
)

from .conftest import ServerThread


def _echo_handler(conn, event, data):
    """Respond with method, uri, and body so clients can verify per-request correctness."""
    if event == MG_EV_HTTP_MSG:
        body = f"method={data.method} uri={data.uri} body={data.body_text}"
        conn.reply(200, body)


def _ws_echo_handler(conn, event, data):
    """Upgrade HTTP to WS and echo text messages back."""
    if event == MG_EV_HTTP_MSG:
        conn.ws_upgrade(data)
    elif event == MG_EV_WS_MSG:
        conn.ws_send(data.text, WEBSOCKET_OP_TEXT)


def _http_get(port, path="/"):
    """Perform a single GET and return (status, body)."""
    resp = urllib.request.urlopen(f"http://localhost:{port}{path}", timeout=5)
    return resp.status, resp.read().decode("utf-8")


def _http_post(port, path="/", body_str=""):
    """Perform a single POST and return (status, body)."""
    data = body_str.encode("utf-8")
    req = urllib.request.Request(
        f"http://localhost:{port}{path}",
        data=data,
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=5)
    return resp.status, resp.read().decode("utf-8")


def _http_method(port, method, path="/", body_str=""):
    """Perform a request with an arbitrary method."""
    data = body_str.encode("utf-8") if body_str else None
    req = urllib.request.Request(
        f"http://localhost:{port}{path}",
        data=data,
        method=method,
    )
    resp = urllib.request.urlopen(req, timeout=5)
    return resp.status, resp.read().decode("utf-8")


class TestConcurrentHTTP:
    """Concurrent HTTP request tests."""

    def test_concurrent_get_requests(self):
        """10 threads x 5 requests each = 50 GETs, all must return 200."""
        with ServerThread(_echo_handler) as port:
            results = []

            def worker():
                for _ in range(5):
                    results.append(_http_get(port, "/hello"))

            threads = []
            for _ in range(10):
                import threading

                t = threading.Thread(target=worker)
                t.start()
                threads.append(t)

            for t in threads:
                t.join(timeout=10)

            assert len(results) == 50
            for status, body in results:
                assert status == 200
                assert "method=GET" in body
                assert "uri=/hello" in body

    def test_concurrent_different_paths(self):
        """10 threads hitting /path/0 .. /path/9 -- each response contains the right path."""
        with ServerThread(_echo_handler) as port:
            with ThreadPoolExecutor(max_workers=10) as pool:
                futures = {pool.submit(_http_get, port, f"/path/{i}"): i for i in range(10)}
                for future in as_completed(futures):
                    idx = futures[future]
                    status, body = future.result()
                    assert status == 200
                    assert f"uri=/path/{idx}" in body

    def test_concurrent_post_requests(self):
        """10 threads POSTing unique payloads -- each echoed body matches."""
        with ServerThread(_echo_handler) as port:
            with ThreadPoolExecutor(max_workers=10) as pool:
                futures = {
                    pool.submit(_http_post, port, "/echo", f"payload-{i}"): i for i in range(10)
                }
                for future in as_completed(futures):
                    idx = futures[future]
                    status, body = future.result()
                    assert status == 200
                    assert f"body=payload-{idx}" in body

    def test_concurrent_mixed_methods(self):
        """GET, POST, PUT, DELETE in parallel -- all return 200 with correct method echo."""
        methods = ["GET", "POST", "PUT", "DELETE"]
        with ServerThread(_echo_handler) as port:
            with ThreadPoolExecutor(max_workers=4) as pool:
                futures = {pool.submit(_http_method, port, m, "/mixed", "x"): m for m in methods}
                for future in as_completed(futures):
                    method = futures[future]
                    status, body = future.result()
                    assert status == 200
                    assert f"method={method}" in body

    def test_rapid_sequential_connections(self):
        """100 requests in a tight serial loop -- all must return 200."""
        with ServerThread(_echo_handler) as port:
            for i in range(100):
                status, body = _http_get(port, f"/seq/{i}")
                assert status == 200
                assert f"uri=/seq/{i}" in body


@pytest.mark.skipif(not HAS_WEBSOCKET, reason="websocket-client not installed")
class TestConcurrentWebSocket:
    """Concurrent WebSocket tests."""

    def test_concurrent_websocket_echo(self):
        """5 WS clients sending/receiving in parallel -- each gets its own echo."""
        with ServerThread(_ws_echo_handler) as port:
            results = {}
            errors = []

            def ws_worker(client_id):
                try:
                    ws = websocket.WebSocket()
                    ws.connect(f"ws://localhost:{port}/ws")
                    msg = f"hello from client {client_id}"
                    ws.send(msg)
                    reply = ws.recv()
                    results[client_id] = reply
                    ws.close()
                except Exception as exc:
                    errors.append((client_id, exc))

            with ThreadPoolExecutor(max_workers=5) as pool:
                futures = [pool.submit(ws_worker, i) for i in range(5)]
                for f in futures:
                    f.result(timeout=10)

            assert not errors, f"WS client errors: {errors}"
            assert len(results) == 5
            for client_id, reply in results.items():
                assert reply == f"hello from client {client_id}"
