# TODO

## Framework Adapters

- [x] **ASGI: Lifespan sub-protocol** (Low)
  Implemented ASGI lifespan startup/shutdown events. The server runs the
  lifespan coroutine before binding and waits for `startup.complete`.
  Apps that don't support lifespan (raise or return without signaling)
  are detected and the server proceeds normally. Shutdown sends
  `lifespan.shutdown` and waits up to 5s. 5 tests.

- [x] **ASGI: Streaming HTTP responses** (Medium)
  Implemented chunked transfer encoding via `more_body=True` in
  `http.response.body`. Uses wakeup prefixes S/C/E for headers, chunks,
  and end-of-stream. Reuses `_format_chunked_header` from WSGI. 5 tests.

- [x] **ASGI: Streaming backpressure** (Low)
  `asyncio.Semaphore(_STREAM_CONCURRENCY=16)` on `_ConnState` limits
  in-flight streaming wakeups. `send()` acquires before each header/chunk
  wakeup; poll thread releases via `call_soon_threadsafe` after processing.
  1 backpressure test (64 chunks, 4x the limit).
