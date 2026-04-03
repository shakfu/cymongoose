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
1. HTTP request arrives via ``MG_EV_HTTP_MSG``.
2. The handler builds a WSGI ``environ`` dict from the ``HttpMessage``
   and submits the WSGI callable to a ``ThreadPoolExecutor``.
3. The worker thread calls the application, collects the response
   status, headers, and body iterator.
4. The worker serialises the result and calls ``Manager.wakeup()``
   to hand it back to the event loop thread.
5. On ``MG_EV_WAKEUP`` the handler sends the HTTP response via
   ``conn.reply()`` (or chunked transfer for streaming bodies).

This keeps the event loop non-blocking while WSGI applications are
free to block in their handlers (database queries, file I/O, etc.).
"""

from __future__ import annotations

import io
import json
import signal
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from types import FrameType, TracebackType
from typing import Any, Callable
from urllib.parse import unquote, urlparse

from . import MG_EV_HTTP_MSG, MG_EV_WAKEUP, Connection, HttpMessage, Manager

# Type alias for a PEP 3333 WSGI application callable.
WSGIApp = Callable[..., Any]


def _build_environ(
    hm: HttpMessage, conn: Connection, server_name: str, server_port: int
) -> dict[str, Any]:
    """Build a PEP 3333 environ dict from an HttpMessage and Connection."""
    uri = hm.uri or "/"

    # Split path from query (uri may contain both)
    if "?" in uri:
        path_info, query_string = uri.split("?", 1)
    else:
        path_info = uri
        query_string = hm.query or ""

    body = hm.body_bytes or b""

    environ: dict[str, Any] = {
        # CGI variables (required by PEP 3333)
        "REQUEST_METHOD": hm.method,
        "SCRIPT_NAME": "",
        "PATH_INFO": unquote(path_info),
        "QUERY_STRING": query_string,
        "SERVER_NAME": server_name,
        "SERVER_PORT": str(server_port),
        "SERVER_PROTOCOL": hm.proto or "HTTP/1.1",
        # WSGI variables
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "https" if conn.is_tls else "http",
        "wsgi.input": io.BytesIO(body),
        "wsgi.errors": sys.stderr,
        "wsgi.multithread": True,
        "wsgi.multiprocess": False,
        "wsgi.run_once": False,
    }

    # Content-Type and Content-Length get special treatment (no HTTP_ prefix)
    content_type = hm.header("Content-Type")
    if content_type is not None:
        environ["CONTENT_TYPE"] = content_type

    content_length = hm.header("Content-Length")
    if content_length is not None:
        environ["CONTENT_LENGTH"] = content_length

    # Remote address
    remote = conn.remote_addr
    if remote:
        environ["REMOTE_ADDR"] = remote[0]
        environ["REMOTE_HOST"] = remote[0]

    # HTTP headers -> HTTP_* variables
    for name, value in hm.headers():
        key = name.upper().replace("-", "_")
        if key in ("CONTENT_TYPE", "CONTENT_LENGTH"):
            continue  # Already handled above
        env_key = "HTTP_" + key
        # PEP 3333: multiple headers with same name joined by ", "
        if env_key in environ:
            environ[env_key] += ", " + value
        else:
            environ[env_key] = value

    return environ


def _call_wsgi_app(
    app: WSGIApp, environ: dict[str, Any]
) -> tuple[int, list[tuple[str, str]], bytes]:
    """Call the WSGI application in a worker thread.

    Returns a tuple of (status_code, headers_list, body_bytes) on success,
    or (500, error_headers, error_body) on failure.
    """
    status_code = 500
    response_headers: list[tuple[str, str]] = []
    body_parts: list[bytes] = []
    headers_set = False

    def start_response(
        status: str,
        headers: list[tuple[str, str]],
        exc_info: tuple[type[BaseException], BaseException, TracebackType | None] | None = None,
    ) -> None:
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

    try:
        result = app(environ, start_response)
        try:
            for chunk in result:
                if chunk:
                    body_parts.append(chunk if isinstance(chunk, bytes) else chunk.encode())
        finally:
            if hasattr(result, "close"):
                result.close()
    except Exception:
        # Application raised -- return a 500
        tb = traceback.format_exc()
        sys.stderr.write(tb)
        status_code = 500
        response_headers = [("Content-Type", "text/plain")]
        body_parts = [b"Internal Server Error"]

    body = b"".join(body_parts)
    return status_code, response_headers, body


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
    """

    def __init__(
        self,
        app: WSGIApp,
        workers: int = 4,
        error_handler: Callable[[Exception], None] | None = None,
    ) -> None:
        self._app = app
        self._workers = workers
        self._pool = ThreadPoolExecutor(max_workers=workers)
        self._manager = Manager(
            self._event_handler, enable_wakeup=True, error_handler=error_handler
        )
        self._server_name = "127.0.0.1"
        self._server_port = 0
        self._shutdown = False

    @property
    def manager(self) -> Manager:
        """The underlying cymongoose Manager."""
        return self._manager

    def listen(self, url: str = "http://127.0.0.1:8000") -> Connection:
        """Start listening on the given URL.

        Parameters
        ----------
        url : str
            Listen URL, e.g. ``"http://127.0.0.1:8000"`` or
            ``"https://0.0.0.0:443"``.

        Returns
        -------
        Connection
            The listener connection.
        """
        parsed = urlparse(url)
        self._server_name = parsed.hostname or "127.0.0.1"
        conn = self._manager.listen(url)
        addr = conn.local_addr
        if addr is not None:
            self._server_port = addr[1]
        # Update server_name if we resolved a real address
        if self._server_name in ("0.0.0.0", "::"):
            self._server_name = "127.0.0.1"
        return conn

    def run(self, poll_ms: int = 100) -> None:
        """Run the server event loop until interrupted.

        Installs SIGINT/SIGTERM handlers for graceful shutdown.

        Parameters
        ----------
        poll_ms : int
            Milliseconds between poll cycles.
        """

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

    def _event_handler(self, conn: Connection, event: int, data: Any) -> None:
        """cymongoose event handler."""
        if event == MG_EV_HTTP_MSG:
            self._handle_request(conn, data)
        elif event == MG_EV_WAKEUP:
            self._handle_wakeup(conn, data)

    def _handle_request(self, conn: Connection, hm: HttpMessage) -> None:
        """Dispatch an incoming HTTP request to the thread pool."""
        environ = _build_environ(hm, conn, self._server_name, self._server_port)
        conn_id = conn.id
        mgr = self._manager

        def worker() -> None:
            status_code, headers, body = _call_wsgi_app(self._app, environ)
            # Serialise the response to send via wakeup.
            # Format: JSON metadata line + newline + body bytes.
            meta = json.dumps(
                {
                    "s": status_code,
                    "h": headers,
                }
            ).encode()
            payload = meta + b"\n" + body
            try:
                mgr.wakeup(conn_id, payload)
            except RuntimeError:
                pass  # Connection closed while we were processing

        self._pool.submit(worker)

    def _handle_wakeup(self, conn: Connection, data: bytes | str) -> None:
        """Send the WSGI response back to the client."""
        # Parse the serialised response
        raw = data if isinstance(data, bytes) else data.encode()
        newline = raw.index(b"\n")
        meta = json.loads(raw[:newline])
        body = raw[newline + 1 :]

        status_code: int = meta["s"]
        headers: dict[str, str] = {k: v for k, v in meta["h"]}

        conn.reply(status_code, body, headers=headers)


def serve(app: WSGIApp, url: str = "http://127.0.0.1:8000", workers: int = 4) -> None:
    """One-liner to serve a WSGI application.

    Parameters
    ----------
    app : callable
        A PEP 3333 WSGI application.
    url : str
        Listen URL.
    workers : int
        Thread pool size for concurrent request handling.
    """
    server = WSGIServer(app, workers=workers)
    conn = server.listen(url)
    addr = conn.local_addr
    port = addr[1] if addr is not None else 0
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    print(f"cymongoose WSGI server on http://{host}:{port}/")
    print(f"  Workers: {workers}")
    print("  Press Ctrl+C to stop")
    server.run()
