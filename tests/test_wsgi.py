"""Tests for the WSGI server adapter."""

import io
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cymongoose.wsgi import WSGIServer, _build_environ, _call_wsgi_app

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
    """Context manager to run a WSGIServer in a background thread."""

    def __init__(self, app, workers=4):
        self.server = WSGIServer(app, workers=workers)
        self._thread = None

    def __enter__(self):
        conn = self.server.listen("http://127.0.0.1:0")
        self.port = conn.local_addr[1]
        self._stop = threading.Event()

        def poll():
            while not self._stop.is_set():
                self.server.manager.poll(50)

        self._thread = threading.Thread(target=poll, daemon=True)
        self._thread.start()
        time.sleep(0.2)
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join(timeout=2)
        self.server.close()


# ---------------------------------------------------------------------------
# Minimal WSGI apps for testing
# ---------------------------------------------------------------------------


def hello_app(environ, start_response):
    """Simplest possible WSGI app."""
    start_response("200 OK", [("Content-Type", "text/plain")])
    return [b"Hello, World!"]


def echo_app(environ, start_response):
    """Echoes back request method, path, query, and body as JSON."""
    body = environ["wsgi.input"].read()
    data = {
        "method": environ["REQUEST_METHOD"],
        "path": environ["PATH_INFO"],
        "query": environ.get("QUERY_STRING", ""),
        "body": body.decode("utf-8", errors="replace"),
        "content_type": environ.get("CONTENT_TYPE", ""),
    }
    payload = json.dumps(data).encode()
    start_response(
        "200 OK",
        [
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(payload))),
        ],
    )
    return [payload]


def headers_app(environ, start_response):
    """Returns all HTTP_* environ keys as JSON."""
    http_headers = {k: v for k, v in environ.items() if k.startswith("HTTP_")}
    payload = json.dumps(http_headers).encode()
    start_response("200 OK", [("Content-Type", "application/json")])
    return [payload]


def status_app(environ, start_response):
    """Returns different status codes based on path."""
    path = environ["PATH_INFO"]
    if path == "/ok":
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [b"OK"]
    elif path == "/created":
        start_response("201 Created", [("Content-Type", "text/plain")])
        return [b"Created"]
    elif path == "/not-found":
        start_response("404 Not Found", [("Content-Type", "text/plain")])
        return [b"Not Found"]
    else:
        start_response("400 Bad Request", [("Content-Type", "text/plain")])
        return [b"Bad Request"]


def error_app(environ, start_response):
    """Raises an exception."""
    raise ValueError("intentional test error")


def iterator_app(environ, start_response):
    """Returns response body as multiple chunks."""
    start_response("200 OK", [("Content-Type", "text/plain")])
    return [b"chunk1", b"chunk2", b"chunk3"]


def closeable_app(environ, start_response):
    """Returns an iterator with a close() method."""
    start_response("200 OK", [("Content-Type", "text/plain")])

    class ClosingIterator:
        closed = False

        def __iter__(self):
            yield b"data"

        def close(self):
            ClosingIterator.closed = True

    return ClosingIterator()


def custom_headers_app(environ, start_response):
    """Sets custom response headers."""
    start_response(
        "200 OK",
        [
            ("Content-Type", "text/plain"),
            ("X-Custom", "test-value"),
            ("X-Request-Method", environ["REQUEST_METHOD"]),
        ],
    )
    return [b"OK"]


# ---------------------------------------------------------------------------
# Tests: _build_environ
# ---------------------------------------------------------------------------


class TestBuildEnviron:
    """Unit tests for environ dict construction."""

    def test_basic_get(self):
        """Verify core CGI variables for a simple GET."""

        class FakeHM:
            method = "GET"
            uri = "/hello"
            query = "a=1"
            proto = "HTTP/1.1"
            body_bytes = b""

            def header(self, name, default=None):
                return default

            def headers(self):
                return []

        class FakeConn:
            is_tls = False
            remote_addr = ("127.0.0.1", 54321, False)

        env = _build_environ(FakeHM(), FakeConn(), "localhost", 8000)

        assert env["REQUEST_METHOD"] == "GET"
        assert env["PATH_INFO"] == "/hello"
        assert env["QUERY_STRING"] == "a=1"
        assert env["SERVER_NAME"] == "localhost"
        assert env["SERVER_PORT"] == "8000"
        assert env["SERVER_PROTOCOL"] == "HTTP/1.1"
        assert env["wsgi.url_scheme"] == "http"
        assert env["wsgi.multithread"] is True
        assert env["wsgi.multiprocess"] is False
        assert env["REMOTE_ADDR"] == "127.0.0.1"

    def test_query_in_uri(self):
        """Query string embedded in URI should be parsed correctly."""

        class FakeHM:
            method = "GET"
            uri = "/search?q=test&page=2"
            query = ""
            proto = "HTTP/1.1"
            body_bytes = b""

            def header(self, name, default=None):
                return default

            def headers(self):
                return []

        class FakeConn:
            is_tls = False
            remote_addr = ("127.0.0.1", 54321, False)

        env = _build_environ(FakeHM(), FakeConn(), "localhost", 8000)
        assert env["PATH_INFO"] == "/search"
        assert env["QUERY_STRING"] == "q=test&page=2"

    def test_tls_scheme(self):
        """TLS connections should report https scheme."""

        class FakeHM:
            method = "GET"
            uri = "/"
            query = ""
            proto = "HTTP/1.1"
            body_bytes = b""

            def header(self, name, default=None):
                return default

            def headers(self):
                return []

        class FakeConn:
            is_tls = True
            remote_addr = ("127.0.0.1", 54321, False)

        env = _build_environ(FakeHM(), FakeConn(), "localhost", 443)
        assert env["wsgi.url_scheme"] == "https"


