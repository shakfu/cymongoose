"""WSGI server adapter for cymongoose.

Run any PEP 3333 WSGI application on cymongoose's C event loop::

    from cymongoose.wsgi import serve
    from myapp import app  # Flask, Django, Bottle, Falcon, ...

    serve(app, "http://127.0.0.1:8000")

Or with more control::

    from cymongoose.wsgi import WSGIServer

    server = WSGIServer(app, workers=8)
    server.listen("http://127.0.0.1:8000")
    server.run()

Architecture
------------
Small responses (< 1 MB) are buffered in full and sent as a single
``conn.send()`` via wakeup.

Large responses (>= 1 MB) switch to **chunked streaming**: the worker
pushes chunks into a per-connection ``queue.Queue`` and sends a tiny
wakeup notification.  The event-loop thread drains the queue and sends
each chunk via ``conn.http_chunk()``.  The bounded queue provides
natural back-pressure -- the worker blocks on ``put()`` when the queue
is full.
"""

from __future__ import annotations

import io
import itertools
import json
import queue
import signal
import sys
import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from types import FrameType, TracebackType
from typing import Any, Callable
from urllib.parse import unquote, urlparse

from . import (
    MG_EV_CLOSE,
    MG_EV_HTTP_MSG,
    MG_EV_WAKEUP,
    Connection,
    HttpMessage,
    Manager,
)

# Type alias for a PEP 3333 WSGI application callable.
WSGIApp = Callable[..., Any]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maximum payload sent inline via wakeup().  mg_wakeup() transmits data
# over a socketpair with MSG_NONBLOCKING; the effective send buffer is
# ~9 KB on macOS, ~64 KB on Linux.  Payloads above this threshold are
# stashed in a thread-safe dict and only a short key goes via wakeup.
_WAKEUP_MAX_BYTES = 8 * 1024  # 8 KB

# Wakeup message types (single-byte prefix).
#
#   I<json_meta>\n<body>   -- inline buffered response (small)
#   S<uuid_hex>            -- stash-lookup buffered response (large)
#   H<raw_http_headers>    -- stream start: raw HTTP headers (inline if small)
#   h<uuid_hex>            -- stream start: raw HTTP headers (stash lookup)
#   D                      -- drain: chunks are waiting in the stream queue
_INLINE = b"I"
_STASH = b"S"
_STREAM_HDR_INLINE = b"H"
_STREAM_HDR_STASH = b"h"
_DRAIN = b"D"

# Body size at which the worker switches from buffered to streaming.
_STREAM_THRESHOLD = 1 * 1024 * 1024  # 1 MB

# Maximum pending chunks in a stream queue.  When full, the worker
# blocks on put() with a timeout -- this is the back-pressure
# mechanism.  If the timeout expires (e.g. because the connection was
# closed and the queue is no longer being drained), the worker aborts.
_STREAM_QUEUE_SIZE = 16
_STREAM_PUT_TIMEOUT = 5.0  # seconds

# Maximum bytes to accumulate before flushing a batch into the queue.
_STREAM_BATCH_SIZE = 256 * 1024  # 256 KB


class FileWrapper:
    """PEP 3333 ``wsgi.file_wrapper`` implementation.

    Wraps a file-like object into an iterable that yields fixed-size
    blocks.

    Parameters
    ----------
    filelike : file-like
        An object with a ``read(size)`` method.
    blksize : int
        Block size for iteration (default 8192).
    """

    def __init__(self, filelike: Any, blksize: int = 8192) -> None:
        self.filelike = filelike
        self.blksize = blksize

    def __iter__(self) -> FileWrapper:
        return self

    def __next__(self) -> bytes:
        data = self.filelike.read(self.blksize)
        if data:
            return data if isinstance(data, bytes) else data.encode()
        raise StopIteration

    def close(self) -> None:
        if hasattr(self.filelike, "close"):
            self.filelike.close()


# ---------------------------------------------------------------------------
# Environ construction
# ---------------------------------------------------------------------------


