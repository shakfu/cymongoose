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


# ---------------------------------------------------------------------------
# Streaming ASGI apps
# ---------------------------------------------------------------------------


async def streaming_app(scope, receive, send):
    """Sends response in multiple chunks with more_body=True."""
    if scope["type"] == "http":
        await receive()
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"text/plain"]],
            }
        )
        chunks = [b"chunk1", b"chunk2", b"chunk3"]
        for i, chunk in enumerate(chunks):
            is_last = i == len(chunks) - 1
            await send(
                {
                    "type": "http.response.body",
                    "body": chunk,
                    "more_body": not is_last,
                }
            )


async def streaming_empty_final_app(scope, receive, send):
    """Sends chunks, then an empty final body (more_body=False)."""
    if scope["type"] == "http":
        await receive()
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"text/plain"]],
            }
        )
        await send(
            {"type": "http.response.body", "body": b"hello", "more_body": True}
        )
        await send(
            {"type": "http.response.body", "body": b"", "more_body": False}
        )


async def streaming_large_app(scope, receive, send):
    """Streams a large response exceeding the wakeup stash threshold."""
    if scope["type"] == "http":
        await receive()
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"application/octet-stream"]],
            }
        )
        # 10 KB chunk -- exceeds _WAKEUP_MAX_BYTES (8 KB)
        big_chunk = b"X" * (10 * 1024)
        await send(
            {"type": "http.response.body", "body": big_chunk, "more_body": True}
        )
        await send(
            {"type": "http.response.body", "body": b"done", "more_body": False}
        )


async def streaming_custom_status_app(scope, receive, send):
    """Streams with a 201 status code."""
    if scope["type"] == "http":
        await receive()
        await send(
            {
                "type": "http.response.start",
                "status": 201,
                "headers": [
                    [b"content-type", b"text/plain"],
                    [b"x-custom", b"val"],
                ],
            }
        )
        await send(
            {"type": "http.response.body", "body": b"created-", "more_body": True}
        )
        await send(
            {"type": "http.response.body", "body": b"ok", "more_body": False}
        )


# ---------------------------------------------------------------------------
# Tests: Streaming HTTP
# ---------------------------------------------------------------------------


class TestASGIHTTPStreaming:
    """Chunked streaming via more_body=True."""

    def test_streaming_basic(self):
        """Multiple chunks are concatenated in the response."""
        with _ServerCtx(streaming_app) as srv:
            status, body, headers = _request(srv.port, "/")
            assert status == 200
            assert body == "chunk1chunk2chunk3"
            te = headers.get("Transfer-Encoding", "").lower()
            assert "chunked" in te

    def test_streaming_empty_final(self):
        """Empty final body terminates the chunked stream."""
        with _ServerCtx(streaming_empty_final_app) as srv:
            status, body, _ = _request(srv.port, "/")
            assert status == 200
            assert body == "hello"

    def test_streaming_large_chunk(self):
        """Large chunks (> 8 KB) go through the stash path."""
        with _ServerCtx(streaming_large_app) as srv:
            status, body, _ = _request(srv.port, "/")
            assert status == 200
            expected = ("X" * (10 * 1024)) + "done"
            assert body == expected

    def test_streaming_preserves_status_and_headers(self):
        """Status code and custom headers are preserved in streaming mode."""
        import http.client

        with _ServerCtx(streaming_custom_status_app) as srv:
            conn = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=3)
            conn.request("GET", "/")
            resp = conn.getresponse()
            body = resp.read().decode()
            assert resp.status == 201
            assert resp.getheader("x-custom") == "val"
            assert body == "created-ok"
            conn.close()

    def test_streaming_many_chunks_backpressure(self):
        """Many chunks (> semaphore limit) complete without deadlock or data loss."""
        num_chunks = 64  # 4x the _STREAM_CONCURRENCY limit (16)

        async def many_chunks_app(scope, receive, send):
            if scope["type"] == "http":
                await receive()
                await send(
                    {
                        "type": "http.response.start",
                        "status": 200,
                        "headers": [[b"content-type", b"text/plain"]],
                    }
                )
                for i in range(num_chunks):
                    is_last = i == num_chunks - 1
                    await send(
                        {
                            "type": "http.response.body",
                            "body": f"{i:04d}".encode(),
                            "more_body": not is_last,
                        }
                    )

        with _ServerCtx(many_chunks_app) as srv:
            status, body, _ = _request(srv.port, "/")
            assert status == 200
            expected = "".join(f"{i:04d}" for i in range(num_chunks))
            assert body == expected

    def test_buffered_still_works(self):
        """Non-streaming (no more_body) responses are unaffected."""
        with _ServerCtx(hello_app) as srv:
            status, body, headers = _request(srv.port, "/")
            assert status == 200
            assert body == "Hello, World!"
            # Buffered responses should NOT use chunked TE.
            te = headers.get("Transfer-Encoding", "")
            assert "chunked" not in te.lower()