# ---------------------------------------------------------------------------
# Tests: _call_wsgi_app
# ---------------------------------------------------------------------------


class TestCallWSGIApp:
    """Unit tests for the WSGI callable invocation."""

    def test_hello(self):
        environ = {"REQUEST_METHOD": "GET", "wsgi.input": io.BytesIO()}
        status, headers, body = _call_wsgi_app(hello_app, environ)
        assert status == 200
        assert body == b"Hello, World!"
        assert ("Content-Type", "text/plain") in headers

    def test_error_returns_500(self):
        environ = {"REQUEST_METHOD": "GET", "wsgi.input": io.BytesIO()}
        status, headers, body = _call_wsgi_app(error_app, environ)
        assert status == 500
        assert b"Internal Server Error" in body

    def test_multi_chunk_body(self):
        environ = {"REQUEST_METHOD": "GET", "wsgi.input": io.BytesIO()}
        status, headers, body = _call_wsgi_app(iterator_app, environ)
        assert status == 200
        assert body == b"chunk1chunk2chunk3"


# ---------------------------------------------------------------------------
# Tests: WSGIServer integration
# ---------------------------------------------------------------------------


class TestWSGIServerBasic:
    """Integration tests: start a real server, make real HTTP requests."""

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
            assert data["content_type"] == "application/x-www-form-urlencoded"

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
            assert data["content_type"] == "application/json"


class TestWSGIServerStatus:
    """Status code handling."""

    def test_200(self):
        with _ServerCtx(status_app) as srv:
            status, body, _ = _request(srv.port, "/ok")
            assert status == 200
            assert body == "OK"

    def test_201(self):
        with _ServerCtx(status_app) as srv:
            status, body, _ = _request(srv.port, "/created")
            assert status == 201
            assert body == "Created"

    def test_404(self):
        with _ServerCtx(status_app) as srv:
            status, body, _ = _request(srv.port, "/not-found")
            assert status == 404
            assert body == "Not Found"

    def test_400(self):
        with _ServerCtx(status_app) as srv:
            status, body, _ = _request(srv.port, "/unknown")
            assert status == 400


class TestWSGIServerHeaders:
    """HTTP header forwarding and response headers."""

    def test_request_headers_forwarded(self):
        with _ServerCtx(headers_app) as srv:
            status, body, _ = _request(
                srv.port,
                "/",
                headers={"X-Custom-Header": "test123"},
            )
            assert status == 200
            data = json.loads(body)
            assert data.get("HTTP_X_CUSTOM_HEADER") == "test123"

    def test_custom_response_headers(self):
        with _ServerCtx(custom_headers_app) as srv:
            status, body, hdrs = _request(srv.port, "/")
            assert status == 200
            assert hdrs.get("X-Custom") == "test-value"
            assert hdrs.get("X-Request-Method") == "GET"


class TestWSGIServerErrors:
    """Application error handling."""

    def test_app_exception_returns_500(self):
        with _ServerCtx(error_app) as srv:
            status, body, _ = _request(srv.port, "/")
            assert status == 500
            assert "Internal Server Error" in body


class TestWSGIServerIterator:
    """Multi-chunk and closeable response iterators."""

    def test_multi_chunk(self):
        with _ServerCtx(iterator_app) as srv:
            status, body, _ = _request(srv.port, "/")
            assert status == 200
            assert body == "chunk1chunk2chunk3"

    def test_closeable_iterator(self):
        with _ServerCtx(closeable_app) as srv:
            status, body, _ = _request(srv.port, "/")
            assert status == 200
            assert body == "data"


class TestWSGIServerConcurrent:
    """Concurrent request handling."""

    def test_concurrent_requests(self):
        """Multiple requests should be handled concurrently."""
        import concurrent.futures

        def slow_app(environ, start_response):
            import time

            time.sleep(0.2)
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [b"done"]

        with _ServerCtx(slow_app, workers=4) as srv:
            start = time.time()
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                futures = [pool.submit(_request, srv.port, "/") for _ in range(4)]
                results = [f.result() for f in futures]
            elapsed = time.time() - start

            # 4 requests at 0.2s each, running in parallel, should
            # complete well under 4 * 0.2s = 0.8s sequential time
            assert elapsed < 0.6, f"Expected parallel execution, took {elapsed:.2f}s"
            assert all(r[0] == 200 for r in results)


if __name__ == "__main__":
    result = pytest.main([__file__, "-v"])
    sys.exit(result)
