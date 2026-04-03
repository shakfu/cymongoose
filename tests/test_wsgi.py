"""Tests for the WSGI server adapter."""

import json
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cymongoose.wsgi import WSGIServer, _build_environ

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


class TestWSGILargePayload:
    """Responses exceeding _WAKEUP_MAX_BYTES use the stash fallback."""

    def test_large_response_stash_fallback(self):
        """A response larger than 8 KB but under 1 MB uses the stash path."""
        # 500 KB -- above _WAKEUP_MAX_BYTES (8 KB) but below
        # _STREAM_THRESHOLD (1 MB), so it takes the buffered+stash path.
        big_body = b"X" * (500 * 1024)

        def large_app(environ, start_response):
            start_response("200 OK", [("Content-Type", "application/octet-stream")])
            return [big_body]

        with _ServerCtx(large_app) as srv:
            status, body, _ = _request(srv.port, "/")
            assert status == 200
            assert len(body) == len(big_body)
            assert body == big_body.decode()

    def test_small_response_inline(self):
        """Responses under the threshold go through the inline path."""

        def small_app(environ, start_response):
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [b"tiny"]

        with _ServerCtx(small_app) as srv:
            status, body, _ = _request(srv.port, "/")
            assert status == 200
            assert body == "tiny"

    def test_stash_cleaned_up_after_delivery(self):
        """The stash entry is removed after the response is sent."""
        big_body = b"Y" * (1024 * 1024)

        def large_app(environ, start_response):
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [big_body]

        srv_ctx = _ServerCtx(large_app)
        with srv_ctx as srv:
            _request(srv.port, "/")
            time.sleep(0.1)
            # Stash should be empty after the response was delivered
            assert len(srv_ctx.server._stash) == 0


class TestWSGIFileWrapper:
    """wsgi.file_wrapper support."""

    def test_file_wrapper_in_environ(self):
        """environ should contain wsgi.file_wrapper."""
        from cymongoose.wsgi import FileWrapper

        def check_app(environ, start_response):
            assert "wsgi.file_wrapper" in environ
            assert environ["wsgi.file_wrapper"] is FileWrapper
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [b"ok"]

        with _ServerCtx(check_app) as srv:
            status, body, _ = _request(srv.port, "/")
            assert status == 200

    def test_file_wrapper_serves_file(self, tmp_path):
        """An app using wsgi.file_wrapper should serve file content."""
        test_file = tmp_path / "test.txt"
        test_content = b"Hello from file wrapper!"
        test_file.write_bytes(test_content)

        def file_app(environ, start_response):
            wrapper = environ["wsgi.file_wrapper"]
            fh = open(str(test_file), "rb")
            start_response(
                "200 OK",
                [
                    ("Content-Type", "text/plain"),
                    ("Content-Length", str(len(test_content))),
                ],
            )
            return wrapper(fh)

        with _ServerCtx(file_app) as srv:
            status, body, _ = _request(srv.port, "/")
            assert status == 200
            assert body == test_content.decode()

    def test_file_wrapper_large_file(self, tmp_path):
        """File wrapper should handle files larger than the block size."""
        test_file = tmp_path / "large.bin"
        # 100 KB file (larger than default 8192 block size)
        test_content = b"A" * (100 * 1024)
        test_file.write_bytes(test_content)

        def file_app(environ, start_response):
            wrapper = environ["wsgi.file_wrapper"]
            fh = open(str(test_file), "rb")
            start_response("200 OK", [("Content-Type", "application/octet-stream")])
            return wrapper(fh, blksize=4096)

        with _ServerCtx(file_app) as srv:
            status, body, _ = _request(srv.port, "/")
            assert status == 200
            assert len(body) == len(test_content)

    def test_file_wrapper_close_called(self, tmp_path):
        """File wrapper should call close() on the underlying file."""
        test_file = tmp_path / "close_test.txt"
        test_file.write_bytes(b"data")

        closed = {"value": False}

        class TrackingFile:
            def __init__(self):
                self._fh = open(str(test_file), "rb")

            def read(self, size=-1):
                return self._fh.read(size)

            def close(self):
                self._fh.close()
                closed["value"] = True

        def file_app(environ, start_response):
            wrapper = environ["wsgi.file_wrapper"]
            start_response("200 OK", [("Content-Type", "text/plain")])
            return wrapper(TrackingFile())

        with _ServerCtx(file_app) as srv:
            status, body, _ = _request(srv.port, "/")
            assert status == 200
            assert body == "data"
            time.sleep(0.1)
            assert closed["value"] is True