# ---------------------------------------------------------------------------
# Tests: Lifespan
# ---------------------------------------------------------------------------


class TestASGILifespan:
    """ASGI lifespan sub-protocol."""

    def test_lifespan_startup_shutdown(self):
        """App receives startup and shutdown events in order."""
        events = []

        async def lifespan_app(scope, receive, send):
            if scope["type"] == "lifespan":
                msg = await receive()
                assert msg["type"] == "lifespan.startup"
                events.append("startup")
                await send({"type": "lifespan.startup.complete"})
                msg = await receive()
                assert msg["type"] == "lifespan.shutdown"
                events.append("shutdown")
                await send({"type": "lifespan.shutdown.complete"})
            elif scope["type"] == "http":
                await receive()
                await send(
                    {
                        "type": "http.response.start",
                        "status": 200,
                        "headers": [[b"content-type", b"text/plain"]],
                    }
                )
                await send({"type": "http.response.body", "body": b"ok"})

        with _ServerCtx(lifespan_app) as srv:
            status, body, _ = _request(srv.port, "/")
            assert status == 200
            assert body == "ok"

        assert "startup" in events
        assert "shutdown" in events

    def test_lifespan_state_available_to_requests(self):
        """State initialised during lifespan.startup is visible to handlers."""
        shared = {}

        async def stateful_app(scope, receive, send):
            if scope["type"] == "lifespan":
                msg = await receive()
                assert msg["type"] == "lifespan.startup"
                shared["db"] = "connected"
                await send({"type": "lifespan.startup.complete"})
                msg = await receive()
                assert msg["type"] == "lifespan.shutdown"
                shared.pop("db", None)
                await send({"type": "lifespan.shutdown.complete"})
            elif scope["type"] == "http":
                await receive()
                body = shared.get("db", "missing").encode()
                await send(
                    {
                        "type": "http.response.start",
                        "status": 200,
                        "headers": [[b"content-type", b"text/plain"]],
                    }
                )
                await send({"type": "http.response.body", "body": body})

        with _ServerCtx(stateful_app) as srv:
            status, body, _ = _request(srv.port, "/")
            assert status == 200
            assert body == "connected"

    def test_no_lifespan_support(self):
        """App that doesn't handle lifespan scope -- server proceeds normally."""

        async def no_lifespan_app(scope, receive, send):
            if scope["type"] == "lifespan":
                raise NotImplementedError("no lifespan")
            if scope["type"] == "http":
                await receive()
                await send(
                    {
                        "type": "http.response.start",
                        "status": 200,
                        "headers": [[b"content-type", b"text/plain"]],
                    }
                )
                await send({"type": "http.response.body", "body": b"works"})

        with _ServerCtx(no_lifespan_app) as srv:
            status, body, _ = _request(srv.port, "/")
            assert status == 200
            assert body == "works"

    def test_lifespan_startup_failed(self):
        """App that signals startup failure -- server raises RuntimeError."""

        async def failing_app(scope, receive, send):
            if scope["type"] == "lifespan":
                msg = await receive()
                assert msg["type"] == "lifespan.startup"
                await send(
                    {
                        "type": "lifespan.startup.failed",
                        "message": "db unreachable",
                    }
                )

        server = ASGIServer(failing_app)
        loop = asyncio.new_event_loop()
        try:
            with pytest.raises(RuntimeError, match="db unreachable"):
                loop.run_until_complete(server.start("http://127.0.0.1:0"))
        finally:
            loop.run_until_complete(server.stop())
            loop.close()

    def test_apps_without_lifespan_unaffected(self):
        """Existing apps (like hello_app) that ignore lifespan still work."""
        with _ServerCtx(hello_app) as srv:
            status, body, _ = _request(srv.port, "/")
            assert status == 200
            assert body == "Hello, World!"


if __name__ == "__main__":
    result = pytest.main([__file__, "-v"])
    sys.exit(result)