def _build_environ(
    hm: HttpMessage, conn: Connection, server_name: str, server_port: int
) -> dict[str, Any]:
    """Build a PEP 3333 environ dict from an HttpMessage and Connection."""
    uri = hm.uri or "/"

    if "?" in uri:
        path_info, query_string = uri.split("?", 1)
    else:
        path_info = uri
        query_string = hm.query or ""

    body = hm.body_bytes or b""

    environ: dict[str, Any] = {
        "REQUEST_METHOD": hm.method,
        "SCRIPT_NAME": "",
        "PATH_INFO": unquote(path_info),
        "QUERY_STRING": query_string,
        "SERVER_NAME": server_name,
        "SERVER_PORT": str(server_port),
        "SERVER_PROTOCOL": hm.proto or "HTTP/1.1",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "https" if conn.is_tls else "http",
        "wsgi.input": io.BytesIO(body),
        "wsgi.errors": sys.stderr,
        "wsgi.multithread": True,
        "wsgi.multiprocess": False,
        "wsgi.run_once": False,
        "wsgi.file_wrapper": FileWrapper,
    }

    content_type = hm.header("Content-Type")
    if content_type is not None:
        environ["CONTENT_TYPE"] = content_type

    content_length = hm.header("Content-Length")
    if content_length is not None:
        environ["CONTENT_LENGTH"] = content_length

    remote = conn.remote_addr
    if remote:
        environ["REMOTE_ADDR"] = remote[0]
        environ["REMOTE_HOST"] = remote[0]

    for name, value in hm.headers():
        key = name.upper().replace("-", "_")
        if key in ("CONTENT_TYPE", "CONTENT_LENGTH"):
            continue
        env_key = "HTTP_" + key
        if env_key in environ:
            environ[env_key] += ", " + value
        else:
            environ[env_key] = value

    return environ


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

# Common HTTP reason phrases (RFC 7231).
_REASON = {
    200: "OK",
    201: "Created",
    202: "Accepted",
    204: "No Content",
    301: "Moved Permanently",
    302: "Found",
    304: "Not Modified",
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    409: "Conflict",
    413: "Content Too Large",
    415: "Unsupported Media Type",
    422: "Unprocessable Content",
    429: "Too Many Requests",
    500: "Internal Server Error",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
}


def _status_line(status_code: int) -> str:
    reason = _REASON.get(status_code, "")
    return f"HTTP/1.1 {status_code} {reason}"


def _format_chunked_header(status_code: int, headers: list[tuple[str, str]]) -> bytes:
    """Build the raw HTTP header block for a chunked response."""
    lines = [_status_line(status_code)]
    has_te = False
    for name, value in headers:
        lines.append(f"{name}: {value}")
        if name.lower() == "transfer-encoding":
            has_te = True
    if not has_te:
        lines.append("Transfer-Encoding: chunked")
    return ("\r\n".join(lines) + "\r\n\r\n").encode()


# ---------------------------------------------------------------------------
# WSGIServer
# ---------------------------------------------------------------------------