class TestWSGIChunkedStreaming:
    """Responses exceeding _STREAM_THRESHOLD use chunked transfer encoding."""

    def test_large_single_chunk_triggers_streaming(self):
        """A single chunk > 1 MB triggers the streaming path."""
        big_body = b"Z" * (2 * 1024 * 1024)  # 2 MB

        def app(environ, start_response):
            start_response("200 OK", [("Content-Type", "application/octet-stream")])
            return [big_body]

        with _ServerCtx(app) as srv:
            status, body, hdrs = _request(srv.port, "/")
            assert status == 200
            assert len(body) == len(big_body)

    def test_many_small_chunks_trigger_streaming(self):
        """Many small chunks that sum to > 1 MB trigger streaming."""
        chunk_size = 64 * 1024  # 64 KB
        num_chunks = 20  # 1.25 MB total

        def app(environ, start_response):
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [b"x" * chunk_size for _ in range(num_chunks)]

        with _ServerCtx(app) as srv:
            status, body, _ = _request(srv.port, "/")
            assert status == 200
            assert len(body) == chunk_size * num_chunks

    def test_streaming_with_generator(self):
        """A generator that yields chunks lazily should stream correctly."""
        chunk = b"CHUNK"
        num_chunks = 300_000  # ~1.4 MB total

        def app(environ, start_response):
            start_response("200 OK", [("Content-Type", "text/plain")])

            def gen():
                for _ in range(num_chunks):
                    yield chunk

            return gen()

        with _ServerCtx(app) as srv:
            status, body, _ = _request(srv.port, "/")
            assert status == 200
            assert len(body) == len(chunk) * num_chunks

    def test_streaming_preserves_headers(self):
        """Custom response headers should be preserved in streaming mode."""
        big_body = b"H" * (2 * 1024 * 1024)

        def app(environ, start_response):
            start_response(
                "200 OK",
                [
                    ("Content-Type", "application/octet-stream"),
                    ("X-Custom", "streaming-test"),
                ],
            )
            return [big_body]

        with _ServerCtx(app) as srv:
            status, body, hdrs = _request(srv.port, "/")
            assert status == 200
            assert hdrs.get("X-Custom") == "streaming-test"
            assert len(body) == len(big_body)

    def test_small_response_stays_buffered(self):
        """Responses under 1 MB should use the buffered path."""

        def app(environ, start_response):
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [b"small"]

        with _ServerCtx(app) as srv:
            status, body, hdrs = _request(srv.port, "/")
            assert status == 200
            assert body == "small"
            # Buffered responses use Content-Length, not chunked
            assert "Content-Length" in hdrs

    def test_streaming_file_wrapper_large(self, tmp_path):
        """FileWrapper serving a file > 1 MB should stream."""

        test_file = tmp_path / "big.bin"
        content = b"F" * (2 * 1024 * 1024)
        test_file.write_bytes(content)

        def app(environ, start_response):
            wrapper = environ["wsgi.file_wrapper"]
            fh = open(str(test_file), "rb")
            start_response("200 OK", [("Content-Type", "application/octet-stream")])
            return wrapper(fh, blksize=65536)

        with _ServerCtx(app) as srv:
            status, body, _ = _request(srv.port, "/")
            assert status == 200
            assert len(body) == len(content)

    def test_stash_cleaned_after_streaming(self):
        """All stash entries should be cleaned up after streaming completes."""
        big_body = b"C" * (2 * 1024 * 1024)

        def app(environ, start_response):
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [big_body]

        srv_ctx = _ServerCtx(app)
        with srv_ctx as srv:
            _request(srv.port, "/")
            time.sleep(0.2)
            assert len(srv_ctx.server._stash) == 0

    def test_large_headers_via_stash(self):
        """Response headers exceeding 8 KB should go through the stash path."""
        big_body = b"B" * (2 * 1024 * 1024)
        # Generate enough headers to exceed _WAKEUP_MAX_BYTES (8 KB).
        # Each header is ~110 bytes, so 80 headers ~= 9 KB.
        many_headers = [(f"X-Hdr-{i:03d}", "x" * 100) for i in range(80)]

        def app(environ, start_response):
            hdrs = [("Content-Type", "text/plain")] + many_headers
            start_response("200 OK", hdrs)
            return [big_body]

        with _ServerCtx(app) as srv:
            status, body, hdrs = _request(srv.port, "/")
            assert status == 200
            assert len(body) == len(big_body)
            # Spot-check a few custom headers survived the round-trip.
            assert hdrs.get("X-Hdr-000") == "x" * 100
            assert hdrs.get("X-Hdr-079") == "x" * 100

    def test_mid_stream_disconnect_no_deadlock(self):
        """Worker should not deadlock if the connection closes mid-stream.

        The worker uses q.put(timeout=5).  We verify that the worker
        finishes promptly rather than hanging.
        """

        # App that yields chunks slowly -- gives us time to kill the connection.
        def slow_stream_app(environ, start_response):
            start_response("200 OK", [("Content-Type", "text/plain")])

            def gen():
                for i in range(100):
                    yield b"X" * (64 * 1024)  # 64 KB chunks, 6.4 MB total
                    time.sleep(0.05)

            return gen()

        srv_ctx = _ServerCtx(slow_stream_app)
        with srv_ctx as srv:
            # Start a request but close it immediately after reading
            # a bit, simulating a client disconnect.
            import http.client

            conn = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=2)
            conn.request("GET", "/")
            resp = conn.getresponse()
            # Read just enough to confirm streaming started.
            resp.read(1024)
            conn.close()

            # Wait a bit -- the worker should abort within
            # _STREAM_PUT_TIMEOUT (5s), not hang forever.
            time.sleep(1.0)

            # The stream entry should be cleaned up.
            assert len(srv_ctx.server._streams) == 0


