# TODO

## Framework Adapters

- [x] **WSGI adapter** (High)
  Implemented in `src/cymongoose/wsgi.py`. Thread-pool dispatch with
  `wakeup()` return path, environ construction (PEP 3333), status codes,
  headers, POST bodies, multi-chunk iterators, closeable iterators, and
  error handling. 20 tests in `tests/test_wsgi.py`. Smoke-tested with
  Flask 3.1.

  Open items:

  - [x] **Chunked streaming for large responses** (Medium)
    Responses exceeding `_STREAM_THRESHOLD` (1 MB) now switch from
    buffered mode to chunked transfer encoding. The worker sends
    HTTP headers via a `H` wakeup, then each body chunk via `C`
    wakeups (always stashed), and a final `E` to close. Small
    chunks are batched up to 256 KB to avoid flooding the wakeup
    pipe. 7 streaming tests added (34 total WSGI tests).

  - [x] **Wakeup payload size limits** (Low)
    `mg_wakeup()` uses `send()` with `MSG_NONBLOCKING` over a
    socketpair; the effective send buffer is ~9.2 KB on macOS and
    ~64 KB on Linux. Payloads exceeding `_WAKEUP_MAX_BYTES` (8 KB)
    are now stashed in a thread-safe dict keyed by UUID, and only
    the short key is sent via wakeup. 3 tests added.

  - [x] **`wsgi.file_wrapper` support** (Low)
    Added `FileWrapper` class implementing the PEP 3333
    `wsgi.file_wrapper` protocol. Injected into `environ` so WSGI
    apps can use it for efficient file serving. 4 tests added
    (environ presence, file serving, large files, close() called).

  - [x] **Duplicate response headers** (Medium)
    Replaced `conn.reply()` (which takes `Dict[str, str]`) with raw
    `conn.send()` in `_send_buffered_response`, constructing the
    HTTP response manually from the header list. The streaming path
    already used `conn.send()` for headers. Both paths now preserve
    duplicate headers (e.g. multiple `Set-Cookie`). 2 tests added.

- [ ] **ASGI adapter** (Medium)
  Implement an ASGI server (HTTP + WebSocket sub-protocols) on top of
  AsyncManager. Covers FastAPI, Starlette, Django async, and Quart.
  More complex protocol (lifespan, receive/send callables) but a
  natural fit for cymongoose's async support and native WebSocket
  handling.
