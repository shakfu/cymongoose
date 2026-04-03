# WSGI Adapter Internals

This document covers the internal architecture, design decisions, and
known limitations of the `cymongoose.wsgi` module.  For user-facing
documentation see the [WSGI/ASGI Guide](../guide/wsgi.md).

## Architecture Overview

The WSGI adapter bridges two fundamentally different execution models:

- **cymongoose**: single-threaded, non-blocking event loop (C)
- **WSGI**: synchronous, blocking callable (Python)

The adapter uses a `ThreadPoolExecutor` to run WSGI callables in
worker threads.  Results are sent back to the event loop via
`Manager.wakeup()`.

### Response Paths

There are two response paths, selected automatically based on the
accumulated body size during WSGI iteration:

| Path | Trigger | Transport | Latency |
|------|---------|-----------|---------|
| **Buffered** | body < 1 MB (`_STREAM_THRESHOLD`) | Single wakeup (inline or stash) | One round-trip |
| **Streaming** | body >= 1 MB | Per-connection `queue.Queue` + drain wakeups | Per-chunk |

The buffered path uses `conn.reply()` for a single complete response.
The streaming path uses `conn.http_chunk()` with chunked transfer
encoding.

### Wakeup Message Types

All communication from worker threads to the event loop uses
`Manager.wakeup()` with a single-byte prefix:

| Prefix | Name | Payload | Description |
|--------|------|---------|-------------|
| `I` | Inline | `<json_meta>\n<body>` | Complete buffered response, payload fits in wakeup buffer |
| `S` | Stash | `<uuid_hex>` | Complete buffered response, payload stored in `_stash` dict |
| `H` | Header inline | `<raw_http_headers>` | Start chunked response, headers fit in wakeup buffer |
| `h` | Header stash | `<uuid_hex>` | Start chunked response, headers stored in `_stash` dict |
| `D` | Drain | (empty) | Signal that chunks are waiting in the stream queue |

### Wakeup Size Limit

`mg_wakeup()` transmits data over a socketpair using non-blocking
`send()`.  The effective send buffer varies by platform:

| Platform | Approximate limit |
|----------|-------------------|
| macOS | ~9 KB |
| Linux | ~64 KB |

Payloads exceeding `_WAKEUP_MAX_BYTES` (8 KB) are stored in a
thread-safe `_stash` dict and only a 32-byte UUID key is sent via
wakeup.  If the wakeup payload exceeds the socket buffer, the
`send()` silently fails and the data is lost -- this is why the 8 KB
threshold is conservative.

## Streaming Design

### Queue-Based Transport

Each streaming response gets a per-connection `queue.Queue(maxsize=16)`
stored in `_streams[conn_id]`.  The worker pushes chunks into the
queue and sends a tiny `D` wakeup to notify the event loop.  The
event loop drains all available chunks and sends them via
`conn.http_chunk()`.

A `None` sentinel in the queue signals end-of-stream.  The event loop
sends an empty chunk to close the chunked response and removes the
stream entry.

### Back-Pressure

The bounded queue (`maxsize=16`) provides natural back-pressure.
When the queue is full, the worker blocks on `q.put(timeout=5.0)`.
If the put times out (e.g. because the connection closed and the
queue is no longer being drained), the worker aborts cleanly.

### Chunk Batching

Fast generators that yield many small chunks (e.g. 5-byte strings in a
tight loop) are batched up to `_STREAM_BATCH_SIZE` (256 KB) before
being pushed to the queue.  This prevents flooding the wakeup
socketpair with hundreds of tiny drain notifications.

### Disconnect Cleanup

When a connection closes, `MG_EV_CLOSE` fires and the event handler
pops the stream entry from `_streams`.  The queue object and its
contents are garbage-collected.  The worker, which holds a local
reference to the queue, may still push a few more chunks that will
never be consumed.  The `put(timeout=5.0)` ensures the worker
eventually aborts instead of blocking forever.

## Thread Safety

### GIL-Dependent Dict Access

The `_streams` dict is accessed from both the event loop thread
(reads and pops in `_drain_stream`, `MG_EV_CLOSE`) and worker threads
(writes in `_worker_stream`, reads in error handling).  No explicit
lock protects it.

This is safe in CPython because dict operations (`__getitem__`,
`__setitem__`, `pop`) are atomic under the GIL.  It is also safe in
PyPy for the same reason.  However, this is an implementation detail
of these interpreters, not a language-level guarantee.  If cymongoose
ever targets a GIL-free Python (PEP 703), this dict must be protected
with a lock.

The `_stash` dict, by contrast, is protected by `_stash_lock` because
it was designed before the queue approach and the explicit lock is
harmless.

### Thread-Safe Methods

Only `Manager.wakeup()` is safe to call from worker threads.  All
`Connection` methods (`reply`, `send`, `http_chunk`) are called
exclusively from the event loop thread via wakeup dispatch.

## Known Limitations

### Response Buffering Below Threshold

Responses under 1 MB are fully buffered in memory before sending.
This is intentional -- the buffered path is faster (single wakeup,
single `conn.reply()`) and covers the vast majority of web API
responses.  The 1 MB threshold is not currently configurable.

### Disconnect Stall

When a client disconnects mid-stream, the worker blocks on
`q.put(timeout=stream_timeout)` until the timeout expires.  During
this time it occupies a thread pool slot.  With `workers=4` and 4
simultaneous disconnects, the server is unresponsive for up to
``stream_timeout`` seconds.

The default is 5 seconds, which avoids false positives on slow
networks.  Reduce it for latency-sensitive deployments:

```python
# Abort stalled workers after 1 second instead of 5
server = WSGIServer(app, workers=8, stream_timeout=1.0)

# Or via the one-liner
serve(app, workers=8, stream_timeout=1.0)
```

### Truncated Response on Mid-Stream Error

If the WSGI application raises an exception after streaming has
started (headers already sent), the worker puts `None` in the queue
to end the chunked response.  The client receives a truncated
response with no error indication -- the 200 status code is already
on the wire.

This is inherent to HTTP chunked encoding and matches the behavior
of production WSGI servers (gunicorn, uwsgi, waitress).

### Duplicate Response Headers

PEP 3333 allows multiple response headers with the same name (e.g.
`Set-Cookie`).  The buffered path converts headers to a
`dict[str, str]` before calling `conn.reply()`, which collapses
duplicates to the last value.  The streaming path sends headers via
raw `conn.send()` and preserves all headers.

A full fix requires extending the Cython `reply()` API to accept a
list of tuples instead of a dict.

### No Concurrent Streaming Load Test

The test suite covers concurrent buffered requests and single
streaming responses, but does not test multiple simultaneous
streaming responses under load.  Real-world load testing with tools
like `wrk` is recommended before deploying the streaming path in
production.

## Constants Reference

| Constant | Value | Description |
|----------|-------|-------------|
| `_WAKEUP_MAX_BYTES` | 8 KB | Max inline wakeup payload |
| `_STREAM_THRESHOLD` | 1 MB | Body size that triggers streaming |
| `_STREAM_QUEUE_SIZE` | 16 | Max pending chunks in stream queue |
| `_STREAM_BATCH_SIZE` | 256 KB | Max bytes batched before queue push |
| `_STREAM_PUT_TIMEOUT` | 5.0 s | Timeout for queue put (deadlock prevention) |

## See Also

- [WSGI/ASGI Guide](../guide/wsgi.md) -- user-facing documentation
- [Threading Guide](../advanced/threading.md) -- wakeup payload limits
- [Performance Tuning](../advanced/performance.md) -- benchmarking