class TestWSGIDuplicateHeaders:
    """PEP 3333 allows multiple headers with the same name."""

    def test_duplicate_set_cookie_preserved(self):
        """Multiple Set-Cookie headers should not be collapsed."""
        import http.client

        def app(environ, start_response):
            start_response(
                "200 OK",
                [
                    ("Content-Type", "text/plain"),
                    ("Set-Cookie", "a=1; Path=/"),
                    ("Set-Cookie", "b=2; Path=/"),
                    ("Set-Cookie", "c=3; Path=/"),
                ],
            )
            return [b"ok"]

        with _ServerCtx(app) as srv:
            conn = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=2)
            conn.request("GET", "/")
            resp = conn.getresponse()
            resp.read()

            # getheaders() returns all values for the given name.
            cookies = resp.getheaders()
            set_cookie_values = [v for k, v in cookies if k == "Set-Cookie"]

            assert len(set_cookie_values) == 3, (
                f"Expected 3 Set-Cookie headers, got {len(set_cookie_values)}: "
                f"{set_cookie_values}"
            )
            assert "a=1; Path=/" in set_cookie_values
            assert "b=2; Path=/" in set_cookie_values
            assert "c=3; Path=/" in set_cookie_values
            conn.close()

    def test_single_valued_headers_still_work(self):
        """Normal single-valued headers should be unaffected."""

        def app(environ, start_response):
            start_response(
                "200 OK",
                [
                    ("Content-Type", "application/json"),
                    ("X-Request-Id", "abc-123"),
                ],
            )
            return [b'{"ok": true}']

        with _ServerCtx(app) as srv:
            status, body, hdrs = _request(srv.port, "/")
            assert status == 200
            assert hdrs.get("Content-Type") == "application/json"
            assert hdrs.get("X-Request-Id") == "abc-123"
            assert body == '{"ok": true}'


if __name__ == "__main__":
    result = pytest.main([__file__, "-v"])
    sys.exit(result)
