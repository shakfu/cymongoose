"""Tests for the ASGI server adapter."""

import asyncio
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cymongoose.asgi import ASGIServer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _request(port, path="/", method="GET", body=None, headers=None):
    """Make an HTTP request and return (status, body_str, headers_dict)."""
    url = f"http://127.0.0.1:{port}{path}"
    data = body.encode() if isinstance(body, str) else body
    req = urllib.request.Request(url, data=data, method=method)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        resp = urllib.request.urlopen(req, timeout=3)
        return resp.status, resp.read().decode(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), dict(e.headers)


class _ServerCtx:
    """Context manager that runs an ASGIServer for testing."""

    def __init__(self, app):
        self.app = app
        self.server = ASGIServer(app)
        self.port = 0
        self._loop = None
        self._thread = None
        self._started = threading.Event()

    def __enter__(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._started.wait(timeout=5)
        return self

    def __exit__(self, *exc):
        if self._loop is not None:
            asyncio.run_coroutine_threadsafe(self.server.stop(), self._loop).result(timeout=5)
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        async def start():
            conn = await self.server.start("http://127.0.0.1:0")
            addr = conn.local_addr
            self.port = addr[1] if addr is not None else 0
            self._started.set()

        self._loop.run_until_complete(start())
        self._loop.run_forever()
        self._loop.close()


# ---------------------------------------------------------------------------
# Minimal ASGI apps
# ---------------------------------------------------------------------------


async def hello_app(scope, receive, send):
    """Simplest ASGI app."""
    if scope["type"] == "http":
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"text/plain"]],
            }
        )
        await send({"type": "http.response.body", "body": b"Hello, World!"})


async def echo_app(scope, receive, send):
    """Echoes request details back as JSON."""
    if scope["type"] == "http":
        msg = await receive()
        body = msg.get("body", b"")
        data = {
            "method": scope["method"],
            "path": scope["path"],
            "query": scope["query_string"].decode(),
            "body": body.decode("utf-8", errors="replace"),
        }
        payload = json.dumps(data).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"application/json"]],
            }
        )
        await send({"type": "http.response.body", "body": payload})


async def status_app(scope, receive, send):
    """Returns different status codes based on path."""
    if scope["type"] == "http":
        await receive()
        path = scope["path"]
        status_map = {"/ok": 200, "/created": 201, "/not-found": 404}
        status = status_map.get(path, 400)
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [[b"content-type", b"text/plain"]],
            }
        )
        body = {200: b"OK", 201: b"Created", 404: b"Not Found"}.get(status, b"Bad Request")
        await send({"type": "http.response.body", "body": body})


async def error_app(scope, receive, send):
    """Raises an exception."""
    if scope["type"] == "http":
        raise ValueError("intentional test error")


async def headers_app(scope, receive, send):
    """Echoes request headers back as JSON."""
    if scope["type"] == "http":
        await receive()
        hdrs = {k.decode(): v.decode() for k, v in scope["headers"] if k.decode().startswith("x-")}
        payload = json.dumps(hdrs).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"application/json"]],
            }
        )
        await send({"type": "http.response.body", "body": payload})


async def duplicate_headers_app(scope, receive, send):
    """Sets multiple Set-Cookie headers."""
    if scope["type"] == "http":
        await receive()
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    [b"content-type", b"text/plain"],
                    [b"set-cookie", b"a=1"],
                    [b"set-cookie", b"b=2"],
                ],
            }
        )
        await send({"type": "http.response.body", "body": b"ok"})


async def ws_echo_app(scope, receive, send):
    """WebSocket echo server."""
    if scope["type"] == "websocket":
        msg = await receive()
        assert msg["type"] == "websocket.connect"
        await send({"type": "websocket.accept"})

        while True:
            msg = await receive()
            if msg["type"] == "websocket.disconnect":
                break
            if "text" in msg:
                await send({"type": "websocket.send", "text": msg["text"]})
            elif "bytes" in msg:
                await send({"type": "websocket.send", "bytes": msg["bytes"]})


# ---------------------------------------------------------------------------
# Tests: HTTP
# ---------------------------------------------------------------------------


