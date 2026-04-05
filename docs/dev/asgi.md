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
| `S` | Stream header inline | `<raw_headers>` | Chunked stream: HTTP headers |
| `s` | Stream header stash | `<uuid>` | Chunked stream: headers in `_stash` |
| `C` | Stream chunk inline | `<data>` | Chunked stream: body chunk |
| `c` | Stream chunk stash | `<uuid>` | Chunked stream: body chunk in `_stash` |
| `E` | Stream end | (empty) | Chunked stream: terminating empty chunk |

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
- `streaming`: whether the connection is in chunked streaming mode
- `stream_sem`: `asyncio.Semaphore` for streaming backpressure (created
  lazily on first `more_body=True`)

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

## Lifespan Sub-Protocol

The server runs the lifespan coroutine during `start()` / `stop()`:

1. **Startup**: `start()` creates an `asyncio.Task` that calls
   `app({"type": "lifespan", ...}, receive, send)` and pushes
   `lifespan.startup` into the receive queue.  It then awaits an
   `asyncio.Event` that is set when the app sends
   `lifespan.startup.complete` (or `lifespan.startup.failed`).
   The listener is not bound until startup completes.

2. **Shutdown**: `stop()` pushes `lifespan.shutdown` into the receive
   queue and waits up to 5 seconds for `lifespan.shutdown.complete`.
   The lifespan task is then cancelled.

3. **Unsupported apps**: If the app raises an exception on the lifespan
   scope, or returns without sending any message, the `finally` block
   in the lifespan coroutine detects that `startup_complete` was never
   set, marks `_lifespan_supported = False`, and unblocks the waiter.
   The server proceeds normally without lifespan.

## Streaming HTTP Responses

When `http.response.body` arrives with `more_body=True`, the adapter
switches to chunked transfer encoding:

1. **First body with `more_body=True`**: headers are formatted using
   `_format_chunked_header()` (reused from the WSGI adapter) with
   `Transfer-Encoding: chunked`, and sent via an `S`/`s` wakeup.
   The first body chunk follows as a `C`/`c` wakeup.

2. **Subsequent bodies**: each chunk is sent as a `C`/`c` wakeup.
   Empty bodies are skipped.

3. **Final body** (`more_body=False` or omitted): the last chunk (if
   non-empty) is sent, then an `E` wakeup triggers `http_chunk(b"")`
   to send the terminating empty chunk.

Responses that never set `more_body=True` use the original buffered
path (`R`/`r` wakeup with JSON-serialised headers + body).

### Backpressure

An `asyncio.Semaphore` with capacity `_STREAM_CONCURRENCY` (16) is
created on the `_ConnState` when streaming begins.  The async `send()`
acquires a permit before each `S` or `C` wakeup.  The poll thread
releases the permit via `loop.call_soon_threadsafe(sem.release)` after
processing the wakeup in `_handle_stream_header` or
`_handle_stream_chunk`.

This bounds in-flight wakeups to 16 per connection.  If the app calls
`await send()` faster than the poll thread can drain, the semaphore
blocks the coroutine -- providing natural backpressure without
explicit queues.

The `E` (stream end) wakeup does not acquire a permit since it is
small, terminal, and must always go through.

## Known Limitations

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
