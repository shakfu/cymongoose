"""ASGI server adapter for cymongoose.

Run any ASGI application (FastAPI, Starlette, Django async, Quart) on
cymongoose's C event loop::

    from cymongoose.asgi import serve
    serve("myapp:app", "http://127.0.0.1:8000")

Or with more control::

    from cymongoose.asgi import ASGIServer
    import asyncio

    async def main():
        server = ASGIServer(app)
        await server.start("http://127.0.0.1:8000")
        try:
            await asyncio.Event().wait()
        finally:
            await server.stop()

    asyncio.run(main())

Architecture
------------
The ASGI adapter bridges cymongoose's C event loop (running in a
background thread via ``AsyncManager``) with the asyncio event loop:

- **Mongoose thread** receives HTTP/WS events and pushes ASGI
  ``receive`` messages into per-connection ``asyncio.Queue`` instances
  via ``loop.call_soon_threadsafe``.
- **Asyncio thread** runs the ASGI application coroutines.  ``send()``
  calls are routed back to the mongoose thread via ``Manager.wakeup()``
  (using the stash for payloads > 8 KB).
- Supports HTTP and WebSocket sub-protocols.  Lifespan is handled
  via startup/shutdown hooks.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import signal
import threading
import traceback
import uuid
from typing import Any, Callable
from urllib.parse import unquote, urlparse

from . import (
    MG_EV_CLOSE,
    MG_EV_HTTP_MSG,
    MG_EV_WAKEUP,
    MG_EV_WS_MSG,
    MG_EV_WS_OPEN,
    WEBSOCKET_OP_BINARY,
    WEBSOCKET_OP_TEXT,
    Connection,
    HttpMessage,
    Manager,
    WsMessage,
)

# Type alias for an ASGI application callable.
ASGIApp = Callable[..., Any]

# ---------------------------------------------------------------------------
# Constants (shared with WSGI adapter)
# ---------------------------------------------------------------------------

_WAKEUP_MAX_BYTES = 8 * 1024  # 8 KB
_STREAM_CONCURRENCY = 16  # max in-flight streaming wakeups per connection

# Wakeup message types.
_RESP = b"R"  # HTTP response (inline): R<json>
_RESP_STASH = b"r"  # HTTP response (stash): r<uuid>
_WS_SEND = b"W"  # WebSocket send (inline): W<json>
_WS_SEND_STASH = b"w"  # WebSocket send (stash): w<uuid>
_WS_CLOSE = b"X"  # WebSocket close
_STREAM_HDR = b"S"  # Chunked stream: headers (inline): S<raw_headers>
_STREAM_HDR_STASH = b"s"  # Chunked stream: headers (stash): s<uuid>
_STREAM_CHUNK = b"C"  # Chunked stream: body chunk (inline): C<data>
_STREAM_CHUNK_STASH = b"c"  # Chunked stream: body chunk (stash): c<uuid>
_STREAM_END = b"E"  # Chunked stream: end (no payload)


# ---------------------------------------------------------------------------
# Scope builders
# ---------------------------------------------------------------------------


def _build_http_scope(
    hm: HttpMessage, conn: Connection, server_name: str, server_port: int
) -> dict[str, Any]:
    """Build an ASGI HTTP connection scope from an HttpMessage."""
    uri = hm.uri or "/"
    if "?" in uri:
        path, query_string = uri.split("?", 1)
    else:
        path = uri
        query_string = hm.query or ""

    # ASGI headers: list of [name, value] as byte pairs
    headers: list[list[bytes]] = []
    for name, value in hm.headers():
        headers.append([name.lower().encode(), value.encode()])

    remote = conn.remote_addr
    client = [remote[0], remote[1]] if remote else ["127.0.0.1", 0]

    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": (hm.proto or "HTTP/1.1").split("/", 1)[-1],
        "method": hm.method,
        "path": unquote(path),
        "raw_path": path.encode(),
        "query_string": query_string.encode(),
        "root_path": "",
        "scheme": "https" if conn.is_tls else "http",
        "server": [server_name, server_port],
        "client": client,
        "headers": headers,
    }


def _build_ws_scope(
    hm: HttpMessage, conn: Connection, server_name: str, server_port: int
) -> dict[str, Any]:
    """Build an ASGI WebSocket connection scope from the upgrade request."""
    uri = hm.uri or "/"
    if "?" in uri:
        path, query_string = uri.split("?", 1)
    else:
        path = uri
        query_string = hm.query or ""

    headers: list[list[bytes]] = []
    for name, value in hm.headers():
        headers.append([name.lower().encode(), value.encode()])

    remote = conn.remote_addr
    client = [remote[0], remote[1]] if remote else ["127.0.0.1", 0]

    return {
        "type": "websocket",
        "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": (hm.proto or "HTTP/1.1").split("/", 1)[-1],
        "scheme": "wss" if conn.is_tls else "ws",
        "path": unquote(path),
        "raw_path": path.encode(),
        "query_string": query_string.encode(),
        "root_path": "",
        "server": [server_name, server_port],
        "client": client,
        "headers": headers,
    }


# ---------------------------------------------------------------------------
# Per-connection state
# ---------------------------------------------------------------------------


class _ConnState:
    """Tracks ASGI state for a single connection."""

    __slots__ = (
        "scope",
        "receive_queue",
        "task",
        "ws_accepted",
        "response_started",
        "streaming",
        "stream_sem",
    )

    def __init__(self, scope: dict[str, Any]) -> None:
        self.scope = scope
        self.receive_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.task: concurrent.futures.Future[None] | None = None
        self.ws_accepted = False
        self.response_started = False
        self.streaming = False
        # Created lazily on first streaming body; limits in-flight wakeups.
        self.stream_sem: asyncio.Semaphore | None = None


# ---------------------------------------------------------------------------
# ASGIServer
# ---------------------------------------------------------------------------


class ASGIServer:
    """ASGI server powered by cymongoose's C event loop.

    Parameters
    ----------
    app : callable
        An ASGI 3.0 application.
    error_handler : callable, optional
        Called on event-loop-level errors (not app errors).
    """

    def __init__(
        self,
        app: ASGIApp,
        error_handler: Callable[[Exception], None] | None = None,
    ) -> None:
        self._app = app
        self._error_handler = error_handler
        self._manager: Manager | None = None
        self._poll_thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None

        self._server_name = "127.0.0.1"
        self._server_port = 0

        # Per-connection ASGI state, keyed by conn.id.
        self._conns: dict[int, _ConnState] = {}

        # Stash for wakeup payloads > 8 KB.
        self._stash: dict[str, bytes] = {}
        self._stash_lock = threading.Lock()

        # Lifespan state.
        self._lifespan_receive: asyncio.Queue[dict[str, Any]] | None = None
        self._lifespan_startup_complete: asyncio.Event | None = None
        self._lifespan_startup_failed = False
        self._lifespan_failure_message: str = ""
        self._lifespan_shutdown_complete: asyncio.Event | None = None
        self._lifespan_task: asyncio.Task[None] | None = None
        self._lifespan_supported = True

    @property
    def manager(self) -> Manager:
        if self._manager is None:
            raise RuntimeError("ASGIServer is not started")
        return self._manager

    async def start(self, url: str = "http://127.0.0.1:8000") -> Connection:
        """Start the server.  Must be called from an async context."""
        self._loop = asyncio.get_running_loop()

        # Run lifespan startup before binding.
        await self._lifespan_startup()
        if self._lifespan_startup_failed:
            raise RuntimeError(
                f"ASGI lifespan startup failed: {self._lifespan_failure_message}"
            )

        self._manager = Manager(
            self._event_handler,
            enable_wakeup=True,
            error_handler=self._error_handler,
        )

        parsed = urlparse(url)
        self._server_name = parsed.hostname or "127.0.0.1"
        conn = self._manager.listen(url)
        addr = conn.local_addr
        if addr is not None:
            self._server_port = addr[1]
        if self._server_name in ("0.0.0.0", "::"):
            self._server_name = "127.0.0.1"

        self._stop.clear()
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()
        return conn

    async def stop(self) -> None:
        """Stop the server gracefully."""
        self._stop.set()
        if self._poll_thread is not None:
            self._poll_thread.join(timeout=5)
            self._poll_thread = None
        # Cancel all running ASGI tasks.
        for state in self._conns.values():
            if state.task is not None and not state.task.done():
                state.task.cancel()
        self._conns.clear()
        if self._manager is not None:
            self._manager.close()
            self._manager = None

        # Run lifespan shutdown after connections are closed.
        await self._lifespan_shutdown()

        self._loop = None

    # -- Lifespan protocol ------------------------------------------------------

    async def _lifespan_startup(self) -> None:
        """Run the ASGI lifespan startup sequence.

        If the app doesn't support lifespan (raises an exception on the
        lifespan scope), we silently proceed without it.
        """
        self._lifespan_receive = asyncio.Queue()
        self._lifespan_startup_complete = asyncio.Event()
        self._lifespan_shutdown_complete = asyncio.Event()

        scope: dict[str, Any] = {
            "type": "lifespan",
            "asgi": {"version": "3.0", "spec_version": "2.0"},
        }

        async def lifespan_send(message: dict[str, Any]) -> None:
            msg_type = message["type"]
            if msg_type == "lifespan.startup.complete":
                self._lifespan_startup_complete.set()
            elif msg_type == "lifespan.startup.failed":
                self._lifespan_startup_failed = True
                self._lifespan_failure_message = message.get("message", "")
                self._lifespan_startup_complete.set()  # unblock waiter
            elif msg_type == "lifespan.shutdown.complete":
                self._lifespan_shutdown_complete.set()
            elif msg_type == "lifespan.shutdown.failed":
                self._lifespan_shutdown_complete.set()  # unblock waiter

        async def lifespan_coro() -> None:
            try:
                await self._app(scope, self._lifespan_receive.get, lifespan_send)
            except Exception:
                # App doesn't support lifespan -- that's fine.
                self._lifespan_supported = False
            finally:
                # If the app returned or raised without signaling
                # startup.complete (e.g. it ignores the lifespan scope
                # entirely), treat as "no lifespan support".
                if not self._lifespan_startup_complete.is_set():
                    self._lifespan_supported = False
                self._lifespan_startup_complete.set()
                self._lifespan_shutdown_complete.set()

        self._lifespan_task = asyncio.ensure_future(lifespan_coro())

        # Push the startup event and wait for the app to respond.
        await self._lifespan_receive.put({"type": "lifespan.startup"})
        await self._lifespan_startup_complete.wait()

    async def _lifespan_shutdown(self) -> None:
        """Run the ASGI lifespan shutdown sequence."""
        if not self._lifespan_supported or self._lifespan_receive is None:
            return
        if self._lifespan_shutdown_complete is None:
            return

        await self._lifespan_receive.put({"type": "lifespan.shutdown"})
        try:
            await asyncio.wait_for(self._lifespan_shutdown_complete.wait(), timeout=5)
        except asyncio.TimeoutError:
            pass

        # Clean up the lifespan task.
        if self._lifespan_task is not None and not self._lifespan_task.done():
            self._lifespan_task.cancel()
            try:
                await self._lifespan_task
            except (asyncio.CancelledError, Exception):
                pass

    def _poll_loop(self) -> None:
        """Background thread: run mongoose poll loop."""
        while not self._stop.is_set():
            if self._manager is not None:
                self._manager.poll(100)

    # -- Mongoose event handler (runs in poll thread) -------------------------

    def _event_handler(self, conn: Connection, event: int, data: Any) -> None:
        if event == MG_EV_HTTP_MSG:
            self._on_http(conn, data)
        elif event == MG_EV_WS_OPEN:
            self._on_ws_open(conn, data)
        elif event == MG_EV_WS_MSG:
            self._on_ws_msg(conn, data)
        elif event == MG_EV_WAKEUP:
            self._on_wakeup(conn, data)
        elif event == MG_EV_CLOSE:
            self._on_close(conn)

    def _on_http(self, conn: Connection, hm: HttpMessage) -> None:
        """Handle MG_EV_HTTP_MSG: either HTTP request or WS upgrade."""
        # Check if this is a WebSocket upgrade request.
        upgrade = hm.header("Upgrade")
        if upgrade and upgrade.lower() == "websocket":
            # Complete the WebSocket upgrade immediately -- the
            # HttpMessage view is invalidated after this handler
            # returns, so we cannot defer ws_upgrade() to a wakeup.
            scope = _build_ws_scope(hm, conn, self._server_name, self._server_port)
            conn.ws_upgrade(hm)
            state = _ConnState(scope)
            self._conns[conn.id] = state
            # Push the websocket.connect event.
            self._schedule_put(conn.id, {"type": "websocket.connect"})
            # Start the ASGI app coroutine.
            self._start_asgi_task(conn.id, state)
            return

        # Regular HTTP request.
        scope = _build_http_scope(hm, conn, self._server_name, self._server_port)
        state = _ConnState(scope)
        self._conns[conn.id] = state

        # Push the http.request event with the full body.
        body = hm.body_bytes or b""
        self._schedule_put(
            conn.id,
            {"type": "http.request", "body": body, "more_body": False},
        )
        self._start_asgi_task(conn.id, state)

    def _on_ws_open(self, conn: Connection, hm: HttpMessage) -> None:
        """Handle MG_EV_WS_OPEN: WebSocket handshake completed."""
        state = self._conns.get(conn.id)
        if state is not None:
            state.ws_accepted = True

    def _on_ws_msg(self, conn: Connection, data: WsMessage) -> None:
        """Handle MG_EV_WS_MSG: incoming WebSocket frame."""
        state = self._conns.get(conn.id)
        if state is None:
            return

        flags = data.flags
        if flags & WEBSOCKET_OP_BINARY:
            msg: dict[str, Any] = {
                "type": "websocket.receive",
                "bytes": bytes(data.data),
            }
        else:
            msg = {
                "type": "websocket.receive",
                "text": data.text,
            }
        self._schedule_put(conn.id, msg)

    def _on_close(self, conn: Connection) -> None:
        """Handle MG_EV_CLOSE: connection closed."""
        state = self._conns.pop(conn.id, None)
        if state is None:
            return

        if state.scope["type"] == "websocket":
            self._schedule_put_orphan(state, {"type": "websocket.disconnect", "code": 1000})
        else:
            self._schedule_put_orphan(state, {"type": "http.disconnect"})

    # -- Wakeup dispatch (runs in poll thread) --------------------------------

    def _on_wakeup(self, conn: Connection, data: bytes | str) -> None:
        raw = data if isinstance(data, bytes) else data.encode()
        prefix = raw[0:1]
        body = raw[1:]

        if prefix == _RESP or prefix == _RESP_STASH:
            self._handle_http_response(conn, prefix, body)
        elif prefix == _STREAM_HDR or prefix == _STREAM_HDR_STASH:
            self._handle_stream_header(conn, prefix, body)
        elif prefix == _STREAM_CHUNK or prefix == _STREAM_CHUNK_STASH:
            self._handle_stream_chunk(conn, prefix, body)
        elif prefix == _STREAM_END:
            conn.http_chunk(b"")
        elif prefix == _WS_SEND or prefix == _WS_SEND_STASH:
            self._handle_ws_send(conn, prefix, body)
        elif prefix == _WS_CLOSE:
            conn.close()

    def _handle_http_response(self, conn: Connection, prefix: bytes, body: bytes) -> None:
        """Send a buffered HTTP response."""
        if prefix == _RESP_STASH:
            key = body.decode()
            with self._stash_lock:
                payload = self._stash.pop(key, b"")
        else:
            payload = body

        if not payload:
            conn.reply(500, b"Internal Server Error")
            return

        meta = json.loads(payload)
        status: int = meta["status"]
        headers_raw: list[list[str]] = meta["headers"]
        resp_body: str = meta.get("body", "")
        body_bytes = resp_body.encode("latin-1") if resp_body else b""

        # Build raw HTTP response (preserves duplicate headers).
        from .wsgi import _status_line

        lines = [_status_line(status)]
        has_ct = False
        has_cl = False
        for name, value in headers_raw:
            lower = name.lower()
            if lower == "content-type":
                has_ct = True
            elif lower == "content-length":
                has_cl = True
            lines.append(f"{name}: {value}")
        if not has_ct:
            lines.append("Content-Type: text/plain")
        if not has_cl:
            lines.append(f"Content-Length: {len(body_bytes)}")
        raw_header = ("\r\n".join(lines) + "\r\n\r\n").encode()
        conn.send(raw_header + body_bytes)

    def _handle_stream_header(self, conn: Connection, prefix: bytes, body: bytes) -> None:
        """Send chunked stream HTTP headers."""
        if prefix == _STREAM_HDR_STASH:
            key = body.decode()
            with self._stash_lock:
                raw = self._stash.pop(key, b"")
        else:
            raw = body
        if raw:
            conn.send(raw)
        self._release_stream_sem(conn.id)

    def _handle_stream_chunk(self, conn: Connection, prefix: bytes, body: bytes) -> None:
        """Send a single chunked body chunk."""
        if prefix == _STREAM_CHUNK_STASH:
            key = body.decode()
            with self._stash_lock:
                chunk_data = self._stash.pop(key, b"")
        else:
            chunk_data = body
        if chunk_data:
            conn.http_chunk(chunk_data)
        self._release_stream_sem(conn.id)

    def _handle_ws_send(self, conn: Connection, prefix: bytes, body: bytes) -> None:
        """Send a WebSocket frame."""
        if prefix == _WS_SEND_STASH:
            key = body.decode()
            with self._stash_lock:
                payload = self._stash.pop(key, b"")
        else:
            payload = body

        meta = json.loads(payload)
        if "text" in meta:
            conn.ws_send(meta["text"], WEBSOCKET_OP_TEXT)
        elif "bytes" in meta:
            frame_bytes = meta["bytes"].encode("latin-1")
            conn.ws_send(frame_bytes, WEBSOCKET_OP_BINARY)

    def _release_stream_sem(self, conn_id: int) -> None:
        """Release one streaming permit after the poll thread processes a wakeup."""
        if self._loop is None:
            return
        state = self._conns.get(conn_id)
        if state is None or state.stream_sem is None:
            return
        self._loop.call_soon_threadsafe(state.stream_sem.release)

    # -- Asyncio helpers (called from poll thread) ----------------------------

    def _schedule_put(self, conn_id: int, msg: dict[str, Any]) -> None:
        """Thread-safe: push an ASGI receive message onto the connection queue."""
        if self._loop is None:
            return
        state = self._conns.get(conn_id)
        if state is None:
            return
        self._loop.call_soon_threadsafe(state.receive_queue.put_nowait, msg)

    def _schedule_put_orphan(self, state: _ConnState, msg: dict[str, Any]) -> None:
        """Push a message even after the conn has been removed from _conns."""
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(state.receive_queue.put_nowait, msg)

    def _start_asgi_task(self, conn_id: int, state: _ConnState) -> None:
        """Schedule the ASGI application coroutine on the asyncio loop."""
        if self._loop is None:
            return

        async def run() -> None:
            try:
                await self._app(
                    state.scope,
                    state.receive_queue.get,
                    self._make_send(conn_id, state),
                )
            except Exception:
                traceback.print_exc()
                # If HTTP and no response sent yet, send 500.
                if state.scope["type"] == "http" and not state.response_started:
                    self._send_error_response(conn_id)

        state.task = asyncio.run_coroutine_threadsafe(run(), self._loop)

    # -- ASGI send() callable -------------------------------------------------

    def _make_send(self, conn_id: int, state: _ConnState) -> Callable[[dict[str, Any]], Any]:
        """Create the ASGI send() callable for a connection."""

        # Accumulate response.start until response.body arrives.
        pending_start: dict[str, Any] = {}

        async def send(message: dict[str, Any]) -> None:
            msg_type = message["type"]

            if msg_type == "http.response.start":
                state.response_started = True
                pending_start.update(message)

            elif msg_type == "http.response.body":
                body = message.get("body", b"")
                more_body = message.get("more_body", False)

                if state.streaming:
                    # Already in chunked streaming mode -- send chunk.
                    if body:
                        await state.stream_sem.acquire()
                        self._wakeup_with_stash(
                            conn_id, _STREAM_CHUNK, _STREAM_CHUNK_STASH, body
                        )
                    if not more_body:
                        self._wakeup_small(conn_id, _STREAM_END)
                        state.streaming = False
                elif more_body:
                    # First body message with more_body=True: start
                    # chunked streaming.  Send headers with
                    # Transfer-Encoding: chunked, then the first chunk.
                    state.streaming = True
                    state.stream_sem = asyncio.Semaphore(_STREAM_CONCURRENCY)
                    status = pending_start.get("status", 200)
                    headers = pending_start.get("headers", [])
                    str_headers: list[tuple[str, str]] = []
                    for h in headers:
                        name = h[0].decode() if isinstance(h[0], bytes) else h[0]
                        value = h[1].decode() if isinstance(h[1], bytes) else h[1]
                        str_headers.append((name, value))

                    from .wsgi import _format_chunked_header

                    hdr_bytes = _format_chunked_header(status, str_headers)
                    await state.stream_sem.acquire()
                    self._wakeup_with_stash(
                        conn_id, _STREAM_HDR, _STREAM_HDR_STASH, hdr_bytes
                    )
                    if body:
                        await state.stream_sem.acquire()
                        self._wakeup_with_stash(
                            conn_id, _STREAM_CHUNK, _STREAM_CHUNK_STASH, body
                        )
                else:
                    # Single buffered response (no streaming).
                    status = pending_start.get("status", 200)
                    headers = pending_start.get("headers", [])
                    # Convert ASGI headers (list of [bytes, bytes]) to
                    # list of [str, str] for JSON serialisation.
                    str_headers_json = []
                    for h in headers:
                        name = h[0].decode() if isinstance(h[0], bytes) else h[0]
                        value = h[1].decode() if isinstance(h[1], bytes) else h[1]
                        str_headers_json.append([name, value])

                    meta = {
                        "status": status,
                        "headers": str_headers_json,
                        "body": body.decode("latin-1") if body else "",
                    }
                    payload = json.dumps(meta).encode()
                    self._wakeup_with_stash(conn_id, _RESP, _RESP_STASH, payload)

            elif msg_type == "websocket.accept":
                # Upgrade was already completed in _on_http (while the
                # HttpMessage was still valid).  Nothing to do here.
                pass

            elif msg_type == "websocket.send":
                ws_meta: dict[str, Any] = {}
                if "text" in message:
                    ws_meta["text"] = message["text"]
                elif "bytes" in message:
                    ws_meta["bytes"] = message["bytes"].decode("latin-1")
                payload = json.dumps(ws_meta).encode()
                self._wakeup_with_stash(conn_id, _WS_SEND, _WS_SEND_STASH, payload)

            elif msg_type == "websocket.close":
                self._wakeup_small(conn_id, _WS_CLOSE)

        return send

    # -- Wakeup helpers -------------------------------------------------------

    def _wakeup_small(self, conn_id: int, data: bytes) -> None:
        """Send a small wakeup payload (must fit in socket buffer)."""
        if self._manager is None:
            return
        try:
            self._manager.wakeup(conn_id, data)
        except RuntimeError:
            pass

    def _wakeup_with_stash(
        self,
        conn_id: int,
        inline_prefix: bytes,
        stash_prefix: bytes,
        payload: bytes,
    ) -> None:
        """Send via wakeup, using stash if payload exceeds threshold."""
        if self._manager is None:
            return
        if len(payload) + 1 <= _WAKEUP_MAX_BYTES:
            msg = inline_prefix + payload
        else:
            key = uuid.uuid4().hex
            with self._stash_lock:
                self._stash[key] = payload
            msg = stash_prefix + key.encode()
        try:
            self._manager.wakeup(conn_id, msg)
        except RuntimeError:
            if msg[0:1] == stash_prefix:
                with self._stash_lock:
                    self._stash.pop(key, None)

    def _send_error_response(self, conn_id: int) -> None:
        """Send a 500 response for unhandled app errors."""
        meta = {
            "status": 500,
            "headers": [["content-type", "text/plain"]],
            "body": "Internal Server Error",
        }
        payload = json.dumps(meta).encode()
        self._wakeup_with_stash(conn_id, _RESP, _RESP_STASH, payload)


# ---------------------------------------------------------------------------
# Convenience runner
# ---------------------------------------------------------------------------


async def _serve_async(app: ASGIApp, url: str = "http://127.0.0.1:8000") -> None:
    """Async entry point for serve()."""
    server = ASGIServer(app)
    conn = await server.start(url)
    addr = conn.local_addr
    port = addr[1] if addr is not None else 0
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    print(f"cymongoose ASGI server on http://{host}:{port}/")
    print("  Press Ctrl+C to stop")

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    try:
        await stop_event.wait()
    finally:
        await server.stop()
        print("Server stopped.")


def serve(app: ASGIApp, url: str = "http://127.0.0.1:8000") -> None:
    """One-liner to serve an ASGI application.

    Parameters
    ----------
    app : callable
        An ASGI 3.0 application.
    url : str
        Listen URL.
    """
    asyncio.run(_serve_async(app, url))
