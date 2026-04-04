# ASGI Adapter Internals

This document covers the internal architecture, design decisions, and
known limitations of the `cymongoose.asgi` module.  For user-facing
documentation see the [ASGI Guide](../guide/asgi.md).

## Architecture Overview

The ASGI adapter bridges cymongoose's C event loop (single-threaded,
running in a background thread) with Python's asyncio event loop:

- **Mongoose thread**: receives HTTP/WS events via `MG_EV_*`, converts
  them to ASGI `receive` messages, and pushes them into per-connection
  `asyncio.Queue` instances via `loop.call_soon_threadsafe`.
- **Asyncio thread**: runs ASGI application coroutines.  `send()` calls
  serialise the response and route it back via `Manager.wakeup()`.

Unlike the WSGI adapter (which uses a `ThreadPoolExecutor`), the ASGI
adapter runs application code directly on the asyncio event loop -- no
thread pool is needed for the application itself.

## Wakeup Message Types

| Prefix | Name | Payload | Description |
|--------|------|---------|-------------|
| `R` | Response inline | `<json>` | HTTP response, payload fits in wakeup buffer |
| `r` | Response stash | `<uuid>` | HTTP response, payload in `_stash` dict |
| `W` | WS send inline | `<json>` | WebSocket frame, payload fits in wakeup buffer |
| `w` | WS send stash | `<uuid>` | WebSocket frame, payload in `_stash` dict |
| `X` | WS close | (empty) | Close WebSocket connection |

Payloads exceeding `_WAKEUP_MAX_BYTES` (8 KB) are stored in a
thread-safe `_stash` dict and only a UUID key is sent via wakeup,
reusing the same pattern as the WSGI adapter.

## Per-Connection State

Each active connection gets a `_ConnState` instance stored in
`_conns[conn.id]`:

- `scope`: the ASGI connection scope dict (HTTP or WebSocket)
- `receive_queue`: `asyncio.Queue` fed by the mongoose thread
- `task`: the `concurrent.futures.Future` running the ASGI app coroutine
- `ws_accepted`: whether the WebSocket handshake completed
- `response_started`: whether `http.response.start` has been received

Cleanup happens in `MG_EV_CLOSE`: the state is popped from `_conns`
and a disconnect message is pushed to the queue so the app coroutine
can exit cleanly.

## WebSocket Upgrade: Eager Completion

cymongoose's `HttpMessage` views are invalidated after the event
handler returns (the `_msg` pointer is set to NULL in
`_event_bridge`).  This means `ws_upgrade(hm)` must be called
inside the `MG_EV_HTTP_MSG` handler -- it cannot be deferred to a
wakeup.

The adapter calls `conn.ws_upgrade(hm)` immediately when it detects
an `Upgrade: websocket` header.  The ASGI application's subsequent
`websocket.accept` message is a no-op on the mongoose side (the
upgrade is already done).

This is a deviation from the ASGI spec's intent (where the server
waits for `websocket.accept` before completing the upgrade), but it
is the only viable approach given cymongoose's message view lifetime.
In practice this has no observable effect -- the app receives
`websocket.connect`, responds with `websocket.accept`, and messaging
proceeds normally.

## Thread Safety

### Queue Access

`asyncio.Queue` is not thread-safe on its own.  The mongoose thread
uses `loop.call_soon_threadsafe(queue.put_nowait, msg)` to push
messages, which schedules the put on the asyncio thread.  The ASGI
app awaits `queue.get()` on the same asyncio thread.  Both operations
run on the asyncio thread, so no lock is needed.

### `_conns` Dict

Like the WSGI adapter's `_streams` dict, `_conns` is accessed from
both threads without an explicit lock.  This relies on CPython's GIL
making dict operations atomic.  See the WSGI internals doc for the
full discussion of this assumption.

### `_stash` Dict

Protected by `_stash_lock`, same pattern as the WSGI adapter.

## Known Limitations

### No Lifespan Sub-Protocol

The ASGI lifespan sub-protocol (startup/shutdown events) is not
implemented.  Applications that need it should handle startup and
shutdown outside the ASGI server.

### No Streaming HTTP Responses

`http.response.body` with `more_body=True` is not supported.  The
adapter buffers the full response and sends it as a single reply.
Chunked streaming (like the WSGI adapter's queue-based approach)
is planned.

### Eager WebSocket Upgrade

As described above, `ws_upgrade()` is called before the ASGI app
sends `websocket.accept`.  An app that inspects the `websocket.connect`
event and decides to reject the connection cannot prevent the upgrade.
The connection is upgraded regardless; a rejection would need to close
it immediately after.

### Response Body Encoding

HTTP response bodies are serialised through JSON using latin-1
encoding (`body.decode("latin-1")`).  This preserves arbitrary byte
values but adds serialisation overhead for large binary responses.

## See Also

- [ASGI Guide](../guide/asgi.md) -- user-facing documentation
- [WSGI Internals](wsgi.md) -- comparison adapter architecture
- [AsyncManager API](../api/async_manager.md) -- asyncio integration
