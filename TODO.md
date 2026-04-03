# TODO

## Framework Adapters

- [x] **WSGI adapter** (High)
  Implemented in `src/cymongoose/wsgi.py`. Thread-pool dispatch with
  `wakeup()` return path, environ construction (PEP 3333), status codes,
  headers, POST bodies, multi-chunk iterators, closeable iterators, and
  error handling. 20 tests in `tests/test_wsgi.py`. Smoke-tested with
  Flask 3.1.

  Open items:

  - [ ] **Chunked streaming for large responses** (Medium)
    The entire response body is buffered before sending. For large
    responses (file downloads, streaming generators) use chunked
    transfer encoding to send chunks as the WSGI iterator yields them.

  - [ ] **Wakeup payload size limits** (Low)
    The response is serialised into a single `wakeup()` payload.
    Investigate mongoose's internal buffer limits and add fallback
    (e.g. shared-memory or temp file) for very large responses.

  - [ ] **`wsgi.file_wrapper` support** (Low)
    Implement the optional `wsgi.file_wrapper` optimisation for
    efficient static file serving via `sendfile()`.

  - [ ] **Duplicate response headers** (Medium)
    PEP 3333 allows multiple headers with the same name (e.g.
    `Set-Cookie`). The current dict conversion loses duplicates.
    Switch to a list-of-tuples pass-through or join with `, ` where
    the HTTP spec permits.

- [ ] **ASGI adapter** (Medium)
  Implement an ASGI server (HTTP + WebSocket sub-protocols) on top of
  AsyncManager. Covers FastAPI, Starlette, Django async, and Quart.
  More complex protocol (lifespan, receive/send callables) but a
  natural fit for cymongoose's async support and native WebSocket
  handling.