class TestASGIHTTPBasic:
    """Basic HTTP request/response."""

    def test_hello(self):
        with _ServerCtx(hello_app) as srv:
            status, body, _ = _request(srv.port, "/")
            assert status == 200
            assert body == "Hello, World!"

    def test_echo_get(self):
        with _ServerCtx(echo_app) as srv:
            status, body, _ = _request(srv.port, "/test?foo=bar")
            assert status == 200
            data = json.loads(body)
            assert data["method"] == "GET"
            assert data["path"] == "/test"
            assert data["query"] == "foo=bar"

    def test_echo_post(self):
        with _ServerCtx(echo_app) as srv:
            payload = "hello=world"
            status, body, _ = _request(
                srv.port,
                "/echo",
                method="POST",
                body=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            assert status == 200
            data = json.loads(body)
            assert data["method"] == "POST"
            assert data["body"] == "hello=world"

    def test_json_post(self):
        with _ServerCtx(echo_app) as srv:
            payload = json.dumps({"key": "value"})
            status, body, _ = _request(
                srv.port,
                "/data",
                method="POST",
                body=payload,
                headers={"Content-Type": "application/json"},
            )
            assert status == 200
            data = json.loads(body)
            assert data["body"] == payload


class TestASGIHTTPStatus:
    """Status code handling."""

    def test_200(self):
        with _ServerCtx(status_app) as srv:
            status, body, _ = _request(srv.port, "/ok")
            assert status == 200

    def test_201(self):
        with _ServerCtx(status_app) as srv:
            status, body, _ = _request(srv.port, "/created")
            assert status == 201

    def test_404(self):
        with _ServerCtx(status_app) as srv:
            status, body, _ = _request(srv.port, "/not-found")
            assert status == 404


class TestASGIHTTPHeaders:
    """Header forwarding."""

    def test_request_headers(self):
        with _ServerCtx(headers_app) as srv:
            status, body, _ = _request(srv.port, "/", headers={"X-Custom": "test123"})
            assert status == 200
            data = json.loads(body)
            assert data.get("x-custom") == "test123"

    def test_duplicate_response_headers(self):
        import http.client

        with _ServerCtx(duplicate_headers_app) as srv:
            conn = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=2)
            conn.request("GET", "/")
            resp = conn.getresponse()
            resp.read()
            cookies = [v for k, v in resp.getheaders() if k == "set-cookie"]
            assert len(cookies) == 2
            assert "a=1" in cookies
            assert "b=2" in cookies
            conn.close()


class TestASGIHTTPErrors:
    """Application error handling."""

    def test_app_exception_returns_500(self):
        with _ServerCtx(error_app) as srv:
            status, body, _ = _request(srv.port, "/")
            assert status == 500
            assert "Internal Server Error" in body


# ---------------------------------------------------------------------------
# Tests: WebSocket
# ---------------------------------------------------------------------------


class TestASGIWebSocket:
    """WebSocket sub-protocol."""

    def _ws_available(self):
        try:
            import websocket  # noqa: F401

            return True
        except ImportError:
            return False

    def test_ws_echo_text(self):
        if not self._ws_available():
            pytest.skip("websocket-client not installed")

        import websocket

        with _ServerCtx(ws_echo_app) as srv:
            ws = websocket.create_connection(f"ws://127.0.0.1:{srv.port}/ws", timeout=3)
            ws.send("hello")
            result = ws.recv()
            assert result == "hello"
            ws.close()

    def test_ws_echo_binary(self):
        if not self._ws_available():
            pytest.skip("websocket-client not installed")

        import websocket

        with _ServerCtx(ws_echo_app) as srv:
            ws = websocket.create_connection(f"ws://127.0.0.1:{srv.port}/ws", timeout=3)
            ws.send_binary(b"\x00\x01\x02\x03")
            _, result = ws.recv_data()
            assert result == b"\x00\x01\x02\x03"
            ws.close()

    def test_ws_multiple_messages(self):
        if not self._ws_available():
            pytest.skip("websocket-client not installed")

        import websocket

        with _ServerCtx(ws_echo_app) as srv:
            ws = websocket.create_connection(f"ws://127.0.0.1:{srv.port}/ws", timeout=3)
            for msg in ["one", "two", "three"]:
                ws.send(msg)
                assert ws.recv() == msg
            ws.close()


# ---------------------------------------------------------------------------
# Tests: Scope
# ---------------------------------------------------------------------------


class TestASGIScope:
    """ASGI scope construction."""

    def test_http_scope_fields(self):
        captured = {}

        async def capture_app(scope, receive, send):
            if scope["type"] == "http":
                captured.update(scope)
                await receive()
                await send(
                    {
                        "type": "http.response.start",
                        "status": 200,
                        "headers": [],
                    }
                )
                await send({"type": "http.response.body", "body": b"ok"})

        with _ServerCtx(capture_app) as srv:
            _request(srv.port, "/test?q=1", headers={"X-Foo": "bar"})
            time.sleep(0.1)

        assert captured["type"] == "http"
        assert captured["method"] == "GET"
        assert captured["path"] == "/test"
        assert captured["query_string"] == b"q=1"
        assert captured["scheme"] == "http"
        assert any(h[0] == b"x-foo" and h[1] == b"bar" for h in captured["headers"])


if __name__ == "__main__":
    result = pytest.main([__file__, "-v"])
    sys.exit(result)