class WSGIServer:
    """WSGI server powered by cymongoose's C event loop.

    Parameters
    ----------
    app : callable
        A PEP 3333 WSGI application.
    workers : int
        Maximum number of threads for handling concurrent WSGI requests.
        Defaults to 4.
    error_handler : callable, optional
        Called with an ``Exception`` when the event loop handler itself
        fails (not WSGI app errors, which are caught separately).
    stream_timeout : float
        Seconds a streaming worker will wait on a full queue before
        aborting.  Lower values free worker threads faster when clients
        disconnect mid-stream, but risk aborting legitimate slow
        connections.  Defaults to 5.0.
    """

    def __init__(
        self,
        app: WSGIApp,
        workers: int = 4,
        error_handler: Callable[[Exception], None] | None = None,
        stream_timeout: float = _STREAM_PUT_TIMEOUT,
    ) -> None:
        self._app = app
        self._workers = workers
        self._stream_timeout = stream_timeout
        self._pool = ThreadPoolExecutor(max_workers=workers)
        self._manager = Manager(
            self._event_handler, enable_wakeup=True, error_handler=error_handler
        )
        self._server_name = "127.0.0.1"
        self._server_port = 0
        self._shutdown = False

        # Stash for buffered responses that exceed _WAKEUP_MAX_BYTES.
        self._stash: dict[str, bytes] = {}
        self._stash_lock = threading.Lock()
        # Track which stash keys belong to which connection, so they
        # can be purged if the connection closes before delivery.
        self._stash_keys: dict[int, set[str]] = {}

        # Per-connection stream queues for chunked responses.
        # Key: conn_id, Value: Queue of (bytes | None).
        # None is the sentinel that signals end-of-stream.
        self._streams: dict[int, queue.Queue[bytes | None]] = {}

    @property
    def manager(self) -> Manager:
        """The underlying cymongoose Manager."""
        return self._manager

    def listen(self, url: str = "http://127.0.0.1:8000") -> Connection:
        """Start listening on the given URL."""
        parsed = urlparse(url)
        self._server_name = parsed.hostname or "127.0.0.1"
        conn = self._manager.listen(url)
        addr = conn.local_addr
        if addr is not None:
            self._server_port = addr[1]
        if self._server_name in ("0.0.0.0", "::"):
            self._server_name = "127.0.0.1"
        return conn

    def run(self, poll_ms: int = 100) -> None:
        """Run the server event loop until interrupted."""

        def on_signal(sig: int, frame: FrameType | None) -> None:
            self._shutdown = True

        signal.signal(signal.SIGINT, on_signal)
        signal.signal(signal.SIGTERM, on_signal)

        try:
            while not self._shutdown:
                self._manager.poll(poll_ms)
        finally:
            self.close()

    def close(self) -> None:
        """Shut down the server and release resources."""
        self._pool.shutdown(wait=False)
        self._manager.close()

    # -- Event handling -------------------------------------------------------

    def _event_handler(self, conn: Connection, event: int, data: Any) -> None:
        if event == MG_EV_HTTP_MSG:
            self._on_http_msg(conn, data)
        elif event == MG_EV_WAKEUP:
            self._on_wakeup(conn, data)
        elif event == MG_EV_CLOSE:
            # Clean up any stream queue for this connection.  The queue
            # and its contents are garbage-collected; the worker will
            # get a broken-pipe or silently finish.
            self._streams.pop(conn.id, None)
            # Purge any stash entries that were never delivered.
            keys = self._stash_keys.pop(conn.id, None)
            if keys:
                with self._stash_lock:
                    for key in keys:
                        self._stash.pop(key, None)

    def _on_http_msg(self, conn: Connection, hm: HttpMessage) -> None:
        environ = _build_environ(hm, conn, self._server_name, self._server_port)
        conn_id = conn.id
        self._pool.submit(self._worker, environ, conn_id)

    def _pop_stash(self, conn_id: int, key: str) -> bytes:
        """Pop a stash entry and remove it from the connection's key set."""
        with self._stash_lock:
            payload = self._stash.pop(key, b"")
        keys = self._stash_keys.get(conn_id)
        if keys is not None:
            keys.discard(key)
        return payload

    def _on_wakeup(self, conn: Connection, data: bytes | str) -> None:
        raw = data if isinstance(data, bytes) else data.encode()
        prefix = raw[0:1]
        body = raw[1:]

        if prefix == _INLINE:
            self._send_buffered_response(conn, body)
        elif prefix == _STASH:
            payload = self._pop_stash(conn.id, body.decode())
            self._send_buffered_response(conn, payload)
        elif prefix == _STREAM_HDR_INLINE:
            conn.send(body)
        elif prefix == _STREAM_HDR_STASH:
            hdr_bytes = self._pop_stash(conn.id, body.decode())
            if hdr_bytes:
                conn.send(hdr_bytes)
        elif prefix == _DRAIN:
            self._drain_stream(conn)

    def _send_buffered_response(self, conn: Connection, payload: bytes) -> None:
        if not payload:
            conn.reply(500, b"Internal Server Error")
            return
        newline = payload.index(b"\n")
        meta = json.loads(payload[:newline])
        body = payload[newline + 1 :]
        status_code: int = meta["s"]
        headers: list[list[str]] = meta["h"]

        # Build the raw HTTP response to preserve duplicate headers
        # (e.g. multiple Set-Cookie).  conn.reply() converts headers
        # to a dict which collapses duplicates.
        lines = [_status_line(status_code)]
        has_ct = False
        has_cl = False
        for name, value in headers:
            lower = name.lower()
            if lower == "content-type":
                has_ct = True
            elif lower == "content-length":
                has_cl = True
            lines.append(f"{name}: {value}")
        if not has_ct:
            lines.append("Content-Type: text/plain")
        if not has_cl:
            lines.append(f"Content-Length: {len(body)}")
        raw_header = ("\r\n".join(lines) + "\r\n\r\n").encode()
        conn.send(raw_header + body)

    def _drain_stream(self, conn: Connection) -> None:
        """Drain all available chunks from this connection's stream queue."""
        q = self._streams.get(conn.id)
        if q is None:
            return

        while True:
            try:
                chunk = q.get_nowait()
            except queue.Empty:
                break

            if chunk is None:
                # End-of-stream sentinel.
                conn.http_chunk(b"")
                self._streams.pop(conn.id, None)
                return

            conn.http_chunk(chunk)

    # -- Worker (runs in thread pool) -----------------------------------------

    def _worker(self, environ: dict[str, Any], conn_id: int) -> None:
        """Execute the WSGI app -- buffered or streaming."""
        status_code = 500
        response_headers: list[tuple[str, str]] = []
        headers_set = False
        write_parts: list[bytes] = []

        def write(data: bytes) -> None:
            """PEP 3333 write() callable (legacy interface)."""
            if not headers_set:
                raise AssertionError("write() called before start_response()")
            write_parts.append(data if isinstance(data, bytes) else data.encode())

        def start_response(
            status: str,
            headers: list[tuple[str, str]],
            exc_info: (
                tuple[type[BaseException], BaseException, TracebackType | None] | None
            ) = None,
        ) -> Callable[[bytes], None]:
            nonlocal status_code, response_headers, headers_set
            if exc_info:
                try:
                    if headers_set:
                        raise exc_info[1].with_traceback(exc_info[2])
                finally:
                    exc_info = None
            status_code = int(status.split(" ", 1)[0])
            response_headers = list(headers)
            headers_set = True
            return write

        try:
            result = self._app(environ, start_response)
        except Exception:
            traceback.print_exc()
            self._worker_send_buffered(
                conn_id, 500, [("Content-Type", "text/plain")], b"Internal Server Error"
            )
            return

        try:
            # Chain write() output before the iterator (PEP 3333).
            it = itertools.chain(write_parts, result)
            self._worker_iterate(iter(it), conn_id, status_code, response_headers)
        except Exception:
            traceback.print_exc()
            # If we've already started streaming, the connection is in a
            # bad state.  Best we can do is end the chunked response.
            if conn_id in self._streams:
                self._streams[conn_id].put(None)
                self._wakeup_drain(conn_id)
            else:
                self._worker_send_buffered(
                    conn_id,
                    500,
                    [("Content-Type", "text/plain")],
                    b"Internal Server Error",
                )
        finally:
            if hasattr(result, "close"):
                result.close()

    def _worker_iterate(
        self,
        it: Any,
        conn_id: int,
        status_code: int,
        headers: list[tuple[str, str]],
    ) -> None:
        """Iterate the WSGI response, switching to streaming if body > 1 MB."""
        body_parts: list[bytes] = []
        body_len = 0

        for chunk in it:
            if not chunk:
                continue
            part = chunk if isinstance(chunk, bytes) else chunk.encode()
            body_parts.append(part)
            body_len += len(part)

            if body_len >= _STREAM_THRESHOLD:
                # -- Switch to streaming --
                self._worker_stream(it, conn_id, status_code, headers, body_parts)
                return

        # Body stayed under threshold -- send as buffered reply.
        body = b"".join(body_parts)
        self._worker_send_buffered(conn_id, status_code, headers, body)

    def _worker_stream(
        self,
        it: Any,
        conn_id: int,
        status_code: int,
        headers: list[tuple[str, str]],
        initial_parts: list[bytes],
    ) -> None:
        """Stream the response using chunked transfer encoding.

        Called after the buffered body exceeded ``_STREAM_THRESHOLD``.
        *initial_parts* contains the chunks already buffered.
        *it* is the iterator positioned after those chunks.
        """
        q: queue.Queue[bytes | None] = queue.Queue(maxsize=_STREAM_QUEUE_SIZE)
        self._streams[conn_id] = q

        # Send the raw HTTP headers via wakeup (needs conn.send, not
        # conn.http_chunk, so it goes through the H/h prefix path
        # rather than the drain queue).
        hdr_bytes = _format_chunked_header(status_code, headers)
        if not self._wakeup_stream_header(conn_id, hdr_bytes):
            self._streams.pop(conn_id, None)
            return

        # Flush already-buffered body parts as the first chunk.
        buffered = b"".join(initial_parts)
        initial_parts.clear()
        if not self._stream_put(q, conn_id, buffered):
            return

        # Continue iterating, batching small chunks.
        batch: list[bytes] = []
        batch_len = 0

        for chunk in it:
            if not chunk:
                continue
            part = chunk if isinstance(chunk, bytes) else chunk.encode()
            batch.append(part)
            batch_len += len(part)

            if batch_len >= _STREAM_BATCH_SIZE:
                if not self._stream_put(q, conn_id, b"".join(batch)):
                    return
                batch.clear()
                batch_len = 0

        # Flush remaining batch.
        if batch:
            if not self._stream_put(q, conn_id, b"".join(batch)):
                return

        # End-of-stream sentinel.
        self._stream_put(q, conn_id, None)

    def _stream_put(
        self,
        q: queue.Queue[bytes | None],
        conn_id: int,
        data: bytes | None,
    ) -> bool:
        """Put a chunk (or None sentinel) into the stream queue.

        Blocks up to ``stream_timeout`` seconds if the queue is full.
        Returns False if the put timed out (connection likely closed
        and the queue is no longer being drained).
        """
        try:
            q.put(data, timeout=self._stream_timeout)
        except queue.Full:
            # Queue not being drained -- connection probably closed.
            self._streams.pop(conn_id, None)
            return False
        self._wakeup_drain(conn_id)
        return True

    def _wakeup_stream_header(self, conn_id: int, hdr_bytes: bytes) -> bool:
        """Send raw HTTP headers via wakeup, using stash if too large."""
        if len(hdr_bytes) + 1 <= _WAKEUP_MAX_BYTES:
            msg = _STREAM_HDR_INLINE + hdr_bytes
        else:
            key = uuid.uuid4().hex
            with self._stash_lock:
                self._stash[key] = hdr_bytes
            self._stash_keys.setdefault(conn_id, set()).add(key)
            msg = _STREAM_HDR_STASH + key.encode()

        try:
            self._manager.wakeup(conn_id, msg)
            return True
        except RuntimeError:
            if msg[0:1] == _STREAM_HDR_STASH:
                with self._stash_lock:
                    self._stash.pop(key, None)
                keys = self._stash_keys.get(conn_id)
                if keys is not None:
                    keys.discard(key)
            return False

    # -- Wakeup helpers -------------------------------------------------------

    def _worker_send_buffered(
        self,
        conn_id: int,
        status_code: int,
        headers: list[tuple[str, str]],
        body: bytes,
    ) -> None:
        """Send a complete response via the buffered path."""
        meta = json.dumps({"s": status_code, "h": headers}).encode()
        payload = meta + b"\n" + body

        if len(payload) <= _WAKEUP_MAX_BYTES:
            msg = _INLINE + payload
        else:
            key = uuid.uuid4().hex
            with self._stash_lock:
                self._stash[key] = payload
            self._stash_keys.setdefault(conn_id, set()).add(key)
            msg = _STASH + key.encode()

        try:
            self._manager.wakeup(conn_id, msg)
        except RuntimeError:
            if msg[0:1] == _STASH:
                with self._stash_lock:
                    self._stash.pop(key, None)
                keys = self._stash_keys.get(conn_id)
                if keys is not None:
                    keys.discard(key)

    def _wakeup_drain(self, conn_id: int) -> None:
        """Send a tiny drain notification via wakeup."""
        try:
            self._manager.wakeup(conn_id, _DRAIN)
        except RuntimeError:
            pass


def serve(
    app: WSGIApp,
    url: str = "http://127.0.0.1:8000",
    workers: int = 4,
    stream_timeout: float = _STREAM_PUT_TIMEOUT,
) -> None:
    """One-liner to serve a WSGI application.

    Parameters
    ----------
    app : callable
        A PEP 3333 WSGI application.
    url : str
        Listen URL.
    workers : int
        Thread pool size for concurrent request handling.
    stream_timeout : float
        Seconds a streaming worker waits on a full queue before
        aborting.  Defaults to 5.0.
    """
    server = WSGIServer(app, workers=workers, stream_timeout=stream_timeout)
    conn = server.listen(url)
    addr = conn.local_addr
    port = addr[1] if addr is not None else 0
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    print(f"cymongoose WSGI server on http://{host}:{port}/")
    print(f"  Workers: {workers}")
    print("  Press Ctrl+C to stop")
    server.run()
